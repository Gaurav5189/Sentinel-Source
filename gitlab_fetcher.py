import time
import requests
from config import (
    GITLAB_TOKEN, GITLAB_API_URL, GITLAB_TIMEOUT, GITLAB_MAX_RETRIES, get_logger
)

logger = get_logger(__name__)


def search_gitlab_repos(query: str, max_results: int = 5) -> list[dict]:
    """
    Search GitLab for repositories matching the query.
    
    Args:
        query: The search query string.
        max_results: Maximum number of results to return. Defaults to 5.
        
    Returns:
        A list of dictionaries containing repository details.
    """
    headers = {}
    if GITLAB_TOKEN:
        headers["PRIVATE-TOKEN"] = GITLAB_TOKEN
        
    url = f"{GITLAB_API_URL}/projects"
    params = {
        "search": query,
        "per_page": min(max_results, 100)
    }
    
    repos = []
    
    for attempt in range(GITLAB_MAX_RETRIES):
        try:
            response = requests.get(url, headers=headers, params=params, timeout=GITLAB_TIMEOUT)
            
            if response.status_code == 429:
                logger.error("GitLab API rate limit exceeded.")
                return repos
                
            response.raise_for_status()
            items = response.json()
            
            for item in items[:max_results]:
                repo_info = {
                    'name': item.get('name'),
                    'html_url': item.get('web_url'),
                    'description': item.get('description'),
                    'stargazers_count': item.get('star_count'),
                    'updated_at': item.get('last_activity_at'),
                    'default_branch': item.get('default_branch', 'main'),
                    'is_gitlab': True,
                    'path_with_namespace': item.get('path_with_namespace')
                }
                repos.append(repo_info)
                
            # Break immediately out of loop on a successful pull
            break
                
        except requests.exceptions.Timeout:
            logger.warning(
                "GitLab API Timeout (Attempt %d/%d). Retrying...",
                attempt + 1, GITLAB_MAX_RETRIES
            )
            if attempt == GITLAB_MAX_RETRIES - 1:
                logger.error("GitLab timed out after %d attempts.", GITLAB_MAX_RETRIES)
            time.sleep(2)
        except requests.exceptions.RequestException as e:
            logger.error("Error fetching data from GitLab API: %s", e)
            break
            
    return repos
