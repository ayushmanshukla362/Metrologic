import test from 'node:test';
import assert from 'node:assert/strict';

globalThis.window = {
  METROLOGIC_API_URL: 'http://localhost:8000',
  METROLOGIC_DEMO_MODE: false
};

const { ApiClient } = await import('../api.js');
const { InspectionView } = await import('../inspection.js');
const { ResultView } = await import('../result.js');

const backendPayload = {
  session_id: 'sess_test',
  overall_status: 'REVIEW_REQUIRED',
  extracted_fields: {
    commodity_name: { value: 'Tea', raw_source: 'Commodity: Tea', source_block_ids: ['img:block-1'], confidence: 0.91 },
    net_quantity: { value: 125, unit: 'g', raw_source: '125 g', source_block_ids: ['img:block-2'], confidence: 0.88 },
    mfg_date: { value: '01/2026', raw_source: 'Mfg: 01/2026', source_block_ids: ['img:block-3'], confidence: 0.84 },
    mrp: { value: 449, unit: 'INR', raw_source: '449.00', source_block_ids: ['img:block-4'], confidence: 0.63 },
    manufacturer: { value: 'Example Foods', raw_source: 'Mfd: Example Foods', source_block_ids: ['img:block-5'], confidence: 0.95 }
  },
  confidence: { commodity_name: 0.91, net_quantity: 0.88, mfg_date: 0.84, mrp: 0.63, manufacturer: 0.95 },
  compliance_evaluations: [
    {
      rule_id: 'mrp_declaration',
      requirement: 'Maximum Retail Price must be declared.',
      status: 'REVIEW_REQUIRED',
      reason: 'Low-confidence extraction.',
      evidence: ['img:block-4']
    }
  ],
  errors: []
};

function response(status, body) {
  return {
    ok: status >= 200 && status < 300,
    status,
    json: async () => body
  };
}

async function withFetch(fakeFetch, callback) {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = fakeFetch;
  try {
    return await callback();
  } finally {
    globalThis.fetch = originalFetch;
  }
}

test('runInspection creates FormData with the exact file key', async () => {
  let captured;
  const file = new File(['image'], 'front.jpg', { type: 'image/jpeg' });
  await withFetch(async (_url, options) => {
    captured = options;
    return response(200, backendPayload);
  }, async () => ApiClient.runInspection(file));

  assert.equal(captured.method, 'POST');
  assert.equal(captured.body.get('file').name, 'front.jpg');
  assert.deepEqual([...captured.body.keys()], ['file']);
});

test('runInspection posts to /api/inspection', async () => {
  let requestedUrl;
  await withFetch(async url => {
    requestedUrl = url;
    return response(200, backendPayload);
  }, async () => ApiClient.runInspection(new File(['image'], 'package.png', { type: 'image/png' })));

  assert.equal(requestedUrl, 'http://localhost:8000/api/inspection');
});

test('successful backend response is returned unchanged', async () => {
  const result = await withFetch(async () => response(200, backendPayload), async () => ApiClient.runInspection(new File(['image'], 'package.jpg')));
  assert.strictEqual(result, backendPayload);
});

test('HTTP 400 becomes a user-facing invalid input error', async () => {
  await assert.rejects(
    withFetch(async () => response(400, { detail: 'bad image' }), async () => ApiClient.runInspection(new File(['x'], 'bad.txt'))),
    error => error.status === 400 && error.code === 'INVALID_INPUT' && error.message.includes('valid package image')
  );
});

test('HTTP 500 becomes a user-facing backend processing error', async () => {
  await assert.rejects(
    withFetch(async () => response(500, { detail: 'pipeline failed' }), async () => ApiClient.runInspection(new File(['x'], 'package.jpg'))),
    error => error.status === 500 && error.code === 'BACKEND_ERROR' && error.message.includes('could not process')
  );
});

function fakeElement() {
  const element = {
    children: [],
    className: '',
    id: '',
    textContent: '',
    innerHTML: '',
    listeners: {},
    classList: {
      values: new Set(),
      add(...names) { names.forEach(name => this.values.add(name)); },
      remove(...names) { names.forEach(name => this.values.delete(name)); },
      contains(name) { return this.values.has(name); }
    },
    append(...items) { this.children.push(...items); },
    appendChild(item) { this.children.push(item); return item; },
    addEventListener(name, handler) { this.listeners[name] = handler; },
    querySelectorAll() { return []; }
  };
  return element;
}

globalThis.document = {
  createElement: () => fakeElement(),
  querySelectorAll: () => [],
  getElementById: () => fakeElement(),
  addEventListener: () => {}
};

function normalizedResult() {
  const view = Object.create(ResultView.prototype);
  const result = view.normalizeResult(backendPayload, {
    activePanel: 'front',
    panels: {
      front: { previewUrl: 'blob:front' },
      back: { previewUrl: 'blob:back' },
      side: { previewUrl: 'blob:side' }
    }
  });
  view.currentResult = result;
  return { view, result };
}

for (const status of ['PASS', 'FAIL', 'REVIEW_REQUIRED']) {
  test(`${status} renders in the overall status banner`, () => {
    const view = Object.create(ResultView.prototype);
    view.overallBanner = fakeElement();
    view.overallIcon = fakeElement();
    view.overallTitle = fakeElement();
    view.overallDesc = fakeElement();
    view.renderOverallStatus(status);
    assert.equal(view.overallTitle.textContent, status);
    assert.equal(view.overallBanner.classList.contains(`status-banner-${status === 'REVIEW_REQUIRED' ? 'review' : status.toLowerCase()}`), true);
  });
}

test('extracted fields render all five backend field displays', () => {
  const { view } = normalizedResult();
  view.extractedFieldsBody = fakeElement();
  view.renderExtractedFields(view.currentResult.extracted_fields);
  assert.equal(view.extractedFieldsBody.children.length, 5);
});

test('confidence values render without fabricated fallbacks', () => {
  const { view } = normalizedResult();
  view.extractedFieldsBody = fakeElement();
  view.renderExtractedFields(view.currentResult.extracted_fields);
  assert.equal(view.extractedFieldsBody.children[3].children[2].children[0].textContent, '63%');
  assert.equal(view.formatConfidence(undefined), '—');
});

test('source_block_ids and raw source render in the extracted fields table', () => {
  const { view } = normalizedResult();
  view.extractedFieldsBody = fakeElement();
  view.renderExtractedFields(view.currentResult.extracted_fields);
  const sourceCell = view.extractedFieldsBody.children[3].children[3];
  assert.match(sourceCell.innerHTML, /449\.00/);
  assert.match(sourceCell.innerHTML, /img:block-4/);
});

test('compliance evaluations render requirement, status, reason, and evidence', () => {
  const { view } = normalizedResult();
  view.ruleCardsContainer = fakeElement();
  view.activeRuleId = null;
  view.renderRuleCards(view.currentResult.rules);
  const card = view.ruleCardsContainer.children[0];
  const renderedText = card.children.map(child => child.textContent || child.children?.map(item => item.textContent).join(' ') || '').join(' ');
  assert.match(renderedText, /Maximum Retail Price/);
  assert.match(renderedText, /REVIEW_REQUIRED/);
  assert.match(renderedText, /Low-confidence extraction/);
  assert.match(renderedText, /img:block-4/);
});

for (const panel of ['front', 'back', 'side']) {
  test(`selected ${panel} image is the file sent to processing`, () => {
    const view = Object.create(InspectionView.prototype);
    view.activePanel = panel;
    view.panels = {
      front: { file: new File(['front'], 'front.jpg') },
      back: { file: new File(['back'], 'back.jpg') },
      side: { file: new File(['side'], 'side.jpg') }
    };
    view.app = { startProcessing(data) { view.sentData = data; } };
    view.startAnalysis();
    assert.strictEqual(view.sentData.panels[view.sentData.activePanel].file, view.panels[panel].file);
    assert.equal(view.sentData.activePanel, panel);
  });
}

test('no selected image uses the existing validation path', () => {
  const view = Object.create(InspectionView.prototype);
  view.activePanel = null;
  view.panels = { front: { file: null }, back: { file: null }, side: { file: null } };
  view.app = { startProcessing() { assert.fail('processing should not start'); } };
  const originalAlert = globalThis.alert;
  let alertMessage;
  globalThis.alert = message => { alertMessage = message; };
  try {
    view.startAnalysis();
  } finally {
    globalThis.alert = originalAlert;
  }
  assert.match(alertMessage, /select an image/i);
});

test('demo fixtures still work when explicitly enabled', async () => {
  window.METROLOGIC_DEMO_MODE = true;
  const demo = ApiClient.getDemoResult('scenario1');
  assert.equal(demo.overall_status, 'PASS');
  assert.equal(demo.rules.length, 5);
  assert.ok(demo.images.front.url.startsWith('data:image/svg+xml'));
  window.METROLOGIC_DEMO_MODE = false;
  assert.equal(await ApiClient.getHistory(), null);
});

test('real mode returns backend data and does not substitute demo data', async () => {
  window.METROLOGIC_DEMO_MODE = false;
  const realResult = await withFetch(async () => response(200, backendPayload), async () => ApiClient.runInspection(new File(['image'], 'real.jpg')));
  assert.equal(realResult.session_id, 'sess_test');
  assert.equal(realResult.overall_status, 'REVIEW_REQUIRED');
  assert.notEqual(realResult.session_id, 'ML-2026-00123');
});
