import os
import requests
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

def search_github_repos(query: str, max_results: int = 10) -> list[dict]:
    """
    Search GitHub repositories using the GitHub REST API.
    
    Args:
        query (str): The search query string.
        max_results (int, optional): Maximum number of results to return. Defaults to 10.
        
    Returns:
        list[dict]: A list of dictionaries containing repository details.
    """
    token = os.environ.get("GITHUB_TOKEN")
    
    headers = {
        "Accept": "application/vnd.github.v3+json",
    }
    
    if token:
        headers["Authorization"] = f"Bearer {token}"
    else:
        print("Warning: GITHUB_TOKEN not found in environment variables. Making unauthenticated request.")
        
    url = "https://api.github.com/search/repositories"
    
    # GitHub's max per_page is 100.
    params = {
        "q": query,
        "per_page": min(max_results, 100) 
    }
    
    repos = []
    
    try:
        response = requests.get(url, headers=headers, params=params)
        
        # Handle rate limit exceeded
        if response.status_code in (403, 429) and "rate limit" in response.text.lower():
            reset_time = response.headers.get("X-RateLimit-Reset", "Unknown")
            print(f"Error: GitHub API rate limit exceeded. Resets at epoch timestamp: {reset_time}")
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
        print(f"HTTP Error fetching data from GitHub API: {http_err}")
    except requests.exceptions.RequestException as req_err:
        print(f"Connection/Request Error fetching data from GitHub API: {req_err}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        
    return repos
