PYTHON ?= python3
DATA ?= parsed_data

.PHONY: test viewer package

test:
	$(PYTHON) -m py_compile muse_activity_parser.py muse_activity_viewer.py test_muse_activity_parser.py test_muse_activity_viewer.py build_artifact.py
	$(PYTHON) test_muse_activity_parser.py
	$(PYTHON) test_muse_activity_viewer.py

viewer:
	$(PYTHON) muse_activity_viewer.py --data $(DATA)

package:
	$(PYTHON) build_artifact.py
