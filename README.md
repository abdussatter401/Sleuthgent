# Sleuthgent

## Requirements

- Python 3.9 or newer
- Git LFS
- `unzip` and `tar`

## Run

Clone the repository and retrieve the dataset:

```bash
git lfs install
git clone https://github.com/abdussatter401/Sleuthgent.git
cd Sleuthgent
git lfs pull
```

Extract the dataset and its nested evidence containers:

```bash
unzip data.zip -d dataset

BASE="dataset/PARSER_DEVELOPMENT_MINIMAL_A03/MUSE_parser_development_MINIMAL"

tar -xzf "$BASE/evidence/system_files/system-files-archive-2026-10-07.tar.gz" \
  -C "$BASE/evidence/system_files" ./agents

mkdir -p "$BASE/evidence/app_export/extracted"

unzip "$BASE/evidence/app_export/EYI Package_10-07-2026_1791398451.zip" \
  -d "$BASE/evidence/app_export/extracted"
```

Run the parser:

```bash
BASE="dataset/PARSER_DEVELOPMENT_MINIMAL_A03/MUSE_parser_development_MINIMAL"

python3 muse_activity_parser.py \
  --android "$BASE/evidence/android" \
  --transcripts "$BASE/evidence/system_files/agents" \
  --manifest "$BASE/evidence/app_export/extracted/manifest.json" \
  --run-index "$BASE/run_index.csv" \
  --out parsed_data
```

Start the local viewer:

```bash
python3 muse_activity_viewer.py --data parsed_data
```

Open <http://127.0.0.1:8765> in a browser. Press `Ctrl+C` in the terminal to
stop the viewer.
