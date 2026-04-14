"""Tests for github_fetcher.py — GitHub repository search."""

import pytest
from unittest.mock import patch, MagicMock
from github_fetcher import search_github_repos


class TestSearchGithubRepos:
    """Tests for the GitHub API search function."""

    @patch("github_fetcher.requests.get")
    def test_successful_search(self, mock_get):
        """Verifies repos are correctly parsed from a valid API response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "items": [
                {
                    "name": "sqlmap",
                    "html_url": "https://github.com/sqlmapproject/sqlmap",
                    "description": "SQL injection tool",
                    "stargazers_count": 30000,
                    "updated_at": "2026-04-10",
                    "default_branch": "master"
                }
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = search_github_repos("sql injection", max_results=5)

        assert len(results) == 1
        assert results[0]["name"] == "sqlmap"
        assert results[0]["html_url"] == "https://github.com/sqlmapproject/sqlmap"

    @patch("github_fetcher.requests.get")
    def test_empty_results(self, mock_get):
        """Verifies empty list on no results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = search_github_repos("nonexistent_tool_xyz")
        assert results == []

    @patch("github_fetcher.requests.get")
    def test_rate_limit_returns_empty(self, mock_get):
        """Verifies graceful handling of rate limit (403/429)."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_response.text = "API rate limit exceeded"
        mock_response.headers = {"X-RateLimit-Reset": "1700000000"}
        mock_get.return_value = mock_response

        results = search_github_repos("nmap")
        assert results == []

    @patch("github_fetcher.requests.get")
    def test_network_error_returns_empty(self, mock_get):
        """Verifies graceful handling of network failures."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("Network unreachable")

        results = search_github_repos("test")
        assert results == []

    @patch("github_fetcher.requests.get")
    def test_max_results_respected(self, mock_get):
        """Verifies that max_results caps the output."""
        items = [
            {"name": f"repo_{i}", "html_url": f"https://github.com/u/repo_{i}",
             "description": "", "stargazers_count": 0, "updated_at": "", "default_branch": "main"}
            for i in range(20)
        ]
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": items}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = search_github_repos("test", max_results=3)
        assert len(results) == 3

    @patch("github_fetcher.requests.get")
    def test_timeout_parameter_set(self, mock_get):
        """Verifies that a timeout is passed to requests.get (SEC-07)."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"items": []}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        search_github_repos("test")

        _, kwargs = mock_get.call_args
        assert "timeout" in kwargs
        assert kwargs["timeout"] > 0
