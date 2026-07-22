"""Content-addressed snapshot store with an append-only observation manifest.

Layout::

    <root>/manifest.jsonl              one Observation per line, append-only
    <root>/blobs/<aa>/<sha256>.gz      gzipped payload, named by its own hash

Two properties matter and both fall out of content addressing:

* **Immutability.** A blob is named by its hash, so writing it twice is a no-op
  and overwriting it with different content is impossible.
* **Cheap repetition.** Registers change slowly. Capturing an unchanged payload
  costs one manifest line and no new blob, so a monthly capture of a static
  register stays flat in size instead of growing linearly.

The manifest is the record of *observations*, the blobs are the record of
*content*, and the two are deliberately separate: "we checked and nothing had
changed" is information worth keeping, and it has no payload of its own.
"""

from __future__ import annotations

import gzip
import hashlib
import json
from datetime import UTC, datetime
from pathlib import Path

from hazium.snapshots.models import Observation

MANIFEST_NAME = "manifest.jsonl"
BLOB_DIR = "blobs"


def sha256_hex(payload: bytes) -> str:
    """Hex SHA-256 digest of ``payload``."""
    return hashlib.sha256(payload).hexdigest()


class SnapshotStore:
    """Append-only store of dated source captures.

    Args:
        root: Directory holding the manifest and blobs. Created on demand.
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)
        self.manifest_path = self.root / MANIFEST_NAME
        self.blob_root = self.root / BLOB_DIR

    # ------------------------------------------------------------------ read

    def observations(self, source: str | None = None) -> list[Observation]:
        """Every recorded observation, oldest first.

        Args:
            source: Restrict to one source name. ``None`` returns all.

        Returns:
            Parsed observations. A malformed line is skipped rather than
            raising: a corrupt tail must not make the whole history unreadable.
        """
        if not self.manifest_path.exists():
            return []
        out: list[Observation] = []
        with self.manifest_path.open("r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    obs = Observation.model_validate_json(line)
                except ValueError:
                    continue
                if source is None or obs.source == source:
                    out.append(obs)
        return out

    def latest_digest(self, source: str) -> str | None:
        """Digest of the most recent successful capture of ``source``."""
        for obs in reversed(self.observations(source)):
            if obs.ok and obs.digest:
                return obs.digest
        return None

    def consecutive_failures(self, source: str) -> int:
        """Number of failures since the last success for ``source``.

        Used to distinguish a transient outage, which should not alert, from a
        collector that has silently rotted, which must.
        """
        count = 0
        for obs in reversed(self.observations(source)):
            if obs.ok:
                break
            count += 1
        return count

    def blob_path(self, digest: str) -> Path:
        """Path a blob with ``digest`` occupies, whether or not it exists."""
        return self.blob_root / digest[:2] / f"{digest}.gz"

    def read_blob(self, digest: str) -> bytes:
        """Decompressed payload for ``digest``.

        Raises:
            FileNotFoundError: If no blob with that digest is stored.
        """
        path = self.blob_path(digest)
        if not path.exists():
            raise FileNotFoundError(f"no blob for digest {digest}")
        with gzip.open(path, "rb") as fh:
            return fh.read()

    # ----------------------------------------------------------------- write

    def record_success(
        self,
        source: str,
        payload: bytes,
        *,
        captured_at: datetime | None = None,
        meta: dict[str, str | int] | None = None,
    ) -> Observation:
        """Store ``payload`` for ``source`` and append an observation.

        The blob is written only when its content is new to the store. When the
        payload matches this source's previous capture the observation is
        flagged ``unchanged`` and no bytes are written.

        Args:
            source: Source name.
            payload: Raw uncompressed bytes as retrieved.
            captured_at: Capture time, defaulting to now (UTC). This becomes the
                ``known_at`` of anything derived from the payload.
            meta: Collector-specific detail to record alongside.

        Returns:
            The appended observation.
        """
        stamp = captured_at or datetime.now(UTC)
        digest = sha256_hex(payload)
        unchanged = self.latest_digest(source) == digest

        path = self.blob_path(digest)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            # mtime=0 so identical payloads compress to identical bytes.
            with gzip.GzipFile(filename="", mode="wb", fileobj=path.open("wb"), mtime=0) as fh:
                fh.write(payload)

        obs = Observation(
            source=source,
            captured_at=stamp,
            ok=True,
            digest=digest,
            n_bytes=len(payload),
            unchanged=unchanged,
            meta=meta or {},
        )
        self._append(obs)
        return obs

    def record_failure(
        self,
        source: str,
        error: str,
        *,
        captured_at: datetime | None = None,
        meta: dict[str, str | int] | None = None,
    ) -> Observation:
        """Append a failed observation for ``source``."""
        obs = Observation(
            source=source,
            captured_at=captured_at or datetime.now(UTC),
            ok=False,
            error=error[:500],
            meta=meta or {},
        )
        self._append(obs)
        return obs

    def _append(self, obs: Observation) -> None:
        """Append one observation to the manifest."""
        self.root.mkdir(parents=True, exist_ok=True)
        line = json.dumps(json.loads(obs.model_dump_json()), sort_keys=True)
        with self.manifest_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")
