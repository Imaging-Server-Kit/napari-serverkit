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

from imaging_server_kit.core.results import Results, DataLayer


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


@dataclass
class UpdateContext:
    viewer: napari.Viewer
    layer: DataLayer
    pbar: QProgressBar


def _napari_layer_update(ctx: UpdateContext):
    for l in ctx.viewer.layers:
        if l.name == ctx.layer.name:
            if ctx.layer.data is not None:
                # Assign to the Napari layer data the data from the corresponding context layer
                l.data = ctx.layer.data
                _set_layer_attributes_from_meta(ctx.layer.meta, l)


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


class NapariResults(Results):
    """Works like Results, but behaves in sync with a Napari Viewer."""

    def __init__(
        self,
        viewer: Optional[napari.Viewer] = None,
        pbar: Optional[QProgressBar] = None,
        layers: Optional[List[DataLayer]] = None,
    ):
        super().__init__(layers=layers)
        
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

        # Instanciate layers and add the existing Napari viewer layers to results
        for l in self.viewer.layers:
            self._handle_new_layer(l)

        # Connect viewer events (layer add/remove/rename)
        self.connect_layer_added_event(self.sync_layer_added)
        self.connect_layer_removed_event(self.sync_layer_removed)
        self.connect_layer_renamed_event(self.sync_layer_renamed)

    def connect_layer_renamed_event(self, func: Callable):
        self.viewer.layers.events.inserted.connect(
            lambda e: e.value.events.name.connect(func)
        )

    def connect_layer_added_event(self, func: Callable):
        self.viewer.layers.events.inserted.connect(func)

    def connect_layer_removed_event(self, func: Callable):
        self.viewer.layers.events.removed.connect(func)

    def sync_layer_added(self, e):
        added_napari_layer = e.source[-1]
        self._handle_new_layer(added_napari_layer)

    def sync_layer_renamed(self, e):
        viewer_layer_names = [l.name for l in self.viewer.layers]
        new_name = e.source
        for layer in self.layers:
            if layer.name not in viewer_layer_names:
                layer.name = new_name

    def sync_layer_removed(self, e):
        layer_name = e.value.name
        self.delete(layer_name)

    def _handle_new_layer(self, napari_layer):
        existing_layer = self.read(napari_layer.name)
        if existing_layer is not None:
            return
            # self.results = napari_layer_to_results_layer(napari_layer, self.results)
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
            return

        # Keep track of the new Napari layer in the layer stack (even without any layer metadata)
        self.create(kind=kind, name=napari_layer.name, data=data)
            
    def post_create(self, layer: DataLayer) -> DataLayer:
        if layer.data is None:
            return layer
        
        kind = layer.kind
        data = layer.data
        name = layer.name
        meta = layer.meta
        
        napari_layer = None
        if kind == "image":
            napari_layer = self.viewer.add_image(data, name=name)
        elif kind == "mask":
            napari_layer = self.viewer.add_labels(data.astype(np.uint16), name=name)
        elif kind == "points":
            napari_layer = self.viewer.add_points(data, name=name)
        elif kind in ["boxes", "paths"]:
            if "shape_type" in meta:  # Make sure it isn't used twice
                meta.pop("shape_type")
            if kind == "boxes":
                napari_layer = self.viewer.add_shapes(data, name=name, shape_type="rectangle")
            elif kind == "paths":
                napari_layer = self.viewer.add_shapes(data, name=name, shape_type="path")
        elif kind == "vectors":
            napari_layer = self.viewer.add_vectors(data, name=name)
        elif kind == "tracks":
            napari_layer = self.viewer.add_tracks(data, name=name)

        if napari_layer is not None:
            _set_layer_attributes_from_meta(meta, napari_layer)
        
        return layer

    def post_delete(self, name: str) -> None:
        """Hook called after layer deletion."""
        for idx, l in enumerate(self.viewer.layers):
            if l.name == name:
                self.viewer.layers.pop(idx)

    def post_merge(self, dst_layers: List[DataLayer]) -> None:
        for layer in dst_layers:
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
            
            # Before doint the napari layer update, make sure the viewer layers exist by running post_create..
            # A little weird, but for now the only solution that seems to work!
            if update_func is _napari_layer_update:
                if not layer.name in [l.name for l in self.viewer.layers]:
                    self.post_create(layer)
            
            if update_func is not None:
                ctx = UpdateContext(viewer=self.viewer, layer=layer, pbar=self.pbar)
                update_func(ctx)