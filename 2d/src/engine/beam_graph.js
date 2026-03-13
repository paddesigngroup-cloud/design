// src/engine/beam_graph.js
// Node-based beam graph (nodes + Beam edges)
// Beam graph intentionally does not perform wall-specific topology merge/split logic.

export class Node {
  constructor(id, x, y) {
    this.id = id;
    this.x = x; // world mm
    this.y = y; // world mm
  }
}

export class BeamEdge {
  constructor(
    id,
    aNodeId,
    bNodeId,
    thicknessMm = 40,
    heightMm = 200,
    floorOffsetMm = 2600,
    name = "",
  ) {
    this.id = id;
    this.a = aNodeId;
    this.b = bNodeId;

    this.thickness = thicknessMm;
    this.heightMm = heightMm;
    this.floorOffsetMm = floorOffsetMm;
    this.name = name || id;

    // Keep visual style fields aligned with wall usage patterns.
    this.fillColor = "#C7CCD1";
    this.color3d = "#C7CCD1";
  }
}

export class BeamGraph {
  constructor() {
    this.nodes = new Map();       // id -> Node
    this.beams = new Map();       // id -> BeamEdge
    this.nodeToBeams = new Map(); // nodeId -> Set(beamId)

    this._nid = 1;
    this._bid = 1;
  }

  newNodeId() { return `n${this._nid++}`; }
  newBeamId() { return `b${this._bid++}`; }

  clear() {
    this.nodes.clear();
    this.beams.clear();
    this.nodeToBeams.clear();
    this._nid = 1;
    this._bid = 1;
  }

  getNode(nodeId) { return this.nodes.get(nodeId) || null; }
  getBeam(beamId) { return this.beams.get(beamId) || null; }

  addNode(x, y) {
    const id = this.newNodeId();
    const n = new Node(id, x, y);
    this.nodes.set(id, n);
    this.nodeToBeams.set(id, new Set());
    return n;
  }

  moveNode(nodeId, x, y) {
    const n = this.getNode(nodeId);
    if (!n) return false;
    n.x = x;
    n.y = y;
    return true;
  }

  findNearestNode(x, y, tolMm = 30) {
    let best = null;
    let bestD2 = tolMm * tolMm;

    for (const n of this.nodes.values()) {
      const dx = n.x - x;
      const dy = n.y - y;
      const d2 = dx * dx + dy * dy;
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

  _defaultBeamName() {
    const index = this.beams.size;
    const letter = String.fromCharCode(65 + (index % 26));
    const cycle = Math.floor(index / 26);
    return cycle === 0 ? `Beam ${letter}` : `Beam ${letter}-${cycle}`;
  }

  addBeamByNodeIds(
    aNodeId,
    bNodeId,
    thicknessMm = 40,
    heightMm = 200,
    floorOffsetMm = 2600,
    name = "",
  ) {
    if (aNodeId === bNodeId) throw new Error("Beam must connect two distinct nodes");
    if (!this.nodes.has(aNodeId) || !this.nodes.has(bNodeId)) throw new Error("Invalid node id(s)");

    // prevent duplicates
    for (const beam of this.beams.values()) {
      const same = (beam.a === aNodeId && beam.b === bNodeId)
        || (beam.a === bNodeId && beam.b === aNodeId);
      if (same) return beam;
    }

    const id = this.newBeamId();
    const beamName = String(name || "").trim() || this._defaultBeamName();
    const beam = new BeamEdge(id, aNodeId, bNodeId, thicknessMm, heightMm, floorOffsetMm, beamName);

    this.beams.set(id, beam);
    if (!this.nodeToBeams.has(aNodeId)) this.nodeToBeams.set(aNodeId, new Set());
    if (!this.nodeToBeams.has(bNodeId)) this.nodeToBeams.set(bNodeId, new Set());
    this.nodeToBeams.get(aNodeId).add(id);
    this.nodeToBeams.get(bNodeId).add(id);

    return beam;
  }

  addBeamByPoints(
    ax,
    ay,
    bx,
    by,
    thicknessMm = 40,
    heightMm = 200,
    floorOffsetMm = 2600,
    name = "",
    snapTolMm = 30,
  ) {
    const na = this.getOrCreateNode(ax, ay, snapTolMm);
    const nb = this.getOrCreateNode(bx, by, snapTolMm);
    return this.addBeamByNodeIds(na.id, nb.id, thicknessMm, heightMm, floorOffsetMm, name);
  }

  getBeamsAtNode(nodeId) {
    const set = this.nodeToBeams.get(nodeId);
    if (!set) return [];
    return [...set].map((id) => this.beams.get(id)).filter(Boolean);
  }

  deleteBeam(beamId) {
    const beam = this.beams.get(beamId);
    if (!beam) return false;

    this.beams.delete(beamId);

    const sa = this.nodeToBeams.get(beam.a);
    if (sa) sa.delete(beamId);
    const sb = this.nodeToBeams.get(beam.b);
    if (sb) sb.delete(beamId);

    return true;
  }

  // Closest point on any beam segment within tolerance.
  // Returns { beamId, point:{x,y}, t } where t in [0,1] on beam A->B.
  findNearestBeamPoint(x, y, tolMm = 30) {
    let best = null;
    let bestD2 = tolMm * tolMm;

    for (const beam of this.beams.values()) {
      const A = this.getNode(beam.a);
      const B = this.getNode(beam.b);
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
        best = { beamId: beam.id, point: { x: px, y: py }, t };
      }
    }

    return best;
  }

  // Move B endpoint to set length, keep A fixed.
  setBeamLengthMm(beamId, newLenMm) {
    const beam = this.getBeam(beamId);
    if (!beam) return false;
    const A = this.getNode(beam.a);
    const B = this.getNode(beam.b);
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

  // Move the non-fixed endpoint to set length, keep fixed endpoint stable.
  setBeamLengthFromFixedNode(beamId, fixedNodeId, newLenMm) {
    const beam = this.getBeam(beamId);
    if (!beam) return false;
    if (beam.a !== fixedNodeId && beam.b !== fixedNodeId) return false;

    const fixed = this.getNode(fixedNodeId);
    const otherId = (beam.a === fixedNodeId) ? beam.b : beam.a;
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
