"""Kelola scenario worker sebagai proses anak dari backend.

Worker tetap dipisahkan pada level proses agar koneksi TraCI miliknya tidak
bertabrakan dengan controller SUMO dashboard, tetapi operator cukup memulai
backend: lifecycle FastAPI yang menyalakan dan menghentikannya.
"""

from __future__ import annotations

import logging
import subprocess
import sys
from pathlib import Path


logger = logging.getLogger("uvicorn.error")
PROJECT_ROOT = Path(__file__).resolve().parents[3]
WORKER_SCRIPT = PROJECT_ROOT / "simulation" / "scenario_worker.py"


class ScenarioWorkerService:
    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None

    def start(self, interval_seconds: int = 60) -> None:
        if self._process is not None and self._process.poll() is None:
            return
        if not WORKER_SCRIPT.exists():
            logger.error("Scenario worker tidak ditemukan: %s", WORKER_SCRIPT)
            return

        command = [
            sys.executable,
            str(WORKER_SCRIPT),
            "--replay",
            "--full-cycle",
            "--interval",
            str(interval_seconds),
        ]
        self._process = subprocess.Popen(command, cwd=PROJECT_ROOT)
        logger.info(
            "Scenario worker replay otomatis aktif (PID %s, interval %ss).",
            self._process.pid,
            interval_seconds,
        )

    def stop(self) -> None:
        process = self._process
        self._process = None
        if process is None or process.poll() is not None:
            return

        logger.info("Menghentikan scenario worker otomatis (PID %s).", process.pid)
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            logger.warning("Scenario worker tidak berhenti dalam 10 detik; memaksa berhenti.")
            process.kill()
            process.wait(timeout=5)


scenario_worker_service = ScenarioWorkerService()
