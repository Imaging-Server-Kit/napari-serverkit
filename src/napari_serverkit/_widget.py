from typing import List, Tuple, Dict
from napari.qt.threading import thread_worker
import napari
import napari.layers
from napari.utils.notifications import show_error, show_info, show_warning
from qtpy.QtWidgets import (
    QWidget,
    QGridLayout,
    QSizePolicy,
    QGroupBox,
    QLabel,
    QPushButton,
    QProgressBar,
    QComboBox,
    QCheckBox,
    QLineEdit,
    QSpinBox,
    QDoubleSpinBox,
)
from qtpy.QtCore import Qt
import numpy as np
import imaging_server_kit as serverkit
from imaging_server_kit.errors import (
    ServerRequestError,
    InvalidAlgorithmParametersError,
    AlgorithmServerError,
)
import webbrowser


class ServerKitWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        self.client = serverkit.Client()

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

        # Server URL
        grid_layout.addWidget(QLabel("Server URL", self), 0, 0)
        self.server_url_field = QLineEdit(self)
        self.server_url_field.setText("http://localhost:7000")
        grid_layout.addWidget(self.server_url_field, 0, 1)
        self.connect_btn = QPushButton("Connect", self)
        self.connect_btn.clicked.connect(self._connect_to_server)
        grid_layout.addWidget(self.connect_btn, 0, 2)

        # Algorithms
        self.cb_algorithms = QComboBox()
        self.cb_algorithms.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid_layout.addWidget(QLabel("Algorithm", self), 1, 0)
        grid_layout.addWidget(self.cb_algorithms, 1, 1, 1, 2)

        self.cb_algorithms.currentTextChanged.connect(self._handle_algorithm_changed)

        # Sample image
        self.sample_image_btn = QPushButton("Sample image", self)
        self.sample_image_btn.clicked.connect(self._trigger_sample_image_download)
        grid_layout.addWidget(self.sample_image_btn, 2, 0, 1, 3)

        # Algo info
        self.algo_info_btn = QPushButton("🌐 Documentation", self)
        self.algo_info_btn.clicked.connect(self._trigger_algo_info_link)
        grid_layout.addWidget(self.algo_info_btn, 3, 0, 1, 3)

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

        # Progress bar
        self.pbar = QProgressBar(self, minimum=0, maximum=1)
        self.pbar.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        grid_layout.addWidget(self.pbar, 7, 0, 1, 3)

        # Layer callbacks
        self.viewer.layers.events.inserted.connect(
            lambda e: e.value.events.name.connect(self._on_layer_change)
        )
        self.viewer.layers.events.inserted.connect(self._on_layer_change)
        self.viewer.layers.events.removed.connect(self._on_layer_change)
        self._on_layer_change(None)

    def _connect_to_server(self):
        self.cb_algorithms.clear()
        server_url = self.server_url_field.text()
        try:
            self.client.connect(server_url)
            self.cb_algorithms.addItems(self.client.algorithms)
            show_info(f"Connected!")
        except ServerRequestError as e:
            show_error(e.message)

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

    @thread_worker
    def _run_algorithm(self, selected_algorithm, **algo_params) -> List[Tuple]:
        try:
            return self.client.run_algorithm(selected_algorithm, **algo_params)
        except (
            ServerRequestError,
            InvalidAlgorithmParametersError,
            AlgorithmServerError,
        ) as e:
            show_error(e.message)
            return []

    def _trigger_run_algorithm(self):
        selected_algorithm = self.cb_algorithms.currentText()
        if selected_algorithm == "":
            return

        algo_params = self.algo_params_from_dynamic_ui()

        self.pbar.setMaximum(0)
        worker = self._run_algorithm(selected_algorithm, **algo_params)
        worker.returned.connect(self._thread_returned)
        worker.start()

    def _thread_returned(self, payload: List):
        self.pbar.setMaximum(1)

        if len(payload) == 0:
            return
        
        # Add the right layer into the viewer
        for layer_data, layer_params, layer_type in payload:
            if layer_type == "image":
                self.viewer.add_image(layer_data, **layer_params)
            elif layer_type == "labels":
                self.viewer.add_labels(layer_data, **layer_params)
            elif layer_type == "boxes":
                self.viewer.add_shapes(layer_data, **layer_params)
            elif layer_type == "points":
                self.viewer.add_points(layer_data, **layer_params)
            elif layer_type == "vectors":
                self.viewer.add_vectors(layer_data, **layer_params)
            elif layer_type == "tracks":
                self.viewer.add_tracks(layer_data, **layer_params)
            else:
                show_warning(f"Unhandled layer type: {layer_type}")

    def _handle_algorithm_changed(self, selected_algorithm):
        if selected_algorithm == "":
            return
        # Get a JSON Schema of the algorithm parameters from the server
        try:
            algo_params = self.client.get_algorithm_parameters(selected_algorithm)
        except (AlgorithmServerError, ServerRequestError) as e:
            show_error(e.message)
            return

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
            elif param_widget_type == "labels":
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
                qt_widget.addItems(param_values.get("enum"))
            elif param_widget_type == "int":
                qt_widget = QSpinBox()
                qt_widget.setMinimum(param_values.get("minimum"))
                qt_widget.setMaximum(param_values.get("maximum"))
                qt_widget.setValue(param_values.get("default"))
                if param_values.get("step"):
                    qt_widget.setSingleStep(param_values.get("step"))
            elif param_widget_type == "float":
                qt_widget = QDoubleSpinBox()
                qt_widget.setMinimum(param_values.get("minimum"))
                qt_widget.setMaximum(param_values.get("maximum"))
                qt_widget.setValue(param_values.get("default"))
                if param_values.get("step"):
                    qt_widget.setSingleStep(param_values.get("step"))
            elif param_widget_type == "bool":
                qt_widget = QCheckBox()
                qt_widget.setChecked(param_values.get("default"))
            elif param_widget_type == "str":
                qt_widget = QLineEdit()
                qt_widget.setText(param_values.get("default"))
            else:
                continue

            self.algo_params_layout.addWidget(qt_widget, k, 1)

            self.dynamic_ui_state[param_name] = (param_widget_type, qt_widget)

        self._on_layer_change(None)  # Refresh dropdowns in new UI

    def algo_params_from_dynamic_ui(self) -> Dict:
        # Returns a Json dict representation of the parameter values
        algo_params = {}
        for param_name, (param_widget_type, qt_widget) in self.dynamic_ui_state.items():
            if param_widget_type in [
                "image",
                "labels",
                "shapes",
                "points",
                "vectors",
                "tracks",
            ]:
                if qt_widget.currentText() == "":
                    param_value = np.array([])
                else:
                    # if param_widget_type == "shapes":
                    param_value = np.array(
                        self.viewer.layers[qt_widget.currentText()].data
                    )
                    # param_value = self.viewer.layers[qt_widget.currentText()].data
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

    def _trigger_sample_image_download(self):
        selected_algorithm = self.cb_algorithms.currentText()
        if selected_algorithm == "":
            return

        try:
            images = self.client.get_sample_images(selected_algorithm)
        except (AlgorithmServerError, ServerRequestError) as e:
            show_error(e.message)
            return

        for image in images:
            self.viewer.add_image(image)

    def _trigger_algo_info_link(self):
        selected_algorithm = self.cb_algorithms.currentText()
        if selected_algorithm is None:
            return

        server_url = self.server_url_field.text()
        algo_info_url = f"{server_url}/{selected_algorithm}/info"
        webbrowser.open(algo_info_url)
