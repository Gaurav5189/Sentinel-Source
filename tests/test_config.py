"""Tests for config.py — centralized configuration and utility functions."""

import pytest
from config import (
    sanitize_filename,
    sanitize_readme_text,
    validate_url_domain,
    sanitize_query,
    MAX_QUERY_LENGTH,
    MAX_README_LENGTH,
    ALLOWED_README_DOMAINS,
)


class TestSanitizeFilename:
    """Tests for filename sanitization (CQ-07)."""

    def test_spaces_replaced(self):
        assert sanitize_filename("sql injection scanner") == "sql_injection_scanner"

    def test_special_chars_removed(self):
        assert sanitize_filename("../../etc/passwd") == "______etc_passwd"

    def test_preserves_alphanumeric(self):
        assert sanitize_filename("nmap_tool-v2") == "nmap_tool-v2"

    def test_empty_string(self):
        assert sanitize_filename("") == ""

    def test_null_bytes_removed(self):
        assert "\x00" not in sanitize_filename("test\x00file")


class TestSanitizeReadmeText:
    """Tests for README sanitization & prompt injection defense (SEC-02)."""

    def test_truncates_to_max_length(self):
        long_text = "A" * (MAX_README_LENGTH + 500)
        result = sanitize_readme_text(long_text)
        assert len(result) == MAX_README_LENGTH

    def test_removes_control_characters(self):
        text = "Hello\x00World\x07Test"
        result = sanitize_readme_text(text)
        assert "\x00" not in result
        assert "\x07" not in result
        assert "HelloWorldTest" == result

    def test_preserves_newlines_and_tabs(self):
        text = "Line 1\nLine 2\tTabbed"
        result = sanitize_readme_text(text)
        assert "\n" in result
        assert "\t" in result

    def test_empty_string(self):
        assert sanitize_readme_text("") == ""

    def test_none_input(self):
        assert sanitize_readme_text(None) == ""

    def test_custom_max_length(self):
        result = sanitize_readme_text("A" * 100, max_length=50)
        assert len(result) == 50


class TestValidateUrlDomain:
    """Tests for SSRF defense URL validation (SEC-01)."""

    def test_valid_github_url(self):
        url = "https://raw.githubusercontent.com/user/repo/main/README.md"
        assert validate_url_domain(url) is True

    def test_valid_gitlab_url(self):
        url = "https://gitlab.com/group/project/-/raw/main/README.md"
        assert validate_url_domain(url) is True

    def test_blocks_arbitrary_domain(self):
        url = "https://evil.com/malicious"
        assert validate_url_domain(url) is False

    def test_blocks_http_scheme(self):
        url = "http://raw.githubusercontent.com/user/repo/main/README.md"
        assert validate_url_domain(url) is False

    def test_blocks_internal_ip(self):
        url = "https://127.0.0.1/secret"
        assert validate_url_domain(url) is False

    def test_blocks_file_scheme(self):
        url = "file:///etc/passwd"
        assert validate_url_domain(url) is False

    def test_empty_url(self):
        assert validate_url_domain("") is False

    def test_malformed_url(self):
        assert validate_url_domain("not-a-url") is False


class TestSanitizeQuery:
    """Tests for user input query sanitization (SEC-03)."""

    def test_strips_whitespace(self):
        assert sanitize_query("  sql injection  ") == "sql injection"

    def test_enforces_max_length(self):
        long_query = "A" * (MAX_QUERY_LENGTH + 100)
        result = sanitize_query(long_query)
        assert len(result) == MAX_QUERY_LENGTH

    def test_removes_null_bytes(self):
        assert "\x00" not in sanitize_query("test\x00query")

    def test_removes_control_characters(self):
        result = sanitize_query("test\x07\x08query")
        assert result == "testquery"

    def test_empty_string(self):
        assert sanitize_query("") == ""

    def test_none_input(self):
        assert sanitize_query(None) == ""

    def test_normal_query_unchanged(self):
        assert sanitize_query("subdomain scanner") == "subdomain scanner"
