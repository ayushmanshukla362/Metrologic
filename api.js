/**
 * METROLOGIC - API Client Layer
 * Real backend communication plus explicitly enabled standalone demo fixtures.
 */

import { DEMO_SCENARIOS, DEMO_HISTORY } from './demo-data.js';

export const API_BASE_URL = window.METROLOGIC_API_URL || "http://localhost:8000";

// Demo mode is opt-in. Set window.METROLOGIC_DEMO_MODE = true before app.js loads
// when running the standalone demo fixtures.
if (window.METROLOGIC_DEMO_MODE === undefined) {
  window.METROLOGIC_DEMO_MODE = false;
}

export class ApiError extends Error {
  constructor(message, status = 0, details = null) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.details = details;
    this.code = status >= 500 ? 'BACKEND_ERROR' : status >= 400 ? 'INVALID_INPUT' : 'NETWORK_ERROR';
  }
}

export class ApiClient {
  static isDemoMode() {
    return !!window.METROLOGIC_DEMO_MODE;
  }

  // Resolve image URLs (local data URLs, full URLs, or relative backend URLs).
  static resolveImageUrl(url) {
    if (!url) return '';
    if (url.startsWith('data:') || url.startsWith('http://') || url.startsWith('https://') || url.startsWith('blob:')) {
      return url;
    }
    return `${API_BASE_URL.replace(/\/$/, '')}/${url.replace(/^\//, '')}`;
  }

  /**
   * Submit exactly one selected image to the frozen backend contract.
   * Demo mode is intentionally not handled here; the real flow must never
   * replace a backend response with demo data.
   */
  static async runInspection(file) {
    const formData = new FormData();
    formData.append('file', file);

    let response;
    try {
      response = await fetch(`${API_BASE_URL.replace(/\/$/, '')}/api/inspection`, {
        method: 'POST',
        body: formData
      });
    } catch (error) {
      throw new ApiError('The inspection service is currently unavailable. Please try again.', 0, error);
    }

    const payload = await response.json().catch(() => ({}));
    if (!response.ok) {
      if (response.status >= 500) {
        throw new ApiError('The inspection service could not process this image. Please try again.', response.status, payload);
      }
      if (response.status >= 400) {
        throw new ApiError('This image could not be accepted. Please upload a valid package image and try again.', response.status, payload);
      }
      throw new ApiError(`Inspection request failed (HTTP ${response.status}).`, response.status, payload);
    }

    return payload;
  }

  // Demo-only result loader. This path is used only when the user explicitly
  // enables METROLOGIC_DEMO_MODE.
  static getDemoResult(scenarioKey = 'scenario2') {
    const scenario = DEMO_SCENARIOS[scenarioKey] || DEMO_SCENARIOS.scenario2;
    return {
      session_id: scenario.sessionId,
      overall_status: scenario.status,
      processing_time: scenario.processingTime,
      product: scenario.product,
      images: scenario.images,
      rules: scenario.rules
    };
  }

  // History is available only for the standalone demo until a history
  // endpoint is included in the frozen backend contract.
  static async getHistory() {
    return this.isDemoMode() ? DEMO_HISTORY : null;
  }
}
