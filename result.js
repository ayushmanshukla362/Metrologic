/**
 * METROLOGIC - Inspection Result & Evidence Drawer View Module
 * Renders compliance summary, 5 rule cards, extracted fields table,
 * and orchestrates interactive evidence bounding box navigation & slide-over drawer.
 */

import { ApiClient } from './api.js';
import { EvidenceOverlay } from './evidence.js';

export class ResultView {
  constructor(appController) {
    this.app = appController;
    this.currentResult = null;
    this.activePanel = 'back';
    this.activeRuleId = null;

    // Left Viewer Elements
    this.viewport = document.getElementById('image-viewport');
    this.stage = document.getElementById('viewport-stage');
    this.img = document.getElementById('result-package-img');
    this.overlayLayer = document.getElementById('evidence-overlay-layer');
    this.activePanelTag = document.getElementById('active-panel-name');
    this.boundingStatusText = document.getElementById('bounding-status-text');

    // Overlay Engine Instance
    this.evidenceOverlay = new EvidenceOverlay(
      this.viewport,
      this.stage,
      this.img,
      this.overlayLayer
    );

    // Zoom Controls
    this.btnZoomIn = document.getElementById('btn-zoom-in');
    this.btnZoomOut = document.getElementById('btn-zoom-out');
    this.btnZoomFit = document.getElementById('btn-zoom-fit');
    this.btnZoomReset = document.getElementById('btn-zoom-reset');

    // Right Column Elements
    this.overallBanner = document.getElementById('overall-status-banner');
    this.overallIcon = document.getElementById('overall-status-icon');
    this.overallTitle = document.getElementById('overall-status-title');
    this.overallDesc = document.getElementById('overall-status-desc');
    this.resultSessionId = document.getElementById('result-session-id');
    this.resultProcTime = document.getElementById('result-proc-time');

    this.ruleCardsContainer = document.getElementById('rule-cards-container');
    this.extractedFieldsBody = document.getElementById('extracted-fields-body');

    // Evidence Drawer Elements
    this.drawerBackdrop = document.getElementById('drawer-backdrop');
    this.drawer = document.getElementById('evidence-drawer');
    this.btnCloseDrawer = document.getElementById('btn-close-drawer');
    this.btnDrawerOpenImage = document.getElementById('btn-drawer-open-image');

    this.drawerFieldName = document.getElementById('drawer-field-name');
    this.drawerExtractedVal = document.getElementById('drawer-extracted-val');
    this.drawerConfidenceBadge = document.getElementById('drawer-confidence-badge');
    this.drawerStatusBadge = document.getElementById('drawer-status-badge');
    this.drawerSourcePanel = document.getElementById('drawer-source-panel');
    this.drawerRawOcr = document.getElementById('drawer-raw-ocr');
    this.drawerReason = document.getElementById('drawer-reason');
    this.drawerEvidenceId = document.getElementById('drawer-evidence-id');

    this.bindEvents();
  }

  bindEvents() {
    // Viewer Tab Switching
    ['front', 'back', 'side'].forEach(panel => {
      const tabBtn = document.getElementById(`tab-${panel}`);
      tabBtn.addEventListener('click', () => {
        this.switchPanel(panel);
      });
    });

    // Zoom Buttons
    this.btnZoomIn.addEventListener('click', () => this.evidenceOverlay.zoomIn());
    this.btnZoomOut.addEventListener('click', () => this.evidenceOverlay.zoomOut());
    this.btnZoomFit.addEventListener('click', () => this.evidenceOverlay.resetZoom());
    this.btnZoomReset.addEventListener('click', () => this.evidenceOverlay.resetZoom());

    // Evidence Box Click Event
    this.evidenceOverlay.setOnBoxClick((boxItem) => {
      this.openEvidenceDrawer(boxItem.ruleId);
    });

    // Drawer Controls
    this.btnCloseDrawer.addEventListener('click', () => this.closeDrawer());
    this.drawerBackdrop.addEventListener('click', () => this.closeDrawer());
    
    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape' && !this.drawer.classList.contains('hidden')) {
        this.closeDrawer();
      }
    });

    this.btnDrawerOpenImage.addEventListener('click', () => {
      this.closeDrawer();
      if (this.activeRuleId) {
        this.evidenceOverlay.focusRegion(this.activeRuleId);
      }
    });
  }

  // Load inspection result data
  async loadResult(sessionId, scenarioKey = 'scenario2') {
    const result = await ApiClient.getResult(sessionId, scenarioKey);
    this.currentResult = result;

    this.app.updateHeaderSession(sessionId);

    // Render Overall Status
    this.renderOverallStatus(result.status);
    this.resultSessionId.textContent = result.session_id;
    this.resultProcTime.textContent = result.processing_time || '1.8s';

    // Render 5 Rule Cards
    this.renderRuleCards(result.rules);

    // Render Extracted Information Table
    this.renderExtractedFields(result.rules);

    // Default to Back Panel
    this.switchPanel('back');
  }

  renderOverallStatus(status) {
    this.overallBanner.className = 'summary-status-banner';

    if (status === 'PASS') {
      this.overallBanner.classList.add('status-banner-pass');
      this.overallIcon.textContent = '✓';
      this.overallTitle.textContent = 'PASS';
      this.overallDesc.textContent = 'All selected requirements appear satisfied based on available evidence.';
    } else if (status === 'REVIEW_REQUIRED') {
      this.overallBanner.classList.add('status-banner-review');
      this.overallIcon.textContent = '⚠️';
      this.overallTitle.textContent = 'REVIEW_REQUIRED';
      this.overallDesc.textContent = 'One or more requirements require officer verification.';
    } else {
      this.overallBanner.classList.add('status-banner-fail');
      this.overallIcon.textContent = '✕';
      this.overallTitle.textContent = 'FAIL';
      this.overallDesc.textContent = 'One or more selected requirements appear violated based on available evidence.';
    }
  }

  // Render 5 Legal Metrology Check Cards
  renderRuleCards(rules) {
    this.ruleCardsContainer.innerHTML = '';

    rules.forEach(rule => {
      let badgeClass = 'badge-pass';
      if (rule.status === 'REVIEW_REQUIRED') badgeClass = 'badge-review';
      if (rule.status === 'FAIL') badgeClass = 'badge-fail';

      const card = document.createElement('div');
      card.className = `rule-card ${rule.id === this.activeRuleId ? 'active-selected' : ''}`;
      card.id = `rule-card-${rule.id}`;

      card.innerHTML = `
        <div class="rule-card-header">
          <span class="rule-name">${rule.name}</span>
          <span class="badge ${badgeClass}">${rule.status}</span>
        </div>
        <p class="rule-reason">${rule.reason || rule.requirement}</p>
      `;

      card.addEventListener('click', () => {
        this.selectRule(rule.id);
      });

      this.ruleCardsContainer.appendChild(card);
    });
  }

  // Render Extracted Information Table
  renderExtractedFields(rules) {
    this.extractedFieldsBody.innerHTML = '';

    rules.forEach(rule => {
      const tr = document.createElement('tr');
      const confPct = Math.round((rule.confidence || 0.95) * 100);

      tr.innerHTML = `
        <td class="text-bold">${rule.name}</td>
        <td>${rule.extractedValue || 'Not detected'}</td>
        <td><span class="conf-pill">${confPct}%</span></td>
        <td><span class="badge badge-pass" style="background:#f1f5f9; color:#475569; border-color:#cbd5e1;">${(rule.panel || 'back').toUpperCase()}</span></td>
      `;

      tr.addEventListener('click', () => {
        this.selectRule(rule.id);
      });

      this.extractedFieldsBody.appendChild(tr);
    });
  }

  // Select a rule -> switch panel, render overlay bounding box, focus, and open drawer
  selectRule(ruleId) {
    this.activeRuleId = ruleId;
    
    // Highlight active card
    document.querySelectorAll('.rule-card').forEach(c => c.classList.remove('active-selected'));
    const targetCard = document.getElementById(`rule-card-${ruleId}`);
    if (targetCard) targetCard.classList.add('active-selected');

    const rule = this.currentResult.rules.find(r => r.id === ruleId);
    if (!rule) return;

    const sourcePanel = rule.panel || 'back';
    
    // Switch viewer tab to source panel if needed
    if (this.activePanel !== sourcePanel) {
      this.switchPanel(sourcePanel, ruleId);
    } else {
      this.evidenceOverlay.focusRegion(ruleId);
    }

    this.openEvidenceDrawer(ruleId);
  }

  // Switch image viewer tab (FRONT / BACK / SIDE)
  switchPanel(panel, focusRuleId = null) {
    this.activePanel = panel;

    // Update tab UI
    ['front', 'back', 'side'].forEach(p => {
      const tabBtn = document.getElementById(`tab-${p}`);
      if (p === panel) tabBtn.classList.add('active');
      else tabBtn.classList.remove('active');
    });

    this.activePanelTag.textContent = `Panel: ${panel.toUpperCase()} PANEL`;

    if (!this.currentResult || !this.currentResult.images[panel]) return;

    const imageUrl = this.currentResult.images[panel].url;
    
    // Filter rules belonging to this panel
    const panelBoxes = this.currentResult.rules
      .filter(r => (r.panel || 'back') === panel)
      .map(r => ({
        ruleId: r.id,
        ruleName: r.name,
        box: r.box,
        label: r.name
      }));

    this.evidenceOverlay.setPanelData(imageUrl, panelBoxes, focusRuleId || this.activeRuleId);

    if (focusRuleId || this.activeRuleId) {
      setTimeout(() => {
        this.evidenceOverlay.focusRegion(focusRuleId || this.activeRuleId);
      }, 100);
    }
  }

  // Slide open Evidence Detail Drawer
  openEvidenceDrawer(ruleId) {
    const rule = this.currentResult.rules.find(r => r.id === ruleId);
    if (!rule) return;

    const confPct = Math.round((rule.confidence || 0.95) * 100);

    this.drawerFieldName.textContent = rule.name;
    this.drawerExtractedVal.textContent = rule.extractedValue || 'Not detected';
    this.drawerConfidenceBadge.textContent = `${confPct}%`;
    
    let statusClass = 'badge-pass';
    if (rule.status === 'REVIEW_REQUIRED') statusClass = 'badge-review';
    if (rule.status === 'FAIL') statusClass = 'badge-fail';

    this.drawerStatusBadge.className = `badge ${statusClass}`;
    this.drawerStatusBadge.textContent = rule.status;

    this.drawerSourcePanel.textContent = `${(rule.panel || 'back').toUpperCase()} PANEL`;
    this.drawerRawOcr.textContent = rule.rawOcr || rule.extractedValue || '—';
    this.drawerReason.textContent = rule.reason || rule.requirement;
    this.drawerEvidenceId.textContent = rule.evidenceId || `block_${rule.id}`;

    this.drawerBackdrop.classList.remove('hidden');
    this.drawer.classList.remove('hidden');
  }

  closeDrawer() {
    this.drawerBackdrop.classList.add('hidden');
    this.drawer.classList.add('hidden');
  }
}
