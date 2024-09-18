![EPFL Center for Imaging logo](https://imaging.epfl.ch/resources/logo-for-gitlab.svg)
# 🪐 Napari Server Kit

Process and analyze images in Napari via a web server. This plugin is based on the [imaging-server-kit](https://github.com/EPFL-Center-for-Imaging/napari-serverkit) project.

**Key features**

- Run algorithms on remote servers via a web API.
- ...

## Installation

You can install `napari-serverkit` via:

    pip install git+https://gitlab.com/epfl-center-for-imaging/napari-serverkit.git

## Usage

Start the plugin from the `Plugins` menu of Napari:

```
Plugins > Server Kit
```

or type in the command:

```
napari -w napari-serverkit
```

- Set up the `Server URL`.
- Press `Connect`. A list of algorithms should appear in the `Algorithm` dropdown.

## Contributing

Contributions are very welcome.

## License

This software is distributed under the terms of the [BSD-3](http://opensource.org/licenses/BSD-3-Clause) license.

## Issues

If you encounter any problems, please file an issue along with a detailed description.
