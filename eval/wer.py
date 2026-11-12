"""Word error rate for the Whisper evaluation (no extra dependencies).

Usage:  python eval/wer.py eval/aviation_phrases.csv
CSV columns: audio_path,reference   (record the audio yourself; keep clips short)
"""
import csv
import re
import argparse
from pathlib import Path


def norm(s: str) -> list[str]:
    return re.sub(r"[^\w\s']", " ", s.lower()).split()


def wer(ref: str, hyp: str) -> float:
    r, h = norm(ref), norm(hyp)
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return d[len(h)] / max(len(r), 1)


def resolve_audio_path(value: str, csv_path: Path) -> Path:
    path = Path(value).expanduser()
    if path.is_absolute():
        return path
    if path.exists():
        return path.resolve()
    return (csv_path.parent / path).resolve()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Measure Whisper word error rate on audio clips.")
    parser.add_argument("csv_path", type=Path, help="CSV with audio_path and reference columns")
    args = parser.parse_args(argv)
    csv_path = args.csv_path.expanduser().resolve()
    if not csv_path.is_file():
        parser.error(f"CSV file not found: {csv_path}")

    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        required = {"audio_path", "reference"}
        if not required.issubset(reader.fieldnames or []):
            parser.error("CSV must include audio_path and reference columns")
        rows = list(reader)
    if not rows:
        parser.error("CSV contains no evaluation rows")

    audio_paths = [(row, resolve_audio_path(row["audio_path"], csv_path)) for row in rows]
    missing = [str(path) for _, path in audio_paths if not path.is_file()]
    if missing:
        parser.error("audio file(s) not found: " + ", ".join(missing))

    from aerosafe.speech.whisper_service import transcribe  # needs the speech extra

    scores = []
    for row, audio_path in audio_paths:
        hyp = transcribe(str(audio_path)).text
        scores.append(wer(row["reference"], hyp))
        print(f"{scores[-1]:.2f}  {audio_path}")
    print(f"mean WER over {len(scores)} clips: {sum(scores) / len(scores):.3f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
