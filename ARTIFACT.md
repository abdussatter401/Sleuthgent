# Artifact evaluation guide

## Scope

This artifact contains the Muse activity reconstruction parser, a local
forensic viewer, synthetic tests, and the documented reconstruction method. It
does not contain restricted research evidence or outputs derived from that
evidence.

## Requirements

- Python 3.9 or newer
- A modern browser for the optional local viewer
- No third-party Python packages
- No network connection for parsing, testing, or viewing

The artifact was validated with Python 3.12 on Linux. The implementation uses
only the Python standard library and browser-native HTML, CSS, and JavaScript.

## Quick evaluation

From the repository root, run:

```bash
make test
```

Expected result:

```text
ALL PASS
ALL PASS
```

The first suite exercises ordering, stable-ID joins, call/result pairing,
explicit approval extraction, thinking-content withholding, malformed input,
and content linkage. The second suite exercises viewer indexing, filtering,
summary generation, and missing-record handling using synthetic data.

## Full evaluation

Prepare the evidence as described in `DATA.md`, run the parser command in the
README, and compare the resulting summary with the paper's reported dataset
results. For the development package used during implementation, the observed
summary was:

```text
396 sessions, 522 turns, 17 explicit approvals;
manifest<->android id overlap 145/150
```

These values are dataset-specific acceptance references, not constants encoded
in the parser.

## Viewer evaluation

After producing `parsed_data/`, run:

```bash
make viewer DATA=parsed_data
```

Open `http://127.0.0.1:8765`. Confirm that the overview loads, session filters
return results, a session timeline opens, and device messages can be filtered
by role and manifest-join status. The viewer binds to localhost by default and
loads no third-party assets.

## Reproducible release archive

Run:

```bash
make package
```

This creates `dist/muse-activity-parser-artifact.zip` from an explicit source
allowlist. The archive includes `SHA256SUMS` for every packaged file and cannot
include the local dataset, extracted evidence, parser output, caches, or logs.
The builder prints the SHA-256 digest of the completed archive.

## Claims and limitations

The parser reconstructs surviving recorded activity. It does not claim that
assistant statements prove external effects, that unmatched records are
unrelated, or that absence of an approval record proves no prompt occurred.
Turn grouping and transcript-to-device content links are explicitly identified
as reconstruction logic. See `RECONSTRUCTION_APPROACH.md` for the complete
method and limitations.

## Anonymized review

The source artifact contains no author, affiliation, or paper-identifier
metadata. Add the venue-approved license, author list, citation metadata, and
archival DOI only when permitted by the submission's anonymity policy.
