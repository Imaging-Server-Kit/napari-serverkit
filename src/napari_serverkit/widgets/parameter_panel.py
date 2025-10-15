from typing import Callable, Dict

import napari.layers
from qtpy.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout,
                            QGroupBox, QLabel, QLineEdit, QSpinBox)

from napari_serverkit.widgets.napari_results import NapariResults

NAPARI_LAYER_MAPPINGS = {
    "image": napari.layers.Image,
    "mask": napari.layers.Labels,
    "instance_mask": napari.layers.Labels,
    "points": napari.layers.Points,
    "boxes": napari.layers.Shapes,
    "paths": napari.layers.Shapes,
    "vectors": napari.layers.Vectors,
    "tracks": napari.layers.Tracks,
}


class ParameterPanel:
    def __init__(self, trigger: Callable, napari_results: NapariResults):
        self._trigger_func = trigger
        self.napari_results = napari_results

        self.ui_state = {}

        self.layer_comboboxes = {
            # array_type: [] for array_type in list(DATA_TYPES.keys())
        }

        self.widget = QGroupBox()
        self.widget.setTitle("Parameters")

        self.layout = QGridLayout()
        self.widget.setLayout(self.layout)

        self.napari_results.connect_layer_added_event(self._on_layer_change)
        self.napari_results.connect_layer_removed_event(self._on_layer_change)
        self.napari_results.connect_layer_renamed_event(self._on_layer_change)
        self._on_layer_change(None)

    def update(self, schema: Dict):
        # Clean-up the previous dynamic UI layout
        for i in reversed(range(self.layout.count())):
            self.layout.itemAt(i).widget().setParent(None)

        # Generate the new dynamic UI state and layout
        self.ui_state = {}
        for k, (param_name, param_values) in enumerate(schema["properties"].items()):
            # Parameter name
            qt_label = QLabel(param_values.get("title"))
            self.layout.addWidget(qt_label, k, 0)

            # Add the right UI element based on the retreived parameter type.
            param_type = param_values.get("param_type")

            if param_type == "dropdown":
                qt_widget = QComboBox()
                # If there is only one element, we get a `const` attribute instead of `enum`
                if param_values.get("enum") is None:
                    qt_widget.addItem(param_values.get("const"))
                else:
                    qt_widget.addItems(param_values.get("enum"))
                qt_widget.setCurrentText(param_values.get("default"))
                if param_values.get("auto_call"):
                    qt_widget.currentTextChanged.connect(self._trigger_func)
            elif param_type == "int":
                qt_widget = QSpinBox()
                qt_widget.setMinimum(param_values.get("minimum"))
                qt_widget.setMaximum(param_values.get("maximum"))
                qt_widget.setValue(param_values.get("default"))
                if param_values.get("step"):
                    qt_widget.setSingleStep(param_values.get("step"))
                if param_values.get("auto_call"):
                    qt_widget.valueChanged.connect(self._trigger_func)
            elif param_type == "float":
                qt_widget = QDoubleSpinBox()
                qt_widget.setMinimum(param_values.get("minimum"))
                qt_widget.setMaximum(param_values.get("maximum"))
                qt_widget.setValue(param_values.get("default"))
                if param_values.get("step"):
                    qt_widget.setSingleStep(param_values.get("step"))
                if param_values.get("auto_call"):
                    qt_widget.valueChanged.connect(self._trigger_func)
            elif param_type == "bool":
                qt_widget = QCheckBox()
                qt_widget.setChecked(param_values.get("default"))
                if param_values.get("auto_call"):
                    qt_widget.stateChanged.connect(self._trigger_func)
            elif param_type == "str":
                qt_widget = QLineEdit()
                qt_widget.setText(param_values.get("default"))
            elif param_type == "notification":
                # A notification input (probably never going to happen)
                qt_widget = QLineEdit()
                qt_widget.setText(param_values.get("default"))
            else:
                # Numpy layers
                qt_widget = QComboBox()
                if param_type not in self.layer_comboboxes:
                    self.layer_comboboxes[param_name] = []
                self.layer_comboboxes[param_type].append(qt_widget)

            self.layout.addWidget(qt_widget, k, 1)

            self.ui_state[param_name] = (param_type, qt_widget)

        self._on_layer_change(None)  # Refresh dropdowns in new UI

    def _on_layer_change(self, *args, **kwargs):
        for kind, cb_list in self.layer_comboboxes.items():
            # layer_type = self.napari_results.layer_types.get(kind)
            # if layer_type in supported_napari_layers:
            layer_type = NAPARI_LAYER_MAPPINGS[kind]
            for cb in cb_list:
                cb.clear()
                for layer in self.napari_results.viewer.layers:
                    if isinstance(layer, layer_type):
                        cb.addItem(layer.name, layer.data)

    def get_algo_params(self) -> Dict:
        """Create a dictionary representation of parameter values based on the UI state."""
        algo_params = {}
        for param_name, (param_widget_type, qt_widget) in self.ui_state.items():
            if param_widget_type == "dropdown":
                param_value = qt_widget.currentText()
            elif param_widget_type == "int":
                param_value = int(qt_widget.value())
            elif param_widget_type == "float":
                param_value = float(qt_widget.value())
            elif param_widget_type == "str":
                param_value = qt_widget.text()
            elif param_widget_type == "bool":
                param_value = qt_widget.isChecked()
            elif param_widget_type == "notification":
                param_value = qt_widget.text()
            else:
                # Numpy layers
                if qt_widget.currentText():
                    layer_name = qt_widget.currentText()
                    layer = self.napari_results.read(layer_name)
                    param_value = layer.data if layer else None
                else:
                    param_value = None

            algo_params[param_name] = param_value

        return algo_params

    def manage_cbs_events(self, worker):
        """Whenever a worker returns, we update the napari layer comboboxes to their current index (instead of resetting it)"""
        for kind, cb_list in self.layer_comboboxes.items():
            # kind: image, mask...
            # if kind in ["image", "mask" ...]
            # layer_type = self.napari_results.layer_types.get(kind)  # Napari layer type
            # viewer.Image, viewer.Mask...
            # if layer_type in supported_napari_layers:
            for cb in cb_list:
                worker.returned.connect(lambda _: cb.setCurrentIndex(cb.currentIndex()))
