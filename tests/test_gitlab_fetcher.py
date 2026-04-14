"""Tests for gitlab_fetcher.py — GitLab repository search."""

import pytest
from unittest.mock import patch, MagicMock
from gitlab_fetcher import search_gitlab_repos


class TestSearchGitlabRepos:
    """Tests for the GitLab API search function."""

    @patch("gitlab_fetcher.requests.get")
    def test_successful_search(self, mock_get):
        """Verifies repos are correctly parsed from a valid API response."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = [
            {
                "name": "nmap-wrapper",
                "web_url": "https://gitlab.com/sec/nmap-wrapper",
                "description": "Nmap scanner wrapper",
                "star_count": 42,
                "last_activity_at": "2026-03-15",
                "default_branch": "main",
                "path_with_namespace": "sec/nmap-wrapper"
            }
        ]
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = search_gitlab_repos("nmap", max_results=5)

        assert len(results) == 1
        assert results[0]["name"] == "nmap-wrapper"
        assert results[0]["is_gitlab"] is True
        assert results[0]["path_with_namespace"] == "sec/nmap-wrapper"

    @patch("gitlab_fetcher.requests.get")
    def test_empty_results(self, mock_get):
        """Verifies empty list on no results."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = []
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        results = search_gitlab_repos("nonexistent_xyz")
        assert results == []

    @patch("gitlab_fetcher.requests.get")
    def test_rate_limit_returns_empty(self, mock_get):
        """Verifies graceful handling of rate limit (429)."""
        mock_response = MagicMock()
        mock_response.status_code = 429
        mock_get.return_value = mock_response

        results = search_gitlab_repos("nmap")
        assert results == []

    @patch("gitlab_fetcher.time.sleep")
    @patch("gitlab_fetcher.requests.get")
    def test_timeout_retries(self, mock_get, mock_sleep):
        """Verifies that timeouts trigger retries with sleep."""
        import requests as req
        mock_get.side_effect = req.exceptions.Timeout("Connection timed out")

        results = search_gitlab_repos("test", max_results=3)

        assert results == []
        # Should have retried (GITLAB_MAX_RETRIES = 2, so 2 calls)
        assert mock_get.call_count == 2
        # sleep is called between retries
        assert mock_sleep.called

    @patch("gitlab_fetcher.requests.get")
    def test_network_error_breaks_loop(self, mock_get):
        """Verifies non-timeout RequestException breaks retry loop."""
        import requests as req
        mock_get.side_effect = req.exceptions.ConnectionError("DNS failure")

        results = search_gitlab_repos("test")

        assert results == []
        # Should NOT retry on non-timeout errors
        assert mock_get.call_count == 1
