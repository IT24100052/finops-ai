"""
Cost Prediction Engine — Enhanced v2.

Approach: fit a linear trend (numpy polyfit, degree 1) to daily total
spend over the available history, then project it forward. Computes a
confidence band from residual standard deviation.

This is intentionally simple and explainable. Architecture comment:
  - Swap predict_next_period_cost() for a Prophet/XGBoost/LSTM function
    without changing any router code. The contract (daily_costs Series → dict)
    is the public API.
"""
import numpy as np
import pandas as pd


def predict_next_period_cost(daily_costs: pd.Series, horizon_days: int = 30) -> dict:
    """
    daily_costs: pandas Series indexed by date, values = total cost that day.
    Returns a dict matching schemas.CostPrediction.
    """
    daily_costs = daily_costs.sort_index().dropna()
    n = len(daily_costs)
    values = daily_costs.values.astype(float)

    historical_avg = float(values.mean()) if n > 0 else 0.0

    if n < 2:
        flat_total = historical_avg * horizon_days
        return {
            "next_period_days":          horizon_days,
            "predicted_cost":            round(flat_total, 2),
            "lower_bound":               round(flat_total * 0.85, 2),
            "upper_bound":               round(flat_total * 1.15, 2),
            "trend":                     "flat",
            "daily_avg_recent":          round(historical_avg, 2),
            "historical_average":        round(historical_avg, 2),
            "forecast_change_percentage": 0.0,
            "confidence":                "low",
            "explanation":               (
                "Insufficient historical data for trend analysis. "
                "Forecast is based on your current daily average spend."
            ),
        }

    x = np.arange(n)

    # Fit linear trend: cost(day) = slope * day + intercept
    slope, intercept = np.polyfit(x, values, 1)
    fitted = slope * x + intercept
    residuals = values - fitted
    residual_std = float(np.std(residuals)) if n > 2 else float(np.std(values)) * 0.5

    # Project forward
    future_x = np.arange(n, n + horizon_days)
    future_y = slope * future_x + intercept
    future_y = np.clip(future_y, a_min=0, a_max=None)

    predicted_total = float(np.sum(future_y))
    predicted_daily_avg = predicted_total / max(horizon_days, 1)

    # Confidence band (uncertainty grows with horizon — sqrt of time)
    band = residual_std * np.sqrt(horizon_days)

    recent_window = min(7, n)
    daily_avg_recent = float(values[-recent_window:].mean())

    # Trend classification
    if slope > 0.5:
        trend = "rising"
    elif slope < -0.5:
        trend = "falling"
    else:
        trend = "flat"

    # Historical vs forecast change
    historical_period_total = historical_avg * horizon_days
    forecast_change_pct = (
        ((predicted_total - historical_period_total) / historical_period_total * 100)
        if historical_period_total > 0 else 0.0
    )

    # Confidence based on data quantity and residual noise
    cv = residual_std / historical_avg if historical_avg > 0 else 1.0
    if n >= 30 and cv < 0.2:
        confidence = "high"
    elif n >= 14 and cv < 0.4:
        confidence = "medium"
    else:
        confidence = "low"

    # Plain-English explanation
    change_dir = "increasing" if forecast_change_pct > 3 else "decreasing" if forecast_change_pct < -3 else "stable"
    explanation = (
        f"Based on {n} days of historical data, spending is {change_dir}. "
        f"Expected {horizon_days}-day total: ${predicted_total:,.2f} "
        f"(daily average ${predicted_daily_avg:.2f})."
    )
    if abs(forecast_change_pct) > 3:
        explanation += (
            f" This is approximately {abs(forecast_change_pct):.1f}% "
            f"{'higher' if forecast_change_pct > 0 else 'lower'} than your historical average."
        )

    return {
        "next_period_days":           horizon_days,
        "predicted_cost":             round(predicted_total, 2),
        "lower_bound":                round(max(predicted_total - band, 0), 2),
        "upper_bound":                round(predicted_total + band, 2),
        "trend":                      trend,
        "daily_avg_recent":           round(daily_avg_recent, 2),
        "historical_average":         round(historical_avg, 2),
        "forecast_change_percentage": round(forecast_change_pct, 1),
        "confidence":                 confidence,
        "explanation":                explanation,
    }
