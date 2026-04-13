import os
import requests
from dotenv import load_dotenv

load_dotenv()

def search_gitlab_repos(query: str, max_results: int = 5) -> list[dict]:
    """
    Search GitLab for repositories matching the query.
    """
    # GitLab API works anonymously for public repos, but token increases limits
    token = os.environ.get("GITLAB_TOKEN")
    
    headers = {}
    if token:
        headers["PRIVATE-TOKEN"] = token
        
    url = "https://gitlab.com/api/v4/projects"
    params = {
        "search": query,
        "per_page": min(max_results, 100)
    }
    
    repos = []
    
    try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        
        if response.status_code == 429:
            print("Error: GitLab API rate limit exceeded.")
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
            
    except requests.exceptions.RequestException as e:
        print(f"Error fetching data from GitLab API: {e}")
        
    return repos
