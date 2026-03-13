// src/engine/tools/BeamTool.js
// Segment chain tool for beams:
// - Click1: set start (no beam created)
// - Click2: create Beam A
// - Next clicks: chain Beam B, C...
// - Escape: stop chaining (keeps existing beams)
// - Right click: toggle 45° snap
// - S key: toggle 45° snap
// Naming stays sequential even if you stop and start elsewhere.

const DEG45 = Math.PI / 4;

function normalize(x, y) {
  const L = Math.hypot(x, y) || 1;
  return { x: x / L, y: y / L };
}

function cross(ax, ay, bx, by) { return ax * by - ay * bx; }

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

function beamNameFromIndex(i) {
  const letter = String.fromCharCode(65 + (i % 26));
  const suffix = i >= 26 ? `-${Math.floor(i / 26)}` : "";
  return `Beam ${letter}${suffix}`;
}

function beamIndexFromName(name) {
  const m = String(name || "").trim().match(/^Beam\s+([A-Z])(?:-(\d+))?$/i);
  if (!m) return null;
  const letterIdx = String(m[1]).toUpperCase().charCodeAt(0) - 65;
  if (letterIdx < 0 || letterIdx > 25) return null;
  const cycle = Number.isFinite(Number(m[2])) ? Number(m[2]) : 0;
  return cycle * 26 + letterIdx;
}

export class BeamTool {
  constructor({
    graph,
    view,
    defaultThickness = 40,
    defaultHeightMm = 200,
    defaultFloorOffsetMm = 2600,
    defaultColor = "#A6A6A6",
    snapTolMm = 30,
    startIndex = 0,
  }) {
    this.graph = graph;
    this.view = view;

    this.defaultThickness = defaultThickness;
    this.defaultHeightMm = defaultHeightMm;
    this.defaultFloorOffsetMm = defaultFloorOffsetMm;
    this.defaultColor = defaultColor;
    this.snapTolMm = snapTolMm;

    this.snapEnabled = true;
    this.lastDir = null;
    this.shiftLockDir = null;
    this.error = null; // { type:"overlap" } | null

    this.beamIndex = startIndex;
    this.pendingStartNodeId = null;
    this.pendingStartPos = null;
    this.previewEndPos = null;
  }

  getStatus() {
    return {
      isDrawing: !!this.pendingStartNodeId,
      snapEnabled: this.snapEnabled,
      beamName: beamNameFromIndex(this.beamIndex),
      thickness: this.defaultThickness,
      heightMm: this.defaultHeightMm,
      floorOffsetMm: this.defaultFloorOffsetMm,
      fillColor: this.defaultColor,
      color3d: this.defaultColor,
      error: this.error,
    };
  }

  getOverlaySegments() {
    if (!this.pendingStartPos || !this.previewEndPos) return [];
    return [{ a: this.pendingStartPos, b: this.previewEndPos }];
  }

  syncBeamIndexFromGraph() {
    let maxIdx = -1;
    for (const w of this.graph.walls.values()) {
      const idx = beamIndexFromName(w?.name);
      if (idx != null && idx > maxIdx) maxIdx = idx;
    }
    this.beamIndex = maxIdx + 1;
  }

  stopChaining() {
    const pendingNodeId = this.pendingStartNodeId;
    if (pendingNodeId) {
      const linkedWalls = this.graph.nodeToWalls.get(pendingNodeId);
      if (linkedWalls && linkedWalls.size === 0) {
        this.graph.nodeToWalls.delete(pendingNodeId);
        this.graph.nodes.delete(pendingNodeId);
      }
    }

    this.pendingStartNodeId = null;
    this.pendingStartPos = null;
    this.previewEndPos = null;
    this.lastDir = null;
    this.shiftLockDir = null;
    this.snapEnabled = true;
    this.error = null;
  }

  _checkOverlap(startPos, endPos) {
    const ax = startPos.x, ay = startPos.y;
    const bx = endPos.x, by = endPos.y;
    const abx = bx - ax;
    const aby = by - ay;
    const L = Math.hypot(abx, aby);
    if (L < 1e-6) return false;

    const ux = abx / L;
    const uy = aby / L;
    const nx = -uy;
    const ny = ux;

    const ANG_EPS = 0.01;
    const DIST_EPS_MM = 1;
    const OVERLAP_EPS_MM = 1;

    for (const w of this.graph.walls.values()) {
      const A = this.graph.getNode(w.a);
      const B = this.graph.getNode(w.b);
      if (!A || !B) continue;

      const cx = A.x, cy = A.y;
      const dx = B.x, dy = B.y;
      const cdx = dx - cx;
      const cdy = dy - cy;
      const L2 = Math.hypot(cdx, cdy);
      if (L2 < 1e-6) continue;

      const sin = Math.abs(cross(abx, aby, cdx, cdy) / (L * L2));
      if (sin > ANG_EPS) continue;

      const dist = Math.abs((cx - ax) * nx + (cy - ay) * ny);
      if (dist > DIST_EPS_MM) continue;

      const tC = (cx - ax) * ux + (cy - ay) * uy;
      const tD = (dx - ax) * ux + (dy - ay) * uy;
      const minCD = Math.min(tC, tD);
      const maxCD = Math.max(tC, tD);
      const overlap = Math.min(L, maxCD) - Math.max(0, minCD);
      if (overlap > OVERLAP_EPS_MM) return true;
    }

    return false;
  }

  _applyAngle(startPos, endPos, shiftKey, opts = {}) {
    const hasLineToggle = typeof opts?.stepLineEnabled === "boolean";
    const hasDegreeToggle = typeof opts?.stepDegreeEnabled === "boolean";
    const legacyStepsEnabled = opts?.stepDrawEnabled !== false;
    const legacyMode = opts?.stepDrawMode === "degree" ? "degree" : "line";

    let nextPos = endPos;
    if (this.snapEnabled) {
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

  onPointerDown(e, opts = {}) {
    if (e.button === 2) {
      e.preventDefault?.();
      if (this.pendingStartNodeId) {
        this.snapEnabled = !this.snapEnabled;
        this.shiftLockDir = null;
      }
      return;
    }
    if (e.button !== 0) return;

    const snapOn = !!opts?.snapOn;
    const resolveSnapPoint = opts?.resolveSnapPoint;
    let p = this.view.screenToWorld(e.offsetX, e.offsetY);
    if (snapOn && typeof resolveSnapPoint === "function") p = resolveSnapPoint(p.x, p.y) || p;

    if (!this.pendingStartNodeId) {
      const useWallMagnet = snapOn && opts?.wallMagnetEnabled !== false;
      const n0 = this._findSnapTargetPoint(p.x, p.y, useWallMagnet);
      this.pendingStartNodeId = n0.id;
      this.pendingStartPos = { x: n0.x, y: n0.y };
      this.previewEndPos = { x: n0.x, y: n0.y };
      this.error = null;
      return;
    }

    const startPos = this.pendingStartPos;

    let endPos = this._applyAngle(startPos, { x: p.x, y: p.y }, !!e.shiftKey, opts);
    if (snapOn && typeof resolveSnapPoint === "function") endPos = resolveSnapPoint(endPos.x, endPos.y) || endPos;

    const useWallMagnet = snapOn && opts?.wallMagnetEnabled !== false;
    const n1 = this._findSnapTargetPoint(endPos.x, endPos.y, useWallMagnet);
    if (n1.id === this.pendingStartNodeId) {
      this.stopChaining();
      return;
    }

    if (this._checkOverlap(startPos, { x: n1.x, y: n1.y })) {
      this.error = { type: "overlap" };
      return;
    }
    this.error = null;

    this.syncBeamIndexFromGraph();
    const name = beamNameFromIndex(this.beamIndex);
    const w = this.graph.addWallByNodeIds(
      this.pendingStartNodeId,
      n1.id,
      this.defaultThickness,
      name
    );
    if (w) {
      w.heightMm = Math.max(1, Number(this.defaultHeightMm) || 200);
      w.floorOffsetMm = Math.max(0, Number(this.defaultFloorOffsetMm) || 2600);
      w.color3d = String(this.defaultColor || "#C7CCD1");
    }

    this.lastDir = normalize(n1.x - startPos.x, n1.y - startPos.y);

    this.beamIndex++;
    this.pendingStartNodeId = n1.id;
    this.pendingStartPos = { x: n1.x, y: n1.y };
    this.previewEndPos = { x: n1.x, y: n1.y };
  }

  onPointerMove(e, opts = {}) {
    if (!this.pendingStartPos) return;

    const snapOn = !!opts?.snapOn;
    const resolveSnapPoint = opts?.resolveSnapPoint;
    const p = this.view.screenToWorld(e.offsetX, e.offsetY);
    const startPos = this.pendingStartPos;

    let endPos = this._applyAngle(startPos, { x: p.x, y: p.y }, !!e.shiftKey, opts);
    if (snapOn && typeof resolveSnapPoint === "function") endPos = resolveSnapPoint(endPos.x, endPos.y) || endPos;

    this.previewEndPos = endPos;

    this.error = this._checkOverlap(startPos, endPos) ? { type: "overlap" } : null;
  }

  onKeyDown(e) {
    if (e.key === "Escape") {
      this.stopChaining();
      return;
    }
    if (e.key === "s" || e.key === "S") {
      this.snapEnabled = !this.snapEnabled;
    }
  }

  _findSnapTargetPoint(x, y, useWallMagnet = true) {
    return this._resolveSnapNode(x, y, useWallMagnet);
  }

  _resolveSnapNode(x, y, useWallMagnet = true) {
    const n = this.graph.findNearestNode(x, y, this.snapTolMm);
    if (n) return n;

    if (!useWallMagnet) return this.graph.addNode(x, y);

    const hit = this.graph.findNearestWallPoint(x, y, this.snapTolMm);
    if (hit) {
      const res = this.graph.splitWallAtPoint(hit.wallId, hit.point.x, hit.point.y, 1);
      if (res?.node) return res.node;
    }

    return this.graph.addNode(x, y);
  }
}

export { beamNameFromIndex, beamIndexFromName };
