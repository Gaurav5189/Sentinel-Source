import requests
from config import GITHUB_TOKEN, GITHUB_API_URL, DEFAULT_TIMEOUT, get_logger

logger = get_logger(__name__)


def search_github_repos(query: str, max_results: int = 10) -> list[dict]:
    """
    Search GitHub repositories using the GitHub REST API.
    
    Args:
        query: The search query string.
        max_results: Maximum number of results to return. Defaults to 10.
        
    Returns:
        A list of dictionaries containing repository details.
    """
    headers = {
        "Accept": "application/vnd.github.v3+json",
    }
    
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    else:
        logger.warning("GITHUB_TOKEN not found. Making unauthenticated request (stricter rate limits).")
        
    url = f"{GITHUB_API_URL}/search/repositories"
    
    # GitHub's max per_page is 100.
    params = {
        "q": query,
        "per_page": min(max_results, 100) 
    }
    
    repos = []
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
        
        # Handle rate limit exceeded
        if response.status_code in (403, 429) and "rate limit" in response.text.lower():
            reset_time = response.headers.get("X-RateLimit-Reset", "Unknown")
            logger.error("GitHub API rate limit exceeded. Resets at epoch timestamp: %s", reset_time)
            return repos
            
        # Raise an exception for other HTTP errors (4xx or 5xx)
        response.raise_for_status()
        
        data = response.json()
        items = data.get("items", [])
        
        for item in items[:max_results]:
            repo_info = {
                'name': item.get('name'),
                'html_url': item.get('html_url'),
                'description': item.get('description'),
                'stargazers_count': item.get('stargazers_count'),
                'updated_at': item.get('updated_at'),
                'default_branch': item.get('default_branch')
            }
            repos.append(repo_info)
            
    except requests.exceptions.HTTPError as http_err:
        logger.error("HTTP Error fetching data from GitHub API: %s", http_err)
    except requests.exceptions.RequestException as req_err:
        logger.error("Connection/Request Error fetching data from GitHub API: %s", req_err)
    except Exception as e:
        logger.exception("Unexpected error during GitHub search: %s", e)
        
    return repos
