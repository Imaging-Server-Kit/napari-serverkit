from typing import Callable
from napari.qt.threading import thread_worker, GeneratorWorker

from napari_serverkit.widgets.parameter_panel import ParameterPanel


class TaskManager:
    def __init__(
        self,
        grayout_ui: Callable,
        ungrayout_ui: Callable,
        progress_update_func: Callable,
        parameters_panel: ParameterPanel,
    ):
        self.progress_update_func = progress_update_func
        self.ungrayout_func = ungrayout_ui
        self.grayout_func = grayout_ui
        self.active_workers = []
        self.parameters_panel = parameters_panel

    @property
    def n_active(self):
        return len(self.active_workers)

    def add_active(self, task: Callable, return_func: Callable, max_iter: int = 0):
        worker = thread_worker(task)()

        worker.returned.connect(return_func)
        worker.returned.connect(self._worker_stopped)
        worker.errored.connect(self._worker_errored)

        if isinstance(worker, GeneratorWorker):
            worker.yielded.connect(return_func)
            worker.aborted.connect(self._worker_stopped)

        self.parameters_panel.manage_cbs_events(worker)

        if max_iter > 0:
            worker.yielded.connect(lambda step: self.progress_update_func(step))

        self.active_workers.append(worker)
        self.grayout_func()
        worker.start()

    def cancel_all(self):
        for worker in self.active_workers:
            worker.quit()

    def _worker_stopped(self):
        self.ungrayout_func()
        self.active_workers.clear()  # TODO: only stop the worker that finished?
    
    def _worker_errored(self, e: Exception):
        self._worker_stopped()