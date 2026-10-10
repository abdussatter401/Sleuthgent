# Data preparation

The research evidence is not part of the source-code artifact. It contains
restricted and potentially sensitive material and must be obtained through the
data-access process described by the paper or artifact repository.

## Required inputs

The parser expects four prepared inputs:

```text
dataset/
├── evidence/
│   ├── android/
│   │   └── <RUN>/
│   │       ├── messages.json
│   │       └── threads.json
│   ├── system_files/
│   │   └── agents/
│   │       └── agent-*/sessions/*.jsonl
│   └── app_export/
│       └── extracted/manifest.json
└── run_index.csv
```

If the supplied evidence uses nested ZIP or TAR.GZ containers, extract the app
export and System Files containers before invoking the parser. Do not execute
code embedded in evidence packages.

## Parser invocation

```bash
python3 muse_activity_parser.py \
  --android dataset/evidence/android \
  --transcripts dataset/evidence/system_files/agents \
  --manifest dataset/evidence/app_export/extracted/manifest.json \
  --run-index dataset/run_index.csv \
  --out parsed_data
```

The parser never reads `ground_truth/`. Keep evaluation labels outside the
input paths supplied to the parser.

## Data handling

- Verify checksums supplied with the evidence before extraction.
- Work on a controlled host appropriate for the evidence classification.
- Do not commit raw evidence, extracted evidence, or parser output.
- Review output before sharing because reconstructed content may remain
  sensitive even though private thinking content is withheld.
- Treat source locators as paths into the local evidence copy; they may reveal
  directory names even when the underlying evidence is not distributed.
