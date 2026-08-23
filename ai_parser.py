import json
import requests
from ocr_engine import extract_text_from_image

OLLAMA_URL = "http://localhost:11434/api/generate"

def parse_ocr_with_ai(ocr_blocks):
    # OCR blocks ko readable text string me badlo
    raw_text = "\n".join([f"ID: {b['block_id']} | Text: {b['text']}" for b in ocr_blocks])
    
    prompt = f"""
    You are a Legal Metrology packaging extractor. Extract structured fields from the OCR text below.
    
    OCR TEXT:
    {raw_text}
    
    CRITICAL RULES:
    1. Extract ONLY these fields: 'mrp', 'net_quantity', 'commodity_name', 'manufacturer', 'mfg_date'.
    2. Do NOT invent values. If a field is not present, set its value to null.
    3. Provide exact OCR 'source_block_ids' (e.g., ['b_12']) and raw_source text for every extracted value.
    4. Respond ONLY with a valid JSON object matching this schema:
    
    {{
      "commodity_name": {{"value": "Soap", "raw_source": "Soap", "source_block_ids": ["b_5"]}},
      "net_quantity": {{"value": 500, "unit": "g", "raw_source": "500 g", "source_block_ids": ["b_20"]}},
      "mfg_date": {{"value": "05/2026", "raw_source": "Mfg 05/2026", "source_block_ids": ["b_30"]}},
      "mrp": {{"value": 120, "unit": "INR", "inclusive_of_taxes": true, "raw_source": "MRP Rs. 120 inclusive of all taxes", "source_block_ids": ["b_14"]}},
      "manufacturer": {{"value": null, "raw_source": "", "source_block_ids": []}}
    }}
    """

    payload = {
        "model": "qwen2.5:0.5b",
        "prompt": prompt,
        "format": "json",
        "stream": False
    }

    try:
        response = requests.post(OLLAMA_URL, json=payload)
        result = response.json()
        parsed_json = json.loads(result['response'])
        return parsed_json
    except Exception as e:
        print(f"AI Extraction Error: {e}")
        return None

# Combined Test Run: sample.jpg -> OCR -> AI Parser
if __name__ == "__main__":
    print("Step 1: Extracting OCR from sample.jpg...")
    ocr_output = extract_text_from_image("sample.jpg")
    
    if isinstance(ocr_output, list) and len(ocr_output) > 0:
        print("Step 2: Sending OCR text to Local Qwen AI Model...")
        ai_result = parse_ocr_with_ai(ocr_output)
        
        print("\n--- FINAL AI PARSED OUTPUT ---")
        print(json.dumps(ai_result, indent=2))
    else:
        print("Error: OCR failed or no text found in sample.jpg")
