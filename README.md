![EPFL Center for Imaging logo](https://imaging.epfl.ch/resources/logo-for-gitlab.svg)
# 🪐 Napari Server Kit

Connect to an [Imaging Server Kit](https://github.com/Imaging-Server-Kit/imaging-server-kit) server and run algorithms in [Napari](https://napari.org/stable/).

[napari_screencast.webm](https://github.com/user-attachments/assets/4c1e3e0d-0623-4fe4-a9dd-c9d1e5e68844)

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

- Make sure to have an [algorithm server](https://github.com/Imaging-Server-Kit/imaging-server-kit) running that you can connect to.
- Enter the server URL (by default, http://localhost:8000) and click `Connect`.
- A list of algorithms should appear in the algorithm dropdown.
- The parameters should update based on the selected algorithm.

## Contributing

Contributions are very welcome.

## License

This software is distributed under the terms of the [BSD-3](http://opensource.org/licenses/BSD-3-Clause) license.

## Issues

If you encounter any problems, please file an issue along with a detailed description.

## Acknowledgements

This project uses the [PyApp](https://github.com/ofek/pyapp) software for creating a runtime installer.
