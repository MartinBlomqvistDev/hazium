"""ECHA CLH-intention adapter and feature tests: pure transforms and the
pre-cutoff feature, no network (the snapshot is committed, browser-acquired).
"""

from datetime import date

from hazium.ml.features import clh_intention_features
from hazium.sources.echa_clh import clh_intention_records, earliest_intention_year


class TestEarliestIntentionYear:
    def test_min_year_per_cas(self, tmp_path) -> None:
        p = tmp_path / "clh.jsonl"
        p.write_text(
            '{"receipt_year": 2013, "cas": ["111988-49-9", "60-51-5"]}\n'
            '{"receipt_year": 2010, "cas": ["111988-49-9"]}\n',
            encoding="utf-8",
        )
        got = earliest_intention_year(p)
        assert got["111988-49-9"] == 2010  # earliest of 2013/2010
        assert got["60-51-5"] == 2013

    def test_blank_lines_ignored(self, tmp_path) -> None:
        p = tmp_path / "clh.jsonl"
        p.write_text('\n{"receipt_year": 2015, "cas": ["8018-01-7"]}\n\n', encoding="utf-8")
        assert earliest_intention_year(p) == {"8018-01-7": 2015}


class TestClhIntentionRecords:
    def test_ids_and_known_at(self) -> None:
        recs = {r.substance_id: r for r in clh_intention_records({"8018-01-7": 2017})}
        r = recs["substance:cas:8018-01-7"]
        assert r.intention_year == 2017
        # year-only granularity -> conservatively known at year end (Jan 1 of year+1)
        assert r.known_at == date(2018, 1, 1)
        assert r.source == "echa:clh_intentions"


class TestClhIntentionFeatures:
    def _records(self):
        return clh_intention_records({"8018-01-7": 2017})

    def test_absent_before_known_at(self) -> None:
        # 2017 intention is known_at 2018-01-01, so invisible at a 2017 cutoff
        f = clh_intention_features("substance:cas:8018-01-7", self._records(), date(2017, 1, 1))
        assert f == {"clh_has_intention": 0.0, "clh_years_since_intention": 0.0}

    def test_present_after_known_at(self) -> None:
        f = clh_intention_features("substance:cas:8018-01-7", self._records(), date(2020, 1, 1))
        assert f["clh_has_intention"] == 1.0
        assert f["clh_years_since_intention"] == 3.0  # 2020 - 2017

    def test_other_substance_gets_nothing(self) -> None:
        f = clh_intention_features("substance:cas:2921-88-2", self._records(), date(2020, 1, 1))
        assert f == {"clh_has_intention": 0.0, "clh_years_since_intention": 0.0}
