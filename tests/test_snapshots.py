"""Tests for dated snapshot capture.

No network: every test injects a fake fetcher. What is verified is the
behaviour that has to hold for an unattended collector to stay trustworthy over
years, namely content-addressed dedup, an append-only manifest that records
failures as well as successes, failure isolation across sources, and alerting
that fires on persistent breakage rather than on a single blip.
"""

from __future__ import annotations

import json
from datetime import UTC, date, datetime

import pytest

from hazium.snapshots.collectors import (
    collect_file,
    collect_ogc_features_window,
    collect_ppdb_details,
)
from hazium.snapshots.fetch import FetchError
from hazium.snapshots.models import Cadence, CollectorKind, SourceSpec
from hazium.snapshots.registry import REGISTRY, spec_by_name
from hazium.snapshots.runner import broken_sources, exit_code, run_sources, window_start
from hazium.snapshots.store import SnapshotStore, sha256_hex


def _spec(name: str = "demo", kind: CollectorKind = CollectorKind.FILE, **params) -> SourceSpec:
    return SourceSpec(
        name=name,
        description="test source",
        future_use="test",
        cadence=Cadence.MONTHLY,
        kind=kind,
        url="https://example.invalid/data",
        params=params,
    )


def _nosleep(_seconds: float) -> None:
    return None


# --------------------------------------------------------------------- store


def test_store_records_success_and_reads_blob_back(tmp_path):
    store = SnapshotStore(tmp_path)
    obs = store.record_success("demo", b"hello")

    assert obs.ok
    assert obs.unchanged is False
    assert obs.n_bytes == 5
    assert obs.digest == sha256_hex(b"hello")
    assert store.read_blob(obs.digest) == b"hello"


def test_identical_payload_is_flagged_unchanged_and_writes_no_new_blob(tmp_path):
    store = SnapshotStore(tmp_path)
    first = store.record_success("demo", b"same")
    blobs_after_first = list(store.blob_root.rglob("*.gz"))

    second = store.record_success("demo", b"same")
    blobs_after_second = list(store.blob_root.rglob("*.gz"))

    assert first.unchanged is False
    assert second.unchanged is True
    assert second.digest == first.digest
    assert blobs_after_second == blobs_after_first
    # Both observations are still recorded: "checked, nothing changed" is dated
    # information in its own right.
    assert len(store.observations("demo")) == 2


def test_changed_payload_writes_a_second_blob(tmp_path):
    store = SnapshotStore(tmp_path)
    store.record_success("demo", b"v1")
    store.record_success("demo", b"v2")

    assert len({p.name for p in store.blob_root.rglob("*.gz")}) == 2
    assert store.latest_digest("demo") == sha256_hex(b"v2")


def test_manifest_is_append_only_across_store_instances(tmp_path):
    SnapshotStore(tmp_path).record_success("demo", b"a")
    SnapshotStore(tmp_path).record_failure("demo", "boom")

    observations = SnapshotStore(tmp_path).observations("demo")
    assert [o.ok for o in observations] == [True, False]


def test_observations_filter_by_source(tmp_path):
    store = SnapshotStore(tmp_path)
    store.record_success("a", b"x")
    store.record_success("b", b"y")

    assert [o.source for o in store.observations("a")] == ["a"]
    assert len(store.observations()) == 2


def test_corrupt_manifest_line_is_skipped_not_fatal(tmp_path):
    store = SnapshotStore(tmp_path)
    store.record_success("demo", b"a")
    with store.manifest_path.open("a", encoding="utf-8") as fh:
        fh.write("{not json\n")
    store.record_success("demo", b"b")

    assert len(store.observations("demo")) == 2


def test_latest_digest_ignores_failures(tmp_path):
    store = SnapshotStore(tmp_path)
    store.record_success("demo", b"good")
    store.record_failure("demo", "later outage")

    assert store.latest_digest("demo") == sha256_hex(b"good")


def test_consecutive_failures_counts_back_to_last_success(tmp_path):
    store = SnapshotStore(tmp_path)
    store.record_failure("demo", "1")
    store.record_success("demo", b"ok")
    store.record_failure("demo", "2")
    store.record_failure("demo", "3")

    assert store.consecutive_failures("demo") == 2


def test_read_blob_missing_digest_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        SnapshotStore(tmp_path).read_blob("0" * 64)


# ---------------------------------------------------------------- collectors


def test_collect_file_returns_body_verbatim():
    payload, meta = collect_file(_spec(), fetch=lambda url: b"raw-bytes")

    assert payload == b"raw-bytes"
    assert meta["url"] == "https://example.invalid/data"


def test_ogc_window_applies_the_cql_date_filter():
    spec = _spec(kind=CollectorKind.OGC_FEATURES_WINDOW, collection="c", date_field="d")
    seen: list[str] = []

    def fake(url: str) -> bytes:
        seen.append(url)
        return json.dumps({"numberMatched": 1, "features": [{"properties": {"id": 1}}]}).encode()

    _payload, meta = collect_ogc_features_window(
        spec, since=date(2026, 1, 1), fetch=fake, sleep=_nosleep
    )

    assert meta["since"] == "2026-01-01"
    assert "DATE%28%272026-01-01%27%29" in seen[0]
    assert "collections/c/items" in seen[0]


def test_ogc_window_respects_max_pages():
    spec = _spec(
        kind=CollectorKind.OGC_FEATURES_WINDOW, collection="c", date_field="d", page_size=2
    )
    # Endless next links and no numberMatched: only max_pages can stop this.
    full = json.dumps(
        {
            "features": [{"properties": {"id": 1}}, {"properties": {"id": 2}}],
            "links": [{"rel": "next", "href": "https://example.invalid/next"}],
        }
    ).encode()

    _payload, meta = collect_ogc_features_window(
        spec, since=date(2026, 1, 1), fetch=lambda url: full, sleep=_nosleep, max_pages=3
    )

    assert meta["n_features"] == 6


def test_ogc_window_follows_next_links_rather_than_building_offsets():
    # Regression guard. SGU silently ignores `offset` and `startindex`, honouring
    # only `startIndex`, so a hand-built offset returns page one forever and the
    # archive fills with duplicates. Paging must follow the server's next link.
    spec = _spec(
        kind=CollectorKind.OGC_FEATURES_WINDOW, collection="c", date_field="d", page_size=2
    )
    seen: list[str] = []

    def fake(url: str) -> bytes:
        seen.append(url)
        if "PAGE2" not in url:
            return json.dumps(
                {
                    "numberMatched": 3,
                    "features": [{"properties": {"id": 1}}, {"properties": {"id": 2}}],
                    "links": [{"rel": "next", "href": "https://example.invalid/PAGE2"}],
                }
            ).encode()
        return json.dumps({"features": [{"properties": {"id": 3}}], "links": []}).encode()

    payload, meta = collect_ogc_features_window(
        spec, since=date(2026, 1, 1), fetch=fake, sleep=_nosleep
    )

    assert meta["n_features"] == 3
    assert seen[1] == "https://example.invalid/PAGE2"
    ids = [json.loads(line)["id"] for line in payload.decode().splitlines()]
    assert ids == [1, 2, 3]


def test_ogc_window_stops_when_matched_count_is_reached():
    # Second guard against runaway duplication: even if a server keeps handing
    # out next links, collection stops once numberMatched is satisfied.
    spec = _spec(
        kind=CollectorKind.OGC_FEATURES_WINDOW, collection="c", date_field="d", page_size=2
    )

    def fake(url: str) -> bytes:
        return json.dumps(
            {
                "numberMatched": 2,
                "features": [{"properties": {"id": 1}}, {"properties": {"id": 2}}],
                "links": [{"rel": "next", "href": "https://example.invalid/again"}],
            }
        ).encode()

    _payload, meta = collect_ogc_features_window(
        spec, since=date(2026, 1, 1), fetch=fake, sleep=_nosleep, max_pages=50
    )

    assert meta["n_features"] == 2


def test_ogc_window_projects_to_the_declared_fields_and_drops_geometry():
    spec = _spec(
        kind=CollectorKind.OGC_FEATURES_WINDOW,
        collection="c",
        date_field="d",
        fields="cas_kod, matvardetal",
    )
    feature = {
        "geometry": {"type": "Point", "coordinates": [1, 2]},
        "properties": {
            "cas_kod": "56-23-5",
            "matvardetal": 0.0031,
            "utfor_org": "noise",
            "kommentar_prov": "more noise",
        },
    }

    payload, _meta = collect_ogc_features_window(
        spec,
        since=date(2026, 1, 1),
        fetch=lambda url: json.dumps({"features": [feature]}).encode(),
        sleep=_nosleep,
    )

    record = json.loads(payload.decode())
    assert record == {"cas_kod": "56-23-5", "matvardetal": 0.0031}


def test_sgu_projection_keeps_the_join_and_value_fields():
    # The archive is only useful if a measurement can be tied to a substance,
    # placed in time, and read with its detection limits.
    fields = str(spec_by_name("sgu_groundwater").params["fields"])
    for required in ("cas_kod", "provtagningsdatum", "matvardetal", "enhet", "loq", "lod"):
        assert required in fields


def test_ppdb_details_rejects_empty_basicdetails_shells():
    # Regression guard. The endpoint answers 200 with a truthy payload whose
    # basicDetails is [] for ids that do not exist (verified against 5000 and
    # 99999), so a truthiness check accepts everything, archives shells, and
    # reports a perfect hit rate.
    spec = _spec(kind=CollectorKind.PPDB_DETAILS, id_start=1, id_end=3)

    def fake(url: str) -> bytes:
        substance_id = int(url.rsplit("/", 1)[1])
        details = [{"AS_ID": str(substance_id)}] if substance_id == 2 else []
        return json.dumps({"payload": {"basicDetails": details}}).encode()

    payload, meta = collect_ppdb_details(spec, fetch=fake, sleep=_nosleep)

    assert meta["n_substances"] == 1
    assert meta["n_missing"] == 2
    ids = [json.loads(line)["id"] for line in payload.decode().splitlines()]
    assert ids == [2]


def test_ppdb_details_excludes_records_the_register_withholds():
    # Scanning ids reaches records the official search does not return, and 87 of
    # 100 such records carry AS_PUBLIC="0". The archive is meant to be shareable,
    # so records a source flags as not for publication are counted, not kept.
    spec = _spec(kind=CollectorKind.PPDB_DETAILS, id_start=1, id_end=3)

    def fake(url: str) -> bytes:
        substance_id = int(url.rsplit("/", 1)[1])
        public = "0" if substance_id == 2 else "1"
        return json.dumps(
            {"payload": {"basicDetails": [{"AS_ID": str(substance_id), "AS_PUBLIC": public}]}}
        ).encode()

    payload, meta = collect_ppdb_details(spec, fetch=fake, sleep=_nosleep)

    assert meta["n_substances"] == 2
    assert meta["n_non_public"] == 1
    ids = [json.loads(line)["id"] for line in payload.decode().splitlines()]
    assert ids == [1, 3]


def test_ppdb_details_keeps_records_with_no_public_flag():
    # Absent flag defaults to public: withholding is the exception and must be
    # stated by the source, not inferred from a missing field.
    spec = _spec(kind=CollectorKind.PPDB_DETAILS, id_start=1, id_end=1)

    def fake(url: str) -> bytes:
        return json.dumps({"payload": {"basicDetails": [{"AS_ID": "1"}]}}).encode()

    _payload, meta = collect_ppdb_details(spec, fetch=fake, sleep=_nosleep)

    assert meta["n_substances"] == 1
    assert meta["n_non_public"] == 0


def test_ppdb_default_id_range_covers_ids_above_the_observed_maximum():
    # The bulk export's highest id was 1577 with 38 substances above 1500, so
    # the scan must run past the current maximum or it truncates silently.
    assert int(spec_by_name("eu_ppdb_details").params["id_end"]) > 1577


def test_ppdb_details_skips_misses_and_counts_hits():
    spec = _spec(kind=CollectorKind.PPDB_DETAILS, id_start=1, id_end=4)

    def fake(url: str) -> bytes:
        substance_id = int(url.rsplit("/", 1)[1])
        if substance_id == 2:
            raise FetchError("404")
        if substance_id == 3:
            return json.dumps({"payload": None}).encode()
        return json.dumps({"payload": {"basicDetails": {"id": substance_id}}}).encode()

    payload, meta = collect_ppdb_details(spec, fetch=fake, sleep=_nosleep)

    assert meta["n_substances"] == 2
    ids = [json.loads(line)["id"] for line in payload.decode().splitlines()]
    assert ids == [1, 4]


# -------------------------------------------------------------------- runner


def test_run_sources_isolates_a_failing_source(tmp_path):
    store = SnapshotStore(tmp_path)
    bad = _spec("bad")
    # Specs are frozen, so distinguish the two by URL for the fake fetcher.
    good = _spec("good").model_copy(update={"url": "https://example.invalid/good"})

    def fetch(url: str, **_) -> bytes:
        if url.endswith("/good"):
            return b"ok"
        raise FetchError("dead")

    report = run_sources([bad, good], store, fetch=fetch, sleep=_nosleep)

    # The dead source did not abort the run: both were attempted and recorded.
    assert len(report.observations) == 2
    assert {o.source for o in report.succeeded} == {"good"}
    assert {o.source for o in report.failed} == {"bad"}
    assert len(store.observations()) == 2


def test_run_sources_records_failure_without_raising(tmp_path):
    store = SnapshotStore(tmp_path)

    def boom(url: str, **_) -> bytes:
        raise FetchError("dead")

    report = run_sources([_spec("s1")], store, fetch=boom, sleep=_nosleep)

    assert report.failed and not report.succeeded
    assert "dead" in (report.failed[0].error or "")


def test_window_start_is_a_fixed_rolling_window():
    spec = _spec(kind=CollectorKind.OGC_FEATURES_WINDOW, collection="c", date_field="d")

    start = window_start(spec, today=date(2026, 7, 22), window_days=365)

    assert start == date(2025, 7, 22)


def test_window_start_does_not_advance_with_prior_captures(tmp_path):
    # Regression guard for the publication-lag bug: a high-water mark anchored
    # on the previous run silently drops late-registered records, so the window
    # must stay a fixed rolling span regardless of capture history.
    store = SnapshotStore(tmp_path)
    spec = _spec(kind=CollectorKind.OGC_FEATURES_WINDOW, collection="c", date_field="d")
    store.record_success(
        spec.name,
        b"x",
        captured_at=datetime(2026, 6, 1, tzinfo=UTC),
        meta={"since": "2025-06-01"},
    )

    assert window_start(spec, today=date(2026, 7, 22), window_days=730) == date(2024, 7, 22)


def test_window_days_can_be_overridden_per_spec():
    spec = _spec(
        kind=CollectorKind.OGC_FEATURES_WINDOW,
        collection="c",
        date_field="d",
        window_days=30,
    )

    assert window_start(spec, today=date(2026, 7, 22)) == date(2026, 6, 22)


def test_exit_code_zero_when_one_source_fails_transiently(tmp_path):
    store = SnapshotStore(tmp_path)
    specs = [_spec("a"), _spec("b")]
    report = run_sources(
        specs,
        store,
        fetch=lambda url, **_: b"ok",
        sleep=_nosleep,
    )
    store.record_failure("b", "one blip")

    assert exit_code(report, store, specs) == 0


def test_exit_code_one_when_every_source_fails(tmp_path):
    store = SnapshotStore(tmp_path)
    specs = [_spec("a")]

    def boom(url: str, **_) -> bytes:
        raise FetchError("dead")

    report = run_sources(specs, store, fetch=boom, sleep=_nosleep)

    assert exit_code(report, store, specs) == 1


def test_exit_code_one_when_a_source_is_persistently_broken(tmp_path):
    store = SnapshotStore(tmp_path)
    specs = [_spec("a"), _spec("b")]
    report = run_sources(specs, store, fetch=lambda url, **_: b"ok", sleep=_nosleep)
    for _ in range(3):
        store.record_failure("b", "schema changed")

    assert broken_sources(store, specs) == ["b"]
    assert exit_code(report, store, specs) == 1


# ------------------------------------------------------------------ registry


def test_every_registered_source_declares_a_future_use():
    # Policy check, not a formality: an archive with no named consumer is pure
    # maintenance cost, so this is the guard against adding one.
    for spec in REGISTRY:
        assert spec.future_use.strip()
        assert len(spec.future_use) > 40


def test_registry_names_are_unique():
    names = [s.name for s in REGISTRY]
    assert len(names) == len(set(names))


def test_every_registered_kind_has_a_collector():
    from hazium.snapshots.collectors import COLLECTORS

    for spec in REGISTRY:
        assert spec.kind in COLLECTORS


def test_spec_by_name_roundtrips_and_reports_unknown():
    assert spec_by_name("sgu_groundwater").name == "sgu_groundwater"
    with pytest.raises(KeyError, match="unknown source"):
        spec_by_name("nope")


def test_no_echa_source_is_registered():
    # ECHA is WAF-gated and returns 403 to programmatic clients (verified
    # 2026-07-22). A collector that 403s every month is worse than none, so
    # ECHA data stays a manual browser acquisition.
    assert not [s for s in REGISTRY if "echa.europa.eu" in s.url]
