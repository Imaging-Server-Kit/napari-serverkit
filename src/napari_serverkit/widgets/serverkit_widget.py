from functools import partial
import napari
from napari.utils.notifications import show_info, show_warning
from qtpy.QtCore import Qt
from qtpy.QtWidgets import QProgressBar, QPushButton, QVBoxLayout, QWidget

from imaging_server_kit.core.errors import (
    AlgorithmServerError,
    ServerRequestError,
)

from napari_serverkit.widgets.parameter_panel import ParameterPanel
from napari_serverkit.widgets.task_manager import TaskManager
from napari_serverkit.widgets.napari_results import NapariResults
from napari_serverkit.widgets.runner_widget import RunnerWidget


class ServerKitWidget(QWidget):
    def __init__(self, viewer: napari.Viewer, runner_widget: RunnerWidget):
        super().__init__()
        self.sk_viewer = NapariResults(viewer)
        self.runner_widget = runner_widget

        # Layout
        layout = QVBoxLayout()
        layout.setAlignment(Qt.AlignTop)
        self.setLayout(layout)

        # Add the runner's extra UI
        layout.addWidget(self.runner_widget.widget)

        # Connect the ComboBox change from the runner to the UI update
        self.runner_widget.update_params_trigger.connect(self._algorithm_changed)

        self.runner_widget.sample_image_btn.clicked.connect(self._download_samples)

        # Algorithm parameters (dynamic UI)
        self.params_panel = ParameterPanel(
            trigger=self._run,  # gets linked to auto_call
            napari_results=self.sk_viewer,  # layer change events update the cbs
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
            schema = self.runner_widget.get_algorithm_parameters()
            self.params_panel.update(schema)
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
                self.sk_viewer.merge,
                tiles_callback=self._update_pbar_on_tiled,
            )
            self.tasks.add_active(task=task, return_func=return_func)

    def _download_samples(self):
        self.tasks.add_active(
            task=self.runner_widget._download_samples_from_btn,
            return_func=self.sk_viewer.samples_emitted,
        )

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
