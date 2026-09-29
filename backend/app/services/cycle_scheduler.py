"""
CYCLE SCHEDULER — continuous autonomous operation.

The scheduler is only a wrapper around the canonical ``run_once`` runner.  It
uses a process lock plus an advisory file lock where available, never lets a
failed tick stop future ticks, and reports timeout truthfully (a Python thread
cannot safely be killed, so a timed-out run is marked timed out while the
worker is allowed to finish before the next run is admitted).
"""

import logging
import os
import signal
import time
from pathlib import Path
from threading import Event, Lock, Thread
from typing import Callable

from . import backup

log = logging.getLogger("forgeos.scheduler")

_SCRIPT_DIR = Path(__file__).resolve().parent.parent.parent / "scripts"
_sys = __import__("sys")
if str(_SCRIPT_DIR) not in _sys.path:
    _sys.path.insert(0, str(_SCRIPT_DIR))
from scripts import run_daily_cycle  # noqa: E402


class _ProcessRunLock:
    """Best-effort cross-process lock using a lock file and fcntl."""

    def __init__(self, path: Path):
        self.path = path
        self._fh = None

    def acquire(self) -> bool:
        try:
            import fcntl
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._fh = open(self.path, "a+")
            fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            return True
        except (BlockingIOError, OSError):
            if self._fh:
                self._fh.close()
                self._fh = None
            return False

    def release(self) -> None:
        if self._fh:
            try:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            finally:
                self._fh.close()
                self._fh = None


class CycleScheduler:
    def __init__(self, interval_seconds: int = 3600,
                 backup_interval_seconds: int | None = 6 * 3600,
                 backup_keep: int = 10, max_run_seconds: int = 600,
                 lock_path: Path | None = None):
        self.interval_seconds = max(10, int(interval_seconds))
        self.backup_interval_seconds = backup_interval_seconds
        self.backup_keep = int(backup_keep)
        if self.backup_keep < 1:
            raise ValueError("backup_keep must be >= 1")
        self.max_run_seconds = max(1, int(max_run_seconds))
        self._stop = Event()
        self._running = Event()
        self._lock = Lock()
        self._last_backup_ts: float | None = None
        self._process_lock = _ProcessRunLock(lock_path or (backup._DEFAULT_STORAGE / "scheduler.run.lock"))

    def start(self) -> None:
        log.info("Scheduler started: cycle every %ss, backup every %s (keep %s)",
                 self.interval_seconds, self.backup_interval_seconds, self.backup_keep)
        self._stop.clear()
        self._reconcile_stale_cycles()
        self._tick(force_backup_check=True)
        while not self._stop.wait(self.interval_seconds):
            self._tick()

    @staticmethod
    def _reconcile_stale_cycles() -> None:
        """Recover observability records abandoned by a prior process."""
        try:
            from app import database
            from app.services import truth_audit

            database.init_db()
            db = database.SessionLocal()
            try:
                reconciled = truth_audit.reconcile_stale_cycles(db)
                if reconciled:
                    log.warning("Reconciled %s stale cycle record(s) before starting.", reconciled)
            finally:
                db.close()
        except Exception:
            log.exception("Could not reconcile stale cycle records; scheduler will continue.")

    def stop(self) -> None:
        self._stop.set()
        log.info("Scheduler stop requested; no new runs will start.")

    def wait(self, timeout: float | None = None) -> None:
        self._running.wait(timeout)
        if timeout is None:
            while self._running.is_set():
                time.sleep(0.2)

    def run_single_cycle(
        self, on_timeout: Callable[[], None] | None = None
    ) -> dict:
        """Run one scheduled invocation through the canonical timeout/log path."""
        return self._run_cycle_with_timeout(on_timeout=on_timeout)

    def _tick(self, force_backup_check: bool = False) -> None:
        if self._running.is_set():
            log.warning("Skipping tick: a cycle run is still in progress.")
            return
        if not self._lock.acquire(blocking=False):
            log.warning("Skipping tick: another local run is in progress.")
            return
        if not self._process_lock.acquire():
            self._lock.release()
            log.warning("Skipping tick: another scheduler process is in progress.")
            return
        self._running.set()
        release_deferred = False
        try:
            result = self._run_cycle_with_timeout(on_timeout=self._release_run_locks)
            release_deferred = result.get("lock_release_deferred") is True
        except Exception:
            log.exception("Unexpected scheduler error during cycle; next tick will continue.")
        finally:
            if not release_deferred:
                self._release_run_locks()

        now = time.time()
        if self.backup_interval_seconds and (force_backup_check or self._last_backup_ts is None or
                                             now - self._last_backup_ts >= self.backup_interval_seconds):
            self._maybe_backup()

    def _run_cycle_with_timeout(
        self, on_timeout: Callable[[], None] | None = None
    ) -> dict:
        result: dict = {}
        error: list[BaseException] = []

        def worker() -> None:
            try:
                result.update(self._run_cycle())
            except BaseException as exc:
                error.append(exc)

        started = time.monotonic()
        thread = Thread(target=worker, name="forgeos-cycle", daemon=True)
        thread.start()
        thread.join(self.max_run_seconds)
        if thread.is_alive():
            log.error("Cycle timed out after %ss; run remains in progress and will not overlap.",
                      self.max_run_seconds)
            if on_timeout is not None:
                def release_when_finished() -> None:
                    thread.join()
                    on_timeout()

                release_thread = Thread(
                    target=release_when_finished,
                    name="forgeos-cycle-lock-release",
                    daemon=True,
                )
                try:
                    release_thread.start()
                except (OSError, RuntimeError):
                    thread.join()
                    raise
            return {
                "status": "timeout",
                "duration_ms": int((time.monotonic() - started) * 1000),
                "lock_release_deferred": on_timeout is not None,
            }
        if error:
            raise error[0]
        return result

    def _release_run_locks(self) -> None:
        self._running.clear()
        try:
            self._process_lock.release()
        finally:
            self._lock.release()

    def _run_cycle(self) -> dict:
        started = time.monotonic()
        record = run_daily_cycle.run_once()
        duration_ms = int((time.monotonic() - started) * 1000)
        forge_error = record.get("forge_cycle_error")
        autonomy_error = record.get("autonomy_cycle_error")
        status = "ok" if forge_error is None and autonomy_error is None else "error"
        log_fn = log.info if status == "ok" else log.warning
        log_fn("Cycle finished status=%s duration_ms=%d forge=%s autonomy=%s", status, duration_ms,
               forge_error, autonomy_error)
        try:
            backup.append_scheduler_log("cycle_run", status, record, duration_ms)
        except Exception:
            log.exception("Scheduler log append failed; cycle result is preserved.")
        return record

    def _maybe_backup(self) -> None:
        try:
            made = backup.safe_backup(keep=self.backup_keep)
            legacy = backup.archive_legacy_snapshots(keep=2)
            log.info("Database backup result: %s; legacy retention: %s", made, legacy)
            self._last_backup_ts = time.time()
        except Exception:
            log.exception("Backup failed (non-fatal); next tick will retry.")

    @staticmethod
    def install_signal_handlers(scheduler: "CycleScheduler") -> None:
        def _handler(signum, frame):
            scheduler.stop()
        signal.signal(signal.SIGINT, _handler)
        signal.signal(signal.SIGTERM, _handler)


def run(interval: int = 3600, backup_every: int | None = 6 * 3600, backup_keep: int = 10) -> None:
    scheduler = CycleScheduler(interval_seconds=interval, backup_interval_seconds=backup_every,
                                backup_keep=backup_keep)
    CycleScheduler.install_signal_handlers(scheduler)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    try:
        scheduler.start()
    except KeyboardInterrupt:
        scheduler.stop()
