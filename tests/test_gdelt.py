"""GDELT adapter tests: the pure annual-aggregation transform.

Network fetch (`fetch_timeline`) is not unit-tested here; these cover the
deterministic transform that turns dated volume points into annual facts.
"""

from datetime import date

from hazium.sources.gdelt import media_volume_records


class TestMediaVolumeRecords:
    def test_annual_mean_and_known_at(self) -> None:
        points = [
            ("20180101T000000Z", 0.2),
            ("20180701T000000Z", 0.4),
            ("20190101T000000Z", 1.0),
        ]
        recs = {r.year: r for r in media_volume_records("substance:cas:1", points)}
        assert recs[2018].volume == 0.30000000000000004 or abs(recs[2018].volume - 0.3) < 1e-9
        assert recs[2019].volume == 1.0
        # known_at is Jan 1 of year+1 (a year's coverage is complete once it ends)
        assert recs[2018].known_at == date(2019, 1, 1)
        assert recs[2018].source == "gdelt:doc"

    def test_pre_2017_points_dropped(self) -> None:
        points = [("20150101T000000Z", 0.9), ("20170101T000000Z", 0.1)]
        years = {r.year for r in media_volume_records("substance:cas:1", points)}
        assert years == {2017}

    def test_no_points_no_records(self) -> None:
        assert media_volume_records("substance:cas:1", []) == []

    def test_custom_min_year(self) -> None:
        points = [("20180101T000000Z", 0.5), ("20200101T000000Z", 0.5)]
        years = {r.year for r in media_volume_records("substance:cas:1", points, min_year=2019)}
        assert years == {2020}
