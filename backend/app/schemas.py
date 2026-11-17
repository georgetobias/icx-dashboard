from __future__ import annotations

from typing import Any

import numpy as np
import pandas as pd


def clean_value(value: Any) -> Any:
    if value is pd.NA:
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, float) and (np.isnan(value) or np.isinf(value)):
        return None
    if isinstance(value, (np.bool_,)):
        return bool(value)
    return value


def records(df: pd.DataFrame, columns: list[str] | None = None) -> list[dict[str, Any]]:
    if columns is not None:
        df = df[[col for col in columns if col in df.columns]].copy()
    return [
        {key: clean_value(value) for key, value in row.items()}
        for row in df.to_dict(orient="records")
    ]

