from __future__ import annotations

import json

from keel.journal import Journal, verify_journal


def test_records_carry_chain_fields(tmp_path):
    j = Journal(tmp_path / "j.jsonl", process_instance_id="p1", deployment_id="dep")
    rec = j.write("entry", symbol="AAPL")
    assert rec["seq"] == 0
    assert rec["prev_hash"] == "genesis"
    assert "hash" in rec
    assert rec["process_instance_id"] == "p1"
    assert rec["deployment_id"] == "dep"


def test_chain_verifies_intact(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    j.write("entry", symbol="AAPL")
    j.write("exit", symbol="AAPL", reason="stop")
    ok, detail = j.verify()
    assert ok is True
    assert "2 records" in detail


def test_tamper_is_detected(tmp_path):
    path = tmp_path / "j.jsonl"
    j = Journal(path)
    j.write("entry", symbol="AAPL")
    j.write("exit", symbol="AAPL")
    lines = path.read_text().splitlines()
    rec = json.loads(lines[0])
    rec["symbol"] = "TSLA"  # tamper with a past record
    lines[0] = json.dumps(rec)
    path.write_text("\n".join(lines) + "\n")
    ok, detail = verify_journal(path)
    assert ok is False
    assert "mismatch" in detail


def test_backward_compatible_readers(tmp_path):
    j = Journal(tmp_path / "j.jsonl")
    j.write("entry", symbol="AAPL", via="rsi2")
    j.write("exit", symbol="AAPL", reason="stop")
    today = j.today()
    assert len(today) == 2
    assert today[-1]["kind"] == "exit"
    assert today[-1]["reason"] == "stop"  # fields still top-level


def test_legacy_records_without_hash_are_tolerated(tmp_path):
    path = tmp_path / "j.jsonl"
    # a pre-upgrade line with no hash chain
    path.write_text(json.dumps({"ts": "2024-01-02T10:00:00+00:00", "kind": "entry"}) + "\n")
    j = Journal(path)  # continues the chain
    j.write("exit", symbol="AAPL")
    ok, _ = j.verify()
    assert ok is True


def test_new_instance_continues_sequence(tmp_path):
    path = tmp_path / "j.jsonl"
    Journal(path).write("a")
    j2 = Journal(path)  # fresh instance, same file
    rec = j2.write("b")
    assert rec["seq"] == 1  # sequence continued
    assert j2.verify()[0] is True
