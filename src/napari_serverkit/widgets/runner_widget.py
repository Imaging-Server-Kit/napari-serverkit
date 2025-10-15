from functools import partial
from typing import Callable, Dict, Iterable
from napari.utils.notifications import show_warning
from napari_toolkit.containers.collapsible_groupbox import QCollapsibleGroupBox
from imaging_server_kit.core.algorithm import Algorithm

import numpy as np
from qtpy.QtWidgets import (
    QLabel,
    QPushButton,
    QComboBox,
    QCheckBox,
    QGridLayout,
    QSpinBox,
    QDoubleSpinBox,
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
    def __init__(self, server: Algorithm):
        self.runner = server

        # Layout and widget
        self._widget = QWidget()
        layout = QGridLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        self._widget.setLayout(layout)

        # Algorithms
        self.cb_algorithms = QComboBox()
        layout.addWidget(QLabel("Algorithm"), 1, 0)
        layout.addWidget(self.cb_algorithms, 1, 1, 1, 2)

        # Sample image
        self.sample_image_btn = QPushButton("Sample image(s)")
        layout.addWidget(self.sample_image_btn, 2, 0, 1, 3)

        # Algo info
        self.algo_info_btn = QPushButton("🌐 Documentation")
        self.algo_info_btn.clicked.connect(self._open_info_link_from_btn)
        layout.addWidget(self.algo_info_btn, 3, 0, 1, 3)

        # (Experimental) run in tiles
        experimental_gb = QCollapsibleGroupBox("Experimental")
        experimental_gb.setChecked(False)
        experimental_layout = QGridLayout(experimental_gb)
        layout.addWidget(experimental_gb, 4, 0, 1, 3)

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
        return self.cb_algorithms.currentTextChanged

    @require_algorithm
    def _download_samples_from_btn(self, *args, **kwargs) -> Iterable[np.ndarray]:
        try:
            return self.runner.get_sample_images(self.cb_algorithms.currentText())
        except:
            show_warning("Failed to download sample images.")
            return []

    @require_algorithm
    def _get_run_func(self, algo_params: Dict) -> Callable:
        algorithm = self.cb_algorithms.currentText()
        tiled = self.cb_run_in_tiles.isChecked()
        stream = self.runner._is_stream(algorithm)
        if tiled:
            if stream:
                show_warning("Cannot run streamed algorithm in tiling mode!")
                return
            return partial(
                self.runner._tile,
                algorithm=algorithm,
                tile_size_px=self.qds_tile_size.value(),
                overlap_percent=self.qds_overlap.value(),
                delay_sec=self.qds_delay.value(),
                randomize=self.cb_randomize.isChecked(),
                **algo_params,
            )
        else:
            if stream:
                return partial(
                    self.runner._stream,
                    algorithm=algorithm, 
                    **algo_params,
                )
            else:
                return partial(
                    self.runner._run,
                    algorithm=algorithm, 
                    **algo_params,
                )

    @require_algorithm
    def _open_info_link_from_btn(self, *args, **kwargs):
        self.runner.info(algorithm=self.cb_algorithms.currentText())

    @require_algorithm
    def get_algorithm_parameters(self):
        return self.runner.get_parameters(self.cb_algorithms.currentText())

    def _run_in_tiles_changed(self, run_in_tiles: bool):
        for ui_element in [
            self.qds_tile_size,
            self.qds_overlap,
            self.qds_delay,
            self.cb_randomize,
        ]:
            ui_element.setEnabled(run_in_tiles)

        