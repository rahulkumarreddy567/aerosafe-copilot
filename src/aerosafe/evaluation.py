"""Evaluate the keyword ATA baseline on a small, explicitly synthetic smoke set."""
import csv
from pathlib import Path

from aerosafe.nlp.triage import analyze

EVAL_CSV = Path(__file__).resolve().parents[2] / "eval" / "ata_smoke.csv"
if not EVAL_CSV.is_file():
    EVAL_CSV = Path.cwd() / "eval" / "ata_smoke.csv"


def evaluate_ata_baseline() -> dict:
    with EVAL_CSV.open(encoding="utf-8", newline="") as stream:
        rows = list(csv.DictReader(stream))
    labels = sorted({row["expected_ata"] for row in rows})
    if not rows or not labels:
        return {"sample_count": 0, "accuracy": None, "macro_f1": None, "per_class": []}

    confusion = {label: {pred: 0 for pred in labels} for label in labels}
    predicted_totals = {label: 0 for label in labels}
    correct = 0
    for row in rows:
        expected = row["expected_ata"]
        ranked = analyze(row["description"]).ata
        predicted = ranked[0][0] if ranked else "__no_match__"
        if predicted == expected:
            correct += 1
        if predicted in labels:
            confusion[expected][predicted] += 1
            predicted_totals[predicted] += 1

    per_class = []
    for label in labels:
        tp = confusion[label][label]
        support = sum(confusion[label].values())
        predicted_count = predicted_totals[label]
        precision = tp / predicted_count if predicted_count else 0.0
        recall = tp / support if support else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_class.append({
            "ata": label,
            "support": support,
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
        })

    return {
        "dataset": "synthetic_smoke_set",
        "sample_count": len(rows),
        "accuracy": round(correct / len(rows), 3),
        "macro_f1": round(sum(item["f1"] for item in per_class) / len(per_class), 3),
        "per_class": per_class,
        "warning": "Synthetic sanity check only; these examples are not an operational or held-out benchmark.",
    }
