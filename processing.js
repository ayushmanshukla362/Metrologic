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
      const activePanel = uploadData.activePanel || ['front', 'back', 'side'].find(panel => uploadData.panels[panel]?.file);
      const selectedFile = activePanel ? uploadData.panels[activePanel]?.file : null;

      if (!selectedFile) {
        const validationError = new Error('Please select an image before running analysis.');
        validationError.code = 'INVALID_INPUT';
        throw validationError;
      }

      // Stage 1: Selected image ready
      this.setStageState(0, 'processing');
      this.setStageState(0, 'completed');

      let result;

      if (ApiClient.isDemoMode()) {
        // Standalone demo mode remains fixture-driven and never calls the API.
        this.setStageState(1, 'processing');
        await this.delay(350);
        result = ApiClient.getDemoResult(uploadData.scenarioKey);
      } else {
        // Real MVP flow: submit only the currently active panel's file.
        this.setStageState(1, 'processing');
        result = await ApiClient.runInspection(selectedFile);
      }
      await this.delay(150);
      this.setStageState(1, 'completed');

      // The backend performs the remaining extraction/evaluation stages in
      // one request. Keep the existing checklist animation for continuity.
      this.setStageState(2, 'processing');
      await this.delay(300);
      this.setStageState(2, 'completed');

      this.setStageState(3, 'processing');
      await this.delay(200);
      this.setStageState(3, 'completed');

      this.setStageState(4, 'processing');
      await this.delay(180);
      this.setStageState(4, 'completed');

      this.setStageState(5, 'processing');
      await this.delay(180);
      this.setStageState(5, 'completed');

      // Completed -> Navigate to Result
      await this.delay(200);
      this.app.openInspectionResult(result, uploadData);

    } catch (err) {
      this.spinner.style.display = 'none';

      if (err.status === 400 || err.code === 'INVALID_INPUT') {
        this.setStageState(0, 'failed');
        this.alertTitle.textContent = 'Invalid Image or Input';
        this.alertText.textContent = err.message || 'Please select a valid package image and try again.';
        this.alertBanner.classList.remove('hidden');
      } else {
        this.setStageState(1, 'failed');
        this.alertTitle.textContent = err.status >= 500 ? 'Backend Processing Error' : 'Analysis Failure';
        this.alertText.textContent = err.message || 'Inspection service is currently unavailable. Please try again.';
        this.alertBanner.classList.remove('hidden');
        this.errorActions.classList.remove('hidden');
      }
    }
  }

  delay(ms) {
    return new Promise(res => setTimeout(res, ms));
  }
}
