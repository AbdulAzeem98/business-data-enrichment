import pytest
from app.cleaning import normalize_public_url, company_key, classify, clean_text


def test_normalizes_domain_and_trailing_slash():
    url = normalize_public_url("https://www.example.com/about/")
    assert url == "https://www.example.com/about"
    assert company_key(url) == "example.com"


def test_adds_https():
    assert normalize_public_url("example.com") == "https://example.com"


def test_rejects_localhost():
    with pytest.raises(ValueError):
        normalize_public_url("http://localhost:8000")


def test_cleans_whitespace():
    assert clean_text("  hello\n  world ") == "hello world"


def test_classifies_software():
    assert classify("Cloud software and cybersecurity platform") == "Software & IT"
