# METROLOGIC — AI-Assisted Legal Metrology Package Compliance System

**MetroLogic** is an internal inspection workstation frontend for **Legal Metrology Officers**. It enables package compliance evaluation across three panel views (Front, Back, Side), providing evidence traceability, bounding box highlighting, intra-image conflict resolution, and deterministic rule checks.

---

## 🚀 Quick Start (Local Setup)

The frontend is built using **HTML5, CSS3, Vanilla JavaScript, and ES Modules** without external frameworks or dependencies.

### Option 1: Serve with any HTTP static server (Recommended for ES Modules)
Using Python:
```bash
python -m http.server 8080
```
Then open `http://localhost:8080` in your browser.

Using Node `serve` / `npx`:
```bash
npx serve .
```

### Option 2: Live Server (VSCode)
Right-click `index.html` in VSCode and select **Open with Live Server**.

---

## ⚙️ Configuration

### 1. Enabling / Disabling Demo Mode
The application includes a standalone offline **Demo Mode** (`METROLOGIC_DEMO_MODE`) with generated SVG package panels and pre-configured test scenarios (Clean Pass, Uncertain MRP, Conflicting MRP).

- **Default State**: Disabled (`false`), so the frozen backend is used by default.
- To toggle Demo Mode or switch to a live backend, modify `index.html` or set it in your browser console:

```javascript
// Enable standalone offline demo mode
window.METROLOGIC_DEMO_MODE = true;

// Enable real FastAPI backend API mode
window.METROLOGIC_DEMO_MODE = false;
```

### 2. Configuring the Backend FastAPI URL
Set the backend base URL before `app.js` initializes:

```html
<script>
  window.METROLOGIC_API_URL = "http://localhost:8000";
  window.METROLOGIC_DEMO_MODE = false; // Set to false when connecting to FastAPI
</script>
<script type="module" src="app.js"></script>
```

---

## 📡 Expected API Endpoints

When connected to the frozen Python / FastAPI backend (`METROLOGIC_DEMO_MODE = false`), the frontend calls one endpoint:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/inspection` | Submit one selected image as multipart field `file` and receive the complete inspection result |

---

## 📦 Expected Result Schema

The `POST /api/inspection` endpoint returns JSON structured as:

```json
{
  "session_id": "ML-2026-00123",
  "overall_status": "REVIEW_REQUIRED",
  "extracted_fields": {
    "commodity_name": { "value": "Household Cleaner", "raw_source": "Commodity: Household Cleaner", "source_block_ids": ["img1:block2"], "confidence": 0.96 },
    "net_quantity": { "value": 125, "unit": "g", "raw_source": "125 g", "source_block_ids": ["img1:block4"], "confidence": 0.98 },
    "mfg_date": { "value": "01/2026", "raw_source": "Mfg Date: 01/2026", "source_block_ids": ["img2:block3"], "confidence": 0.95 },
    "mrp": { "value": 449, "unit": "INR", "raw_source": "449.00", "source_block_ids": ["img1:block7"], "confidence": 0.63 },
    "manufacturer": { "value": "Example Manufacturer", "raw_source": "Mfd & Pkd by: Example Manufacturer", "source_block_ids": ["img2:block8"], "confidence": 0.97 }
  },
  "confidence": { "commodity_name": 0.96, "net_quantity": 0.98, "mfg_date": 0.95, "mrp": 0.63, "manufacturer": 0.97 },
  "compliance_evaluations": [
    {
      "rule_id": "LM-PCR-6-1-e",
      "status": "REVIEW_REQUIRED",
      "requirement": "Maximum Retail Price (MRP) must be clearly printed inclusive of all taxes.",
      "reason": "Low-confidence MRP extraction (63%). Officer verification required.",
      "evidence": ["img1:block7"]
    }
  ]
}
```

---

## 💡 Key Inspection Workflow

1. **Dashboard**: View summary metrics and previous inspection logs.
2. **Start Inspection**: Select one image from the Front, Back, or Side panel cards (or click Quick Demo Scenarios 1, 2, or 3). The current backend MVP processes one image per inspection.
3. **Processing**: Watch stage-based checklist execution (Images uploaded → OCR → Candidate filtering → AI parsing → Evidence validation → Rule evaluation).
4. **Inspection Result**:
   - Inspect overall status (`PASS`, `REVIEW_REQUIRED`, `FAIL`).
   - Audit 5 selected Legal Metrology rule checks.
   - Click any rule (e.g., **MRP Declaration**) to automatically switch to the source package panel image, highlight the evidence region with a precision bounding box, focus the view, and slide out the **Evidence Detail** drawer.
