/**
 * METROLOGIC - Evidence Overlay & Coordinate Engine
 * Handles precision bounding box rendering, coordinate scaling (absolute & normalized),
 * zoom stage controls, and window/image resize observations.
 */

export class EvidenceOverlay {
  constructor(viewportEl, stageEl, imgEl, overlayLayerEl) {
    this.viewport = viewportEl;
    this.stage = stageEl;
    this.img = imgEl;
    this.overlayLayer = overlayLayerEl;

    this.currentZoom = 1.0;
    this.activeRuleId = null;
    this.currentBoxes = []; // Array of evidence box objects for current panel
    this.resizeObserver = null;
    this.onBoxClickCallback = null;

    this.bindEvents();
  }

  bindEvents() {
    // Window & container resize observer
    if (window.ResizeObserver) {
      this.resizeObserver = new ResizeObserver(() => {
        this.renderOverlays();
      });
      this.resizeObserver.observe(this.viewport);
      this.resizeObserver.observe(this.img);
    } else {
      window.addEventListener('resize', () => this.renderOverlays());
    }

    // Image load event triggers recalculation
    this.img.addEventListener('load', () => {
      this.renderOverlays();
    });
  }

  setOnBoxClick(callback) {
    this.onBoxClickCallback = callback;
  }

  // Load image & set boxes for active panel
  setPanelData(imageUrl, boxes = [], activeRuleId = null) {
    this.currentBoxes = boxes;
    this.activeRuleId = activeRuleId;
    
    if (this.img.src !== imageUrl) {
      this.img.src = imageUrl;
    } else {
      this.renderOverlays();
    }
  }

  // Render bounding box overlays on top of rendered image dimensions
  renderOverlays() {
    this.overlayLayer.innerHTML = '';

    if (!this.img.complete || this.img.naturalWidth === 0) {
      return;
    }

    const naturalW = this.img.naturalWidth;
    const naturalH = this.img.naturalHeight;
    const renderedW = this.img.clientWidth;
    const renderedH = this.img.clientHeight;

    if (renderedW === 0 || renderedH === 0) return;

    const scaleX = renderedW / naturalW;
    const scaleY = renderedH / naturalH;

    this.currentBoxes.forEach(item => {
      let left = 0, top = 0, width = 0, height = 0;

      // Handle coordinate schemas (absolute vs normalized vs array)
      if (Array.isArray(item.box)) {
        if (item.box.length === 4) {
          const [b0, b1, b2, b3] = item.box;
          // If normalized (all values <= 1.0)
          if (b0 <= 1 && b1 <= 1 && b2 <= 1 && b3 <= 1) {
            left = b0 * renderedW;
            top = b1 * renderedH;
            width = (b2 - b0) * renderedW;
            height = (b3 - b1) * renderedH;
          } else {
            // Absolute coordinates [x, y, w, h]
            left = b0 * scaleX;
            top = b1 * scaleY;
            width = b2 * scaleX;
            height = b3 * scaleY;
          }
        }
      } else if (item.normalized_x1 !== undefined) {
        left = item.normalized_x1 * renderedW;
        top = item.normalized_y1 * renderedH;
        width = (item.normalized_x2 - item.normalized_x1) * renderedW;
        height = (item.normalized_y2 - item.normalized_y1) * renderedH;
      } else if (item.x !== undefined) {
        left = item.x * scaleX;
        top = item.y * scaleY;
        width = item.width * scaleX;
        height = item.height * scaleY;
      }

      const boxDiv = document.createElement('div');
      boxDiv.className = `evidence-box ${item.ruleId === this.activeRuleId ? 'active' : ''}`;
      boxDiv.style.left = `${left}px`;
      boxDiv.style.top = `${top}px`;
      boxDiv.style.width = `${width}px`;
      boxDiv.style.height = `${height}px`;

      const labelSpan = document.createElement('span');
      labelSpan.className = 'evidence-box-label';
      labelSpan.textContent = item.label || item.ruleName || item.ruleId || 'Evidence';
      boxDiv.appendChild(labelSpan);

      boxDiv.addEventListener('click', (e) => {
        e.stopPropagation();
        if (this.onBoxClickCallback) {
          this.onBoxClickCallback(item);
        }
      });

      this.overlayLayer.appendChild(boxDiv);
    });
  }

  // Zoom Engine Controls
  setZoom(level) {
    this.currentZoom = Math.max(0.5, Math.min(3.0, level));
    this.stage.style.transform = `scale(${this.currentZoom})`;
  }

  zoomIn() {
    this.setZoom(this.currentZoom + 0.25);
  }

  zoomOut() {
    this.setZoom(this.currentZoom - 0.25);
  }

  resetZoom() {
    this.currentZoom = 1.0;
    this.stage.style.transform = `scale(1.0)`;
    this.viewport.scrollTop = 0;
    this.viewport.scrollLeft = 0;
  }

  // Focus specific region: centers viewport on the bounding box and applies subtle zoom
  focusRegion(ruleId) {
    this.activeRuleId = ruleId;
    this.renderOverlays();

    const targetBox = this.currentBoxes.find(b => b.ruleId === ruleId);
    if (!targetBox) return;

    // Slight zoom for visibility
    this.setZoom(1.25);

    const naturalW = this.img.naturalWidth;
    const naturalH = this.img.naturalHeight;
    const renderedW = this.img.clientWidth;
    const renderedH = this.img.clientHeight;

    if (renderedW === 0 || renderedH === 0) return;

    const scaleX = renderedW / naturalW;
    const scaleY = renderedH / naturalH;

    let centerX = renderedW / 2;
    let centerY = renderedH / 2;

    if (Array.isArray(targetBox.box)) {
      centerX = (targetBox.box[0] + targetBox.box[2] / 2) * scaleX * this.currentZoom;
      centerY = (targetBox.box[1] + targetBox.box[3] / 2) * scaleY * this.currentZoom;
    }

    // Scroll viewport to center bounding box
    const viewportW = this.viewport.clientWidth;
    const viewportH = this.viewport.clientHeight;

    this.viewport.scrollTo({
      left: Math.max(0, centerX - viewportW / 2),
      top: Math.max(0, centerY - viewportH / 2),
      behavior: 'smooth'
    });
  }
}
