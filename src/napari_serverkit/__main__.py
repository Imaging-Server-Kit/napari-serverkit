import napari
from napari_serverkit import __version__
from napari_serverkit.widgets import ServerKitWidget

if __name__ == "__main__":
    viewer = napari.Viewer(title=f"Imaging Server Kit ({__version__})")
    viewer.window.add_dock_widget(ServerKitWidget(viewer), name="Imaging Server Kit")
    napari.run()