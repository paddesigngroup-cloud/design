/* =============================
   main.js (Node-based v2) — Full integration (fixed)
   Fixes:
   1) Dimension buttons constant px (no scaling with zoom/resize)
   2) Clicking wall/UI does NOT start drawing
   3) Rounded buttons + aligned to dimension text
   4) Buttons work (events routed correctly)
   5) Dimension behind wall name (name on top)
   6) Arrow icon perpendicular, always below dimension text, no mirroring jumps
   7) "O" removed
   8) Offset toggle arrow like dimension arrow (per wall)
============================= */

import { WallGraph } from "./src/engine/wall_graph_v2.js";
import { Node as RuleNode, Wall as RuleWall, computeGammaForJoint } from "./src/engine/wall_rules_v2.js";
import { SolidWallTool } from "./src/engine/tools/SolidWallTool.js";
import { HiddenWallTool, drawHiddenWalls } from "./hiddenwall.js";
import { DimensionTool } from "./src/engine/dimension.js";

/* =============================
   Runtime Error Overlay (helps debugging on user machines)
============================= */
let _fatalErrorText = null;
function showFatalError(msg) {
  _fatalErrorText = String(msg || "Unknown error");
  try {
    let el = document.getElementById("fatalErrorOverlay");
    if (!el) {
      el = document.createElement("pre");
      el.id = "fatalErrorOverlay";
      el.style.position = "fixed";
      el.style.left = "12px";
      el.style.top = "12px";
      el.style.zIndex = "9999";
      el.style.maxWidth = "min(920px, calc(100vw - 24px))";
      el.style.maxHeight = "min(420px, calc(100vh - 24px))";
      el.style.overflow = "auto";
      el.style.padding = "12px 14px";
      el.style.border = "1px solid rgba(255,0,0,.35)";
      el.style.borderRadius = "12px";
      el.style.background = "rgba(255,255,255,.94)";
      el.style.backdropFilter = "blur(6px)";
      el.style.boxShadow = "0 18px 60px rgba(0,0,0,.20)";
      el.style.color = "#111";
      el.style.font = "12px/1.6 ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, \"Liberation Mono\", \"Courier New\", monospace";
      el.style.direction = "ltr";
      el.style.textAlign = "left";
      document.body.appendChild(el);
    }
    el.textContent = _fatalErrorText;
  } catch (_) {}
}

let _globalErrorHooksInstalled = false;
function installGlobalErrorHooksOnce() {
  if (_globalErrorHooksInstalled) return;
  _globalErrorHooksInstalled = true;
  if (typeof window === "undefined") return;

  window.addEventListener("error", (e) => {
    const msg = e?.error?.stack || e?.message || "Unknown window error";
    showFatalError(msg);
  });
  window.addEventListener("unhandledrejection", (e) => {
    const msg = e?.reason?.stack || e?.reason || "Unhandled promise rejection";
    showFatalError(msg);
  });
}

export function createWallApp({ canvas, container, onModel2dTransformChange } = {}) {
  installGlobalErrorHooksOnce();

  // Boot flag (used by standalone index.html to detect module load failures)
  if (typeof window !== "undefined") window.__WALL_APP_BOOT_OK__ = false;

  if (!canvas) throw new Error("createWallApp: canvas is required");
  const ctx = canvas.getContext("2d");
  if (!ctx) throw new Error("createWallApp: 2D context not available");
  if (!container) container = canvas.parentElement || document.body;

  // Cursor tracking (must be initialized before the first draw loop tick)
  let lastMouseX = 0;
  let lastMouseY = 0;
  let isMouseOverCanvas = false;
  let inputEnabled = true;

  function setInputEnabled(v) {
    inputEnabled = !!v;
    if (!inputEnabled) {
      isPanning = false;
    }
  }

  /* =============================
     Canvas / DPR / Viewport (container-sized)
  ============================= */
  let DPR = 1;
  let viewportW = 1;
  let viewportH = 1;

  function resize() {
    DPR = (typeof window !== "undefined" && window.devicePixelRatio) ? window.devicePixelRatio : 1;
    const rect = container.getBoundingClientRect();
    const w = Math.max(1, Math.floor(rect.width || 1));
    const h = Math.max(1, Math.floor(rect.height || 1));

    viewportW = w;
    viewportH = h;

    canvas.width = Math.floor(w * DPR);
    canvas.height = Math.floor(h * DPR);
    ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
  }
  resize();

  /* =============================
     State
  ============================= */
  const state = {
  unit: "cm",

  // Modal tool selection (AutoCAD-like)
  activeTool: "wall", // "select" | "wall" | "hidden" | "dim"
  // Object snap + guides overlay
  snapOn: true,
  snapCornerEnabled: true,
  snapMidEnabled: true,
  snapCenterEnabled: true,
  snapEdgeEnabled: true,
  // Placeholder for staged drawing mode (UI state).
  stepDrawMode: "line",

  meterDivisions: 10,
  majorEvery: 10,
  bgColor: "#FFFFFF",
  minorColor: "#E6E6E6",
  majorColor: "#A3A3A3",
  axisXColor: "#9CC9B4",
  axisYColor: "#BCC8EB",
  showObjectAxes: false,

  wallFillColor: "#A6A6A6",
  wallEdgeColor: "#000000",
  wallTextColor: "#FFFFFF",
  wallHeightColor: "#4B5563",
  // Global wall thickness (world millimeters). UI shows cm.
  wallThicknessMm: 120,
  // Global wall height (world millimeters). UI shows cm.
  wallHeightMm: 3000,

  // Hidden walls (dashed guide-like lines)
  hiddenWallColor: "#D8D4D4",
  hiddenWallLineWidthPx: 2,
  hiddenWallDash: [10, 8],

  dimColor: "#E8A559",
  dimFontPx: 15,
  dimLineWidthPx: 2,
  dimOffsetMm: 150,
  dimTickPx: 8,
  dimGapTextPx: 6,
  dimTextPadPx: 6,
  showDimensions: true,

  angleColor: "#E8A559",
  angleFontPx: 12,
  angleRadiusPx: 22,
  angleArcWidthPx: 2,

  offsetWallEnabled: true,
  offsetWallDistanceMm: 600,
  offsetWallColor: "#D8D4D4",
  offsetWallLineWidthPx: 2,
  offsetWallDash: [10, 8],

  fontFamily: "Tahoma",
  wallNameFontPx: 15,

  zoom: 1,
  offsetX: 0,
  offsetY: 0,

  // Miter join limit multiplier (relative to half thickness).
  // Higher = longer miters allowed at sharp angles.
  miterLimit: 10,

  showGammaDebug: false,
  };

const STORAGE_KEY = "wall_v1_settings_rtl_v2";
function loadSettings() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const obj = JSON.parse(raw);
    if (!obj || typeof obj !== "object") return;
    for (const k of Object.keys(state)) if (k in obj) state[k] = obj[k];
  } catch (_) {}
}
function saveSettings() {
  try {
    const obj = {};
    for (const k of Object.keys(state)) obj[k] = state[k];
    localStorage.setItem(STORAGE_KEY, JSON.stringify(obj));
  } catch (_) {}
}
loadSettings();
// Keep gamma debug off for now (industrial view).
state.showGammaDebug = false;
// Default tool on load.
state.activeTool = "wall";

/* =============================
   Camera
============================= */
function resetCameraToOriginCenter() {
  // Ensure initial view shows at least 6m x 6m (world is in millimeters).
  const minWorldMm = 6000;
  const fitZoom = 0.9 * Math.min(viewportW, viewportH) / minWorldMm;
  state.zoom = clamp(fitZoom, 0.05, 20);
  state.offsetX = viewportW / 2;
  state.offsetY = viewportH / 2;
}
resetCameraToOriginCenter();

/* =============================
   Transforms
============================= */
function worldToScreen(x, y) {
  return { x: x * state.zoom + state.offsetX, y: -y * state.zoom + state.offsetY };
}
function screenToWorld(x, y) {
  return { x: (x - state.offsetX) / state.zoom, y: -(y - state.offsetY) / state.zoom };
}

/* =============================
   Utils
============================= */
function clamp(v, a, b) { return Math.max(a, Math.min(b, v)); }
function len(ax, ay, bx, by) { return Math.hypot(bx-ax, by-ay); }
function normalize(x, y) { const l = Math.hypot(x, y) || 1; return { x:x/l, y:y/l }; }
function dot(ax, ay, bx, by) { return ax*bx + ay*by; }
function radToDeg(r) { return r * 180 / Math.PI; }

function angleBetween(ax, ay, bx, by) {
  const na = normalize(ax, ay);
  const nb = normalize(bx, by);
  const d = clamp(dot(na.x, na.y, nb.x, nb.y), -1, 1);
  return Math.acos(d);
}

function pointToSegmentDistance(px, py, ax, ay, bx, by) {
  const abx = bx - ax, aby = by - ay;
  const apx = px - ax, apy = py - ay;
  const ab2 = abx*abx + aby*aby;
  if (ab2 === 0) return Math.hypot(px-ax, py-ay);

  let t = (apx*abx + apy*aby) / ab2;
  t = clamp(t, 0, 1);

  const cx = ax + t*abx;
  const cy = ay + t*aby;
  return Math.hypot(px-cx, py-cy);
}

function pointToSegmentDistancePx(px, py, ax, ay, bx, by) {
  // Same as pointToSegmentDistance but in screen pixels.
  return pointToSegmentDistance(px, py, ax, ay, bx, by);
}

function lineIntersect(p1, p2, p3, p4) {
  const x1=p1.x,y1=p1.y,x2=p2.x,y2=p2.y;
  const x3=p3.x,y3=p3.y,x4=p4.x,y4=p4.y;
  const den = (x1-x2)*(y3-y4) - (y1-y2)*(x3-x4);
  if (Math.abs(den) < 1e-9) return null;

  const px = ((x1*y2 - y1*x2)*(x3 - x4) - (x1 - x2)*(x3*y4 - y3*x4)) / den;
  const py = ((x1*y2 - y1*x2)*(y3 - y4) - (y1 - y2)*(x3*y4 - y3*x4)) / den;
  return { x:px, y:py };
}

function rectFrom2Points(x1, y1, x2, y2) {
  return {
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    w: Math.abs(x2 - x1),
    h: Math.abs(y2 - y1),
  };
}

function segmentIntersectsRectScreen(ax, ay, bx, by, r) {
  if (pointInRect(ax, ay, r) || pointInRect(bx, by, r)) return true;
  const edges = [
    [{ x: r.x, y: r.y }, { x: r.x + r.w, y: r.y }],
    [{ x: r.x + r.w, y: r.y }, { x: r.x + r.w, y: r.y + r.h }],
    [{ x: r.x + r.w, y: r.y + r.h }, { x: r.x, y: r.y + r.h }],
    [{ x: r.x, y: r.y + r.h }, { x: r.x, y: r.y }],
  ];
  const eps = 1e-6;
  function onSeg(px, py, x1, y1, x2, y2) {
    return px >= Math.min(x1, x2) - eps && px <= Math.max(x1, x2) + eps &&
      py >= Math.min(y1, y2) - eps && py <= Math.max(y1, y2) + eps;
  }
  for (const [p, q] of edges) {
    const hit = lineIntersect({ x: ax, y: ay }, { x: bx, y: by }, p, q);
    if (!hit) continue;
    if (onSeg(hit.x, hit.y, ax, ay, bx, by) && onSeg(hit.x, hit.y, p.x, p.y, q.x, q.y)) return true;
  }
  return false;
}

function formatLengthMm(mm) {
  if (state.unit === "cm") return `${(mm / 10).toFixed(1)} cm`;
  return `${Math.round(mm)} mm`;
}

function parseUserLengthToMm(str) {
  if (typeof str !== "string") return null;
  const s = str.trim().toLowerCase();
  const m = s.match(/^([0-9]+(\.[0-9]+)?)\s*(mm|cm)?$/);
  if (!m) return null;
  const v = parseFloat(m[1]);
  const unit = m[3] || state.unit;
  if (!isFinite(v) || v <= 0) return null;
  return unit === "cm" ? v * 10 : v;
}

function computePolygonCentroidWorld(pts) {
  if (!Array.isArray(pts) || pts.length < 3) return null;
  let twiceArea = 0;
  let cx = 0;
  let cy = 0;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const p0 = pts[j];
    const p1 = pts[i];
    const cross = p0.x * p1.y - p1.x * p0.y;
    twiceArea += cross;
    cx += (p0.x + p1.x) * cross;
    cy += (p0.y + p1.y) * cross;
  }
  if (Math.abs(twiceArea) < 1e-9) {
    let sx = 0;
    let sy = 0;
    for (const p of pts) {
      sx += p.x;
      sy += p.y;
    }
    return { x: sx / pts.length, y: sy / pts.length };
  }
  const k = 1 / (3 * twiceArea);
  return { x: cx * k, y: cy * k };
}

function getInteriorReferencePointWorld() {
  if (Array.isArray(model2d.outline) && model2d.outline.length >= 3) {
    const c = computePolygonCentroidWorld(model2d.outline);
    if (c) return c;
  }
  let sx = 0;
  let sy = 0;
  let cnt = 0;
  for (const n of graph.nodes.values()) {
    sx += n.x;
    sy += n.y;
    cnt++;
  }
  if (cnt > 0) return { x: sx / cnt, y: sy / cnt };
  return null;
}

function chooseInsideSideSign(ax, ay, bx, by) {
  const d = normalize(bx - ax, by - ay);
  const nWorldLeft = { x: -d.y, y: d.x };
  const mid = { x: (ax + bx) / 2, y: (ay + by) / 2 };
  const ref = getInteriorReferencePointWorld();
  if (ref) {
    const toRefX = ref.x - mid.x;
    const toRefY = ref.y - mid.y;
    const proj = dot(toRefX, toRefY, nWorldLeft.x, nWorldLeft.y);
    if (Math.abs(proj) > 1e-6) return proj >= 0 ? 1 : -1;
  }
  const nScr = chooseDimensionNormalScreen(ax, ay, bx, by);
  return screenNormalToWorldSideSign(ax, ay, bx, by, nScr);
}

function chooseInsideSideSignForWall(edge) {
  if (!edge) return 1;
  const A = graph.getNode(edge.a);
  const B = graph.getNode(edge.b);
  if (!A || !B) return 1;

  const d = normalize(B.x - A.x, B.y - A.y);
  const nWorldLeft = { x: -d.y, y: d.x };
  if (Array.isArray(model2d.outline) && model2d.outline.length >= 3) {
    const mid = { x: (A.x + B.x) / 2, y: (A.y + B.y) / 2 };
    const testDist = Math.max(60, state.offsetWallDistanceMm || 0);
    const pLeft = { x: mid.x + nWorldLeft.x * testDist, y: mid.y + nWorldLeft.y * testDist };
    const pRight = { x: mid.x - nWorldLeft.x * testDist, y: mid.y - nWorldLeft.y * testDist };
    const inLeft = pointInPolygonWorld(pLeft.x, pLeft.y, model2d.outline);
    const inRight = pointInPolygonWorld(pRight.x, pRight.y, model2d.outline);
    if (inLeft !== inRight) return inLeft ? 1 : -1;
  }
  let score = 0;
  const ends = [
    edge.a,
    edge.b,
  ];

  for (const jointId of ends) {
    const J = graph.getNode(jointId);
    const connected = graph.nodeToWalls.get(jointId);
    if (!J || !connected || connected.size <= 1) continue;

    for (const wid of connected) {
      if (wid === edge.id) continue;
      const w2 = graph.getWall(wid);
      if (!w2) continue;
      const Oa = graph.getNode(w2.a);
      const Ob = graph.getNode(w2.b);
      if (!Oa || !Ob) continue;

      const ox = (w2.a === jointId) ? (Ob.x - Oa.x) : (Oa.x - Ob.x);
      const oy = (w2.a === jointId) ? (Ob.y - Oa.y) : (Oa.y - Ob.y);
      const oLen = Math.hypot(ox, oy);
      if (oLen < 1e-9) continue;

      const ux = ox / oLen;
      const uy = oy / oLen;
      const sideProj = dot(ux, uy, nWorldLeft.x, nWorldLeft.y);
      const turnWeight = Math.abs(d.x * uy - d.y * ux); // prefer non-collinear neighbors
      score += sideProj * Math.max(0.2, turnWeight);
    }
  }

  if (Math.abs(score) > 0.03) return score >= 0 ? 1 : -1;
  return chooseInsideSideSign(A.x, A.y, B.x, B.y);
}

function resolveOffsetSideSign(edge) {
  if (!edge) return 1;
  if (!edge.offsetSideManual) return chooseInsideSideSignForWall(edge);
  const pref = edge.offsetSide || "auto";
  if (pref === "left") return 1;
  if (pref === "right") return -1;
  return chooseInsideSideSignForWall(edge);
}

function getOffsetAxisDistanceMm(edge) {
  const wallThickness = (typeof edge?.thickness === "number" && isFinite(edge.thickness))
    ? Math.max(0, edge.thickness)
    : Math.max(0, state.wallThicknessMm || 0);
  return Math.max(0, state.offsetWallDistanceMm || 0) + wallThickness / 2;
}

/* =============================
   Dimension placement
============================= */
function chooseDimensionNormalScreen(ax, ay, bx, by) {
  const aS = worldToScreen(ax, ay);
  const bS = worldToScreen(bx, by);
  const dx = bS.x - aS.x;
  const dy = bS.y - aS.y;
  const L = Math.hypot(dx, dy) || 1;

  const n1 = { x: -dy / L, y: dx / L };
  const n2 = { x: -n1.x, y: -n1.y };

  const adx = Math.abs(dx);
  const ady = Math.abs(dy);

  if (adx >= ady) return (n1.y > 0) ? n1 : n2; // below
  return (n1.x < 0) ? n1 : n2;                 // left
}

function screenNormalToWorldSideSign(ax, ay, bx, by, nScr) {
  const d = normalize(bx - ax, by - ay);
  const nWorldLeft = { x: -d.y, y: d.x };
  const leftScr = { x: nWorldLeft.x * state.zoom, y: -nWorldLeft.y * state.zoom };
  return (dot(nScr.x, nScr.y, leftScr.x, leftScr.y) >= 0) ? 1 : -1;
}

// sidePref: "auto" | "left" | "right"
function chooseSideSignWithPref(ax, ay, bx, by, sidePref, edge = null) {
  if (sidePref === "auto") {
    if (edge) return chooseInsideSideSignForWall(edge);
    return chooseInsideSideSign(ax, ay, bx, by);
  }
  return sidePref === "left" ? 1 : -1;
}

/* =============================
   MODEL: Graph
============================= */
const graph = new WallGraph();
graph.clear();
const hiddenGraph = new WallGraph();
hiddenGraph.clear();

let selectedWallId = null;
let hoverWallId = null;
let lastJointGammaMap = null; // cached per-frame for accurate hover/selection outlines
let selectedHiddenId = null;
let hoverHiddenId = null;
let selectedDimId = null;
let hoverDimId = null;
let selectedWallIds = [];
let selectedHiddenIds = [];
let selectedDimIds = [];
let hoverDimTextWallId = null;
let hoverWallHandle = null; // { type, wallId }
const wallDimDrag = {
  active: false,
  wallId: null,
  startDimSide: "auto",
  startSide: "left",
  startOffsetMm: 0,
  startX: 0,
  startY: 0,
  moved: false,
};
const wallHandleDrag = {
  active: false,
  kind: null, // len_a|len_b|free_a|free_b|mid_move
  wallId: null,
  graphStartSnap: null,
  startMouse: null, // world
  startA: null,
  startB: null,
  moved: false,
};
const boxSelect = {
  active: false,
  startX: 0,
  startY: 0,
  curX: 0,
  curY: 0,
};
const modelDrag = {
  active: false,
  startMouseWorld: null,
  startLines: null,
  startOutline: null,
  startOffsetXmm: 0,
  startOffsetYmm: 0,
  startRotationRad: 0,
  startSnap: null,
  moved: false,
};
const axisDrag = {
  active: false,
  axis: null, // "x" | "y"
  targetType: null, // "wall" | "hidden" | "dim" | "model"
  startMouseWorld: null,
  startGraphSnap: null,
  startHiddenGraphSnap: null,
  startDimensionsSnap: null,
  startModelSnap: null,
  moved: false,
};
let hoverObjectAxis = null; // "x" | "y" | null

function clearGroupSelection() {
  selectedWallIds = [];
  selectedHiddenIds = [];
  selectedDimIds = [];
}

function _cloneModel2dLines(lines) {
  return (lines || []).map((l) => ({ ax: l.ax, ay: l.ay, bx: l.bx, by: l.by }));
}
function _cloneModel2dOutline(outline) {
  return (outline || []).map((p) => ({ x: p.x, y: p.y }));
}
function startModelDrag(offsetX, offsetY) {
  if (!model2d.lines || model2d.lines.length === 0) return false;
  modelDrag.active = true;
  modelDrag.startMouseWorld = screenToWorld(offsetX, offsetY);
  modelDrag.startLines = _cloneModel2dLines(model2d.lines);
  modelDrag.startOutline = _cloneModel2dOutline(model2d.outline);
  modelDrag.startOffsetXmm = model2d.offsetXmm || 0;
  modelDrag.startOffsetYmm = model2d.offsetYmm || 0;
  modelDrag.startRotationRad = model2d.rotationRad || 0;
  modelDrag.startSnap = snapshotModel2d(model2d);
  modelDrag.moved = false;
  return true;
}
function emitModel2dTransform() {
  if (typeof onModel2dTransformChange !== "function") return;
  try {
    onModel2dTransformChange({
      x: model2d.offsetXmm || 0,
      y: model2d.offsetYmm || 0,
      rotRad: model2d.rotationRad || 0,
    });
  } catch (_) {}
}
<<<<<<< ours
function applyModelDrag(targetWorld) {
  if (!modelDrag.active || !modelDrag.startMouseWorld) return;
  const dx = targetWorld.x - modelDrag.startMouseWorld.x;
  const dy = targetWorld.y - modelDrag.startMouseWorld.y;

  let rotRad = 0;
  let snapTx = 0;
  let snapTy = 0;
  if (state.snapOn && (modelDrag.startOutline || []).length >= 2 && graph.walls.size > 0) {
    const movedOutline = (modelDrag.startOutline || []).map((p) => ({ x: p.x + dx, y: p.y + dy }));
    const nearest = nearestWallToPoints(movedOutline);
    if (nearest && nearest.dist <= MODEL_WALL_SNAP_DIST_MM) {
      const wallAng = Math.atan2(nearest.dir.y, nearest.dir.x);
      const modelAng = dominantModelAngle(modelDrag.startLines || []);
      if (isFinite(modelAng)) {
        const d0 = wrapAnglePi(wallAng - modelAng);
        const d1 = wrapAnglePi(d0 + Math.PI);
        rotRad = Math.abs(d1) < Math.abs(d0) ? d1 : d0;
      }

      transformModelFromStart(dx, dy, rotRad, 0, 0);
      const nearestAfterRotate = nearestWallToPoints(model2d.outline || []);
      if (nearestAfterRotate && nearestAfterRotate.dist <= MODEL_WALL_SNAP_DIST_MM) {
        snapTx = nearestAfterRotate.wallPoint.x - nearestAfterRotate.modelPoint.x;
        snapTy = nearestAfterRotate.wallPoint.y - nearestAfterRotate.modelPoint.y;
      }
    }
  }

  transformModelFromStart(dx, dy, rotRad, snapTx, snapTy);
  model2d.offsetXmm = (modelDrag.startOffsetXmm || 0) + dx + snapTx;
  model2d.offsetYmm = (modelDrag.startOffsetYmm || 0) + dy + snapTy;
  model2d.rotationRad = wrapAnglePi((modelDrag.startRotationRad || 0) + rotRad);
  emitModel2dTransform();
}
function resolveModelDragTargetWorld(rawTargetWorld) {
  if (!modelDrag.active || !modelDrag.startMouseWorld) return rawTargetWorld;

  const tolMm = Math.max(8, (SNAP_TOL_PX * 1.5) / Math.max(state.zoom, 1e-6));
  const baseDx = rawTargetWorld.x - modelDrag.startMouseWorld.x;
  const baseDy = rawTargetWorld.y - modelDrag.startMouseWorld.y;

  let best = null;
  function considerAnchor(anchorX, anchorY) {
    const candidates = collectSnapCandidatesWorld(anchorX, anchorY, tolMm);
    for (const c of candidates) {
      const shiftX = c.x - anchorX;
      const shiftY = c.y - anchorY;
      const score = {
        priority: c.priority,
        d2: c.d2,
      };
      if (!best) {
        best = { shiftX, shiftY, score };
        continue;
      }
      if (score.priority > best.score.priority || (score.priority === best.score.priority && score.d2 < best.score.d2)) {
        best = { shiftX, shiftY, score };
      }
    }
  }

  considerAnchor(rawTargetWorld.x, rawTargetWorld.y);

  const pts = modelDrag.startOutline || [];
  if (pts.length >= 2) {
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i];
      const b = pts[(i + 1) % pts.length];
      considerAnchor(a.x + baseDx, a.y + baseDy);
      considerAnchor((a.x + b.x) / 2 + baseDx, (a.y + b.y) / 2 + baseDy);
    }
  }

  if (!best) return rawTargetWorld;
  return {
    x: rawTargetWorld.x + best.shiftX,
    y: rawTargetWorld.y + best.shiftY,
  };
}
function stopModelDrag(keepMovedGeometry = true) {
  if (!modelDrag.active) return;
  if (!keepMovedGeometry && modelDrag.startLines && modelDrag.startOutline) {
    model2d.lines = _cloneModel2dLines(modelDrag.startLines);
    model2d.outline = _cloneModel2dOutline(modelDrag.startOutline);
    model2d.offsetXmm = modelDrag.startOffsetXmm || 0;
    model2d.offsetYmm = modelDrag.startOffsetYmm || 0;
    model2d.rotationRad = modelDrag.startRotationRad || 0;
    emitModel2dTransform();
  }
  modelDrag.active = false;
  modelDrag.startMouseWorld = null;
  modelDrag.startLines = null;
  modelDrag.startOutline = null;
  modelDrag.startOffsetXmm = 0;
  modelDrag.startOffsetYmm = 0;
  modelDrag.startRotationRad = 0;
  modelDrag.startSnap = null;
  modelDrag.moved = false;
}

// Standalone dimensions (AutoCAD-like 3-click). Implemented later; keep store here for Clear/Undo scaffolding.
const dimensions = [];

/* =============================
   Inline dimension editor (no popup)
============================= */
const dimEditor = {
  active: false,
  wallId: null,
  input: null,
};

function ensureDimEditorInput() {
  if (dimEditor.input) return dimEditor.input;

  const el = document.createElement("input");
  el.type = "text";
  el.autocomplete = "off";
  el.spellcheck = false;
  el.dir = "ltr";
  el.style.position = "fixed";
  el.style.zIndex = "1000";
  el.style.display = "none";
  el.style.padding = "0 6px";
  el.style.borderRadius = "8px";
  el.style.border = "1px solid rgba(0,0,0,0.35)";
  el.style.background = "rgba(255,255,255,0.92)";
  el.style.color = "#111";
  el.style.font = `${state.dimFontPx}px ${state.fontFamily}`;
  el.style.textAlign = "center";
  el.style.outline = "none";
  el.style.boxShadow = "0 10px 25px rgba(0,0,0,0.12)";

  el.addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      commitDimEditor();
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      closeDimEditor(false);
      return;
    }
  });

  // If user clicks away, cancel instead of committing implicitly.
  el.addEventListener("blur", () => closeDimEditor(false));

  document.body.appendChild(el);
  dimEditor.input = el;
  return el;
}

function openDimEditor(wallId) {
  const w = graph.getWall(wallId);
  if (!w) return;
  const A = graph.getNode(w.a);
  const B = graph.getNode(w.b);
  if (!A || !B) return;

  ensureDimEditorInput();

  dimEditor.active = true;
  dimEditor.wallId = wallId;

  // Match the drawn dimension value for the current dimension side.
  const nodeMap = buildNodeEndpointMap(graph);
  const jointGammaMap = buildJointGammaMap(nodeMap);
  const c = computeTrimmedWallCorners(w, jointGammaMap);
  const sideSign = chooseSideSignWithPref(A.x, A.y, B.x, B.y, w.dimSide || "auto", w);
  const curLen = c ? ((sideSign === 1) ? c.leftLen : c.rightLen) : Math.hypot(B.x - A.x, B.y - A.y);
  dimEditor.input.value = formatLengthMm(curLen);
  dimEditor.input.style.display = "block";
  positionDimEditor(jointGammaMap);
  dimEditor.input.focus({ preventScroll: true });
  dimEditor.input.select();
}

function closeDimEditor(keepSelection = true) {
  dimEditor.active = false;
  dimEditor.wallId = null;
  if (dimEditor.input) dimEditor.input.style.display = "none";
  if (!keepSelection) {
    hoverWallId = null;
    selectedWallId = null;
    hoverHiddenId = null;
    selectedHiddenId = null;
    hoverDimId = null;
    selectedDimId = null;
    clearGroupSelection();
  }
}

function commitDimEditor() {
  if (!dimEditor.active || !dimEditor.wallId || !dimEditor.input) return;
  const targetMm = parseUserLengthToMm(dimEditor.input.value ?? "");
  if (targetMm) {
    const wallId = dimEditor.wallId;
    // Adjust centerline length so the rendered useful dimension matches the requested value.
    undo.runAction(() => {
      let guess = Math.max(1, targetMm);

      const w = graph.getWall(wallId);
      if (!w) return;
      const A0 = graph.getNode(w.a);
      const B0 = graph.getNode(w.b);
      const sideSign = (A0 && B0) ? chooseSideSignWithPref(A0.x, A0.y, B0.x, B0.y, w.dimSide || "auto", w) : 1;

      // Seed guess using current error (derivative ~ 1).
      {
        const nodeMap0 = buildNodeEndpointMap(graph);
        const jointGammaMap0 = buildJointGammaMap(nodeMap0);
        const c0 = computeTrimmedWallCorners(w, jointGammaMap0);
        if (A0 && B0) {
          const curCenter = Math.hypot(B0.x - A0.x, B0.y - A0.y);
          const curFace = c0 ? ((sideSign === 1) ? c0.leftLen : c0.rightLen) : curCenter;
          guess = Math.max(1, curCenter + (targetMm - curFace));
        }
      }

      for (let i = 0; i < 6; i++) {
        graph.setWallLengthMm(wallId, guess);

        const nodeMap = buildNodeEndpointMap(graph);
        const jointGammaMap = buildJointGammaMap(nodeMap);
        const c = computeTrimmedWallCorners(w, jointGammaMap);

        const A = graph.getNode(w.a);
        const B = graph.getNode(w.b);
        const curFace = (c && isFinite(c.leftLen) && isFinite(c.rightLen))
          ? ((sideSign === 1) ? c.leftLen : c.rightLen)
          : (A && B ? Math.hypot(B.x - A.x, B.y - A.y) : guess);

        const err = targetMm - curFace;
        if (!isFinite(err) || Math.abs(err) < 0.1) break;

        guess = Math.max(1, guess + err);
      }

      // Driving dimension: keep the last "useful" length stable across topology changes (best-effort).
      w.lockedInsideLenMm = targetMm;
    });
    selectedWallId = wallId;
  }
  closeDimEditor(true);
}

function positionDimEditor(jointGammaMap = null) {
  if (!dimEditor.active || !dimEditor.wallId || !dimEditor.input) return;
  const w = graph.getWall(dimEditor.wallId);
  if (!w) { closeDimEditor(false); return; }
  const A = graph.getNode(w.a);
  const B = graph.getNode(w.b);
  if (!A || !B) { closeDimEditor(false); return; }

  let jgm = jointGammaMap;
  if (!jgm) {
    const nodeMap = buildNodeEndpointMap(graph);
    jgm = buildJointGammaMap(nodeMap);
  }
  const c = computeTrimmedWallCorners(w, jgm);
  const wallDimOffset =
    (typeof w.dimOffsetMm === "number" && isFinite(w.dimOffsetMm))
      ? Math.max(0, w.dimOffsetMm)
      : state.dimOffsetMm;
  const opts = c
    ? { anchorsBySide: c.anchorsBySide, offsetMm: wallDimOffset, wallEdge: w }
    : { offsetMm: wallDimOffset, wallEdge: w };

  const lay = computeDimensionLayout(A.x, A.y, B.x, B.y, w.dimSide || "auto", c ? { left: c.leftLen, right: c.rightLen } : null, opts);
  if (!lay) { closeDimEditor(false); return; }

  const r = lay.textRect;
  dimEditor.input.style.left = `${Math.round(r.x)}px`;
  dimEditor.input.style.top = `${Math.round(r.y)}px`;
  dimEditor.input.style.width = `${Math.round(Math.max(70, r.w))}px`;
  dimEditor.input.style.height = `${Math.round(r.h)}px`;
  dimEditor.input.style.lineHeight = `${Math.round(r.h)}px`;
  dimEditor.input.style.font = `${state.dimFontPx}px ${state.fontFamily}`;
}

/* =============================
   Undo (Ctrl+Z) for wall edits
   - Snapshots only graph + tool chaining state
   - Does NOT include camera or UI settings
============================= */
function _idNum(id) {
  if (typeof id !== "string" || id.length < 2) return Number.POSITIVE_INFINITY;
  const n = Number.parseInt(id.slice(1), 10);
  return Number.isFinite(n) ? n : Number.POSITIVE_INFINITY;
}

function snapshotGraph(g) {
  const nodes = [];
  for (const n of g.nodes.values()) nodes.push({ id: n.id, x: n.x, y: n.y });
  nodes.sort((a, b) => _idNum(a.id) - _idNum(b.id));

  const walls = [];
  for (const w of g.walls.values()) {
    walls.push({
      id: w.id,
      a: w.a,
      b: w.b,
      thickness: w.thickness,
      name: w.name,
      dimSide: w.dimSide ?? "auto",
      offsetSide: w.offsetSide ?? "auto",
      offsetSideManual: !!w.offsetSideManual,
      dimOffsetMm: (typeof w.dimOffsetMm === "number" && isFinite(w.dimOffsetMm)) ? Math.max(0, w.dimOffsetMm) : null,
      dimAlwaysVisible: !!w.dimAlwaysVisible,
      lockedInsideLenMm: (typeof w.lockedInsideLenMm === "number") ? w.lockedInsideLenMm : null,
    });
  }
  walls.sort((a, b) => _idNum(a.id) - _idNum(b.id));

  return { _nid: g._nid, _wid: g._wid, nodes, walls };
}

function restoreGraph(g, snap) {
  g.nodes = new Map();
  g.walls = new Map();
  g.nodeToWalls = new Map();
  g._nid = snap?._nid ?? 1;
  g._wid = snap?._wid ?? 1;

  for (const n of snap?.nodes ?? []) {
    const node = { id: n.id, x: n.x, y: n.y };
    g.nodes.set(node.id, node);
    g.nodeToWalls.set(node.id, new Set());
  }

  for (const w of snap?.walls ?? []) {
    const wall = {
      id: w.id,
      a: w.a,
      b: w.b,
      thickness: w.thickness,
      name: w.name,
      dimSide: w.dimSide ?? "auto",
      offsetSide: w.offsetSide ?? "auto",
      offsetSideManual: !!w.offsetSideManual,
      dimOffsetMm: (typeof w.dimOffsetMm === "number" && isFinite(w.dimOffsetMm)) ? Math.max(0, w.dimOffsetMm) : null,
      dimAlwaysVisible: !!w.dimAlwaysVisible,
      lockedInsideLenMm: (typeof w.lockedInsideLenMm === "number") ? w.lockedInsideLenMm : null,
    };
    g.walls.set(wall.id, wall);

    if (!g.nodeToWalls.has(wall.a)) g.nodeToWalls.set(wall.a, new Set());
    if (!g.nodeToWalls.has(wall.b)) g.nodeToWalls.set(wall.b, new Set());
    g.nodeToWalls.get(wall.a).add(wall.id);
    g.nodeToWalls.get(wall.b).add(wall.id);
  }
}

function snapshotTool(t) {
  return {
    wallIndex: t?.wallIndex ?? 0,
    pendingStartNodeId: t?.pendingStartNodeId ?? null,
    snapEnabled: (typeof t?.snapEnabled === "boolean") ? t.snapEnabled : true,
    lastDir: t?.lastDir ? { x: t.lastDir.x, y: t.lastDir.y } : null,
  };
}

function restoreTool(t, g, snap) {
  if (!t) return;
  t.wallIndex = snap?.wallIndex ?? t.wallIndex ?? 0;
  t.pendingStartNodeId = snap?.pendingStartNodeId ?? null;
  if (typeof snap?.snapEnabled === "boolean") t.snapEnabled = snap.snapEnabled;
  t.lastDir = snap?.lastDir ? { x: snap.lastDir.x, y: snap.lastDir.y } : null;

  const n = t.pendingStartNodeId ? g.getNode(t.pendingStartNodeId) : null;
  if (n) {
    t.pendingStartPos = { x: n.x, y: n.y };
    t.previewEndPos = { x: n.x, y: n.y };
  } else {
    t.pendingStartNodeId = null;
    t.pendingStartPos = null;
    t.previewEndPos = null;
    t.lastDir = null;
  }
}

function snapshotHiddenTool(t) {
  return {
    pendingStartNodeId: t?.pendingStartNodeId ?? null,
    angleLocked: (typeof t?.angleLocked === "boolean") ? t.angleLocked : true,
    lastDir: t?.lastDir ? { x: t.lastDir.x, y: t.lastDir.y } : null,
  };
}

function restoreHiddenTool(t, g, snap) {
  if (!t) return;
  t.pendingStartNodeId = snap?.pendingStartNodeId ?? null;
  if (typeof snap?.angleLocked === "boolean") t.angleLocked = snap.angleLocked;
  t.lastDir = snap?.lastDir ? { x: snap.lastDir.x, y: snap.lastDir.y } : null;

  const n = t.pendingStartNodeId ? g.getNode(t.pendingStartNodeId) : null;
  if (n) {
    t.pendingStartPos = { x: n.x, y: n.y };
    t.previewEndPos = { x: n.x, y: n.y };
  } else {
    t.pendingStartNodeId = null;
    t.pendingStartPos = null;
    t.previewEndPos = null;
    t.lastDir = null;
  }
}

function snapshotDimTool(t) {
  return {
    stage: t?.stage ?? 0,
    a: t?.a ? { x: t.a.x, y: t.a.y } : null,
    b: t?.b ? { x: t.b.x, y: t.b.y } : null,
    cursor: t?.cursor ? { x: t.cursor.x, y: t.cursor.y } : null,
    _did: t?._did ?? 1,
  };
}

function restoreDimTool(t, snap) {
  if (!t) return;
  t.cancel?.();
  t.stage = snap?.stage ?? 0;
  t.a = snap?.a ? { x: snap.a.x, y: snap.a.y } : null;
  t.b = snap?.b ? { x: snap.b.x, y: snap.b.y } : null;
  t.cursor = snap?.cursor ? { x: snap.cursor.x, y: snap.cursor.y } : null;
  if (typeof snap?._did === "number") t._did = snap._did;
}

function snapshotDimensions(dims) {
  const out = [];
  for (const d of dims) {
    out.push({
      id: d.id,
      a: { x: d.a.x, y: d.a.y },
      b: { x: d.b.x, y: d.b.y },
      offsetMm: d.offsetMm,
      sideSign: d.sideSign,
    });
  }
  return out;
}

function restoreDimensions(dims, snap) {
  dims.length = 0;
  for (const d of snap ?? []) dims.push({
    id: d.id,
    a: { x: d.a.x, y: d.a.y },
    b: { x: d.b.x, y: d.b.y },
    offsetMm: d.offsetMm,
    sideSign: d.sideSign,
  });
}

function snapshotModel2d(model) {
  return {
    lines: (model?.lines || []).map((l) => ({ ax: l.ax, ay: l.ay, bx: l.bx, by: l.by })),
    outline: (model?.outline || []).map((p) => ({ x: p.x, y: p.y })),
    offsetXmm: (typeof model?.offsetXmm === "number" && isFinite(model.offsetXmm)) ? model.offsetXmm : 0,
    offsetYmm: (typeof model?.offsetYmm === "number" && isFinite(model.offsetYmm)) ? model.offsetYmm : 0,
    rotationRad: (typeof model?.rotationRad === "number" && isFinite(model.rotationRad)) ? model.rotationRad : 0,
  };
}

function restoreModel2d(model, snap) {
  if (!model) return;
  model.lines = (snap?.lines || []).map((l) => ({ ax: l.ax, ay: l.ay, bx: l.bx, by: l.by }));
  model.outline = (snap?.outline || []).map((p) => ({ x: p.x, y: p.y }));
  model.offsetXmm = (typeof snap?.offsetXmm === "number" && isFinite(snap.offsetXmm)) ? snap.offsetXmm : 0;
  model.offsetYmm = (typeof snap?.offsetYmm === "number" && isFinite(snap.offsetYmm)) ? snap.offsetYmm : 0;
  model.rotationRad = (typeof snap?.rotationRad === "number" && isFinite(snap.rotationRad)) ? snap.rotationRad : 0;
}

function _stateSignature(snap) {
  // Exclude selection/hover so canceled prompts or pure selection changes don't create undo steps.
  return JSON.stringify({
    graph: snap.graphSnap,
    hiddenGraph: snap.hiddenGraphSnap,
    tool: snap.toolSnap,
    hiddenTool: snap.hiddenToolSnap,
    dimTool: snap.dimToolSnap,
    dimensions: snap.dimensionsSnap,
    model2d: snap.model2dSnap,
  });
}

class UndoManager {
  constructor({ graph, tool, hiddenGraph, hiddenTool, dimTool, dimensions, model2d, onModel2dRestore, getSelection, setSelection, maxDepth = 200 }) {
    this.graph = graph;
    this.tool = tool;
    this.hiddenGraph = hiddenGraph;
    this.hiddenTool = hiddenTool;
    this.dimTool = dimTool;
    this.dimensions = dimensions;
    this.model2d = model2d;
    this.onModel2dRestore = onModel2dRestore;
    this.getSelection = getSelection;
    this.setSelection = setSelection;
    this.maxDepth = maxDepth;
    this.stack = [];
    this.redoStack = [];
  }

  capture() {
    const graphSnap = snapshotGraph(this.graph);
    const toolSnap = snapshotTool(this.tool);
    const sel = this.getSelection();
    const hiddenGraphSnap = snapshotGraph(this.hiddenGraph);
    const hiddenToolSnap = snapshotHiddenTool(this.hiddenTool);
    const dimToolSnap = snapshotDimTool(this.dimTool);
    const dimensionsSnap = snapshotDimensions(this.dimensions);
    const model2dSnap = snapshotModel2d(this.model2d);
    return {
      graphSnap,
      hiddenGraphSnap,
      toolSnap,
      hiddenToolSnap,
      dimToolSnap,
      dimensionsSnap,
      model2dSnap,
      selectedWallId: sel.selectedWallId,
      hoverWallId: sel.hoverWallId,
      selectedHiddenId: sel.selectedHiddenId,
      hoverHiddenId: sel.hoverHiddenId,
      selectedDimId: sel.selectedDimId,
      hoverDimId: sel.hoverDimId,
      selectedWallIds: Array.isArray(sel.selectedWallIds) ? sel.selectedWallIds.slice() : [],
      selectedHiddenIds: Array.isArray(sel.selectedHiddenIds) ? sel.selectedHiddenIds.slice() : [],
      selectedDimIds: Array.isArray(sel.selectedDimIds) ? sel.selectedDimIds.slice() : [],
      selectedModelOutline: !!sel.selectedModelOutline,
      hoverModelOutline: !!sel.hoverModelOutline,
    };
  }

  runAction(fn) {
    const before = this.capture();
    const beforeSig = _stateSignature(before);

    fn();

    const after = this.capture();
    const afterSig = _stateSignature(after);
    if (afterSig === beforeSig) return;

    this.stack.push(before);
    if (this.stack.length > this.maxDepth) this.stack.shift();
    this.redoStack.length = 0;
  }

  undo() {
    const snap = this.stack.pop();
    if (!snap) return;

    const cur = this.capture();
    this.redoStack.push(cur);
    if (this.redoStack.length > this.maxDepth) this.redoStack.shift();

    restoreGraph(this.graph, snap.graphSnap);
    restoreGraph(this.hiddenGraph, snap.hiddenGraphSnap);
    restoreTool(this.tool, this.graph, snap.toolSnap);
    restoreHiddenTool(this.hiddenTool, this.hiddenGraph, snap.hiddenToolSnap);
    restoreDimTool(this.dimTool, snap.dimToolSnap);
    restoreDimensions(this.dimensions, snap.dimensionsSnap);
    restoreModel2d(this.model2d, snap.model2dSnap);
    this.onModel2dRestore?.();

    // Validate selection/hover IDs against restored walls
    let nextSelected = snap.selectedWallId ?? null;
    let nextHover = snap.hoverWallId ?? null;
    if (nextSelected && !this.graph.walls.has(nextSelected)) nextSelected = null;
    if (nextHover && !this.graph.walls.has(nextHover)) nextHover = null;

    let nextSelectedHidden = snap.selectedHiddenId ?? null;
    let nextHoverHidden = snap.hoverHiddenId ?? null;
    if (nextSelectedHidden && !this.hiddenGraph.walls.has(nextSelectedHidden)) nextSelectedHidden = null;
    if (nextHoverHidden && !this.hiddenGraph.walls.has(nextHoverHidden)) nextHoverHidden = null;

    const hasDim = (id) => !!(id && this.dimensions.some((d) => d && d.id === id));
    let nextSelectedDim = snap.selectedDimId ?? null;
    let nextHoverDim = snap.hoverDimId ?? null;
    if (nextSelectedDim && !hasDim(nextSelectedDim)) nextSelectedDim = null;
    if (nextHoverDim && !hasDim(nextHoverDim)) nextHoverDim = null;
    const nextSelectedWalls = Array.isArray(snap.selectedWallIds)
      ? snap.selectedWallIds.filter((id) => this.graph.walls.has(id))
      : [];
    const nextSelectedHiddens = Array.isArray(snap.selectedHiddenIds)
      ? snap.selectedHiddenIds.filter((id) => this.hiddenGraph.walls.has(id))
      : [];
    const nextSelectedDims = Array.isArray(snap.selectedDimIds)
      ? snap.selectedDimIds.filter((id) => hasDim(id))
      : [];

    this.setSelection({
      selectedWallId: nextSelected,
      hoverWallId: nextHover,
      selectedHiddenId: nextSelectedHidden,
      hoverHiddenId: nextHoverHidden,
      selectedDimId: nextSelectedDim,
      hoverDimId: nextHoverDim,
      selectedWallIds: nextSelectedWalls,
      selectedHiddenIds: nextSelectedHiddens,
      selectedDimIds: nextSelectedDims,
      selectedModelOutline: !!snap.selectedModelOutline,
      hoverModelOutline: !!snap.hoverModelOutline,
    });
  }

  redo() {
    const snap = this.redoStack.pop();
    if (!snap) return;

    const cur = this.capture();
    this.stack.push(cur);
    if (this.stack.length > this.maxDepth) this.stack.shift();

    restoreGraph(this.graph, snap.graphSnap);
    restoreGraph(this.hiddenGraph, snap.hiddenGraphSnap);
    restoreTool(this.tool, this.graph, snap.toolSnap);
    restoreHiddenTool(this.hiddenTool, this.hiddenGraph, snap.hiddenToolSnap);
    restoreDimTool(this.dimTool, snap.dimToolSnap);
    restoreDimensions(this.dimensions, snap.dimensionsSnap);
    restoreModel2d(this.model2d, snap.model2dSnap);
    this.onModel2dRestore?.();

    let nextSelected = snap.selectedWallId ?? null;
    let nextHover = snap.hoverWallId ?? null;
    if (nextSelected && !this.graph.walls.has(nextSelected)) nextSelected = null;
    if (nextHover && !this.graph.walls.has(nextHover)) nextHover = null;

    let nextSelectedHidden = snap.selectedHiddenId ?? null;
    let nextHoverHidden = snap.hoverHiddenId ?? null;
    if (nextSelectedHidden && !this.hiddenGraph.walls.has(nextSelectedHidden)) nextSelectedHidden = null;
    if (nextHoverHidden && !this.hiddenGraph.walls.has(nextHoverHidden)) nextHoverHidden = null;

    const hasDim = (id) => !!(id && this.dimensions.some((d) => d && d.id === id));
    let nextSelectedDim = snap.selectedDimId ?? null;
    let nextHoverDim = snap.hoverDimId ?? null;
    if (nextSelectedDim && !hasDim(nextSelectedDim)) nextSelectedDim = null;
    if (nextHoverDim && !hasDim(nextHoverDim)) nextHoverDim = null;
    const nextSelectedWalls = Array.isArray(snap.selectedWallIds)
      ? snap.selectedWallIds.filter((id) => this.graph.walls.has(id))
      : [];
    const nextSelectedHiddens = Array.isArray(snap.selectedHiddenIds)
      ? snap.selectedHiddenIds.filter((id) => this.hiddenGraph.walls.has(id))
      : [];
    const nextSelectedDims = Array.isArray(snap.selectedDimIds)
      ? snap.selectedDimIds.filter((id) => hasDim(id))
      : [];

    this.setSelection({
      selectedWallId: nextSelected,
      hoverWallId: nextHover,
      selectedHiddenId: nextSelectedHidden,
      hoverHiddenId: nextHoverHidden,
      selectedDimId: nextSelectedDim,
      hoverDimId: nextHoverDim,
      selectedWallIds: nextSelectedWalls,
      selectedHiddenIds: nextSelectedHiddens,
      selectedDimIds: nextSelectedDims,
      selectedModelOutline: !!snap.selectedModelOutline,
      hoverModelOutline: !!snap.hoverModelOutline,
    });
  }
}

// hidden guide (optional)
const guides = [];

// 3D model -> 2D projection (plan edges) overlay. Stored in world millimeters.
// These are visual guides only; they do not affect snapping/selection yet.
const model2d = {
  lines: [], // [{ax,ay,bx,by}]
  outline: [], // [{x,y}] in world mm, closed polyline is implied
  color: "#7a8792",
  outlineColor: "#7A4A2B", // brown (default as requested)
  outlineHoverColor: "#9B6B3A",
  outlineSelectedColor: "#762D47", // same as fixed right rail base
  lineWidthPx: 1,
  outlineWidthPx: 2,
  dash: [5, 7],
  alpha: 0.55,
  offsetXmm: 0,
  offsetYmm: 0,
  rotationRad: 0,
};
let hoverModelOutline = false;
let selectedModelOutline = false;
let uiCursorMode = null; // null | "wall" | "hidden" | "dim" | "beam" | "clicker"
const cursorImgs = new Map();
const wallHandleImgs = new Map();

function _loadImgWithFallback(map, key, urls) {
  if (map.has(key)) return map.get(key);
  const img = new Image();
  img.decoding = "async";
  const tries = (Array.isArray(urls) ? urls : [urls]).filter(Boolean);
  let idx = 0;
  img.onerror = () => {
    idx += 1;
    if (idx < tries.length) img.src = tries[idx];
  };
  if (tries.length) img.src = tries[0];
  map.set(key, img);
  return img;
}

function loadCursorImg(key, urls) {
  return _loadImgWithFallback(cursorImgs, key, urls);
}

function loadWallHandleImg(key, urls) {
  return _loadImgWithFallback(wallHandleImgs, key, urls);
}

function resolveIconUrls(name) {
  const out = [];
  try {
    out.push(new URL(`../icons/${name}`, import.meta.url).href);
  } catch (_) {
    // no-op
  }
  out.push(`/icons/${name}`);
  out.push(`./icons/${name}`);
  out.push(`icons/${name}`);
  return out;
}

function initCursorImagesOnce() {
  loadCursorImg("cursor", resolveIconUrls("cursor.png"));
  loadCursorImg("clicker", resolveIconUrls("clicker.png"));
  loadCursorImg("wall", resolveIconUrls("wall_drawing.png"));
  loadCursorImg("hidden", resolveIconUrls("hidden_wall_drawing.png"));
  loadCursorImg("dim", resolveIconUrls("dimention_drawimg.png"));
  loadCursorImg("beam", resolveIconUrls("beam_pointer.png"));
  loadWallHandleImg("free", resolveIconUrls("arrow.png"));
  loadWallHandleImg("len", resolveIconUrls("double-arrow.png"));
  loadWallHandleImg("mid", resolveIconUrls("fix-arrow.png"));
  loadWallHandleImg("joint", resolveIconUrls("joint_point.png"));
}

function setUiCursorMode(mode) {
  uiCursorMode = mode || null;
  updateCanvasCursor();
}

function cross2(ax, ay, bx, by) { return ax * by - ay * bx; }

// Monotonic chain convex hull (returns array of points without repeating first at end).
function convexHull(points) {
  const pts = points
    .filter((p) => p && isFinite(p.x) && isFinite(p.y))
    .map((p) => ({ x: +p.x, y: +p.y }));
  if (pts.length < 3) return pts;

  pts.sort((a, b) => (a.x - b.x) || (a.y - b.y));
  const uniq = [];
  for (const p of pts) {
    const last = uniq[uniq.length - 1];
    if (!last || last.x !== p.x || last.y !== p.y) uniq.push(p);
  }
  if (uniq.length < 3) return uniq;

  const lower = [];
  for (const p of uniq) {
    while (lower.length >= 2) {
      const a = lower[lower.length - 2];
      const b = lower[lower.length - 1];
      if (cross2(b.x - a.x, b.y - a.y, p.x - b.x, p.y - b.y) <= 0) lower.pop();
      else break;
    }
    lower.push(p);
  }
  const upper = [];
  for (let i = uniq.length - 1; i >= 0; i--) {
    const p = uniq[i];
    while (upper.length >= 2) {
      const a = upper[upper.length - 2];
      const b = upper[upper.length - 1];
      if (cross2(b.x - a.x, b.y - a.y, p.x - b.x, p.y - b.y) <= 0) upper.pop();
      else break;
    }
    upper.push(p);
  }
  upper.pop();
  lower.pop();
  return lower.concat(upper);
}

function recomputeModel2dOutline() {
  const pts = [];
  for (const l of model2d.lines) {
    pts.push({ x: l.ax, y: l.ay }, { x: l.bx, y: l.by });
  }
  model2d.outline = convexHull(pts);
}

function _applyModel2dLines(lines, opts = null) {
  if (!Array.isArray(lines)) return;
  stopModelDrag(true);
  model2d.lines = lines
    .filter((l) => l && isFinite(l.ax) && isFinite(l.ay) && isFinite(l.bx) && isFinite(l.by))
    .map((l) => ({ ax: +l.ax, ay: +l.ay, bx: +l.bx, by: +l.by }));
  recomputeModel2dOutline();
  model2d.offsetXmm = 0;
  model2d.offsetYmm = 0;
  model2d.rotationRad = 0;
  hoverModelOutline = false;
  selectedModelOutline = false;
  if (opts && typeof opts === "object") {
    if (typeof opts.color === "string") model2d.color = opts.color;
    if (typeof opts.lineWidthPx === "number" && isFinite(opts.lineWidthPx) && opts.lineWidthPx > 0) model2d.lineWidthPx = opts.lineWidthPx;
    if (Array.isArray(opts.dash) && opts.dash.length >= 2) model2d.dash = opts.dash.slice(0, 2).map((n) => +n);
    if (typeof opts.alpha === "number" && isFinite(opts.alpha)) model2d.alpha = Math.max(0, Math.min(1, opts.alpha));
    if (typeof opts.outlineColor === "string") model2d.outlineColor = opts.outlineColor;
  }
  emitModel2dTransform();
}

function setModel2dLines(lines, opts = null, recordUndo = true) {
  if (!Array.isArray(lines)) return;
  if (!recordUndo) {
    _applyModel2dLines(lines, opts);
    return;
  }
  undo.runAction(() => {
    _applyModel2dLines(lines, opts);
  });
}

function _clearModel2dLines() {
  stopModelDrag(true);
  model2d.lines.length = 0;
  model2d.outline.length = 0;
  model2d.offsetXmm = 0;
  model2d.offsetYmm = 0;
  model2d.rotationRad = 0;
  hoverModelOutline = false;
  selectedModelOutline = false;
  emitModel2dTransform();
}

function clearModel2dLines(recordUndo = true) {
  if (!recordUndo) {
    _clearModel2dLines();
    return;
  }
  undo.runAction(() => {
    _clearModel2dLines();
  });
}

/* =============================
   Node endpoint map
============================= */
function buildNodeEndpointMap(graph) {
  const map = new Map();
  for (const e of graph.walls.values()) {
    if (!map.has(e.a)) map.set(e.a, []);
    if (!map.has(e.b)) map.set(e.b, []);
    map.get(e.a).push({ edge: e, at: "a" });
    map.get(e.b).push({ edge: e, at: "b" });
  }
  return map;
}

/* =============================
   RuleEngine Bridge (Gamma / Miter)
============================= */
function makeRuleWallFromEdge(graph, edge, sharedNodeId, side /* "left"|"right" */) {
  const A = graph.getNode(edge.a);
  const B = graph.getNode(edge.b);

  const startIsShared = (edge.a === sharedNodeId);
  const nShared = startIsShared ? A : B;
  const nOther  = startIsShared ? B : A;

  const alphaStart = new RuleNode(nShared.id, { x: nShared.x, y: nShared.y });
  const alphaEnd   = new RuleNode(nOther.id,  { x: nOther.x,  y: nOther.y  });

  return new RuleWall({
    id: edge.id,
    alphaStartNode: alphaStart,
    alphaEndNode: alphaEnd,
    thickness: edge.thickness,
    side,
  });
}

function computeGammaAtJoint(graph, nodeId, edge1, edge2, side1, side2) {
  const w1 = makeRuleWallFromEdge(graph, edge1, nodeId, side1);
  const w2 = makeRuleWallFromEdge(graph, edge2, nodeId, side2);
  return computeGammaForJoint(w1, w2, { miterLimit: state.miterLimit });
}

/* =============================
   Grid
============================= */
function drawGrid() {
  const W = viewportW;
  const H = viewportH;

  ctx.fillStyle = state.bgColor;
  ctx.fillRect(0, 0, W, H);

  const meterMM = 1000;
  const minorStep = meterMM / state.meterDivisions;

  const a = screenToWorld(0, H);
  const b = screenToWorld(W, 0);

  const minX = Math.floor(a.x / minorStep) * minorStep;
  const maxX = Math.ceil(b.x / minorStep) * minorStep;
  const minY = Math.floor(a.y / minorStep) * minorStep;
  const maxY = Math.ceil(b.y / minorStep) * minorStep;

  for (let x=minX; x<=maxX; x+=minorStep) {
    const idx = Math.round(x / minorStep);
    const isMajor = idx % state.majorEvery === 0;

    const p = worldToScreen(x, 0);
    ctx.beginPath();
    ctx.strokeStyle = isMajor ? state.majorColor : state.minorColor;
    ctx.lineWidth = isMajor ? 1.2 : 0.6;
    ctx.moveTo(p.x, 0);
    ctx.lineTo(p.x, H);
    ctx.stroke();
  }

  for (let y=minY; y<=maxY; y+=minorStep) {
    const idx = Math.round(y / minorStep);
    const isMajor = idx % state.majorEvery === 0;

    const p = worldToScreen(0, y);
    ctx.beginPath();
    ctx.strokeStyle = isMajor ? state.majorColor : state.minorColor;
    ctx.lineWidth = isMajor ? 1.2 : 0.6;
    ctx.moveTo(0, p.y);
    ctx.lineTo(W, p.y);
    ctx.stroke();
  }

  const origin = worldToScreen(0, 0);

  ctx.beginPath();
  ctx.strokeStyle = state.axisXColor;
  ctx.lineWidth = 2;
  ctx.moveTo(0, origin.y);
  ctx.lineTo(W, origin.y);
  ctx.stroke();

  ctx.beginPath();
  ctx.strokeStyle = state.axisYColor;
  ctx.lineWidth = 2;
  ctx.moveTo(origin.x, 0);
  ctx.lineTo(origin.x, H);
  ctx.stroke();

  ctx.beginPath();
  ctx.fillStyle = "#000";
  ctx.arc(origin.x, origin.y, 4, 0, Math.PI*2);
  ctx.fill();
}

function getBoundsCenterWorld(points) {
  if (!Array.isArray(points) || points.length === 0) return null;
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const p of points) {
    if (!p || !isFinite(p.x) || !isFinite(p.y)) continue;
    if (p.x < minX) minX = p.x;
    if (p.y < minY) minY = p.y;
    if (p.x > maxX) maxX = p.x;
    if (p.y > maxY) maxY = p.y;
  }
  if (!isFinite(minX) || !isFinite(minY) || !isFinite(maxX) || !isFinite(maxY)) return null;
  return { x: (minX + maxX) * 0.5, y: (minY + maxY) * 0.5 };
}

function getSelectedObjectTargetInfo() {
  const wallIds = [];
  if (selectedWallId) wallIds.push(selectedWallId);
  for (const id of selectedWallIds) wallIds.push(id);
  if (wallIds.length) {
    const uniq = [];
    const seen = new Set();
    const pts = [];
    for (const id of wallIds) {
      if (seen.has(id)) continue;
      seen.add(id);
      const w = graph.getWall(id);
      if (!w) continue;
      uniq.push(id);
      const a = graph.getNode(w.a);
      const b = graph.getNode(w.b);
      if (a) pts.push({ x: a.x, y: a.y });
      if (b) pts.push({ x: b.x, y: b.y });
    }
    const center = getBoundsCenterWorld(pts);
    if (center && uniq.length) return { type: "wall", center, ids: uniq };
  }

  const hiddenIds = [];
  if (selectedHiddenId) hiddenIds.push(selectedHiddenId);
  for (const id of selectedHiddenIds) hiddenIds.push(id);
  if (hiddenIds.length) {
    const uniq = [];
    const seen = new Set();
    const pts = [];
    for (const id of hiddenIds) {
      if (seen.has(id)) continue;
      seen.add(id);
      const w = hiddenGraph.getWall(id);
      if (!w) continue;
      uniq.push(id);
      const a = hiddenGraph.getNode(w.a);
      const b = hiddenGraph.getNode(w.b);
      if (a) pts.push({ x: a.x, y: a.y });
      if (b) pts.push({ x: b.x, y: b.y });
    }
    const center = getBoundsCenterWorld(pts);
    if (center && uniq.length) return { type: "hidden", center, ids: uniq };
  }

  const dimIds = [];
  if (selectedDimId) dimIds.push(selectedDimId);
  for (const id of selectedDimIds) dimIds.push(id);
  if (dimIds.length) {
    const uniq = [];
    const seen = new Set();
    const pts = [];
    for (const id of dimIds) {
      if (seen.has(id)) continue;
      seen.add(id);
      const d = dimensions.find((x) => x && x.id === id);
      if (!d) continue;
      uniq.push(id);
      if (d.a) pts.push({ x: d.a.x, y: d.a.y });
      if (d.b) pts.push({ x: d.b.x, y: d.b.y });
    }
    const center = getBoundsCenterWorld(pts);
    if (center && uniq.length) return { type: "dim", center, ids: uniq };
  }

  if (selectedModelOutline && Array.isArray(model2d.outline) && model2d.outline.length >= 1) {
    const center = getBoundsCenterWorld(model2d.outline);
    if (center) return { type: "model", center, ids: [] };
  }

  return null;
}

function getObjectAxesGeometryScreen() {
  if (!state.showObjectAxes) return null;
  const target = getSelectedObjectTargetInfo();
  if (!target?.center) return null;

  const lenPx = 72;
  const lenWorld = lenPx / Math.max(0.001, state.zoom);
  const originWorld = target.center;
  const xEndWorld = { x: originWorld.x + lenWorld, y: originWorld.y };
  const yEndWorld = { x: originWorld.x, y: originWorld.y + lenWorld };

  return {
    target,
    originWorld,
    originScreen: worldToScreen(originWorld.x, originWorld.y),
    xEndScreen: worldToScreen(xEndWorld.x, xEndWorld.y),
    yEndScreen: worldToScreen(yEndWorld.x, yEndWorld.y),
  };
}

function hitTestObjectAxesScreen(x, y) {
  const g = getObjectAxesGeometryScreen();
  if (!g) return null;
  const tolPx = 11;
  const dx = pointToSegmentDistancePx(x, y, g.originScreen.x, g.originScreen.y, g.xEndScreen.x, g.xEndScreen.y);
  const dy = pointToSegmentDistancePx(x, y, g.originScreen.x, g.originScreen.y, g.yEndScreen.x, g.yEndScreen.y);
  const hitX = dx <= tolPx;
  const hitY = dy <= tolPx;
  if (hitX && hitY) return { axis: "x", geometry: g };
  if (hitX) return { axis: "x", geometry: g };
  if (hitY) return { axis: "y", geometry: g };
  return null;
}

function beginAxisDrag(axis, offsetX, offsetY) {
  const target = getSelectedObjectTargetInfo();
  if (!target) return false;
  axisDrag.active = true;
  axisDrag.axis = (axis === "y") ? "y" : "x";
  axisDrag.targetType = target.type;
  axisDrag.startMouseWorld = screenToWorld(offsetX, offsetY);
  axisDrag.startGraphSnap = snapshotGraph(graph);
  axisDrag.startHiddenGraphSnap = snapshotGraph(hiddenGraph);
  axisDrag.startDimensionsSnap = snapshotDimensions(dimensions);
  axisDrag.startModelSnap = snapshotModel2d(model2d);
  axisDrag.moved = false;
  hoverObjectAxis = axisDrag.axis;
  return true;
}

function stopAxisDrag() {
  axisDrag.active = false;
  axisDrag.axis = null;
  axisDrag.targetType = null;
  axisDrag.startMouseWorld = null;
  axisDrag.startGraphSnap = null;
  axisDrag.startHiddenGraphSnap = null;
  axisDrag.startDimensionsSnap = null;
  axisDrag.startModelSnap = null;
  axisDrag.moved = false;
}

function applyAxisDrag(targetWorld) {
  if (!axisDrag.active || !axisDrag.startMouseWorld) return;
  const start = axisDrag.startMouseWorld;
  const deltaRaw = { x: targetWorld.x - start.x, y: targetWorld.y - start.y };
  const axisUnit = axisDrag.axis === "y" ? { x: 0, y: 1 } : { x: 1, y: 0 };
  const t = dot(deltaRaw.x, deltaRaw.y, axisUnit.x, axisUnit.y);
  const delta = { x: axisUnit.x * t, y: axisUnit.y * t };

  restoreGraph(graph, axisDrag.startGraphSnap);
  restoreGraph(hiddenGraph, axisDrag.startHiddenGraphSnap);
  restoreDimensions(dimensions, axisDrag.startDimensionsSnap);
  restoreModel2d(model2d, axisDrag.startModelSnap);

  if (axisDrag.targetType === "wall") {
    const info = getSelectedObjectTargetInfo();
    const ids = info?.type === "wall" ? info.ids : [];
    const nodeIds = new Set();
    for (const id of ids) {
      const w = graph.getWall(id);
      if (!w) continue;
      nodeIds.add(w.a);
      nodeIds.add(w.b);
    }
    for (const nid of nodeIds) {
      const n = graph.getNode(nid);
      if (!n) continue;
      n.x += delta.x;
      n.y += delta.y;
    }
    graph.mergeCloseNodes(1);
    graph.deleteTinyEdges(1);
  } else if (axisDrag.targetType === "hidden") {
    const info = getSelectedObjectTargetInfo();
    const ids = info?.type === "hidden" ? info.ids : [];
    const nodeIds = new Set();
    for (const id of ids) {
      const w = hiddenGraph.getWall(id);
      if (!w) continue;
      nodeIds.add(w.a);
      nodeIds.add(w.b);
    }
    for (const nid of nodeIds) {
      const n = hiddenGraph.getNode(nid);
      if (!n) continue;
      n.x += delta.x;
      n.y += delta.y;
    }
    hiddenGraph.mergeCloseNodes(1);
    hiddenGraph.deleteTinyEdges(1);
  } else if (axisDrag.targetType === "dim") {
    const info = getSelectedObjectTargetInfo();
    const ids = new Set(info?.type === "dim" ? info.ids : []);
    for (const d of dimensions) {
      if (!d || !ids.has(d.id)) continue;
      if (d.a) { d.a.x += delta.x; d.a.y += delta.y; }
      if (d.b) { d.b.x += delta.x; d.b.y += delta.y; }
    }
  } else if (axisDrag.targetType === "model") {
    model2d.lines = model2d.lines.map((l) => ({
      ax: l.ax + delta.x, ay: l.ay + delta.y, bx: l.bx + delta.x, by: l.by + delta.y,
    }));
    model2d.outline = model2d.outline.map((pt) => ({ x: pt.x + delta.x, y: pt.y + delta.y }));
    model2d.offsetXmm = (model2d.offsetXmm || 0) + delta.x;
    model2d.offsetYmm = (model2d.offsetYmm || 0) + delta.y;
    emitModel2dTransform();
  }

  if (Math.hypot(delta.x, delta.y) > 0.5) axisDrag.moved = true;
}

function drawSelectedObjectAxes() {
  if (!state.showObjectAxes) return;
  const g = getObjectAxesGeometryScreen();
  if (!g) return;

  const drawAxis = (from, to, color, label, active) => {
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const dl = Math.hypot(dx, dy) || 1;
    const ux = dx / dl;
    const uy = dy / dl;
    const px = -uy;
    const py = ux;

    ctx.save();
    ctx.strokeStyle = color;
    ctx.fillStyle = color;
    ctx.globalAlpha = active ? 1 : 0.88;
    ctx.lineWidth = active ? 4 : 3;

    ctx.beginPath();
    ctx.moveTo(from.x, from.y);
    ctx.lineTo(to.x, to.y);
    ctx.stroke();

    const ah = active ? 11 : 9;
    const aw = active ? 6 : 5;
    ctx.beginPath();
    ctx.moveTo(to.x, to.y);
    ctx.lineTo(to.x - ux * ah + px * aw, to.y - uy * ah + py * aw);
    ctx.lineTo(to.x - ux * ah - px * aw, to.y - uy * ah - py * aw);
    ctx.closePath();
    ctx.fill();

    ctx.font = `bold ${active ? 14 : 13}px ${state.fontFamily || "Tahoma"}`;
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(label, to.x + ux * 12 + px * 2, to.y + uy * 12 + py * 2);
    ctx.restore();
  };

  const xActive = hoverObjectAxis === "x" || (axisDrag.active && axisDrag.axis === "x");
  const yActive = hoverObjectAxis === "y" || (axisDrag.active && axisDrag.axis === "y");

  drawAxis(g.originScreen, g.xEndScreen, state.axisXColor, "X", xActive);
  drawAxis(g.originScreen, g.yEndScreen, state.axisYColor, "Y", yActive);

  ctx.save();
  ctx.fillStyle = "#111";
  ctx.beginPath();
  ctx.arc(g.originScreen.x, g.originScreen.y, 4, 0, Math.PI * 2);
  ctx.fill();
  ctx.restore();
}

/* =============================
   Hit targets
============================= */
const hitTargets = []; // rebuilt each frame
const wallUiIcons = []; // draw after all layers
let hoverUi = null; // { type:"dim_side"|"off_side", wallId }
let iconPulse = null; // { type, wallId, untilMs }
function addRectTarget(type, wallId, rect, payload = {}) {
  hitTargets.push({ type, wallId, rect, payload });
}
function pointInRect(x, y, r) {
  return !!r && x >= r.x && x <= r.x + r.w && y >= r.y && y <= r.y + r.h;
}
function hitTest(x, y) {
  let firstOffSideHit = null;
  let firstDimSideHit = null;
  let firstWallHandleHit = null;
  let firstNonUiHit = null;
  for (let i = hitTargets.length - 1; i >= 0; i--) {
    const t = hitTargets[i];
    const r = t.rect;
    if (!pointInRect(x, y, r)) continue;

    // Deterministic overlap priority: off_side > dim_side > all others.
    if (t.type === "off_side") {
      if (!firstOffSideHit) firstOffSideHit = t;
      continue;
    }
    if (t.type === "dim_side") {
      if (!firstDimSideHit) firstDimSideHit = t;
      continue;
    }
    if (
      t.type === "wall_len_a" || t.type === "wall_len_b" ||
      t.type === "wall_free_a" || t.type === "wall_free_b" ||
      t.type === "wall_mid_move" ||
      t.type === "wall_chain_a" || t.type === "wall_chain_b"
    ) {
      if (!firstWallHandleHit) firstWallHandleHit = t;
      continue;
    }
    if (!firstNonUiHit) firstNonUiHit = t;
  }
  if (firstOffSideHit) return firstOffSideHit;
  if (firstDimSideHit) return firstDimSideHit;
  if (firstWallHandleHit) return firstWallHandleHit;
  return firstNonUiHit;
}
function hitTestSelectedWallUiFallback(x, y) {
  if (!selectedWallId) return null;
  const edge = graph.getWall(selectedWallId);
  if (!edge) return null;

  const nodeMap = buildNodeEndpointMap(graph);
  const jointGammaMap = buildJointGammaMap(nodeMap);
  const c = computeTrimmedWallCorners(edge, jointGammaMap);
  if (c) {
    const dimLayout = computeDimensionLayout(
      c.ax, c.ay, c.bx, c.by,
      edge.dimSide || "auto",
      { left: c.leftLen, right: c.rightLen },
      {
        anchorsBySide: c.anchorsBySide,
        offsetMm: (typeof edge.dimOffsetMm === "number" && isFinite(edge.dimOffsetMm)) ? Math.max(0, edge.dimOffsetMm) : state.dimOffsetMm,
        wallEdge: edge,
      }
    );
    if (dimLayout && pointInRect(x, y, dimLayout.arrowRect)) {
      return { type: "dim_side", wallId: edge.id, rect: dimLayout.arrowRect };
    }
  }

  if (state.offsetWallEnabled) {
    const BTN = 18;
    const m = computeOffsetMidpoint(edge);
    if (m) {
      const p = worldToScreen(m.x, m.y);
      const rect = { x: p.x - BTN / 2, y: p.y - BTN / 2, w: BTN, h: BTN };
      if (pointInRect(x, y, rect)) {
        return { type: "off_side", wallId: edge.id, rect };
      }
    }
  }

  return null;
}

/* =============================
   Rounded buttons + arrows
============================= */
function roundedRectPath(x, y, w, h, r) {
  const rr = Math.max(0, Math.min(r, Math.min(w, h) / 2));
  ctx.beginPath();
  ctx.moveTo(x + rr, y);
  ctx.arcTo(x + w, y, x + w, y + h, rr);
  ctx.arcTo(x + w, y + h, x, y + h, rr);
  ctx.arcTo(x, y + h, x, y, rr);
  ctx.arcTo(x, y, x + w, y, rr);
  ctx.closePath();
}

function drawMiniButton(rect, label, disabled = false) {
  ctx.save();
  // Enabled buttons should be dark gray (not black). Disabled are lighter.
  if (disabled) ctx.globalAlpha = 0.35;
  ctx.setLineDash([]);
  ctx.lineWidth = 1;
  ctx.strokeStyle = disabled ? "#666666" : "#6b6b6b";
  ctx.fillStyle = disabled ? "#f5f5f5" : "#d9d9d9";

  roundedRectPath(rect.x, rect.y, rect.w, rect.h, 4);
  ctx.fill();
  ctx.stroke();

  ctx.fillStyle = disabled ? "#666666" : "#4a4a4a";
  ctx.font = `12px ${state.fontFamily}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.direction = "ltr";
  ctx.fillText(label, rect.x + rect.w/2, rect.y + rect.h/2 + 0.5);
  ctx.restore();
}

function drawArrowButton(rect, rotRad, disabled = false, opts = null) {
  const accent = opts?.accentColor || state.dimColor;
  const hovered = !disabled && !!opts?.hovered;
  const active = !disabled && !!opts?.active;
  const hl = active ? 2 : hovered ? 1 : 0; // 0:none, 1:hover, 2:click pulse

  ctx.save();
  // Enabled buttons should be dark gray (not black). Disabled are lighter.
  if (disabled) ctx.globalAlpha = 0.35;
  ctx.setLineDash([]);
  ctx.lineWidth = 1;
  ctx.strokeStyle = disabled ? "#666666" : "#6b6b6b";
  ctx.fillStyle = disabled ? "#f5f5f5" : "#d9d9d9";

  roundedRectPath(rect.x, rect.y, rect.w, rect.h, 4);
  ctx.fill();
  ctx.stroke();

  if (hl) {
    ctx.save();
    ctx.lineWidth = hl === 2 ? 3 : 2;
    ctx.strokeStyle = accent;
    ctx.shadowColor = accent;
    ctx.shadowBlur = hl === 2 ? 10 : 6;
    roundedRectPath(rect.x, rect.y, rect.w, rect.h, 4);
    ctx.stroke();
    ctx.restore();
  }

  const cx = rect.x + rect.w/2;
  const cy = rect.y + rect.h/2;

  ctx.translate(cx, cy);
  ctx.rotate(rotRad); // perpendicular

  ctx.strokeStyle = disabled ? "#666666" : (hl ? accent : "#4a4a4a");
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-5, 0);
  ctx.lineTo(5, 0);
  ctx.stroke();

  ctx.beginPath();
  ctx.moveTo(-5, 0); ctx.lineTo(-2, -2);
  ctx.moveTo(-5, 0); ctx.lineTo(-2,  2);
  ctx.moveTo( 5, 0); ctx.lineTo( 2, -2);
  ctx.moveTo( 5, 0); ctx.lineTo( 2,  2);
  ctx.stroke();

  ctx.restore();
}

/* =============================
   Dimension layout (fixed px buttons, arrow below text)
============================= */
function computeDimensionLayout(ax, ay, bx, by, sidePref /* auto|left|right */, lenBySide = null, opts = null) {
  const sideSign = (opts && (opts.fixedSideSign === 1 || opts.fixedSideSign === -1))
    ? opts.fixedSideSign
    : chooseSideSignWithPref(ax, ay, bx, by, sidePref, opts?.wallEdge || null);

  let aW = { x: ax, y: ay };
  let bW = { x: bx, y: by };

  if (opts?.anchorsBySide) {
    const pack = (sideSign === 1) ? opts.anchorsBySide.left : opts.anchorsBySide.right;
    if (pack?.a && pack?.b) {
      aW = pack.a;
      bW = pack.b;
    }
  } else if (opts?.anchorAWorld && opts?.anchorBWorld) {
    aW = opts.anchorAWorld;
    bW = opts.anchorBWorld;
  }

  const aS = worldToScreen(aW.x, aW.y);
  const bS = worldToScreen(bW.x, bW.y);

  const dxS = bS.x - aS.x;
  const dyS = bS.y - aS.y;
  const LS = Math.hypot(dxS, dyS);
  if (LS < 2) return null;

  const dW = normalize(bx-ax, by-ay);
  const nWorldLeft = { x: -dW.y, y: dW.x };
  const nWorld = { x: nWorldLeft.x * sideSign, y: nWorldLeft.y * sideSign };

  const off = Math.max(0, (opts && typeof opts.offsetMm === "number") ? opts.offsetMm : state.dimOffsetMm);
  const aW2 = { x: aW.x + nWorld.x*off, y: aW.y + nWorld.y*off };
  const bW2 = { x: bW.x + nWorld.x*off, y: bW.y + nWorld.y*off };

  const a2 = worldToScreen(aW2.x, aW2.y);
  const b2 = worldToScreen(bW2.x, bW2.y);

  const dx2 = b2.x - a2.x;
  const dy2 = b2.y - a2.y;
  const L2 = Math.hypot(dx2, dy2) || 1;
  const t = { x: dx2 / L2, y: dy2 / L2 };
  // Pick nTick direction so it always points "outward" (from wall to dimension line),
  // independent of wall node order. This stabilizes text/icon placement for vertical walls.
  let nTick = { x: -t.y, y: t.x };
  const outward = normalize(a2.x - aS.x, a2.y - aS.y); // screen space
  if (dot(nTick.x, nTick.y, outward.x, outward.y) < 0) nTick = { x: -nTick.x, y: -nTick.y };

  const baseLen = Math.hypot(bW.x - aW.x, bW.y - aW.y);
  let effLen = baseLen;
  if (opts && typeof opts.effLenMm === "number" && isFinite(opts.effLenMm) && opts.effLenMm > 0) {
    effLen = opts.effLenMm;
  } else if (lenBySide && typeof lenBySide.left === "number" && typeof lenBySide.right === "number") {
    effLen = (sideSign === 1) ? lenBySide.left : lenBySide.right;
  }
  const txt = formatLengthMm(effLen);

  ctx.save();
  ctx.font = `${state.dimFontPx}px ${state.fontFamily}`;
  const textW = ctx.measureText(txt).width;
  ctx.restore();

  const mid = { x:(a2.x+b2.x)/2, y:(a2.y+b2.y)/2 };

  const tx = mid.x + nTick.x * state.dimGapTextPx;
  const ty = mid.y + nTick.y * state.dimGapTextPx;

  const angle = Math.atan2(dy2, dx2);
  let rot = angle;
  if (rot > Math.PI/2 || rot < -Math.PI/2) rot += Math.PI;

  // fixed-size UI in screen pixels
  const BTN = 18;
  const GAP = 6;
  const PAD = 6;

  const textH = state.dimFontPx + 2*PAD;
  // Text hit area (AABB in screen coords)
  const w0 = textW + 2*PAD;
  const h0 = textH;
  const c = Math.cos(rot), s = Math.sin(rot);
  const aabbW = Math.abs(w0*c) + Math.abs(h0*s);
  const aabbH = Math.abs(w0*s) + Math.abs(h0*c);

  const textRect = { x: tx - aabbW/2, y: ty - aabbH/2, w: aabbW, h: aabbH };

  // Move icon: always "below" the number along nTick (perpendicular to the wall/dimension line)
  const arrowDist = (h0 / 2) + GAP + (BTN / 2);
  const arrowCx = tx + nTick.x * arrowDist;
  const arrowCy = ty + nTick.y * arrowDist;
  const arrowRect = { x: arrowCx - BTN/2, y: arrowCy - BTN/2, w: BTN, h: BTN };

  return {
    aS, bS, a2, b2, t, nTick,
    txt, tx, ty, rot,
    textRect, arrowRect,
    arrowRot: rot + Math.PI/2,
    sideSign,
  };
}

function drawDimensionFromLayout(layout) {
  const { aS, bS, a2, b2, t, nTick, txt, tx, ty, rot } = layout;

  ctx.save();
  ctx.strokeStyle = state.dimColor;
  ctx.fillStyle = state.dimColor;
  ctx.lineWidth = state.dimLineWidthPx;
  ctx.setLineDash([]);

  ctx.beginPath();
  ctx.moveTo(aS.x, aS.y); ctx.lineTo(a2.x, a2.y);
  ctx.moveTo(bS.x, bS.y); ctx.lineTo(b2.x, b2.y);
  ctx.stroke();

  ctx.save();
  ctx.font = `${state.dimFontPx}px ${state.fontFamily}`;
  const textW = ctx.measureText(txt).width;
  ctx.restore();

  const mid = { x:(a2.x+b2.x)/2, y:(a2.y+b2.y)/2 };
  const halfGap = (textW/2) + state.dimTextPadPx;
  const m1 = { x: mid.x - t.x*halfGap, y: mid.y - t.y*halfGap };
  const m2 = { x: mid.x + t.x*halfGap, y: mid.y + t.y*halfGap };

  ctx.beginPath();
  ctx.moveTo(a2.x, a2.y); ctx.lineTo(m1.x, m1.y);
  ctx.moveTo(m2.x, m2.y); ctx.lineTo(b2.x, b2.y);
  ctx.stroke();

  const tick = state.dimTickPx;
  ctx.beginPath();
  ctx.moveTo(a2.x - nTick.x*tick, a2.y - nTick.y*tick);
  ctx.lineTo(a2.x + nTick.x*tick, a2.y + nTick.y*tick);
  ctx.moveTo(b2.x - nTick.x*tick, b2.y - nTick.y*tick);
  ctx.lineTo(b2.x + nTick.x*tick, b2.y + nTick.y*tick);
  ctx.stroke();

  if (layout.hideText) { ctx.restore(); return; }

  ctx.save();
  ctx.translate(tx, ty);
  ctx.rotate(rot);

  ctx.font = `${state.dimFontPx}px ${state.fontFamily}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.direction = "ltr";

  ctx.save();
  ctx.lineWidth = 4;
  ctx.strokeStyle = "#ffffff";
  ctx.strokeText(txt, 0, 0);
  ctx.restore();

  ctx.fillText(txt, 0, 0);
  ctx.restore();

  ctx.restore();
}

/* =============================
   Offset toggle arrow (per wall)
============================= */
function computeOffsetMidpoint(edge) {
  const A = graph.getNode(edge.a);
  const B = graph.getNode(edge.b);
  if (!A || !B) return null;

  const ax=A.x, ay=A.y, bx=B.x, by=B.y;
  const d = normalize(bx-ax, by-ay);
  const nWorldLeft = { x:-d.y, y:d.x };

  const sign = resolveOffsetSideSign(edge);

  const off = getOffsetAxisDistanceMm(edge);

  const mx = (ax+bx)/2;
  const my = (ay+by)/2;

  const ox = mx + nWorldLeft.x*off*sign;
  const oy = my + nWorldLeft.y*off*sign;

  const ang = Math.atan2(by-ay, bx-ax);
  const rot = -ang; // consistent with wall name rotation
  return { x: ox, y: oy, arrowRot: rot + Math.PI/2 };
}

function drawOffsetToggleButtons() {
  if (!state.offsetWallEnabled) return;
  if (!selectedWallId) return;

  const BTN = 18;
  const e = graph.getWall(selectedWallId);
  if (!e) return;
  const m = computeOffsetMidpoint(e);
  if (!m) return;

  const p = worldToScreen(m.x, m.y);
  const rect = { x: p.x - BTN/2, y: p.y - BTN/2, w: BTN, h: BTN };

  addRectTarget("off_side", e.id, rect);
  wallUiIcons.push({ type: "off_side", wallId: e.id, rect, rot: m.arrowRot });
}

/* =============================
   Offset dashed walls
============================= */
function drawOffsetWalls(nodeMap) {
  if (!state.offsetWallEnabled) return;

  const offsets = [];

  for (const e of graph.walls.values()) {
    const A = graph.getNode(e.a);
    const B = graph.getNode(e.b);

    const ax=A.x, ay=A.y, bx=B.x, by=B.y;
    const d = normalize(bx-ax, by-ay);
    const nWorldLeft = { x:-d.y, y:d.x };

    const pref = e.offsetSide || "auto";
    const sign = resolveOffsetSideSign(e);

    const off = getOffsetAxisDistanceMm(e);

    offsets.push({
      A: { x: ax + nWorldLeft.x*off*sign, y: ay + nWorldLeft.y*off*sign },
      B: { x: bx + nWorldLeft.x*off*sign, y: by + nWorldLeft.y*off*sign },
      nA: e.a,
      nB: e.b,
    });
  }

  const jointToOffsets = new Map();
  for (const o of offsets) {
    if (!jointToOffsets.has(o.nA)) jointToOffsets.set(o.nA, []);
    if (!jointToOffsets.has(o.nB)) jointToOffsets.set(o.nB, []);
    jointToOffsets.get(o.nA).push({ o, end:"A" });
    jointToOffsets.get(o.nB).push({ o, end:"B" });
  }

  for (const [, arr] of jointToOffsets.entries()) {
    if (arr.length < 2) continue;
    const p = arr[0], q = arr[1];

    const I = lineIntersect(p.o.A, p.o.B, q.o.A, q.o.B);
    if (!I) continue;

    if (p.end === "A") p.o.A = I; else p.o.B = I;
    if (q.end === "A") q.o.A = I; else q.o.B = I;
  }

  ctx.save();
  ctx.strokeStyle = state.offsetWallColor;
  ctx.lineWidth = state.offsetWallLineWidthPx;
  ctx.setLineDash(state.offsetWallDash);

  for (const o of offsets) {
    const a = worldToScreen(o.A.x, o.A.y);
    const b = worldToScreen(o.B.x, o.B.y);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }

  ctx.restore();
}

/* =============================
   Angles
============================= */
function drawAngles(nodeMap) {
  for (const [nodeId, arr] of nodeMap.entries()) {
    if (arr.length < 2) continue;
    const Jn = graph.getNode(nodeId);
    if (!Jn) continue;

    const dirs = arr.map(({edge}) => {
      const A = graph.getNode(edge.a);
      const B = graph.getNode(edge.b);
      const isJointA = (edge.a === nodeId);
      const ox = isJointA ? (B.x - A.x) : (A.x - B.x);
      const oy = isJointA ? (B.y - A.y) : (A.y - B.y);
      return { edge, v: normalize(ox, oy) };
    });

    for (let i=0; i<dirs.length; i++) {
      for (let j=i+1; j<dirs.length; j++) {
        const v1 = dirs[i].v;
        const v2 = dirs[j].v;
        const ang = angleBetween(v1.x, v1.y, v2.x, v2.y);
        if (!isFinite(ang) || ang < 1e-6) continue;

        const deg = Math.round(radToDeg(ang));

        const Js = worldToScreen(Jn.x, Jn.y);
        const r = state.angleRadiusPx;

        const v1s = { x:v1.x, y:-v1.y };
        const v2s = { x:v2.x, y:-v2.y };
        const a1 = Math.atan2(v1s.y, v1s.x);
        const a2 = Math.atan2(v2s.y, v2s.x);

        let start = a1, end = a2;
        let delta = end - start;
        while (delta > Math.PI) delta -= 2*Math.PI;
        while (delta < -Math.PI) delta += 2*Math.PI;
        end = start + delta;

        ctx.save();
        ctx.strokeStyle = state.angleColor;
        ctx.lineWidth = state.angleArcWidthPx;
        ctx.setLineDash([]);

        ctx.beginPath();
        ctx.arc(Js.x, Js.y, r, start, end, delta < 0);
        ctx.stroke();

        const midA = (start + end)/2;
        const tx = Js.x + Math.cos(midA) * (r + 12);
        const ty = Js.y + Math.sin(midA) * (r + 12);

        ctx.font = `${state.angleFontPx}px ${state.fontFamily}`;
        ctx.fillStyle = state.angleColor;
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.direction = "ltr";

        ctx.save();
        ctx.lineWidth = 4;
        ctx.strokeStyle = "#ffffff";
        ctx.strokeText(`${deg}°`, tx, ty);
        ctx.restore();

        ctx.fillText(`${deg}°`, tx, ty);
        ctx.restore();
      }
    }
  }
}

/* =============================
   Guides
============================= */
function drawGuides() {
  for (const g of guides) {
    const a = worldToScreen(g.x1, g.y1);
    const b = worldToScreen(g.x2, g.y2);

    ctx.save();
    ctx.setLineDash([10, 8]);
    ctx.lineWidth = 2;
    ctx.strokeStyle = state.wallEdgeColor;
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
    ctx.restore();

    const mm = len(g.x1, g.y1, g.x2, g.y2);
    const txt = formatLengthMm(mm);
    const mid = worldToScreen((g.x1+g.x2)/2, (g.y1+g.y2)/2);

    ctx.save();
    ctx.font = `${state.dimFontPx}px ${state.fontFamily}`;
    ctx.fillStyle = state.dimColor;
    ctx.direction = "ltr";
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.fillText(txt, mid.x, mid.y - 14);
    ctx.restore();
  }
}

/* =============================
   3D Model (Projected to 2D) Overlay
============================= */
function drawModel2dOverlay() {
  if (!model2d.lines || model2d.lines.length === 0) return;

  ctx.save();
  ctx.setLineDash(model2d.dash || []);
  ctx.lineWidth = model2d.lineWidthPx || 1;
  ctx.strokeStyle = model2d.color || "#7a8792";
  ctx.globalAlpha = (typeof model2d.alpha === "number") ? model2d.alpha : 0.55;
  ctx.lineCap = "round";

  ctx.beginPath();
  for (const l of model2d.lines) {
    const a = worldToScreen(l.ax, l.ay);
    const b = worldToScreen(l.bx, l.by);
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
  }
  ctx.stroke();
  ctx.restore();

  // Outer outline (brown, hover brightens, selection = menu rail color).
  if (model2d.outline && model2d.outline.length >= 3) {
    const pts = model2d.outline;
    const col = selectedModelOutline
      ? model2d.outlineSelectedColor
      : (hoverModelOutline ? model2d.outlineHoverColor : model2d.outlineColor);

    ctx.save();
    ctx.setLineDash([]);
    // Glow strip similar to wall hover/selection.
    const isSel = !!selectedModelOutline;
    const isHover = !!hoverModelOutline && !isSel;
    const glowAlpha = isSel ? 0.75 : isHover ? 0.55 : 0.40;
    ctx.lineWidth = (isSel ? 6 : isHover ? 5 : 3) || 3;
    ctx.strokeStyle = col;
    ctx.globalAlpha = glowAlpha;
    ctx.shadowColor = col;
    ctx.shadowBlur = isSel ? 16 : isHover ? 11 : 0;
    ctx.lineJoin = "round";
    ctx.lineCap = "round";

    const p0 = worldToScreen(pts[0].x, pts[0].y);
    ctx.beginPath();
    ctx.moveTo(p0.x, p0.y);
    for (let i = 1; i < pts.length; i++) {
      const p = worldToScreen(pts[i].x, pts[i].y);
      ctx.lineTo(p.x, p.y);
    }
    ctx.closePath();
    ctx.stroke();

    // Core pass
    ctx.shadowBlur = 0;
    ctx.globalAlpha = 1;
    ctx.lineWidth = isSel ? 2.8 : isHover ? 2.4 : 2;
    ctx.strokeStyle = col;
    ctx.stroke();
    ctx.restore();
  }
}

function hitTestModelOutline(screenX, screenY) {
  if (!model2d.outline || model2d.outline.length < 3) return false;
  const pts = model2d.outline;
  const thr = selectedModelOutline ? 9 : 7; // px tolerance

  let prev = worldToScreen(pts[0].x, pts[0].y);
  for (let i = 1; i < pts.length; i++) {
    const cur = worldToScreen(pts[i].x, pts[i].y);
    const d = pointToSegmentDistancePx(screenX, screenY, prev.x, prev.y, cur.x, cur.y);
    if (d <= thr) return true;
    prev = cur;
  }
  // closing segment
  const first = worldToScreen(pts[0].x, pts[0].y);
  const last = worldToScreen(pts[pts.length - 1].x, pts[pts.length - 1].y);
  const dClose = pointToSegmentDistancePx(screenX, screenY, last.x, last.y, first.x, first.y);
  return dClose <= thr;
}

function pointInPolygonWorld(x, y, pts) {
  // Ray casting. Works for convex/concave polygons. Boundary is treated as inside.
  if (!pts || pts.length < 3) return false;

  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i].x, yi = pts[i].y;
    const xj = pts[j].x, yj = pts[j].y;

    // Check if point is on the edge (with small epsilon in world mm).
    const d = pointToSegmentDistance(x, y, xj, yj, xi, yi);
    if (d <= 0.5) return true; // 0.5mm

    const intersect = ((yi > y) !== (yj > y)) &&
      (x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-9) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function hitTestModelFill(screenX, screenY) {
  if (!model2d.outline || model2d.outline.length < 3) return false;
  const w = screenToWorld(screenX, screenY);
  return pointInPolygonWorld(w.x, w.y, model2d.outline);
}

/* =============================
   Selection + hover highlight
============================= */
function drawSelectionAndHover() {
  // Hover/selection "light strip" uses the fixed right menu color, like a soft neon.
  const MENU_BASE = "#762D47";
  function hexToRgb(hex) {
    const h = String(hex || "").trim().replace("#", "");
    if (h.length !== 6) return { r: 0, g: 0, b: 0 };
    const n = parseInt(h, 16);
    return { r: (n >> 16) & 255, g: (n >> 8) & 255, b: n & 255 };
  }
  function mixWithWhite(hex, t) {
    const { r, g, b } = hexToRgb(hex);
    const k = Math.max(0, Math.min(1, t));
    const rr = Math.round(r + (255 - r) * k);
    const gg = Math.round(g + (255 - g) * k);
    const bb = Math.round(b + (255 - b) * k);
    return `rgb(${rr},${gg},${bb})`;
  }
  const HOVER_COLOR = mixWithWhite(MENU_BASE, 0.22);
  const SELECT_COLOR = mixWithWhite(MENU_BASE, 0.38);
  const ids = new Set();
  const selectedWallIdSet = new Set(selectedWallIds);
  if (hoverWallId) ids.add(hoverWallId);
  if (selectedWallId) ids.add(selectedWallId);
  for (const id of selectedWallIds) ids.add(id);

  for (const id of ids) {
    const e = graph.getWall(id);
    if (!e) continue;

    const c = computeTrimmedWallCorners(e, lastJointGammaMap);
    if (!c) continue;

    const AL = worldToScreen(c.AL.x, c.AL.y);
    const AR = worldToScreen(c.AR.x, c.AR.y);
    const BL = worldToScreen(c.BL.x, c.BL.y);
    const BR = worldToScreen(c.BR.x, c.BR.y);

    const isSel = id === selectedWallId || selectedWallIdSet.has(id);
    const glow = isSel ? SELECT_COLOR : HOVER_COLOR;
    const core = glow;

    ctx.save();
    ctx.setLineDash([]);
    // Glow pass
    ctx.lineWidth = isSel ? 7 : 6;
    ctx.strokeStyle = glow;
    ctx.globalAlpha = isSel ? 0.85 : 0.62;
    ctx.shadowColor = glow;
    ctx.shadowBlur = isSel ? 18 : 12;
    ctx.beginPath();
    ctx.moveTo(AL.x, AL.y);
    ctx.lineTo(BL.x, BL.y);
    ctx.lineTo(BR.x, BR.y);
    ctx.lineTo(AR.x, AR.y);
    ctx.closePath();
    ctx.stroke();

    // Core "light strip" pass
    ctx.shadowBlur = 0;
    ctx.globalAlpha = 1;
    ctx.lineWidth = isSel ? 3 : 2.5;
    ctx.strokeStyle = core;
    ctx.stroke();
    ctx.restore();
  }
}

function drawWallEditHandles() {
  if (!selectedWallId) return;
  initCursorImagesOnce();
  const w = graph.getWall(selectedWallId);
  if (!w) return;
  const A = graph.getNode(w.a);
  const B = graph.getNode(w.b);
  if (!A || !B) return;

  const aS = worldToScreen(A.x, A.y);
  const bS = worldToScreen(B.x, B.y);
  const midS = { x: (aS.x + bS.x) / 2, y: (aS.y + bS.y) / 2 };
  const dx = bS.x - aS.x;
  const dy = bS.y - aS.y;
  const L = Math.hypot(dx, dy) || 1;
  const tx = dx / L;
  const ty = dy / L;
  const nx = -ty;
  const ny = tx;

  const LEN_SZ = 48;
  const FREE_SZ = 44;
  const MID_W = 48;
  const MID_H = 48;
  const CHAIN_SZ = 18;
  const CHAIN_PUSH = 0; // exactly on wall endpoint
  const LEN_PUSH = (CHAIN_SZ / 2) + (LEN_SZ / 2) + 8; // after joint
  const FREE_PUSH = LEN_PUSH + (LEN_SZ / 2) + (FREE_SZ / 2) + 8; // outermost

  function rectCenter(cx, cy, w0, h0) {
    return { x: cx - w0 / 2, y: cy - h0 / 2, w: w0, h: h0 };
  }
  function drawRect(rect, fill, stroke, lw = 2) {
    ctx.save();
    ctx.setLineDash([]);
    ctx.fillStyle = fill;
    ctx.strokeStyle = stroke;
    ctx.lineWidth = lw;
    ctx.beginPath();
    ctx.rect(rect.x, rect.y, rect.w, rect.h);
    ctx.fill();
    ctx.stroke();
    ctx.restore();
  }
  function drawHandleIcon(rect, iconKey, rotRad, fallbackFill, fallbackStroke) {
    const isHover = !!(hoverWallHandle && hoverWallHandle.wallId === w.id && hoverWallHandle.type === iconKey);
    const activeByKind =
      (iconKey === "len_a" && wallHandleDrag.active && wallHandleDrag.wallId === w.id && wallHandleDrag.kind === "len_a") ||
      (iconKey === "len_b" && wallHandleDrag.active && wallHandleDrag.wallId === w.id && wallHandleDrag.kind === "len_b") ||
      (iconKey === "free_a" && wallHandleDrag.active && wallHandleDrag.wallId === w.id && wallHandleDrag.kind === "free_a") ||
      (iconKey === "free_b" && wallHandleDrag.active && wallHandleDrag.wallId === w.id && wallHandleDrag.kind === "free_b") ||
      (iconKey === "mid" && wallHandleDrag.active && wallHandleDrag.wallId === w.id && wallHandleDrag.kind === "mid_move");
    const alpha = activeByKind ? 1 : isHover ? 0.88 : 0.7;

    const baseKey =
      (iconKey === "len_a" || iconKey === "len_b") ? "len" :
      (iconKey === "free_a" || iconKey === "free_b") ? "free" :
      iconKey;
    const img = wallHandleImgs.get(baseKey);
    if (img && img.complete && img.naturalWidth > 0) {
      ctx.save();
      ctx.globalAlpha = alpha;
      ctx.translate(rect.x + rect.w / 2, rect.y + rect.h / 2);
      if (rotRad) ctx.rotate(rotRad);
      ctx.drawImage(img, -rect.w / 2, -rect.h / 2, rect.w, rect.h);
      ctx.restore();
      return;
    }
    ctx.save();
    ctx.globalAlpha = alpha;
    drawRect(rect, fallbackFill, fallbackStroke);
    ctx.restore();
  }

  const lenA = rectCenter(aS.x - tx * LEN_PUSH, aS.y - ty * LEN_PUSH, LEN_SZ, LEN_SZ);
  const lenB = rectCenter(bS.x + tx * LEN_PUSH, bS.y + ty * LEN_PUSH, LEN_SZ, LEN_SZ);
  const freeA = rectCenter(aS.x - tx * FREE_PUSH, aS.y - ty * FREE_PUSH, FREE_SZ, FREE_SZ);
  const freeB = rectCenter(bS.x + tx * FREE_PUSH, bS.y + ty * FREE_PUSH, FREE_SZ, FREE_SZ);
  const mid = rectCenter(midS.x, midS.y, MID_W, MID_H);
  const chainA = rectCenter(aS.x - tx * CHAIN_PUSH, aS.y - ty * CHAIN_PUSH, CHAIN_SZ, CHAIN_SZ);
  const chainB = rectCenter(bS.x + tx * CHAIN_PUSH, bS.y + ty * CHAIN_PUSH, CHAIN_SZ, CHAIN_SZ);

  addRectTarget("wall_len_a", w.id, lenA);
  addRectTarget("wall_len_b", w.id, lenB);
  addRectTarget("wall_free_a", w.id, freeA);
  addRectTarget("wall_free_b", w.id, freeB);
  addRectTarget("wall_mid_move", w.id, mid);
  addRectTarget("wall_chain_a", w.id, chainA);
  addRectTarget("wall_chain_b", w.id, chainB);

  const wallAng = Math.atan2(ty, tx);
  drawHandleIcon(lenA, "len_a", wallAng, "#ffd18a", "#d97706");
  drawHandleIcon(lenB, "len_b", wallAng, "#ffd18a", "#d97706");
  drawHandleIcon(freeA, "free_a", wallAng + Math.PI, "#ddf9d3", "#16a34a");
  drawHandleIcon(freeB, "free_b", wallAng, "#ddf9d3", "#16a34a");
  drawHandleIcon(mid, "mid", wallAng, "#ffd18a", "#d97706");
  drawHandleIcon(chainA, "joint", wallAng + Math.PI / 2, "#cfe3ff", "#2563eb");
  drawHandleIcon(chainB, "joint", wallAng + Math.PI / 2, "#cfe3ff", "#2563eb");
}

/* =============================
   Gamma debug
============================= */
function drawGammaDebug(jointGammaMap) {
  ctx.save();
  ctx.setLineDash([]);
  ctx.fillStyle = "#ff0000";
  ctx.strokeStyle = "#ffffff";
  ctx.lineWidth = 3;
  ctx.font = `12px ${state.fontFamily}`;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.direction = "ltr";

  const seen = new Set();
  for (const [, m] of jointGammaMap.entries()) {
    for (const [, g] of m.entries()) {
      if (!g?.ok) continue;
      // Avoid drawing the same gamma point multiple times (edges share the same joint corners).
      const k = `${g.gamma.x.toFixed(4)}|${g.gamma.y.toFixed(4)}|${g.mode || ""}`;
      if (seen.has(k)) continue;
      seen.add(k);
      const p = worldToScreen(g.gamma.x, g.gamma.y);
      ctx.beginPath();
      ctx.arc(p.x, p.y, 5, 0, Math.PI * 2);
      ctx.stroke();
      ctx.fill();
      ctx.fillText("γ", p.x + 8, p.y);
    }
  }

  ctx.restore();
}

function buildJointGammaMap(nodeMap) {
  const jointGammaMap = new Map();

  for (const [nodeId, arr] of nodeMap.entries()) {
    if (arr.length !== 2) continue;

    const e1 = arr[0].edge;
    const e2 = arr[1].edge;

    // Miter join needs "cross" pairing:
    // - intersection( e1.left , e2.right )
    // - intersection( e1.right, e2.left  )
    // Doing left-left/right-right makes the two gamma points cross for 90deg corners.
    const gLR = computeGammaAtJoint(graph, nodeId, e1, e2, "left", "right");
    const gRL = computeGammaAtJoint(graph, nodeId, e1, e2, "right", "left");

    const m = new Map();
    // Map into each edge's L/R corners (relative to that edge's local A->B direction in drawSolidEdge).
    // At the joint, e1.left participates in gLR and e1.right participates in gRL.
    // For the other edge, it's swapped.
    m.set(`${e1.id}|L`, gLR);
    m.set(`${e1.id}|R`, gRL);
    m.set(`${e2.id}|L`, gRL);
    m.set(`${e2.id}|R`, gLR);

    jointGammaMap.set(nodeId, m);
  }

  return jointGammaMap;
}

/* =============================
   Draw solid edge
============================= */
function computeTrimmedWallCorners(edge, jointGammaMap) {
  const A = graph.getNode(edge.a);
  const B = graph.getNode(edge.b);
  if (!A || !B) return null;

  const ax = A.x, ay = A.y;
  const bx = B.x, by = B.y;

  const d = normalize(bx - ax, by - ay);
  const n = { x: -d.y, y: d.x };
  const h = edge.thickness / 2;

  // base corners A->B
  let AL = { x: ax + n.x*h, y: ay + n.y*h };
  let AR = { x: ax - n.x*h, y: ay - n.y*h };
  let BL = { x: bx + n.x*h, y: by + n.y*h };
  let BR = { x: bx - n.x*h, y: by - n.y*h };

  // gamma A
  const gA = jointGammaMap?.get(edge.a);
  if (gA && gA.size) {
    const gl = gA.get(`${edge.id}|L`);
    if (gl?.ok) AL = gl.gamma;
    const gr = gA.get(`${edge.id}|R`);
    if (gr?.ok) AR = gr.gamma;
  }
  // gamma B (swap: rule walls are oriented away from the joint, which flips L/R vs A->B)
  const gB = jointGammaMap?.get(edge.b);
  if (gB && gB.size) {
    const gl = gB.get(`${edge.id}|L`);
    if (gl?.ok) BR = gl.gamma;
    const gr = gB.get(`${edge.id}|R`);
    if (gr?.ok) BL = gr.gamma;
  }

  const leftLen = Math.hypot(BL.x - AL.x, BL.y - AL.y);
  const rightLen = Math.hypot(BR.x - AR.x, BR.y - AR.y);

  return {
    ax, ay, bx, by,
    AL, AR, BL, BR,
    leftLen, rightLen,
    anchorsBySide: {
      left: { a: AL, b: BL },
      right: { a: AR, b: BR },
    },
  };
}

function enforceLockedInsideLengths() {
  // Best-effort enforcement: only if wall has exactly one "free" endpoint (degree=1).
  // The joint endpoint stays fixed; the free endpoint moves along the wall direction.
  for (const w of graph.walls.values()) {
    if (!(typeof w.lockedInsideLenMm === "number") || !isFinite(w.lockedInsideLenMm) || w.lockedInsideLenMm <= 0) continue;

    const degA = graph.nodeToWalls.get(w.a)?.size ?? 0;
    const degB = graph.nodeToWalls.get(w.b)?.size ?? 0;

    let fixedNodeId = null;
    if (degA > 1 && degB > 1) continue; // needs a multi-wall solver
    if (degA > 1) fixedNodeId = w.a;        // keep joint fixed
    else if (degB > 1) fixedNodeId = w.b;   // keep joint fixed
    else fixedNodeId = w.a;                 // isolated: keep A fixed

    const A0 = graph.getNode(w.a);
    const B0 = graph.getNode(w.b);
    if (!A0 || !B0) continue;

    const sideSign0 = chooseSideSignWithPref(A0.x, A0.y, B0.x, B0.y, w.dimSide || "auto", w);
    let guess = Math.hypot(B0.x - A0.x, B0.y - A0.y);

    for (let i = 0; i < 6; i++) {
      graph.setWallLengthFromFixedNode(w.id, fixedNodeId, guess);

      const nodeMap = buildNodeEndpointMap(graph);
      const jointGammaMap = buildJointGammaMap(nodeMap);
      const c = computeTrimmedWallCorners(w, jointGammaMap);

      const A = graph.getNode(w.a);
      const B = graph.getNode(w.b);
      const curCenter = (A && B) ? Math.hypot(B.x - A.x, B.y - A.y) : guess;
      const curFace = (c && isFinite(c.leftLen) && isFinite(c.rightLen))
        ? ((sideSign0 === 1) ? c.leftLen : c.rightLen)
        : curCenter;

      const err = w.lockedInsideLenMm - curFace;
      if (!isFinite(err) || Math.abs(err) < 0.1) break;
      guess = Math.max(1, guess + err);
    }
  }
}

function drawWallBodyFromCorners(c) {
  const s1 = worldToScreen(c.AL.x, c.AL.y);
  const s2 = worldToScreen(c.BL.x, c.BL.y);
  const s3 = worldToScreen(c.BR.x, c.BR.y);
  const s4 = worldToScreen(c.AR.x, c.AR.y);

  ctx.save();
  ctx.fillStyle = state.wallFillColor;
  ctx.strokeStyle = state.wallEdgeColor;
  ctx.lineWidth = 1;
  ctx.setLineDash([]);

  ctx.beginPath();
  ctx.moveTo(s1.x, s1.y);
  ctx.lineTo(s2.x, s2.y);
  ctx.lineTo(s3.x, s3.y);
  ctx.lineTo(s4.x, s4.y);
  ctx.closePath();
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function drawWallName(edge, ax, ay, bx, by) {
  const midW = { x: (ax + bx) / 2, y: (ay + by) / 2 };
  const midS = worldToScreen(midW.x, midW.y);
  const ang = Math.atan2(by - ay, bx - ax);

  // Keep wall names readable (avoid upside-down text on right-to-left walls).
  let rot = -ang;
  if (rot > Math.PI / 2) rot -= Math.PI;
  else if (rot < -Math.PI / 2) rot += Math.PI;

  ctx.save();
  ctx.translate(midS.x, midS.y);
  ctx.rotate(rot);

  ctx.fillStyle = state.wallTextColor;
  ctx.font = `${state.wallNameFontPx}px ${state.fontFamily}`;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.direction = "ltr";
  ctx.fillText(edge.name, 0, 0);
  ctx.restore();
}

/* =============================
   Tool overlay (solid preview + live dimension)
============================= */
function drawToolOverlay(tool) {
  const segs = tool.getOverlaySegments();
  if (!segs || !segs.length) return;

  const st = tool.getStatus();
  const thickness = st?.thickness || 120;
  const PREVIEW_COLOR = st?.error ? "#FF2D2D" : "#FF7A00";

  for (const s of segs) {
    const ax = s.a.x, ay = s.a.y;
    const bx = s.b.x, by = s.b.y;

    const d = normalize(bx - ax, by - ay);
    const n = { x: -d.y, y: d.x };
    const h = thickness / 2;

    const AL = { x: ax + n.x*h, y: ay + n.y*h };
    const AR = { x: ax - n.x*h, y: ay - n.y*h };
    const BL = { x: bx + n.x*h, y: by + n.y*h };
    const BR = { x: bx - n.x*h, y: by - n.y*h };

    const p1 = worldToScreen(AL.x, AL.y);
    const p2 = worldToScreen(BL.x, BL.y);
    const p3 = worldToScreen(BR.x, BR.y);
    const p4 = worldToScreen(AR.x, AR.y);

    ctx.save();
    ctx.fillStyle = state.wallFillColor;
    ctx.strokeStyle = state.wallEdgeColor;
    ctx.lineWidth = 1;
    ctx.setLineDash([]);

    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.lineTo(p3.x, p3.y);
    ctx.lineTo(p4.x, p4.y);
    ctx.closePath();
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    // selected-like highlight for preview
    ctx.save();
    ctx.setLineDash([]);
    ctx.lineWidth = 4;
    ctx.strokeStyle = PREVIEW_COLOR;
    ctx.globalAlpha = 1;
    ctx.beginPath();
    ctx.moveTo(p1.x, p1.y);
    ctx.lineTo(p2.x, p2.y);
    ctx.lineTo(p3.x, p3.y);
    ctx.lineTo(p4.x, p4.y);
    ctx.closePath();
    ctx.stroke();
    ctx.restore();

    // live dimension on preview
    const lay = computeDimensionLayout(ax, ay, bx, by, "auto");
    if (lay) drawDimensionFromLayout(lay);
  }

  // Start point marker (plus) for chaining
  if (st?.isDrawing && tool.pendingStartPos) {
    const p = worldToScreen(tool.pendingStartPos.x, tool.pendingStartPos.y);
    const s = 10;
    ctx.save();
    ctx.setLineDash([]);
    ctx.lineCap = "round";

    // White halo for contrast
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.moveTo(p.x - s, p.y); ctx.lineTo(p.x + s, p.y);
    ctx.moveTo(p.x, p.y - s); ctx.lineTo(p.x, p.y + s);
    ctx.stroke();

    // Main mark
    ctx.strokeStyle = PREVIEW_COLOR;
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(p.x - s, p.y); ctx.lineTo(p.x + s, p.y);
    ctx.moveTo(p.x, p.y - s); ctx.lineTo(p.x, p.y + s);
    ctx.stroke();

    ctx.restore();
  }

  if (st?.isDrawing) {
    ctx.save();
    ctx.font = `12px ${state.fontFamily}`;
    ctx.fillStyle = "#000000";
    ctx.textAlign = "left";
    ctx.textBaseline = "top";
    ctx.direction = "ltr";
    ctx.fillText(`${st.wallName}   SNAP:${st.snapEnabled ? "ON" : "OFF"}`, 12, 12);
    ctx.restore();
  }
}

function drawHiddenToolOverlay(tool) {
  const segs = tool.getOverlaySegments();
  if (!segs || !segs.length) return;

  ctx.save();
  ctx.setLineDash(state.hiddenWallDash || [10, 8]);
  ctx.lineCap = "round";
  ctx.lineWidth = (state.hiddenWallLineWidthPx || 2) + 1;
  ctx.strokeStyle = state.hiddenWallColor || "#D8D4D4";

  for (const s of segs) {
    const a = worldToScreen(s.a.x, s.a.y);
    const b = worldToScreen(s.b.x, s.b.y);
    ctx.beginPath();
    ctx.moveTo(a.x, a.y);
    ctx.lineTo(b.x, b.y);
    ctx.stroke();
  }
  ctx.restore();

  // Start point marker (plus) for chaining
  if (tool.getStatus()?.isDrawing && tool.pendingStartPos) {
    const p = worldToScreen(tool.pendingStartPos.x, tool.pendingStartPos.y);
    const s = 10;
    ctx.save();
    ctx.setLineDash([]);
    ctx.lineCap = "round";

    // White halo for contrast
    ctx.strokeStyle = "#ffffff";
    ctx.lineWidth = 6;
    ctx.beginPath();
    ctx.moveTo(p.x - s, p.y); ctx.lineTo(p.x + s, p.y);
    ctx.moveTo(p.x, p.y - s); ctx.lineTo(p.x, p.y + s);
    ctx.stroke();

    // Main mark
    ctx.strokeStyle = state.hiddenWallColor || "#D8D4D4";
    ctx.lineWidth = 3;
    ctx.beginPath();
    ctx.moveTo(p.x - s, p.y); ctx.lineTo(p.x + s, p.y);
    ctx.moveTo(p.x, p.y - s); ctx.lineTo(p.x, p.y + s);
    ctx.stroke();

    ctx.restore();
  }
}

function drawSnapOverlay() {
  if (!state.snapOn) return;
  if (!snapPreview.visible || !snapPreview.candidates.length) return;

  function typeColor(type, active) {
    const midMatchedWhileDrawing =
      type === "mid" &&
      active &&
      state.activeTool === "wall" &&
      !!tool?.getStatus?.()?.isDrawing;
    if (midMatchedWhileDrawing) return "#22c55e"; // green: midpoint matched during wall drawing
    if (type === "origin") return "#2563eb";
    if (type === "corner") return "#111111";
    if (type === "mid") return "#d97706";
    if (type === "edge") return "#dc2626";
    return "#0ea5e9"; // center
  }
  function typeRadius(type, active) {
    const base = (type === "origin") ? 5.2 : (type === "corner") ? 4.8 : (type === "edge") ? 4.2 : 4.5;
    return active ? base + 1.8 : base;
  }

  ctx.save();
  ctx.setLineDash([]);
  ctx.font = `11px ${state.fontFamily}`;
  ctx.textAlign = "left";
  ctx.textBaseline = "middle";
  ctx.direction = "ltr";

  for (const c of snapPreview.candidates) {
    const p = worldToScreen(c.x, c.y);
    const active = !!(snapPreview.active && snapPreview.active.id === c.id);
    const color = typeColor(c.type, active);
    const r = typeRadius(c.type, active);

    ctx.save();
    ctx.globalAlpha = active ? 1 : 0.82;
    ctx.fillStyle = "#ffffff";
    ctx.strokeStyle = color;
    ctx.lineWidth = active ? 2.4 : 1.7;
    ctx.beginPath();
    ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
    ctx.fill();
    ctx.stroke();
    ctx.restore();

    if (active || c.showLabel) {
      const label = c.type;
      const lx = p.x + 9;
      const ly = p.y - 10;
      ctx.save();
      ctx.fillStyle = "rgba(255,255,255,0.92)";
      const tw = ctx.measureText(label).width;
      ctx.fillRect(lx - 3, ly - 7, tw + 6, 14);
      ctx.fillStyle = color;
      ctx.fillText(label, lx, ly);
      ctx.restore();
    }
  }

  ctx.restore();
}

function updateCanvasCursor() {
  // We draw our own cursor inside the canvas. When input is disabled (menus),
  // let the browser show the native cursor.
  canvas.style.cursor = inputEnabled ? "none" : "default";
}

function drawToolCursor() {
  if (!inputEnabled) return;
  if (!isMouseOverCanvas) return;
  if (!isFinite(lastMouseX) || !isFinite(lastMouseY)) return;

  initCursorImagesOnce();

  const isHoverAny =
    !!hoverObjectAxis || !!axisDrag.active ||
    !!hoverModelOutline ||
    !!hoverWallId || !!hoverHiddenId || !!hoverDimId ||
    !!selectedWallId || !!selectedHiddenId || !!selectedDimId || !!selectedModelOutline ||
    selectedWallIds.length > 0 || selectedHiddenIds.length > 0 || selectedDimIds.length > 0;

  // Priority: explicit UI cursor mode (from Vue) -> drawing tool -> hover -> idle.
  let key = null;
  if (uiCursorMode === "beam") key = "beam";
  else if (uiCursorMode === "clicker") key = "clicker";
  else if (uiCursorMode === "wall") key = "wall";
  else if (uiCursorMode === "hidden") key = "hidden";
  else if (uiCursorMode === "dim") key = "dim";
  else if (state.activeTool === "wall") key = "wall";
  else if (state.activeTool === "hidden") key = "hidden";
  else if (state.activeTool === "dim") key = "dim";
  else if (isHoverAny) key = "clicker";
  else key = "cursor";

  // If no draw tool is "selected" (UI mode null) but the engine tool is wall/hidden/dim,
  // fall back to idle/hover cursors to avoid showing a "start drawing" cursor unexpectedly.
  if (!uiCursorMode && (state.activeTool === "wall" || state.activeTool === "hidden" || state.activeTool === "dim")) {
    key = isHoverAny ? "clicker" : "cursor";
  }

  const x = lastMouseX;
  const y = lastMouseY;

  ctx.save();
  ctx.setLineDash([]);
  const img = cursorImgs.get(key);
  const size = (key === "cursor") ? 22 : 24;
  // Cursor hotspot is center-top of PNG to match selection point expectations.
  const hotspotX = size / 2;
  const hotspotY = 0;
  if (img && img.complete && img.naturalWidth > 0) {
    ctx.globalAlpha = 1;
    ctx.drawImage(img, x - hotspotX, y - hotspotY, size, size);
  }

  ctx.restore();
}

function drawBoxSelectOverlay() {
  if (!boxSelect.active) return;
  const r = rectFrom2Points(boxSelect.startX, boxSelect.startY, boxSelect.curX, boxSelect.curY);
  if (r.w < 2 && r.h < 2) return;
  const crossing = boxSelect.curX < boxSelect.startX;
  ctx.save();
  ctx.setLineDash([6, 5]);
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = crossing ? "#2ea3ff" : "#2fbf71";
  ctx.fillStyle = crossing ? "rgba(46,163,255,0.12)" : "rgba(47,191,113,0.12)";
  ctx.beginPath();
  ctx.rect(r.x, r.y, r.w, r.h);
  ctx.fill();
  ctx.stroke();
  ctx.restore();
}

function computeOffsetAndSide(ax, ay, bx, by, px, py) {
  const d = normalize(bx - ax, by - ay);
  const nL = { x: -d.y, y: d.x };
  const apx = px - ax;
  const apy = py - ay;
  const signed = dot(apx, apy, nL.x, nL.y);
  return { offsetMm: Math.abs(signed), sideSign: (signed >= 0) ? 1 : -1 };
}

function drawHourglassMarkerScreen(x, y, color, sizePx = 6) {
  const s = sizePx;
  ctx.save();
  ctx.setLineDash([]);
  ctx.lineWidth = 2;
  ctx.strokeStyle = color;
  ctx.beginPath();
  // two triangles tip-to-tip
  ctx.moveTo(x - s, y);
  ctx.lineTo(x, y - s);
  ctx.lineTo(x + s, y);
  ctx.closePath();
  ctx.moveTo(x - s, y);
  ctx.lineTo(x, y + s);
  ctx.lineTo(x + s, y);
  ctx.closePath();
  ctx.stroke();
  ctx.restore();
}

function drawStandaloneDimensions() {
  if (!state.showDimensions) return;
  for (const d of dimensions) {
    if (!d || !d.a || !d.b) continue;

    const was = state.dimLineWidthPx;
    if (d.id === selectedDimId || selectedDimIds.includes(d.id)) state.dimLineWidthPx = was + 1;
    else if (d.id === hoverDimId) state.dimLineWidthPx = was + 0.5;

    const lay = computeDimensionLayout(
      d.a.x, d.a.y, d.b.x, d.b.y,
      "auto",
      null,
      { offsetMm: d.offsetMm ?? state.dimOffsetMm, fixedSideSign: d.sideSign ?? 1 }
    );
    if (lay) drawDimensionFromLayout(lay);

    state.dimLineWidthPx = was;
  }
}

function drawDimToolOverlay() {
  if (!state.showDimensions) return;
  const st = dimTool.getStatus();
  if (!st?.isDrawing) return;

  const prev = dimTool.getPreview();
  const A = prev.a;
  const B = prev.b;
  const P = prev.cursor;
  if (!A || !P) return;

  // Preview markers
  const aS = worldToScreen(A.x, A.y);
  if (!state.snapOn) drawHourglassMarkerScreen(aS.x, aS.y, state.dimColor, 5);

  if (prev.stage === 1) {
    const pS = worldToScreen(P.x, P.y);
    ctx.save();
    ctx.setLineDash([6, 8]);
    ctx.lineWidth = state.dimLineWidthPx;
    ctx.strokeStyle = state.dimColor;
    ctx.beginPath();
    ctx.moveTo(aS.x, aS.y);
    ctx.lineTo(pS.x, pS.y);
    ctx.stroke();
    ctx.restore();

    if (!state.snapOn) drawHourglassMarkerScreen(pS.x, pS.y, state.dimColor, 5);
    return;
  }

  if (prev.stage === 2 && B) {
    const bS = worldToScreen(B.x, B.y);
    if (!state.snapOn) drawHourglassMarkerScreen(bS.x, bS.y, state.dimColor, 5);

    const { offsetMm, sideSign } = computeOffsetAndSide(A.x, A.y, B.x, B.y, P.x, P.y);
    const lay = computeDimensionLayout(
      A.x, A.y, B.x, B.y,
      "auto",
      null,
      { offsetMm, fixedSideSign: sideSign }
    );
    if (lay) drawDimensionFromLayout(lay);
  }
}

/* =============================
   Main draw
============================= */
function drawWallsNodeBased(tool) {
  hitTargets.length = 0;
  wallUiIcons.length = 0;

  const nodeMap = buildNodeEndpointMap(graph);
  const jointGammaMap = buildJointGammaMap(nodeMap);
  lastJointGammaMap = jointGammaMap;

  if (state.showGammaDebug) drawGammaDebug(jointGammaMap);

  drawOffsetWalls(nodeMap);
  drawOffsetToggleButtons();

  // Precompute trimmed corners once per wall for consistent body/dimension/name layers.
  const wallDrawList = [];
  for (const e of graph.walls.values()) {
    const c = computeTrimmedWallCorners(e, jointGammaMap);
    if (!c) continue;
    wallDrawList.push({ edge: e, corners: c });
  }

  // 1) Wall bodies (geometry layer)
  for (const it of wallDrawList) drawWallBodyFromCorners(it.corners);

  // Guides are drawn above walls, but below dimensions.
  drawGuides();

  // 2) Dimensions (annotation layer, above walls/objects, below wall names)
  if (state.showDimensions) {
    for (const it of wallDrawList) {
      const edge = it.edge;
      const c = it.corners;

      const dimPref = edge.dimSide || "auto";
      const dimLayout = computeDimensionLayout(
        c.ax, c.ay, c.bx, c.by,
        dimPref,
        { left: c.leftLen, right: c.rightLen },
        {
          anchorsBySide: c.anchorsBySide,
          offsetMm: (typeof edge.dimOffsetMm === "number" && isFinite(edge.dimOffsetMm)) ? Math.max(0, edge.dimOffsetMm) : state.dimOffsetMm,
          wallEdge: edge,
        }
      );
      if (!dimLayout) continue;

      dimLayout.hideText = !!(dimEditor.active && dimEditor.wallId === edge.id);
      drawDimensionFromLayout(dimLayout);

      addRectTarget("dim_text", edge.id, dimLayout.textRect);
      if (selectedWallId === edge.id || hoverDimTextWallId === edge.id) {
        addRectTarget("dim_side", edge.id, dimLayout.arrowRect);
        wallUiIcons.push({ type: "dim_side", wallId: edge.id, rect: dimLayout.arrowRect, rot: dimLayout.arrowRot });
      }
    }
  }

  // 3) Wall names (always on top of dimensions)
  for (const it of wallDrawList) {
    const edge = it.edge;
    const c = it.corners;
    drawWallName(edge, c.ax, c.ay, c.bx, c.by);
  }

  drawAngles(nodeMap);
  drawSelectionAndHover();
  drawWallEditHandles();
  drawToolOverlay(tool);
  drawWallUiIconsTopLayer();

  // Keep the inline editor attached to the moving camera/zoom.
  if (dimEditor.active) positionDimEditor(jointGammaMap);
}

function drawWallUiIconsTopLayer() {
  const now = performance.now();
  for (const icon of wallUiIcons) {
    if (icon.type === "dim_side" || icon.type === "off_side") {
      const hovered = !!(hoverUi && hoverUi.type === icon.type && hoverUi.wallId === icon.wallId);
      const active = !!(iconPulse && iconPulse.type === icon.type && iconPulse.wallId === icon.wallId && now < iconPulse.untilMs);
      drawArrowButton(icon.rect, icon.rot, false, { hovered, active, accentColor: state.dimColor });
    }
  }
}

/* =============================
   Tool setup
============================= */
const view = { screenToWorld: (x, y) => screenToWorld(x, y) };

const tool = new SolidWallTool({
  graph,
  view,
  defaultThickness: state.wallThicknessMm || 120,
  snapTolMm: 30,
  startIndex: 0,
});

const hiddenTool = new HiddenWallTool({
  graph: hiddenGraph,
  view,
  snapTolMm: 30,
});

const dimTool = new DimensionTool({
  view,
  snapTolMm: 30,
});

const undo = new UndoManager({
  graph,
  tool,
  hiddenGraph,
  hiddenTool,
  dimTool,
  dimensions,
  model2d,
  onModel2dRestore: () => emitModel2dTransform(),
  getSelection: () => ({
    selectedWallId,
    hoverWallId,
    selectedHiddenId,
    hoverHiddenId,
    selectedDimId,
    hoverDimId,
    selectedWallIds,
    selectedHiddenIds,
    selectedDimIds,
    selectedModelOutline,
    hoverModelOutline,
  }),
  setSelection: (v) => {
    selectedWallId = v.selectedWallId ?? null;
    hoverWallId = v.hoverWallId ?? null;
    selectedHiddenId = v.selectedHiddenId ?? null;
    hoverHiddenId = v.hoverHiddenId ?? null;
    selectedDimId = v.selectedDimId ?? null;
    hoverDimId = v.hoverDimId ?? null;
    selectedWallIds = Array.isArray(v.selectedWallIds) ? v.selectedWallIds.slice() : [];
    selectedHiddenIds = Array.isArray(v.selectedHiddenIds) ? v.selectedHiddenIds.slice() : [];
    selectedDimIds = Array.isArray(v.selectedDimIds) ? v.selectedDimIds.slice() : [];
    selectedModelOutline = !!v.selectedModelOutline;
    hoverModelOutline = !!v.hoverModelOutline;
  },
  maxDepth: 200,
});

/* =============================
   Loop
 ============================= */
let _attached = false;
let _rafId = null;
let _resizeObserver = null;
let _standaloneUiBound = false;

function loop() {
  if (!_attached) return;
  try {
    drawGrid();
    drawModel2dOverlay();
    drawHiddenWalls({
      ctx,
      state,
      graph: hiddenGraph,
      worldToScreen,
      selectedId: selectedHiddenId,
      selectedIds: selectedHiddenIds,
      hoverId: hoverHiddenId,
    });
    drawWallsNodeBased(tool);
    drawSelectedObjectAxes();
    drawStandaloneDimensions();
    drawSnapOverlay();
    if (state.activeTool === "hidden") drawHiddenToolOverlay(hiddenTool);
    if (state.activeTool === "dim") drawDimToolOverlay();
    drawToolCursor();
    drawBoxSelectOverlay();
  } catch (err) {
    showFatalError(err?.stack || err);
    return;
  }
  if (typeof window !== "undefined") window.__WALL_APP_BOOT_OK__ = true;
  _rafId = requestAnimationFrame(loop);
}

/* =============================
   Interaction
 ============================= */
function attach() {
  if (_attached) return;
  _attached = true;

  resize();
  initCursorImagesOnce();
  updateCanvasCursor();

  canvas.addEventListener("mouseenter", onMouseEnter);
  canvas.addEventListener("mouseleave", onMouseLeave);

  // Keep canvas sized to its container (Vue stage / standalone body)
  if (typeof ResizeObserver !== "undefined") {
    _resizeObserver = new ResizeObserver(() => resize());
    try { _resizeObserver.observe(container); } catch (_) {}
  }
  if (typeof window !== "undefined") window.addEventListener("resize", resize);

  canvas.addEventListener("contextmenu", onContextMenu);
  canvas.addEventListener("mousedown", onMouseDown);
  canvas.addEventListener("dblclick", onDblClick);
  canvas.addEventListener("wheel", onWheel, { passive: false });
  if (typeof window !== "undefined") {
    window.addEventListener("mouseup", onWindowMouseUp);
    window.addEventListener("mousemove", onWindowMouseMove);
    window.addEventListener("keydown", onWindowKeyDown);
    window.addEventListener("mousedown", onWindowMouseDown, true);
  }

  bindStandaloneUiIfPresent();

  _rafId = requestAnimationFrame(loop);
}

function detach() {
  if (!_attached) return;
  _attached = false;

  if (dimEditor.active) closeDimEditor(true);
  isPanning = false;

  if (_rafId != null) cancelAnimationFrame(_rafId);
  _rafId = null;

  canvas.removeEventListener("mouseenter", onMouseEnter);
  canvas.removeEventListener("mouseleave", onMouseLeave);

  canvas.removeEventListener("contextmenu", onContextMenu);
  canvas.removeEventListener("mousedown", onMouseDown);
  canvas.removeEventListener("dblclick", onDblClick);
  canvas.removeEventListener("wheel", onWheel, { passive: false });

  if (typeof window !== "undefined") {
    window.removeEventListener("mouseup", onWindowMouseUp);
    window.removeEventListener("mousemove", onWindowMouseMove);
    window.removeEventListener("keydown", onWindowKeyDown);
    window.removeEventListener("mousedown", onWindowMouseDown, true);
    window.removeEventListener("resize", resize);
  }

  if (_resizeObserver) {
    try { _resizeObserver.disconnect(); } catch (_) {}
    _resizeObserver = null;
  }
}

function destroy() {
  detach();
  if (dimEditor.input) {
    try { dimEditor.input.remove(); } catch (_) {}
    dimEditor.input = null;
  }
}

function onMouseEnter() { isMouseOverCanvas = true; }
function onMouseLeave() {
  isMouseOverCanvas = false;
  hoverDimTextWallId = null;
  hoverWallHandle = null;
  hoverObjectAxis = null;
  updateSnapPreview(NaN, NaN);
}
function onContextMenu(e) { e.preventDefault(); }

let isPanning = false;
let lastMiddleClickMs = 0;

function updateHover(offsetX, offsetY) {
  const p = screenToWorld(offsetX, offsetY);
  const tolMm = 40;

  let bestSolid = null;
  let bestSolidD = Infinity;
  for (const edge of graph.walls.values()) {
    const A = graph.getNode(edge.a);
    const B = graph.getNode(edge.b);
    if (!A || !B) continue;
    const d = pointToSegmentDistance(p.x, p.y, A.x, A.y, B.x, B.y);
    if (d < bestSolidD) { bestSolidD = d; bestSolid = edge; }
  }

  let bestHidden = null;
  let bestHiddenD = Infinity;
  for (const edge of hiddenGraph.walls.values()) {
    const A = hiddenGraph.getNode(edge.a);
    const B = hiddenGraph.getNode(edge.b);
    if (!A || !B) continue;
    const d = pointToSegmentDistance(p.x, p.y, A.x, A.y, B.x, B.y);
    if (d < bestHiddenD) { bestHiddenD = d; bestHidden = edge; }
  }

  const solidOk = !!(bestSolid && bestSolidD <= (bestSolid.thickness / 2 + tolMm));
  const hiddenOk = !!(bestHidden && bestHiddenD <= tolMm);

  // Dimension entities are hit-tested in screen space (thin lines).
  let bestDimId = null;
  let bestDimD = Infinity;
  const DIM_TOL_PX = 10;
  for (const d of dimensions) {
    if (!d || !d.a || !d.b) continue;
    const dx = d.b.x - d.a.x;
    const dy = d.b.y - d.a.y;
    const L = Math.hypot(dx, dy);
    if (L < 1e-6) continue;
    const ux = dx / L;
    const uy = dy / L;
    const nx = -uy * (d.sideSign ?? 1);
    const ny = ux * (d.sideSign ?? 1);
    const off = (typeof d.offsetMm === "number") ? d.offsetMm : state.dimOffsetMm;
    const a2w = { x: d.a.x + nx * off, y: d.a.y + ny * off };
    const b2w = { x: d.b.x + nx * off, y: d.b.y + ny * off };
    const a2s = worldToScreen(a2w.x, a2w.y);
    const b2s = worldToScreen(b2w.x, b2w.y);
    const dist = pointToSegmentDistance(offsetX, offsetY, a2s.x, a2s.y, b2s.x, b2s.y);
    if (dist < bestDimD) { bestDimD = dist; bestDimId = d.id; }
  }
  const dimOk = !!(bestDimId && bestDimD <= DIM_TOL_PX);

  // Pick the closest hit across object types.
  if (dimOk) {
    hoverDimId = bestDimId;
    hoverWallId = null;
    hoverHiddenId = null;
  } else if (solidOk && (!hiddenOk || bestSolidD <= bestHiddenD)) {
    hoverWallId = bestSolid.id;
    hoverHiddenId = null;
    hoverDimId = null;
  } else if (hiddenOk) {
    hoverHiddenId = bestHidden.id;
    hoverWallId = null;
    hoverDimId = null;
  } else {
    hoverWallId = null;
    hoverHiddenId = null;
    hoverDimId = null;
  }
}

function pointInPolygonScreen(x, y, pts) {
  if (!pts || pts.length < 3) return false;
  let inside = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i].x, yi = pts[i].y;
    const xj = pts[j].x, yj = pts[j].y;
    const intersect = ((yi > y) !== (yj > y)) &&
      (x < (xj - xi) * (y - yi) / ((yj - yi) || 1e-9) + xi);
    if (intersect) inside = !inside;
  }
  return inside;
}

function applyBoxSelection(x1, y1, x2, y2) {
  const r = rectFrom2Points(x1, y1, x2, y2);
  if (r.w < 3 && r.h < 3) return false;
  const crossing = x2 < x1; // AutoCAD-like: drag left => crossing, right => window

  const nodeMap = buildNodeEndpointMap(graph);
  const jointGammaMap = buildJointGammaMap(nodeMap);
  lastJointGammaMap = jointGammaMap;

  const wallHits = [];
  for (const e of graph.walls.values()) {
    const c = computeTrimmedWallCorners(e, jointGammaMap);
    if (!c) continue;
    const poly = [
      worldToScreen(c.AL.x, c.AL.y),
      worldToScreen(c.BL.x, c.BL.y),
      worldToScreen(c.BR.x, c.BR.y),
      worldToScreen(c.AR.x, c.AR.y),
    ];
    const allInside = poly.every((p) => pointInRect(p.x, p.y, r));
    if (!crossing) {
      if (allInside) wallHits.push(e.id);
      continue;
    }
    let hit = allInside || poly.some((p) => pointInRect(p.x, p.y, r));
    if (!hit) {
      for (let i = 0; i < poly.length; i++) {
        const a = poly[i];
        const b = poly[(i + 1) % poly.length];
        if (segmentIntersectsRectScreen(a.x, a.y, b.x, b.y, r)) { hit = true; break; }
      }
    }
    if (hit) wallHits.push(e.id);
  }

  const hiddenHits = [];
  for (const e of hiddenGraph.walls.values()) {
    const A = hiddenGraph.getNode(e.a);
    const B = hiddenGraph.getNode(e.b);
    if (!A || !B) continue;
    const a = worldToScreen(A.x, A.y);
    const b = worldToScreen(B.x, B.y);
    const allInside = pointInRect(a.x, a.y, r) && pointInRect(b.x, b.y, r);
    const hit = crossing ? (allInside || segmentIntersectsRectScreen(a.x, a.y, b.x, b.y, r)) : allInside;
    if (hit) hiddenHits.push(e.id);
  }

  const dimHits = [];
  for (const d of dimensions) {
    if (!d || !d.a || !d.b) continue;
    const a = worldToScreen(d.a.x, d.a.y);
    const b = worldToScreen(d.b.x, d.b.y);
    const allInside = pointInRect(a.x, a.y, r) && pointInRect(b.x, b.y, r);
    const hit = crossing ? (allInside || segmentIntersectsRectScreen(a.x, a.y, b.x, b.y, r)) : allInside;
    if (hit) dimHits.push(d.id);
  }

  let modelHit = false;
  if (model2d.outline && model2d.outline.length >= 3) {
    const pts = model2d.outline.map((p) => worldToScreen(p.x, p.y));
    const allInside = pts.every((p) => pointInRect(p.x, p.y, r));
    if (!crossing) modelHit = allInside;
    else {
      modelHit = allInside || pts.some((p) => pointInRect(p.x, p.y, r));
      if (!modelHit) {
        for (let i = 0; i < pts.length; i++) {
          const a = pts[i];
          const b = pts[(i + 1) % pts.length];
          if (segmentIntersectsRectScreen(a.x, a.y, b.x, b.y, r)) { modelHit = true; break; }
        }
      }
      if (!modelHit) modelHit = pointInPolygonScreen(r.x + r.w / 2, r.y + r.h / 2, pts);
    }
  }

  if (wallHits.length) {
    selectedWallIds = wallHits.slice();
    selectedWallId = null;
    selectedHiddenId = null;
    selectedDimId = null;
    selectedHiddenIds = [];
    selectedDimIds = [];
    selectedModelOutline = false;
    return true;
  }
  if (hiddenHits.length) {
    selectedWallId = null;
    selectedHiddenId = null;
    selectedDimId = null;
    selectedWallIds = [];
    selectedHiddenIds = hiddenHits.slice();
    selectedDimIds = [];
    selectedModelOutline = false;
    return true;
  }
  if (dimHits.length) {
    selectedWallId = null;
    selectedHiddenId = null;
    selectedDimId = null;
    selectedWallIds = [];
    selectedHiddenIds = [];
    selectedDimIds = dimHits.slice();
    selectedModelOutline = false;
    return true;
  }
  if (modelHit) {
    selectedWallId = null;
    selectedHiddenId = null;
    selectedDimId = null;
    clearGroupSelection();
    selectedModelOutline = true;
    return true;
  }
  return false;
}

const SNAP_TOL_PX = 16;
const SNAP_SHOW_PX = 26;
let snapPreview = { visible: false, candidates: [], active: null };

function snapTypePriority(type) {
  if (type === "origin") return 5;
  if (type === "corner") return 4;
  if (type === "mid") return 3;
  if (type === "center") return 2;
  return 1; // edge
}
function snapTypeEnabled(type) {
  if (type === "corner") return !!state.snapCornerEnabled;
  if (type === "mid") return !!state.snapMidEnabled;
  if (type === "center") return !!state.snapCenterEnabled;
  if (type === "edge") return !!state.snapEdgeEnabled;
  return true;
}
function projPointOnSegment(px, py, ax, ay, bx, by) {
  const abx = bx - ax;
  const aby = by - ay;
  const ab2 = abx * abx + aby * aby;
  if (ab2 < 1e-12) return null;
  const apx = px - ax;
  const apy = py - ay;
  let t = (apx * abx + apy * aby) / ab2;
  t = Math.max(0, Math.min(1, t));
  const x = ax + abx * t;
  const y = ay + aby * t;
  const dx = px - x;
  const dy = py - y;
  return { x, y, t, d2: dx * dx + dy * dy };
}
function collectSnapCandidatesWorld(x, y, tolMm) {
  const out = [];
  const tol2 = tolMm * tolMm;
  let _sid = 0;

  function consider(type, px, py) {
    if (!snapTypeEnabled(type)) return;
    const dx = px - x;
    const dy = py - y;
    const d2 = dx * dx + dy * dy;
    if (d2 > tol2) return;
    out.push({ id: ++_sid, type, x: px, y: py, d2, priority: snapTypePriority(type) });
  }
  function considerSeg(ax, ay, bx, by) {
    consider("mid", (ax + bx) / 2, (ay + by) / 2);
    const p = projPointOnSegment(x, y, ax, ay, bx, by);
    if (p && p.d2 <= tol2) consider("edge", p.x, p.y);
  }

  // Keep (0,0) available as a dedicated snapping anchor.
  consider("origin", 0, 0);

  // Hidden-wall graph remains line-based; its nodes are valid corner snaps.
  for (const n of hiddenGraph.nodes.values()) consider("corner", n.x, n.y);

  // Use trimmed wall geometry so connected joints expose the real visible corners.
  const nodeMap = buildNodeEndpointMap(graph);
  const jointGammaMap = buildJointGammaMap(nodeMap);
  for (const w of graph.walls.values()) {
    const c = computeTrimmedWallCorners(w, jointGammaMap);
    if (!c) continue;

    // Center point on wall axis (requested snap).
    consider("center", (c.ax + c.bx) / 2, (c.ay + c.by) / 2);

    consider("corner", c.AL.x, c.AL.y);
    consider("corner", c.AR.x, c.AR.y);
    consider("corner", c.BL.x, c.BL.y);
    consider("corner", c.BR.x, c.BR.y);

    considerSeg(c.AL.x, c.AL.y, c.BL.x, c.BL.y); // left face
    considerSeg(c.AR.x, c.AR.y, c.BR.x, c.BR.y); // right face
    considerSeg(c.AL.x, c.AL.y, c.AR.x, c.AR.y); // cap near A
    considerSeg(c.BL.x, c.BL.y, c.BR.x, c.BR.y); // cap near B
  }
  for (const w of hiddenGraph.walls.values()) {
    const A = hiddenGraph.getNode(w.a);
    const B = hiddenGraph.getNode(w.b);
    if (!A || !B) continue;
    considerSeg(A.x, A.y, B.x, B.y);
  }

  if (!modelDrag.active && Array.isArray(model2d.outline) && model2d.outline.length >= 2) {
    const pts = model2d.outline;
    for (let i = 0; i < pts.length; i++) {
      const a = pts[i];
      const b = pts[(i + 1) % pts.length];
      consider("corner", a.x, a.y);
      considerSeg(a.x, a.y, b.x, b.y);
    }
  }
  // Intentionally ignore raw model2d internal lines for snapping.
  // Only the outer outline of imported 3D->2D projection is snappable.

  out.sort((a, b) => {
    if (a.priority !== b.priority) return b.priority - a.priority;
    return a.d2 - b.d2;
  });

  const dedup = [];
  for (const c of out) {
    let seen = false;
    for (const d of dedup) {
      const dx = c.x - d.x;
      const dy = c.y - d.y;
      if ((dx * dx + dy * dy) <= 1) { seen = true; break; } // 1 mm^2
    }
    if (!seen) dedup.push(c);
    if (dedup.length >= 24) break;
  }
  return dedup;
}
function updateSnapPreview(offsetX, offsetY) {
  if (!state.snapOn || !isFinite(offsetX) || !isFinite(offsetY)) {
    snapPreview = { visible: false, candidates: [], active: null };
    return;
  }
  const w = screenToWorld(offsetX, offsetY);
  const tolSnapMm = Math.max(4, SNAP_TOL_PX / Math.max(state.zoom, 1e-6));
  const tolShowMm = Math.max(tolSnapMm, SNAP_SHOW_PX / Math.max(state.zoom, 1e-6));
  const all = collectSnapCandidatesWorld(w.x, w.y, tolShowMm);
  const active = all.find((c) => c.d2 <= tolSnapMm * tolSnapMm) || null;
  const candidates = all.map((c, idx) => ({ ...c, showLabel: idx < 4 }));
  snapPreview = { visible: candidates.length > 0, candidates, active };
}
function resolveSnapPointWorld(x, y) {
  if (!state.snapOn) return null;
  const tolSnapMm = Math.max(4, SNAP_TOL_PX / Math.max(state.zoom, 1e-6));
  const candidates = collectSnapCandidatesWorld(x, y, tolSnapMm);
  if (!candidates.length) return null;
  const best = candidates[0];
  return { x: best.x, y: best.y, type: best.type };
}

function isSceneEmpty() {
  const hasModel2d = !!(
    (model2d.lines && model2d.lines.length > 0) ||
    (model2d.outline && model2d.outline.length > 0)
  );
  return (
    graph.nodes.size === 0 &&
    hiddenGraph.nodes.size === 0 &&
    dimensions.length === 0 &&
    guides.length === 0 &&
    !hasModel2d
  );
}

function oppositeExplicitSide(side) {
  return side === "left" ? "right" : "left";
}
function resolveRenderedDimSide(edge) {
  const A = graph.getNode(edge.a);
  const B = graph.getNode(edge.b);
  if (!A || !B) return "left";
  const sign = chooseSideSignWithPref(A.x, A.y, B.x, B.y, edge.dimSide || "auto", edge);
  return sign === 1 ? "left" : "right";
}
function resolveRenderedOffsetSide(edge) {
  const A = graph.getNode(edge.a);
  const B = graph.getNode(edge.b);
  if (!A || !B) return "left";

  const sign = resolveOffsetSideSign(edge);
  return sign === 1 ? "left" : "right";
}

function changeWallLengthByStep(wallId, deltaMm) {
  const w = graph.getWall(wallId);
  if (!w) return;
  const A = graph.getNode(w.a);
  const B = graph.getNode(w.b);
  if (!A || !B) return;
  const cur = Math.hypot(B.x - A.x, B.y - A.y);
  const next = Math.max(1, cur + deltaMm);
  graph.setWallLengthMm(wallId, next);
}

function beginWallHandleDrag(kind, wallId, offsetX, offsetY) {
  const w = graph.getWall(wallId);
  if (!w) return false;
  const A = graph.getNode(w.a);
  const B = graph.getNode(w.b);
  if (!A || !B) return false;
  wallHandleDrag.active = true;
  wallHandleDrag.kind = kind;
  wallHandleDrag.wallId = wallId;
  wallHandleDrag.graphStartSnap = snapshotGraph(graph);
  wallHandleDrag.startMouse = screenToWorld(offsetX, offsetY);
  wallHandleDrag.startA = { x: A.x, y: A.y };
  wallHandleDrag.startB = { x: B.x, y: B.y };
  wallHandleDrag.moved = false;
  return true;
}

function deleteOrphanNodes(g, keepNodeIds = null) {
  const keep = keepNodeIds || new Set();
  const toDelete = [];
  for (const [nodeId, set] of g.nodeToWalls.entries()) {
    if (keep.has(nodeId)) continue;
    if (!set || set.size === 0) toDelete.push(nodeId);
  }
  for (const nodeId of toDelete) {
    g.nodeToWalls.delete(nodeId);
    g.nodes.delete(nodeId);
  }
}

function onMouseDown(e) {
  if (!inputEnabled) return;
  // If an inline editor is open and user clicks outside it, cancel editing.
  if (dimEditor.active && dimEditor.input && e.target !== dimEditor.input) closeDimEditor(true);

  // Right click: toggle angle lock while drawing (tool ignores when idle)
  if (e.button === 2) {
    const ev = {
      button: 2,
      offsetX: e.offsetX,
      offsetY: e.offsetY,
      preventDefault: () => e.preventDefault(),
    };
    if (state.activeTool === "dim") dimTool.onPointerDown(ev, { snapOn: state.snapOn, resolveSnapPoint: resolveSnapPointWorld });
    else if (state.activeTool === "hidden") hiddenTool.onPointerDown(ev, { snapOn: state.snapOn, resolveSnapPoint: resolveSnapPointWorld });
    else if (state.activeTool === "wall") tool.onPointerDown(ev);
    return;
  }

  // Middle: pan
  if (e.button === 1) {
    const now = performance.now();
    if (now - lastMiddleClickMs <= 300) {
      lastMiddleClickMs = 0;
      if (isSceneEmpty()) resetCameraToOriginCenter();
      else fitViewToBounds();
      return;
    }
    lastMiddleClickMs = now;
    isPanning = true;
    return;
  }
  if (e.button !== 0) return;

<<<<<<< ours
// 0) Axis hit => drag selected object on chosen axis.
=======
  // 0) Axis hit => drag selected object on chosen axis.
>>>>>>> theirs
  const axisHit = hitTestObjectAxesScreen(e.offsetX, e.offsetY);
  if (axisHit) {
    beginAxisDrag(axisHit.axis, e.offsetX, e.offsetY);
    return;
  }

  // 1) UI hit => handle and STOP (does not start drawing)
  const t = hitTest(e.offsetX, e.offsetY) || hitTestSelectedWallUiFallback(e.offsetX, e.offsetY);
  if (t) {
    const w = graph.getWall(t.wallId);
    if (!w) return;
    clearGroupSelection();

    if (t.type === "wall_chain_a" || t.type === "wall_chain_b") {
      const nodeId = (t.type === "wall_chain_a") ? w.a : w.b;
      const n = graph.getNode(nodeId);
      if (!n) return;
      selectedHiddenId = null;
      selectedDimId = null;
      selectedWallId = w.id;
      setActiveTool("wall");
      tool.pendingStartNodeId = nodeId;
      tool.pendingStartPos = { x: n.x, y: n.y };
      tool.previewEndPos = { x: n.x, y: n.y };
      return;
    }
    if (t.type === "wall_len_a") {
      selectedHiddenId = null;
      selectedDimId = null;
      selectedWallId = w.id;
      beginWallHandleDrag("len_a", w.id, e.offsetX, e.offsetY);
      return;
    }
    if (t.type === "wall_len_b") {
      selectedHiddenId = null;
      selectedDimId = null;
      selectedWallId = w.id;
      beginWallHandleDrag("len_b", w.id, e.offsetX, e.offsetY);
      return;
    }
    if (t.type === "wall_free_a") {
      selectedHiddenId = null;
      selectedDimId = null;
      selectedWallId = w.id;
      beginWallHandleDrag("free_a", w.id, e.offsetX, e.offsetY);
      return;
    }
    if (t.type === "wall_free_b") {
      selectedHiddenId = null;
      selectedDimId = null;
      selectedWallId = w.id;
      beginWallHandleDrag("free_b", w.id, e.offsetX, e.offsetY);
      return;
    }
    if (t.type === "wall_mid_move") {
      selectedHiddenId = null;
      selectedDimId = null;
      selectedWallId = w.id;
      beginWallHandleDrag("mid_move", w.id, e.offsetX, e.offsetY);
      return;
    }

    if (t.type === "dim_text") {
      selectedHiddenId = null;
      selectedWallId = w.id;
      selectedDimId = null;
      wallDimDrag.active = true;
      wallDimDrag.wallId = w.id;
      wallDimDrag.startDimSide = w.dimSide || "auto";
      wallDimDrag.startSide = resolveRenderedDimSide(w);
      wallDimDrag.startX = e.offsetX;
      wallDimDrag.startY = e.offsetY;
      wallDimDrag.startOffsetMm =
        (typeof w.dimOffsetMm === "number" && isFinite(w.dimOffsetMm))
          ? Math.max(0, w.dimOffsetMm)
          : state.dimOffsetMm;
      wallDimDrag.moved = false;
      return;
    }

    if (t.type === "dim_side") {
      selectedHiddenId = null;
      selectedWallId = w.id;
      selectedDimId = null;
      undo.runAction(() => {
        const current = resolveRenderedDimSide(w);
        w.dimSide = oppositeExplicitSide(current);
      });
      iconPulse = { type: "dim_side", wallId: w.id, untilMs: performance.now() + 260 };
      return;
    }

    if (t.type === "off_side") {
      selectedHiddenId = null;
      selectedWallId = w.id;
      selectedDimId = null;
      undo.runAction(() => {
        const current = resolveRenderedOffsetSide(w);
        w.offsetSideManual = true;
        w.offsetSide = oppositeExplicitSide(current);
      });
      iconPulse = { type: "off_side", wallId: w.id, untilMs: performance.now() + 260 };
      return;
    }

    return;
  }

  // Dimension tool is modal: clicks place/commit dimensions (no selection here).
  if (state.activeTool === "dim") {
    undo.runAction(() => dimTool.onPointerDown(
      { button: 0, offsetX: e.offsetX, offsetY: e.offsetY, shiftKey: e.shiftKey },
      {
        snapOn: state.snapOn,
        resolveSnapPoint: resolveSnapPointWorld,
        onCommit: (d) => dimensions.push(d),
      }
    ));
    return;
  }

  // 2) If active tool is drawing, next click continues that chain.
  if (state.activeTool === "hidden" && hiddenTool.getStatus()?.isDrawing) {
    undo.runAction(() => hiddenTool.onPointerDown({ button: 0, offsetX: e.offsetX, offsetY: e.offsetY, shiftKey: e.shiftKey }, { snapOn: state.snapOn, resolveSnapPoint: resolveSnapPointWorld }));
    return;
  }
  if (state.activeTool === "wall" && tool.getStatus()?.isDrawing) {
    undo.runAction(() => {
      const beforeWalls = graph.walls.size;
      tool.onPointerDown({ button: 0, offsetX: e.offsetX, offsetY: e.offsetY, shiftKey: e.shiftKey });
      if (graph.walls.size !== beforeWalls) enforceLockedInsideLengths();
    });
    return;
  }

  // 3) Object hit (hovered) => select and STOP
  if (hoverModelOutline) {
    clearGroupSelection();
    selectedModelOutline = true;
    selectedWallId = null;
    selectedHiddenId = null;
    selectedDimId = null;
    startModelDrag(e.offsetX, e.offsetY);
    return;
  }
  if (hoverWallId) {
    clearGroupSelection();
    selectedHiddenId = null;
    selectedWallId = hoverWallId;
    selectedDimId = null;
    selectedModelOutline = false;
    return;
  }
  if (hoverHiddenId) {
    clearGroupSelection();
    selectedWallId = null;
    selectedHiddenId = hoverHiddenId;
    selectedDimId = null;
    selectedModelOutline = false;
    return;
  }
  if (hoverDimId) {
    clearGroupSelection();
    selectedWallId = null;
    selectedHiddenId = null;
    selectedDimId = hoverDimId;
    selectedModelOutline = false;
    return;
  }

  // 4) Empty space => start drawing with active tool (unless we're in select mode)
  selectedWallId = null;
  hoverWallId = null;
  selectedHiddenId = null;
  hoverHiddenId = null;
  selectedDimId = null;
  hoverDimId = null;
  clearGroupSelection();
  selectedModelOutline = false;

  if (state.activeTool === "select") {
    // AutoCAD-like box selection (window/crossing) in select mode.
    boxSelect.active = true;
    boxSelect.startX = e.offsetX;
    boxSelect.startY = e.offsetY;
    boxSelect.curX = e.offsetX;
    boxSelect.curY = e.offsetY;
    hoverUi = null;
    hoverWallHandle = null;
    hoverDimTextWallId = null;
    hoverWallId = null;
    hoverHiddenId = null;
    hoverDimId = null;
    hoverModelOutline = false;
    hoverObjectAxis = null;
    return;
  }

  if (state.activeTool === "hidden") {
    undo.runAction(() => hiddenTool.onPointerDown({ button: 0, offsetX: e.offsetX, offsetY: e.offsetY, shiftKey: e.shiftKey }, { snapOn: state.snapOn, resolveSnapPoint: resolveSnapPointWorld }));
  } else if (state.activeTool === "wall") {
    undo.runAction(() => {
      const beforeWalls = graph.walls.size;
      tool.onPointerDown({ button: 0, offsetX: e.offsetX, offsetY: e.offsetY, shiftKey: e.shiftKey });
      if (graph.walls.size !== beforeWalls) enforceLockedInsideLengths();
    });
  }
}

function onWindowMouseUp() {
  if (boxSelect.active) {
    const x1 = boxSelect.startX;
    const y1 = boxSelect.startY;
    const x2 = boxSelect.curX;
    const y2 = boxSelect.curY;
    boxSelect.active = false;
    applyBoxSelection(x1, y1, x2, y2);
  }
  if (wallHandleDrag.active) {
    const startSnap = wallHandleDrag.graphStartSnap;
    const moved = !!wallHandleDrag.moved;
    const endSnap = snapshotGraph(graph);
    wallHandleDrag.active = false;
    wallHandleDrag.kind = null;
    wallHandleDrag.wallId = null;
    wallHandleDrag.graphStartSnap = null;
    wallHandleDrag.startMouse = null;
    wallHandleDrag.startA = null;
    wallHandleDrag.startB = null;
    wallHandleDrag.moved = false;
    if (moved && startSnap) {
      restoreGraph(graph, startSnap);
      undo.runAction(() => {
        restoreGraph(graph, endSnap);
      });
    }
  }
  if (wallDimDrag.active) {
    const wallId = wallDimDrag.wallId;
    const startDimSide = wallDimDrag.startDimSide || "auto";
    const startSide = wallDimDrag.startSide || "left";
    const startOffsetMm = wallDimDrag.startOffsetMm;
    const moved = !!wallDimDrag.moved;
    wallDimDrag.active = false;
    wallDimDrag.wallId = null;

    const w = wallId ? graph.getWall(wallId) : null;
    if (w) {
      const finalDimSide = (w.dimSide === "left" || w.dimSide === "right")
        ? w.dimSide
        : resolveRenderedDimSide(w);
      const finalOffsetMm =
        (typeof w.dimOffsetMm === "number" && isFinite(w.dimOffsetMm))
          ? Math.max(0, w.dimOffsetMm)
          : state.dimOffsetMm;
      const sideChanged = finalDimSide !== startSide;
      if (moved && (Math.abs(finalOffsetMm - startOffsetMm) > 0.1 || sideChanged)) {
        w.dimOffsetMm = startOffsetMm;
        w.dimSide = startDimSide;
        undo.runAction(() => {
          w.dimSide = finalDimSide;
          w.dimOffsetMm = finalOffsetMm;
        });
      } else {
        w.dimOffsetMm = startOffsetMm;
        w.dimSide = startDimSide;
        openDimEditor(w.id);
      }
    }
  }
  if (modelDrag.active) {
    const startSnap = modelDrag.startSnap;
    const moved = !!modelDrag.moved;
    const endSnap = snapshotModel2d(model2d);
    stopModelDrag(true);
    if (moved && startSnap) {
      restoreModel2d(model2d, startSnap);
      undo.runAction(() => {
        restoreModel2d(model2d, endSnap);
        emitModel2dTransform();
      });
    }
    // Keep the model selected after drag.
    selectedModelOutline = true;
    hoverModelOutline = moved ? true : hoverModelOutline;
  }
  if (axisDrag.active) {
    const moved = !!axisDrag.moved;
    const endGraphSnap = snapshotGraph(graph);
    const endHiddenGraphSnap = snapshotGraph(hiddenGraph);
    const endDimensionsSnap = snapshotDimensions(dimensions);
    const endModelSnap = snapshotModel2d(model2d);
    const startGraphSnap = axisDrag.startGraphSnap;
    const startHiddenGraphSnap = axisDrag.startHiddenGraphSnap;
    const startDimensionsSnap = axisDrag.startDimensionsSnap;
    const startModelSnap = axisDrag.startModelSnap;
    stopAxisDrag();
    if (moved && startGraphSnap && startHiddenGraphSnap && startDimensionsSnap && startModelSnap) {
      restoreGraph(graph, startGraphSnap);
      restoreGraph(hiddenGraph, startHiddenGraphSnap);
      restoreDimensions(dimensions, startDimensionsSnap);
      restoreModel2d(model2d, startModelSnap);
      emitModel2dTransform();
      undo.runAction(() => {
        restoreGraph(graph, endGraphSnap);
        restoreGraph(hiddenGraph, endHiddenGraphSnap);
        restoreDimensions(dimensions, endDimensionsSnap);
        restoreModel2d(model2d, endModelSnap);
        emitModel2dTransform();
      });
    }
  }
  isPanning = false;
}

function onWindowMouseMove(e) {
  if (!inputEnabled) {
    isMouseOverCanvas = false;
    return;
  }
  const rect = canvas.getBoundingClientRect();
  const oxRaw = e.clientX - rect.left;
  const oyRaw = e.clientY - rect.top;
  const inside = oxRaw >= 0 && oyRaw >= 0 && oxRaw <= rect.width && oyRaw <= rect.height;

  isMouseOverCanvas = inside;
  if (inside) {
    lastMouseX = oxRaw;
    lastMouseY = oyRaw;
  }

  const isDrawing =
    (state.activeTool === "dim") ? !!dimTool.getStatus()?.isDrawing :
    (state.activeTool === "hidden") ? !!hiddenTool.getStatus()?.isDrawing :
    !!tool.getStatus()?.isDrawing;

  // When integrated in Vue layout, ignore hover/move when pointer is outside the canvas,
  // except while panning or while an active draw command is in progress.
  if (!inside && !isPanning && !isDrawing && !modelDrag.active && !wallDimDrag.active && !wallHandleDrag.active && !boxSelect.active) {
    updateSnapPreview(NaN, NaN);
    hoverUi = null;
    hoverWallHandle = null;
    hoverDimTextWallId = null;
    hoverWallId = null;
    hoverHiddenId = null;
    hoverDimId = null;
    hoverObjectAxis = null;
<<<<<<< ours
  
=======
>>>>>>> theirs
    return;
  }

  const ox = clamp(oxRaw, 0, rect.width);
  const oy = clamp(oyRaw, 0, rect.height);
  if (boxSelect.active) {
    boxSelect.curX = ox;
    boxSelect.curY = oy;
    hoverUi = null;
    hoverWallHandle = null;
    hoverDimTextWallId = null;
    hoverWallId = null;
    hoverHiddenId = null;
    hoverDimId = null;
    hoverModelOutline = false;
    return;
  }
  updateSnapPreview(ox, oy);

  if (axisDrag.active) {
    const target = screenToWorld(ox, oy);
    applyAxisDrag(target);
    hoverObjectAxis = axisDrag.axis;
    return;
  }

  if (modelDrag.active) {
    let target = screenToWorld(ox, oy);
    if (state.snapOn) {
      target = resolveModelDragTargetWorld(target);
    }
    applyModelDrag(target);
    const movedMm = modelDrag.startMouseWorld
      ? Math.hypot(target.x - modelDrag.startMouseWorld.x, target.y - modelDrag.startMouseWorld.y)
      : 0;
    if (movedMm > 0.5) modelDrag.moved = true;
    selectedModelOutline = true;
    hoverModelOutline = true;
    return;
  }

  if (wallHandleDrag.active) {
    const startSnap = wallHandleDrag.graphStartSnap;
    if (!startSnap) {
      wallHandleDrag.active = false;
    } else {
      restoreGraph(graph, startSnap);
      const w = wallHandleDrag.wallId ? graph.getWall(wallHandleDrag.wallId) : null;
      const A = w ? graph.getNode(w.a) : null;
      const B = w ? graph.getNode(w.b) : null;
      const p0 = wallHandleDrag.startMouse;
      const a0 = wallHandleDrag.startA;
      const b0 = wallHandleDrag.startB;
      if (!w || !A || !B || !p0 || !a0 || !b0) {
        wallHandleDrag.active = false;
      } else {
        const rawW = screenToWorld(ox, oy);
        const snapW = rawW;

        const d0 = normalize(b0.x - a0.x, b0.y - a0.y);
        const n0 = { x: -d0.y, y: d0.x };
        if (wallHandleDrag.kind === "mid_move") {
          const dx = snapW.x - p0.x;
          const dy = snapW.y - p0.y;
          const t = dot(dx, dy, n0.x, n0.y);
          A.x = a0.x + n0.x * t;
          A.y = a0.y + n0.y * t;
          B.x = b0.x + n0.x * t;
          B.y = b0.y + n0.y * t;
        } else if (wallHandleDrag.kind === "free_a") {
          const dxMove = rawW.x - p0.x;
          const dyMove = rawW.y - p0.y;
          let target = { x: a0.x + dxMove, y: a0.y + dyMove };
          if (state.snapOn) target = resolveSnapPointWorld(target.x, target.y) || target;
          A.x = target.x;
          A.y = target.y;
        } else if (wallHandleDrag.kind === "free_b") {
          const dxMove = rawW.x - p0.x;
          const dyMove = rawW.y - p0.y;
          let target = { x: b0.x + dxMove, y: b0.y + dyMove };
          if (state.snapOn) target = resolveSnapPointWorld(target.x, target.y) || target;
          B.x = target.x;
          B.y = target.y;
        } else if (wallHandleDrag.kind === "len_a") {
          const ux = -d0.x;
          const uy = -d0.y;
          const vx = snapW.x - b0.x;
          const vy = snapW.y - b0.y;
          const lenNew = Math.max(1, vx * ux + vy * uy);
          A.x = b0.x + ux * lenNew;
          A.y = b0.y + uy * lenNew;
        } else if (wallHandleDrag.kind === "len_b") {
          const ux = d0.x;
          const uy = d0.y;
          const vx = snapW.x - a0.x;
          const vy = snapW.y - a0.y;
          const lenNew = Math.max(1, vx * ux + vy * uy);
          B.x = a0.x + ux * lenNew;
          B.y = a0.y + uy * lenNew;
        }
        graph.mergeCloseNodes(1);
        graph.deleteTinyEdges(1);
        const movedMm = Math.hypot(snapW.x - p0.x, snapW.y - p0.y);
        if (movedMm > 0.5) wallHandleDrag.moved = true;
        return;
      }
    }
  }

  if (wallDimDrag.active) {
    const w = wallDimDrag.wallId ? graph.getWall(wallDimDrag.wallId) : null;
    const A = w ? graph.getNode(w.a) : null;
    const B = w ? graph.getNode(w.b) : null;
    if (!w || !A || !B) {
      wallDimDrag.active = false;
      wallDimDrag.wallId = null;
    } else {
      const sideSign = (wallDimDrag.startSide === "left") ? 1 : -1;
      const dW = normalize(B.x - A.x, B.y - A.y);
      const nWorldLeft = { x: -dW.y, y: dW.x };
      const nWorld = { x: nWorldLeft.x * sideSign, y: nWorldLeft.y * sideSign };
      const startW = screenToWorld(wallDimDrag.startX, wallDimDrag.startY);
      const curW = screenToWorld(ox, oy);
      const deltaX = curW.x - startW.x;
      const deltaY = curW.y - startW.y;
      const deltaMm = dot(deltaX, deltaY, nWorld.x, nWorld.y);
      const signedOffset = wallDimDrag.startOffsetMm + deltaMm;
      if (signedOffset >= 0) {
        w.dimSide = wallDimDrag.startSide;
        w.dimOffsetMm = signedOffset;
      } else {
        w.dimSide = oppositeExplicitSide(wallDimDrag.startSide);
        w.dimOffsetMm = -signedOffset;
      }
      const movedPx = Math.hypot(ox - wallDimDrag.startX, oy - wallDimDrag.startY);
      if (movedPx >= 3) wallDimDrag.moved = true;
      return;
    }
  }

  if (state.activeTool === "dim") dimTool.onPointerMove({ offsetX: ox, offsetY: oy, shiftKey: e.shiftKey }, { snapOn: state.snapOn, resolveSnapPoint: resolveSnapPointWorld });
  else if (state.activeTool === "hidden") hiddenTool.onPointerMove({ offsetX: ox, offsetY: oy, shiftKey: e.shiftKey }, { snapOn: state.snapOn, resolveSnapPoint: resolveSnapPointWorld });
  else tool.onPointerMove({ offsetX: ox, offsetY: oy, shiftKey: e.shiftKey });

  const axisHoverHit = inside ? hitTestObjectAxesScreen(ox, oy) : null;
  hoverObjectAxis = axisHoverHit ? axisHoverHit.axis : null;

  const ht = inside ? hitTest(ox, oy) : null;
  if (
    ht && (
      ht.type === "wall_len_a" || ht.type === "wall_len_b" ||
      ht.type === "wall_free_a" || ht.type === "wall_free_b" ||
      ht.type === "wall_mid_move" ||
      ht.type === "wall_chain_a" || ht.type === "wall_chain_b"
    )
  ) {
    hoverWallHandle = { type: ht.type, wallId: ht.wallId };
  } else {
    hoverWallHandle = null;
  }
  hoverDimTextWallId = (ht && ht.type === "dim_text") ? ht.wallId : null;
  if (ht && (ht.type === "dim_side" || ht.type === "off_side")) {
    hoverUi = { type: ht.type, wallId: ht.wallId };
  } else {
    hoverUi = null;
  }

  if (!isDrawing && inside) {
    updateHover(ox, oy);
    // Hover should activate anywhere inside the model outline, not only on edges.
    hoverModelOutline = hitTestModelFill(ox, oy) || hitTestModelOutline(ox, oy);
  } else if (isDrawing) {
    hoverWallId = null; hoverHiddenId = null; hoverDimId = null;
    hoverModelOutline = false;
  } else {
    hoverModelOutline = false;
  }

  if (!isPanning) return;
  state.offsetX += e.movementX;
  state.offsetY += e.movementY;
}

function isEditableTarget(el) {
  const t = el;
  if (!t) return false;
  if (t.isContentEditable) return true;
  const tag = (t.tagName || "").toUpperCase();
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT";
}

function onWindowKeyDown(e) {
  if (!inputEnabled) return;
  const key = String(e.key || "");
  const code = String(e.code || "");
  const ctrl = !!(e.ctrlKey || e.metaKey);

  // Ctrl+Z undo (only outside editable inputs)
  if (ctrl && !e.shiftKey && (code === "KeyZ" || key.toLowerCase() === "z")) {
    if (isEditableTarget(e.target)) return;
    e.preventDefault();
    if (dimEditor.active) closeDimEditor(true);
    undo.undo();
    return;
  }

  // Ctrl+Y redo (Windows) and Ctrl+Shift+Z redo
  if (ctrl && !e.shiftKey && (code === "KeyY" || key.toLowerCase() === "y")) {
    if (isEditableTarget(e.target)) return;
    e.preventDefault();
    if (dimEditor.active) closeDimEditor(true);
    undo.redo();
    return;
  }
  if (ctrl && e.shiftKey && (code === "KeyZ" || key.toLowerCase() === "z")) {
    if (isEditableTarget(e.target)) return;
    e.preventDefault();
    if (dimEditor.active) closeDimEditor(true);
    undo.redo();
    return;
  }

  // Delete selected wall/object
  if (key === "Delete") {
    if (isEditableTarget(e.target)) return;
    if (dimEditor.active) closeDimEditor(true);
    if (selectedWallIds.length) {
      e.preventDefault();
      const wallIds = selectedWallIds.slice();
      undo.runAction(() => {
        for (const wallId of wallIds) {
          const w = graph.getWall(wallId);
          if (!w) continue;
          graph.deleteWall(wallId);
        }
        deleteOrphanNodes(graph, tool.pendingStartNodeId ? new Set([tool.pendingStartNodeId]) : null);
        if (tool.pendingStartNodeId && !graph.getNode(tool.pendingStartNodeId)) tool.stopChaining();
        enforceLockedInsideLengths();
      });
      hoverWallId = null;
      selectedWallId = null;
      selectedHiddenId = null;
      hoverHiddenId = null;
      selectedDimId = null;
      hoverDimId = null;
      clearGroupSelection();
    } else if (selectedHiddenIds.length) {
      e.preventDefault();
      const wallIds = selectedHiddenIds.slice();
      undo.runAction(() => {
        for (const wallId of wallIds) {
          const w = hiddenGraph.getWall(wallId);
          if (!w) continue;
          hiddenGraph.deleteWall(wallId);
        }
        deleteOrphanNodes(hiddenGraph, hiddenTool.pendingStartNodeId ? new Set([hiddenTool.pendingStartNodeId]) : null);
        if (hiddenTool.pendingStartNodeId && !hiddenGraph.getNode(hiddenTool.pendingStartNodeId)) hiddenTool.stopChaining();
      });
      hoverHiddenId = null;
      selectedHiddenId = null;
      selectedWallId = null;
      hoverWallId = null;
      selectedDimId = null;
      hoverDimId = null;
      clearGroupSelection();
    } else if (selectedDimIds.length) {
      e.preventDefault();
      const dimIds = new Set(selectedDimIds);
      undo.runAction(() => {
        for (let i = dimensions.length - 1; i >= 0; i--) {
          const d = dimensions[i];
          if (!d || !dimIds.has(d.id)) continue;
          dimensions.splice(i, 1);
        }
      });
      hoverDimId = null;
      selectedDimId = null;
      selectedWallId = null;
      hoverWallId = null;
      selectedHiddenId = null;
      hoverHiddenId = null;
      clearGroupSelection();
    } else if (selectedWallId) {
      e.preventDefault();
      const wallId = selectedWallId;
      undo.runAction(() => {
        const w = graph.getWall(wallId);
        if (!w) return;
        graph.deleteWall(wallId);
        deleteOrphanNodes(graph, tool.pendingStartNodeId ? new Set([tool.pendingStartNodeId]) : null);
        if (tool.pendingStartNodeId && !graph.getNode(tool.pendingStartNodeId)) tool.stopChaining();
        enforceLockedInsideLengths();
      });
      hoverWallId = null;
      selectedWallId = null;
      selectedHiddenId = null;
      hoverHiddenId = null;
      selectedDimId = null;
      hoverDimId = null;
      clearGroupSelection();
    } else if (selectedHiddenId) {
      e.preventDefault();
      const wallId = selectedHiddenId;
      undo.runAction(() => {
        const w = hiddenGraph.getWall(wallId);
        if (!w) return;
        hiddenGraph.deleteWall(wallId);
        deleteOrphanNodes(hiddenGraph, hiddenTool.pendingStartNodeId ? new Set([hiddenTool.pendingStartNodeId]) : null);
        if (hiddenTool.pendingStartNodeId && !hiddenGraph.getNode(hiddenTool.pendingStartNodeId)) hiddenTool.stopChaining();
      });
      hoverHiddenId = null;
      selectedHiddenId = null;
      selectedWallId = null;
      hoverWallId = null;
      selectedDimId = null;
      hoverDimId = null;
      clearGroupSelection();
    } else if (selectedDimId) {
      e.preventDefault();
      const dimId = selectedDimId;
      undo.runAction(() => {
        const idx = dimensions.findIndex((d) => d && d.id === dimId);
        if (idx >= 0) dimensions.splice(idx, 1);
      });
      hoverDimId = null;
      selectedDimId = null;
      selectedWallId = null;
      hoverWallId = null;
      selectedHiddenId = null;
      hoverHiddenId = null;
      clearGroupSelection();
    }
    return;
  }

  if (state.activeTool === "dim") dimTool.onKeyDown(e);
  else if (state.activeTool === "hidden") hiddenTool.onKeyDown(e);
  else tool.onKeyDown(e);

  if (key === "Escape") {
    if (boxSelect.active) {
      boxSelect.active = false;
      return;
    }
    if (modelDrag.active) {
      stopModelDrag(false);
      hoverModelOutline = false;
      selectedModelOutline = true;
      return;
    }
    if (wallHandleDrag.active && wallHandleDrag.graphStartSnap) {
      restoreGraph(graph, wallHandleDrag.graphStartSnap);
      wallHandleDrag.active = false;
      wallHandleDrag.kind = null;
      wallHandleDrag.wallId = null;
      wallHandleDrag.graphStartSnap = null;
      wallHandleDrag.startMouse = null;
      wallHandleDrag.startA = null;
      wallHandleDrag.startB = null;
      wallHandleDrag.moved = false;
    }
    if (dimEditor.active) closeDimEditor(false);
    else {
      hoverWallId = null; selectedWallId = null;
      hoverHiddenId = null; selectedHiddenId = null;
      hoverDimId = null; selectedDimId = null;
      clearGroupSelection();
      hoverModelOutline = false; selectedModelOutline = false;
    }
    // Escape exits Dimension command back to Wall tool (AutoCAD-like).
    if (state.activeTool === "dim") setActiveTool("wall");
  }
}

function onWheel(e) {
  if (!inputEnabled) return;
  e.preventDefault();

  const zoomFactor = 1.12;
  zoomAtScreen(e.offsetX, e.offsetY, (e.deltaY < 0) ? zoomFactor : (1 / zoomFactor));
}

function onDblClick(e) {
  if (!inputEnabled) return;
  if (e.button !== 0) return;
  const isDrawing =
    (state.activeTool === "dim") ? !!dimTool.getStatus()?.isDrawing :
    (state.activeTool === "hidden") ? !!hiddenTool.getStatus()?.isDrawing :
    !!tool.getStatus()?.isDrawing;
  if (isDrawing) return;
  e.preventDefault();
  fitViewToBounds();
}

function zoomAtScreen(sx, sy, mul) {
  const mouseWorld = screenToWorld(sx, sy);
  const nextZoom = clamp(state.zoom * mul, 0.05, 20);
  state.zoom = nextZoom;
  state.offsetX = sx - mouseWorld.x * state.zoom;
  state.offsetY = sy + mouseWorld.y * state.zoom;
}

function zoomIn() {
  zoomAtScreen(viewportW / 2, viewportH / 2, 1.12);
}

function zoomOut() {
  zoomAtScreen(viewportW / 2, viewportH / 2, 1 / 1.12);
}

function fitViewToBounds() {
  const pad = 48;
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity;

  for (const n of graph.nodes.values()) {
    minX = Math.min(minX, n.x);
    minY = Math.min(minY, n.y);
    maxX = Math.max(maxX, n.x);
    maxY = Math.max(maxY, n.y);
  }
  for (const n of hiddenGraph.nodes.values()) {
    minX = Math.min(minX, n.x);
    minY = Math.min(minY, n.y);
    maxX = Math.max(maxX, n.x);
    maxY = Math.max(maxY, n.y);
  }
  for (const g of guides) {
    minX = Math.min(minX, g.x1, g.x2);
    minY = Math.min(minY, g.y1, g.y2);
    maxX = Math.max(maxX, g.x1, g.x2);
    maxY = Math.max(maxY, g.y1, g.y2);
  }
  for (const d of dimensions) {
    if (!d || !d.a || !d.b) continue;
    minX = Math.min(minX, d.a.x, d.b.x);
    minY = Math.min(minY, d.a.y, d.b.y);
    maxX = Math.max(maxX, d.a.x, d.b.x);
    maxY = Math.max(maxY, d.a.y, d.b.y);
  }
  for (const l of model2d.lines || []) {
    if (!l) continue;
    minX = Math.min(minX, l.ax, l.bx);
    minY = Math.min(minY, l.ay, l.by);
    maxX = Math.max(maxX, l.ax, l.bx);
    maxY = Math.max(maxY, l.ay, l.by);
  }
  for (const p of model2d.outline || []) {
    if (!p) continue;
    minX = Math.min(minX, p.x);
    minY = Math.min(minY, p.y);
    maxX = Math.max(maxX, p.x);
    maxY = Math.max(maxY, p.y);
  }

  if (!isFinite(minX) || !isFinite(minY) || !isFinite(maxX) || !isFinite(maxY)) {
    state.zoom = 1;
    resetCameraToOriginCenter();
    return;
  }

  const worldW = Math.max(1, maxX - minX);
  const worldH = Math.max(1, maxY - minY);
  const w = viewportW;
  const h = viewportH;
  const zoomX = (w - pad * 2) / worldW;
  const zoomY = (h - pad * 2) / worldH;
  state.zoom = clamp(Math.min(zoomX, zoomY), 0.05, 20);

  // Center-to-center fit (double middle click).
  const cx = (minX + maxX) / 2;
  const cy = (minY + maxY) / 2;
  state.offsetX = w / 2 - cx * state.zoom;
  state.offsetY = h / 2 + cy * state.zoom;
}

// Click outside canvas closes inline dimension editor (important when embedded in Vue UI).
function onWindowMouseDown(e) {
  if (!dimEditor.active || !dimEditor.input) return;
  if (e.target === dimEditor.input) return;
  // If click is inside canvas, onMouseDown handles it.
  if (canvas.contains(e.target)) return;
  closeDimEditor(true);
}

// UI hook helpers (no-ops in embedded mode).
const _ui = {
  updateToolButtons: () => {},
  updateSnapButton: () => {},
};

function setActiveTool(name) {
  const next =
    (name === "select") ? "select" :
    (name === "hidden" || name === "dim" || name === "wall") ? name :
    "wall";
  if (state.activeTool === next) return;

  // Cancel other tools when switching modes.
  if (dimEditor.active) closeDimEditor(true);
  tool.stopChaining();
  hiddenTool.stopChaining();
  dimTool.cancel();

  state.activeTool = next;
  _ui.updateToolButtons();
  updateCanvasCursor();
  saveSettings();
}

function setSnapOn(v) {
  state.snapOn = !!v;
  if (!state.snapOn) updateSnapPreview(NaN, NaN);
  _ui.updateSnapButton();
  saveSettings();
}

function clearAll() {
  if (dimEditor.active) closeDimEditor(true);
  undo.runAction(() => {
    graph.clear();
    hiddenGraph.clear();
    dimensions.length = 0;
    guides.length = 0;
    clearModel2dLines(false);

    tool.wallIndex = 0;
    tool.stopChaining();
    hiddenTool.stopChaining();
    dimTool.cancel();

    selectedWallId = null;
    hoverWallId = null;
    selectedHiddenId = null;
    hoverHiddenId = null;
    selectedDimId = null;
    hoverDimId = null;
    clearGroupSelection();
  });
}

function getState() {
  const graphSnap = snapshotGraph(graph);
  const hiddenGraphSnap = snapshotGraph(hiddenGraph);
  return {
    state: { ...state },
    graphSnap,
    hiddenGraphSnap,
    counts: {
      solidNodes: graphSnap.nodes.length,
      solidWalls: graphSnap.walls.length,
      hiddenNodes: hiddenGraphSnap.nodes.length,
      hiddenWalls: hiddenGraphSnap.walls.length,
      dimensions: dimensions.length,
    },
    model2d: {
      lines: model2d.lines.length,
    },
    tools: {
      wall: tool?.getStatus?.() || null,
      hidden: hiddenTool?.getStatus?.() || null,
      dim: dimTool?.getStatus?.() || null,
    },
    selection: {
      selectedWallId,
      selectedWallIds: selectedWallIds.slice(),
      selectedHiddenId,
      selectedHiddenIds: selectedHiddenIds.slice(),
      selectedDimId,
      selectedDimIds: selectedDimIds.slice(),
      selectedModelOutline,
    },
    input: {
      enabled: !!inputEnabled,
      mouseOverCanvas: !!isMouseOverCanvas,
      lastMouseX,
      lastMouseY,
    },
    cursor: { mode: uiCursorMode },
    viewport: { w: viewportW, h: viewportH, dpr: DPR },
  };
}

function setState(patch) {
  if (!patch || typeof patch !== "object") return;
  for (const k of Object.keys(patch)) {
    if (!(k in state)) continue;
    state[k] = patch[k];
  }

  // Keep tool thickness aligned with global setting.
  if (typeof patch.wallThicknessMm === "number" && isFinite(patch.wallThicknessMm) && patch.wallThicknessMm > 0) {
    const mm = Math.max(1, patch.wallThicknessMm);
    state.wallThicknessMm = mm;
    tool.defaultThickness = mm;
    for (const w of graph.walls.values()) w.thickness = mm;
  }

  _ui.updateToolButtons();
  _ui.updateSnapButton();
  updateCanvasCursor();
  saveSettings();
}

function bindStandaloneUiIfPresent() {
  if (_standaloneUiBound) return;

  // Only bind if the standalone HTML UI exists.
  const toolWallBtn = document.getElementById("toolWallBtn");
  const settingsBtn = document.getElementById("settingsBtn");
  if (!toolWallBtn && !settingsBtn) return;

  _standaloneUiBound = true;

  /* =============================
     Modal/UI wiring (standalone only)
  ============================= */
  const modal = document.getElementById("modalOverlay");
  const modalBox = document.getElementById("modalBox");
  const closeModalBtn = document.getElementById("closeModal");

  if (settingsBtn && modal) settingsBtn.onclick = () => (modal.style.display = "flex");
  if (closeModalBtn && modal) closeModalBtn.onclick = () => (modal.style.display = "none");
  if (modal) modal.onclick = () => (modal.style.display = "none");
  if (modalBox) modalBox.onclick = (e) => e.stopPropagation();

  document.querySelectorAll("#modalOverlay .tab").forEach((tab) => {
    tab.onclick = () => {
      document.querySelectorAll("#modalOverlay .tab").forEach(t => t.classList.remove("active"));
      document.querySelectorAll("#modalOverlay .section").forEach(s => s.classList.remove("active"));
      tab.classList.add("active");
      const sec = document.getElementById(tab.dataset.tab);
      if (sec) sec.classList.add("active");
    };
  });

  function byId(id) { return document.getElementById(id); }
  function normalizeHex(v) {
    if (typeof v !== "string") return "#000000";
    if (/^#[0-9a-fA-F]{6}$/.test(v)) return v.toUpperCase();
    return "#000000";
  }

  function buildColorControls() {
    document.querySelectorAll("#modalOverlay .colorCtl").forEach((host) => {
      const key = host.dataset.color;
      if (!key) return;

      host.innerHTML = "";

      const swatch = document.createElement("div");
      swatch.className = "swatch";
      swatch.style.background = normalizeHex(state[key] || "#000000");

      const hex = document.createElement("div");
      hex.className = "hex";
      hex.textContent = normalizeHex(state[key] || "#000000").toUpperCase();

      const input = document.createElement("input");
      input.type = "color";
      input.className = "hiddenColorInput";
      input.value = normalizeHex(state[key] || "#000000");

      swatch.onclick = () => input.click();
      hex.onclick = () => input.click();

      input.oninput = (e) => {
        const val = normalizeHex(e.target.value);
        state[key] = val;
        swatch.style.background = val;
        hex.textContent = val.toUpperCase();
        saveSettings();
      };

      host.appendChild(swatch);
      host.appendChild(hex);
      host.appendChild(input);
    });
  }

  function initInputs() {
    const unitSelect = byId("unitSelect");
    if (unitSelect) unitSelect.value = state.unit;

    const wallThicknessCm = byId("wallThicknessCm");
    if (wallThicknessCm) wallThicknessCm.value = (state.wallThicknessMm || 120) / 10;

    const wallHeightCm = byId("wallHeightCm");
    if (wallHeightCm) wallHeightCm.value = (state.wallHeightMm || 3000) / 10;

    const dimOffsetMm = byId("dimOffsetMm");
    if (dimOffsetMm) dimOffsetMm.value = state.dimOffsetMm;

    const offsetWallEnabled = byId("offsetWallEnabled");
    if (offsetWallEnabled) offsetWallEnabled.checked = !!state.offsetWallEnabled;

    const offsetWallDistanceMm = byId("offsetWallDistanceMm");
    if (offsetWallDistanceMm) offsetWallDistanceMm.value = state.offsetWallDistanceMm;

    const fontFamily = byId("fontFamily");
    if (fontFamily) fontFamily.value = state.fontFamily;

    const dimFontPx = byId("dimFontPx");
    if (dimFontPx) dimFontPx.value = state.dimFontPx;

    const angleFontPx = byId("angleFontPx");
    if (angleFontPx) angleFontPx.value = state.angleFontPx;

    const wallNameFontPx = byId("wallNameFontPx");
    if (wallNameFontPx) wallNameFontPx.value = state.wallNameFontPx;

    const dimLineWidthPx = byId("dimLineWidthPx");
    if (dimLineWidthPx) dimLineWidthPx.value = state.dimLineWidthPx;

    const meterDivisions = byId("meterDivisions");
    if (meterDivisions) meterDivisions.value = state.meterDivisions;

    const majorEvery = byId("majorEvery");
    if (majorEvery) majorEvery.value = state.majorEvery;

    buildColorControls();
  }
  initInputs();

  // bind changes
  const unitSelect = byId("unitSelect");
  if (unitSelect) unitSelect.onchange = (e) => { state.unit = e.target.value; saveSettings(); };

  const wallThicknessCm = byId("wallThicknessCm");
  if (wallThicknessCm) wallThicknessCm.onchange = (e) => {
    const cm = +e.target.value;
    if (!isFinite(cm) || cm <= 0) return;
    const mm = Math.max(1, cm * 10);
    setState({ wallThicknessMm: mm });
  };

  const wallHeightCm = byId("wallHeightCm");
  if (wallHeightCm) wallHeightCm.onchange = (e) => {
    const cm = +e.target.value;
    if (!isFinite(cm) || cm <= 0) return;
    const mm = Math.max(1, cm * 10);
    setState({ wallHeightMm: mm });
  };

  const dimOffsetMm = byId("dimOffsetMm");
  if (dimOffsetMm) dimOffsetMm.onchange = (e) => { state.dimOffsetMm = +e.target.value || 0; saveSettings(); };

  const offsetWallEnabled = byId("offsetWallEnabled");
  if (offsetWallEnabled) offsetWallEnabled.onchange = (e) => { state.offsetWallEnabled = !!e.target.checked; saveSettings(); };

  const offsetWallDistanceMm = byId("offsetWallDistanceMm");
  if (offsetWallDistanceMm) offsetWallDistanceMm.onchange = (e) => { state.offsetWallDistanceMm = +e.target.value || state.offsetWallDistanceMm; saveSettings(); };

  const fontFamily = byId("fontFamily");
  if (fontFamily) fontFamily.onchange = (e) => { state.fontFamily = e.target.value; saveSettings(); };

  const dimFontPx = byId("dimFontPx");
  if (dimFontPx) dimFontPx.onchange = (e) => { state.dimFontPx = +e.target.value || state.dimFontPx; saveSettings(); };

  const angleFontPx = byId("angleFontPx");
  if (angleFontPx) angleFontPx.onchange = (e) => { state.angleFontPx = +e.target.value || state.angleFontPx; saveSettings(); };

  const wallNameFontPxEl = byId("wallNameFontPx");
  if (wallNameFontPxEl) wallNameFontPxEl.onchange = (e) => { state.wallNameFontPx = +e.target.value || state.wallNameFontPx; saveSettings(); };

  const dimLineWidthPx = byId("dimLineWidthPx");
  if (dimLineWidthPx) dimLineWidthPx.onchange = (e) => { state.dimLineWidthPx = +e.target.value || state.dimLineWidthPx; saveSettings(); };

  const meterDivisions = byId("meterDivisions");
  if (meterDivisions) meterDivisions.onchange = (e) => { state.meterDivisions = +e.target.value || 10; saveSettings(); };

  const majorEvery = byId("majorEvery");
  if (majorEvery) majorEvery.onchange = (e) => { state.majorEvery = +e.target.value || 10; saveSettings(); };

  // top buttons
  const resetZoomBtn = byId("resetZoom");
  if (resetZoomBtn) resetZoomBtn.onclick = () => fitViewToBounds();

  const goOriginBtn = byId("goOrigin");
  if (goOriginBtn) goOriginBtn.onclick = () => resetCameraToOriginCenter();

  // Toolbar: tools + snap + clear
  const toolHiddenBtn = byId("toolHiddenBtn");
  const toolDimBtn = byId("toolDimBtn");
  const snapBtn = byId("snapBtn");
  const clearBtn = byId("clearBtn");

  function updateToolButtons() {
    if (toolWallBtn) toolWallBtn.classList.toggle("active", state.activeTool === "wall");
    if (toolHiddenBtn) toolHiddenBtn.classList.toggle("active", state.activeTool === "hidden");
    if (toolDimBtn) toolDimBtn.classList.toggle("active", state.activeTool === "dim");
  }

  function updateSnapButton() {
    if (!snapBtn) return;
    snapBtn.textContent = state.snapOn ? "Snap: ON" : "Snap: OFF";
    snapBtn.classList.toggle("toggleOn", !!state.snapOn);
  }

  _ui.updateToolButtons = updateToolButtons;
  _ui.updateSnapButton = updateSnapButton;

  if (toolWallBtn) toolWallBtn.onclick = () => setActiveTool("wall");
  if (toolHiddenBtn) toolHiddenBtn.onclick = () => setActiveTool("hidden");
  if (toolDimBtn) toolDimBtn.onclick = () => setActiveTool("dim");

  if (snapBtn) snapBtn.onclick = () => setSnapOn(!state.snapOn);
  if (clearBtn) clearBtn.onclick = () => clearAll();

  updateToolButtons();
  updateSnapButton();
  updateCanvasCursor();
}

return {
  attach,
  detach,
  destroy,

  setActiveTool,
  setSnapOn,
  setInputEnabled,
  setModel2dLines,
  clearModel2dLines,
  setUiCursorMode,

  undo: () => { if (dimEditor.active) closeDimEditor(true); undo.undo(); },
  redo: () => { if (dimEditor.active) closeDimEditor(true); undo.redo(); },
  clearAll,
  zoomIn,
  zoomOut,
  fitView: fitViewToBounds,
  goOrigin: resetCameraToOriginCenter,

  getState,
  setState,
};
}
