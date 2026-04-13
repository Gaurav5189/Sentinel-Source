import concurrent.futures
import requests

def _fetch_readme(repo: dict) -> dict:
    """
    Worker function to fetch the README for a single repository.
    Handles both GitHub and GitLab URLs automatically.
    """
    # Create a copy so we don't unexpectedly mutate the original list's dictionaries
    updated_repo = repo.copy()
    html_url = updated_repo.get('html_url', '')
    default_branch = updated_repo.get('default_branch', 'main')
    is_gitlab = updated_repo.get('is_gitlab', False)
    
    # Default to an empty string if not found or an error occurs
    updated_repo['readme_text'] = ""
    
    try:
        if html_url:
            if is_gitlab:
                # GitLab raw content URL format relies on the namespace path natively
                path = updated_repo.get('path_with_namespace')
                raw_url = f"https://gitlab.com/{path}/-/raw/{default_branch}/README.md"
            else:
                # Extract owner and repo from the GitHub URL
                parts = html_url.rstrip('/').split('/')
                if len(parts) >= 2:
                    owner = parts[-2]
                    repo_name = parts[-1]
                    raw_url = f"https://raw.githubusercontent.com/{owner}/{repo_name}/{default_branch}/README.md"
                else:
                    return updated_repo
                    
            # Fetch text with a 5-second timeout as requested
            response = requests.get(raw_url, timeout=5.0)
            
            if response.status_code == 200:
                updated_repo['readme_text'] = response.text
                
    except requests.RequestException as e:
        # Catch standard requests exceptions specifically (timeout, connection error, etc.)
        print(f"Network error fetching README for {updated_repo.get('name')}: {e}")
    except Exception as e:
        print(f"Unexpected error fetching README for {updated_repo.get('name')}: {e}")
        
    return updated_repo

def fetch_readmes_concurrently(repo_list: list[dict]) -> list[dict]:
    """
    Concurrently fetch README text for a list of repositories using ThreadPoolExecutor.
    """
    # Using ThreadPoolExecutor since fetching over network is I/O bound
    with concurrent.futures.ThreadPoolExecutor() as executor:
        # executor.map preserves the order of the original list
        results = list(executor.map(_fetch_readme, repo_list))
        
    return results
