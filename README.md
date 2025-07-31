![EPFL Center for Imaging logo](https://imaging.epfl.ch/resources/logo-for-gitlab.svg)
# 🪐 Napari Server Kit

Connect to [Imaging Server Kit](https://github.com/Imaging-Server-Kit/imaging-server-kit) servers and run algorithms in [Napari](https://napari.org/stable/).

[napari_screencast.webm](https://github.com/user-attachments/assets/4c1e3e0d-0623-4fe4-a9dd-c9d1e5e68844)

## Features

- Generate **dock widgets** from `@algorithm_server` definitions

- Custom interactions and compatibility with all [algo types]()

- Compatible with single and multi-algorithm servers

- Layer features and other layer parameters
- Link to download sample images and to the algo documentation
- Enable `auto_call` on individual algorithm parameters
- Process streams, including tiled image processing
- One-click installation via PyApp executables

- Multithreading processing (cancellable)
- Clean error handling and notifications

## Installation

You can install the plugin either via python *or* the executable installer.

**Python installation**

You can install `napari-serverkit` via `pip`::

```
pip install napari-serverkit
```

or clone the project and install the development version:

```
git clone https://github.com/Imaging-Server-Kit/napari-serverkit.git
cd napari-serverkit
pip install -e .
```

Then, start Napari with the Server Kit plugin from the terminal:

```
napari -w napari-serverkit
```

**Executable installer**

Download, unzip, and execute the installer from the [Releases](https://github.com/Imaging-Server-Kit/napari-serverkit/releases) page.

## Usage (TODO: complete this section)

**As a web client to interact with algorithm servers:**

- Make sure to have an [algorithm server](https://github.com/Imaging-Server-Kit/imaging-server-kit) running that you can connect to.
- Enter the server URL (by default, http://localhost:8000) and click `Connect`.
- A list of algorithms should appear in the algorithm dropdown.
- The parameters should update based on the selected algorithm.

**As a widget constructor:**

You can also use `napari-serverkit` to automatically construct dock widgets from algorithm servers *without* running them as servers. In this case, Napari and your algorithm server are installed in the same Python environment.

Use cases:
- Applications where the data transfer between server/client is an unnecessary bottleneck or adds unnecessary overhead
- To easily test algorithm server functionalities
- In other Napari plugins

For example:

```python
from imaging_server_kit import algorithm_server
from napari_serverkit import ServerKitLocalWidget

@algorithm_server(
    ...
)
def my_segmentation_algo(image, ...):
    ...
    return [(result, {}, "mask")]

if __name__=='__main__':
    viewer = napari.Viewer()
    widget = ServerKitLocalWidget(viewer, server=my_segmentation_algo)
    viewer.window.add_dock_widget(widget)
    napari.run()
```

For more details, see the [examples]().

## Contributing

Contributions are very welcome.

## License

This software is distributed under the terms of the [BSD-3](http://opensource.org/licenses/BSD-3-Clause) license.

## Issues

If you encounter any problems, please file an issue along with a detailed description.

## Acknowledgements

This project uses the [PyApp](https://github.com/ofek/pyapp) software for creating a runtime installer.
