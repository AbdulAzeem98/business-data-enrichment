from typing import Any
from pydantic import BaseModel, Field, HttpUrl


class ProcessRequest(BaseModel):
    website_url: str = Field(..., description="Public company website URL")
    company_name: str | None = None
    classification_criteria: list[str] = Field(default_factory=lambda: [
        "Software & IT", "Manufacturing", "Healthcare", "Financial Services",
        "Education", "Retail & E-commerce", "Professional Services", "Other"
    ])


class CompanyRecord(BaseModel):
    company_key: str = ""
    company_name: str = ""
    website: str = ""
    industry: str = ""
    description: str = ""
    products_services: list[str] = Field(default_factory=list)
    location: str = ""
    public_contact: str = ""
    source_url: str = ""
    classification: str = "Other"
    missing_fields: list[str] = Field(default_factory=list)
    review_status: str = "Needs Review"
    processing_status: str = "Review"
    last_updated: str = ""
    extraction_method: str = ""
    error_message: str = ""


class NormalizeRequest(BaseModel):
    record: dict[str, Any]
    classification_criteria: list[str] = Field(default_factory=list)
