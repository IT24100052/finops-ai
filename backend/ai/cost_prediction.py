"""
Cost Prediction Engine.

Approach: fit a linear trend (numpy polyfit, degree 1) to daily total
spend over the available history, then project it forward. We compute
a confidence band from the residual standard deviation of the fit,
which is a reasonably honest way to say "here's our uncertainty"
without pretending a 5-line model is a forecasting oracle.

This is intentionally simple and explainable -- a recruiter or
professor can follow exactly what it's doing. Swapping in an LSTM
later (see README) is a natural "v2" if you have time.
"""
import numpy as np
import pandas as pd


def predict_next_period_cost(daily_costs: pd.Series, horizon_days: int = 30) -> dict:
    """
    daily_costs: pandas Series indexed by date, values = total cost that day.
    Returns a dict matching schemas.CostPrediction.
    """
    daily_costs = daily_costs.sort_index()
    n = len(daily_costs)

    if n < 2:
        avg = float(daily_costs.mean()) if n else 0.0
        flat_total = avg * horizon_days
        return {
            "next_period_days": horizon_days,
            "predicted_cost": round(flat_total, 2),
            "lower_bound": round(flat_total * 0.85, 2),
            "upper_bound": round(flat_total * 1.15, 2),
            "trend": "flat",
            "daily_avg_recent": round(avg, 2),
        }

    x = np.arange(n)
    y = daily_costs.values.astype(float)

    # Fit linear trend: cost(day) = slope * day + intercept
    slope, intercept = np.polyfit(x, y, 1)
    fitted = slope * x + intercept
    residuals = y - fitted
    residual_std = float(np.std(residuals)) if n > 2 else float(np.std(y)) * 0.5

    # Project forward
    future_x = np.arange(n, n + horizon_days)
    future_y = slope * future_x + intercept
    future_y = np.clip(future_y, a_min=0, a_max=None)  # cost can't go negative

    predicted_total = float(np.sum(future_y))
    # Uncertainty grows mildly with horizon (sqrt of time, a standard random-walk assumption)
    band = residual_std * np.sqrt(horizon_days) * 1.0

    recent_window = min(7, n)
    daily_avg_recent = float(daily_costs.values[-recent_window:].mean())

    if slope > 0.5:
        trend = "rising"
    elif slope < -0.5:
        trend = "falling"
    else:
        trend = "flat"

    return {
        "next_period_days": horizon_days,
        "predicted_cost": round(predicted_total, 2),
        "lower_bound": round(max(predicted_total - band, 0), 2),
        "upper_bound": round(predicted_total + band, 2),
        "trend": trend,
        "daily_avg_recent": round(daily_avg_recent, 2),
    }
