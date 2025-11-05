import napari
from imaging_server_kit import Algorithm
from napari_serverkit.widgets.runner_widget import RunnerWidget
from napari_serverkit.widgets.serverkit_widget import ServerKitWidget


class AlgorithmWidget(ServerKitWidget):
    def __init__(self, viewer: napari.Viewer, algorithm: Algorithm):
        super().__init__(viewer=viewer, runner_widget=RunnerWidget(algorithm))

        self.runner_widget.cb_algorithms.clear()
        self.runner_widget.cb_algorithms.addItems(
            self.runner_widget.algorithm.algorithms # type: ignore
        )
