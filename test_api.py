import os
import requests
from dotenv import load_dotenv

def test_github():
    github_token = os.environ.get("GITHUB_TOKEN")
    
    print("-" * 50)
    print("Testing GitHub API")
    print("-" * 50)
    
    if not github_token:
        print("ℹ️ Warning: GITHUB_TOKEN not found in .env. Searches will be anonymous and strictly rate-limited.")
        return
        
    headers = {
        "Accept": "application/vnd.github.v3+json",
        "Authorization": f"Bearer {github_token}"
    }
    
    try:
        # Hitting a simple endpoint to verify authorization status
        response = requests.get("https://api.github.com/user", headers=headers, timeout=10)
        
        if response.status_code == 200:
            try:
                user = response.json().get("login", "Unknown User")
                print(f"✅ SUCCESS! Valid token. Authenticated to GitHub as: {user}")
            except requests.exceptions.JSONDecodeError:
                print("❌ ERROR: Received 200 but failed to parse JSON response.")
        elif response.status_code == 401:
            print("❌ ERROR 401: Your GITHUB_TOKEN is INVALID. Please check it in your .env file.")
        else:
            print(f"❌ ERROR {response.status_code}: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network Error connecting to GitHub: {e}")

def test_openrouter():
    api_key = os.environ.get("OPENROUTER_API_KEY")
    # I noticed you changed your default to minimax!
    model = os.environ.get("OPENROUTER_MODEL", "minimax/minimax-m2.5:free")

    print("\n" + "-" * 50)
    print("Testing OpenRouter API (LLM)")
    print("-" * 50)
    print(f"Selected Model: {model}")
    
    if not api_key:
        print("❌ ERROR: OPENROUTER_API_KEY is missing from your .env file.")
        return
        
    if not api_key.startswith("sk-or-"):
        print("⚠️ Warning: Most OpenRouter keys start with 'sk-or-'. Double-check your key.")
        
    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": "Reply with exactly the word: 'pong'."}]
    }
    
    try:
        # Send a tiny ping requirement
        response = requests.post(url, headers=headers, json=payload, timeout=15)
        
        if response.status_code == 200:
            try:
                data = response.json()
                msg = data['choices'][0]['message']['content']
                print(f"✅ SUCCESS! LLM is actively responding.")
                print(f"🤖 LLM Test Reply: {msg.strip()}")
            except (KeyError, IndexError, requests.exceptions.JSONDecodeError) as e:
                print(f"❌ ERROR: Received 200 but unexpected response format: {e}")
        elif response.status_code in [401, 403]:
            print("❌ ERROR 401/403: OpenRouter API Key is invalid or unauthorized.")
        else:
            print(f"❌ ERROR {response.status_code}: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Fatal Network Error connecting to OpenRouter: {e}")

if __name__ == "__main__":
    # Load keys
    load_dotenv()
    
    print("\n🚀 STARTING API CONNECTION TESTS\n")
    test_github()
    test_openrouter()
    print("\n🏁 TESTS COMPLETE\n")
