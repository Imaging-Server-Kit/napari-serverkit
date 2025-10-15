import napari
from napari_serverkit.widgets.serverkit_widget import ServerKitWidget
from napari_serverkit.widgets.http_runner_widget import HttpRunnerWidget


class ServerKitHttpWidget(ServerKitWidget):
    def __init__(self, viewer: napari.Viewer):
        super().__init__(
            viewer=viewer, 
            runner_widget=HttpRunnerWidget()
        )