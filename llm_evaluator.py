import os
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def enhance_query_llm(raw_query: str) -> str:
    """
    Acts as an intelligent security prompt enhancer. Normalizes typos and heavily contextualizes 
    the search toward cybersecurity/pentesting to provide much cleaner results.
    """
    api_key = os.environ.get("OPENROUTER_API_KEY")
    selected_model = os.environ.get("OPENROUTER_MODEL")
    
    if not api_key or not selected_model:
        return raw_query # Gracefully fall back to original if missing config

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    system_prompt = (
        "You are an expert cybersecurity query analyzer. Your objective is to take a messy, raw "
        "search query and fix it to yield high-quality generic GitHub pentesting repository results. "
        "Correct any spelling/grammar (e.g. 'sql ingestion' -> 'sql injection'). "
        "Strictly bind the query to cybersecurity, hacking, or pentesting contexts if it is ambiguous. "
        "Reply ONLY with the exact, naked corrected string. Do absolutely not include quotes, periods, or extra context. "
        "If the query is already perfect, just return it exactly as is."
    )

    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": raw_query}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        response.raise_for_status()
        content = response.json()['choices'][0]['message'].get('content', '')
        
        if not content:
            return raw_query
            
        # Strip out loose quotes formatting if hallucinated
        enhanced = content.replace('"', '').replace("'", "").strip()
        return enhanced
    except Exception as e:
        print(f"Error during query enhancement: {e}")
        return raw_query


def evaluate_tools_batch(repo_list: list[dict]) -> list[dict]:
    """
    Evaluates a batch of repositories' viability and safety using an LLM.
    Sends one single prompt containing all repos to drastically reduce API requests.
    """
    if not repo_list:
        return []

    # Create a deep-ish copy to avoid mutating original immediately on failure
    updated_repos = [repo.copy() for repo in repo_list]
    
    api_key = os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Warning: OPENROUTER_API_KEY not found. Skipping evaluation.")
        for repo in updated_repos:
            repo.update({"score": 0, "is_legit": False, "analysis": "Skipped due to missing API key."})
        return updated_repos
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    # Compress all readmes into a single prompt string to save massive amounts of requests
    combined_context = ""
    for idx, repo in enumerate(updated_repos):
        name = repo.get("name", f"repo_{idx}")
        updated_at = repo.get("updated_at", "Unknown")
        # Truncating to 2000 chars per repo ensures we comfortably fit within standard context windows
        readme = repo.get("readme_text", "")[:2000]
        combined_context += f"--- REPOSITORY ---\nName: {name}\nLast Updated: {updated_at}\nREADME Snippet:\n{readme}\n\n"

    system_prompt = (
        "You are an expert cybersecurity analyst. Evaluate the following batch of GitHub repositories "
        "to determine if EACH one is a legitimate, currently working, and safe pentesting tool based on its snippet.\n\n"
        "You MUST reply ONLY with a valid JSON object. Do not include markdown formatting or extra text. "
        "The keys of your JSON object MUST be the exact 'Name' of each repository provided. "
        "The value for each key MUST be an object with these exact three keys:\n"
        "- \"score\": integer 1-10 (viability/safety)\n"
        "- \"is_legit\": boolean (true if it's a legitimate tool, false otherwise)\n"
        "- \"analysis\": string (strict 2-sentence summary of your evaluation)\n"
    )

    selected_model = os.environ.get("OPENROUTER_MODEL")
    if not selected_model:
        raise ValueError("OPENROUTER_MODEL is not configured.")

    payload = {
        "model": selected_model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": combined_context}
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=60)
        response.raise_for_status()
        
        response_data = response.json()
        content = response_data['choices'][0]['message'].get('content')
        
        if not content:
            raise ValueError("LLM returned empty or None content.")
            
        # Safely strip potential markdown ticks
        content = content.strip()
        if content.startswith("```json"):
            content = content[7:]
        if content.startswith("```"):
            content = content[3:]
        if content.endswith("```"):
            content = content[:-3]
        content = content.strip()

        eval_results = json.loads(content)
        
        # Map evaluations back to individual repositories
        for repo in updated_repos:
            repo_name = repo.get("name")
            if repo_name in eval_results:
                repo["score"] = int(eval_results[repo_name].get("score", 0))
                repo["is_legit"] = bool(eval_results[repo_name].get("is_legit", False))
                repo["analysis"] = str(eval_results[repo_name].get("analysis", "No analysis provided."))
            else:
                repo["score"] = 0
                repo["is_legit"] = False
                repo["analysis"] = "LLM failed to output analysis for this specific repo."

    except Exception as e:
        print(f"Error during batch LLM evaluation: {e}")
        for repo in updated_repos:
            repo.update({"score": 0, "is_legit": False, "analysis": f"Failed during batch LLM sequence: {e}"})
        
    return updated_repos
