"""
Risk analysis module — calculates failure/degradation risk scores.

Risk Score (0–100) is computed from multiple weighted factors:
  - Response time vs. threshold         (25%)
  - Response time trend                 (15%)
  - Error rate                          (20%)
  - Error rate trend                    (10%)
  - Availability                        (15%)
  - Timeout frequency                   (10%)
  - Recent anomaly count                (5%)

Risk Levels:
   0 – 25  : LOW
  26 – 50  : MEDIUM
  51 – 75  : HIGH
  76 – 100 : CRITICAL

IMPORTANT: This risk score is a heuristic composite indicator, NOT a
statistically calibrated probability of failure.
"""

from typing import Optional
from backend.utils.logger import get_logger

logger = get_logger(__name__)


# Factor weights (must sum to 1.0)
WEIGHTS = {
    "response_time": 0.25,
    "response_time_trend": 0.15,
    "error_rate": 0.20,
    "error_rate_trend": 0.10,
    "availability": 0.15,
    "timeout": 0.10,
    "anomaly_count": 0.05,
}

# Risk level thresholds
RISK_LEVELS = [
    (25, "LOW"),
    (50, "MEDIUM"),
    (75, "HIGH"),
    (100, "CRITICAL"),
]


def _score_response_time(current: float, threshold: float) -> float:
    """Scores response time (0–100). Higher current → higher score."""
    if threshold <= 0:
        return 0.0
    ratio = current / threshold
    if ratio <= 0.5:
        return 0.0
    elif ratio <= 1.0:
        return (ratio - 0.5) * 100  # 0–50
    elif ratio <= 2.0:
        return 50 + (ratio - 1.0) * 50  # 50–100
    else:
        return 100.0


def _score_response_time_trend(current: float, historical_avg: float) -> float:
    """Scores response time trend. Large increases → higher score."""
    if historical_avg <= 0:
        return 0.0
    ratio = current / historical_avg
    if ratio <= 1.2:
        return 0.0
    elif ratio <= 2.0:
        return (ratio - 1.2) / 0.8 * 50  # 0–50
    elif ratio <= 4.0:
        return 50 + (ratio - 2.0) / 2.0 * 50  # 50–100
    else:
        return 100.0


def _score_error_rate(error_rate: float) -> float:
    """Scores error rate (0–100). 0% → 0, 50%+ → 100."""
    return min(100.0, error_rate * 200)


def _score_error_rate_trend(current: float, historical_avg: float) -> float:
    """Scores error rate trend. Increasing error rate → higher score."""
    if historical_avg <= 0.001:
        # No historical errors — any current errors are concerning
        return min(100.0, current * 500)
    ratio = current / historical_avg
    if ratio <= 1.5:
        return 0.0
    elif ratio <= 3.0:
        return (ratio - 1.5) / 1.5 * 50
    else:
        return min(100.0, 50 + (ratio - 3.0) / 3.0 * 50)


def _score_availability(availability: float) -> float:
    """Scores availability. 100% → 0, 0% → 100."""
    return max(0.0, (1.0 - availability) * 100)


def _score_timeout(timeout_count: int, total_checks: int) -> float:
    """Scores timeout frequency."""
    if total_checks <= 0:
        return 0.0
    ratio = timeout_count / total_checks
    return min(100.0, ratio * 200)


def _score_anomaly_count(count: int) -> float:
    """Scores recent anomaly count. More anomalies → higher risk."""
    if count <= 0:
        return 0.0
    elif count <= 2:
        return 30.0
    elif count <= 5:
        return 60.0
    else:
        return 100.0


def calculate_risk(
    current_metrics: dict,
    historical_metrics: Optional[dict] = None,
    service_config: Optional[dict] = None,
) -> dict:
    """
    Calculates a composite risk score for a service.

    Args:
        current_metrics: Latest monitoring record fields.
        historical_metrics: Aggregated historical stats (averages, counts).
        service_config: Service configuration (thresholds).

    Returns:
        Dict with risk_score (0–100), risk_level, and per-factor breakdown.
    """
    if historical_metrics is None:
        historical_metrics = {}
    if service_config is None:
        service_config = {}

    # Extract current values
    response_time = float(current_metrics.get("response_time", 0))
    error_rate = float(current_metrics.get("error_rate", 0))
    availability = float(current_metrics.get("availability", 1.0))

    # Extract historical/config values
    rt_threshold = float(service_config.get("response_time_threshold", 5000))
    hist_avg_rt = float(historical_metrics.get("avg_response_time", response_time))
    hist_avg_error = float(historical_metrics.get("avg_error_rate", 0))
    timeout_count = int(historical_metrics.get("timeout_count", 0))
    total_checks = int(historical_metrics.get("total_checks", 1))
    anomaly_count = int(historical_metrics.get("recent_anomaly_count", 0))

    # Compute individual factor scores
    factors = {
        "response_time": _score_response_time(response_time, rt_threshold),
        "response_time_trend": _score_response_time_trend(response_time, hist_avg_rt),
        "error_rate": _score_error_rate(error_rate),
        "error_rate_trend": _score_error_rate_trend(error_rate, hist_avg_error),
        "availability": _score_availability(availability),
        "timeout": _score_timeout(timeout_count, total_checks),
        "anomaly_count": _score_anomaly_count(anomaly_count),
    }

    # Weighted sum
    risk_score = sum(factors[k] * WEIGHTS[k] for k in WEIGHTS)
    risk_score = round(min(100.0, max(0.0, risk_score)), 1)

    # Determine level
    risk_level = "LOW"
    for threshold, level in RISK_LEVELS:
        if risk_score <= threshold:
            risk_level = level
            break

    result = {
        "risk_score": risk_score,
        "risk_level": risk_level,
        "factors": {k: round(v, 1) for k, v in factors.items()},
        "weights": WEIGHTS,
    }

    logger.info(
        f"Risk analysis: score={risk_score}, level={risk_level}",
        extra={"action": "calculate_risk"},
    )

    return result


def compute_historical_metrics(records: list[dict]) -> dict:
    """
    Computes aggregated historical metrics from a list of monitoring records.
    Used as input to calculate_risk().
    """
    if not records:
        return {
            "avg_response_time": 0,
            "avg_error_rate": 0,
            "timeout_count": 0,
            "total_checks": 0,
            "recent_anomaly_count": 0,
        }

    response_times = [float(r.get("response_time", 0)) for r in records]
    error_rates = [float(r.get("error_rate", 0)) for r in records]
    timeouts = sum(1 for r in records if int(r.get("timeout", 0)) == 1)

    return {
        "avg_response_time": sum(response_times) / len(response_times),
        "avg_error_rate": sum(error_rates) / len(error_rates),
        "timeout_count": timeouts,
        "total_checks": len(records),
        "recent_anomaly_count": 0,  # Updated by anomaly detection pipeline
    }
