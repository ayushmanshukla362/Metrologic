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

- **Default State**: Enabled (`true`)
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
<script type="module" src="js/app.js"></script>
```

---

## 📡 Expected API Endpoints

When connected to a real Python / FastAPI backend (`METROLOGIC_DEMO_MODE = false`), the frontend calls the following endpoints:

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/session/init` | Create new inspection session & return `session_id` |
| `POST` | `/api/session/{id}/upload` | Upload image (`multipart/form-data` with `image` and `panel` = `front` \| `back` \| `side`) |
| `POST` | `/api/session/{id}/analyze` | Trigger OCR, candidate filtering, AI parsing, and rule evaluation |
| `GET` | `/api/session/{id}/result` | Fetch complete evaluation result & rule findings |
| `GET` | `/api/session/{id}/evidence/{field}` | Fetch detailed evidence for a specific field |

---

## 📦 Expected Result Schema

The `GET /api/session/{id}/result` endpoint should return JSON structured as:

```json
{
  "session_id": "ML-2026-00123",
  "status": "REVIEW_REQUIRED",
  "processing_time": "1.8s",
  "product": "Household Cleaner",
  "images": {
    "front": { "url": "/images/front.jpg" },
    "back": { "url": "/images/back.jpg" },
    "side": { "url": "/images/side.jpg" }
  },
  "rules": [
    {
      "id": "mrp_declaration",
      "name": "MRP Declaration",
      "status": "REVIEW_REQUIRED",
      "requirement": "Maximum Retail Price (MRP) must be clearly printed inclusive of all taxes.",
      "reason": "Low-confidence MRP extraction (63%). Officer verification required.",
      "confidence": 0.63,
      "panel": "back",
      "box": [100, 360, 600, 80],
      "evidenceId": "img_back:block_mrp",
      "extractedValue": "₹120 (Uncertain)",
      "rawOcr": "M.R.P R$120"
    }
  ]
}
```

### Coordinate Formats Supported
- **Absolute Coordinates**: `[x, y, width, height]` in natural image dimensions.
- **Normalized Coordinates**: `[x1, y1, x2, y2]` where values range from `0.0` to `1.0`.

---

## 💡 Key Inspection Workflow

1. **Dashboard**: View summary metrics and previous inspection logs.
2. **Start Inspection**: Upload Front, Back, and Side panel images (or click Quick Demo Scenarios 1, 2, or 3).
3. **Processing**: Watch stage-based checklist execution (Images uploaded → OCR → Candidate filtering → AI parsing → Evidence validation → Rule evaluation).
4. **Inspection Result**:
   - Inspect overall status (`PASS`, `REVIEW_REQUIRED`, `FAIL`).
   - Audit 5 selected Legal Metrology rule checks.
   - Click any rule (e.g., **MRP Declaration**) to automatically switch to the source package panel image, highlight the evidence region with a precision bounding box, focus the view, and slide out the **Evidence Detail** drawer.
