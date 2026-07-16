from typing import Union

from ._version import version as __version__

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from qtpy.QtWidgets import QWidget

from napari_serverkit.widgets import AlgorithmWidget, ServerKitHttpWidget, NapariStack
import imaging_server_kit as sk
from imaging_server_kit import Algorithm


class AlgorithmToolsWidget(QWidget):
    def __init__(self, viewer: "napari.viewer.Viewer"):
        super().__init__()
        widget = sk.to_qwidget(sk.tools, viewer=viewer)
        self.setLayout(widget.layout())


class AlgorithmDemosWidget(QWidget):
    def __init__(self, viewer: "napari.viewer.Viewer"):
        super().__init__()
        widget = sk.to_qwidget(sk.demos, viewer=viewer)
        self.setLayout(widget.layout())


def add_as_widget(
    viewer: Union["napari.Viewer", "napari_serverkit.ServerkitNapariViewer"],
    algorithm: Algorithm,
):
    if isinstance(viewer, NapariStack):
        viewer.viewer.window.add_dock_widget(
            widget=AlgorithmWidget(viewer.viewer, algorithm), name=algorithm.name
        )
    else:
        viewer.window.add_dock_widget(
            widget=AlgorithmWidget(viewer, algorithm), name=algorithm.name
        )


__all__ = ["AlgorithmWidget", "ServerKitHttpWidget", "NapariStack", "add_as_widget"]
