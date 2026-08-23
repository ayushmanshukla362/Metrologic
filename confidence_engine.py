CONFIDENCE_THRESHOLD = 0.80

def calculate_field_confidence(extracted_field, ocr_blocks):
    """
    Python code confidence score calculate karega - AI model nahi.
    """
    if not extracted_field or not extracted_field.get("value"):
        return 0.0
    
    source_id = extracted_field.get("source_id")
    if not source_id:
        return 0.50  # AI value laya par OCR source mapping nahi mili

    # OCR text confidence verify karo
    matched_ocr = next((b for b in ocr_blocks if b["block_id"] == source_id), None)
    if matched_ocr:
        return matched_ocr.get("ocr_confidence", 0.70)
    
    return 0.60

def process_extracted_data(ai_output, ocr_blocks):
    processed = {}
    
    for field_key, field_data in ai_output.items():
        if field_data and field_data.get("value"):
            conf = calculate_field_confidence(field_data, ocr_blocks)
            processed[field_key] = {
                "field_key": field_key,
                "value": str(field_data["value"]),
                "unit": field_data.get("unit"),
                "confidence": conf,
                "raw_source": field_data.get("source_id")
            }
        else:
            processed[field_key] = {
                "field_key": field_key,
                "value": None,
                "unit": None,
                "confidence": 0.0,
                "raw_source": None
            }
            
    return processed