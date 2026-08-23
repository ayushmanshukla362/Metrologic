# MetroLogic: Rule Definitions & Data Contracts

## Core Philosophy
1. **AI Extracts:** The Small Language Model (SLM) only extracts semantic meaning from OCR text. It NEVER calculates its own confidence and NEVER makes a legal judgment.
2. **Logic Validates:** Deterministic Python algorithms calculate confidence based on spatial proximity, format validity, and anchor presence.
3. **Rules Evaluate:** Hardcoded Python rule wrappers evaluate the data.
4. **Humans Decide:** Uncertainty always defaults to `REVIEW_REQUIRED`.

## 1. The AI-to-Backend JSON Contract
The local Qwen model MUST output strictly this JSON format:
{
  "commodity_name": { "value": "string | null", "raw_source": "string", "source_block_ids": ["string"] },
  "net_quantity": { "value": "number | null", "unit": "string", "raw_source": "string", "source_block_ids": ["string"] },
  "mfg_date": { "value": "string | null", "raw_source": "string", "source_block_ids": ["string"] },
  "mrp": { "value": "number | null", "unit": "string", "inclusive_of_taxes": "boolean", "raw_source": "string", "source_block_ids": ["string"] },
  "manufacturer": { "value": "string | null", "raw_source": "string", "source_block_ids": ["string"] }
}

The raw AI output MUST NOT contain a `confidence` key. The backend deterministically scores each extracted field and creates the validated Python dictionary consumed by the rules engine. The validated structure preserves the raw field data and adds `confidence`:
{
  "commodity_name": { "value": "string | null", "raw_source": "string", "source_block_ids": ["string"], "confidence": "number" },
  "net_quantity": { "value": "number | null", "unit": "string", "raw_source": "string", "source_block_ids": ["string"], "confidence": "number" },
  "mfg_date": { "value": "string | null", "raw_source": "string", "source_block_ids": ["string"], "confidence": "number" },
  "mrp": { "value": "number | null", "unit": "string", "inclusive_of_taxes": "boolean", "raw_source": "string", "source_block_ids": ["string"], "confidence": "number" },
  "manufacturer": { "value": "string | null", "raw_source": "string", "source_block_ids": ["string"], "confidence": "number" }
}

Data flow: Raw AI Output -> Validated Python Dictionary -> Rules Engine.

## 2. The 5 Legal Metrology MVP Rules
Global Confidence Threshold: Any extracted field with a calculated confidence score < 0.80 automatically results in REVIEW_REQUIRED.
- **Rule 1 (LM-PCR-6-1-b):** Generic/Common Commodity Name. FAIL if missing.
- **Rule 2 (LM-PCR-6-1-c):** Net Quantity. Must use standard metric units (g, kg, ml, l, N). REVIEW_REQUIRED if non-standard (e.g., gms). FAIL if missing.
- **Rule 3 (LM-PCR-6-1-d):** Date of Manufacture. FAIL if missing.
- **Rule 4 (LM-PCR-6-1-e):** MRP. FAIL if the value is missing. REVIEW_REQUIRED if confidence is below 0.80 or Indian currency cannot be confidently established. PASS requires the MRP value, Indian currency, confidence >= 0.80, and evidence. The literal phrase "inclusive of all taxes" is not required for this MVP.
- **Rule 5 (LM-PCR-6-1-a):** Manufacturer Details. Missing value is FAIL. For an existing value, confidence below 0.80 is REVIEW_REQUIRED. An existing manufacturer value on a food product is REVIEW_REQUIRED because of the FSSAI overlap. PASS requires confidence >= 0.80, evidence, and a non-food product.

## 3. Evaluation States
- `PASS`: Requirement met, evidence exists, confidence >= 0.80.
- `FAIL`: Requirement definitively missing.
- `REVIEW_REQUIRED`: Data ambiguous, confidence < 0.80, conflicts, or FSSAI overlap.
