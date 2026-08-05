import napari
from imaging_server_kit.core.runner import AlgorithmRunner
from napari_serverkit.widgets.runner_widget import RunnerWidget
from napari_serverkit.widgets.serverkit_widget import ServerKitWidget


class AlgorithmWidget(ServerKitWidget):
    def __init__(self, viewer: napari.Viewer, runner: AlgorithmRunner):
        runner_widget = RunnerWidget(runner)
        super().__init__(viewer=viewer, runner_widget=runner_widget)
