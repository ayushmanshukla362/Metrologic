/**
 * METROLOGIC - Dashboard View Module
 * Renders summary metrics and interactive inspection history table.
 */

import { ApiClient } from './api.js';

export class DashboardView {
  constructor(appController) {
    this.app = appController;
    this.tableBody = document.getElementById('dashboard-table-body');
    this.btnStart = document.getElementById('btn-dashboard-start');
    
    this.metricTotal = document.getElementById('metric-total');
    this.metricCompleted = document.getElementById('metric-completed');
    this.metricReview = document.getElementById('metric-review');
    this.metricTime = document.getElementById('metric-time');

    this.bindEvents();
  }

  bindEvents() {
    this.btnStart.addEventListener('click', () => {
      this.app.navigateTo('inspection');
    });
  }

  async loadDashboardData() {
    const historyData = await ApiClient.getHistory();

    if (!historyData || historyData.length === 0) {
      // Display '—' when real API metrics unavailable
      this.metricTotal.textContent = '—';
      this.metricCompleted.textContent = '—';
      this.metricReview.textContent = '—';
      this.metricTime.textContent = '—';
      
      this.tableBody.innerHTML = `
        <tr>
          <td colspan="6" class="text-center" style="padding: 30px; color: var(--text-muted);">
            Inspection history will appear here once the history API is connected.
          </td>
        </tr>
      `;
      return;
    }

    // Render Metrics
    const total = historyData.length;
    const completed = historyData.filter(h => h.status === 'PASS').length;
    const review = historyData.filter(h => h.status === 'REVIEW_REQUIRED').length;
    
    this.metricTotal.textContent = total;
    this.metricCompleted.textContent = completed;
    this.metricReview.textContent = review;
    this.metricTime.textContent = '1.7s';

    // Render History Table Rows
    this.tableBody.innerHTML = '';
    historyData.forEach(item => {
      const tr = document.createElement('tr');

      let badgeClass = 'badge-pass';
      if (item.status === 'REVIEW_REQUIRED') badgeClass = 'badge-review';
      if (item.status === 'FAIL') badgeClass = 'badge-fail';

      const isDemo = ApiClient.isDemoMode();

      tr.innerHTML = `
        <td>
          <code class="history-session-id">${item.sessionId}</code>
          ${isDemo ? '<span class="demo-tag-mini">DEMO</span>' : ''}
        </td>
        <td>${item.dateTime}</td>
        <td><span class="product-name">${item.product}</span></td>
        <td><span class="badge ${badgeClass}">${item.status}</span></td>
        <td>${item.processingTime}</td>
        <td class="text-right">
          <button class="btn btn-sm btn-secondary btn-open-history" data-session="${item.sessionId}" data-scenario="${item.scenarioKey || 'scenario2'}">
            Open Inspection
          </button>
        </td>
      `;

      tr.querySelector('.btn-open-history').addEventListener('click', (e) => {
        const session = e.currentTarget.getAttribute('data-session');
        const scenarioKey = e.currentTarget.getAttribute('data-scenario');
        this.app.openInspectionResult(session, scenarioKey);
      });

      this.tableBody.appendChild(tr);
    });
  }
}
