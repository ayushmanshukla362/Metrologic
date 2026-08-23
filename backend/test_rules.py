import pytest

from rules import evaluate_all_rules


def _raw_field(value, source_block_id, **extra):
    return {
        "value": value,
        "source_block_ids": [source_block_id],
        **extra,
    }


def _validated_field(value, source_block_id, confidence=0.95, **extra):
    return {
        **_raw_field(value, source_block_id, **extra),
        "confidence": confidence,
    }


def _clean_package():
    return {
        "commodity_name": _validated_field("Biscuits", "img1:block2"),
        "net_quantity": _validated_field(200, "img1:block4", unit="g"),
        "mfg_date": _validated_field("2026-01-15", "img2:block3"),
        "mrp": _validated_field(50, "img1:block7", unit="INR"),
        "manufacturer": _validated_field("Metro Foods Pvt Ltd", "img2:block8"),
    }


def _evaluation_for(result, rule_id):
    return next(item for item in result["evaluations"] if item["rule_id"] == rule_id)


def test_all_rules_pass():
    result = evaluate_all_rules(_clean_package(), is_food_product=False)

    assert result["overall_status"] == "PASS"
    for rule_id in (
        "LM-PCR-6-1-b",
        "LM-PCR-6-1-c",
        "LM-PCR-6-1-d",
        "LM-PCR-6-1-e",
        "LM-PCR-6-1-a",
    ):
        assert _evaluation_for(result, rule_id)["status"] == "PASS"


def test_missing_mrp_fails():
    package = _clean_package()
    package["mrp"] = _validated_field(None, "img1:block7", unit="INR")

    result = evaluate_all_rules(package)

    assert _evaluation_for(result, "LM-PCR-6-1-e")["status"] == "FAIL"
    assert result["overall_status"] == "FAIL"


def test_low_confidence_mrp_review():
    package = _clean_package()
    package["mrp"] = _validated_field(50, "img1:block7", confidence=0.63, unit="INR")

    result = evaluate_all_rules(package)

    assert _evaluation_for(result, "LM-PCR-6-1-e")["status"] == "REVIEW_REQUIRED"
    assert result["overall_status"] == "REVIEW_REQUIRED"


def test_invalid_quantity_unit_review():
    package = _clean_package()
    package["net_quantity"] = _validated_field(200, "img1:block4", unit="gms")

    result = evaluate_all_rules(package)

    assert _evaluation_for(result, "LM-PCR-6-1-c")["status"] == "REVIEW_REQUIRED"
    assert result["overall_status"] == "REVIEW_REQUIRED"


def test_food_manufacturer_review():
    result = evaluate_all_rules(_clean_package(), is_food_product=True)

    assert _evaluation_for(result, "LM-PCR-6-1-a")["status"] == "REVIEW_REQUIRED"
    assert result["overall_status"] == "REVIEW_REQUIRED"


def test_valid_field_without_evidence_review():
    package = _clean_package()
    package["commodity_name"]["source_block_ids"] = []

    result = evaluate_all_rules(package)

    evaluation = _evaluation_for(result, "LM-PCR-6-1-b")
    assert evaluation["status"] == "REVIEW_REQUIRED"
    assert evaluation["reason"] == "Missing bounding box evidence"
    assert result["overall_status"] == "REVIEW_REQUIRED"


def test_exact_confidence_threshold_passes():
    package = _clean_package()
    package["mrp"]["confidence"] = 0.80

    result = evaluate_all_rules(package)

    assert _evaluation_for(result, "LM-PCR-6-1-e")["status"] == "PASS"
    assert result["overall_status"] == "PASS"


def test_food_product_with_missing_manufacturer_fails():
    package = _clean_package()
    package["manufacturer"] = _validated_field(None, "img2:block8")

    result = evaluate_all_rules(package, is_food_product=True)

    assert _evaluation_for(result, "LM-PCR-6-1-a")["status"] == "FAIL"
    assert result["overall_status"] == "FAIL"


def test_existing_field_without_confidence_review():
    package = _clean_package()
    package["mrp"] = _raw_field(50, "img1:block7", unit="INR")

    result = evaluate_all_rules(package)

    assert _evaluation_for(result, "LM-PCR-6-1-e")["status"] == "REVIEW_REQUIRED"
    assert result["overall_status"] == "REVIEW_REQUIRED"


def test_existing_field_with_malformed_confidence_review():
    package = _clean_package()
    package["mrp"] = _validated_field(
        50, "img1:block7", confidence="not-a-number", unit="INR"
    )

    result = evaluate_all_rules(package)

    assert _evaluation_for(result, "LM-PCR-6-1-e")["status"] == "REVIEW_REQUIRED"
    assert result["overall_status"] == "REVIEW_REQUIRED"


def test_valid_mrp_without_inclusive_tax_phrase_passes():
    package = _clean_package()
    package["mrp"] = _validated_field(50, "img1:block7", unit="INR")

    result = evaluate_all_rules(package)

    assert "inclusive_of_taxes" not in package["mrp"]
    assert _evaluation_for(result, "LM-PCR-6-1-e")["status"] == "PASS"
    assert result["overall_status"] == "PASS"
