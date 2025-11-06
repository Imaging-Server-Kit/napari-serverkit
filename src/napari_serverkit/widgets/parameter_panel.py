from typing import Callable, Dict, Type
import numpy as np

import napari.layers
from qtpy.QtWidgets import (QCheckBox, QComboBox, QDoubleSpinBox, QGridLayout,
                            QGroupBox, QLabel, QLineEdit, QSpinBox)

from imaging_server_kit.core.results import Results
from napari_serverkit.widgets.napari_results import NapariResults

NAPARI_LAYER_MAPPINGS: Dict[str, Type[napari.layers.Layer]] = {
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
        self.layer_comboboxes = {}

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
            ui_item = self.layout.itemAt(i)
            if ui_item is not None:
                ui_item_widget = ui_item.widget()
                if ui_item_widget is not None:
                    ui_item_widget.setParent(None)

        # Generate the new dynamic UI state and layout (TODO: this has grown to be quite complex; we should probably rework self.ui_state and the design here)
        self.ui_state = {}
        for k, (param_name, param_values) in enumerate(schema["properties"].items()):
            # Add the right UI element based on the retreived parameter type.
            param_type = param_values.get("param_type")

            if param_type == "choice":
                qt_widget = QComboBox()
                # If there is only one element, we get a `const` attribute instead of `enum`
                if param_values.get("enum") is None:
                    qt_widget.addItem(param_values.get("const"))
                else:
                    qt_widget.addItems(param_values.get("enum"))
                qt_widget.setCurrentText(param_values.get("default"))
                if param_values.get("auto_call"):
                    qt_widget.currentTextChanged.connect(self._trigger_func)
                qt_widget_setter_func = qt_widget.setCurrentText
                widget_value_recover_func = lambda qt_widget: qt_widget.currentText()
            elif param_type == "int":
                qt_widget = QSpinBox()
                qt_widget.setMinimum(param_values.get("minimum"))
                qt_widget.setMaximum(param_values.get("maximum"))
                qt_widget.setValue(param_values.get("default"))
                if param_values.get("step"):
                    qt_widget.setSingleStep(param_values.get("step"))
                if param_values.get("auto_call"):
                    qt_widget.valueChanged.connect(self._trigger_func)
                qt_widget_setter_func = qt_widget.setValue
                widget_value_recover_func = lambda qt_widget: int(qt_widget.value())
            elif param_type == "float":
                qt_widget = QDoubleSpinBox()
                qt_widget.setMinimum(param_values.get("minimum"))
                qt_widget.setMaximum(param_values.get("maximum"))
                qt_widget.setValue(param_values.get("default"))
                if param_values.get("step"):
                    qt_widget.setSingleStep(param_values.get("step"))
                if param_values.get("auto_call"):
                    qt_widget.valueChanged.connect(self._trigger_func)
                qt_widget_setter_func = qt_widget.setValue
                widget_value_recover_func = lambda qt_widget: float(qt_widget.value())
            elif param_type == "bool":
                qt_widget = QCheckBox()
                qt_widget.setChecked(param_values.get("default"))
                if param_values.get("auto_call"):
                    qt_widget.stateChanged.connect(self._trigger_func)
                qt_widget_setter_func = qt_widget.setChecked
                widget_value_recover_func = lambda qt_widget: qt_widget.isChecked()
            elif param_type == "str":
                qt_widget = QLineEdit()
                qt_widget.setText(param_values.get("default"))
                qt_widget_setter_func = qt_widget.setText
                widget_value_recover_func = lambda qt_widget: qt_widget.text()
            elif param_type == "notification":
                # A notification input (probably never going to happen)
                qt_widget = QLineEdit()
                qt_widget.setText(param_values.get("default"))
                qt_widget_setter_func = qt_widget.setText
                widget_value_recover_func = lambda qt_widget: qt_widget.text()
            elif param_type == "null":
                # Ignore Null parameters
                qt_widget = None
                qt_widget_setter_func = None
                widget_value_recover_func = lambda qt_widget: None
            else:
                # Numpy layers
                if param_type not in NAPARI_LAYER_MAPPINGS:
                    qt_widget = None
                    self.layer_comboboxes[param_type] = []
                else:
                    qt_widget = QComboBox()
                    if param_type not in self.layer_comboboxes:
                        self.layer_comboboxes[param_type] = []
                    self.layer_comboboxes[param_type].append(qt_widget)
                qt_widget_setter_func = None
                widget_value_recover_func = lambda qt_widget: None

            if qt_widget is not None:
                self.layout.addWidget(QLabel(param_values.get("title")), k, 0)
                self.layout.addWidget(qt_widget, k, 1)

            self.ui_state[param_name] = (param_type, qt_widget, qt_widget_setter_func, widget_value_recover_func)

        self._on_layer_change(None)  # Refresh dropdowns in new UI

    def _on_layer_change(self, *args, **kwargs):
        for kind, cb_list in self.layer_comboboxes.items():
            layer_type: Type[napari.layers.Layer] = NAPARI_LAYER_MAPPINGS[kind]
            for cb in cb_list:
                cb.clear()
                for layer in self.napari_results.viewer.layers:
                    if isinstance(layer, layer_type):
                        cb.addItem(layer.name, layer.data)

    def get_algo_params(self) -> Results:
        """Create a dictionary representation of parameter values based on the UI state."""
        algo_params = Results()
        for name, (kind, qt_widget, qt_widget_setter_func, widget_value_recover_func) in self.ui_state.items():
            if kind in NAPARI_LAYER_MAPPINGS:
                if qt_widget.currentText():
                    layer_name = qt_widget.currentText()
                    layer = self.napari_results.viewer.layers[layer_name]
                    data = layer.data if layer else None
                    # For Images and Masks, the results_layer.data is the napari layer's data (remains true when a mask is annotated)
                    # However, this is not the case for shapes (points, vectors, rectangles...).
                    # In this case, we need to manually sync results_layer.data with the current napari layer data here.
                    # This is not great (probably prone to bugs) - TODO: find a better way of handling this?
                    results_layer = self.napari_results.read(layer_name)
                    if results_layer is not None:
                        if results_layer.data is not data:
                            # Moreover, we need to handle boxes as a special case; Shapes.data are interpreted as boxes, 
                            # however the napari layer data is a list of arrays, so we need to cast it into a numpy array of shape (N, 4, D).
                            if results_layer.kind == "boxes":
                                if isinstance(data, list):
                                    if len(data) == 0:
                                        # If the layer data is an empty list, we should convert it to None instead.
                                        data = None
                                    else:
                                        # We assume the Shapes layer contains rectangles that can be casted to a single "boxes" array.
                                        try:
                                            data = np.asarray(data)
                                        except:
                                            print("Could not interpret the content of this Shapes layer as boxes (ignoring it instead): ", layer)
                                            data = None
                            self.napari_results.update(layer_name, data, results_layer.meta)
                else:
                    data = None
            else:
                data = widget_value_recover_func(qt_widget)
            algo_params.create(kind=kind, data=data, name=name)
        return algo_params

    def manage_cbs_events(self, worker):
        """Whenever a worker returns, we update the napari layer comboboxes to their current index (instead of resetting it)"""
        for kind, cb_list in self.layer_comboboxes.items():
            for cb in cb_list:
                worker.returned.connect(lambda _: cb.setCurrentIndex(cb.currentIndex()))
