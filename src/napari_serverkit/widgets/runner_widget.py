from functools import partial
from typing import Callable, Dict, Optional

from imaging_server_kit.core.stack import Stack
from imaging_server_kit.core.algorithm import Algorithm
from imaging_server_kit.core.tiling import TilingSpecs
from imaging_server_kit.types import layer_factory
import imaging_server_kit.core._etc as etc
from napari.utils.notifications import show_warning
from napari_toolkit.containers.collapsible_groupbox import QCollapsibleGroupBox
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDoubleSpinBox,
    QGridLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QWidget,
)


def require_algorithm(func):
    def wrapper(self, *args, **kwargs):
        if self.cb_algorithms.currentText() == "":
            raise Exception("Algoritm selection required")
        else:
            return func(self, *args, **kwargs)

    return wrapper


class RunnerWidget:
    def __init__(self, algorithm: Optional[Algorithm]):
        self.algorithm = algorithm

        # Layout and widget
        self._widget = QWidget()
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self._widget.setLayout(layout)

        # Algorithms
        self.cb_algorithms = QComboBox()
        layout.addWidget(QLabel("Algorithm"), 1, 0)
        layout.addWidget(self.cb_algorithms, 1, 1)

        # Info link
        self.algo_info_btn = QPushButton("🌐 Doc")
        self.algo_info_btn.clicked.connect(self._open_info_link_from_btn)
        layout.addWidget(self.algo_info_btn, 1, 2)

        # Samples
        self.samples_select = QComboBox()
        self.samples_select_btn = QPushButton("Load")
        self.samples_select_label = QLabel("Samples (0)")
        layout.addWidget(self.samples_select_label, 2, 0)
        layout.addWidget(self.samples_select, 2, 1)
        layout.addWidget(self.samples_select_btn, 2, 2)
        self.samples_select.setVisible(False)
        self.samples_select_btn.setVisible(False)
        self.samples_select_label.setVisible(False)

        # (Experimental) run in tiles
        self.experimental_gb = QCollapsibleGroupBox("Tiled inference")  # type: ignore
        self.experimental_gb.setChecked(False)
        experimental_layout = QGridLayout(self.experimental_gb)
        layout.addWidget(self.experimental_gb, 3, 0, 1, 3)

        experimental_layout.addWidget(QLabel("Run in tiles"), 0, 0)
        self.cb_run_in_tiles = QCheckBox()
        self.cb_run_in_tiles.setChecked(False)
        self.cb_run_in_tiles.toggled.connect(self._run_in_tiles_changed)
        experimental_layout.addWidget(self.cb_run_in_tiles, 0, 1)

        experimental_layout.addWidget(QLabel("Tile size [px]"), 1, 0)
        self.qds_tile_size = QSpinBox()
        self.qds_tile_size.setMinimum(16)
        self.qds_tile_size.setMaximum(4096)
        self.qds_tile_size.setSingleStep(16)
        self.qds_tile_size.setValue(128)
        self.qds_tile_size.setEnabled(False)
        experimental_layout.addWidget(self.qds_tile_size, 1, 1)

        experimental_layout.addWidget(QLabel("Overlap [0-1]"), 2, 0)
        self.qds_overlap = QDoubleSpinBox()
        self.qds_overlap.setMinimum(0)
        self.qds_overlap.setMaximum(1)
        self.qds_overlap.setSingleStep(0.01)
        self.qds_overlap.setValue(0)
        self.qds_overlap.setEnabled(False)
        experimental_layout.addWidget(self.qds_overlap, 2, 1)

        experimental_layout.addWidget(QLabel("Delay [sec]"), 3, 0)
        self.qds_delay = QDoubleSpinBox()
        self.qds_delay.setMinimum(0)
        self.qds_delay.setMaximum(1)
        self.qds_delay.setSingleStep(0.1)
        self.qds_delay.setValue(0)
        self.qds_delay.setEnabled(False)
        experimental_layout.addWidget(self.qds_delay, 3, 1)

        experimental_layout.addWidget(QLabel("Randomize"), 4, 0)
        self.cb_randomize = QCheckBox()
        self.cb_randomize.setChecked(True)
        self.cb_randomize.setEnabled(False)
        experimental_layout.addWidget(self.cb_randomize, 4, 1)

    @property
    def widget(self) -> QWidget:
        return self._widget

    @property
    def update_params_trigger(self) -> Callable:
        return self.cb_algorithms.currentTextChanged  # type: ignore

    @require_algorithm
    def _download_sample(self, *args, **kwargs) -> Stack:
        try:
            if self.algorithm:
                sample = self.algorithm.get_sample(
                    self.cb_algorithms.currentText(), *args, **kwargs
                )
                if sample is not None:
                    return sample
        except:
            show_warning("Failed to download sample.")
        return Stack()

    @require_algorithm
    def _get_run_func(self, algo_params: Dict):
        if not self.algorithm:
            return

        algorithm: str = self.cb_algorithms.currentText()

        tiled = self.cb_run_in_tiles.isChecked()

        algo_param_defs: Dict = self.algorithm.get_parameters(algorithm)["properties"]

        signature_params = self.algorithm.get_signature_params(algorithm)

        resolved_params = etc.resolve_params(
            algo_param_defs,
            signature_params,
            args=(),
            algo_params=algo_params,
        )

        params_stack = Stack()
        for name, data in resolved_params.items():
            kw = algo_param_defs[name]
            kind = kw.pop("param_type")
            if "anyOf" in kw:
                kw.pop("anyOf")  # added by Pydantic - we don't need it.
            param_layer = layer_factory(kind=kind, data=data, name=name, **kw)
            params_stack.add(param_layer)

        if tiled:
            tiling_ctx = TilingSpecs(
                tile_size=self.qds_tile_size.value(),
                tile_overlap=self.qds_overlap.value(),
                tile_delay=self.qds_delay.value(),
                tile_randomize=self.cb_randomize.isChecked(),
            )
        else:
            tiling_ctx = None
        
        return partial(
            self.algorithm.run_generator,
            algorithm=algorithm,
            tiling_ctx=tiling_ctx,
            params_stack=params_stack,
        ), params_stack.extent  # Also return the parameters extent

    @require_algorithm
    def _open_info_link_from_btn(self, *args, **kwargs):
        self.algorithm.info(algorithm=self.cb_algorithms.currentText())  # type: ignore

    @require_algorithm
    def get_algorithm_parameters(self):
        return self.algorithm.get_parameters(self.cb_algorithms.currentText())  # type: ignore

    @require_algorithm
    def update_n_samples(self):
        n_samples_available = self.algorithm.get_n_samples(self.cb_algorithms.currentText())  # type: ignore

        self.samples_select.clear()
        if n_samples_available == 0:
            self.samples_select.setVisible(False)
            self.samples_select_btn.setVisible(False)
            self.samples_select_label.setVisible(False)
        else:
            self.samples_select.setVisible(True)
            self.samples_select_btn.setVisible(True)
            self.samples_select_label.setVisible(True)
            self.samples_select.addItems([f"{k}" for k in range(n_samples_available)])
            self.samples_select_label.setText(f"Samples ({n_samples_available})")

    @require_algorithm
    def update_tiled_ui(self):
        algo_is_tileable = self.algorithm.is_tileable(self.cb_algorithms.currentText())
        
        if algo_is_tileable is False:
            # Make sure not to run in tiled mode
            self.cb_run_in_tiles.setChecked(False)
                   
        self.experimental_gb.setVisible(algo_is_tileable)

    def _run_in_tiles_changed(self, run_in_tiles: bool):
        for ui_element in [
            self.qds_tile_size,
            self.qds_overlap,
            self.qds_delay,
            self.cb_randomize,
        ]:
            ui_element.setEnabled(run_in_tiles)
