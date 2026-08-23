# MetroLogic: Execution Phases & Collaboration

## Collaboration Protocol
1. **Mock First:** Frontend builds UI components using static JSON files.
2. **Branching:** Use feature branches for backend, AI, and frontend. 
3. **Integration Rule:** The Headless CLI pipeline (Backend + AI) must work end-to-end on `dev` before wiring to the React dashboard.

## Phases
- **Phase 1: Foundation.** Write `rules.py` and `test_rules.py`. Provision Neon PostgreSQL schema.
- **Phase 2: Core Backend.** FastAPI setup, Tesseract OCR integration, and spatial grid bucket filtering.
- **Phase 3: AI & Validation.** Local Qwen 3.5 parsing, JSON schema enforcement, and deterministic confidence math.
- **Phase 4: Integration.** `inspection_pipeline.py` ties OCR, AI, and Rules together. Saves to DB.
- **Phase 5: Frontend Dashboard.** React UI connects to FastAPI. Renders bounding boxes.
- **Phase 6: Edge Case Testing.** Test clean, blurry, and conflicting physical packages.
- **Phase 7: Demo Polish.** Finalize presentation and rehearse demo script.
