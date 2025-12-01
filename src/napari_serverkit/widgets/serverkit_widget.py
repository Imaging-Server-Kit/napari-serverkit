from functools import partial
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
from imaging_server_kit.core.results import LayerStackBase


class ServerKitWidget(QWidget):
    def __init__(self, viewer: napari.Viewer, runner_widget: RunnerWidget):
        super().__init__()
        self.napari_results = NapariResults(viewer)
        self.runner_widget = runner_widget

        # Layout
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop) # type: ignore
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

        self.pbar = QProgressBar(minimum=0, maximum=1) # type: ignore
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
            # Check if tiled inference should be displayed or not
            self.runner_widget.update_tiled_ui()
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
            self.tasks.add_active(task, return_func)

    def _sample_triggered(self):
        idx = self.runner_widget.samples_select.currentText()
        if idx == "":
            return
        self.tasks.add_active(
            task=partial(self.runner_widget._download_sample, idx=int(idx)),
            return_func=self._sample_emitted,
        )

    def _sample_emitted(self, sample: LayerStackBase):
        for sp in sample:
            if sp.kind in NAPARI_LAYER_MAPPINGS:
                if sp.data is not None:
                    self.napari_results.create(sp.kind, sp.data, sp.name, sp.meta)
            else:
                # Set values in the parameters UI
                qt_widget_setter_func = self.params_panel.ui_state[sp.name][2]
                if qt_widget_setter_func is not None:
                    qt_widget_setter_func(sp.data)

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
