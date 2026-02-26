import requests
from duckduckgo_search import DDGS
from bs4 import BeautifulSoup
import re
import json
import os

# VRGL (Ollama) configuration for summarization
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.2")

def clean_text(text: str) -> str:
    """Clean extracted text from HTML."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove non-printable characters
    text = re.sub(r'[^\x20-\x7E\n]', '', text)
    return text.strip()

def fetch_webpage_content(url: str, max_length: int = 5000) -> str:
    """Fetch and extract text content from a webpage."""
    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        response = requests.get(url, headers=headers, timeout=10)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        # Remove script and style elements
        for script in soup(["script", "style"]):
            script.extract()
        text = soup.get_text()
        cleaned = clean_text(text)
        return cleaned[:max_length]  # Limit content length
    except Exception as e:
        return f"Error fetching {url}: {str(e)}"

def search_and_retrieve(query: str, num_results: int = 3) -> list:
    """Search the web and retrieve content from top results."""
    results = []
    try:
        with DDGS() as ddgs:
            search_results = list(ddgs.text(query, max_results=num_results))
        for result in search_results:
            url = result['href']
            content = fetch_webpage_content(url)
            if content and not content.startswith("Error"):
                results.append({
                    'url': url,
                    'content': content
                })
    except Exception as e:
        results.append({'error': f"Search failed: {str(e)}"})
    return results

def summarize_with_vrgl(content: str, query: str) -> str:
    """Use VRGL (Ollama) to summarize the content based on the query."""
    prompt = f"Based on the following information, answer the query: '{query}'\n\nContent:\n{content}\n\nProvide a concise summary or answer."
    try:
        payload = {
            "model": OLLAMA_MODEL,
            "prompt": prompt,
            "stream": False
        }
        response = requests.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        return data.get("response", "No summary available.")
    except Exception as e:
        return f"Error summarizing with VRGL: {str(e)}"

def web_search_answer(query: str, use_vrgl: bool = True) -> str:
    """Main function: Search web, retrieve content, and optionally summarize with VRGL."""
    print(f"Searching for: {query}")
    results = search_and_retrieve(query)
    if not results or 'error' in results[0]:
        return "Unable to retrieve information from the web."

    # Combine content from top results
    combined_content = "\n\n".join([r.get('content', '') for r in results if 'content' in r])

    if use_vrgl:
        summary = summarize_with_vrgl(combined_content, query)
        return f"Web search summary: {summary}"
    else:
        # Return raw combined content
        return f"Retrieved information:\n{combined_content[:2000]}..."