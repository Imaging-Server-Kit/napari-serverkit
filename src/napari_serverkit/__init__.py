from typing import Union

from ._version import version as __version__

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from napari_serverkit.widgets import AlgorithmWidget, ServerKitHttpWidget, NapariResults
from imaging_server_kit import Algorithm


def add_as_widget(
    viewer: Union["napari.Viewer", "napari_serverkit.ServerkitNapariViewer"],
    algorithm: Algorithm,
):
    if isinstance(viewer, NapariResults):
        viewer.viewer.window.add_dock_widget(
            widget=AlgorithmWidget(viewer.viewer, algorithm), name=algorithm.name
        )
    else:
        viewer.window.add_dock_widget(
            widget=AlgorithmWidget(viewer, algorithm), name=algorithm.name
        )


__all__ = ["AlgorithmWidget", "ServerKitHttpWidget", "NapariResults", "add_as_widget"]
