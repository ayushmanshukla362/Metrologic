/**
 * METROLOGIC - Main Application Controller
 * Orchestrates view navigation, persistent shell updates, and module lifecycles.
 */

import { DashboardView } from './dashboard.js';
import { InspectionView } from './inspection.js';
import { ProcessingView } from './processing.js';
import { ResultView } from './result.js';
import { ApiClient } from './api.js';

class AppController {
  constructor() {
    this.currentView = 'dashboard';
    
    // Page Title & Subtitle Elements
    this.pageTitle = document.getElementById('page-title');
    this.pageSubtitle = document.getElementById('page-subtitle');
    this.headerSessionBadge = document.getElementById('header-session-badge');
    this.activeSessionIdEl = document.getElementById('active-session-id');
    this.systemStatusBadge = document.getElementById('system-status-badge');
    this.systemStatusText = document.getElementById('system-status-text');

    // Sidebar Nav Items
    this.navDashboard = document.getElementById('nav-dashboard');
    this.navInspection = document.getElementById('nav-inspection');
    this.sidebar = document.getElementById('sidebar');
    this.mobileToggle = document.getElementById('mobile-toggle');

    // Initialize View Modules
    this.dashboardView = new DashboardView(this);
    this.inspectionView = new InspectionView(this);
    this.processingView = new ProcessingView(this);
    this.resultView = new ResultView(this);

    this.bindEvents();
    this.init();
  }

  bindEvents() {
    // Navigation Listeners
    this.navDashboard.addEventListener('click', (e) => {
      e.preventDefault();
      this.navigateTo('dashboard');
    });

    this.navInspection.addEventListener('click', (e) => {
      e.preventDefault();
      this.navigateTo('inspection');
    });

    // Mobile Sidebar Toggle
    if (this.mobileToggle) {
      this.mobileToggle.addEventListener('click', () => {
        this.sidebar.classList.toggle('open');
      });
    }

    // Hash Navigation Listener
    window.addEventListener('hashchange', () => {
      const hash = window.location.hash.replace('#', '');
      if (['dashboard', 'inspection', 'processing', 'result'].includes(hash)) {
        this.navigateTo(hash, false);
      }
    });
  }

  async init() {
    this.updateStatusBadge();
    
    const initialHash = window.location.hash.replace('#', '') || 'dashboard';
    this.navigateTo(initialHash, false);
  }

  updateStatusBadge() {
    if (ApiClient.isDemoMode()) {
      this.systemStatusBadge.innerHTML = `
        <span class="status-dot dot-demo"></span>
        <span class="status-text">Demo Mode</span>
      `;
    } else {
      this.systemStatusBadge.innerHTML = `
        <span class="status-dot dot-live"></span>
        <span class="status-text">API Connected</span>
      `;
    }
  }

  // Navigate between views
  navigateTo(viewName, updateHash = true) {
    this.currentView = viewName;
    if (updateHash) {
      window.location.hash = viewName;
    }

    // Update active nav link
    if (viewName === 'dashboard') {
      this.navDashboard.classList.add('active');
      this.navInspection.classList.remove('active');
    } else if (viewName === 'inspection') {
      this.navInspection.classList.add('active');
      this.navDashboard.classList.remove('active');
    } else {
      this.navDashboard.classList.remove('active');
      this.navInspection.classList.remove('active');
    }

    // Close mobile sidebar if open
    this.sidebar.classList.remove('open');

    // Hide all view sections
    document.querySelectorAll('.view-section').forEach(sec => {
      sec.classList.remove('active');
    });

    // Show target section
    const targetSec = document.getElementById(`view-${viewName}`);
    if (targetSec) {
      targetSec.classList.add('active');
    }

    // Update Header Title & Subtitle according to section
    switch (viewName) {
      case 'dashboard':
        this.pageTitle.textContent = 'Dashboard';
        this.pageSubtitle.textContent = 'Package inspection overview';
        this.headerSessionBadge.classList.add('hidden');
        this.dashboardView.loadDashboardData();
        break;

      case 'inspection':
        this.pageTitle.textContent = 'Start Inspection';
        this.pageSubtitle.textContent = 'Upload three views of the same package to begin a preliminary compliance assessment.';
        this.headerSessionBadge.classList.add('hidden');
        break;

      case 'processing':
        this.pageTitle.textContent = 'Analyzing Package';
        this.pageSubtitle.textContent = 'MetroLogic is extracting package information and evaluating compliance requirements.';
        break;

      case 'result':
        this.pageTitle.textContent = 'Inspection Result';
        this.pageSubtitle.textContent = 'Package compliance evaluation and evidence audit.';
        this.headerSessionBadge.classList.remove('hidden');
        break;
    }
  }

  // Active Session Badge Manager
  updateHeaderSession(sessionId) {
    this.activeSessionIdEl.textContent = sessionId;
    this.headerSessionBadge.classList.remove('hidden');
  }

  // Trigger processing pipeline
  startProcessing(uploadData) {
    this.navigateTo('processing');
    this.processingView.startProcessingPipeline(uploadData);
  }

  // Open a result returned by the real inspection request, or a demo history
  // result when demo mode is explicitly enabled.
  openInspectionResult(resultOrSession, uploadDataOrScenario = 'scenario2') {
    const isResultPayload = resultOrSession && typeof resultOrSession === 'object';
    const result = isResultPayload
      ? resultOrSession
      : ApiClient.getDemoResult(uploadDataOrScenario);
    const uploadData = isResultPayload ? uploadDataOrScenario : null;

    this.navigateTo('result');
    this.resultView.loadResult(result, uploadData);
  }

  // Handle Image Quality Retry Action
  returnToUploadForReplacement(panelToReplace) {
    this.navigateTo('inspection');
    this.inspectionView.highlightPanelForQuality(panelToReplace);
  }
}

// Bootstrap application on DOM ready
document.addEventListener('DOMContentLoaded', () => {
  window.MetroLogicApp = new AppController();
});
