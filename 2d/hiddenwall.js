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

export class HiddenWallTool {
  constructor({ graph, view, snapTolMm = 30 }) {
    this.graph = graph;
    this.view = view;
    this.snapTolMm = snapTolMm;

    this.angleLocked = true; // 45deg
    this.lastDir = null;

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
    this.angleLocked = true;
  }

  _applyAngle(startPos, endPos, shiftKey) {
    if (this.angleLocked) return snap45(startPos, endPos);
    if (shiftKey && this.lastDir) return constrainAlongDir(startPos, endPos, this.lastDir);
    return endPos;
  }

  onPointerDown(e, opts = null) {
    const snapOn = !!opts?.snapOn;
    const resolveSnapPoint = opts?.resolveSnapPoint;

    // right click: toggle angle lock (only while drawing)
    if (e.button === 2) {
      e.preventDefault?.();
      if (this.pendingStartNodeId) this.angleLocked = !this.angleLocked;
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
    let endPos = this._applyAngle(startPos, p, !!e.shiftKey);
    if (snapOn && typeof resolveSnapPoint === "function") endPos = resolveSnapPoint(endPos.x, endPos.y) || endPos;

    const n1 = this.graph.getOrCreateNode(endPos.x, endPos.y, snapOn ? this.snapTolMm : 1);
    if (n1.id === this.pendingStartNodeId) return;

    const w = this.graph.addWallByNodeIds(this.pendingStartNodeId, n1.id, 1, "");
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
    let endPos = this._applyAngle(startPos, p, !!e.shiftKey);
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
  ctx.save();
  ctx.setLineDash(state.hiddenWallDash || [10, 8]);
  ctx.lineWidth = state.hiddenWallLineWidthPx || 2;
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
    ctx.lineWidth = isSelected ? 4 : 3;
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

