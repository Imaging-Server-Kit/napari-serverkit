from functools import partial
from typing import Callable, Dict, Optional

from imaging_server_kit.core.results import DataLayer, Results
from imaging_server_kit.core.algorithm import Algorithm
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
        self.experimental_gb = QCollapsibleGroupBox("Tiled inference") # type: ignore
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
        return self.cb_algorithms.currentTextChanged # type: ignore

    @require_algorithm
    def _download_sample(self, *args, **kwargs) -> Results:
        try:
            sample = self.algorithm.get_sample( # type: ignore
                self.cb_algorithms.currentText(), *args, **kwargs
            )
            if sample is not None:
                return sample
        except:
            show_warning("Failed to download sample.")
        return Results()

    @require_algorithm
    def _get_run_func(self, algo_params: Results) -> Optional[Callable]:
        algorithm: str = self.cb_algorithms.currentText()
        tiled = self.cb_run_in_tiles.isChecked()
        is_stream = self.algorithm._is_stream(algorithm) # type: ignore

        # Handle the RGB case (suboptimal)
        algo_param_defs: Dict = self.algorithm.get_parameters(algorithm)["properties"] # type: ignore
        for param_name, param_value in algo_param_defs.items():
            layer: Optional[DataLayer] = algo_params.read(param_name)
            if layer is not None:
                if layer.kind == "image":
                    layer.rgb = param_value.get("rgb") # type: ignore

        if tiled:
            if is_stream:
                show_warning("Cannot run streamed algorithm in tiling mode!")
                return
            return partial(
                self.algorithm._tile, # type: ignore
                algorithm=algorithm,
                tile_size_px=self.qds_tile_size.value(),
                overlap_percent=self.qds_overlap.value(),
                delay_sec=self.qds_delay.value(),
                randomize=self.cb_randomize.isChecked(),
                param_results=algo_params,
            )
        else:
            if is_stream:
                return partial(
                    self.algorithm._stream, # type: ignore
                    algorithm=algorithm,
                    param_results=algo_params,
                )
            else:
                return partial(
                    self.algorithm._run, # type: ignore
                    algorithm=algorithm,
                    param_results=algo_params,
                )

    @require_algorithm
    def _open_info_link_from_btn(self, *args, **kwargs):
        self.algorithm.info(algorithm=self.cb_algorithms.currentText()) # type: ignore

    @require_algorithm
    def get_algorithm_parameters(self):
        return self.algorithm.get_parameters(self.cb_algorithms.currentText()) # type: ignore

    @require_algorithm
    def update_n_samples(self):
        n_samples_available = self.algorithm.get_n_samples(self.cb_algorithms.currentText()) # type: ignore
        
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
        self.experimental_gb.setVisible(algo_is_tileable)
    
    def _run_in_tiles_changed(self, run_in_tiles: bool):
        for ui_element in [
            self.qds_tile_size,
            self.qds_overlap,
            self.qds_delay,
            self.cb_randomize,
        ]:
            ui_element.setEnabled(run_in_tiles)