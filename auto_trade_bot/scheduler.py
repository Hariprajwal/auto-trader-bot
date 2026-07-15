import traceback

import schedule


class SafeScheduler(schedule.Scheduler):
    """
    Wrapper around schedule.Scheduler that catches and logs exceptions
    instead of crashing the entire bot on a single failed job.
    """

    def __init__(self, logger=None):
        super().__init__()
        self.logger = logger

    def _run_job(self, job):
        try:
            super()._run_job(job)
        except Exception as e:
            if self.logger:
                self.logger.error(f"Unhandled exception in scheduled job: {e}\n{traceback.format_exc()}")
            else:
                print(f"[SCHEDULER ERROR] {e}\n{traceback.format_exc()}")
