"""
Implements the LayerStackBase interface for Napari's viewer.
"""

from typing import Any, Callable, Dict, Optional
import numpy as np

import napari
import napari.layers
from napari.utils.notifications import show_error, show_info, show_warning

from imaging_server_kit.core.results import Results, LayerStackBase, DataLayer


def _set_layer_attributes_from_meta(meta: Dict, layer: DataLayer):
    # Set the features first
    if "features" in meta:
        value = meta["features"]
        try:
            setattr(layer, "features", value)
        except:
            print("Could not set layer features.")
    
    for key, value in meta.items():
        if key not in ["tile_params", "name", "features", "ndim"]:
            try:
                setattr(layer, key, value)
            except:
                print("Could not set this layer property: ", key)


def create(viewer, layer) -> None:
    kind = layer.kind
    data = layer.data
    name = layer.name
    meta = layer.meta

    if kind == "image":
        layer = viewer.add_image(data, name=name)
    elif kind in ["mask", "instance_mask"]:
        layer = viewer.add_labels(data.astype(np.uint16), name=name)
    elif kind == "points":
        layer = viewer.add_points(data, name=name)
    elif kind in ["boxes", "paths"]:
        if "shape_type" in meta:  # Make sure it isn't used twice
            meta.pop("shape_type")
        if kind == "boxes":
            layer = viewer.add_shapes(data, name=name, shape_type="rectangle")
        elif kind == "paths":
            layer = viewer.add_shapes(data, name=name, shape_type="path")
    elif kind == "vectors":
        layer = viewer.add_vectors(data, name=name)
    elif kind == "tracks":
        layer = viewer.add_tracks(data, name=name)

    _set_layer_attributes_from_meta(meta, layer)

    layer.refresh()


def _napari_layer_update(viewer, layer):
    for l in viewer.layers:
        if l.name == layer.name:
            l.data = layer.data
            _set_layer_attributes_from_meta(layer.meta, l)
            l.refresh()


def _notification_update(viewer, layer):
    if layer.data is not None:
        level = layer.meta.get("level", "info")
        if level == "error":
            show_error(layer.data)
        elif level == "warning":
            show_warning(layer.data)
        else:
            show_info(layer.data)


def _textlayer_update(viewer, layer):
    viewer.text_overlay.visible = True
    viewer.text_overlay.text = str(layer.data)


def update(viewer, layer) -> None:
    """Based on the kind of layer, execute the right update function."""
    update_hooks = {
        "image": _napari_layer_update,
        "mask": _napari_layer_update,
        "instance_mask": _napari_layer_update,
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
    }
    update_func: Optional[Callable] = update_hooks.get(layer.kind)
    if update_func is not None:
        update_func(viewer, layer)


def read(viewer, layer) -> None:
    # Nothing to do here (for now)
    pass


def delete(viewer, layer_name) -> None:
    for idx, l in enumerate(viewer.layers):
        if l.name == layer_name:
            viewer.layers.pop(idx)


def napari_layer_to_results_layer(napari_layer, results: Results):
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

    def __init__(self, viewer: Optional[napari.Viewer] = None):
        super().__init__()

        # Create a Results object
        self.results = Results()

        # Create a Viewer
        if viewer is None:
            self.viewer = napari.Viewer()
        else:
            self.viewer = viewer

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
        self.results = napari_layer_to_results_layer(napari_layer, self.results)

    @property
    def layers(self):
        return self.results.layers

    def __iter__(self):
        return iter(self.results.layers)

    def __getitem__(self, idx):
        return self.results.layers[idx]

    def create(self, kind, data, name=None, meta=None):
        layer = self.results.create(kind, data, name, meta) # type: ignore
        create(self.viewer, layer)
        return layer

    def read(self, layer_name):
        layer = self.results.read(layer_name)
        read(self.viewer, layer)
        return layer

    def update(self, layer_name, layer_data: Any, layer_meta: Dict):
        layer = self.results.update(layer_name, layer_data, layer_meta)
        update(self.viewer, layer)
        return layer

    def delete(self, layer_name) -> None:
        self.results.delete(layer_name)
        delete(self.viewer, layer_name)

    def connect_layer_renamed_event(self, func: Callable):
        self.viewer.layers.events.inserted.connect(
            lambda e: e.value.events.name.connect(func)
        )

    def connect_layer_added_event(self, func: Callable):
        self.viewer.layers.events.inserted.connect(func)

    def connect_layer_removed_event(self, func: Callable):
        self.viewer.layers.events.removed.connect(func)
    
    def get_pixel_domain(self) -> np.ndarray:
        return self.results.get_pixel_domain()
