"""Tests for app.py — deduplication and utility logic."""

import sys
import pytest

# We need to handle the streamlit import gracefully in test environment
# by importing only the standalone functions we can test without Streamlit

# Import the deduplication function directly from app module source
# We mock st.set_page_config since it runs at module level
from unittest.mock import MagicMock, patch

# Patch streamlit before importing app to prevent set_page_config from running
mock_st = MagicMock()
with patch.dict(sys.modules, {"streamlit": mock_st}):
    # We need to reload the module with the mock in place
    import importlib
    import app as app_module
    deduplicate_repos = app_module.deduplicate_repos


class TestDeduplicateRepos:
    """Tests for the cross-platform deduplication function."""

    def test_removes_duplicates_by_name(self):
        repos = [
            {"name": "sqlmap", "html_url": "https://github.com/a/sqlmap"},
            {"name": "sqlmap", "html_url": "https://gitlab.com/b/sqlmap"},
            {"name": "nmap", "html_url": "https://github.com/c/nmap"},
        ]
        result = deduplicate_repos(repos)
        assert len(result) == 2
        names = [r["name"] for r in result]
        assert "sqlmap" in names
        assert "nmap" in names

    def test_case_insensitive_dedup(self):
        repos = [
            {"name": "SQLMap", "html_url": "https://github.com/a"},
            {"name": "sqlmap", "html_url": "https://gitlab.com/b"},
        ]
        result = deduplicate_repos(repos)
        assert len(result) == 1

    def test_empty_list(self):
        assert deduplicate_repos([]) == []

    def test_preserves_first_occurrence(self):
        repos = [
            {"name": "tool", "html_url": "https://github.com/first"},
            {"name": "tool", "html_url": "https://gitlab.com/second"},
        ]
        result = deduplicate_repos(repos)
        assert result[0]["html_url"] == "https://github.com/first"

    def test_skips_empty_names(self):
        repos = [
            {"name": "", "html_url": "https://github.com/a"},
            {"name": "valid", "html_url": "https://github.com/b"},
        ]
        result = deduplicate_repos(repos)
        assert len(result) == 1
        assert result[0]["name"] == "valid"

    def test_handles_missing_name_key(self):
        repos = [
            {"html_url": "https://github.com/a"},
            {"name": "valid", "html_url": "https://github.com/b"},
        ]
        result = deduplicate_repos(repos)
        assert len(result) == 1
