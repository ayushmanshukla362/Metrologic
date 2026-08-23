from confidence_engine import CONFIDENCE_THRESHOLD
from schemas import PackageData, RuleResult


def _result(rule_id, requirement, field, missing_reason, invalid_reason=""):
    evidence = field.source_block_ids if field else []
    if not field or field.value in (None, ""):
        return RuleResult(rule_id=rule_id, requirement=requirement, status="FAIL", reason=missing_reason, evidence=evidence)
    if field.confidence < CONFIDENCE_THRESHOLD:
        return RuleResult(rule_id=rule_id, requirement=requirement, status="REVIEW_REQUIRED", reason=f"Low extraction confidence ({field.confidence:.2f}).", evidence=evidence)
    if invalid_reason:
        return RuleResult(rule_id=rule_id, requirement=requirement, status="REVIEW_REQUIRED", reason=invalid_reason, evidence=evidence)
    return RuleResult(rule_id=rule_id, requirement=requirement, status="PASS", reason="Requirement met with supporting evidence.", evidence=evidence)


def check_commodity_name(data):
    return _result("LM-PCR-6-1-b", "Generic/Common Commodity Name", data.commodity_name, "Commodity name is missing.")


def check_net_quantity(data):
    field = data.net_quantity
    invalid = "Net quantity uses a non-standard unit and needs human review." if field and field.value not in (None, "") and (field.unit or "").lower() not in {"g", "kg", "ml", "l", "n"} else ""
    return _result("LM-PCR-6-1-c", "Net Quantity", field, "Net quantity is missing.", invalid)


def check_mfg_date(data):
    return _result("LM-PCR-6-1-d", "Date of Manufacture", data.mfg_date, "Date of manufacture is missing.")


def check_mrp(data):
    field = data.mrp
    invalid = "MRP must state that it is inclusive of all taxes." if field and field.value not in (None, "") and field.inclusive_of_taxes is not True else ""
    return _result("LM-PCR-6-1-e", "Maximum Retail Price (MRP)", field, "MRP is missing.", invalid)


def check_manufacturer(data):
    field = data.manufacturer
    if data.is_food_product:
        return RuleResult(
            rule_id="LM-PCR-6-1-a",
            requirement="Manufacturer Details",
            status="REVIEW_REQUIRED",
            reason="Food product detected; manufacturer details require FSSAI overlap review.",
            evidence=field.source_block_ids if field else [],
        )
    if data.is_food_product is None:
        return RuleResult(
            rule_id="LM-PCR-6-1-a",
            requirement="Manufacturer Details",
            status="REVIEW_REQUIRED",
            reason="Product category is unknown; FSSAI overlap cannot be ruled out.",
            evidence=field.source_block_ids if field else [],
        )
    return _result("LM-PCR-6-1-a", "Manufacturer Details", field, "Manufacturer details are missing.")


def evaluate_package(data):
    return [check_commodity_name(data), check_net_quantity(data), check_mfg_date(data), check_mrp(data), check_manufacturer(data)]


def overall_status(results):
    statuses = {result.status for result in results}
    if "FAIL" in statuses:
        return "FAIL"
    if "REVIEW_REQUIRED" in statuses:
        return "REVIEW_REQUIRED"
    return "PASS"
