"""Tests for repo_scraper.py — concurrent README fetching with SSRF defense."""

import pytest
from unittest.mock import patch, MagicMock
from repo_scraper import _fetch_readme, fetch_readmes_concurrently


class TestFetchReadme:
    """Tests for the individual README fetch worker."""

    @patch("repo_scraper.requests.get")
    def test_github_readme_fetch(self, mock_get, sample_github_repo):
        """Verifies successful README fetch from GitHub."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# SQLMap\nAutomatic SQL injection tool."
        mock_get.return_value = mock_response

        result = _fetch_readme(sample_github_repo)

        assert result["readme_text"] == "# SQLMap\nAutomatic SQL injection tool."
        assert result["name"] == "sqlmap"

    @patch("repo_scraper.requests.get")
    def test_gitlab_readme_fetch(self, mock_get, sample_gitlab_repo):
        """Verifies successful README fetch from GitLab."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Nmap Scanner\nNetwork scanning wrapper."
        mock_get.return_value = mock_response

        result = _fetch_readme(sample_gitlab_repo)

        assert result["readme_text"] == "# Nmap Scanner\nNetwork scanning wrapper."
        assert result["is_gitlab"] is True

    @patch("repo_scraper.requests.get")
    def test_404_returns_empty_readme(self, mock_get, sample_github_repo):
        """Verifies empty readme_text on 404 response."""
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        result = _fetch_readme(sample_github_repo)
        assert result["readme_text"] == ""

    def test_ssrf_blocks_untrusted_domain(self):
        """SSRF defense: blocks fetch to non-allowed domains (SEC-01)."""
        malicious_repo = {
            "name": "evil-tool",
            "html_url": "https://evil.com/attacker/evil-tool",
            "default_branch": "main"
        }
        # This should be blocked before making any network request
        result = _fetch_readme(malicious_repo)
        assert result["readme_text"] == ""

    def test_missing_html_url(self):
        """Verifies graceful handling of missing html_url."""
        repo = {"name": "no-url", "default_branch": "main"}
        result = _fetch_readme(repo)
        assert result["readme_text"] == ""

    @patch("repo_scraper.requests.get")
    def test_does_not_mutate_original(self, mock_get, sample_github_repo):
        """Verifies the original dict is not mutated."""
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.text = "# Test"
        mock_get.return_value = mock_response

        original_keys = set(sample_github_repo.keys())
        _fetch_readme(sample_github_repo)
        assert set(sample_github_repo.keys()) == original_keys
        assert "readme_text" not in sample_github_repo

    def test_gitlab_missing_path_with_namespace(self):
        """Verifies graceful handling when GitLab repo has no path_with_namespace."""
        repo = {
            "name": "broken-gitlab",
            "html_url": "https://gitlab.com/test/broken-gitlab",
            "default_branch": "main",
            "is_gitlab": True,
            # path_with_namespace intentionally missing
        }
        result = _fetch_readme(repo)
        assert result["readme_text"] == ""


class TestFetchReadmesConcurrently:
    """Tests for the concurrent README fetcher."""

    @patch("repo_scraper._fetch_readme")
    def test_preserves_order(self, mock_fetch):
        """Verifies results maintain the same order as input."""
        repos = [
            {"name": "repo_a"},
            {"name": "repo_b"},
            {"name": "repo_c"},
        ]
        mock_fetch.side_effect = lambda r: {**r, "readme_text": f"readme_{r['name']}"}

        results = fetch_readmes_concurrently(repos)

        assert len(results) == 3
        assert results[0]["name"] == "repo_a"
        assert results[1]["name"] == "repo_b"
        assert results[2]["name"] == "repo_c"

    def test_empty_list(self):
        """Verifies empty input returns empty output."""
        results = fetch_readmes_concurrently([])
        assert results == []
