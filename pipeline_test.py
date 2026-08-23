import json
from ocr_engine import extract_text_from_image
from ai_parser import parse_ocr_with_ai
from confidence_engine import process_extracted_data
from schemas import PackageData, ExtractedField
from rules import evaluate_package, overall_status

def run_full_pipeline(image_path):
    print(f"--- 1. OCR Extraction: {image_path} ---")
    ocr_blocks = extract_text_from_image(image_path)
    
    print("--- 2. AI Semantic Parsing ---")
    ai_raw = parse_ocr_with_ai(ocr_blocks)
    
    print("--- 3. Confidence Calculation ---")
    structured = process_extracted_data(ai_raw, ocr_blocks)
    
    print("--- 4. Map to Rules Engine Schema ---")
    fields = {key: ExtractedField(**value) for key, value in structured.items()}
    
    pkg_data = PackageData(
        session_id="session_test_101",
        commodity_name=fields["commodity_name"],
        net_quantity=fields["net_quantity"],
        mfg_date=fields["mfg_date"],
        mrp=fields["mrp"],
        manufacturer=fields["manufacturer"]
    )
    
    print("--- 5. Evaluating Legal Metrology Rules ---")
    rule_results = evaluate_package(pkg_data)
    
    print("\n================ FINAL RESULT ================")
    print(f"Overall status: {overall_status(rule_results)}")
    for result in rule_results:
        print(f"{result.rule_id}: {result.status} — {result.reason}")
    print("==============================================")

if __name__ == "__main__":
    run_full_pipeline("sample.jpg")
