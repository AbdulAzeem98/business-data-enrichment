import os
import secrets
from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import JSONResponse
from dotenv import load_dotenv

load_dotenv()

from .schemas import ProcessRequest, NormalizeRequest
from .cleaning import clean_text, normalize_public_url, company_key, now_iso, classify
from .scraper import scrape
from .extractor import extract
app = FastAPI(title="Business Data Enrichment API", version="1.0.0", description="Python API for n8n company scraping and CRM data preparation")


def authorize(authorization: str | None):
    expected = os.getenv("API_TOKEN", "").strip()
    if not expected:
        return  # local development only; set API_TOKEN before exposing the service
    supplied = (authorization or "").removeprefix("Bearer ").strip()
    if not secrets.compare_digest(supplied, expected):
        raise HTTPException(status_code=401, detail="Invalid or missing bearer token")


@app.get("/health")
def health():
    return {"status": "ok", "service": "business-data-enrichment", "version": "1.0.0"}


@app.post("/process")
async def process_company(request: ProcessRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    try:
        url = normalize_public_url(request.website_url)
        scraped = await scrape(url)
        extracted = await extract(scraped, request.company_name or "", request.classification_criteria)
        website = normalize_public_url(extracted.get("website") or url)
        name = clean_text(extracted.get("company_name") or request.company_name)
        industry = clean_text(extracted.get("industry"))
        description = clean_text(extracted.get("description"))
        services = extracted.get("products_services") or []
        if not isinstance(services, list):
            services = [clean_text(services)] if clean_text(services) else []
        services = [clean_text(x) for x in services if clean_text(x)]
        missing = [field for field, value in {
            "company_name": name, "website": website, "industry": industry, "description": description
        }.items() if not value]
        review = bool(extracted.get("review_required")) or bool(missing)
        classification = clean_text(extracted.get("classification")) or classify(" ".join([name, industry, description, " ".join(services)]), request.classification_criteria)
        record = {
            "company_key": company_key(website),
            "company_name": name,
            "website": website,
            "industry": industry,
            "description": description,
            "products_services": services,
            "location": clean_text(extracted.get("location")),
            "public_contact": clean_text(extracted.get("public_contact")) or ", ".join(scraped.get("emails", [])),
            "source_url": clean_text(extracted.get("source_url")) or scraped.get("url", url),
            "classification": classification,
            "missing_fields": missing,
            "review_status": "Needs Review" if review else "Ready",
            "processing_status": "Review" if review else "Success",
            "last_updated": now_iso(),
            "extraction_method": extracted.get("extraction_method", scraped.get("method", "unknown")),
            "error_message": "",
        }
        return record
    except HTTPException:
        raise
    except Exception as exc:
        # Return an actionable error. n8n should log this and continue with the next company.
        raise HTTPException(status_code=502, detail={"error": str(exc), "website_url": request.website_url}) from exc


@app.post("/normalize")
def normalize_record(request: NormalizeRequest, authorization: str | None = Header(default=None)):
    authorize(authorization)
    data = request.record
    try:
        website = normalize_public_url(clean_text(data.get("website") or data.get("website_url")))
    except ValueError:
        website = ""
    name = clean_text(data.get("company_name"))
    industry = clean_text(data.get("industry"))
    description = clean_text(data.get("description"))
    missing = [k for k, v in {"company_name": name, "website": website, "industry": industry, "description": description}.items() if not v]
    services = data.get("products_services", [])
    if not isinstance(services, list):
        services = [services] if services else []
    criteria = request.classification_criteria or None
    return {
        **data,
        "company_key": company_key(website) if website else "",
        "company_name": name,
        "website": website,
        "industry": industry,
        "description": description,
        "products_services": [clean_text(x) for x in services if clean_text(x)],
        "classification": clean_text(data.get("classification")) or classify(" ".join([name, industry, description]), criteria),
        "missing_fields": missing,
        "review_status": "Needs Review" if missing else "Ready",
        "processing_status": "Review" if missing else "Success",
        "last_updated": now_iso(),
    }


@app.exception_handler(Exception)
async def unhandled_exception_handler(request, exc):
    return JSONResponse(status_code=500, content={"detail": "Internal server error", "type": type(exc).__name__})
