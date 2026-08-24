/**
 * METROLOGIC - Inspection Result & Evidence Drawer View Module
 * Renders the existing result UI against the frozen inspection response.
 */

import { ApiClient } from './api.js';
import { EvidenceOverlay } from './evidence.js';

const FIELD_DEFINITIONS = [
  ['commodity_name', 'Commodity Name'],
  ['net_quantity', 'Net Quantity'],
  ['mfg_date', 'Manufacturing Date'],
  ['mrp', 'MRP'],
  ['manufacturer', 'Manufacturer']
];

export class ResultView {
  constructor(appController) {
    this.app = appController;
    this.currentResult = null;
    this.activePanel = 'back';
    this.activeRuleId = null;

    this.viewport = document.getElementById('image-viewport');
    this.stage = document.getElementById('viewport-stage');
    this.img = document.getElementById('result-package-img');
    this.overlayLayer = document.getElementById('evidence-overlay-layer');
    this.activePanelTag = document.getElementById('active-panel-name');
    this.boundingStatusText = document.getElementById('bounding-status-text');

    this.evidenceOverlay = new EvidenceOverlay(this.viewport, this.stage, this.img, this.overlayLayer);

    this.btnZoomIn = document.getElementById('btn-zoom-in');
    this.btnZoomOut = document.getElementById('btn-zoom-out');
    this.btnZoomFit = document.getElementById('btn-zoom-fit');
    this.btnZoomReset = document.getElementById('btn-zoom-reset');

    this.overallBanner = document.getElementById('overall-status-banner');
    this.overallIcon = document.getElementById('overall-status-icon');
    this.overallTitle = document.getElementById('overall-status-title');
    this.overallDesc = document.getElementById('overall-status-desc');
    this.resultSessionId = document.getElementById('result-session-id');
    this.resultProcTime = document.getElementById('result-proc-time');
    this.ruleCardsContainer = document.getElementById('rule-cards-container');
    this.extractedFieldsBody = document.getElementById('extracted-fields-body');

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
    ['front', 'back', 'side'].forEach(panel => {
      document.getElementById(`tab-${panel}`).addEventListener('click', () => this.switchPanel(panel));
    });

    this.btnZoomIn.addEventListener('click', () => this.evidenceOverlay.zoomIn());
    this.btnZoomOut.addEventListener('click', () => this.evidenceOverlay.zoomOut());
    this.btnZoomFit.addEventListener('click', () => this.evidenceOverlay.resetZoom());
    this.btnZoomReset.addEventListener('click', () => this.evidenceOverlay.resetZoom());
    this.evidenceOverlay.setOnBoxClick(boxItem => this.openEvidenceDrawer(boxItem.ruleId));

    this.btnCloseDrawer.addEventListener('click', () => this.closeDrawer());
    this.drawerBackdrop.addEventListener('click', () => this.closeDrawer());
    document.addEventListener('keydown', e => {
      if (e.key === 'Escape' && !this.drawer.classList.contains('hidden')) this.closeDrawer();
    });
    this.btnDrawerOpenImage.addEventListener('click', () => {
      this.closeDrawer();
      if (this.activeRuleId) this.evidenceOverlay.focusRegion(this.activeRuleId);
    });
  }

  /** Load and normalize a backend response, retaining local selected images. */
  loadResult(result, uploadData = null) {
    const response = result && typeof result === 'object'
      ? result
      : ApiClient.getDemoResult(result || 'scenario2');

    this.currentResult = this.normalizeResult(response, uploadData);
    this.activeRuleId = null;
    this.activePanel = uploadData?.activePanel || 'back';

    this.app.updateHeaderSession(this.currentResult.session_id);
    this.renderOverallStatus(this.currentResult.overall_status);
    this.resultSessionId.textContent = this.currentResult.session_id || '—';
    this.resultProcTime.textContent = this.currentResult.processing_time || '—';
    this.renderRuleCards(this.currentResult.rules);
    this.renderExtractedFields(this.currentResult.extracted_fields, this.currentResult.confidence);
    this.switchPanel(this.activePanel);
  }

  normalizeResult(response, uploadData) {
    const extractedFields = response.extracted_fields || this.deriveDemoFields(response.rules || []);
    const confidence = response.confidence || {};
    const sourceImages = uploadData?.panels || {};
    const responseImages = response.images || {};
    const images = {};

    ['front', 'back', 'side'].forEach(panel => {
      const backendUrl = responseImages[panel]?.url;
      const localUrl = sourceImages[panel]?.previewUrl;
      images[panel] = { url: backendUrl ? ApiClient.resolveImageUrl(backendUrl) : (localUrl || '') };
    });

    const rawRules = response.compliance_evaluations || response.evaluations || response.rules || [];
    const rules = rawRules.map((rawRule, index) => this.normalizeRule(rawRule, extractedFields, confidence, index));

    return {
      session_id: response.session_id || '—',
      overall_status: response.overall_status || response.status || 'REVIEW_REQUIRED',
      processing_time: response.processing_time || null,
      extracted_fields: extractedFields,
      confidence,
      rules,
      images
    };
  }

  deriveDemoFields(rules) {
    const fields = {};
    rules.forEach(rule => {
      const text = `${rule.id || ''} ${rule.name || ''}`.toLowerCase();
      const fieldKey = FIELD_DEFINITIONS.find(([key, label]) => text.includes(key) || text.includes(label.toLowerCase()))?.[0];
      if (!fieldKey) return;
      fields[fieldKey] = {
        value: rule.extractedValue,
        confidence: rule.confidence,
        raw_source: rule.rawOcr,
        source_block_ids: rule.evidenceId ? [rule.evidenceId] : []
      };
    });
    return fields;
  }

  normalizeRule(rawRule, extractedFields, confidenceByField, index) {
    const id = rawRule.rule_id || rawRule.id || `rule-${index + 1}`;
    const fieldKey = FIELD_DEFINITIONS.find(([key]) => id.toLowerCase().includes(key))?.[0]
      || FIELD_DEFINITIONS.find(([key, label]) => `${rawRule.requirement || ''} ${rawRule.name || ''}`.toLowerCase().includes(key.replace('_', ' ')) || `${rawRule.requirement || ''} ${rawRule.name || ''}`.toLowerCase().includes(label.toLowerCase()))?.[0]
      || null;
    const field = fieldKey ? extractedFields[fieldKey] || {} : {};
    const evidence = Array.isArray(rawRule.evidence) ? rawRule.evidence : [];
    const evidenceGeometry = evidence.find(item => item && typeof item === 'object' && (item.box || item.bbox || item.coordinates));

    return {
      id,
      fieldKey,
      name: rawRule.name || (fieldKey && this.fieldLabel(fieldKey)) || rawRule.requirement || id,
      requirement: rawRule.requirement || 'Requirement details were not provided.',
      status: rawRule.status || 'REVIEW_REQUIRED',
      reason: rawRule.reason || '',
      evidence,
      evidenceText: this.formatEvidence(evidence),
      confidence: typeof field.confidence === 'number' ? field.confidence : (typeof confidenceByField[fieldKey] === 'number' ? confidenceByField[fieldKey] : (typeof rawRule.confidence === 'number' ? rawRule.confidence : null)),
      panel: rawRule.panel || null,
      box: rawRule.box || evidenceGeometry?.box || evidenceGeometry?.bbox || evidenceGeometry?.coordinates || null,
      extractedValue: this.formatFieldValue(field.value, field.unit),
      rawOcr: field.raw_source || rawRule.rawOcr || null,
      sourceBlockIds: Array.isArray(field.source_block_ids) ? field.source_block_ids : []
    };
  }

  fieldLabel(fieldKey) {
    return FIELD_DEFINITIONS.find(([key]) => key === fieldKey)?.[1] || fieldKey;
  }

  formatFieldValue(value, unit = '') {
    if (value === undefined || value === null || value === '') return 'Not detected';
    const valueText = typeof value === 'object' ? JSON.stringify(value) : String(value);
    return unit ? `${valueText} ${unit}` : valueText;
  }

  formatConfidence(confidence) {
    return typeof confidence === 'number' ? `${Math.round(confidence * 100)}%` : '—';
  }

  formatEvidence(evidence) {
    if (!Array.isArray(evidence) || evidence.length === 0) return '—';
    return evidence.map(item => typeof item === 'string' ? item : JSON.stringify(item)).join(', ');
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

  statusClass(status) {
    if (status === 'REVIEW_REQUIRED') return 'badge-review';
    if (status === 'FAIL') return 'badge-fail';
    return 'badge-pass';
  }

  renderRuleCards(rules) {
    this.ruleCardsContainer.innerHTML = '';
    rules.forEach(rule => {
      const card = document.createElement('div');
      card.className = `rule-card ${rule.id === this.activeRuleId ? 'active-selected' : ''}`;
      card.id = `rule-card-${rule.id}`;

      const header = document.createElement('div');
      header.className = 'rule-card-header';
      const name = document.createElement('span');
      name.className = 'rule-name';
      name.textContent = rule.name;
      const badge = document.createElement('span');
      badge.className = `badge ${this.statusClass(rule.status)}`;
      badge.textContent = rule.status;
      header.append(name, badge);

      const requirement = document.createElement('p');
      requirement.className = 'rule-requirement';
      requirement.textContent = rule.requirement;
      const reason = document.createElement('p');
      reason.className = 'rule-reason';
      reason.textContent = rule.reason || 'No additional reason provided.';
      const evidence = document.createElement('p');
      evidence.className = 'rule-evidence';
      evidence.textContent = `Evidence: ${rule.evidenceText}`;

      card.append(header, requirement, reason, evidence);
      card.addEventListener('click', () => this.selectRule(rule.id));
      this.ruleCardsContainer.appendChild(card);
    });
  }

  renderExtractedFields(fields, confidenceByField = {}) {
    this.extractedFieldsBody.innerHTML = '';
    FIELD_DEFINITIONS.forEach(([key, label]) => {
      const field = fields[key] || {};
      const tr = document.createElement('tr');
      const value = this.formatFieldValue(field.value, field.unit);
      const confidence = this.formatConfidence(typeof field.confidence === 'number' ? field.confidence : confidenceByField[key]);
      const rawSource = field.raw_source || '—';
      const sourceIds = Array.isArray(field.source_block_ids) && field.source_block_ids.length
        ? field.source_block_ids.join(', ')
        : '—';

      const fieldCell = document.createElement('td');
      fieldCell.className = 'text-bold';
      fieldCell.textContent = label;
      const valueCell = document.createElement('td');
      valueCell.textContent = value;
      const confidenceCell = document.createElement('td');
      const confidencePill = document.createElement('span');
      confidencePill.className = 'conf-pill';
      confidencePill.textContent = confidence;
      confidenceCell.appendChild(confidencePill);
      const sourceCell = document.createElement('td');
      sourceCell.innerHTML = `<div>Raw: ${this.escapeHtml(rawSource)}</div><div>Blocks: ${this.escapeHtml(sourceIds)}</div>`;

      tr.append(fieldCell, valueCell, confidenceCell, sourceCell);
      const matchingRule = this.currentResult.rules.find(rule => rule.fieldKey === key);
      if (matchingRule) tr.addEventListener('click', () => this.selectRule(matchingRule.id));
      this.extractedFieldsBody.appendChild(tr);
    });
  }

  escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, char => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' }[char]));
  }

  selectRule(ruleId) {
    this.activeRuleId = ruleId;
    document.querySelectorAll('.rule-card').forEach(card => card.classList.remove('active-selected'));
    const targetCard = document.getElementById(`rule-card-${ruleId}`);
    if (targetCard) targetCard.classList.add('active-selected');

    const rule = this.currentResult.rules.find(item => item.id === ruleId);
    if (!rule) return;

    if (rule.panel && this.activePanel !== rule.panel) {
      this.switchPanel(rule.panel, ruleId);
    } else if (rule.box) {
      this.evidenceOverlay.focusRegion(ruleId);
    }
    this.openEvidenceDrawer(ruleId);
  }

  switchPanel(panel, focusRuleId = null) {
    this.activePanel = panel;
    ['front', 'back', 'side'].forEach(item => {
      const tabBtn = document.getElementById(`tab-${item}`);
      if (item === panel) tabBtn.classList.add('active');
      else tabBtn.classList.remove('active');
    });
    this.activePanelTag.textContent = `Panel: ${panel.toUpperCase()} PANEL`;

    const image = this.currentResult?.images?.[panel];
    const imageUrl = image?.url || '';
    const panelBoxes = (this.currentResult?.rules || [])
      .filter(rule => rule.panel === panel && rule.box)
      .map(rule => ({ ruleId: rule.id, ruleName: rule.name, box: rule.box, label: rule.name }));

    if (!imageUrl) {
      this.evidenceOverlay.setPanelData('', [], null);
      this.boundingStatusText.textContent = 'No image was supplied for this panel.';
      return;
    }

    this.boundingStatusText.textContent = panelBoxes.length
      ? 'Click any rule check or extracted field to focus evidence.'
      : 'Evidence references are available; image geometry was not provided by the backend.';
    this.evidenceOverlay.setPanelData(imageUrl, panelBoxes, focusRuleId || this.activeRuleId);
    if ((focusRuleId || this.activeRuleId) && panelBoxes.length) {
      setTimeout(() => this.evidenceOverlay.focusRegion(focusRuleId || this.activeRuleId), 100);
    }
  }

  openEvidenceDrawer(ruleId) {
    const rule = this.currentResult.rules.find(item => item.id === ruleId);
    if (!rule) return;

    this.drawerFieldName.textContent = rule.name;
    this.drawerExtractedVal.textContent = rule.extractedValue;
    this.drawerConfidenceBadge.textContent = this.formatConfidence(rule.confidence);
    this.drawerStatusBadge.className = `badge ${this.statusClass(rule.status)}`;
    this.drawerStatusBadge.textContent = rule.status;
    this.drawerSourcePanel.textContent = rule.panel ? `${rule.panel.toUpperCase()} PANEL` : 'Not provided';
    this.drawerRawOcr.textContent = rule.rawOcr || '—';
    this.drawerReason.textContent = rule.reason || rule.requirement;
    this.drawerEvidenceId.textContent = rule.sourceBlockIds.length
      ? rule.sourceBlockIds.join(', ')
      : rule.evidenceText;

    this.drawerBackdrop.classList.remove('hidden');
    this.drawer.classList.remove('hidden');
  }

  closeDrawer() {
    this.drawerBackdrop.classList.add('hidden');
    this.drawer.classList.add('hidden');
  }
}
