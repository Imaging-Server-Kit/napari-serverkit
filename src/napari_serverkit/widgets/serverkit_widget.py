from functools import partial
from typing import Dict
import napari
from napari.utils.notifications import show_info, show_warning
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QProgressBar, QPushButton, QVBoxLayout, QWidget

from imaging_server_kit.core.errors import (
    AlgorithmServerError,
    ServerRequestError,
)

from napari_serverkit.widgets.parameter_panel import ParameterPanel, NAPARI_LAYER_MAPPINGS
from napari_serverkit.widgets.task_manager import TaskManager
from napari_serverkit.widgets.napari_results import NapariResults
from napari_serverkit.widgets.runner_widget import RunnerWidget


class ServerKitWidget(QWidget):
    def __init__(self, viewer: napari.Viewer, runner_widget: RunnerWidget):
        super().__init__()
        self.napari_results = NapariResults(viewer)
        self.runner_widget = runner_widget

        # Layout
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        self.setLayout(layout)

        # Add the runner's extra UI
        layout.addWidget(self.runner_widget.widget)

        # Connect the ComboBox change from the runner to the UI update
        self.runner_widget.update_params_trigger.connect(self._algorithm_changed)

        # Connect the samples loading event
        self.runner_widget.samples_select_btn.clicked.connect(self._sample_triggered)

        # Algorithm parameters (dynamic UI)
        self.params_panel = ParameterPanel(
            trigger=self._run,  # gets linked to auto_call
            napari_results=self.napari_results,  # layer change events update the cbs
        )
        layout.addWidget(self.params_panel.widget)

        # Run button
        self.run_btn = QPushButton("Run", self)
        self.run_btn.clicked.connect(self._run)
        layout.addWidget(self.run_btn)

        # Task manager
        self.tasks = TaskManager(
            self._grayout_ui,  # called when worker starts
            self._ungrayout_ui,  # called when worker stops
            self._update_pbar,  # called when worker yields
            self.params_panel,  # linked to manage_cbs_events(worker)
        )

        self.grayout_ui_list = [self.params_panel.widget, self.run_btn]

        cancel_btn = QPushButton("❌ Cancel")
        cancel_btn.clicked.connect(self._cancel)
        layout.addWidget(cancel_btn)

        self.pbar = QProgressBar(minimum=0, maximum=1)
        layout.addWidget(self.pbar)

    def _algorithm_changed(self, selected_algo):
        if selected_algo == "":
            return
        try:
            # Update the parameters panel
            schema = self.runner_widget.get_algorithm_parameters()
            self.params_panel.update(schema)
            # Update the number of samples available
            self.runner_widget.update_n_samples()
        except (AlgorithmServerError, ServerRequestError) as e:
            show_warning(e.message)

    def _run(self):
        algo_params = self.params_panel.get_algo_params()

        try:
            task = self.runner_widget._get_run_func(algo_params)
        except (AlgorithmServerError, ServerRequestError) as e:
            show_warning(e.message)

        if task:
            return_func = partial(
                self.napari_results.merge,
                tiles_callback=self._update_pbar_on_tiled,
            )
            self.tasks.add_active(task=task, return_func=return_func)

    def _sample_triggered(self):
        idx = self.runner_widget.samples_select.currentText()
        if idx == "":
            return
        idx = int(idx)
        download_sample_func = partial(
            self.runner_widget._download_sample,
            idx=idx,
        )
        self.tasks.add_active(
            task=download_sample_func,
            return_func=self._sample_emitted,
        )

    def _sample_emitted(self, sample_params: Dict):
        sk_params = self.runner_widget._resolve_sk_params(sample_params)
        for param_name, skp in sk_params.items():
            kind = skp.kind
            data = skp.data
            name = skp.name
            meta = skp.meta
            if kind in list(NAPARI_LAYER_MAPPINGS.keys()):
                self.napari_results.create(kind=kind, data=data, name=name, meta=meta)
            else:
                # Set values in the parameters UI
                param_type, widget = self.params_panel.ui_state.get(param_name)
                if param_type == "dropdown":
                    widget.setCurrentText(data)
                elif param_type == "int":
                    widget.setValue(data)
                elif param_type == "float":
                    widget.setValue(data)
                elif param_type == "bool":
                    widget.setChecked(data)
                elif param_type == "str":
                    widget.setText(data)
                elif param_type == "notification":
                    widget.setText(data)

    def _cancel(self):
        show_info("Cancelling...")
        self.tasks.cancel_all()

    def _aborted(self):
        self._ungrayout_ui()
        self.pbar.setMaximum(1)

    def _grayout_ui(self):
        self.pbar.setMaximum(0)  # Start the pbar
        for ui_element in self.grayout_ui_list:
            ui_element.setEnabled(False)

    def _ungrayout_ui(self):
        self.pbar.setMaximum(1)  # Stop the pbar
        for ui_element in self.grayout_ui_list:
            ui_element.setEnabled(True)

    def _update_pbar(self, value: int):
        self.pbar.setValue(value)

    def _update_pbar_on_tiled(self, tile_idx, n_tiles):
        self.pbar.setMaximum(n_tiles)
        self.pbar.setValue(tile_idx)
