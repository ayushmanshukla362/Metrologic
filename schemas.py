from pydantic import BaseModel
from typing import Optional

# Ek field ka data kaisa dikhega
class ExtractedField(BaseModel):
    field_key: str
    value: Optional[str] = None
    unit: Optional[str] = None
    confidence: float

# Pure package ka data
class PackageData(BaseModel):
    session_id: str
    mrp: Optional[ExtractedField] = None
    net_quantity: Optional[ExtractedField] = None

# Rule check ka final result
class RuleResult(BaseModel):
    rule_id: str
    requirement: str
    status: str  # PASS, FAIL, ya REVIEW_REQUIRED
    reason: str