// src/engine/dimension.js
// Standalone Dimension tool (AutoCAD-like 3-click).
// - Click1: pick point A
// - Click2: pick point B
// - Click3: place dimension offset (creates entity)
// Right-click while drawing: toggle ortho lock
// Escape: cancel

function normalize(x, y) {
  const L = Math.hypot(x, y) || 1;
  return { x: x / L, y: y / L };
}

function dot(ax, ay, bx, by) { return ax * bx + ay * by; }
const DEG45 = Math.PI / 4;

function snap45(from, to) {
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const L = Math.hypot(dx, dy);
  if (L < 1e-9) return { x: to.x, y: to.y };
  const ang = Math.atan2(dy, dx);
  const snapped = Math.round(ang / DEG45) * DEG45;
  return {
    x: from.x + Math.cos(snapped) * L,
    y: from.y + Math.sin(snapped) * L,
  };
}

function quantizeLength(from, to, stepMm) {
  const step = Number(stepMm);
  if (!Number.isFinite(step) || step <= 0) return to;
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.hypot(dx, dy);
  if (len < 1e-9) return { x: from.x, y: from.y };
  const snappedLen = Math.round(len / step) * step;
  const scale = snappedLen / len;
  return { x: from.x + dx * scale, y: from.y + dy * scale };
}

function quantizeAngle(from, to, stepDeg) {
  const step = Number(stepDeg);
  if (!Number.isFinite(step) || step <= 0) return to;
  const dx = to.x - from.x;
  const dy = to.y - from.y;
  const len = Math.hypot(dx, dy);
  if (len < 1e-9) return { x: from.x, y: from.y };
  const stepRad = (step * Math.PI) / 180;
  const angle = Math.atan2(dy, dx);
  const snapped = Math.round(angle / stepRad) * stepRad;
  return {
    x: from.x + Math.cos(snapped) * len,
    y: from.y + Math.sin(snapped) * len,
  };
}

export class DimensionTool {
  constructor({ view, snapTolMm = 30 }) {
    this.view = view;
    this.snapTolMm = snapTolMm;

    this.stage = 0; // 0 idle, 1 has A, 2 has A+B (placing offset)
    this.a = null;
    this.b = null;
    this.cursor = null;
    this.orthoLocked = true;
    this.lastDir = null;
    this.shiftLockDir = null;

    this._did = 1;
  }

  getStatus() {
    return { isDrawing: this.stage !== 0, stage: this.stage, orthoLocked: this.orthoLocked };
  }

  getPreview() {
    return { stage: this.stage, a: this.a, b: this.b, cursor: this.cursor };
  }

  cancel() {
    this.stage = 0;
    this.a = null;
    this.b = null;
    this.cursor = null;
    this.lastDir = null;
    this.shiftLockDir = null;
  }

  _screenToWorld(e) {
    return this.view.screenToWorld(e.offsetX, e.offsetY);
  }

  _applySnap(point, opts = null, ctx = null) {
    const snapOn = !!opts?.snapOn;
    const resolveSnapPoint = opts?.resolveSnapPoint;
    if (!snapOn || typeof resolveSnapPoint !== "function") return point;
    const sp = resolveSnapPoint(point.x, point.y, ctx || {});
    return sp || point;
  }

  _applyAngleAndStep(anchor, point, shiftKey, opts = null) {
    if (!anchor) return point;
    const hasLineToggle = typeof opts?.stepLineEnabled === "boolean";
    const hasDegreeToggle = typeof opts?.stepDegreeEnabled === "boolean";
    const legacyStepsEnabled = opts?.stepDrawEnabled !== false;
    const legacyMode = opts?.stepDrawMode === "degree" ? "degree" : "line";

    let next = point;
    if (this.orthoLocked) {
      this.shiftLockDir = null;
      next = snap45(anchor, next);
    } else if (!shiftKey) {
      this.shiftLockDir = null;
    } else {
      const vx = next.x - anchor.x;
      const vy = next.y - anchor.y;
      if (!this.shiftLockDir) {
        const L0 = Math.hypot(vx, vy);
        if (L0 >= 1e-9) this.shiftLockDir = normalize(vx, vy);
        else if (this.lastDir) this.shiftLockDir = normalize(this.lastDir.x, this.lastDir.y);
      }
      const u = this.shiftLockDir || this.lastDir;
      if (u) {
        const L = Math.hypot(vx, vy);
        if (L < 1e-9) next = { x: anchor.x, y: anchor.y };
        else {
          const proj = vx * u.x + vy * u.y;
          const signedLen = proj < 0 ? -L : L;
          next = { x: anchor.x + u.x * signedLen, y: anchor.y + u.y * signedLen };
        }
      }
    }

    let useLineStep = false;
    let useDegreeStep = false;
    if (hasLineToggle || hasDegreeToggle) {
      useLineStep = hasLineToggle ? !!opts.stepLineEnabled : false;
      useDegreeStep = hasDegreeToggle ? !!opts.stepDegreeEnabled : false;
    } else if (legacyStepsEnabled) {
      useLineStep = legacyMode !== "degree";
      useDegreeStep = legacyMode === "degree";
    }

    if (useDegreeStep) next = quantizeAngle(anchor, next, opts?.stepAngleDeg);
    if (useLineStep) next = quantizeLength(anchor, next, opts?.stepLineMm);
    return next;
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
    if (this.stage === 0 && typeof opts?.orthoEnabled === "boolean") {
      this.orthoLocked = !!opts.orthoEnabled;
    }

    // Right click toggles ortho lock while drawing.
    if (e.button === 2) {
      e.preventDefault?.();
      if (this.stage !== 0) {
        this.orthoLocked = !this.orthoLocked;
        this.shiftLockDir = null;
      }
      return;
    }
    if (e.button !== 0) return;

    const raw = this._screenToWorld(e);
    let p = this._applySnap(raw, opts, { phase: this.stage === 2 ? "offset" : "line", stage: this.stage });
    this.cursor = p;

    if (this.stage === 0) {
      this.a = { x: p.x, y: p.y };
      this.stage = 1;
      return;
    }

    if (this.stage === 1) {
      p = this._applyAngleAndStep(this.a, raw, !!e.shiftKey, opts);
      p = this._applySnap(p, opts, { phase: "line", stage: this.stage, anchor: this.a });
      const dx = p.x - this.a.x;
      const dy = p.y - this.a.y;
      if (Math.hypot(dx, dy) < 1) return;
      this.b = { x: p.x, y: p.y };
      this.lastDir = normalize(dx, dy);
      this.stage = 2;
      this.cursor = p;
      return;
    }

    if (this.stage === 2) {
      p = this._applyAngleAndStep(this.b || this.a, raw, !!e.shiftKey, opts);
      p = this._applySnap(p, opts, { phase: "offset", stage: this.stage, anchorA: this.a, anchorB: this.b });
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
    const raw = this._screenToWorld(e);
    if (this.stage === 1 && this.a) {
      let p = this._applyAngleAndStep(this.a, raw, !!e.shiftKey, opts);
      p = this._applySnap(p, opts, { phase: "line", stage: this.stage, anchor: this.a });
      this.cursor = p;
      return;
    }
    if (this.stage === 2) {
      let p = this._applyAngleAndStep(this.b || this.a, raw, !!e.shiftKey, opts);
      p = this._applySnap(p, opts, { phase: "offset", stage: this.stage, anchorA: this.a, anchorB: this.b });
      this.cursor = p;
      return;
    }
    this.cursor = this._applySnap(raw, opts, { phase: "line", stage: this.stage });
  }

  onKeyDown(e) {
    if (e.key === "Escape") this.cancel();
  }
}
