"""
Implements the LayerStackBase interface for Napari's viewer.
"""

from typing import Callable, Dict, List, Optional
from dataclasses import dataclass
import numpy as np

import napari
import napari.layers
from napari.utils.notifications import show_error, show_info, show_warning
from qtpy.QtWidgets import QProgressBar

from imaging_server_kit.core.results import Results, LayerStackBase, DataLayer


def _set_layer_attributes_from_meta(meta: Dict, napari_layer: napari.layers.Layer):
    # Set the features first
    if "features" in meta:
        value = meta["features"]
        try:
            setattr(napari_layer, "features", value)
        except:
            print("Could not set layer features.")

    for key, value in meta.items():
        if key not in ["tile_params", "name", "features", "ndim"]:
            try:
                setattr(napari_layer, key, value)
            except:
                print("Could not set this layer property: ", key)


def create(viewer, layer: DataLayer) -> None:
    if layer.data is None:
        return
    
    kind = layer.kind
    data = layer.data
    name = layer.name
    meta = layer.meta
    
    napari_layer = None
    if kind == "image":
        napari_layer = viewer.add_image(data, name=name)
    elif kind == "mask":
        napari_layer = viewer.add_labels(data.astype(np.uint16), name=name)
    elif kind == "points":
        napari_layer = viewer.add_points(data, name=name)
    elif kind in ["boxes", "paths"]:
        if "shape_type" in meta:  # Make sure it isn't used twice
            meta.pop("shape_type")
        if kind == "boxes":
            napari_layer = viewer.add_shapes(data, name=name, shape_type="rectangle")
        elif kind == "paths":
            napari_layer = viewer.add_shapes(data, name=name, shape_type="path")
    elif kind == "vectors":
        napari_layer = viewer.add_vectors(data, name=name)
    elif kind == "tracks":
        napari_layer = viewer.add_tracks(data, name=name)

    if napari_layer is not None:
        _set_layer_attributes_from_meta(meta, napari_layer)
        napari_layer.refresh()


@dataclass
class UpdateContext:
    viewer: napari.Viewer
    layer: DataLayer
    pbar: QProgressBar


def _napari_layer_update(ctx: UpdateContext):
    if not ctx.layer.name in [l.name for l in ctx.viewer.layers]:
        create(ctx.viewer, ctx.layer)
    else:
        for l in ctx.viewer.layers:
            if l.name == ctx.layer.name:
                if ctx.layer.data is not None:
                    # Assign to the Napari layer data the data from the corresponding context layer
                    l.data = ctx.layer.data
                    _set_layer_attributes_from_meta(ctx.layer.meta, l)
                    l.refresh()


def _notification_update(ctx: UpdateContext):
    if ctx.layer.data is not None:
        level = ctx.layer.meta.get("level", "info")
        if level == "error":
            show_error(ctx.layer.data)
        elif level == "warning":
            show_warning(ctx.layer.data)
        else:
            show_info(ctx.layer.data)


def _textlayer_update(ctx: UpdateContext):
    ctx.viewer.text_overlay.visible = True
    ctx.viewer.text_overlay.text = str(ctx.layer.data)


def _pbar_update(ctx: UpdateContext):
    if ctx.layer.data is not None:
        ctx.pbar.setValue(ctx.layer.data)
        ctx.pbar.setMaximum(ctx.layer.meta["max_val"])


def update(viewer, layer: Optional[DataLayer], pbar: QProgressBar) -> None:
    """Based on the kind of layer, execute the right update function."""
    if layer is None:
        return

    update_hooks = {
        "image": _napari_layer_update,
        "mask": _napari_layer_update,
        "points": _napari_layer_update,
        "boxes": _napari_layer_update,
        "paths": _napari_layer_update,
        "vectors": _napari_layer_update,
        "tracks": _napari_layer_update,
        "notification": _notification_update,
        "float": _textlayer_update,
        "int": _textlayer_update,
        "bool": _textlayer_update,
        "str": _textlayer_update,
        "choice": _textlayer_update,
        "progress": _pbar_update,
    }
    update_func: Optional[Callable] = update_hooks.get(layer.kind)
    if update_func is not None:
        ctx = UpdateContext(viewer=viewer, layer=layer, pbar=pbar)
        update_func(ctx)


def read(viewer, layer) -> None:
    # Nothing to do here (for now)
    pass


def delete(viewer, name) -> None:
    for idx, l in enumerate(viewer.layers):
        if l.name == name:
            viewer.layers.pop(idx)


def napari_layer_to_results_layer(napari_layer, results: Results) -> Results:
    # layer_to_kind = {}  # TODO: better approach...
    if isinstance(napari_layer, napari.layers.Image):
        kind = "image"
        data = napari_layer.data
    elif isinstance(napari_layer, napari.layers.Labels):
        kind = "mask"
        data = napari_layer.data
    elif isinstance(napari_layer, napari.layers.Points):
        kind = "points"
        data = napari_layer.data
    elif isinstance(napari_layer, napari.layers.Tracks):
        kind = "tracks"
        data = napari_layer.data
    elif isinstance(napari_layer, napari.layers.Vectors):
        kind = "vectors"
        data = napari_layer.data
    elif isinstance(napari_layer, napari.layers.Shapes):
        # TODO: For now, when a `Shapes` layer is created, we assume it's meant to contain boxes (rectangles).
        # So, it won't work with algorithms that would use annotated "Paths" as input (quite rare).
        kind = "boxes"
        data = None  # instead of []
    else:
        print("Could not convert this layer: ", napari_layer)
        return results

    results.create(kind=kind, data=data, name=napari_layer.name)
    
    return results


class NapariResults(LayerStackBase):
    """Works like Results, but behaves in sync with a Napari Viewer."""

    def __init__(
        self,
        viewer: Optional[napari.Viewer] = None,
        pbar: Optional[QProgressBar] = None,
    ):
        # Create a Viewer
        if viewer is None:
            self.viewer = napari.Viewer()
        else:
            self.viewer = viewer

        # Progress bar (shared from ServerKitWidget)
        if pbar is None:
            self.pbar = QProgressBar()
        else:
            self.pbar = pbar

        # Create a Results object
        self.results = Results()

        # Instanciate layers and add the existing Napari viewer layers to results
        for l in self.viewer.layers:
            self._handle_new_layer(l)

        # Connect viewer events (layer add/remove/rename)
        self.connect_layer_added_event(self.sync_layer_added)
        self.connect_layer_removed_event(self.sync_layer_removed)
        self.connect_layer_renamed_event(self.sync_layer_renamed)

    def sync_layer_added(self, e):
        added_napari_layer = e.source[-1]
        self._handle_new_layer(added_napari_layer)

    def sync_layer_renamed(self, e):
        viewer_layer_names = [l.name for l in self.viewer.layers]
        new_name = e.source
        for layer in self.results:
            if layer.name not in viewer_layer_names:
                layer.name = new_name

    def sync_layer_removed(self, e):
        layer_name = e.value.name
        self.delete(layer_name)

    def _handle_new_layer(self, napari_layer):
        existing_layer = self.read(napari_layer.name)
        if existing_layer is None:
            self.results = napari_layer_to_results_layer(napari_layer, self.results)

    @property
    def layers(self):
        return self.results.layers

    @property
    def pixel_domain(self) -> List[int]:
        return self.results.pixel_domain

    def __iter__(self):
        return iter(self.results.layers)

    def __getitem__(self, idx):
        return self.results.layers[idx]

    def create(self, kind, name=None, **kwargs) -> DataLayer:
        layer = self.results.create(kind=kind, name=name, **kwargs)
        create(self.viewer, layer)
        return layer

    def read(self, name: str) -> Optional[DataLayer]:
        layer = self.results.read(name)
        read(self.viewer, layer)
        return layer

    def merge(self, layer_stack: Optional[LayerStackBase]) -> None:
        if layer_stack is None:
            return

        dst_layers = []
        for src_layer in layer_stack:
            dst_layer = self.read(src_layer.name)
            if dst_layer is None:
                dst_layer = self.create(
                    kind=src_layer.kind,
                    name=src_layer.name,
                    meta=src_layer.meta,
                    merger=src_layer.merger_type,
                    data_serializer=src_layer.data_serializer_type,
                )
            dst_layers.append(dst_layer)

        for src_layer, dst_layer in zip(layer_stack, dst_layers):
            dst_layer.merge(src_layer)
            update(self.viewer, dst_layer, self.pbar)

    def delete(self, name) -> None:
        self.results.delete(name)
        delete(self.viewer, name)

    def connect_layer_renamed_event(self, func: Callable):
        self.viewer.layers.events.inserted.connect(
            lambda e: e.value.events.name.connect(func)
        )

    def connect_layer_added_event(self, func: Callable):
        self.viewer.layers.events.inserted.connect(func)

    def connect_layer_removed_event(self, func: Callable):
        self.viewer.layers.events.removed.connect(func)
