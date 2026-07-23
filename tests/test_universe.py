from __future__ import annotations

from datetime import date

from keel.universe import Membership, Universe


def test_membership_is_point_in_time():
    u = Universe(
        (
            Membership("AAA", date(2015, 1, 1)),
            Membership("DEAD", date(2015, 1, 1), date(2020, 6, 30)),
            Membership("NEW", date(2022, 3, 1)),
        )
    )
    assert u.as_of(date(2016, 1, 1)) == {"AAA", "DEAD"}
    assert u.as_of(date(2021, 1, 1)) == {"AAA"}
    assert u.as_of(date(2023, 1, 1)) == {"AAA", "NEW"}
    # before anything listed: honestly empty, not backfilled from today
    assert u.as_of(date(2014, 1, 1)) == frozenset()


def test_universe_from_csv(tmp_path):
    p = tmp_path / "u.csv"
    p.write_text("symbol,start,end\nAAA,2015-01-01,\nDEAD,2015-01-01,2020-06-30\n")
    u = Universe.from_csv(p)
    assert u.as_of(date(2021, 1, 1)) == {"AAA"}
