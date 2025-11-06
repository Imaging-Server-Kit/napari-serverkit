import napari
from napari_serverkit import __version__
from napari_serverkit.widgets import ServerKitHttpWidget

if __name__ == "__main__":
    viewer = napari.Viewer(title=f"Imaging Server Kit ({__version__})")
    viewer.window.add_dock_widget(ServerKitHttpWidget(viewer), name="Imaging Server Kit")
    napari.run()