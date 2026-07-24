from __future__ import annotations

import json

from keel.doctor import diagnose


def test_doctor_no_data_is_not_ready(tmp_path):
    r = diagnose(tmp_path)
    assert r["data_symbols"] == 0
    assert "NOT READY" in r["verdict"]


def test_doctor_reports_honest_no_edge(tmp_path):
    (tmp_path / "AAPL.csv").write_text("date,open,high,low,close,volume\n2024-01-02,1,1,1,1,1\n")
    (tmp_path / "edge_ledger.jsonl").write_text(
        json.dumps({"beats_luck": False, "pvalue": 1.0, "oos_sharpe": 0.0, "n_folds": 3}) + "\n"
    )
    r = diagnose(tmp_path)
    assert r["data_symbols"] == 1
    assert r["edge"]["has_proven_edge"] is False
    assert "no proven edge" in r["verdict"].lower()


def test_doctor_reports_edge_when_present(tmp_path):
    (tmp_path / "AAPL.csv").write_text("date,open,high,low,close,volume\n2024-01-02,1,1,1,1,1\n")
    (tmp_path / "edge_ledger.jsonl").write_text(
        json.dumps({"beats_luck": True, "pvalue": 0.01, "oos_sharpe": 1.2, "n_folds": 12}) + "\n"
    )
    r = diagnose(tmp_path)
    assert r["edge"]["has_proven_edge"] is True
    assert "EDGE PRESENT" in r["verdict"]


def test_doctor_reads_roster_champion(tmp_path):
    (tmp_path / "AAPL.csv").write_text("date,open,high,low,close,volume\n2024-01-02,1,1,1,1,1\n")
    (tmp_path / "roster.json").write_text(
        json.dumps(
            {
                "champion": {"strategy": "rsi2", "params": {"entry_level": 10}},
                "variants": [{"survived": True}, {"survived": False}],
            }
        )
    )
    r = diagnose(tmp_path)
    assert r["roster"]["champion"]["strategy"] == "rsi2"
    assert r["roster"]["validated_survivors"] == 1
