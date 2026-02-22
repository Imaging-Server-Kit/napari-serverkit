from typing import Callable, Dict, Optional, Type
from dataclasses import dataclass
import numpy as np

import napari.layers
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QLineEdit,
    QSpinBox,
    QWidget,
)

from napari_serverkit.widgets.napari_results import NapariResults

NAPARI_LAYER_MAPPINGS: Dict[str, Type[napari.layers.Layer]] = {
    "image": napari.layers.Image,
    "mask": napari.layers.Labels,
    "points": napari.layers.Points,
    "boxes": napari.layers.Shapes,
    "paths": napari.layers.Shapes,
    "vectors": napari.layers.Vectors,
    "tracks": napari.layers.Tracks,
}


@dataclass
class UIStateItem:
    param_type: str
    qt_widget: QWidget
    qt_widget_setter_func: Optional[Callable]
    widget_value_recover_func: Callable


class ParameterPanel:
    def __init__(self, trigger: Callable, napari_results: NapariResults):
        self._trigger_func = trigger
        self.napari_results = napari_results

        self.ui_state: Dict[str, UIStateItem] = {}
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

        # Generate the new dynamic UI state and layout
        self.ui_state: Dict[str, UIStateItem] = {}
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

            state_item = UIStateItem(
                param_type=param_type,
                qt_widget=qt_widget,
                qt_widget_setter_func=qt_widget_setter_func,
                widget_value_recover_func=widget_value_recover_func,
            )

            self.ui_state[param_name] = state_item

        self._on_layer_change(None)  # Refresh dropdowns in new UI

    def _on_layer_change(self, *args, **kwargs):
        for kind, cb_list in self.layer_comboboxes.items():
            layer_type: Type[napari.layers.Layer] = NAPARI_LAYER_MAPPINGS[kind]
            for cb in cb_list:
                cb.clear()
                for layer in self.napari_results.viewer.layers:
                    if isinstance(layer, layer_type):
                        
                        # Napari layers data are not always in the format expected by serverkit, so we do the conversion here
                        # and assign serverkit-formatted data to the combobox data attributes, which get retreived later as parameters
                        
                        # For boxes, extract the rectangle data from shapes layers (and convert them to Numpy)
                        if kind == "boxes":
                            data = None
                            if isinstance(layer.data, list):
                                if len(layer.data) > 0:
                                    rectangle_data = []
                                    for d, t in zip(layer.data, layer.shape_type):
                                        if t == "rectangle":
                                            rectangle_data.append(d)
                                    if len(rectangle_data) > 0:
                                        data = np.array(rectangle_data)
                            cb.addItem(layer.name, data)
                        
                        # For paths, extract the path data from shapes layers
                        elif kind == "paths":
                            data = None
                            if isinstance(layer.data, list):
                                if len(layer.data) > 0:
                                    path_data = []
                                    for d, t in zip(layer.data, layer.shape_type):
                                        if t == "rectangle":
                                            path_data.append(d)
                                    if len(path_data) > 0:
                                        data = path_data
                            cb.addItem(layer.name, data)
                        
                        else:                      
                            cb.addItem(layer.name, layer.data)

    def get_algo_params(self) -> Dict:
        """Create a dictionary representation of parameter values based on the UI state."""
        algo_params = {}
        for name, state_item in self.ui_state.items():
            if state_item.param_type in NAPARI_LAYER_MAPPINGS:
                if state_item.qt_widget.currentText():
                    data = state_item.qt_widget.currentData()
                    # layer_name = state_item.qt_widget.currentText()
                    # layer = self.napari_results.viewer.layers[layer_name]
                    # data = layer.data if layer else None               
                else:
                    data = None
            else:
                data = state_item.widget_value_recover_func(state_item.qt_widget)
            algo_params[name] = data
        return algo_params

    def manage_cbs_events(self, worker):
        """Whenever a worker returns, we update the napari layer comboboxes to their current index (instead of resetting it)"""
        for cb_list in self.layer_comboboxes.values():
            for cb in cb_list:
                worker.returned.connect(lambda _: cb.setCurrentIndex(cb.currentIndex()))
