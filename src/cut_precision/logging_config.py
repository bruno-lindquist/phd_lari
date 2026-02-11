from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from uuid import uuid4
import sys
import time

from loguru import logger


def build_run_id() -> str:
    return uuid4().hex[:12]


def setup_logging(out_dir: str | Path, run_id: str, debug: bool = False):
    log_dir = Path(out_dir)
    log_dir.mkdir(parents=True, exist_ok=True)
    logger.remove()
    logger.add(sys.stderr, level="DEBUG" if debug else "INFO")
    logger.add(log_dir / "run.log", level="DEBUG", rotation="10 MB", retention="14 days")
    logger.add(
        log_dir / "run.jsonl",
        level="INFO",
        rotation="10 MB",
        retention="14 days",
        serialize=True,
    )
    return logger.bind(run_id=run_id)


@contextmanager
def log_stage(log, stage: str) -> Iterator[None]:
    started = time.perf_counter()
    log.bind(event=f"{stage}.start", stage=stage, status="started").info("stage_start")
    try:
        yield
    except Exception:
        duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
        log.bind(
            event=f"{stage}.error",
            stage=stage,
            status="failed",
            duration_ms=duration_ms,
        ).exception("stage_failed")
        raise
    duration_ms = round((time.perf_counter() - started) * 1000.0, 2)
    log.bind(
        event=f"{stage}.end",
        stage=stage,
        status="ok",
        duration_ms=duration_ms,
    ).info("stage_end")
