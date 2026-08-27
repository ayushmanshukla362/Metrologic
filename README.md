
# MetroLogic

**Evidence-Backed AI for Legal Metrology Inspection**

MetroLogic is an AI-assisted inspection platform for checking selected packaged-commodity declarations under Legal Metrology requirements.

Instead of treating an LLM response as the final answer, MetroLogic combines **OCR, Vision AI, evidence mapping, deterministic confidence evaluation, and rule-based assessment** to produce a traceable preliminary inspection result:

**PASS / FAIL / REVIEW_REQUIRED**

> **AI extracts. Evidence supports. Rules evaluate. Officers confirm.**

---

## Problem

Legal Metrology officers may need to verify multiple declarations on packaged commodities, including:

- Commodity name
- Net quantity
- MRP
- Manufacturing / packing information
- Manufacturer / packer details
- Other applicable requirements

At scale, manual inspection becomes difficult because officers may inspect many retailers, manufacturers, packers and other businesses while dealing with dense package labels, glare, curved surfaces, noisy OCR, multiple numbers and detailed regulatory requirements.

The department needs a faster, standardized and evidence-linked inspection workflow that assists officers without allowing an unsupported AI answer to become a legal conclusion.

---

## What MetroLogic Does

A package image is submitted to the inspection API and passes through this workflow:

```text
Package Image
      ↓
Tesseract OCR + Gemini Vision
      ↓
Structured Field Extraction
      ↓
Vision → OCR Evidence Mapping
      ↓
Deterministic Confidence
      ↓
Selected Legal Metrology Rule Evaluation
      ↓
PASS / FAIL / REVIEW_REQUIRED
      ↓
Digital Inspection Record
```

### Current MVP fields

The prototype currently focuses on:

- Commodity Name
- Net Quantity
- MRP
- Manufacturing Date
- Manufacturer Details

---

## Why It Is Different

### 1. Evidence-backed extraction

MetroLogic does not rely on a Vision model alone.

Gemini Vision identifies relevant information and visual regions, while Tesseract provides OCR text blocks, locations and OCR confidence.

The system then maps Vision regions back to OCR evidence using:

- Coordinate normalization
- Spatial overlap / coverage
- IoU-based matching
- Text corroboration for relevant borderline cases
- `source_block_ids`

This creates a traceable link between an extracted value and its supporting OCR evidence.

### 2. Deterministic confidence

The AI does not decide its own trusted confidence score.

Confidence is evaluated by deterministic backend logic using the quality and validity of supporting evidence.

Invalid or unsupported evidence is prevented from silently becoming high-confidence evidence.

### 3. Human-in-the-loop safety

The system supports a `REVIEW_REQUIRED` outcome when information is uncertain or evidence is insufficient.

This allows the inspection workflow to treat uncertainty as uncertainty instead of forcing an AI-generated PASS.

### 4. Rule-based compliance evaluation

The current rules engine evaluates the selected Legal Metrology requirements implemented in the prototype.

It does **not** claim complete coverage of every Legal Metrology rule or product category.

---

## Technical Architecture

```text
Frontend
   │
   │ multipart/form-data
   ▼
FastAPI
POST /api/inspection
   │
   ├───────────────┐
   ▼               ▼
Tesseract       Gemini Vision
OCR             Visual Extraction
   │               │
   └───────┬───────┘
           ▼
   Structured Extraction
           │
           ▼
   Evidence Mapping
   Vision BBox
        ↓
   Coordinate Normalization
        ↓
   OCR Spatial Matching
        ↓
   source_block_ids
           │
           ▼
   Schema Validation
      (Pydantic)
           │
           ▼
 Deterministic Confidence
           │
           ▼
 Selected Legal Rules
           │
           ▼
 PASS / FAIL / REVIEW_REQUIRED
           │
           ▼
   Neon PostgreSQL
           │
           ▼
   Result Dashboard
```

---

## Technology Stack

| Layer | Technology |
|---|---|
| Frontend | HTML, CSS, JavaScript |
| Backend | Python, FastAPI |
| OCR | Tesseract OCR |
| AI / Vision | Google Gemini API / Gemini Vision |
| Validation | Pydantic |
| ORM | SQLAlchemy |
| Database | PostgreSQL / Neon |
| Deployment | Docker / Render |
| Backend Testing | pytest |
| Frontend Testing | Node test runner |

---

## API

### `POST /api/inspection`

Accepts a package image using `multipart/form-data`.

The response contains structured inspection information including:

- `session_id`
- `image_id`
- `overall_status`
- `extracted_fields`
- `confidence`
- `compliance_evaluations`
- `errors`

### `GET /api/health`

Basic service health endpoint.

---

## Example Inspection

A sample package image can produce results such as:

```text
Commodity Name
→ NIVEA CREME SOFT SOAP

Net Quantity
→ 125 g

Manufacturer
→ VVF (India) Limited...

Confidence
→ field-level confidence scores

Compliance
→ PASS / FAIL / REVIEW_REQUIRED
```

A missing or insufficiently supported declaration can result in `FAIL` or `REVIEW_REQUIRED` depending on the implemented requirement and available evidence.

---

## Reliability and Edge Cases

MetroLogic is designed around explicit failure handling rather than blind AI confidence.

Examples include:

- Curved or glossy packaging
- Noisy OCR
- Missing text
- Weak extraction confidence
- Missing evidence
- Invalid evidence
- Empty / dangling evidence references
- Evidence associated with the wrong image
- Vision / OCR coordinate mismatch
- AI / model variability

When evidence is not trustworthy enough, the system can use:

```text
REVIEW_REQUIRED
```

rather than forcing an unsupported compliance result.

---

## Testing

The current project includes:

- **143 backend automated tests**
- **18 frontend automated tests**

The backend suite covers areas including:

- OCR / extraction behavior
- Vision response handling
- Schema validation
- Evidence mapping
- Evidence integrity
- Deterministic confidence
- Rule evaluation
- Pipeline integration
- Persistence
- FastAPI API behavior
- CORS behavior

The frontend suite covers areas including:

- Real API integration
- File upload handling
- `/api/inspection` requests
- Backend response rendering
- Confidence rendering
- Compliance result rendering
- Evidence/source rendering
- Error handling
- Demo-mode behavior

---

## Current Prototype vs Future Scope

### Implemented in the current MVP

- OCR + Vision extraction
- Structured field extraction
- Evidence mapping
- Deterministic confidence
- Selected Legal Metrology rule evaluation
- `PASS / FAIL / REVIEW_REQUIRED`
- FastAPI inspection API
- Neon persistence
- Browser-based result dashboard
- Dockerized deployment with Tesseract
- Public Render deployment
- Automated backend and frontend tests

### Planned / Phase 2

The architecture is designed to support additional department-level capabilities such as:

#### Product-category intelligence

Identify product categories and load category-specific inspection checklists and rules.

```text
Package
   ↓
Product Category
   ↓
Applicable Rule Set
   ↓
Inspection
```

Potential categories include:

- Packaged food
- Cosmetics / personal care
- Household goods
- Imported products
- Small consumer electronics

#### Multi-image inspection

Support front, back, side and other package views while maintaining image-specific evidence references.

#### Officer confirmation

A future workflow layer can allow officers to:

- Inspect supporting evidence
- Accept or correct extracted values
- Add comments
- Confirm the final inspection record

The current prototype's result should be understood as a **preliminary system assessment**, not an automatic legal finding.

#### Senior-officer dashboard

Potential department-level analytics include:

- Total inspections
- Compliant / non-compliant products
- Pending reviews
- Repeat businesses
- Common violations
- District-wise trends
- Follow-up cases
- Joint-operation summaries

#### Structured digital inspection reports

Future reports can combine:

- Inspection ID
- Business and officer details
- Date/time/location
- Product/category
- Original images
- Extracted declarations
- Evidence
- Confidence
- Rule references
- Officer comments
- Final confirmation
- Follow-up status

#### Joint Inspection Mode

A future coordination layer could allow departments such as Legal Metrology and FDA to share an operation/business context while keeping their findings, evidence and legal responsibilities separate.

Example:

```text
Joint Operation
      │
      ├── Legal Metrology findings
      │
      └── FDA findings
```

The shared operation ID is intended as operational context, not a combined legal decision.

#### Government-system integration

MetroLogic is intended as an **inspection-intelligence layer**, not a replacement for existing departmental systems.

Future versions could support structured export/integration with relevant government platforms, subject to departmental security and integration requirements.

---

## Deployment

The prototype can be deployed with Docker so the backend has access to the Tesseract system dependency.

### Backend

The production backend is designed to run FastAPI with:

```bash
uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-10000}
```

### Local development

#### Backend

```bash
python -m uvicorn backend.main:app --reload
```

#### Frontend

```bash
python -m http.server 5500
```

Then open:

```text
http://127.0.0.1:5500
```

---

## Project Philosophy

MetroLogic is designed around a simple separation of responsibilities:

```text
AI
→ perception and extraction

OCR
→ textual evidence

Validation
→ structural correctness

Confidence engine
→ trust assessment

Rules engine
→ requirement evaluation

Officer
→ final confirmation
```

This separation is intentional. A multimodal model should assist inspection, but an unsupported model response should not automatically become a legal conclusion.

---

## Status

**Prototype status: Working**

The current prototype has been demonstrated through a real browser-to-backend inspection flow and public deployment.

The project is intended as an **AI-assisted inspection system**, with the current MVP focusing on evidence-backed extraction and selected compliance checks.

---

## License

This project is currently developed as a Smart India Hackathon prototype.

Add an appropriate open-source or project-specific license before public redistribution.
