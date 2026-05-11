from pypdf import PdfReader
import requests
from bs4 import BeautifulSoup
import nltk
import re
from urllib.parse import urlparse

nltk.download("punkt", quiet=True)
nltk.download("punkt_tab", quiet=True)
from nltk.tokenize import sent_tokenize


def normalize_url(url: str) -> str:
    url = url.strip()
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "http://" + url
    return url


def chunk_text(text, chunk_size=500):
    sentences = sent_tokenize(text)

    chunks = []
    current_chunk = ""

    for sentence in sentences:
        if len(current_chunk) + len(sentence) < chunk_size:
            current_chunk += " " + sentence
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence

    if current_chunk:
        chunks.append(current_chunk.strip())

    return chunks


def read_pdf(file):
    reader = PdfReader(file)
    text = ""

    for page in reader.pages:
        text += page.extract_text() or ""

    return text


def read_url(url):
    """Enhanced URL scraper with better content extraction."""
    url = normalize_url(url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }
    
    try:
        res = requests.get(url, headers=headers, timeout=15)
        res.raise_for_status()
    except requests.RequestException as e:
        return f"Failed to fetch URL: {str(e)}"
    
    soup = BeautifulSoup(res.text, "html.parser")

    # Remove noise elements
    noise_tags = [
        "script", "style", "nav", "footer", "header", "aside",
        "form", "iframe", "noscript", "svg", "button",
        "meta", "link"
    ]
    for tag in soup(noise_tags):
        tag.decompose()
    
    # Remove hidden elements
    for tag in soup.find_all(attrs={"style": re.compile(r"display\s*:\s*none")}):
        tag.decompose()
    for tag in soup.find_all(attrs={"hidden": True}):
        tag.decompose()

    # Extract structured content
    parts = []
    
    # Get page title
    title = soup.find("title")
    if title and title.string:
        parts.append(f"Page Title: {title.string.strip()}")
    
    # Get meta description
    meta_desc = soup.find("meta", attrs={"name": "description"})
    if meta_desc and meta_desc.get("content"):
        parts.append(f"Description: {meta_desc['content'].strip()}")
    
    # Extract headings and their content
    main_content = soup.find("main") or soup.find("article") or soup.find("body")
    
    if main_content:
        for element in main_content.find_all(["h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "span", "div", "blockquote"]):
            text = element.get_text(separator=" ", strip=True)
            if text and len(text) > 10:
                if element.name in ["h1", "h2", "h3", "h4", "h5", "h6"]:
                    parts.append(f"\n{element.name.upper()}: {text}")
                else:
                    parts.append(text)
    
    # Deduplicate while preserving order
    seen = set()
    unique_parts = []
    for p in parts:
        normalized = p.strip().lower()
        if normalized not in seen:
            seen.add(normalized)
            unique_parts.append(p)
    
    result = "\n".join(unique_parts)
    
    # Fallback if structured extraction yielded little
    if len(result.strip()) < 100:
        result = soup.get_text(separator=" ", strip=True)
    
    # Clean up whitespace
    result = re.sub(r'\n{3,}', '\n\n', result)
    result = re.sub(r' {2,}', ' ', result)
    
    return result