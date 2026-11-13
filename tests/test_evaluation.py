import pytest

from aerosafe.evaluation import score_predictions


def test_macro_f1_includes_missed_and_out_of_set_predictions():
    result = score_predictions(
        ["29", "29", "32", "32"],
        ["29", "32", "71", "__no_match__"],
    )

    assert result["accuracy"] == 0.25
    assert result["macro_f1"] == 0.167
    classes = {row["ata"]: row for row in result["per_class"]}
    assert classes["29"]["support"] == 2
    assert classes["29"]["recall"] == 0.5
    assert classes["32"]["support"] == 2
    assert classes["32"]["recall"] == 0
    assert classes["71"]["support"] == 0
    assert classes["__no_match__"]["support"] == 0


def test_empty_scores_and_length_validation():
    assert score_predictions([], []) == {
        "sample_count": 0,
        "accuracy": None,
        "macro_f1": None,
        "per_class": [],
    }
    with pytest.raises(ValueError, match="equal lengths"):
        score_predictions(["29"], [])
