// hiddenwall.js
// Hidden wall tool + rendering (dashed guide-like segments).

const DEG45 = Math.PI / 4;

function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function normalize(x, y) { const L = Math.hypot(x, y) || 1; return { x: x / L, y: y / L }; }

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

function constrainAlongDir(from, to, dir) {
  const u = normalize(dir.x, dir.y);
  const vx = to.x - from.x;
  const vy = to.y - from.y;
  const t = vx * u.x + vy * u.y;
  return { x: from.x + u.x * t, y: from.y + u.y * t };
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

export class HiddenWallTool {
  constructor({ graph, view, snapTolMm = 30, defaultThickness = 1 }) {
    this.graph = graph;
    this.view = view;
    this.snapTolMm = snapTolMm;
    this.defaultThickness = Math.max(1, Number(defaultThickness) || 1);

    this.angleLocked = true; // 45deg
    this.lastDir = null;
    this.shiftLockDir = null;

    this.pendingStartNodeId = null;
    this.pendingStartPos = null;
    this.previewEndPos = null;
  }

  getStatus() {
    return {
      isDrawing: !!this.pendingStartNodeId,
      angleLocked: this.angleLocked,
    };
  }

  getOverlaySegments() {
    if (!this.pendingStartPos || !this.previewEndPos) return [];
    return [{ a: this.pendingStartPos, b: this.previewEndPos }];
  }

  stopChaining() {
    this.pendingStartNodeId = null;
    this.pendingStartPos = null;
    this.previewEndPos = null;
    this.lastDir = null;
    this.shiftLockDir = null;
    this.angleLocked = true;
  }

  _applyAngle(startPos, endPos, shiftKey, opts = {}) {
    let nextPos = endPos;
    if (this.angleLocked) {
      this.shiftLockDir = null;
      nextPos = snap45(startPos, nextPos);
    } else {
      const vx = nextPos.x - startPos.x;
      const vy = nextPos.y - startPos.y;

      if (!shiftKey) {
        this.shiftLockDir = null;
      } else {
        if (!this.shiftLockDir) {
          const L0 = Math.hypot(vx, vy);
          if (L0 >= 1e-9) this.shiftLockDir = normalize(vx, vy);
          else if (this.lastDir) this.shiftLockDir = normalize(this.lastDir.x, this.lastDir.y);
        }

        const u = this.shiftLockDir || this.lastDir;
        if (u) {
          const L = Math.hypot(vx, vy);
          if (L < 1e-9) nextPos = { x: startPos.x, y: startPos.y };
          else {
            const dot = vx * u.x + vy * u.y;
            const signedLen = dot < 0 ? -L : L;
            nextPos = { x: startPos.x + u.x * signedLen, y: startPos.y + u.y * signedLen };
          }
        }
      }
    }

    const hasLineToggle = typeof opts?.stepLineEnabled === "boolean";
    const hasDegreeToggle = typeof opts?.stepDegreeEnabled === "boolean";
    const legacyStepsEnabled = opts?.stepDrawEnabled !== false;
    const legacyMode = opts?.stepDrawMode === "degree" ? "degree" : "line";
    let useLineStep = false;
    let useDegreeStep = false;
    if (hasLineToggle || hasDegreeToggle) {
      useLineStep = hasLineToggle ? !!opts.stepLineEnabled : false;
      useDegreeStep = hasDegreeToggle ? !!opts.stepDegreeEnabled : false;
    } else if (legacyStepsEnabled) {
      useLineStep = legacyMode !== "degree";
      useDegreeStep = legacyMode === "degree";
    }

    if (useDegreeStep) nextPos = quantizeAngle(startPos, nextPos, opts?.stepAngleDeg);
    if (useLineStep) nextPos = quantizeLength(startPos, nextPos, opts?.stepLineMm);
    return nextPos;
  }

  onPointerDown(e, opts = null) {
    const snapOn = !!opts?.snapOn;
    const resolveSnapPoint = opts?.resolveSnapPoint;

    // right click: toggle angle lock (only while drawing)
    if (e.button === 2) {
      e.preventDefault?.();
      if (this.pendingStartNodeId) {
        this.angleLocked = !this.angleLocked;
        this.shiftLockDir = null;
      }
      return;
    }
    if (e.button !== 0) return;

    let p = this.view.screenToWorld(e.offsetX, e.offsetY);
    if (snapOn && typeof resolveSnapPoint === "function") p = resolveSnapPoint(p.x, p.y) || p;

    // click1: set start
    if (!this.pendingStartNodeId) {
      const n0 = this.graph.getOrCreateNode(p.x, p.y, snapOn ? this.snapTolMm : 1);
      this.pendingStartNodeId = n0.id;
      this.pendingStartPos = { x: n0.x, y: n0.y };
      this.previewEndPos = { x: n0.x, y: n0.y };
      return;
    }

    // click2+: create segment
    const startPos = this.pendingStartPos;
    let endPos = this._applyAngle(startPos, p, !!e.shiftKey, opts);
    if (snapOn && typeof resolveSnapPoint === "function") endPos = resolveSnapPoint(endPos.x, endPos.y) || endPos;

    const n1 = this.graph.getOrCreateNode(endPos.x, endPos.y, snapOn ? this.snapTolMm : 1);
    if (n1.id === this.pendingStartNodeId) return;

    const thicknessMm = Math.max(1, Number(opts?.defaultThicknessMm ?? this.defaultThickness) || 1);
    const w = this.graph.addWallByNodeIds(this.pendingStartNodeId, n1.id, thicknessMm, "");
    if (!w) return;

    this.lastDir = normalize(n1.x - startPos.x, n1.y - startPos.y);
    this.pendingStartNodeId = n1.id;
    this.pendingStartPos = { x: n1.x, y: n1.y };
    this.previewEndPos = { x: n1.x, y: n1.y };
  }

  onPointerMove(e, opts = null) {
    if (!this.pendingStartPos) return;
    const snapOn = !!opts?.snapOn;
    const resolveSnapPoint = opts?.resolveSnapPoint;

    let p = this.view.screenToWorld(e.offsetX, e.offsetY);
    const startPos = this.pendingStartPos;
    let endPos = this._applyAngle(startPos, p, !!e.shiftKey, opts);
    if (snapOn && typeof resolveSnapPoint === "function") endPos = resolveSnapPoint(endPos.x, endPos.y) || endPos;
    this.previewEndPos = endPos;
  }

  onKeyDown(e) {
    if (e.key === "Escape") {
      this.stopChaining();
      return;
    }
  }
}

export function drawHiddenWalls({
  ctx,
  state,
  graph,
  worldToScreen,
  selectedId = null,
  selectedIds = null,
  hoverId = null,
}) {
  const zoom = Math.max(0.001, Number(state?.zoom) || 1);
  const basePx = Math.max(1, Number(state?.hiddenWallLineWidthPx) || 2);
  const defaultThicknessMm = Math.max(1, Number(state?.hiddenWallThicknessMm) || 1);
  const lineWidthFromMm = (mm) => Math.max(basePx, Number(mm) * zoom);

  ctx.save();
  ctx.setLineDash(state.hiddenWallDash || [10, 8]);
  ctx.strokeStyle = state.hiddenWallColor || "#D8D4D4";
  ctx.lineCap = "round";

  for (const e of graph.walls.values()) {
    const A = graph.getNode(e.a);
    const B = graph.getNode(e.b);
    if (!A || !B) continue;
    const a = worldToScreen(A.x, A.y);
    const b = worldToScreen(B.x, B.y);

    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.lineWidth = lineWidthFromMm(e?.thickness || defaultThicknessMm);
    ctx.stroke();
  }

  // hover/selection highlight
  const selectedSet = new Set(Array.isArray(selectedIds) ? selectedIds : []);
  if (selectedId) selectedSet.add(selectedId);
  const highlightIds = new Set(selectedSet);
  if (hoverId) highlightIds.add(hoverId);
  for (const hlId of highlightIds) {
    const e = graph.getWall(hlId);
    if (!e) continue;
    const A = graph.getNode(e.a);
    const B = graph.getNode(e.b);
    if (!A || !B) continue;
    const a = worldToScreen(A.x, A.y);
    const b = worldToScreen(B.x, B.y);
    const isSelected = selectedSet.has(hlId);
    ctx.save();
    ctx.setLineDash(state.hiddenWallDash || [10, 8]);
    const base = lineWidthFromMm(e?.thickness || defaultThicknessMm);
    ctx.lineWidth = isSelected ? (base + 2) : (base + 1);
    ctx.globalAlpha = isSelected ? 1 : 0.8;
    ctx.strokeStyle = state.hiddenWallColor || "#D8D4D4";
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
    ctx.restore();
  }

  ctx.restore();
}

