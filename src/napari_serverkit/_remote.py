from napari.qt.threading import thread_worker
from napari.utils.notifications import show_error, show_info
from qtpy.QtWidgets import (
    QSizePolicy,
    QLabel,
    QPushButton,
    QComboBox,
    QLineEdit,
)
import imaging_server_kit as sk
from imaging_server_kit.core import (
    ServerRequestError,
    InvalidAlgorithmParametersError,
    AlgorithmServerError,
    AlgorithmTimeoutError,
)
import webbrowser

from ._widget import ServerKitAbstractWidget


class ServerKitRemoteWidget(ServerKitAbstractWidget):
    def __init__(self, napari_viewer):
        super().__init__(napari_viewer=napari_viewer)

        self.client = sk.Client()

        # Server URL
        super().layout().addWidget(QLabel("Server URL", self), 0, 0)
        self.server_url_field = QLineEdit(self)
        self.server_url_field.setText("http://localhost:8000")
        super().layout().addWidget(self.server_url_field, 0, 1)
        self.connect_btn = QPushButton("Connect", self)
        self.connect_btn.clicked.connect(self._connect_to_server)
        super().layout().addWidget(self.connect_btn, 0, 2)

        # Algorithms
        self.cb_algorithms = QComboBox()
        self.cb_algorithms.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        super().layout().addWidget(QLabel("Algorithm", self), 1, 0)
        super().layout().addWidget(self.cb_algorithms, 1, 1, 1, 2)

        self.cb_algorithms.currentTextChanged.connect(self._handle_algorithm_changed)

        # Algo info
        self.algo_info_btn = QPushButton("🌐 Documentation", self)
        self.algo_info_btn.clicked.connect(self._trigger_algo_info_link)
        super().layout().addWidget(self.algo_info_btn, 3, 0, 1, 3)

    def _connect_to_server(self):
        self.cb_algorithms.clear()
        server_url = self.server_url_field.text()
        try:
            self.client.connect(server_url)
            self.cb_algorithms.addItems(self.client.algorithms)
            show_info(f"Connected!")
        except ServerRequestError as e:
            show_error(e.message)

    @thread_worker
    def _run_algorithm(self, algorithm, is_stream, **algo_params):
        try:
            if is_stream:
                for result_data_tuple in self.client.stream_algorithm(
                    algorithm, **algo_params
                ):
                    yield result_data_tuple
                return []
            else:
                return self.client.run_algorithm(algorithm, **algo_params)
        except (
            ServerRequestError,
            InvalidAlgorithmParametersError,
            AlgorithmServerError,
            AlgorithmTimeoutError,
        ) as e:
            show_error(e.message)
            return []

    def _trigger_run_algorithm(self):
        selected_algorithm = self.cb_algorithms.currentText()
        if selected_algorithm == "":
            return

        algo_is_stream = self.client.is_algo_stream(selected_algorithm)

        algo_params = self.algo_params_from_dynamic_ui()
        worker = self._run_algorithm(selected_algorithm, algo_is_stream, **algo_params)
        worker.returned.connect(self._thread_returned)
        if algo_is_stream:
            worker.yielded.connect(self._thread_returned)

        # Slightly hacky: make sure the combobox current selections stay the same on algo run
        for cb in self.cbs_image:
            worker.returned.connect(lambda _: cb.setCurrentIndex(cb.currentIndex()))
        for cb in self.cbs_labels:
            worker.returned.connect(lambda _: cb.setCurrentIndex(cb.currentIndex()))
        for cb in self.cbs_points:
            worker.returned.connect(lambda _: cb.setCurrentIndex(cb.currentIndex()))
        for cb in self.cbs_shapes:
            worker.returned.connect(lambda _: cb.setCurrentIndex(cb.currentIndex()))
        for cb in self.cbs_vectors:
            worker.returned.connect(lambda _: cb.setCurrentIndex(cb.currentIndex()))
        for cb in self.cbs_tracks:
            worker.returned.connect(lambda _: cb.setCurrentIndex(cb.currentIndex()))
        
        self.worker_manager.add_active(worker)

    def _handle_algorithm_changed(self, selected_algorithm):
        if selected_algorithm == "":
            return
        # Get a JSON Schema of the algorithm parameters from the server
        try:
            algo_params = self.client.get_algorithm_parameters(selected_algorithm)
        except (AlgorithmServerError, ServerRequestError) as e:
            show_error(e.message)
            return
        
        self._update_params_layout(algo_params)

    @thread_worker
    def _download_worker(self, selected_algorithm):
        try:
            images = self.client.get_sample_images(selected_algorithm)
        except (AlgorithmServerError, ServerRequestError) as e:
            show_error(e.message)
            return
        return images

    def _trigger_sample_image_download(self):
        selected_algorithm = self.cb_algorithms.currentText()
        if selected_algorithm == "":
            return
        
        worker = self._download_worker(selected_algorithm)
        worker.returned.connect(self._download_samples_returned)
        self.worker_manager.add_active(worker)

    def _download_samples_returned(self, images):
        for image in images:
            self.viewer.add_image(image)

    def _trigger_algo_info_link(self):
        selected_algorithm = self.cb_algorithms.currentText()
        if selected_algorithm == "":
            return

        server_url = self.server_url_field.text()
        algo_info_url = f"{server_url}/{selected_algorithm}/info"
        webbrowser.open(algo_info_url)
