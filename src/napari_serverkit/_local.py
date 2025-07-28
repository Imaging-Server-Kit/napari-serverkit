from imaging_server_kit.core import (
    AlgorithmServer,
    AlgorithmServerError,
    AlgorithmTimeoutError,
    InvalidAlgorithmParametersError,
)
from napari.qt.threading import thread_worker
from napari.utils.notifications import show_error
from qtpy.QtWidgets import QLabel

from ._widget import ServerKitAbstractWidget


class AlgorithmWidget(ServerKitAbstractWidget):
    def __init__(self, napari_viewer, server: AlgorithmServer):
        super().__init__(napari_viewer=napari_viewer)

        self.server = server
        if len(self.server.services):
            self.algorithm = self.server.services[0]
        else:
            self.algorithm = ""

        # Algorithms
        self.cb_algorithms = QLabel()
        self.cb_algorithms.setText(self.algorithm)
        super().layout().addWidget(QLabel("Algorithm:", self), 1, 0)
        super().layout().addWidget(self.cb_algorithms, 1, 1, 1, 2)

        algo_params = self.server.parameters
        self._update_params_layout(algo_params)

    @thread_worker
    def _run_algorithm(self, is_stream, **algo_params):
        try:
            if is_stream:
                for result_data_tuple in self.server.run_algorithm(**algo_params):
                    yield result_data_tuple
                return []
            else:
                return self.server.run_algorithm(**algo_params)
        except (
            InvalidAlgorithmParametersError,
            AlgorithmServerError,
            AlgorithmTimeoutError,
        ) as e:
            show_error(e.message)
            return []

    def _trigger_run_algorithm(self, **kwargs):
        algo_is_stream = self.server.is_stream

        algo_params = self.algo_params_from_dynamic_ui()
        worker = self._run_algorithm(algo_is_stream, **algo_params)
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

    @thread_worker
    def _download_worker(self):
        return self.server.load_sample_images()

    def _trigger_sample_image_download(self):
        worker = self._download_worker()
        worker.returned.connect(self._download_samples_returned)
        self.worker_manager.add_active(worker)

    def _download_samples_returned(self, images):
        for image in images:
            self.viewer.add_image(image)
