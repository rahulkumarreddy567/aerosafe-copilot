from aerosafe.audit.chain import AuditLog
from concurrent.futures import ThreadPoolExecutor


def test_chain_is_intact_then_detects_tampering(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    log.append("user", "submitted", {"text": "defect"})
    log.append("verifier", "removed_claim", {"n": 1})
    log.append("reviewer", "approved", {})
    assert log.verify() == (True, None)

    lines = (tmp_path / "audit.jsonl").read_text().splitlines()
    lines[1] = lines[1].replace('"n": 1', '"n": 2')
    (tmp_path / "audit.jsonl").write_text("\n".join(lines) + "\n")
    ok, bad = log.verify()
    assert not ok and bad == 2


def test_malformed_log_is_reported_as_corrupt_instead_of_raising(tmp_path):
    path = tmp_path / "audit.jsonl"
    log = AuditLog(str(path))
    log.append("system", "ok", {})
    with path.open("a", encoding="utf-8") as f:
        f.write("not-json\n")
    assert AuditLog(str(path)).verify() == (False, 2)


def test_concurrent_appends_preserve_a_valid_chain(tmp_path):
    log = AuditLog(str(tmp_path / "audit.jsonl"))
    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(lambda n: log.append("worker", "event", {"n": n}), range(40)))
    assert log.verify() == (True, None)
    assert len(log._records()) == 40
