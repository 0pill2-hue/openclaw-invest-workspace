from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Iterable

import pandas as pd


def atomic_write_csv(df: pd.DataFrame, path: str | Path, *, index: bool = False, encoding: str = 'utf-8-sig') -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f'.{target.name}.', suffix='.tmp', dir=str(target.parent))
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        df.to_csv(tmp_path, index=index, encoding=encoding)
        os.replace(tmp_path, target)
    finally:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def merge_dedup_sort(existing: pd.DataFrame | None, new_rows: pd.DataFrame, *, key_columns: Iterable[str]) -> pd.DataFrame:
    frames = []
    if existing is not None and not existing.empty:
        frames.append(existing.copy())
    if new_rows is not None and not new_rows.empty:
        frames.append(new_rows.copy())
    if not frames:
        return pd.DataFrame()

    merged = pd.concat(frames, ignore_index=True)
    key_columns = list(key_columns)
    merged = merged.drop_duplicates(subset=key_columns, keep='last')
    if 'Date' in merged.columns:
        merged['Date'] = pd.to_datetime(merged['Date'], errors='coerce')
        merged = merged.sort_values(['Date'] + [c for c in key_columns if c != 'Date']).reset_index(drop=True)
        merged['Date'] = merged['Date'].dt.strftime('%Y-%m-%d')
    return merged


def append_report_rows(path: str | Path, rows: pd.DataFrame) -> None:
    report_path = Path(path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    if rows is None or rows.empty:
        return
    if report_path.exists():
        prev = pd.read_csv(report_path)
        rows = pd.concat([prev, rows], ignore_index=True)
    rows.to_csv(report_path, index=False, encoding='utf-8-sig')
