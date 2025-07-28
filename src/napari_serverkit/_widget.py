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
    QSizePolicy,
    QSpinBox,
    QWidget,
)

from ._worker import WorkerManager


class ServerKitAbstractWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        self.cbs_image = []
        self.cbs_labels = []
        self.cbs_points = []
        self.cbs_shapes = []
        self.cbs_vectors = []
        self.cbs_tracks = []
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
        self.pbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid_layout.addWidget(self.pbar, 8, 0, 1, 3)

    def _on_layer_change(self, e):
        for cb_image in self.cbs_image:
            cb_image.clear()
            for x in self.viewer.layers:
                if isinstance(x, napari.layers.Image):
                    cb_image.addItem(x.name, x.data)

        for cb_labels in self.cbs_labels:
            cb_labels.clear()
            for x in self.viewer.layers:
                if isinstance(x, napari.layers.Labels):
                    cb_labels.addItem(x.name, x.data)

        for cb_points in self.cbs_points:
            cb_points.clear()
            for x in self.viewer.layers:
                if isinstance(x, napari.layers.Points):
                    cb_points.addItem(x.name, x.data)

        for cb_shapes in self.cbs_shapes:
            cb_shapes.clear()
            for x in self.viewer.layers:
                if isinstance(x, napari.layers.Shapes):
                    cb_shapes.addItem(x.name, x.data)

        for cb_vectors in self.cbs_vectors:
            cb_vectors.clear()
            for x in self.viewer.layers:
                if isinstance(x, napari.layers.Vectors):
                    cb_vectors.addItem(x.name, x.data)

        for cb_tracks in self.cbs_tracks:
            cb_tracks.clear()
            for x in self.viewer.layers:
                if isinstance(x, napari.layers.Tracks):
                    cb_tracks.addItem(x.name, x.data)

    def _trigger_run_algorithm(self, **kwargs):
        raise NotImplementedError("Subclasses should implement this method.")

    def _thread_returned(self, payload: List):
        if payload is None:
            return

        if len(payload) == 0:
            return

        self.viewer.text_overlay.visible = False
        for layer_data, layer_params, layer_type in payload:
            if layer_type in [
                "image",
                "mask",
                "instance_mask",
                "mask3d",
                "points",
                "points3d",
                "vectors",
                "boxes",
            ]:
                self._handle_layered_algo_type(layer_type, layer_data, layer_params)
            else:
                self._handle_special_algo_type(layer_type, layer_data, layer_params)

    def _handle_layered_algo_type(self, layer_type, layer_data, layer_params):
        layer_name = layer_params.pop("name", "Output")
        tile_params = layer_params.get("tile_params")

        existing_layer = None
        for layer in self.viewer.layers:
            if layer.name == layer_name:
                existing_layer = layer
                break

        if existing_layer is None:
            if tile_params:
                image_layer_data = initialize_tiled_image(tile_params)
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

        if tile_params:
            if layer_type == "instance_mask":
                # TODO: implement a good emough merging strategy for instance masks (difficult!)
                mask = layer_data == 0
                layer_data += existing_layer.data.max()
                layer_data[mask] = 0

            chunk_pos_x = tile_params.get("pos_x")
            chunk_pos_y = tile_params.get("pos_y")

            try:
                if tile_params.get("pos_z"):  # 3D case
                    chunk_pos_z = tile_params.get("pos_z")
                    chunk_size_z, chunk_size_y, chunk_size_x = (
                        layer_data.shape[0],
                        layer_data.shape[1],
                        layer_data.shape[2],
                    )
                    existing_layer.data[
                        chunk_pos_z : (chunk_pos_z + chunk_size_z),
                        chunk_pos_y : (chunk_pos_y + chunk_size_y),
                        chunk_pos_x : (chunk_pos_x + chunk_size_x),
                    ] = layer_data
                else:  # 2D / RGB cases
                    chunk_size_x, chunk_size_y = (
                        layer_data.shape[0],
                        layer_data.shape[1],
                    )
                    existing_layer.data[
                        chunk_pos_x : (chunk_pos_x + chunk_size_x),
                        chunk_pos_y : (chunk_pos_y + chunk_size_y),
                    ] = layer_data
            except:
                print("Attempted to write tiles outside of the image.")

            # Update the progress bar
            self.pbar.setMaximum(tile_params.get("n_tiles"))
            self.pbar.setValue(tile_params.get("tile_idx"))
        else:
            existing_layer.data = layer_data

        existing_layer.refresh()

    def _handle_special_algo_type(self, algo_type, layer_data, layer_params):
        if algo_type == "notification":
            notification_level = layer_params.get("level")
            if notification_level == "error":
                show_error(layer_data)
            elif notification_level == "warning":
                show_warning(layer_data)
            else:
                show_info(layer_data)
        elif algo_type == "class":
            # Display the class label in the viewer text overlay
            self.viewer.text_overlay.visible = True
            self.viewer.text_overlay.text = layer_data
        elif algo_type == "text":
            # Display the text in the viewer text overlay
            self.viewer.text_overlay.visible = True
            self.viewer.text_overlay.text = layer_data
        elif algo_type == "scalar":
            self.viewer.text_overlay.visible = True
            self.viewer.text_overlay.text = str(layer_data)
        elif algo_type == "list":
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
            if param_widget_type == "image":
                qt_widget = QComboBox()
                self.cbs_image.append(qt_widget)  # `subscribe` it to the viewer events
            elif param_widget_type == "mask":
                qt_widget = QComboBox()
                self.cbs_labels.append(qt_widget)
            elif param_widget_type == "points":
                qt_widget = QComboBox()
                self.cbs_points.append(qt_widget)
            elif param_widget_type == "shapes":
                qt_widget = QComboBox()
                self.cbs_shapes.append(qt_widget)
            elif param_widget_type == "vectors":
                qt_widget = QComboBox()
                self.cbs_vectors.append(qt_widget)
            elif param_widget_type == "tracks":
                qt_widget = QComboBox()
                self.cbs_tracks.append(qt_widget)
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
        elif layer_type in ["mask", "mask3d", "instance_mask"]:
            added_layer = self.viewer.add_labels(
                layer_data, name=layer_name, **layer_params
            )
        elif layer_type == "boxes":
            added_layer = self.viewer.add_shapes(
                layer_data, name=layer_name, **layer_params
            )
        elif layer_type in ["points", "points3d"]:
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

    def algo_params_from_dynamic_ui(self) -> Dict:
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
                if qt_widget.currentText() == "":
                    param_value = np.array([])
                else:
                    param_value = np.array(
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

    def _trigger_sample_image_download(self, **kwargs):
        raise NotImplementedError("Subclasses should implement this method.")