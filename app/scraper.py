import os
import re
from urllib.parse import urljoin
import httpx
from bs4 import BeautifulSoup

TIMEOUT = float(os.getenv("REQUEST_TIMEOUT_SECONDS", "20"))
MAX_CONTENT = int(os.getenv("MAX_CONTENT_CHARS", "24000"))


def _emails(text: str) -> list[str]:
    found = re.findall(r"[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}", text, re.I)
    return sorted({x.lower() for x in found if not x.lower().endswith((".png", ".jpg", ".webp"))})[:5]


async def scrape(url: str) -> dict:
    key = os.getenv("FIRECRAWL_API_KEY", "").strip()
    if key:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            response = await client.post(
                "https://api.firecrawl.dev/v2/scrape",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={"url": url, "formats": ["markdown", "html"]},
            )
            response.raise_for_status()
            payload = response.json()
            data = payload.get("data", payload)
            markdown = data.get("markdown") or ""
            html = data.get("html") or ""
            metadata = data.get("metadata") or {}
            soup = BeautifulSoup(html, "html.parser") if html else BeautifulSoup("", "html.parser")
            title = metadata.get("title") or (soup.title.get_text(" ", strip=True) if soup.title else "")
            description = metadata.get("description") or ""
            text = markdown or soup.get_text(" ", strip=True)
            return {"url": url, "title": title, "meta_description": description,
                    "text": text[:MAX_CONTENT], "emails": _emails(text), "method": "firecrawl"}

    headers = {"User-Agent": "BusinessDataEnrichmentBot/1.0 (respectful public-page extraction)"}
    async with httpx.AsyncClient(timeout=TIMEOUT, follow_redirects=False, headers=headers) as client:
        response = await client.get(url)
        if 300 <= response.status_code < 400:
            raise ValueError("Website redirected. Provide the final canonical URL directly for this MVP.")
        response.raise_for_status()
        content_type = response.headers.get("content-type", "").lower()
        if "text/html" not in content_type and "application/xhtml" not in content_type:
            raise ValueError(f"Unsupported content type: {content_type or 'unknown'}")
        soup = BeautifulSoup(response.text, "html.parser")
        for node in soup(["script", "style", "noscript", "svg"]):
            node.decompose()
        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        desc_tag = soup.find("meta", attrs={"name": re.compile("description", re.I)})
        description = desc_tag.get("content", "").strip() if desc_tag else ""
        text = soup.get_text(" ", strip=True)
        # Avoid following links automatically in MVP; preserve the homepage as source.
        return {"url": str(response.url), "title": title, "meta_description": description,
                "text": text[:MAX_CONTENT], "emails": _emails(text), "method": "requests+beautifulsoup"}
