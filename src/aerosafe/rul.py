"""Small, transparent health-index trend estimate for prototype sensor CSVs."""
import csv
import io
import math


MAX_SENSOR_CSV_BYTES = 1_000_000


class SensorCsvError(ValueError):
    """The uploaded file does not meet the documented sensor CSV format."""


def estimate_rul(contents: bytes, threshold: float = 0.2) -> dict:
    if not contents:
        raise SensorCsvError("The CSV file is empty.")
    if len(contents) > MAX_SENSOR_CSV_BYTES:
        raise SensorCsvError("The CSV file exceeds the 1 MB limit.")
    if not math.isfinite(threshold) or not 0 <= threshold < 1:
        raise SensorCsvError("Failure threshold must be at least 0 and less than 1.")

    try:
        text = contents.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(text))
        if not {"cycle", "health_index"}.issubset(reader.fieldnames or []):
            raise SensorCsvError("CSV must include cycle and health_index columns.")
        points = []
        for row_number, row in enumerate(reader, start=2):
            cycle = float(row["cycle"])
            health = float(row["health_index"])
            if not math.isfinite(cycle) or not math.isfinite(health):
                raise SensorCsvError(f"Row {row_number} must contain finite numbers.")
            if not 0 <= health <= 1:
                raise SensorCsvError(f"Row {row_number} health_index must be between 0 and 1.")
            points.append({"cycle": cycle, "health_index": health})
    except (UnicodeDecodeError, csv.Error, TypeError, ValueError) as exc:
        if isinstance(exc, SensorCsvError):
            raise
        raise SensorCsvError("CSV rows must contain numeric cycle and health_index values.") from exc

    if len(points) < 3:
        raise SensorCsvError("At least 3 sensor rows are required.")
    if any(b["cycle"] <= a["cycle"] for a, b in zip(points, points[1:])):
        raise SensorCsvError("Cycle values must be strictly increasing.")

    x_mean = sum(point["cycle"] for point in points) / len(points)
    y_mean = sum(point["health_index"] for point in points) / len(points)
    denominator = sum((point["cycle"] - x_mean) ** 2 for point in points)
    slope = sum(
        (point["cycle"] - x_mean) * (point["health_index"] - y_mean)
        for point in points
    ) / denominator
    if slope >= 0:
        raise SensorCsvError("The health trend is not declining, so this demo cannot estimate remaining cycles.")

    last = points[-1]
    remaining = max(0, math.ceil((last["health_index"] - threshold) / -slope))
    return {
        "estimate_cycles": remaining,
        "threshold": threshold,
        "slope_per_cycle": round(slope, 6),
        "last_cycle": last["cycle"],
        "last_health_index": last["health_index"],
        "series": points,
        "method": "ordinary least-squares linear trend extrapolation",
        "warning": "Illustrative estimate from the supplied health index only. Not a trained RUL model and not for maintenance decisions.",
    }
