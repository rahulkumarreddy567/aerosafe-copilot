"""Evaluate the keyword ATA baseline on a small, explicitly synthetic smoke set."""
import csv
from pathlib import Path

from aerosafe.nlp.triage import analyze

EVAL_CSV = Path(__file__).resolve().parents[2] / "eval" / "ata_smoke.csv"
if not EVAL_CSV.is_file():
    EVAL_CSV = Path.cwd() / "eval" / "ata_smoke.csv"


def score_predictions(expected: list[str], predicted: list[str]) -> dict:
    """Compute accuracy and macro-F1 over the union of true and predicted labels."""
    if len(expected) != len(predicted):
        raise ValueError("expected and predicted must have equal lengths")
    if not expected:
        return {"sample_count": 0, "accuracy": None, "macro_f1": None, "per_class": []}

    labels = sorted(set(expected) | set(predicted))
    true_counts = {label: expected.count(label) for label in labels}
    predicted_counts = {label: predicted.count(label) for label in labels}
    true_positives = {
        label: sum(actual == label and guess == label for actual, guess in zip(expected, predicted))
        for label in labels
    }

    per_class = []
    raw_f1 = []
    for label in labels:
        tp = true_positives[label]
        precision = tp / predicted_counts[label] if predicted_counts[label] else 0.0
        recall = tp / true_counts[label] if true_counts[label] else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        raw_f1.append(f1)
        per_class.append({
            "ata": label,
            "support": true_counts[label],
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        })

    correct = sum(actual == guess for actual, guess in zip(expected, predicted))
    return {
        "sample_count": len(expected),
        "accuracy": round(correct / len(expected), 3),
        "macro_f1": round(sum(raw_f1) / len(raw_f1), 3),
        "per_class": per_class,
    }


def evaluate_ata_baseline() -> dict:
    with EVAL_CSV.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    expected = [row["expected_ata"] for row in rows]
    predicted = []
    for row in rows:
        ranked = analyze(row["description"]).ata
        predicted.append(ranked[0][0] if ranked else "__no_match__")

    return {
        "dataset": "synthetic_smoke_set",
        **score_predictions(expected, predicted),
        "warning": "Synthetic sanity check only; these examples are not an operational or held-out benchmark.",
    }
