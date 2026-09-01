"""Shared utilities for the pipeline: logging and merge diagnostics.

Every script does, near the top:

    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from utils import setup_logger, log_merge
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path


def setup_logger(name: str, logfile: str | None = None) -> logging.Logger:
    """Console + optional file logger, idempotent per name."""
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(name)s %(levelname)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(fmt)
    logger.addHandler(sh)
    if logfile:
        Path(logfile).parent.mkdir(parents=True, exist_ok=True)
        fh = logging.FileHandler(logfile)
        fh.setFormatter(fmt)
        logger.addHandler(fh)
    return logger


def log_merge(logger: logging.Logger, left, right, merged, on, how: str) -> None:
    """Log the shape story of a merge so match rates are auditable.

    If the merge was run with indicator=True, the _merge distribution is
    logged too. Call this after EVERY merge that feeds an analysis panel.
    """
    logger.info("merge on=%s how=%s | left=%d right=%d -> merged=%d",
                on, how, len(left), len(right), len(merged))
    if hasattr(merged, "columns") and "_merge" in getattr(merged, "columns", []):
        counts = merged["_merge"].value_counts(dropna=False)
        for key, val in counts.items():
            logger.info("  _merge %s: %d (%.1f%%)", key, val, 100 * val / len(merged))
        both = int(counts.get("both", 0))
        logger.info("  match rate (both/merged): %.3f", both / max(len(merged), 1))
