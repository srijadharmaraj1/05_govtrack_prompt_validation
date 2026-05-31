from __future__ import annotations
from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field, validator

VALID_ROLES = {
    "collector": "District Collector",
    "superintendent": "Superintendent of Police",
    "sp": "Superintendent of Police",
    "mla": "MLA",
    "mp": "MP",
    "member of parliament": "MP",
    "cabinet minister": "Cabinet Minister",
    "chief minister": "Chief Minister",
    "ias": "IAS Officer",
    "ips": "IPS Officer",
}


class GovTrackProfile(BaseModel):
    query: str
    name: Optional[str] = None
    role: Optional[str] = None
    cadre: Optional[str] = None
    batch_year: Optional[str] = None
    district: Optional[str] = None
    state: Literal["Tamil Nadu"] = "Tamil Nadu"
    department: Optional[str] = None
    party: Optional[str] = None
    office_phone: Optional[str] = None
    email: Optional[str] = None
    posted_since: Optional[str] = None
    additional_info: Optional[str] = None
    sources: List[str] = Field(default_factory=list)
    source_titles: List[str] = Field(default_factory=list)
    raw_snippets: List[str] = Field(default_factory=list)
    model_used: str
    fetched_at: str = Field(default_factory=lambda: datetime.now().isoformat())
    verified: bool = True
    bookmarked: bool = False
    flagged: bool = False
    note: str = ""

    @validator("role", pre=True, always=True)
    def normalize_role(cls, value):
        if value is None:
            return "Other"
        text = str(value).strip()
        lower = text.lower()
        for token, normalized in VALID_ROLES.items():
            if token in lower:
                return normalized
        return text

    @validator("batch_year", pre=True)
    def normalize_batch_year(cls, value):
        if value is None or str(value).strip() == "":
            return None
        return str(value).strip()

    @validator("office_phone", "email", "posted_since", "additional_info", pre=True)
    def normalize_optional_string(cls, value):
        if value is None:
            return None
        text = str(value).strip()
        return text if text else None
