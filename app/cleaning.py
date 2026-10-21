from datetime import datetime, timezone
from urllib.parse import urlparse, urlunparse
import ipaddress
import socket
import re


def clean_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, list):
        value = ", ".join(str(x) for x in value if x is not None)
    return re.sub(r"\s+", " ", str(value)).strip()


def normalize_public_url(value: str) -> str:
    """Normalize a URL and reject non-public destinations to reduce SSRF risk."""
    raw = clean_text(value)
    if not raw:
        raise ValueError("website_url is required")
    if not re.match(r"^https?://", raw, re.I):
        raw = "https://" + raw
    parsed = urlparse(raw)
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only valid http/https website URLs are accepted")
    if parsed.username or parsed.password:
        raise ValueError("URLs containing embedded credentials are not accepted")
    host = parsed.hostname.lower().rstrip(".")
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("Private/local destinations are not allowed")
    try:
        addresses = {ipaddress.ip_address(host)}
    except ValueError:
        try:
            addresses = {ipaddress.ip_address(info[4][0]) for info in socket.getaddrinfo(host, None)}
        except socket.gaierror:
            # Let the HTTP client provide the final DNS error.
            addresses = set()
    for address in addresses:
        if not address.is_global:
            raise ValueError("Private, loopback, or non-public IP destinations are not allowed")
    netloc = host
    if parsed.port and not ((parsed.scheme == "http" and parsed.port == 80) or (parsed.scheme == "https" and parsed.port == 443)):
        netloc = f"{host}:{parsed.port}"
    path = parsed.path.rstrip("/")
    return urlunparse((parsed.scheme.lower(), netloc, path, "", parsed.query, ""))


def company_key(website: str) -> str:
    host = urlparse(website).hostname or ""
    return host.lower().removeprefix("www.")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def classify(text: str, criteria: list[str] | None = None) -> str:
    criteria = criteria or ["Software & IT", "Manufacturing", "Healthcare", "Financial Services", "Education", "Retail & E-commerce", "Professional Services", "Other"]
    corpus = text.lower()
    keyword_map = {
        "Software & IT": ["software", "saas", "cloud", "developer", "technology", "cybersecurity", "data analytics", "it services", "artificial intelligence", " ai "],
        "Manufacturing": ["manufacturing", "factory", "industrial", "production", "machinery", "components"],
        "Healthcare": ["healthcare", "medical", "clinic", "hospital", "pharma", "biotech"],
        "Financial Services": ["banking", "insurance", "fintech", "financial services", "investment", "payments"],
        "Education": ["education", "university", "school", "training", "learning", "edtech"],
        "Retail & E-commerce": ["e-commerce", "ecommerce", "retail", "online store", "marketplace", "consumer products"],
        "Professional Services": ["consulting", "legal services", "accounting", "marketing agency", "recruitment", "professional services"],
    }
    scores = {}
    for category in criteria:
        if category == "Other":
            continue
        words = keyword_map.get(category, [category.lower()])
        scores[category] = sum(corpus.count(word) for word in words)
    if not scores or max(scores.values(), default=0) == 0:
        return "Other" if "Other" in criteria else criteria[-1]
    return max(scores, key=scores.get)
