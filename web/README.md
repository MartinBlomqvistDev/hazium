# hazium.org

The public site. Next.js 16 (App Router), React 19, Tailwind 4, deployed on
Vercel from the repository root.

## Routes

| route | what it carries |
|---|---|
| `/` | the result in three cards, the Fluazinam evidence mesh, why the project exists |
| `/method` | the six feature groups and what each is worth, and what the first benchmark's lead times actually measure |
| `/watchlist` | the 100-substance withdrawal watchlist, the anchor case it misses, and the PFAS-precursor screen |
| `/explorer` | the full scored population at the 2023 cutoff, searchable |

## Every figure on this site is generated

No component holds a number as a string literal. That rule exists because the
ones that did drifted: the page claimed 374 tests against 385, then 395 against
415, and a crop caption went on naming an extreme the data had moved away from.
Components read `web/data/*.json`, and each of those files is written by a
numbered pipeline in the repository root:

| file | written by |
|---|---|
| `build.json` | `pipeline/36_export_build_facts.py` |
| `survival.json` | `pipeline/33_export_survival_site_data.py` |
| `tfa_screen.json` | `pipeline/35_run_tfa_screen.py` |
| `watchlist.json` | `pipeline/27_export_watchlist_site_data.py` |
| `evidence_mesh.json` | `pipeline/24_export_evidence_mesh.py` |
| `capability.json`, `hewb.json`, `substances.json`, `rank_race.json` | `pipeline/12`, `18`, `19`, `23` |

If a figure on the site looks wrong, fix the pipeline that produces it rather
than the component.

## Local development

```bash
npm install
npm run dev
```

Then open http://localhost:3000. The data files are committed, so the site runs
without the Python pipeline present.

## Before pushing

```bash
npx tsc --noEmit && npm run build
```

CI runs the Python suite only, so the site is verified by the Vercel build. A
type error or a failed prerender surfaces there, which is late; run both locally
first.
