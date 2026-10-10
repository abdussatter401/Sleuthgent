# Muse Activity Parser

Reconstructs user and agent activity from the PARSER_DEVELOPMENT_MINIMAL_A03
evidence package: device-side conversation snapshots, provider-side agent
transcripts, and the app-export manifest.

## Files

- `muse_activity_parser.py` — the parser (Python 3, stdlib only)
- `test_muse_activity_parser.py` — 18 synthetic tests (`python3 test_muse_activity_parser.py`)
- `muse_activity_viewer.py` and `viewer_web/` — local forensic viewer
- `test_muse_activity_viewer.py` — synthetic viewer data-model tests
- `RECONSTRUCTION_APPROACH.md` — the reconstruction approach, stated in full:
  source roles, join order, sequencing rules, and explicit non-claims
- `ARTIFACT.md` — artifact evaluation and reproducibility guide
- `DATA.md` — expected input layout and evidence-handling guidance

## Requirements

- Python 3.9 or newer
- No third-party Python packages
- A modern browser for the optional viewer

Run all synthetic validation with:

```bash
make test
```

## Usage

```bash
python3 muse_activity_parser.py \
  --android <evidence/android> \
  --transcripts <evidence/system_files/agents> \
  --manifest <evidence/app_export/extracted/manifest.json> \
  --run-index <run_index.csv> \
  --out <output dir>
```

## Outputs

- `session_<id>.json` — per provider session: turns (user message + agent
  actions), per-action locators (file + line), explicit approvals only,
  content-links to android messages with confidence labels
- `android_<RUN>.json` — per-run device messages ordered by
  `(timestamp_ms, seq)`, each joined to its manifest turn where the stable
  `message.id == turn_id` matches
- `index.json` — session inventory, manifest↔android join audit, run index

## Local forensic viewer

After producing the parser output, launch the dependency-free local viewer:

```bash
python3 muse_activity_viewer.py --data parsed_data
```

Then open `http://127.0.0.1:8765`. The viewer provides:

- case-level coverage and join auditing
- searchable/filterable provider sessions
- turn timelines with tool calls, explicit approvals, and source locators
- Android message review with role and manifest-join filters
- an interpretation guide that distinguishes recorded evidence from heuristics

The server binds to localhost by default, uses no external assets or services,
and sends browser responses with no-store and restrictive security headers.
Use `--host` or `--port` to override the local address only when needed.

## Enforced dataset policies

- Thinking content is never reproduced — not even when nested inside
  worker-dispatch payloads carried as user text (scrubbed at parse time).
- Approvals come only from explicit `userConfirmationStatus` records; never
  inferred from missing popups, thinking, or delegation.
- `ground_truth/` is never loaded by the parser.

## Validation performed

- 18/18 synthetic tests pass (ordering, joins, pairing, approval extraction,
  thinking scrubbing, malformed input).
- Full run: 396 sessions → 522 turns, 17 explicit approvals, manifest↔android
  ID overlap 145/150.
- Thinking-leak sweep over sampled phrases: zero hits in output.

## Artifact packaging

Raw evidence, extracted evidence, and parser output are intentionally excluded
from the source artifact. See `DATA.md` for data preparation and `ARTIFACT.md`
for the evaluation workflow.

Build the deterministic source archive with:

```bash
make package
```

The archive is assembled from an explicit allowlist and contains per-file
SHA-256 checksums. Before de-anonymized public release, add the license,
authors, citation metadata, and archival DOI approved for the paper.
