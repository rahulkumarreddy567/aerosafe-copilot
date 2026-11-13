import pytest

from aerosafe.rul import SensorCsvError, estimate_rul


def test_estimates_threshold_crossing_from_health_trend():
    result = estimate_rul(b"cycle,health_index\n0,1.0\n10,0.8\n20,0.6\n", threshold=0.2)
    assert result["estimate_cycles"] == 20
    assert result["slope_per_cycle"] == -0.02
    assert result["method"] == "ordinary least-squares linear trend extrapolation"
    assert "not for maintenance decisions" in result["warning"]


@pytest.mark.parametrize("contents", [
    b"",
    b"cycle,temperature\n0,1\n1,0.9\n2,0.8\n",
    b"cycle,health_index\n0,1\n1,0.9\n",
    b"cycle,health_index\n0,1\n0,0.9\n1,0.8\n",
    b"cycle,health_index\n0,0.5\n1,0.6\n2,0.7\n",
    b"cycle,health_index\n0,1.2\n1,0.9\n2,0.8\n",
])
def test_rejects_invalid_sensor_csv(contents):
    with pytest.raises(SensorCsvError):
        estimate_rul(contents)


def test_rejects_invalid_threshold():
    with pytest.raises(SensorCsvError, match="threshold"):
        estimate_rul(b"cycle,health_index\n0,0.9\n1,0.8\n2,0.7\n", threshold=1)
