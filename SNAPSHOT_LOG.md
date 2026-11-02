# Snapshot log

Some of the sources behind Hazium publish only their current state. They carry
no history, so a month that goes uncaptured is a month that cannot be recovered
later. `.github/workflows/snapshots.yml` captures them on the 2nd of each month
and appends to a private archive, `MartinBlomqvist/hazium-snapshots`.

That archive being private left the public repository with no record that the
capture happens at all. This file is that record, one row per run, written by
the workflow itself.

It also keeps the schedule alive. GitHub disables a scheduled workflow after 60
days without repository activity, and on 2026-11-02 it did exactly that, the
last push having been on 14 August. A commit once a month sits well inside the
limit.

A run reports success even when one source fails transiently, so the captured
column is the number of sources that returned and a row can read 3/4 and still
be a healthy run. A source that fails three runs in a row is marked broken.

| Date | Captured | Status | Notes | Log |
| --- | --- | --- | --- | --- |
| 2026-08-02 | unknown | success | run log expired before this file existed | [log](https://github.com/MartinBlomqvistDev/hazium/actions/runs/30735424428) |
| 2026-09-02 | 3/4 | success | kemi_sales unreachable | [log](https://github.com/MartinBlomqvistDev/hazium/actions/runs/33605744513) |
| 2026-10-02 | 4/4 | success |  | [log](https://github.com/MartinBlomqvistDev/hazium/actions/runs/36991243194) |
