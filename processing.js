/**
 * METROLOGIC - Processing View Module
 * Visual stage-based checklist animator and backend API processing coordinator.
 */

import { ApiClient } from './api.js';

export class ProcessingView {
  constructor(appController) {
    this.app = appController;

    this.spinner = document.getElementById('processing-spinner');
    this.alertBanner = document.getElementById('quality-alert-banner');
    this.alertTitle = document.getElementById('quality-alert-title');
    this.alertText = document.getElementById('quality-alert-text');
    this.btnReplaceQualityImg = document.getElementById('btn-replace-quality-img');
    this.errorActions = document.getElementById('processing-error-actions');
    this.btnRetry = document.getElementById('btn-retry-analysis');
    this.btnDashboard = document.getElementById('btn-return-dashboard');

    this.stages = [
      document.getElementById('stage-1'),
      document.getElementById('stage-2'),
      document.getElementById('stage-3'),
      document.getElementById('stage-4'),
      document.getElementById('stage-5'),
      document.getElementById('stage-6')
    ];

    this.activeTask = null;
    this.bindEvents();
  }

  bindEvents() {
    this.btnReplaceQualityImg.addEventListener('click', () => {
      const targetPanel = this.btnReplaceQualityImg.getAttribute('data-target-panel') || 'back';
      this.app.returnToUploadForReplacement(targetPanel);
    });

    this.btnRetry.addEventListener('click', () => {
      this.app.navigateTo('inspection');
    });

    this.btnDashboard.addEventListener('click', () => {
      this.app.navigateTo('dashboard');
    });
  }

  resetState() {
    this.spinner.style.display = 'block';
    this.alertBanner.classList.add('hidden');
    this.errorActions.classList.add('hidden');

    this.stages.forEach(s => {
      s.className = 'stage-item';
      s.querySelector('.stage-icon').textContent = '○';
    });
  }

  // Update visual stage state
  setStageState(stageIndex, state) {
    const stageEl = this.stages[stageIndex];
    if (!stageEl) return;

    stageEl.className = `stage-item ${state}`;
    const iconEl = stageEl.querySelector('.stage-icon');

    if (state === 'completed') iconEl.textContent = '✓';
    else if (state === 'processing') iconEl.textContent = '●';
    else if (state === 'failed') iconEl.textContent = '✕';
    else iconEl.textContent = '○';
  }

  // Execute processing workflow
  async startProcessingPipeline(uploadData) {
    this.resetState();

    try {
      // Stage 1: Init & Images Uploaded
      this.setStageState(0, 'processing');
      const sessionRes = await ApiClient.initSession();
      const sessionId = sessionRes.session_id;

      // Upload panels
      for (const panel of ['front', 'back', 'side']) {
        const fileObj = uploadData.panels[panel].file;
        await ApiClient.uploadImage(sessionId, panel, fileObj);
      }
      this.setStageState(0, 'completed');

      // Stage 2: OCR Extraction
      this.setStageState(1, 'processing');
      await this.delay(350);
      this.setStageState(1, 'completed');

      // Stage 3: Candidate Filtering
      this.setStageState(2, 'processing');
      await this.delay(300);
      this.setStageState(2, 'completed');

      // Stage 4: AI Parsing
      this.setStageState(3, 'processing');
      await ApiClient.analyzeSession(sessionId, uploadData.scenarioKey);
      await this.delay(400);
      this.setStageState(3, 'completed');

      // Stage 5: Evidence Validation
      this.setStageState(4, 'processing');
      await this.delay(300);
      this.setStageState(4, 'completed');

      // Stage 6: Rule Evaluation
      this.setStageState(5, 'processing');
      await this.delay(250);
      this.setStageState(5, 'completed');

      // Completed -> Navigate to Result
      await this.delay(200);
      this.app.openInspectionResult(sessionId, uploadData.scenarioKey);

    } catch (err) {
      this.spinner.style.display = 'none';

      if (err.code === 'IMAGE_UNUSABLE') {
        const affectedPanel = err.panel || 'back';
        this.setStageState(0, 'failed');
        
        this.alertTitle.textContent = 'Image Quality Insufficient';
        this.alertText.textContent = `Image quality for ${affectedPanel.toUpperCase()} PANEL is insufficient for reliable analysis. Please replace this image.`;
        this.btnReplaceQualityImg.setAttribute('data-target-panel', affectedPanel);
        
        this.alertBanner.classList.remove('hidden');
      } else {
        this.setStageState(3, 'failed');
        this.alertTitle.textContent = 'Analysis Failure';
        this.alertText.textContent = 'Analysis could not be completed. ' + (err.message || 'Inspection service is currently unavailable.');
        this.alertBanner.classList.remove('hidden');
        this.errorActions.classList.remove('hidden');
      }
    }
  }

  delay(ms) {
    return new Promise(res => setTimeout(res, ms));
  }
}
