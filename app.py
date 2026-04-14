import streamlit as st
import time
import concurrent.futures
import requests
from config import (
    OPENROUTER_API_KEY, OPENROUTER_MODEL, OPENROUTER_BASE_URL,
    GITHUB_TOKEN, GITLAB_TOKEN, GITHUB_API_URL, GITLAB_API_URL,
    DEFAULT_TIMEOUT, TOP_RESULTS_DISPLAY,
    sanitize_query, sanitize_filename, get_logger
)
from github_fetcher import search_github_repos
from gitlab_fetcher import search_gitlab_repos
from repo_scraper import fetch_readmes_concurrently
from llm_evaluator import evaluate_tools_batch, enhance_query_llm

logger = get_logger(__name__)

# Standard UI Styling
st.set_page_config(
    page_title="Pentest Tool Analyzer",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded"
)

def deduplicate_repos(repos: list[dict]) -> list[dict]:
    """
    Remove mirror clones or forks across platforms by tracking raw repo names to 
    prevent the LLM from analyzing the exact same tool twice.
    """
    seen_names = set()
    cleaned = []
    for r in repos:
        name = str(r.get("name", "")).strip().lower()
        if name and name not in seen_names:
            seen_names.add(name)
            cleaned.append(r)
    return cleaned

def main():
    # ---------------------------
    # SIDEBAR SETUP
    # ---------------------------
    with st.sidebar:
        st.title("🛡️ Pentest Analyzer")
        st.markdown("AI-Powered OSINT Tool")
        
        st.subheader("Settings")
        
        # Fetch the exact model specified in the user's .env file
        env_model = OPENROUTER_MODEL
        display_model = env_model if env_model else "Model Not Configured"
        
        # Only show the model they have explicitly provided
        selected_model = st.selectbox("Configured LLM Model (.env)", [display_model], index=0)
        
        st.subheader("Platform Toggles")
        use_github = st.toggle("Enable GitHub Search", value=True)
        use_gitlab = st.toggle("Enable GitLab Search", value=True)
        
        st.subheader("Search Limits")
        num_gh_repos = st.slider("GitHub Deep Search Limit", min_value=1, max_value=25, value=5) if use_github else 0
        num_gl_repos = st.slider("GitLab Deep Search Limit", min_value=1, max_value=25, value=5) if use_gitlab else 0
        
        st.subheader("Output Settings")
        max_ui_results = st.slider("Final Output Scope", min_value=5, max_value=15, value=6)
        
        st.divider()
        st.subheader("Health Checks")
        
        # 1. OpenRouter Integration Health Check (uses lightweight models endpoint)
        if st.button("🔌 Check LLM Connection"):
            if not OPENROUTER_API_KEY:
                st.error("Missing OpenRouter API Key in .env!")
            else:
                try:
                    res = requests.get(
                        f"{OPENROUTER_BASE_URL}/models",
                        headers={"Authorization": f"Bearer {OPENROUTER_API_KEY}"},
                        timeout=DEFAULT_TIMEOUT
                    )
                    if res.status_code == 200:
                        st.success(f"✅ Connection Successful!\nModel ({selected_model}) is configured.")
                    else:
                        st.error(f"❌ Error {res.status_code}: API Unavailable.")
                except Exception as e:
                    st.error(f"❌ Connection Failed: {e}")
                    
        # 2. GitHub Integration Health Check
        if st.button("🔌 Check GitHub API"):
            headers = {"Accept": "application/vnd.github.v3+json"}
            try:
                if not GITHUB_TOKEN:
                    # Use rate_limit endpoint for anonymous check
                    res = requests.get(f"{GITHUB_API_URL}/rate_limit", headers=headers, timeout=DEFAULT_TIMEOUT)
                    if res.status_code == 200:
                        st.warning("⚠️ No Token Configured. Using limited anonymous bandwidth.")
                    else:
                        st.error(f"❌ GitHub API Error: {res.status_code}")
                else:
                    headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
                    res = requests.get(f"{GITHUB_API_URL}/user", headers=headers, timeout=DEFAULT_TIMEOUT)
                    if res.status_code == 200:
                        st.success(f"✅ GitHub Valid! (Authenticated User: {res.json().get('login')})")
                    elif res.status_code == 401:
                        st.error("❌ GitHub Token Invalid (401).")
                    else:
                        st.error(f"❌ GitHub API Error: {res.status_code}")
            except Exception as e:
                st.error(f"❌ Connection Failed: {e}")

        # 3. GitLab Integration Health Check
        if st.button("🔌 Check GitLab API"):
            headers = {}
            if GITLAB_TOKEN:
                headers["PRIVATE-TOKEN"] = GITLAB_TOKEN
            try:
                res = requests.get(f"{GITLAB_API_URL}/projects?per_page=1", headers=headers, timeout=DEFAULT_TIMEOUT)
                if res.status_code == 200:
                    st.success("✅ GitLab Local Connection is Valid!")
                    if GITLAB_TOKEN:
                        st.info("🔐 Authenticated PAT link established.")
                    else:
                        st.warning("⚠️ No Token Configured. Using limited anonymous bandwidth.")
                elif res.status_code == 401:
                    st.error("❌ GitLab Token Invalid (401).")
                else:
                    st.error(f"❌ GitLab Rejection {res.status_code}")
            except Exception as e:
                st.error(f"❌ Connection Failed: {e}")

    # ---------------------------
    # MAIN APPLICATION UI
    # ---------------------------
    col1, col2 = st.columns([1, 10])
    with col1:
        st.header("🛡️")
    with col2:
        st.title("Pentest Tool Analyzer")
        
    st.markdown("Search GitHub **and GitLab** for pentesting tools and let AI evaluate their validity and safety in parallel. *Powered by OpenRouter.*")

    # Native integration to forcefully capture and sync Streamlit state
    if "search_query" not in st.session_state:
        st.session_state.search_query = ""

    # Input Row
    colL, colR = st.columns([4, 1])
    
    with colL:
        # Manual state tracking prevents the strict Streamlit Widget Key mutation error
        query_val = st.text_input(
            "Enter Search Query:", 
            value=st.session_state.search_query,
            placeholder="e.g., 'subdomain scanner', 'ransomware osint'"
        )
        
    with colR:
        # UI Spacing to align with the text_input perfectly
        st.markdown("")
        if st.button("✨ Enhance Query", use_container_width=True):
            if not env_model:
                st.error("Model Not Configured!")
            elif not query_val.strip():
                st.warning("Type a query first!")
            else:
                with st.spinner("🤖 Aligning context specifically to Pentesting..."):
                    enhanced_query = enhance_query_llm(query_val)
                    
                    if enhanced_query != query_val:
                        st.session_state.search_query = enhanced_query
                        st.rerun()

    # Track manual typing
    if query_val != st.session_state.search_query:
        st.session_state.search_query = query_val

    # Sanitize input: enforce max length, strip control characters (SEC-03)
    query = sanitize_query(query_val)

    if st.button("🚀 Run Pipeline", type="primary"):
        if not env_model:
             st.error("Model Not Configured! Please specify OPENROUTER_MODEL in your .env file.")
             st.stop()
             
        if not query.strip():
             st.warning("Please enter a valid search query.")
             st.stop()
             
        start_time = time.time()
        
        # Transparent Processing
        with st.status("Executing Multi-Stage OSINT Pipeline...", expanded=True) as status:
            if not use_github and not use_gitlab:
                status.update(label="Pipeline failed: Choose at least one search platform.", state="error")
                st.stop()
                
            st.write(f"🔍 Initializing Platform Searches... GitHub ({'On' if use_github else 'Off'}) | GitLab ({'On' if use_gitlab else 'Off'})")
            
            gh_repos, gl_repos = [], []
            # PERF-02: Run GitHub and GitLab searches in parallel conditionally
            with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
                gh_future = executor.submit(search_github_repos, query, num_gh_repos) if use_github else None
                gl_future = executor.submit(search_gitlab_repos, query, num_gl_repos) if use_gitlab else None
                
                if gh_future: gh_repos = gh_future.result()
                if gl_future: gl_repos = gl_future.result()
            
            combined_repos = gh_repos + gl_repos
            if not combined_repos:
                status.update(label="Pipeline failed: No repositories found on either platform.", state="error")
                st.stop()
            
            # Filter identical repositories mirrored across platforms
            combined_repos = deduplicate_repos(combined_repos)
            
            st.write(f"✅ Found {len(combined_repos)} unique repositories. Scraping raw README contexts concurrently...")
            repos_with_readmes = fetch_readmes_concurrently(combined_repos)
            
            st.write("🧠 Forwarding heavily batched repository snapshot to LLM for joint evaluation...")
            evaluated_repos = evaluate_tools_batch(repos_with_readmes)
            
            elapsed = time.time() - start_time
            status.update(label=f"Pipeline completed successfully in {elapsed:.2f} seconds!", state="complete", expanded=False)

        # Sort results logically by LLM score
        def get_score(r):
            s = r.get("score", 0)
            return s if isinstance(s, int) else 0

        # Cap the final UI output to the dynamically selected top results scope
        sorted_repos = sorted(evaluated_repos, key=get_score, reverse=True)[:max_ui_results]
        
        # Save explicitly into Session State so downloads don't wipe the dashboard!
        st.session_state.last_results = sorted_repos
        st.session_state.last_query = query
        
    # ------------- RENDER RESULTS IMMUNIZED AGAINST DOWNLOAD RERUNS -------------
    if "last_results" in st.session_state and st.session_state.last_results:
        sorted_repos = st.session_state.last_results
        query_executed = st.session_state.last_query
        
        legit_count = sum(1 for r in sorted_repos if r.get('is_legit'))
        
        # Metrics Dashboard
        c1, c2, c3 = st.columns(3)
        c1.metric("Search Query", query_executed)
        c2.metric("Best Repos Extracted", len(sorted_repos))
        c3.metric("Legitimate Tools Filtered", legit_count)
        
        st.divider()
        
        # Build raw text report for download
        report_lines = [f"🛡️ PENTEST TOOL ANALYZER REPORT"]
        report_lines.append(f"Query: '{query_executed}' | Total Finalists: {len(sorted_repos)} | Legitimate: {legit_count}\n")
        report_lines.append("=" * 60 + "\n")
        
        for repo in sorted_repos:
            r_name = repo.get("name", "Unknown")
            r_score = repo.get("score", 0)
            r_legit = "Yes" if repo.get("is_legit", False) else "No"
            raw_url = repo.get("html_url", "#")
            r_url = raw_url if raw_url.startswith(("https://github.com/", "https://gitlab.com/")) else "[URL Sanitized]"
            r_Platform = "GitLab" if repo.get("is_gitlab") else "GitHub"
            r_analysis = repo.get("analysis", "No analysis.")
            
            report_lines.append(f"Name   : {r_name} (Platform: {r_Platform}, Score: {r_score}/10)")
            report_lines.append(f"URL    : {r_url}")
            report_lines.append(f"Status : Legitimate: {r_legit}")
            report_lines.append(f"Analysis: {r_analysis}")
            report_lines.append("-" * 60 + "\n")
            
        report_text = "\n".join(report_lines)

        colA, colB = st.columns([3, 1])
        with colA:
            st.subheader(f"Top {len(sorted_repos)} Investigation Summary")
        with colB:
            # CQ-07: Sanitize filename to prevent path injection
            safe_filename = sanitize_filename(query_executed)
            st.download_button(
                label="📥 Download Report (.txt)",
                data=report_text,
                file_name=f"pentest_eval_{safe_filename}.txt",
                mime="text/plain",
                use_container_width=True
            )

        for repo in sorted_repos:
            repo_name = repo.get("name", "Unknown Repo")
            score = repo.get("score", 0)
            is_legit = repo.get("is_legit", False)
            html_url = repo.get("html_url", "#")
            platform_badge = "🦊 GitLab" if repo.get("is_gitlab") else "🐙 GitHub"
            analysis = repo.get("analysis", "No analysis available.")
            
            status_color = "🟢" if is_legit else "🔴"
            
            # SEC-04: Sanitize URL — only allow https:// github/gitlab URLs in rendered markdown
            safe_url = html_url if html_url.startswith(("https://github.com/", "https://gitlab.com/")) else "#"
            
            with st.expander(f"{status_color} {repo_name} | {platform_badge} | AI Score: {score}/10"):
                st.markdown(f"**🔗 Source URL:** [{safe_url}]({safe_url})")
                st.markdown(f"**🛡️ Is Legitimate:** {'Yes' if is_legit else 'No'}")
                st.markdown(f"**📝 AI Analysis:** {analysis}")

if __name__ == "__main__":
    main()
