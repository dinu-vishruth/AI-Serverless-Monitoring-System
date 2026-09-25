"""
ML data preprocessing — converts raw monitoring records into feature vectors.

Features used by the Isolation Forest model:
  - response_time           : HTTP response time in ms
  - error_rate              : Error rate (0.0 – 1.0)
  - availability            : Availability (0 or 1)
  - status_code             : HTTP status code (normalized)
  - timeout                 : Whether the request timed out (0 or 1)
  - request_success         : Whether the request succeeded (0 or 1)

Derived features (computed from historical window):
  - rolling_avg_response_time   : Mean response time over the window
  - response_time_change        : Ratio of current to rolling average
  - rolling_error_rate          : Mean error rate over the window
  - error_rate_change           : Ratio of current to rolling average
  - recent_anomaly_count        : Number of anomalies in the recent window
"""

import numpy as np
import pandas as pd
from typing import Optional


# Feature columns used by the model
BASE_FEATURES = [
    "response_time",
    "error_rate",
    "availability",
    "status_code_normalized",
    "timeout",
    "request_success",
]

DERIVED_FEATURES = [
    "rolling_avg_response_time",
    "response_time_change",
    "rolling_error_rate",
    "error_rate_change",
]

ALL_FEATURES = BASE_FEATURES + DERIVED_FEATURES


def normalize_status_code(code: int) -> float:
    """
    Normalizes HTTP status codes to 0–1 range.
    2xx → 0.0 (good), 3xx → 0.25, 4xx → 0.5, 5xx → 1.0 (bad)
    """
    if 200 <= code < 300:
        return 0.0
    elif 300 <= code < 400:
        return 0.25
    elif 400 <= code < 500:
        return 0.5
    elif 500 <= code < 600:
        return 1.0
    else:
        return 0.75  # Unknown codes


def records_to_dataframe(records: list[dict]) -> pd.DataFrame:
    """Converts raw monitoring records into a cleaned DataFrame."""
    if not records:
        return pd.DataFrame(columns=BASE_FEATURES)

    df = pd.DataFrame(records)

    # Ensure required columns exist with defaults
    defaults = {
        "response_time": 0.0,
        "error_rate": 0.0,
        "availability": 1.0,
        "status_code": 200,
        "timeout": 0,
        "request_success": 1,
    }
    for col, default in defaults.items():
        if col not in df.columns:
            df[col] = default

    # Convert types
    for col in ["response_time", "error_rate", "availability"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(defaults[col])

    for col in ["status_code", "timeout", "request_success"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(defaults[col]).astype(int)

    # Add normalized status code
    df["status_code_normalized"] = df["status_code"].apply(normalize_status_code)

    return df


def add_derived_features(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """
    Adds rolling/derived features to the DataFrame.
    Uses a rolling window to compute trends.
    """
    if df.empty or len(df) < 2:
        for feat in DERIVED_FEATURES:
            df[feat] = 0.0
        return df

    # Sort by timestamp if available
    if "timestamp" in df.columns:
        df = df.sort_values("timestamp").reset_index(drop=True)

    # Rolling averages
    effective_window = min(window, len(df))
    df["rolling_avg_response_time"] = (
        df["response_time"].rolling(window=effective_window, min_periods=1).mean()
    )
    df["rolling_error_rate"] = (
        df["error_rate"].rolling(window=effective_window, min_periods=1).mean()
    )

    # Change ratios (current / rolling average) — clamped to avoid div-by-zero
    df["response_time_change"] = np.where(
        df["rolling_avg_response_time"] > 0,
        df["response_time"] / df["rolling_avg_response_time"],
        1.0,
    )
    df["error_rate_change"] = np.where(
        df["rolling_error_rate"] > 0,
        df["error_rate"] / df["rolling_error_rate"],
        1.0,
    )

    # Cap extreme values
    df["response_time_change"] = df["response_time_change"].clip(0, 10)
    df["error_rate_change"] = df["error_rate_change"].clip(0, 10)

    return df


def extract_features(df: pd.DataFrame) -> np.ndarray:
    """Extracts the feature matrix for the ML model."""
    # Ensure all feature columns exist
    for col in ALL_FEATURES:
        if col not in df.columns:
            df[col] = 0.0

    features = df[ALL_FEATURES].values.astype(np.float64)

    # Replace NaN/inf with 0
    features = np.nan_to_num(features, nan=0.0, posinf=0.0, neginf=0.0)

    return features


def prepare_single_record(
    record: dict, historical_records: Optional[list[dict]] = None
) -> np.ndarray:
    """
    Prepares a single monitoring record for prediction.
    If historical records are provided, derived features are computed from them.
    """
    if historical_records:
        all_records = historical_records + [record]
    else:
        all_records = [record]

    df = records_to_dataframe(all_records)
    df = add_derived_features(df)

    # Return only the last row (the current record)
    features = extract_features(df)
    return features[-1:, :]


def validate_records(records: list[dict]) -> list[dict]:
    """Removes invalid/incomplete records before training."""
    valid = []
    for r in records:
        if not r.get("service_id") or not r.get("timestamp"):
            continue
        if r.get("response_time") is None and r.get("status_code") is None:
            continue
        valid.append(r)
    return valid
