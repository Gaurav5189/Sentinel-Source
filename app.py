import streamlit as st
import time
import os
import requests
from github_fetcher import search_github_repos
from gitlab_fetcher import search_gitlab_repos
from repo_scraper import fetch_readmes_concurrently
from llm_evaluator import evaluate_tools_batch, enhance_query_llm

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
        env_model = os.environ.get("OPENROUTER_MODEL")
        display_model = env_model if env_model else "Model Not Configured"
        
        # Only show the model they have explicitly provided
        selected_model = st.selectbox("Configured LLM Model (.env)", [display_model], index=0)
        
        # We inject this into the environment dynamically so the evaluator grabs it over the .env
        if env_model:
            os.environ["OPENROUTER_MODEL"] = env_model
        
        st.subheader("Search Limits")
        num_gh_repos = st.slider("GitHub Deep Search Limit", min_value=1, max_value=25, value=5)
        num_gl_repos = st.slider("GitLab Deep Search Limit", min_value=1, max_value=25, value=5)
        
        st.divider()
        st.subheader("Health Checks")
        
        # 1. OpenRouter Integration Health Check
        if st.button("🔌 Check LLM Connection"):
            api_key = os.environ.get("OPENROUTER_API_KEY")
            if not api_key:
                st.error("Missing OpenRouter API Key in .env!")
            else:
                try:
                    res = requests.post(
                        "https://openrouter.ai/api/v1/chat/completions",
                        headers={"Authorization": f"Bearer {api_key}"},
                        json={"model": selected_model, "messages": [{"role": "user", "content": "ping"}]},
                        timeout=10
                    )
                    if res.status_code == 200:
                        st.success(f"✅ Connection Successful!\nModel ({selected_model}) is active.")
                    else:
                        st.error(f"❌ Error {res.status_code}: Model Unavailable.")
                except Exception as e:
                    st.error(f"❌ Connection Failed: {e}")
                    
        # 2. GitHub Integration Health Check
        if st.button("🔌 Check GitHub API"):
            github_token = os.environ.get("GITHUB_TOKEN")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if github_token:
                headers["Authorization"] = f"Bearer {github_token}"
            try:
                res = requests.get("https://api.github.com/user", headers=headers, timeout=10)
                if res.status_code == 200:
                    st.success(f"✅ GitHub Valid! (Authenticated User: {res.json().get('login')})")
                elif res.status_code == 401:
                    st.error("❌ GitHub Token Invalid (401).")
                else:
                    st.warning("⚠️ No Token Configured. Using limited anonymous bandwidth.")
            except Exception as e:
                st.error(f"❌ Connection Failed: {e}")

        # 3. GitLab Integration Health Check
        if st.button("🔌 Check GitLab API"):
            gitlab_token = os.environ.get("GITLAB_TOKEN")
            headers = {}
            if gitlab_token:
                headers["PRIVATE-TOKEN"] = gitlab_token
            try:
                res = requests.get("https://gitlab.com/api/v4/projects?per_page=1", headers=headers, timeout=10)
                if res.status_code == 200:
                    st.success("✅ GitLab Local Connection is Valid!")
                    if gitlab_token:
                        st.info("🔐 Authenticated PAT link established.")
                    else:
                        st.warning("⚠️ No Token Configured. Using limited anonymous bandwidth.")
                elif res.status_code == 401:
                    st.error("❌ GitLab Token Invalid (401).")
                else:
                    st.error(f"❌ GitLab Rejection {res.status_code}: {res.text}")
            except Exception as e:
                st.error(f"❌ Connection Failed: {e}")

    # ---------------------------
    # MAIN APPLICATION UI
    # ---------------------------
    col1, col2 = st.columns([1, 10])
    with col1:
        st.markdown("<h1 style='text-align: center;'>🛡️</h1>", unsafe_allow_html=True)
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
        st.markdown("<div style='margin-top: 28px;'></div>", unsafe_allow_html=True)
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

    # Keep query variable pointing to the text box output so Run Pipeline behaves normally
    query = query_val

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
            st.write(f"🔍 Searching GitHub (Limit: {num_gh_repos}) and GitLab (Limit: {num_gl_repos})...")
            
            gh_repos = search_github_repos(query, max_results=num_gh_repos)
            gl_repos = search_gitlab_repos(query, max_results=num_gl_repos)
            
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

        # Cap the final UI output to the absolute top 6 results
        sorted_repos = sorted(evaluated_repos, key=get_score, reverse=True)[:6]
        legit_count = sum(1 for r in sorted_repos if r.get('is_legit'))
        
        # Metrics Dashboard
        c1, c2, c3 = st.columns(3)
        c1.metric("Search Query", query)
        c2.metric("Best Repos Extracted", len(sorted_repos))
        c3.metric("Legitimate Tools Filtered", legit_count)
        
        st.divider()
        
        # Build raw text report for download
        report_lines = [f"🛡️ PENTEST TOOL ANALYZER REPORT"]
        report_lines.append(f"Query: '{query}' | Total Finalists: {len(sorted_repos)} | Legitimate: {legit_count}\n")
        report_lines.append("=" * 60 + "\n")
        
        for repo in sorted_repos:
            r_name = repo.get("name", "Unknown")
            r_score = repo.get("score", 0)
            r_legit = "Yes" if repo.get("is_legit", False) else "No"
            r_url = repo.get("html_url", "#")
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
            st.subheader("Top 6 Investigation Summary")
        with colB:
            st.download_button(
                label="📥 Download Report (.txt)",
                data=report_text,
                file_name=f"pentest_eval_{query.replace(' ', '_')}.txt",
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
            
            with st.expander(f"{status_color} {repo_name} | {platform_badge} | AI Score: {score}/10"):
                st.markdown(f"**🔗 Source URL:** [{html_url}]({html_url})")
                st.markdown(f"**🛡️ Is Legitimate:** {'Yes' if is_legit else 'No'}")
                st.markdown(f"**📝 AI Analysis:** {analysis}")

if __name__ == "__main__":
    main()
