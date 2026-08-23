import json
from ocr_engine import extract_text_from_image
from ai_parser import parse_ocr_with_ai
from confidence_engine import process_extracted_data
from schemas import PackageData, ExtractedField
from rules import check_mrp

def run_full_pipeline(image_path):
    print(f"--- 1. OCR Extraction: {image_path} ---")
    ocr_blocks = extract_text_from_image(image_path)
    
    print("--- 2. AI Semantic Parsing ---")
    ai_raw = parse_ocr_with_ai(ocr_blocks)
    
    print("--- 3. Confidence Calculation ---")
    structured = process_extracted_data(ai_raw, ocr_blocks)
    
    print("--- 4. Map to Rules Engine Schema ---")
    mrp_field = ExtractedField(**structured["mrp"]) if structured.get("mrp") else None
    net_qty_field = ExtractedField(**structured["net_quantity"]) if structured.get("net_quantity") else None
    
    pkg_data = PackageData(
        session_id="session_test_101",
        mrp=mrp_field,
        net_quantity=net_qty_field
    )
    
    print("--- 5. Evaluating Legal Metrology Rules ---")
    mrp_result = check_mrp(pkg_data)
    
    print("\n================ FINAL RESULT ================")
    print(f"Rule: {mrp_result.requirement}")
    print(f"Status: {mrp_result.status}")
    print(f"Reason: {mrp_result.reason}")
    print("==============================================")

if __name__ == "__main__":
    run_full_pipeline("sample.jpg")