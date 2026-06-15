# Development Utilities

These scripts were used during development for
smoke testing and exploration. They are not part
of the main application pipeline and not run by
pytest.

| Script | What it does |
|---|---|
| test_extraction.py | Runs docling on a sample PDF and dumps extraction JSON for manual inspection |
| test_bookmarks.py | Smoke test for pikepdf bookmark writing |
| test_tags.py | Exploratory script for full tag-tree injection via pikepdf — prototype for future tagged PDF structural remediation |
| compare_tags.py | Generates a before/after tag comparison HTML file — superseded by the in-app diff reporter |

To run any of these from ada-pdf-tool/:
  pixi run python dev/test_extraction.py
