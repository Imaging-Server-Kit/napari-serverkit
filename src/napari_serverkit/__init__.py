from typing import Callable, Optional, Union

from ._version import version as __version__

try:
    from ._version import version as __version__
except ImportError:
    __version__ = "unknown"

from qtpy.QtWidgets import QWidget

import napari
from napari_serverkit.widgets import AlgorithmWidget, ServerKitHttpWidget, NapariStack
from imaging_server_kit import Algorithm, tools, demos
from imaging_server_kit.core.runner import AlgorithmRunner


def to_qwidget(algorithm: Union[AlgorithmRunner, Callable], viewer: napari.Viewer):
    """Convert an algorithm to a QWidget. Used when packaging a Napari plugin."""
    if not isinstance(algorithm, AlgorithmRunner):
        # Assuming the user has passed a "raw" Python function, we attempt to convert it to an Algorithm:
        algorithm = Algorithm(algorithm)

    return AlgorithmWidget(viewer=viewer, runner=algorithm)


def add_as_widget(algorithm: Union[AlgorithmRunner, Callable], viewer: napari.Viewer):
    viewer.window.add_dock_widget(
        widget=to_qwidget(algorithm=algorithm, viewer=viewer),
        name=algorithm.name,
    )


def to_napari(
    algorithm: Union[AlgorithmRunner, Callable],
    viewer: Optional[napari.Viewer] = None,
) -> napari.Viewer:
    """
    Convert an algorithm (or algorithm collection) to a dock widget and add it to a Napari viewer.

    Parameters
    ----------
    algorithm : The algorithm object to add to Napari as a dock widget.
    viewer : An existing Napari viewer to add the dock widget to. If none is passed, a new Napari viewer is created.
    """
    if viewer is None:
        viewer = napari.Viewer()

    if not isinstance(algorithm, AlgorithmRunner):
        # Assuming the user has passed a "raw" Python function, we attempt to convert it to an Algorithm:
        algorithm = Algorithm(algorithm)

    add_as_widget(algorithm=algorithm, viewer=viewer)

    return viewer


class AlgorithmToolsWidget(QWidget):
    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        widget = to_qwidget(tools, viewer=viewer)
        self.setLayout(widget.layout())


class AlgorithmDemosWidget(QWidget):
    def __init__(self, viewer: napari.Viewer):
        super().__init__()
        widget = to_qwidget(demos, viewer=viewer)
        self.setLayout(widget.layout())


__all__ = [
    "AlgorithmWidget",
    "ServerKitHttpWidget",
    "NapariStack",
    "add_as_widget",
    "to_qwidget",
    "to_napari",
]
