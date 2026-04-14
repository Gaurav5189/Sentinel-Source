"""
Shared pytest fixtures for the Sentinel-Source test suite.
All fixtures defined here are automatically available to every test module.
"""

import pytest


@pytest.fixture
def sample_github_repo():
    """A representative GitHub repo dict as returned by github_fetcher."""
    return {
        "name": "sqlmap",
        "html_url": "https://github.com/sqlmapproject/sqlmap",
        "description": "Automatic SQL injection and database takeover tool",
        "stargazers_count": 30000,
        "updated_at": "2026-04-10T12:00:00Z",
        "default_branch": "master"
    }


@pytest.fixture
def sample_gitlab_repo():
    """A representative GitLab repo dict as returned by gitlab_fetcher."""
    return {
        "name": "nmap-scanner",
        "html_url": "https://gitlab.com/security/nmap-scanner",
        "description": "Network scanner wrapper",
        "stargazers_count": 50,
        "updated_at": "2026-03-20T08:00:00Z",
        "default_branch": "main",
        "is_gitlab": True,
        "path_with_namespace": "security/nmap-scanner"
    }


@pytest.fixture
def sample_repo_list(sample_github_repo, sample_gitlab_repo):
    """A mixed list of GitHub and GitLab repos."""
    return [sample_github_repo, sample_gitlab_repo]


@pytest.fixture
def sample_llm_response_json():
    """Valid JSON that mimics a well-formed LLM evaluation response."""
    return {
        "sqlmap": {
            "score": 9,
            "is_legit": True,
            "analysis": "Well-known SQL injection tool. Actively maintained and widely used."
        },
        "nmap-scanner": {
            "score": 5,
            "is_legit": True,
            "analysis": "Simple nmap wrapper. Functional but limited in scope."
        }
    }
