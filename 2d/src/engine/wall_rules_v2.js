// src/engine/wall_rules_v2.js
// Wall Rules Engine - v2 (Alpha/Beta/Gamma)
// Rule 1,2,3 with line/ray intersections (miter joins + exception trimming)

function v(x, y) { return { x, y }; }
function add(a, b) { return v(a.x + b.x, a.y + b.y); }
function sub(a, b) { return v(a.x - b.x, a.y - b.y); }
function mul(a, s) { return v(a.x * s, a.y * s); }
function dot(a, b) { return a.x * b.x + a.y * b.y; }
function cross(a, b) { return a.x * b.y - a.y * b.x; }
function len(a) { return Math.hypot(a.x, a.y); }
function norm(a) {
  const l = len(a);
  if (l === 0) return v(0, 0);
  return v(a.x / l, a.y / l);
}
function perpLeft(a) { return v(-a.y, a.x); }
function perpRight(a) { return v(a.y, -a.x); }
function clamp(x, a, b) { return Math.max(a, Math.min(b, x)); }
function almostEqual(a, b, eps = 1e-9) { return Math.abs(a - b) <= eps; }

// Ray-Ray intersection: p + t*r and q + u*s with t>=0,u>=0
function rayRayIntersection(p, r, q, s, eps = 1e-9) {
  const rxs = cross(r, s);
  if (Math.abs(rxs) < eps) return null;

  const q_p = sub(q, p);
  const t = cross(q_p, s) / rxs;
  const u = cross(q_p, r) / rxs;

  if (t >= -eps && u >= -eps) return add(p, mul(r, t));
  return null;
}

// Line-Line intersection: p + t*r and q + u*s (t/u free)
function lineLineIntersection(p, r, q, s, eps = 1e-9) {
  const rxs = cross(r, s);
  if (Math.abs(rxs) < eps) return null;

  const q_p = sub(q, p);
  const t = cross(q_p, s) / rxs;
  return add(p, mul(r, t));
}

// Ray-Line intersection: p + t*r with t>=0 and q + u*s (u free)
function rayLineIntersection(p, r, q, s, eps = 1e-9) {
  const rxs = cross(r, s);
  if (Math.abs(rxs) < eps) return null;

  const q_p = sub(q, p);
  const t = cross(q_p, s) / rxs;

  if (t >= -eps) return add(p, mul(r, t));
  return null;
}

// Angle between directions (0..180)
function angleDeg(dirA, dirB) {
  const a = norm(dirA);
  const b = norm(dirB);
  const c = clamp(dot(a, b), -1, 1);
  return Math.acos(c) * 180 / Math.PI;
}

export class Node {
  constructor(id, pos) {
    this.id = id;
    this.pos = pos; // {x,y}
  }
}

export class Wall {
  constructor({
    id,
    alphaStartNode,
    alphaEndNode,
    thickness,
    side = "left", // "left" or "right" relative to AlphaStart->AlphaEnd
  }) {
    if (!alphaStartNode || !alphaEndNode) throw new Error("Wall: alpha nodes are required");
    if (!(thickness > 0)) throw new Error("Wall: thickness must be > 0");
    if (side !== "left" && side !== "right") throw new Error("Wall: side must be left/right");

    this.id = id;
    this.a0 = alphaStartNode;
    this.a1 = alphaEndNode;
    this.thickness = thickness;
    this.side = side;
  }

  getAlphaSegment() {
    return { p0: this.a0.pos, p1: this.a1.pos };
  }

  getDirA() {
    return sub(this.a1.pos, this.a0.pos);
  }

  // IMPORTANT: Use half thickness to match your current main.js model
  getBetaSegment() {
    const { p0, p1 } = this.getAlphaSegment();
    const dir = sub(p1, p0);
    const n = norm(this.side === "left" ? perpLeft(dir) : perpRight(dir));
    const off = mul(n, this.thickness / 2);
    return { p0: add(p0, off), p1: add(p1, off) };
  }
}

// Rule 2: shared alpha node (by id, not object identity)
export function getSharedAlphaNode(w1, w2) {
  if (w1.a0?.id === w2.a0?.id) return w1.a0;
  if (w1.a0?.id === w2.a1?.id) return w1.a0;
  if (w1.a1?.id === w2.a0?.id) return w1.a1;
  if (w1.a1?.id === w2.a1?.id) return w1.a1;
  return null;
}

export function areWallsConnectedByAlpha(w1, w2) {
  return !!getSharedAlphaNode(w1, w2);
}

// Rule 3: Gamma using offset line intersections (miter join)
export function computeGammaForJoint(w1, w2, opts = {}) {
  const eps = opts.eps ?? 1e-9;
  const miterLimit = opts.miterLimit ?? 10;

  const shared = getSharedAlphaNode(w1, w2);
  if (!shared) return { ok: false, reason: "Walls are not connected by Alpha" };
  const sharedId = shared.id;

  // We need rays that start at the B-edge point at the joint and go outward.
  // Choose joint = shared Alpha position; then compute beta "joint point" by offsetting joint in each wall.
  const J = shared.pos;

  const d1 = norm(w1.getDirA());
  const d2 = norm(w2.getDirA());

  // Ensure directions go "away" from the joint:
  // If joint is a1, reverse. If joint is a0, keep.
  const jointIsW1Start = (w1.a0?.id === sharedId);
  const jointIsW2Start = (w2.a0?.id === sharedId);
  const dir1 = jointIsW1Start ? d1 : mul(d1, -1);
  const dir2 = jointIsW2Start ? d2 : mul(d2, -1);

  const n1 = norm(w1.side === "left" ? perpLeft(dir1) : perpRight(dir1));
  const n2 = norm(w2.side === "left" ? perpLeft(dir2) : perpRight(dir2));

  const b1J = add(J, mul(n1, w1.thickness / 2));
  const b2J = add(J, mul(n2, w2.thickness / 2));

  // Primary: line-line intersection (miter join).
  // Using infinite lines avoids "no intersection" when both walls are oriented away from the joint.
  const gammaPrimary = lineLineIntersection(b1J, dir1, b2J, dir2, eps);
  if (gammaPrimary) {
    const h = Math.max(w1.thickness, w2.thickness) / 2;
    const miterLen = len(sub(gammaPrimary, J));
    if (isFinite(miterLimit) && miterLimit > 0 && isFinite(h) && h > 0) {
      if (miterLen > h * miterLimit) {
        return {
          ok: false,
          reason: "miter_limit",
          angleDeg: angleDeg(dir1, dir2),
        };
      }
    }
    return {
      ok: true,
      mode: "miter_line",
      gamma: gammaPrimary,
      sharedAlpha: J,
      angleDeg: angleDeg(dir1, dir2),
      trim: null,
    };
  }

  // Exception: thickness not equal AND angle > 90
  const ang = angleDeg(dir1, dir2);
  const thicknessNotEqual = !almostEqual(w1.thickness, w2.thickness, eps);

  if (!(thicknessNotEqual && ang > 90)) {
    return { ok: false, reason: "No primary gamma; exception conditions not met", angleDeg: ang };
  }

  const thinner = (w1.thickness <= w2.thickness) ? w1 : w2;
  const thicker = (thinner === w1) ? w2 : w1;

  // Recompute rays for thinner/thicker with their own directions
  const getRay = (w) => {
    const jointIsStart = (w.a0?.id === sharedId);
    const d = norm(w.getDirA());
    const dir = jointIsStart ? d : mul(d, -1);
    const n = norm(w.side === "left" ? perpLeft(dir) : perpRight(dir));
    const bJ = add(J, mul(n, w.thickness / 2));
    return { bJ, dir };
  };

  const thinRay = getRay(thinner);
  const thickRay = getRay(thicker);

  // Gamma = intersection( extend(b_thinner as ray), b_thicker as infinite line )
  const gammaEx = rayLineIntersection(thinRay.bJ, thinRay.dir, thickRay.bJ, thickRay.dir, eps);
  if (!gammaEx) {
    return { ok: false, reason: "Exception mode: no intersection found", angleDeg: ang };
  }

  return {
    ok: true,
    mode: "exception_thickness_angle",
    gamma: gammaEx,
    sharedAlpha: J,
    angleDeg: ang,
    trim: { wallId: thicker.id, rule: "trim_thicker_after_gamma" },
  };
}
