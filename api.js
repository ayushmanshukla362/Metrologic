/**
 * METROLOGIC - API Client Layer
 * Centralized network communication module with DEMO_MODE fallback capability
 */

import { DEMO_SCENARIOS, DEMO_HISTORY } from './demo-data.js';

export const API_BASE_URL = window.METROLOGIC_API_URL || "http://localhost:8000";

// Global Demo Mode Toggle (Defaults to true for standalone hackathon prototype)
if (window.METROLOGIC_DEMO_MODE === undefined) {
  window.METROLOGIC_DEMO_MODE = true;
}

export class ApiClient {
  static isDemoMode() {
    return !!window.METROLOGIC_DEMO_MODE;
  }

  // Resolve image URLs (local data URLs, full URLs, or relative backend URLs)
  static resolveImageUrl(url) {
    if (!url) return '';
    if (url.startsWith('data:') || url.startsWith('http://') || url.startsWith('https://') || url.startsWith('blob:')) {
      return url;
    }
    return `${API_BASE_URL.replace(/\/$/, '')}/${url.replace(/^\//, '')}`;
  }

  // Session Initialization
  static async initSession() {
    if (this.isDemoMode()) {
      const demoId = `ML-2026-${Math.floor(10000 + Math.random() * 90000)}`;
      return { session_id: demoId, status: "created" };
    }

    try {
      const res = await fetch(`${API_BASE_URL}/api/session/init`, { method: "POST" });
      if (!res.ok) throw new Error(`HTTP Error ${res.status}`);
      return await res.json();
    } catch (err) {
      console.warn("Backend unavailable, falling back to Demo Mode:", err);
      window.METROLOGIC_DEMO_MODE = true;
      const demoId = `ML-2026-${Math.floor(10000 + Math.random() * 90000)}`;
      return { session_id: demoId, status: "created" };
    }
  }

  // Upload Panel Image
  static async uploadImage(sessionId, panelType, file) {
    if (this.isDemoMode()) {
      return {
        session_id: sessionId,
        panel: panelType,
        filename: file.name || `${panelType}_panel.jpg`,
        status: "uploaded"
      };
    }

    const formData = new FormData();
    formData.append("image", file);
    formData.append("panel", panelType);

    const res = await fetch(`${API_BASE_URL}/api/session/${sessionId}/upload`, {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      const errorJson = await res.json().catch(() => ({}));
      if (res.status === 422 || errorJson.code === "IMAGE_UNUSABLE") {
        const error = new Error(errorJson.message || "Image quality is insufficient for reliable analysis.");
        error.code = "IMAGE_UNUSABLE";
        error.panel = panelType;
        throw error;
      }
      throw new Error(`Upload failed: ${res.statusText}`);
    }

    return await res.json();
  }

  // Trigger Analysis
  static async analyzeSession(sessionId, activeScenario = "scenario2") {
    if (this.isDemoMode()) {
      return { session_id: sessionId, status: "processing" };
    }

    const res = await fetch(`${API_BASE_URL}/api/session/${sessionId}/analyze`, {
      method: "POST"
    });

    if (!res.ok) throw new Error(`Analysis failed to start: ${res.statusText}`);
    return await res.json();
  }

  // Retrieve Inspection Result
  static async getResult(sessionId, activeScenarioKey = "scenario2") {
    if (this.isDemoMode()) {
      const scenario = DEMO_SCENARIOS[activeScenarioKey] || DEMO_SCENARIOS.scenario2;
      return {
        session_id: sessionId,
        status: scenario.status,
        processing_time: scenario.processingTime,
        product: scenario.product,
        images: scenario.images,
        rules: scenario.rules
      };
    }

    const res = await fetch(`${API_BASE_URL}/api/session/${sessionId}/result`);
    if (!res.ok) throw new Error(`Could not fetch result: ${res.statusText}`);
    const data = await res.json();

    // Standardize backend response schema
    return {
      session_id: data.session_id || sessionId,
      status: data.status || "REVIEW_REQUIRED",
      processing_time: data.processing_time || "1.5s",
      product: data.product || "Packaged Commodity",
      images: {
        front: { url: this.resolveImageUrl(data.images?.front?.url) },
        back: { url: this.resolveImageUrl(data.images?.back?.url) },
        side: { url: this.resolveImageUrl(data.images?.side?.url) }
      },
      rules: data.rules || []
    };
  }

  // Retrieve Specific Field Evidence
  static async getEvidence(sessionId, field) {
    if (this.isDemoMode()) {
      const scenario = DEMO_SCENARIOS.scenario2;
      const rule = scenario.rules.find(r => r.id === field || r.name.toLowerCase().includes(field.toLowerCase()));
      return rule || null;
    }

    const res = await fetch(`${API_BASE_URL}/api/session/${sessionId}/evidence/${field}`);
    if (!res.ok) throw new Error(`Could not fetch evidence for ${field}`);
    return await res.json();
  }

  // Fetch Inspection History
  static async getHistory() {
    if (this.isDemoMode()) {
      return DEMO_HISTORY;
    }

    try {
      const res = await fetch(`${API_BASE_URL}/api/history`);
      if (!res.ok) return null;
      return await res.json();
    } catch {
      return null;
    }
  }
}
