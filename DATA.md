# Data preparation

The owner-authorized research evidence is stored in this repository as
`data.zip` using Git LFS. The package is unsanitized and may contain historical
or private material. Install Git LFS before cloning so the archive is retrieved
instead of only its pointer file:

```bash
git lfs install
git clone https://github.com/abdussatter401/Sleuthgent.git
cd Sleuthgent
git lfs pull
```

Verify the archive before extraction:

```text
SHA-256  0eeba52c63cd3cae6e27b5ec768fd52620c30ec09b7bb8c4113415642a4cf5bf
Size     294318505 bytes
```

Example:

```bash
sha256sum data.zip
```

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
- Treat repository availability as distribution authorization, not as a statement
  that the evidence is free of sensitive information.
- Work on a controlled host appropriate for the evidence classification.
- Do not commit raw evidence, extracted evidence, or parser output.
- Review output before sharing because reconstructed content may remain
  sensitive even though private thinking content is withheld.
- Treat source locators as paths into the local evidence copy; they may reveal
  directory names even when the underlying evidence is not distributed.
