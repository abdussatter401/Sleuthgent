PYTHON ?= python3
DATA ?= parsed_data

.PHONY: viewer package

viewer:
	$(PYTHON) muse_activity_viewer.py --data $(DATA)

package:
	$(PYTHON) build_artifact.py
