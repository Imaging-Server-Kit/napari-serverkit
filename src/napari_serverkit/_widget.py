from typing import Dict, List

import napari
import napari.layers
import numpy as np
from imaging_server_kit.streaming import initialize_tiled_image
from napari.utils.notifications import show_error, show_info, show_warning
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QWidget,
)

from ._worker import WorkerManager


def is_algo_layered(layer_type: str):
    return layer_type in [
        "image",
        "mask",
        "instance_mask",
        "mask3d",
        "points",
        "points3d",
        "vectors",
        "boxes",
    ]


def is_algo_arrayed(layer_type: str):
    return layer_type in [
        "image",
        "mask",
        "instance_mask",
        "mask3d",
    ]


def is_algo_points(layer_type: str):
    return layer_type in ["points", "points3d"]


def is_algo_mask(layer_type: str):
    return layer_type in ["mask", "mask3d", "instance_mask"]


def is_algo_text(layer_type: str):
    return layer_type in ["class", "text", "scalar", "list"]


class ServerKitAbstractWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        self.layer_box_states = {
            "image": {
                "cbs": [],
                "type": napari.layers.Image,
            },
            "labels": {
                "cbs": [],
                "type": napari.layers.Labels,
            },
            "points": {
                "cbs": [],
                "type": napari.layers.Points,
            },
            "shapes": {
                "cbs": [],
                "type": napari.layers.Shapes,
            },
            "vectors": {
                "cbs": [],
                "type": napari.layers.Vectors,
            },
            "tracks": {
                "cbs": [],
                "type": napari.layers.Tracks,
            },
        }

        self.dynamic_ui_state = {}

        # Layout
        grid_layout = QGridLayout()
        grid_layout.setAlignment(Qt.AlignTop)
        self.setLayout(grid_layout)

        # Sample image
        self.sample_image_btn = QPushButton("Sample image(s)", self)
        self.sample_image_btn.clicked.connect(self._trigger_sample_image_download)
        grid_layout.addWidget(self.sample_image_btn, 2, 0, 1, 3)

        # Algorithm parameters (dynamic UI)
        algo_params_group = QGroupBox()
        algo_params_group.setTitle("Parameters")
        self.algo_params_layout = QGridLayout()
        algo_params_group.setLayout(self.algo_params_layout)
        algo_params_group.layout().setContentsMargins(5, 5, 5, 5)
        grid_layout.addWidget(algo_params_group, 4, 0, 1, 3)

        # Run button
        self.run_btn = QPushButton("Run", self)
        self.run_btn.clicked.connect(self._trigger_run_algorithm)
        grid_layout.addWidget(self.run_btn, 6, 0, 1, 3)

        # Layer callbacks
        self.viewer.layers.events.inserted.connect(
            lambda e: e.value.events.name.connect(self._on_layer_change)
        )
        self.viewer.layers.events.inserted.connect(self._on_layer_change)
        self.viewer.layers.events.removed.connect(self._on_layer_change)
        self._on_layer_change(None)

        # Worker manager
        self.worker_manager = WorkerManager(
            grayout_ui_list=[algo_params_group, self.run_btn]
        )
        cancel_btn = self.worker_manager.cancel_btn
        grid_layout.addWidget(cancel_btn, 7, 0, 1, 3)
        self.pbar = self.worker_manager.pbar
        grid_layout.addWidget(self.pbar, 8, 0, 1, 3)

    def _on_layer_change(self, e):
        for cbs_values in self.layer_box_states.values():
            for cb in cbs_values.get("cbs"):
                cb.clear()
                for layer in self.viewer.layers:
                    if isinstance(layer, cbs_values.get("type")):
                        cb.addItem(layer.name, layer.data)
                        break

    def _thread_returned(self, payload: List):
        if payload is None:
            return

        if len(payload) == 0:
            return

        self.viewer.text_overlay.visible = False

        for layer_data, layer_params, layer_type in payload:
            if is_algo_layered(layer_type):
                self._handle_layered_algo_type(layer_type, layer_data, layer_params)
            else:
                self._handle_special_algo(layer_type, layer_data, layer_params)

    def _find_existing_layer(self, layer_name):
        for layer in self.viewer.layers:
            if layer.name == layer_name:
                return layer

    def _handle_layered_algo_type(self, layer_type, layer_data, layer_params):
        layer_name = layer_params.pop("name")
        if layer_name is not None:
            existing_layer = self._find_existing_layer(layer_name)
        else:
            print("Algo output doesn't have a layer name!")
            return  # TODO: should we raise instead?

        tile_params = layer_params.get("tile_params")
        algo_is_tiled = tile_params is not None

        if existing_layer is None:
            if algo_is_tiled:
                if is_algo_arrayed(layer_type):
                    image_layer_data = initialize_tiled_image(tile_params)
                else:
                    image_layer_data = layer_data  # For points, vectors, boxes - this should get filtered out in the next step
                valid_layer_params = layer_params.copy()
                valid_layer_params.pop("tile_params")
            else:
                image_layer_data = layer_data
                valid_layer_params = layer_params

            existing_layer = self._add_layer_by_type(
                layer_type,
                image_layer_data,
                layer_name,
                valid_layer_params,
            )

        if algo_is_tiled:
            self._handle_tiled_algo(layer_type, tile_params, existing_layer, layer_data)
        else:
            existing_layer.data = layer_data

    def _handle_arrayed_tiled_algo(self, tile_params, existing_layer, layer_data):
        tile_size = tile_params.get("tile_size_px")
        tile_pos_z = tile_params.get("pos_z")
        algo_is_3d = tile_pos_z is not None
        tile_pos_y = tile_params.get("pos_y")
        tile_pos_x = tile_params.get("pos_x")
        max_y = tile_pos_y + tile_size
        max_x = tile_pos_x + tile_size
        if algo_is_3d:
            max_z = tile_pos_z + tile_size
        try:
            if algo_is_3d:
                existing_layer.data[
                    tile_pos_z:max_z, tile_pos_y:max_y, tile_pos_x:max_x
                ] = layer_data
            else:  # 2D / RGB cases
                existing_layer.data[tile_pos_x:max_x, tile_pos_y:max_y] = layer_data
        except:
            print(
                "Attempted to write tiles outside of the image."
            )  # TODO: why does this happen?

    def _handle_points_tiled_algo(self, tile_params, existing_layer, layer_data):
        tile_size = tile_params.get("tile_size_px")
        tile_pos_z = tile_params.get("pos_z")
        algo_is_3d = tile_pos_z is not None
        tile_pos_y = tile_params.get("pos_y")
        tile_pos_x = tile_params.get("pos_x")
        max_y = tile_pos_y + tile_size
        max_x = tile_pos_x + tile_size
        if algo_is_3d:
            max_z = tile_pos_z + tile_size
        if len(layer_data):
            if tile_pos_z:
                zvals = existing_layer.data[:, 0]
                yvals = existing_layer.data[:, 1]
                xvals = existing_layer.data[:, 2]
                filt = (
                    (tile_pos_x <= xvals)
                    & (xvals < max_x)
                    & (tile_pos_y <= yvals)
                    & (yvals < max_y)
                    & (tile_pos_z <= zvals)
                    & (zvals < max_z)
                )
                layer_data[:, 0] += tile_pos_z
                layer_data[:, 1] += tile_pos_y
                layer_data[:, 2] += tile_pos_x
            else:
                xvals = existing_layer.data[:, 0]
                yvals = existing_layer.data[:, 1]
                filt = (
                    (tile_pos_x <= xvals)
                    & (xvals < max_x)
                    & (tile_pos_y <= yvals)
                    & (yvals < max_y)
                )
                layer_data[:, 0] += tile_pos_x
                layer_data[:, 1] += tile_pos_y

            existing_layer.data = np.vstack((existing_layer.data[~filt], layer_data))

    def _handle_vectors_tiled_algo(self, tile_params, existing_layer, layer_data):
        tile_size = tile_params.get("tile_size_px")
        tile_pos_z = tile_params.get("pos_z")
        algo_is_3d = tile_pos_z is not None
        tile_pos_y = tile_params.get("pos_y")
        tile_pos_x = tile_params.get("pos_x")
        max_y = tile_pos_y + tile_size
        max_x = tile_pos_x + tile_size
        if algo_is_3d:
            max_z = tile_pos_z + tile_size
        if len(layer_data):
            if tile_pos_z:
                # TODO: test this
                zvals = existing_layer.data[:, 0, 0][..., np.newaxis]
                yvals = existing_layer.data[:, 0, 1][..., np.newaxis]
                xvals = existing_layer.data[:, 0, 2][..., np.newaxis]
                filt = (
                    (tile_pos_x <= xvals)
                    & (xvals < max_x)
                    & (tile_pos_y <= yvals)
                    & (yvals < max_y)
                    & (tile_pos_z <= zvals)
                    & (zvals < max_z)
                )
                layer_data[:, 0, 0] += tile_pos_z
                layer_data[:, 0, 1] += tile_pos_y
                layer_data[:, 0, 2] += tile_pos_x
            else:
                xvals = existing_layer.data[:, 0, 0][..., np.newaxis]
                yvals = existing_layer.data[:, 0, 1][..., np.newaxis]
                filt = (
                    (tile_pos_x <= xvals)
                    & (xvals < max_x)
                    & (tile_pos_y <= yvals)
                    & (yvals < max_y)
                )
                layer_data[:, 0, 0] += tile_pos_x
                layer_data[:, 0, 1] += tile_pos_y

            filt = np.all(filt, axis=1)

            existing_layer.data = np.vstack((existing_layer.data[~filt], layer_data))

    def _handle_boxes_tiled_algo(self, tile_params, existing_layer, layer_data):
        tile_size = tile_params.get("tile_size_px")
        tile_pos_z = tile_params.get("pos_z")
        algo_is_3d = tile_pos_z is not None
        tile_pos_y = tile_params.get("pos_y")
        tile_pos_x = tile_params.get("pos_x")
        max_y = tile_pos_y + tile_size
        max_x = tile_pos_x + tile_size
        if algo_is_3d:
            max_z = tile_pos_z + tile_size
        if len(layer_data):
            if tile_pos_z:
                raise NotImplementedError("3D boxes are not supported.")

            xvals = np.asarray(existing_layer.data)[:, :, 0]
            yvals = np.asarray(existing_layer.data)[:, :, 1]
            filt = (
                (tile_pos_x <= xvals)
                & (xvals < max_x)
                & (tile_pos_y <= yvals)
                & (yvals < max_y)
            )
            layer_data[:, :, 0] += tile_pos_x
            layer_data[:, :, 1] += tile_pos_y

            filt = np.all(filt, axis=1)

            existing_layer.data = np.vstack(
                (np.asarray(existing_layer.data)[~filt], layer_data)
            )

    def _handle_tiled_algo(self, layer_type, tile_params, existing_layer, layer_data):
        if is_algo_arrayed(layer_type):
            self._handle_arrayed_tiled_algo(tile_params, existing_layer, layer_data)
        elif is_algo_points(layer_type):
            self._handle_points_tiled_algo(tile_params, existing_layer, layer_data)
        elif layer_type == "vectors":
            self._handle_vectors_tiled_algo(tile_params, existing_layer, layer_data)
        elif layer_type == "boxes":
            self._handle_boxes_tiled_algo(tile_params, existing_layer, layer_data)
        else:
            print(f"{layer_type} not implemented in tiled mode.")

        # Update the progress bar (TODO: weird to do it here..)
        self.pbar.setMaximum(tile_params.get("n_tiles"))
        self.pbar.setValue(tile_params.get("tile_idx"))

    def _handle_special_algo(self, algo_type, layer_data, layer_params):
        if algo_type == "notification":
            notification_level = layer_params.get("level")
            if notification_level == "error":
                show_error(layer_data)
            elif notification_level == "warning":
                show_warning(layer_data)
            else:
                show_info(layer_data)
        elif is_algo_text(algo_type):
            self.viewer.text_overlay.visible = True
            self.viewer.text_overlay.text = str(layer_data)
        else:
            show_warning(f"Unhandled layer type: {algo_type}")

    def _update_params_layout(self, algo_params):
        # Clean-up the previous dynamic UI layout
        for i in reversed(range(self.algo_params_layout.count())):
            self.algo_params_layout.itemAt(i).widget().setParent(None)

        # Generate the new dynamic UI state and layout
        self.dynamic_ui_state = {}
        for k, (param_name, param_values) in enumerate(
            algo_params["properties"].items()
        ):
            # Parameter name
            qt_label = QLabel(param_values.get("title"))
            self.algo_params_layout.addWidget(qt_label, k, 0)

            # Add the right UI element based on the retreived "widget type" spec.
            param_widget_type = param_values.get("widget_type")

            if param_widget_type in list(self.layer_box_states.keys()):
                qt_widget = QComboBox()
                self.layer_box_states[param_widget_type].get("cbs").append(qt_widget)
            elif param_widget_type == "dropdown":
                qt_widget = QComboBox()
                # If there is only one element, we get a `const` attribute instead of `enum`
                if param_values.get("enum") is None:
                    qt_widget.addItem(param_values.get("const"))
                else:
                    qt_widget.addItems(param_values.get("enum"))
                if param_values.get("auto_call"):
                    qt_widget.currentTextChanged.connect(self._trigger_run_algorithm)
            elif param_widget_type == "int":
                qt_widget = QSpinBox()
                qt_widget.setMinimum(param_values.get("minimum"))
                qt_widget.setMaximum(param_values.get("maximum"))
                qt_widget.setValue(param_values.get("default"))
                if param_values.get("step"):
                    qt_widget.setSingleStep(param_values.get("step"))
                if param_values.get("auto_call"):
                    qt_widget.valueChanged.connect(self._trigger_run_algorithm)
            elif param_widget_type == "float":
                qt_widget = QDoubleSpinBox()
                qt_widget.setMinimum(param_values.get("minimum"))
                qt_widget.setMaximum(param_values.get("maximum"))
                qt_widget.setValue(param_values.get("default"))
                if param_values.get("step"):
                    qt_widget.setSingleStep(param_values.get("step"))
                if param_values.get("auto_call"):
                    qt_widget.valueChanged.connect(self._trigger_run_algorithm)
            elif param_widget_type == "bool":
                qt_widget = QCheckBox()
                qt_widget.setChecked(param_values.get("default"))
                if param_values.get("auto_call"):
                    qt_widget.stateChanged.connect(self._trigger_run_algorithm)
            elif param_widget_type == "str":
                qt_widget = QLineEdit()
                qt_widget.setText(param_values.get("default"))
            else:
                continue

            self.algo_params_layout.addWidget(qt_widget, k, 1)

            self.dynamic_ui_state[param_name] = (param_widget_type, qt_widget)

        self._on_layer_change(None)  # Refresh dropdowns in new UI

    def _add_layer_by_type(self, layer_type, layer_data, layer_name, layer_params):
        if layer_type == "image":
            added_layer = self.viewer.add_image(
                layer_data, name=layer_name, **layer_params
            )
        elif is_algo_mask(layer_type):
            added_layer = self.viewer.add_labels(
                layer_data, name=layer_name, **layer_params
            )
        elif layer_type == "boxes":
            added_layer = self.viewer.add_shapes(
                layer_data, name=layer_name, **layer_params
            )
        elif is_algo_points(layer_type):
            added_layer = self.viewer.add_points(
                layer_data, name=layer_name, **layer_params
            )
        elif layer_type == "vectors":
            added_layer = self.viewer.add_vectors(
                layer_data, name=layer_name, **layer_params
            )
        elif layer_type == "tracks":
            added_layer = self.viewer.add_tracks(
                layer_data, name=layer_name, **layer_params
            )
        return added_layer

    def _algo_params_from_dynamic_ui(self) -> Dict:
        # Returns a Json dict representation of the parameter values
        algo_params = {}
        for param_name, (param_widget_type, qt_widget) in self.dynamic_ui_state.items():
            if param_widget_type in [
                "image",
                "mask",
                "shapes",
                "points",
                "vectors",
                "tracks",
            ]:
                if qt_widget.currentText():
                    param_value = np.asarray(
                        self.viewer.layers[qt_widget.currentText()].data
                    )
            elif param_widget_type == "dropdown":
                param_value = qt_widget.currentText()
            elif param_widget_type == "int":
                param_value = int(qt_widget.value())
            elif param_widget_type == "float":
                param_value = float(qt_widget.value())
            elif param_widget_type == "str":
                param_value = qt_widget.text()
            elif param_widget_type == "bool":
                param_value = qt_widget.isChecked()
            else:
                param_value = None

            algo_params[param_name] = param_value

        return algo_params

    def _manage_cbs_events(self, worker):
        for cbs_values in self.layer_box_states.values():
            for cb in cbs_values.get("cbs"):
                worker.returned.connect(lambda _: cb.setCurrentIndex(cb.currentIndex()))

    def _download_samples_returned(self, images):
        for image in images:
            self.viewer.add_image(image)

    def _trigger_run_algorithm(self, **kwargs):
        raise NotImplementedError("Subclasses should implement this method.")

    def _trigger_sample_image_download(self, **kwargs):
        raise NotImplementedError("Subclasses should implement this method.")
