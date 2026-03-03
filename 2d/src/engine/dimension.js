// src/engine/dimension.js
// Standalone Dimension tool (AutoCAD-like 3-click).
// - Click1: pick point A
// - Click2: pick point B
// - Click3: place dimension offset (creates entity)
// Right-click: cancel current dimension command (no toggles)
// Escape: cancel

function normalize(x, y) {
  const L = Math.hypot(x, y) || 1;
  return { x: x / L, y: y / L };
}

function dot(ax, ay, bx, by) { return ax * bx + ay * by; }

export class DimensionTool {
  constructor({ view, snapTolMm = 30 }) {
    this.view = view;
    this.snapTolMm = snapTolMm;

    this.stage = 0; // 0 idle, 1 has A, 2 has A+B (placing offset)
    this.a = null;
    this.b = null;
    this.cursor = null;

    this._did = 1;
  }

  getStatus() {
    return { isDrawing: this.stage !== 0, stage: this.stage };
  }

  getPreview() {
    return { stage: this.stage, a: this.a, b: this.b, cursor: this.cursor };
  }

  cancel() {
    this.stage = 0;
    this.a = null;
    this.b = null;
    this.cursor = null;
  }

  _resolvePoint(e, opts = null) {
    let p = this.view.screenToWorld(e.offsetX, e.offsetY);
    const snapOn = !!opts?.snapOn;
    const resolveSnapPoint = opts?.resolveSnapPoint;
    if (snapOn && typeof resolveSnapPoint === "function") {
      const sp = resolveSnapPoint(p.x, p.y);
      if (sp) p = sp;
    }
    return p;
  }

  _computeOffsetAndSide(A, B, P) {
    const d = normalize(B.x - A.x, B.y - A.y);
    const nL = { x: -d.y, y: d.x };
    const apx = P.x - A.x;
    const apy = P.y - A.y;
    const signed = dot(apx, apy, nL.x, nL.y);
    const sideSign = (signed >= 0) ? 1 : -1;
    const offsetMm = Math.abs(signed);
    return { offsetMm, sideSign };
  }

  onPointerDown(e, opts = null) {
    // Right click cancels current dimension command (no toggles).
    if (e.button === 2) {
      e.preventDefault?.();
      if (this.stage !== 0) this.cancel();
      return;
    }
    if (e.button !== 0) return;

    const p = this._resolvePoint(e, opts);
    this.cursor = p;

    if (this.stage === 0) {
      this.a = { x: p.x, y: p.y };
      this.stage = 1;
      return;
    }

    if (this.stage === 1) {
      const dx = p.x - this.a.x;
      const dy = p.y - this.a.y;
      if (Math.hypot(dx, dy) < 1) return;
      this.b = { x: p.x, y: p.y };
      this.stage = 2;
      return;
    }

    if (this.stage === 2) {
      const A = this.a;
      const B = this.b;
      const { offsetMm, sideSign } = this._computeOffsetAndSide(A, B, p);

      const dim = {
        id: `d${this._did++}`,
        a: { x: A.x, y: A.y },
        b: { x: B.x, y: B.y },
        offsetMm,
        sideSign,
      };

      if (typeof opts?.onCommit === "function") opts.onCommit(dim);
      this.cancel();
    }
  }

  onPointerMove(e, opts = null) {
    if (this.stage === 0) return;
    this.cursor = this._resolvePoint(e, opts);
  }

  onKeyDown(e) {
    if (e.key === "Escape") this.cancel();
  }
}
