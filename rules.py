from schemas import PackageData, RuleResult

CONFIDENCE_THRESHOLD = 0.80  # Baseline confidence score

def check_mrp(data: PackageData) -> RuleResult:
    # 1. Agar MRP mila hi nahi
    if not data.mrp or not data.mrp.value:
        return RuleResult(
            rule_id="LM-PCR-01",
            requirement="MRP Declaration",
            status="FAIL",
            reason="MRP is missing from package labels."
        )
    
    # 2. Agar MRP photo se saf-saf nahi padh paye (low confidence)
    if data.mrp.confidence < CONFIDENCE_THRESHOLD:
        return RuleResult(
            rule_id="LM-PCR-01",
            requirement="MRP Declaration",
            status="REVIEW_REQUIRED",
            reason=f"Low extraction confidence ({data.mrp.confidence}). Needs human review."
        )
        
    # 3. Sab sahi hai
    return RuleResult(
        rule_id="LM-PCR-01",
        requirement="MRP Declaration",
        status="PASS",
        reason="Valid MRP found."
    )