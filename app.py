import os
import shutil
import json
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from ocr_engine import extract_text_from_image
from ai_parser import parse_ocr_with_ai
from confidence_engine import process_extracted_data
from schemas import PackageData, ExtractedField
from rules import check_mrp

app = FastAPI(title="Legal Metrology Automated Inspector API")

# Enable CORS for Frontend/Web UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/")
def home():
    return {"message": "Legal Metrology API is up and running!"}

@app.post("/inspect-image/")
async def inspect_image(file: UploadFile = File(...)):
    # Save uploaded image temporarily
    file_path = os.path.join(UPLOAD_DIR, file.filename)
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
        
    try:
        # 1. Extract OCR
        ocr_blocks = extract_text_from_image(file_path)
        if isinstance(ocr_blocks, dict) and "error" in ocr_blocks:
            raise HTTPException(status_code=400, detail=ocr_blocks["error"])

        # 2. Extract fields with Local AI
        ai_raw = parse_ocr_with_ai(ocr_blocks)
        if not ai_raw:
            raise HTTPException(status_code=500, detail="AI Extraction failed")

        # 3. Calculate Confidence Scores
        structured = process_extracted_data(ai_raw, ocr_blocks)

        # 4. Map to Rules Schema
        mrp_field = ExtractedField(**structured["mrp"]) if structured.get("mrp") else None
        net_qty_field = ExtractedField(**structured["net_quantity"]) if structured.get("net_quantity") else None

        pkg_data = PackageData(
            session_id=f"session_{file.filename}",
            mrp=mrp_field,
            net_quantity=net_qty_field
        )

        # 5. Evaluate Rules
        mrp_rule = check_mrp(pkg_data)

        # Clean temp file
        if os.path.exists(file_path):
            os.remove(file_path)

        return {
            "status": "success",
            "extracted_data": structured,
            "rules_evaluation": [
                mrp_rule.dict()
            ]
        }

    except Exception as e:
        if os.path.exists(file_path):
            os.remove(file_path)
        raise HTTPException(status_code=500, detail=str(e))