"""Baseline NLP for triage: language guess, ATA chapter ranking, entity tags.

This is a keyword BASELINE so the pipeline runs end to end. Replace it with
your fine-tuned CamemBERT / ModernBERT classifier and an NER model, and keep
this version as the baseline row in your evaluation table.
"""
import re
from dataclasses import dataclass, field

ATA_KEYWORDS = {
    "32": ["landing gear", "nose gear", "main gear", "retraction", "train d'atterrissage", "rentree du train", "gear door", "strut"],
    "29": ["hydraulic", "hydraulique", "pressure", "pression", "reservoir", "hydraulic pump", "hydraulic fluid"],
    "27": ["flap", "slat", "aileron", "spoiler", "flight control", "commandes de vol", "actuator", "control surface"],
    "28": ["fuel", "carburant", "fuel pump", "fuel leak", "fuel flow", "fuel pressure", "fuel quantity"],
    "31": ["display", "avionics", "avionique", "instrument", "efis", "eicas", "ecam", "warning light", "caution"],
    "71": ["engine", "moteur", "nacelle", "turbine", "thrust", "n1", "n2", "egt", "oil pressure", "compressor"],
    "55": ["stabilizer", "empennage", "horizontal stabilizer", "vertical stabilizer", "trim", "rudder", "elevator"],
    "34": ["navigation", "gps", "ils", "vor", "adiru", "irs", "inertial", "radio altimeter", "transponder", "tcas"],
}
ATA_NAMES = {
    "32": "Landing gear", "29": "Hydraulic power", "27": "Flight controls",
    "28": "Fuel", "31": "Instruments", "71": "Power plant", "55": "Stabilizers",
    "34": "Navigation",
}
SYMPTOMS = [
    "pressure drop", "perte de pression", "leak", "fuite", "vibration", "overheat", "noise",
    "intermittent", "failure", "fault", "warning", "caution", "abnormal", "erratic", "fluctuation",
]
COMPONENTS = [
    "landing gear", "actuator", "verin", "fitting", "pump", "valve", "engine",
    "sensor", "display", "hydraulic pump", "fuel pump", "transponder", "adiru",
]
PHASES = [
    "retraction", "extension", "takeoff", "landing", "taxi", "climb", "approach",
    "cruise", "descent", "rotation", "flare",
]
FRENCH_HINTS = re.compile(r"[éèêàùç]|\b(le|la|les|du|des|perte|sur|vols)\b", re.IGNORECASE)


@dataclass
class TriageResult:
    language: str
    ata: list[tuple[str, str, float]] = field(default_factory=list)  # (code, name, score)
    entities: list[tuple[str, str]] = field(default_factory=list)    # (label, text)
    signals: list[dict] = field(default_factory=list)


def detect_language(text: str) -> str:
    return "fr" if FRENCH_HINTS.search(text) else "en"


def analyze(text: str) -> TriageResult:
    low = text.lower()
    counts = {code: {term: low.count(term) for term in terms if low.count(term)}
              for code, terms in ATA_KEYWORDS.items()}
    raw = {code: sum(found.values()) for code, found in counts.items()}
    total = sum(raw.values()) or 1
    ranked = sorted(raw.items(), key=lambda kv: kv[1], reverse=True)[:3]
    ata = [(c, ATA_NAMES[c], round(v / total, 2)) for c, v in ranked if v > 0]
    signals = [
        {
            "ata": code,
            "name": ATA_NAMES[code],
            "rank": index,
            "relative_match_share": round(raw[code] / total, 2),
            "matched_terms": [{"term": term, "count": count} for term, count in counts[code].items()],
        }
        for index, (code, _) in enumerate(ranked, start=1) if raw[code] > 0
    ]
    ents = [("SYMPTOM", s) for s in SYMPTOMS if s in low]
    ents += [("COMPONENT", c) for c in COMPONENTS if c in low]
    ents += [("PHASE", p) for p in PHASES if p in low]
    return TriageResult(language=detect_language(text), ata=ata, entities=ents, signals=signals)
