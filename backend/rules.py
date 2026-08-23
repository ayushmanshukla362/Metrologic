"""Deterministic MVP rule evaluation for MetroLogic inspections."""

from math import isfinite
from numbers import Number
from typing import Any, TypedDict


class RawFieldData(TypedDict, total=False):
    """A field returned by the AI before deterministic validation."""

    value: Any
    unit: str
    inclusive_of_taxes: bool
    raw_source: str
    source_block_ids: list[str]


class ValidatedFieldData(RawFieldData):
    """A raw field after deterministic confidence scoring."""

    confidence: float


class RawExtractionData(TypedDict, total=False):
    commodity_name: RawFieldData
    net_quantity: RawFieldData
    mfg_date: RawFieldData
    mrp: RawFieldData
    manufacturer: RawFieldData


class ValidatedExtractionData(TypedDict, total=False):
    commodity_name: ValidatedFieldData
    net_quantity: ValidatedFieldData
    mfg_date: ValidatedFieldData
    mrp: ValidatedFieldData
    manufacturer: ValidatedFieldData


PASS = "PASS"
FAIL = "FAIL"
REVIEW_REQUIRED = "REVIEW_REQUIRED"
CONFIDENCE_THRESHOLD = 0.80
SUPPORTED_QUANTITY_UNITS = ["g", "kg", "ml", "l", "N"]
INDIAN_CURRENCY_UNITS = {"inr", "rs", "rs.", "₹", "rupee", "rupees"}


def _evaluation(
    rule_id: str,
    requirement: str,
    status: str,
    reason: str,
    evidence: list[Any],
) -> dict[str, Any]:
    return {
        "rule_id": rule_id,
        "requirement": requirement,
        "status": status,
        "reason": reason,
        "evidence": evidence,
    }


def _evidence(field_data: ValidatedFieldData) -> list[Any]:
    return field_data.get("source_block_ids", [])


def _has_sufficient_confidence(field_data: ValidatedFieldData) -> bool:
    confidence = field_data.get("confidence")
    if isinstance(confidence, bool) or not isinstance(confidence, Number):
        return False
    try:
        confidence_value = float(confidence)
    except (TypeError, ValueError, OverflowError):
        return False
    return isfinite(confidence_value) and confidence_value >= CONFIDENCE_THRESHOLD


def _missing_evidence(field_data: ValidatedFieldData) -> bool:
    return not _evidence(field_data)


def evaluate_commodity_name(field_data: ValidatedFieldData) -> dict[str, Any]:
    """Evaluate Rule 6(1)(b): Generic/Common Commodity Name."""
    evidence = _evidence(field_data)
    if field_data.get("value") is None:
        return _evaluation(
            "LM-PCR-6-1-b",
            "Generic/Common Commodity Name",
            FAIL,
            "Commodity name is missing",
            evidence,
        )
    if not _has_sufficient_confidence(field_data):
        return _evaluation(
            "LM-PCR-6-1-b",
            "Generic/Common Commodity Name",
            REVIEW_REQUIRED,
            "Low extraction confidence",
            evidence,
        )
    if _missing_evidence(field_data):
        return _evaluation(
            "LM-PCR-6-1-b",
            "Generic/Common Commodity Name",
            REVIEW_REQUIRED,
            "Missing bounding box evidence",
            evidence,
        )
    return _evaluation(
        "LM-PCR-6-1-b",
        "Generic/Common Commodity Name",
        PASS,
        "",
        evidence,
    )


def evaluate_net_quantity(field_data: ValidatedFieldData) -> dict[str, Any]:
    """Evaluate Rule 6(1)(c): Net Quantity."""
    evidence = _evidence(field_data)
    if field_data.get("value") is None:
        return _evaluation(
            "LM-PCR-6-1-c",
            "Net Quantity",
            FAIL,
            "Net quantity is missing",
            evidence,
        )
    if not _has_sufficient_confidence(field_data):
        return _evaluation(
            "LM-PCR-6-1-c",
            "Net Quantity",
            REVIEW_REQUIRED,
            "Low extraction confidence",
            evidence,
        )
    if _missing_evidence(field_data):
        return _evaluation(
            "LM-PCR-6-1-c",
            "Net Quantity",
            REVIEW_REQUIRED,
            "Missing bounding box evidence",
            evidence,
        )
    if field_data.get("unit") not in SUPPORTED_QUANTITY_UNITS:
        return _evaluation(
            "LM-PCR-6-1-c",
            "Net Quantity",
            REVIEW_REQUIRED,
            "Unsupported or non-canonical quantity unit",
            evidence,
        )
    return _evaluation("LM-PCR-6-1-c", "Net Quantity", PASS, "", evidence)


def evaluate_manufacturing_date(field_data: ValidatedFieldData) -> dict[str, Any]:
    """Evaluate Rule 6(1)(d): Date of Manufacture."""
    evidence = _evidence(field_data)
    if field_data.get("value") is None:
        return _evaluation(
            "LM-PCR-6-1-d",
            "Date of Manufacture",
            FAIL,
            "Date of manufacture is missing",
            evidence,
        )
    if not _has_sufficient_confidence(field_data):
        return _evaluation(
            "LM-PCR-6-1-d",
            "Date of Manufacture",
            REVIEW_REQUIRED,
            "Low extraction confidence",
            evidence,
        )
    if _missing_evidence(field_data):
        return _evaluation(
            "LM-PCR-6-1-d",
            "Date of Manufacture",
            REVIEW_REQUIRED,
            "Missing bounding box evidence",
            evidence,
        )
    return _evaluation("LM-PCR-6-1-d", "Date of Manufacture", PASS, "", evidence)


def evaluate_mrp(field_data: ValidatedFieldData) -> dict[str, Any]:
    """Evaluate Rule 6(1)(e): Maximum Retail Price (MRP)."""
    evidence = _evidence(field_data)
    if field_data.get("value") is None:
        return _evaluation(
            "LM-PCR-6-1-e",
            "Maximum Retail Price (MRP)",
            FAIL,
            "MRP value is missing",
            evidence,
        )
    if not _has_sufficient_confidence(field_data):
        return _evaluation(
            "LM-PCR-6-1-e",
            "Maximum Retail Price (MRP)",
            REVIEW_REQUIRED,
            "Low extraction confidence",
            evidence,
        )
    if _missing_evidence(field_data):
        return _evaluation(
            "LM-PCR-6-1-e",
            "Maximum Retail Price (MRP)",
            REVIEW_REQUIRED,
            "Missing bounding box evidence",
            evidence,
        )
    currency_unit = field_data.get("unit")
    normalized_unit = currency_unit.strip().lower() if isinstance(currency_unit, str) else ""
    if normalized_unit not in INDIAN_CURRENCY_UNITS:
        return _evaluation(
            "LM-PCR-6-1-e",
            "Maximum Retail Price (MRP)",
            REVIEW_REQUIRED,
            "Indian currency unit cannot be confidently identified",
            evidence,
        )
    return _evaluation(
        "LM-PCR-6-1-e",
        "Maximum Retail Price (MRP)",
        PASS,
        "",
        evidence,
    )


def evaluate_manufacturer(
    field_data: ValidatedFieldData, is_food_product: bool = False
) -> dict[str, Any]:
    """Evaluate Rule 6(1)(a): Manufacturer Details."""
    evidence = _evidence(field_data)
    if field_data.get("value") is None:
        return _evaluation(
            "LM-PCR-6-1-a",
            "Manufacturer Details",
            FAIL,
            "Manufacturer details are missing",
            evidence,
        )
    if not _has_sufficient_confidence(field_data):
        return _evaluation(
            "LM-PCR-6-1-a",
            "Manufacturer Details",
            REVIEW_REQUIRED,
            "Low extraction confidence",
            evidence,
        )
    if _missing_evidence(field_data):
        return _evaluation(
            "LM-PCR-6-1-a",
            "Manufacturer Details",
            REVIEW_REQUIRED,
            "Missing bounding box evidence",
            evidence,
        )
    if is_food_product:
        return _evaluation(
            "LM-PCR-6-1-a",
            "Manufacturer Details",
            REVIEW_REQUIRED,
            "Food labelling has an FSSAI overlap",
            evidence,
        )
    return _evaluation("LM-PCR-6-1-a", "Manufacturer Details", PASS, "", evidence)


def evaluate_all_rules(
    extracted_data: ValidatedExtractionData, is_food_product: bool = False
) -> dict[str, Any]:
    """Evaluate all five MVP rules and calculate the overall inspection status."""
    evaluations = [
        evaluate_commodity_name(extracted_data.get("commodity_name", {})),
        evaluate_net_quantity(extracted_data.get("net_quantity", {})),
        evaluate_manufacturing_date(extracted_data.get("mfg_date", {})),
        evaluate_mrp(extracted_data.get("mrp", {})),
        evaluate_manufacturer(
            extracted_data.get("manufacturer", {}), is_food_product=is_food_product
        ),
    ]
    statuses = {evaluation["status"] for evaluation in evaluations}
    if FAIL in statuses:
        overall_status = FAIL
    elif REVIEW_REQUIRED in statuses:
        overall_status = REVIEW_REQUIRED
    else:
        overall_status = PASS
    return {"overall_status": overall_status, "evaluations": evaluations}
