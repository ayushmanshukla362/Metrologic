from typing import Any, List, Optional

from pydantic import BaseModel, Field


class ExtractedField(BaseModel):
    """A backend-owned representation of one AI-extracted package field."""

    field_key: str
    value: Optional[Any] = None
    unit: Optional[str] = None
    inclusive_of_taxes: Optional[bool] = None
    raw_source: str = ""
    source_block_ids: List[str] = Field(default_factory=list)
    confidence: float = 0.0


class PackageData(BaseModel):
    session_id: str
    commodity_name: Optional[ExtractedField] = None
    net_quantity: Optional[ExtractedField] = None
    mfg_date: Optional[ExtractedField] = None
    mrp: Optional[ExtractedField] = None
    manufacturer: Optional[ExtractedField] = None
    is_food_product: Optional[bool] = None


class RuleResult(BaseModel):
    rule_id: str
    requirement: str
    status: str  # PASS, FAIL, or REVIEW_REQUIRED
    reason: str
    evidence: List[str] = Field(default_factory=list)
