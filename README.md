![EPFL Center for Imaging logo](https://imaging.epfl.ch/resources/logo-for-gitlab.svg)
# 🪐 Napari Server Kit

Run [Imaging Server Kit](https://github.com/Imaging-Server-Kit/imaging-server-kit) algorithms interactively in [Napari](https://napari.org/stable/).

[screencast.webm](https://github.com/user-attachments/assets/1ac68cc5-da38-4430-819a-30d325a43176)

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

## Usage

Refer to the [Imaging Server Kit](https://imaging-server-kit.github.io/imaging-server-kit/) documentation for detailed instructions on how to use the `napari-serverkit` plugin.

**TL;DR**

- In Python, use `sk.to_napari(algo)` to generate a dock widget for an `sk.algorithm` object and use it in Napari.
- In Napari, connect to an algorithm server via `Plugins > Server Kit (Napari Server Kit)`.

```python
import napari
import imaging_server_kit as sk

@sk.algorithm
def my_algorithm(...):
    ...

sk.to_napari(my_algorithm)
napari.run()
```

## Contributing

Contributions are very welcome.

## License

This software is distributed under the terms of the [BSD-3](http://opensource.org/licenses/BSD-3-Clause) license.

## Issues

If you encounter any problems, please file an issue along with a detailed description.

## Acknowledgements

This project uses the [PyApp](https://github.com/ofek/pyapp) software for creating a runtime installer.
