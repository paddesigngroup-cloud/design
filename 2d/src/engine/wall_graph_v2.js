// src/engine/wall_graph_v2.js
// Node-based wall graph (Alpha nodes + Wall edges)
// No rendering, no UI.

export class Node {
  constructor(id, x, y) {
    this.id = id;
    this.x = x; // world mm
    this.y = y; // world mm
  }
}

export class WallEdge {
  constructor(id, aNodeId, bNodeId, thicknessMm = 120, name = "") {
    this.id = id;
    this.a = aNodeId;
    this.b = bNodeId;
    this.thickness = thicknessMm;
    this.name = name || id;

    // per-wall UI placement
    this.dimSide = "auto";    // "auto" | "left" | "right"
    this.offsetSide = "auto"; // "auto" | "left" | "right"
    this.offsetSideManual = false;
    this.dimOffsetMm = null;  // null => use global default

    // Dimension visibility + driving length
    this.dimAlwaysVisible = false;
    // Keep the last "inside (useful)" length stable when topology changes.
    // Only enforced when the wall has a free endpoint (degree=1).
    this.lockedInsideLenMm = null;
  }
}

export class WallGraph {
  constructor() {
    this.nodes = new Map();       // id -> Node
    this.walls = new Map();       // id -> WallEdge
    this.nodeToWalls = new Map(); // nodeId -> Set(wallId)

    this._nid = 1;
    this._wid = 1;
  }

  newNodeId() { return `n${this._nid++}`; }
  newWallId() { return `w${this._wid++}`; }

  clear() {
    this.nodes.clear();
    this.walls.clear();
    this.nodeToWalls.clear();
    this._nid = 1;
    this._wid = 1;
  }

  getNode(nodeId) { return this.nodes.get(nodeId) || null; }
  getWall(wallId) { return this.walls.get(wallId) || null; }

  addNode(x, y) {
    const id = this.newNodeId();
    const n = new Node(id, x, y);
    this.nodes.set(id, n);
    this.nodeToWalls.set(id, new Set());
    return n;
  }

  moveNode(nodeId, x, y) {
    const n = this.getNode(nodeId);
    if (!n) return false;
    n.x = x; n.y = y;
    return true;
  }

  findNearestNode(x, y, tolMm = 30) {
    let best = null;
    let bestD2 = tolMm * tolMm;

    for (const n of this.nodes.values()) {
      const dx = n.x - x;
      const dy = n.y - y;
      const d2 = dx*dx + dy*dy;
      if (d2 <= bestD2) {
        bestD2 = d2;
        best = n;
      }
    }
    return best;
  }

  getOrCreateNode(x, y, tolMm = 30) {
    const hit = this.findNearestNode(x, y, tolMm);
    if (hit) return hit;
    return this.addNode(x, y);
  }

  addWallByNodeIds(aNodeId, bNodeId, thicknessMm = 120, name = "") {
    if (aNodeId === bNodeId) throw new Error("Wall must connect two distinct nodes");
    if (!this.nodes.has(aNodeId) || !this.nodes.has(bNodeId)) throw new Error("Invalid node id(s)");

    // prevent duplicates
    for (const w of this.walls.values()) {
      const same = (w.a === aNodeId && w.b === bNodeId) || (w.a === bNodeId && w.b === aNodeId);
      if (same) return w;
    }

    const id = this.newWallId();
    const w = new WallEdge(id, aNodeId, bNodeId, thicknessMm, name);
    this.walls.set(id, w);

    if (!this.nodeToWalls.has(aNodeId)) this.nodeToWalls.set(aNodeId, new Set());
    if (!this.nodeToWalls.has(bNodeId)) this.nodeToWalls.set(bNodeId, new Set());
    this.nodeToWalls.get(aNodeId).add(id);
    this.nodeToWalls.get(bNodeId).add(id);

    return w;
  }

  addWallByPoints(ax, ay, bx, by, thicknessMm = 120, name = "", snapTolMm = 30) {
    const na = this.getOrCreateNode(ax, ay, snapTolMm);
    const nb = this.getOrCreateNode(bx, by, snapTolMm);
    return this.addWallByNodeIds(na.id, nb.id, thicknessMm, name);
  }

  getWallsAtNode(nodeId) {
    const set = this.nodeToWalls.get(nodeId);
    if (!set) return [];
    return [...set].map(id => this.walls.get(id)).filter(Boolean);
  }

  deleteWall(wallId) {
    const w = this.walls.get(wallId);
    if (!w) return false;

    this.walls.delete(wallId);

    const sa = this.nodeToWalls.get(w.a);
    if (sa) sa.delete(wallId);
    const sb = this.nodeToWalls.get(w.b);
    if (sb) sb.delete(wallId);

    return true;
  }

  // Closest point on any wall segment within tolerance.
  // Returns { wallId, point:{x,y}, t } where t in [0,1] on wall A->B.
  findNearestWallPoint(x, y, tolMm = 30) {
    let best = null;
    let bestD2 = tolMm * tolMm;

    for (const w of this.walls.values()) {
      const A = this.getNode(w.a);
      const B = this.getNode(w.b);
      if (!A || !B) continue;

      const abx = B.x - A.x;
      const aby = B.y - A.y;
      const ab2 = abx * abx + aby * aby;
      if (ab2 < 1e-12) continue;

      const apx = x - A.x;
      const apy = y - A.y;
      let t = (apx * abx + apy * aby) / ab2;
      t = Math.max(0, Math.min(1, t));

      const px = A.x + abx * t;
      const py = A.y + aby * t;
      const dx = x - px;
      const dy = y - py;
      const d2 = dx * dx + dy * dy;
      if (d2 <= bestD2) {
        bestD2 = d2;
        best = { wallId: w.id, point: { x: px, y: py }, t };
      }
    }
    return best;
  }

  // Split a wall at a point. If point is near an endpoint (within epsMm), returns that node.
  // Returns { node, newWallIds: [w1, w2] } where newWallIds may be [] if no split.
  splitWallAtPoint(wallId, px, py, epsMm = 1) {
    const w = this.getWall(wallId);
    if (!w) return null;
    const A = this.getNode(w.a);
    const B = this.getNode(w.b);
    if (!A || !B) return null;

    const dA2 = (A.x - px) ** 2 + (A.y - py) ** 2;
    const dB2 = (B.x - px) ** 2 + (B.y - py) ** 2;
    if (dA2 <= epsMm * epsMm) return { node: A, newWallIds: [] };
    if (dB2 <= epsMm * epsMm) return { node: B, newWallIds: [] };

    const nP = this.addNode(px, py);

    // remove original wall
    this.deleteWall(wallId);

    // preserve properties
    const base = {
      thickness: w.thickness,
      name: w.name,
      dimSide: w.dimSide ?? "auto",
      offsetSide: w.offsetSide ?? "auto",
      offsetSideManual: !!w.offsetSideManual,
      dimOffsetMm: (typeof w.dimOffsetMm === "number" && isFinite(w.dimOffsetMm)) ? Math.max(0, w.dimOffsetMm) : null,
      dimAlwaysVisible: !!w.dimAlwaysVisible,
      lockedInsideLenMm: (typeof w.lockedInsideLenMm === "number") ? w.lockedInsideLenMm : null,
    };

    const w1 = this.addWallByNodeIds(A.id, nP.id, base.thickness, base.name);
    if (w1) {
      w1.dimSide = base.dimSide;
      w1.offsetSide = base.offsetSide;
      w1.offsetSideManual = !!base.offsetSideManual;
      w1.dimOffsetMm = base.dimOffsetMm;
      w1.dimAlwaysVisible = base.dimAlwaysVisible;
      w1.lockedInsideLenMm = base.lockedInsideLenMm;
    }
    const w2 = this.addWallByNodeIds(nP.id, B.id, base.thickness, base.name);
    if (w2) {
      w2.dimSide = base.dimSide;
      w2.offsetSide = base.offsetSide;
      w2.offsetSideManual = !!base.offsetSideManual;
      w2.dimOffsetMm = base.dimOffsetMm;
      w2.dimAlwaysVisible = base.dimAlwaysVisible;
      w2.lockedInsideLenMm = base.lockedInsideLenMm;
    }

    return { node: nP, newWallIds: [w1?.id, w2?.id].filter(Boolean) };
  }

  // Merge nodes closer than epsMm. Keeps first node, rewires edges.
  mergeCloseNodes(epsMm = 1) {
    const nodes = [...this.nodes.values()];
    const eps2 = epsMm * epsMm;

    for (let i = 0; i < nodes.length; i++) {
      const ni = nodes[i];
      if (!this.nodes.has(ni.id)) continue;
      for (let j = i + 1; j < nodes.length; j++) {
        const nj = nodes[j];
        if (!this.nodes.has(nj.id)) continue;
        const dx = ni.x - nj.x;
        const dy = ni.y - nj.y;
        if (dx * dx + dy * dy > eps2) continue;

        // rewire edges from nj to ni
        const set = this.nodeToWalls.get(nj.id);
        if (set) {
          for (const wid of set) {
            const w = this.walls.get(wid);
            if (!w) continue;
            if (w.a === nj.id) w.a = ni.id;
            if (w.b === nj.id) w.b = ni.id;
            if (!this.nodeToWalls.has(ni.id)) this.nodeToWalls.set(ni.id, new Set());
            this.nodeToWalls.get(ni.id).add(wid);
          }
        }
        this.nodeToWalls.delete(nj.id);
        this.nodes.delete(nj.id);
      }
    }

    // Cleanup: remove self-loops and duplicate walls after rewiring.
    const seen = new Map();
    for (const w of [...this.walls.values()]) {
      if (w.a === w.b) {
        this.deleteWall(w.id);
        continue;
      }
      const a = (w.a < w.b) ? w.a : w.b;
      const b = (w.a < w.b) ? w.b : w.a;
      const key = `${a}|${b}`;
      const kept = seen.get(key);
      if (!kept) {
        seen.set(key, w.id);
        continue;
      }
      this.deleteWall(w.id);
    }
  }

  // Delete walls shorter than minLenMm.
  deleteTinyEdges(minLenMm = 1) {
    const min2 = minLenMm * minLenMm;
    for (const w of [...this.walls.values()]) {
      const A = this.getNode(w.a);
      const B = this.getNode(w.b);
      if (!A || !B) {
        this.deleteWall(w.id);
        continue;
      }
      const dx = A.x - B.x;
      const dy = A.y - B.y;
      if (dx * dx + dy * dy <= min2) this.deleteWall(w.id);
    }
  }

  // Split intersections between a new wall and all others.
  // If the new wall is split, continue processing the resulting segments.
  // epsMm is a distance threshold used to treat near-endpoint hits as endpoint (no split).
  intersectAndSplitAll(newWallId, epsMm = 1) {
    const queue = [newWallId];
    const visited = new Set();

    while (queue.length) {
      const wid = queue.pop();
      if (visited.has(wid)) continue;
      visited.add(wid);

      const wNew = this.getWall(wid);
      if (!wNew) continue;
      const A = this.getNode(wNew.a);
      const B = this.getNode(wNew.b);
      if (!A || !B) continue;

      const otherWalls = [...this.walls.values()].filter(w => w.id !== wid);
      for (const w of otherWalls) {
        const C = this.getNode(w.a);
        const D = this.getNode(w.b);
        if (!C || !D) continue;

        const hit = segmentIntersection(A, B, C, D, 1e-9);
        if (!hit) continue;

        const p = hit.point;

        // split existing wall
        this.splitWallAtPoint(w.id, p.x, p.y, epsMm);

        // split new wall; if split, enqueue new segments
        const res = this.splitWallAtPoint(wid, p.x, p.y, epsMm);
        if (res?.newWallIds?.length) {
          for (const id of res.newWallIds) queue.push(id);
        }
        // current wall is gone after split; stop checking against others
        break;
      }
    }
  }

  // Move B endpoint to set length, keep A fixed
  setWallLengthMm(wallId, newLenMm) {
    const w = this.getWall(wallId);
    if (!w) return false;
    const A = this.getNode(w.a);
    const B = this.getNode(w.b);
    if (!A || !B) return false;

    const dx = B.x - A.x;
    const dy = B.y - A.y;
    const L = Math.hypot(dx, dy);
    if (L < 1e-6) return false;

    const t = { x: dx / L, y: dy / L };
    const L2 = Math.max(1, newLenMm);

    B.x = A.x + t.x * L2;
    B.y = A.y + t.y * L2;
    return true;
  }

  // Move the non-fixed endpoint to set length, keep the fixed endpoint stable.
  setWallLengthFromFixedNode(wallId, fixedNodeId, newLenMm) {
    const w = this.getWall(wallId);
    if (!w) return false;
    if (w.a !== fixedNodeId && w.b !== fixedNodeId) return false;

    const fixed = this.getNode(fixedNodeId);
    const otherId = (w.a === fixedNodeId) ? w.b : w.a;
    const moving = this.getNode(otherId);
    if (!fixed || !moving) return false;

    const dx = moving.x - fixed.x;
    const dy = moving.y - fixed.y;
    const L = Math.hypot(dx, dy);
    if (L < 1e-6) return false;

    const t = { x: dx / L, y: dy / L };
    const L2 = Math.max(1, newLenMm);

    moving.x = fixed.x + t.x * L2;
    moving.y = fixed.y + t.y * L2;
    return true;
  }
}

// Segment intersection helper (non-collinear). Returns { point, t, u }.
function segmentIntersection(A, B, C, D, eps = 1e-9) {
  const r = { x: B.x - A.x, y: B.y - A.y };
  const s = { x: D.x - C.x, y: D.y - C.y };
  const rxs = r.x * s.y - r.y * s.x;
  if (Math.abs(rxs) < eps) return null; // parallel or collinear

  const qpx = C.x - A.x;
  const qpy = C.y - A.y;
  const t = (qpx * s.y - qpy * s.x) / rxs;
  const u = (qpx * r.y - qpy * r.x) / rxs;

  if (t < -eps || t > 1 + eps || u < -eps || u > 1 + eps) return null;
  const px = A.x + r.x * t;
  const py = A.y + r.y * t;
  return { point: { x: px, y: py }, t, u };
}
