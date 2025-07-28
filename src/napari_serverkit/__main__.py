import napari
from napari_serverkit._remote import ServerKitRemoteWidget
from napari_serverkit import __version__

if __name__ == "__main__":
    viewer = napari.Viewer(title=f"Imaging Server Kit ({__version__})")
    viewer.window.add_dock_widget(ServerKitRemoteWidget(viewer), name="Imaging Server Kit")
    napari.run()