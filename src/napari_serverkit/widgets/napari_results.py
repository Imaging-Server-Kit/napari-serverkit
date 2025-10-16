"""
Implements the Results interface for Napari's viewer.
"""

from typing import Callable, Optional
import numpy as np

import napari
import napari.layers
from napari.utils.notifications import show_error, show_info, show_warning

from imaging_server_kit.core.results import Results, LayerStackBase


def create(viewer, layer) -> None:
    kind = layer.kind
    data = layer.data
    name = layer.name
    meta = layer.meta

    # Sanitize meta
    valid_meta = meta.copy()
    if "tile_params" in valid_meta:
        valid_meta.pop("tile_params")
    else:
        valid_meta = meta

    if kind == "image":
        viewer.add_image(data, name=name, **valid_meta)
    elif kind in ["mask", "instance_mask"]:
        viewer.add_labels(data.astype(np.uint16), name=name, **valid_meta)
    elif kind == "points":
        viewer.add_points(data, name=name, **valid_meta)
    elif kind in ["boxes", "paths"]:
        if "shape_type" in meta:  # Make sure it isn't used twice
            meta.pop("shape_type")
        if kind == "boxes":
            viewer.add_shapes(data, name=name, shape_type="rectangle", **valid_meta)
        elif kind == "paths":
            viewer.add_shapes(data, name=name, shape_type="path", **valid_meta)
    elif kind == "vectors":
        viewer.add_vectors(data, name=name, **valid_meta)
    elif kind == "tracks":
        viewer.add_tracks(data, name=name, **valid_meta)


def update(viewer, layer) -> None:
    # Napari layers
    if layer.kind in [
        "image",
        "mask",
        "instance_mask",
        "points",
        "boxes",
        "paths",
        "vectors",
        "tracks",
    ]:
        for l in viewer.layers:
            if l.name == layer.name:
                l.data = layer.data
                l.refresh()

    # Notifications
    elif layer.kind == "notification":
        # if isinstance(layer, sk.Notification):
        level = layer.meta.get("level", "info")
        if level == "error":
            show_error(layer.data)
        elif level == "warning":
            show_warning(layer.data)
        else:
            show_info(layer.data)

    # Text shown in the viewer
    elif layer.kind in ["float", "int", "bool", "str", "dropdown"]:
        viewer.text_overlay.visible = True
        viewer.text_overlay.text = str(layer.data)


def read(viewer, layer) -> None:
    # Nothing to do here (for now)
    pass


def delete(viewer, layer_name) -> None:
    for idx, l in enumerate(viewer.layers):
        if l.name == layer_name:
            viewer.layers.pop(idx)


def napari_layer_to_results_layer(napari_layer, results: Results):
    if isinstance(napari_layer, napari.layers.Image):
        results.create(kind="image", data=napari_layer.data, name=napari_layer.name)
    elif isinstance(napari_layer, napari.layers.Labels):
        results.create(kind="mask", data=napari_layer.data, name=napari_layer.name)
    elif isinstance(napari_layer, napari.layers.Points):
        results.create(kind="points", data=napari_layer.data, name=napari_layer.name)
    elif isinstance(napari_layer, napari.layers.Tracks):
        results.create(kind="tracks", data=napari_layer.data, name=napari_layer.name)
    elif isinstance(napari_layer, napari.layers.Vectors):
        results.create(kind="vectors", data=napari_layer.data, name=napari_layer.name)
    elif isinstance(napari_layer, napari.layers.Shapes):
        # TODO: handle this special case cleanly
        pass
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
        layer = self.results.create(kind=kind, data=data, name=name, meta=meta)
        create(self.viewer, layer)
        return layer

    def read(self, layer_name):
        layer = self.results.read(layer_name)
        read(self.viewer, layer)
        return layer

    def update(self, layer_name, layer_data: np.ndarray):
        layer = self.results.update(layer_name, layer_data)
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
