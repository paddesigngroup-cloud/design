// src/engine/tools/SolidWallTool.js
// Segment chain tool:
// - Click1: set start (no wall created)
// - Click2: create Wall A
// - Next clicks: chain Wall B, C...
// - Escape: stop chaining (keeps existing walls)
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

function wallNameFromIndex(i) {
  const letter = String.fromCharCode(65 + (i % 26));
  const suffix = i >= 26 ? `-${Math.floor(i / 26)}` : "";
  return `Wall ${letter}${suffix}`;
}

function wallIndexFromName(name) {
  const m = String(name || "").trim().match(/^Wall\s+([A-Z])(?:-(\d+))?$/i);
  if (!m) return null;
  const letterIdx = String(m[1]).toUpperCase().charCodeAt(0) - 65;
  if (letterIdx < 0 || letterIdx > 25) return null;
  const cycle = Number.isFinite(Number(m[2])) ? Number(m[2]) : 0;
  return cycle * 26 + letterIdx;
}

export class SolidWallTool {
  constructor({
    graph,
    view,
    defaultThickness = 120,
    defaultHeightMm = 3000,
    defaultColor = "#A6A6A6",
    snapTolMm = 30,
    startIndex = 0,
  }) {
    this.graph = graph;
    this.view = view;

    this.defaultThickness = defaultThickness;
    this.defaultHeightMm = defaultHeightMm;
    this.defaultColor = defaultColor;
    this.snapTolMm = snapTolMm;

    this.snapEnabled = true;
    this.lastDir = null;
    this.error = null; // { type:"overlap" } | null

    this.wallIndex = startIndex;
    this.pendingStartNodeId = null;
    this.pendingStartPos = null;
    this.previewEndPos = null;
  }

  getStatus() {
    return {
      isDrawing: !!this.pendingStartNodeId,
      snapEnabled: this.snapEnabled,
      wallName: wallNameFromIndex(this.wallIndex),
      thickness: this.defaultThickness,
      heightMm: this.defaultHeightMm,
      fillColor: this.defaultColor,
      color3d: this.defaultColor,
      error: this.error,
    };
  }

  getOverlaySegments() {
    if (!this.pendingStartPos || !this.previewEndPos) return [];
    return [{ a: this.pendingStartPos, b: this.previewEndPos }];
  }


  syncWallIndexFromGraph() {
    let maxIdx = -1;
    for (const w of this.graph.walls.values()) {
      const idx = wallIndexFromName(w?.name);
      if (idx != null && idx > maxIdx) maxIdx = idx;
    }
    this.wallIndex = maxIdx + 1;
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

    const ANG_EPS = 0.01; // ~0.57 deg
    const DIST_EPS_MM = 1; // 1mm
    const OVERLAP_EPS_MM = 1; // 1mm

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

      // distance from existing endpoint to new line (unit normal)
      const dist = Math.abs((cx - ax) * nx + (cy - ay) * ny);
      if (dist > DIST_EPS_MM) continue;

      // overlap in 1D along AB axis
      const tC = (cx - ax) * ux + (cy - ay) * uy;
      const tD = (dx - ax) * ux + (dy - ay) * uy;
      const minCD = Math.min(tC, tD);
      const maxCD = Math.max(tC, tD);
      const overlap = Math.min(L, maxCD) - Math.max(0, minCD);
      if (overlap > OVERLAP_EPS_MM) return true;
    }

    return false;
  }

  _applyAngle(startPos, endPos, shiftKey) {
    if (this.snapEnabled) return snap45(startPos, endPos);
    if (shiftKey && this.lastDir) {
      const u = normalize(this.lastDir.x, this.lastDir.y);
      const vx = endPos.x - startPos.x;
      const vy = endPos.y - startPos.y;
      const t = vx * u.x + vy * u.y;
      return { x: startPos.x + u.x * t, y: startPos.y + u.y * t };
    }
    return endPos;
  }

  onPointerDown(e) {
    // right click: toggle snap
    if (e.button === 2) {
      e.preventDefault?.();
      // Only toggle snap while actively drawing; otherwise right-click does nothing.
      if (this.pendingStartNodeId) this.snapEnabled = !this.snapEnabled;
      return;
    }
    if (e.button !== 0) return;

    const p = this.view.screenToWorld(e.offsetX, e.offsetY);

    // click1: set start
    if (!this.pendingStartNodeId) {
      const n0 = this._resolveSnapNode(p.x, p.y);
      this.pendingStartNodeId = n0.id;
      this.pendingStartPos = { x: n0.x, y: n0.y };
      this.previewEndPos = { x: n0.x, y: n0.y };
      this.error = null;
      return;
    }

    // click2+: set end and create wall
    const startPos = this.pendingStartPos;

    let endPos = this._applyAngle(startPos, { x: p.x, y: p.y }, !!e.shiftKey);

    const n1 = this._resolveSnapNode(endPos.x, endPos.y);
    if (n1.id === this.pendingStartNodeId) return;

    // Overlap check (collinear overlap with existing walls)
    if (this._checkOverlap(startPos, { x: n1.x, y: n1.y })) {
      this.error = { type: "overlap" };
      return;
    }
    this.error = null;

    this.syncWallIndexFromGraph();
    const name = wallNameFromIndex(this.wallIndex);
    const w = this.graph.addWallByNodeIds(
      this.pendingStartNodeId,
      n1.id,
      this.defaultThickness,
      name
    );
    if (w) {
      w.heightMm = Math.max(1, Number(this.defaultHeightMm) || 3000);
      w.color3d = String(this.defaultColor || "#C7CCD1");
      // Split intersections and cleanup
      this.graph.intersectAndSplitAll(w.id, 1);
      this.graph.mergeCloseNodes(1);
      this.graph.deleteTinyEdges(1);
    }

    this.lastDir = normalize(n1.x - startPos.x, n1.y - startPos.y);

    // chain
    this.wallIndex++;
    this.pendingStartNodeId = n1.id;
    this.pendingStartPos = { x: n1.x, y: n1.y };
    this.previewEndPos = { x: n1.x, y: n1.y };
  }

  onPointerMove(e) {
    if (!this.pendingStartPos) return;

    const p = this.view.screenToWorld(e.offsetX, e.offsetY);
    const startPos = this.pendingStartPos;

    const endPos = this._applyAngle(startPos, { x: p.x, y: p.y }, !!e.shiftKey);

    this.previewEndPos = endPos;

    // Preview-only overlap check (uses raw endPos, without snap node resolution)
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

  _resolveSnapNode(x, y) {
    // 1) snap to existing nodes
    const n = this.graph.findNearestNode(x, y, this.snapTolMm);
    if (n) return n;

    // 2) snap to nearest wall segment (split)
    const hit = this.graph.findNearestWallPoint(x, y, this.snapTolMm);
    if (hit) {
      const res = this.graph.splitWallAtPoint(hit.wallId, hit.point.x, hit.point.y, 1);
      if (res?.node) return res.node;
    }

    // 3) create new node
    return this.graph.addNode(x, y);
  }
}
