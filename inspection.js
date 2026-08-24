/**
 * METROLOGIC - Start Inspection View Module
 * Handles 3-panel upload cards, drag-and-drop, image format validation,
 * metadata extraction, quick demo scenario loaders, and RUN ANALYSIS trigger.
 */

import { DEMO_SCENARIOS } from './demo-data.js';

export class InspectionView {
  constructor(appController) {
    this.app = appController;
    
    this.panels = {
      front: { file: null, previewUrl: null, meta: null },
      back: { file: null, previewUrl: null, meta: null },
      side: { file: null, previewUrl: null, meta: null }
    };

    this.activeScenarioKey = 'scenario2'; // Default scenario for demo analysis

    this.btnRunAnalysis = document.getElementById('btn-run-analysis');
    
    // Quick Demo Buttons
    this.btnDemo1 = document.getElementById('btn-load-demo-1');
    this.btnDemo2 = document.getElementById('btn-load-demo-2');
    this.btnDemo3 = document.getElementById('btn-load-demo-3');

    this.bindEvents();
  }

  bindEvents() {
    ['front', 'back', 'side'].forEach(panel => {
      const dropzone = document.getElementById(`dropzone-${panel}`);
      const fileInput = document.getElementById(`file-${panel}`);

      // Drag & Drop
      dropzone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropzone.classList.add('drag-over');
      });

      dropzone.addEventListener('dragleave', () => {
        dropzone.classList.remove('drag-over');
      });

      dropzone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropzone.classList.remove('drag-over');
        if (e.dataTransfer.files && e.dataTransfer.files[0]) {
          this.handleFileSelect(panel, e.dataTransfer.files[0]);
        }
      });

      // Click to browse
      dropzone.addEventListener('click', (e) => {
        if (e.target.closest('.btn-replace') || e.target.closest('.btn-remove')) return;
        fileInput.click();
      });

      fileInput.addEventListener('change', (e) => {
        if (e.target.files && e.target.files[0]) {
          this.handleFileSelect(panel, e.target.files[0]);
        }
      });

      // Replace & Remove actions
      const card = document.getElementById(`card-${panel}`);
      card.querySelector('.btn-replace').addEventListener('click', (e) => {
        e.stopPropagation();
        fileInput.click();
      });

      card.querySelector('.btn-remove').addEventListener('click', (e) => {
        e.stopPropagation();
        this.clearPanel(panel);
      });
    });

    // Run Analysis Button
    this.btnRunAnalysis.addEventListener('click', () => {
      this.startAnalysis();
    });

    // Demo Scenarios Quick Loaders
    this.btnDemo1.addEventListener('click', () => this.loadDemoScenario('scenario1'));
    this.btnDemo2.addEventListener('click', () => this.loadDemoScenario('scenario2'));
    this.btnDemo3.addEventListener('click', () => this.loadDemoScenario('scenario3'));
  }

  // Handle file selection & frontend validation
  handleFileSelect(panel, file) {
    const validTypes = ['image/jpeg', 'image/jpg', 'image/png', 'image/webp'];
    if (!validTypes.includes(file.type.toLowerCase()) && !file.name.match(/\.(jpg|jpeg|png|webp)$/i)) {
      alert('Unable to upload this image. Unsupported image format. Please select a JPG, PNG or WEBP image.');
      return;
    }

    const previewUrl = URL.createObjectURL(file);
    const sizeKb = (file.size / 1024).toFixed(1);
    const sizeFormatted = sizeKb > 1024 ? `${(sizeKb / 1024).toFixed(1)} MB` : `${sizeKb} KB`;

    // Extract image dimensions
    const imgObj = new Image();
    imgObj.src = previewUrl;
    imgObj.onload = () => {
      const dimensions = `${imgObj.naturalWidth} x ${imgObj.naturalHeight}`;
      this.setPanelState(panel, file, previewUrl, {
        name: file.name,
        size: sizeFormatted,
        dimensions
      });
    };
  }

  // Update card UI state
  setPanelState(panel, file, previewUrl, meta) {
    this.panels[panel] = { file, previewUrl, meta };

    const dzEmpty = document.getElementById(`dz-empty-${panel}`);
    const dzPreview = document.getElementById(`dz-preview-${panel}`);
    const imgEl = document.getElementById(`img-${panel}`);
    const nameEl = document.getElementById(`name-${panel}`);
    const sizeEl = document.getElementById(`size-${panel}`);
    const dimsEl = document.getElementById(`dims-${panel}`);
    const cardEl = document.getElementById(`card-${panel}`);

    cardEl.classList.remove('highlight-error');
    imgEl.src = previewUrl;
    nameEl.textContent = meta.name;
    sizeEl.textContent = meta.size;
    dimsEl.textContent = meta.dimensions;

    dzEmpty.classList.add('hidden');
    dzPreview.classList.remove('hidden');

    this.checkFormCompletion();
  }

  // Clear single panel
  clearPanel(panel) {
    this.panels[panel] = { file: null, previewUrl: null, meta: null };

    const dzEmpty = document.getElementById(`dz-empty-${panel}`);
    const dzPreview = document.getElementById(`dz-preview-${panel}`);
    const fileInput = document.getElementById(`file-${panel}`);

    fileInput.value = '';
    dzEmpty.classList.remove('hidden');
    dzPreview.classList.add('hidden');

    this.checkFormCompletion();
  }

  // Highlight specific panel for Quality Retry
  highlightPanelForQuality(panel) {
    const cardEl = document.getElementById(`card-${panel}`);
    if (cardEl) {
      cardEl.classList.add('highlight-error');
      cardEl.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }
  }

  // Check if all 3 panel images exist
  checkFormCompletion() {
    const isComplete = !!(this.panels.front.file && this.panels.back.file && this.panels.side.file);
    this.btnRunAnalysis.disabled = !isComplete;
  }

  // Load Pre-packaged Demo Scenario
  loadDemoScenario(scenarioKey) {
    this.activeScenarioKey = scenarioKey;
    const scenario = DEMO_SCENARIOS[scenarioKey];
    if (!scenario) return;

    ['front', 'back', 'side'].forEach(panel => {
      const data = scenario.images[panel];
      // Create synthetic file object for demo
      const fakeFile = new File(["demo"], data.name, { type: "image/svg+xml" });
      this.setPanelState(panel, fakeFile, data.url, {
        name: data.name,
        size: data.size,
        dimensions: data.dimensions
      });
    });
  }

  // Start analysis transition
  startAnalysis() {
    if (!this.panels.front.file || !this.panels.back.file || !this.panels.side.file) return;

    this.app.startProcessing({
      panels: this.panels,
      scenarioKey: this.activeScenarioKey
    });
  }
}
