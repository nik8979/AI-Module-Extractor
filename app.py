import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from urllib.parse import urljoin, urlparse
import json
import time

# ---------------- PAGE CONFIG ----------------
st.set_page_config(
    page_title="AI Module Extractor",
    page_icon="🔍",
    layout="wide"
)

# ---------------- API KEY ----------------
API_KEY = "AIzaSyDIlSoS0qkeYBFUyWsedmgnAlC9aXkpGU4"  # 🔒 keep safe

# ---------------- SIDEBAR ----------------
with st.sidebar:
    st.title("⚙️ Settings")
    st.info("The agent will crawl up to **5 pages** from the same domain.")

# ---------------- CRAWLER UTILS ----------------
def is_valid_subpage(url, base_url):
    """Check if a URL is valid for crawling (same domain, not a file)."""
    base_domain = urlparse(base_url).netloc
    target_domain = urlparse(url).netloc
    return (
        base_domain == target_domain and
        not any(url.lower().endswith(ext) for ext in ['.pdf', '.jpg', '.png', '.zip'])
    )

def clean_text(html):
    """Extract and clean text from HTML."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    return " ".join(soup.get_text().split())

def crawl_site(start_url, max_pages=5):
    """
    Crawl the documentation site and return list of text content.
    """
    visited = set()
    queue = [start_url]
    content = []

    progress = st.progress(0)
    status = st.empty()

    while queue and len(visited) < max_pages:
        url = queue.pop(0)
        if url in visited:
            continue

        try:
            status.text(f"🕷️ Crawling: {url}")
            r = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            if r.status_code != 200:
                st.warning(f"⚠️ Failed to access {url} (Status {r.status_code})")
                continue

            visited.add(url)
            content.append(f"SOURCE: {url}\nCONTENT: {clean_text(r.text)}")

            soup = BeautifulSoup(r.text, "html.parser")
            for link in soup.find_all("a", href=True):
                full_url = urljoin(url, link["href"])
                if is_valid_subpage(full_url, start_url) and full_url not in visited:
                    queue.append(full_url)

            progress.progress(len(visited) / max_pages)
            time.sleep(1)

        except Exception as e:
            st.warning(f"⚠️ Error crawling {url}: {e}")

    return content

# ---------------- AI EXTRACTION ----------------
def extract_hierarchy(content_list, target_url):
    """
    Extract product/module/submodule hierarchy using Google Gemini AI.
    """
    genai.configure(api_key=API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    full_text = "\n\n".join(content_list)[:30000]

    prompt = f"""
You are an expert product analyst.

Analyze documentation from: {target_url}

Return ONLY valid JSON:
{{
  "product": "Product name",
  "overview": "Short overview",
  "modules": [
    {{
      "module_name": "Module name",
      "purpose": "Why it exists",
      "submodules": [
        {{
          "name": "Feature name",
          "details": "What it does"
        }}
      ]
    }}
  ]
}}

DOCUMENTATION:
{full_text}
"""

    response = model.generate_content(prompt)
    clean_json = response.text.replace("```json", "").replace("```", "").strip()

    try:
        return json.loads(clean_json)
    except json.JSONDecodeError:
        st.error("❌ Failed to parse JSON from AI response.")
        return {}

# ---------------- UI RENDER ----------------
def render_modules_ui(data):
    """Render extracted product modules and submodules in Streamlit UI."""
    st.subheader(f"📦 {data.get('product', 'Product')}")
    st.markdown(f"📝 **Overview:** {data.get('overview', '')}")
    st.divider()

    for i, module in enumerate(data.get("modules", []), start=1):
        with st.expander(f"🧩 Module {i}: {module['module_name']}"):
            st.markdown(f"**Purpose:** {module.get('purpose', '')}")
            st.markdown("### 🔹 Features")

            for sub in module.get("submodules", []):
                st.markdown(
                    f"""
                    <div style="
                        padding:14px;
                        border-radius:12px;
                        background:#0e1117;
                        border:1px solid #262730;
                        margin-bottom:12px;
                    ">
                        <h4 style="margin:0;">✨ {sub['name']}</h4>
                        <p style="margin-top:6px; color:#cfcfcf;">
                            {sub['details']}
                        </p>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

# ---------------- MAIN ----------------
st.title("📘 AI Agent: Module Extraction")
st.markdown("Enter a documentation URL. The agent will analyze and extract product modules.")

doc_url = st.text_input(
    "Documentation URL",
    placeholder="https://help.instagram.com"
)

if st.button("🚀 Start Extraction"):
    if not doc_url:
        st.error("Please provide a URL.")
    else:
        st.info("🕷️ Crawling documentation pages...")
        pages = crawl_site(doc_url)

        if pages:
            st.info("🧠 Extracting product structure from crawled content...")
            result = extract_hierarchy(pages, doc_url)

            if result:
                st.success("✅ Extraction completed successfully!")
                render_modules_ui(result)

                st.download_button(
                    "📥 Download JSON",
                    data=json.dumps(result, indent=2),
                    file_name="modules.json",
                    mime="application/json"
                )
            else:
                st.error("❌ AI failed to generate structured output.")
        else:
            st.error("❌ No content could be crawled from the URL.")
