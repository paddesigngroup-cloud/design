<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const props = defineProps({
  src: { type: String, required: true },
  model2dTransform: {
    type: Object,
    default: () => ({ x: 0, y: 0, rotRad: 0 }),
  },
  walls2d: {
    type: Object,
    default: () => ({ nodes: [], walls: [] }),
  },
  wallStyleDraft: {
    type: Object,
    default: () => ({ thicknessCm: 12, heightCm: 300, floorOffsetCm: 0, color: "#A6A6A6" }),
  },
  selectedWallStyle: {
    type: Object,
    default: null,
  },
});

const emit = defineEmits(["mouseenter", "mouseleave", "model2d", "update:wallStyleDraft", "update:selectedWallCoords"]);

const widgetEl = ref(null);
const hostEl = ref(null);
const canvasEl = ref(null);

let renderer = null;
let scene = null;
let camera = null;
let controls = null;
let raf = 0;
let ro = null;
let widgetRo = null;
let modelRoot = null;
let modelBasePosition = null;
let modelBaseRotationY = 0;
let wallsRoot = null;

let axesHelper = null;

const DEFAULT_WALL_HEIGHT_M = 2.8;
const DEFAULT_MITER_LIMIT = 10;
const attrsSnapshot = computed(() => props.walls2d?.metrics || props.walls2d || {});
const selectedEntityType = computed(
  () => attrsSnapshot.value?.entityType || props.selectedWallStyle?.entityType || "wall"
);
const isBeamLikeEntity = computed(() => selectedEntityType.value === "beam" || selectedEntityType.value === "column");
const showThicknessField = computed(() => selectedEntityType.value === "wall" || isBeamLikeEntity.value);
const showHeightField = computed(() => selectedEntityType.value === "wall" || isBeamLikeEntity.value);
const showFloorDistanceField = computed(() => showHeightField.value);
const lengthFieldLabel = computed(() => selectedEntityType.value === "column" ? "عرض (cm)" : "طول (cm)");
const thicknessFieldLabel = computed(() => selectedEntityType.value === "column" ? "عمق (cm)" : "ضخامت (cm)");
const colorFieldLabel = computed(() => {
  if (selectedEntityType.value === "column") return "رنگ ستون";
  if (selectedEntityType.value === "beam") return "رنگ تیر";
  return "رنگ دیوار";
});
const showColorField = computed(() => selectedEntityType.value === "wall");

const selectedWallCount = computed(() => {
  const selectedIds = Array.isArray(attrsSnapshot.value?.selection?.selectedWallIds)
    ? attrsSnapshot.value.selection.selectedWallIds.filter(Boolean)
    : [];
  if (selectedIds.length > 0) return selectedIds.length;
  return attrsSnapshot.value?.selection?.selectedWallId ? 1 : 0;
});
const isGroupEditMode = computed(() => selectedWallCount.value > 1);
const selectedObjectTitle = computed(() => {
  const raw = props.selectedWallStyle?.name || props.selectedWallStyle?.id || wallMetrics.value?.id || "";
  return String(raw).trim();
});
const wallMoveDeltaCm = ref({ x: 0, y: 0 });
const coordInputDrafts = ref({});


const wallMetrics = computed(() => {
  const snapshot = attrsSnapshot.value || {};
  const nodes = Array.isArray(snapshot.nodes) ? snapshot.nodes : [];
  const walls = Array.isArray(snapshot.walls) ? snapshot.walls : [];
  const byId = new Map(nodes.map((n) => [n.id, n]));

  const selectedIds = Array.isArray(snapshot?.selection?.selectedWallIds)
    ? snapshot.selection.selectedWallIds
    : [];
  const selectedId = snapshot?.selection?.selectedWallId || selectedIds[0] || null;

  const wall = selectedId ? walls.find((w) => w.id === selectedId) : null;
  if (!wall) return null;

  const a = byId.get(wall.a);
  const b = byId.get(wall.b);
  if (!a || !b) return null;

  const thicknessMm = Math.max(1, Number(wall.thickness) || 120);
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const lengthMm = Math.hypot(dx, dy);
  const heightMm = Number.isFinite(Number(wall.heightMm))
    ? Number(wall.heightMm)
    : 2800;
  const floorOffsetMm = Number.isFinite(Number(wall.floorOffsetMm))
    ? Number(wall.floorOffsetMm)
    : 0;

  const mmToCm = (v) => (Math.round((v * 0.1) * 10) / 10);

  return {
    id: wall.id,
    thicknessCm: mmToCm(thicknessMm),
    lengthCm: mmToCm(lengthMm),
    heightCm: mmToCm(heightMm),
    floorOffsetCm: mmToCm(floorOffsetMm),
    a: { x: mmToCm(a.x), y: mmToCm(a.y) },
    b: { x: mmToCm(b.x), y: mmToCm(b.y) },
  };
});

const wallCoordPoints = computed(() => {
  if (!wallMetrics.value) return null;
  const a = wallMetrics.value.a;
  const b = wallMetrics.value.b;

  const aIsBottomLeft =
    (a.y < b.y) ||
    (a.y === b.y && a.x <= b.x);

  const bottomLeftKey = aIsBottomLeft ? "a" : "b";
  const topRightKey = aIsBottomLeft ? "b" : "a";
  const bottomLeft = aIsBottomLeft ? a : b;
  const topRight = aIsBottomLeft ? b : a;

  return {
    bottomLeftKey,
    topRightKey,
    bottomLeft,
    topRight,
    center: {
      x: Math.round(((a.x + b.x) * 0.5) * 10) / 10,
      y: Math.round(((a.y + b.y) * 0.5) * 10) / 10,
    },
  };
});

const axisTagStyles = computed(() => {
  const st = props.walls2d?.state || {};
  const xColor = (typeof st.axisXColor === "string" && st.axisXColor) ? st.axisXColor : "#9CC9B4";
  const yColor = (typeof st.axisYColor === "string" && st.axisYColor) ? st.axisYColor : "#BCC8EB";
  return {
    x: { color: xColor },
    y: { color: yColor },
  };
});

function getAxisColorsFromState() {
  const st = props.walls2d?.state || {};
  return {
    x: (typeof st.axisXColor === "string" && st.axisXColor) ? st.axisXColor : "#9CC9B4",
    y: (typeof st.axisYColor === "string" && st.axisYColor) ? st.axisYColor : "#BCC8EB",
    z: (typeof st.axisZColor === "string" && st.axisZColor) ? st.axisZColor : "#0000FF",
  };
}

function applyAxesHelperColors() {
  if (!axesHelper?.geometry) return;
  const colorsAttr = axesHelper.geometry.getAttribute("color");
  if (!colorsAttr || colorsAttr.itemSize !== 3 || colorsAttr.count < 6) return;

  const { x, y, z } = getAxisColorsFromState();
  const xColor = new THREE.Color(x);
  const yColor = new THREE.Color(y);
  const zColor = new THREE.Color(z);

  // AxesHelper vertex order: [X0, X1, Y0, Y1, Z0, Z1]
  colorsAttr.setXYZ(0, xColor.r, xColor.g, xColor.b);
  colorsAttr.setXYZ(1, xColor.r, xColor.g, xColor.b);
  colorsAttr.setXYZ(2, yColor.r, yColor.g, yColor.b);
  colorsAttr.setXYZ(3, yColor.r, yColor.g, yColor.b);
  colorsAttr.setXYZ(4, zColor.r, zColor.g, zColor.b);
  colorsAttr.setXYZ(5, zColor.r, zColor.g, zColor.b);
  colorsAttr.needsUpdate = true;
}

function createPlanAlignedAxesHelper(length = 1) {
  const l = Math.max(0.01, Number(length) || 1);

  // Project axis mapping:
  // X -> +X (plan horizontal)
  // Y -> -Z (plan vertical in 2D space)
  // Z -> +Y (height/up)
  const positions = new Float32Array([
    0, 0, 0,  l, 0, 0,   // X
    0, 0, 0,  0, 0, -l,  // Y
    0, 0, 0,  0, l, 0,   // Z
  ]);
  const colors = new Float32Array(18);

  const geom = new THREE.BufferGeometry();
  geom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  geom.setAttribute("color", new THREE.BufferAttribute(colors, 3));

  const mat = new THREE.LineBasicMaterial({
    vertexColors: true,
    toneMapped: false,
    transparent: true,
    opacity: 0.9,
    depthTest: false,
    depthWrite: false,
  });

  const helper = new THREE.LineSegments(geom, mat);
  helper.renderOrder = 999;
  return helper;
}

function patchByPointKey(pointKey, axis, value) {
  if (!Number.isFinite(value)) return;
  if (pointKey === "a") {
    patchSelectedWallCoords(axis === "x" ? { axCm: value } : { ayCm: value });
  } else {
    patchSelectedWallCoords(axis === "x" ? { bxCm: value } : { byCm: value });
  }
}


function patchWallStyleDraft(patch) {
  emit("update:wallStyleDraft", {
    ...props.wallStyleDraft,
    ...patch,
  });
}

function patchSelectedWallCoords(patch) {
  emit("update:selectedWallCoords", patch);
}

function patchCenterCoord(axis, value) {
  if (!wallMetrics.value) return;
  const num = Number(value);
  if (!Number.isFinite(num)) return;

  const curCenter = wallCoordPoints.value?.center;
  if (!curCenter) return;

  const dx = (axis === "x") ? (num - curCenter.x) : 0;
  const dy = (axis === "y") ? (num - curCenter.y) : 0;
  if (dx === 0 && dy === 0) return;

  patchSelectedWallCoords({
    axCm: wallMetrics.value.a.x + dx,
    ayCm: wallMetrics.value.a.y + dy,
    bxCm: wallMetrics.value.b.x + dx,
    byCm: wallMetrics.value.b.y + dy,
  });
}

function patchWallMoveDelta(axis, value) {
  if (axis !== "x" && axis !== "y") return;
  const num = parseNumericInput(value);
  wallMoveDeltaCm.value = {
    ...wallMoveDeltaCm.value,
    [axis]: Number.isFinite(num) ? (Math.round(num * 10) / 10) : 0,
  };
}

function moveWallByAxis(axis) {
  if (axis !== "x" && axis !== "y") return;
  const delta = Number(wallMoveDeltaCm.value?.[axis]);
  if (!Number.isFinite(delta) || delta === 0) return;

  if (isGroupEditMode.value) {
    patchSelectedWallCoords(axis === "x" ? { dxCm: delta } : { dyCm: delta });
    wallMoveDeltaCm.value = {
      ...wallMoveDeltaCm.value,
      [axis]: 0,
    };
    return;
  }
  if (!wallMetrics.value) return;

  if (axis === "x") {
    patchSelectedWallCoords({
      axCm: wallMetrics.value.a.x + delta,
      bxCm: wallMetrics.value.b.x + delta,
    });
  } else {
    patchSelectedWallCoords({
      ayCm: wallMetrics.value.a.y + delta,
      byCm: wallMetrics.value.b.y + delta,
    });
  }

  wallMoveDeltaCm.value = {
    ...wallMoveDeltaCm.value,
    [axis]: 0,
  };
}

function normalizeNumericText(value) {
  const raw = String(value ?? "").trim();
  if (!raw) return "";
  return raw
    .replace(/[۰-۹]/g, (d) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(d)))
    .replace(/[٠-٩]/g, (d) => String("٠١٢٣٤٥٦٧٨٩".indexOf(d)))
    .replace(/[−﹣－]/g, "-")
    .replace(/[٫،]/g, ".");
}

function parseNumericInput(value) {
  const normalized = normalizeNumericText(value);
  if (!normalized) return NaN;
  return Number(normalized);
}

function getCoordFieldValue(key, fallback) {
  if (Object.prototype.hasOwnProperty.call(coordInputDrafts.value, key)) {
    return coordInputDrafts.value[key];
  }
  return (fallback ?? "");
}

function setCoordFieldDraft(key, value) {
  coordInputDrafts.value = { ...coordInputDrafts.value, [key]: String(value ?? "") };
}

function clearCoordFieldDraft(key) {
  if (!Object.prototype.hasOwnProperty.call(coordInputDrafts.value, key)) return;
  const next = { ...coordInputDrafts.value };
  delete next[key];
  coordInputDrafts.value = next;
}

function commitMoveDeltaInput(axis, key) {
  const text = coordInputDrafts.value[key];
  if (typeof text === "undefined") return;
  patchWallMoveDelta(axis, text);
  clearCoordFieldDraft(key);
}

function commitCenterCoordInput(axis, key) {
  const text = coordInputDrafts.value[key];
  const num = parseNumericInput(text);
  clearCoordFieldDraft(key);
  if (!Number.isFinite(num)) return;
  patchCenterCoord(axis, num);
}

function commitPointCoordInput(pointKey, axis, key) {
  const text = coordInputDrafts.value[key];
  const num = parseNumericInput(text);
  clearCoordFieldDraft(key);
  if (!Number.isFinite(num)) return;
  patchByPointKey(pointKey, axis, num);
}

watch(
  [() => wallMetrics.value?.id, () => selectedWallCount.value, () => isGroupEditMode.value],
  () => {
    coordInputDrafts.value = {};
  }
);


function v(x, z) {
  return { x, z };
}

function add(a, b) {
  return v(a.x + b.x, a.z + b.z);
}

function sub(a, b) {
  return v(a.x - b.x, a.z - b.z);
}

function mul(a, s) {
  return v(a.x * s, a.z * s);
}

function len(a) {
  return Math.hypot(a.x, a.z);
}

function norm(a) {
  const l = len(a);
  if (l <= 1e-9) return v(0, 0);
  return v(a.x / l, a.z / l);
}

function perpLeft(a) {
  return v(-a.z, a.x);
}

function cross2(a, b) {
  return a.x * b.z - a.z * b.x;
}

function lineLineIntersection2d(p, r, q, s, eps = 1e-9) {
  const rxs = cross2(r, s);
  if (Math.abs(rxs) < eps) return null;
  const qmp = sub(q, p);
  const t = cross2(qmp, s) / rxs;
  return add(p, mul(r, t));
}

function angleDeg2d(a, b) {
  const na = norm(a);
  const nb = norm(b);
  const d = THREE.MathUtils.clamp(na.x * nb.x + na.z * nb.z, -1, 1);
  return (Math.acos(d) * 180) / Math.PI;
}

function buildNodeEndpointMap(walls) {
  const map = new Map();
  for (const e of walls) {
    if (!map.has(e.a)) map.set(e.a, []);
    if (!map.has(e.b)) map.set(e.b, []);
    map.get(e.a).push({ edge: e, at: "a" });
    map.get(e.b).push({ edge: e, at: "b" });
  }
  return map;
}

function computeGammaAtJoint(nodeId, edge1, edge2, side1, side2, byId) {
  const makeRay = (edge, side) => {
    const A = byId.get(edge.a);
    const B = byId.get(edge.b);
    if (!A || !B) return null;

    const sharedIsA = edge.a === nodeId;
    const J = sharedIsA ? v(A.x * 0.001, -A.y * 0.001) : v(B.x * 0.001, -B.y * 0.001);
    const O = sharedIsA ? v(B.x * 0.001, -B.y * 0.001) : v(A.x * 0.001, -A.y * 0.001);
    const dir = norm(sub(O, J));
    const n = norm(side === "left" ? perpLeft(dir) : mul(perpLeft(dir), -1));
    const half = Math.max(0.01, (Number(edge.thickness) || 120) * 0.001 * 0.5);
    return { J, dir, bJ: add(J, mul(n, half)), half };
  };

  const r1 = makeRay(edge1, side1);
  const r2 = makeRay(edge2, side2);
  if (!r1 || !r2) return null;

  const gamma = lineLineIntersection2d(r1.bJ, r1.dir, r2.bJ, r2.dir);
  if (!gamma) return null;

  const miterLen = len(sub(gamma, r1.J));
  const h = Math.max(r1.half, r2.half);
  if (h > 0 && miterLen > h * DEFAULT_MITER_LIMIT) return null;

  return { ok: true, gamma, angleDeg: angleDeg2d(r1.dir, r2.dir) };
}

function buildJointGammaMap(walls, byId) {
  const map = new Map();
  const nodeMap = buildNodeEndpointMap(walls);

  for (const [nodeId, arr] of nodeMap.entries()) {
    if (arr.length !== 2) continue;
    const e1 = arr[0].edge;
    const e2 = arr[1].edge;

    const gLR = computeGammaAtJoint(nodeId, e1, e2, "left", "right", byId);
    const gRL = computeGammaAtJoint(nodeId, e1, e2, "right", "left", byId);

    const m = new Map();
    m.set(`${e1.id}|L`, gLR);
    m.set(`${e1.id}|R`, gRL);
    m.set(`${e2.id}|L`, gRL);
    m.set(`${e2.id}|R`, gLR);
    map.set(nodeId, m);
  }

  return map;
}

function computeTrimmedWallCorners(edge, byId, jointGammaMap) {
  const A = byId.get(edge.a);
  const B = byId.get(edge.b);
  if (!A || !B) return null;

  const ax = A.x * 0.001;
  const az = -A.y * 0.001;
  const bx = B.x * 0.001;
  const bz = -B.y * 0.001;

  const d = norm(v(bx - ax, bz - az));
  if (len(d) <= 1e-9) return null;
  const n = perpLeft(d);
  const h = Math.max(0.01, (Number(edge.thickness) || 120) * 0.001 * 0.5);

  let AL = v(ax + n.x * h, az + n.z * h);
  let AR = v(ax - n.x * h, az - n.z * h);
  let BL = v(bx + n.x * h, bz + n.z * h);
  let BR = v(bx - n.x * h, bz - n.z * h);

  const gA = jointGammaMap?.get(edge.a);
  if (gA?.size) {
    const gl = gA.get(`${edge.id}|L`);
    if (gl?.ok) AL = gl.gamma;
    const gr = gA.get(`${edge.id}|R`);
    if (gr?.ok) AR = gr.gamma;
  }

  const gB = jointGammaMap?.get(edge.b);
  if (gB?.size) {
    const gl = gB.get(`${edge.id}|L`);
    if (gl?.ok) BR = gl.gamma;
    const gr = gB.get(`${edge.id}|R`);
    if (gr?.ok) BL = gr.gamma;
  }

  return { AL, AR, BL, BR };
}

function makeWallExtrudedMesh(corners, heightM, material) {
  const pts = [corners.AL, corners.BL, corners.BR, corners.AR];
  const h = Math.max(0.1, Number(heightM) || DEFAULT_WALL_HEIGHT_M);

  // Build a 2D face from wall corners (plan view), then extrude it by wall height.
  // Shape is authored in (x, -z) so after rotateX(-90deg):
  // - shape plane maps to XZ
  // - extrusion depth maps to +Y (wall height)
  const shape = new THREE.Shape();
  shape.moveTo(pts[0].x, -pts[0].z);
  for (let i = 1; i < pts.length; i += 1) shape.lineTo(pts[i].x, -pts[i].z);
  shape.closePath();

  const g = new THREE.ExtrudeGeometry(shape, {
    depth: h,
    bevelEnabled: false,
    steps: 1,
    curveSegments: 1,
  });
  g.rotateX(-Math.PI / 2);
  g.computeVertexNormals();
  return new THREE.Mesh(g, material);
}

function clearWalls3d() {
  if (!scene || !wallsRoot) return;
  wallsRoot.traverse((n) => {
    if (n.geometry) n.geometry.dispose?.();
    if (n.material) {
      const mats = Array.isArray(n.material) ? n.material : [n.material];
      for (const m of mats) m.dispose?.();
    }
  });
  scene.remove(wallsRoot);
  wallsRoot = null;
}

function normalizeLinearMembers(snapshot) {
  const nodes = Array.isArray(snapshot?.nodes) ? snapshot.nodes : [];
  const walls = Array.isArray(snapshot?.walls) ? snapshot.walls : [];
  return { nodes, walls };
}

function buildLinearMemberMesh(w, byId, jointGammaMap, fallbackFillColor = "#C7CCD1") {
  const corners = computeTrimmedWallCorners(w, byId, jointGammaMap);
  if (!corners) return null;

  const heightMm = Number.isFinite(Number(w?.heightMm))
    ? Number(w.heightMm)
    : 2800;
  const heightM = Math.max(0.1, heightMm * 0.001);

  const colorHex = (typeof w?.color3d === "string" && w.color3d)
    ? w.color3d
    : ((typeof w?.fillColor === "string" && w.fillColor) ? w.fillColor : fallbackFillColor);

  const memberMat = new THREE.MeshStandardMaterial({
    color: new THREE.Color(colorHex),
    roughness: 0.86,
    metalness: 0.05,
  });

  const mesh = makeWallExtrudedMesh(corners, heightM, memberMat);
  const floorOffsetMm = Number.isFinite(Number(w?.floorOffsetMm)) ? Number(w.floorOffsetMm) : 0;
  mesh.position.y = Math.max(0, floorOffsetMm * 0.001);
  return mesh;
}

function rebuildWalls3d(snapshot) {
  if (!scene) return;
  clearWalls3d();

  try {
    const normalized =
      (typeof normalizeLinearMembers === "function")
        ? normalizeLinearMembers(snapshot)
        : {
            nodes: Array.isArray(snapshot?.nodes) ? snapshot.nodes : [],
            walls: Array.isArray(snapshot?.walls) ? snapshot.walls : [],
          };
    const nodes = Array.isArray(normalized?.nodes) ? normalized.nodes : [];
    const walls = Array.isArray(normalized?.walls) ? normalized.walls : [];
    if (!nodes.length || !walls.length) return;

    const byId = new Map(nodes.map((n) => [n.id, n]));
    const root = new THREE.Group();
    root.name = "walls2d-extruded";
    const fallbackFillColor = "#C7CCD1";

    const jointGammaMap = buildJointGammaMap(walls, byId);

    for (const w of walls) {
      const mesh = buildLinearMemberMesh(w, byId, jointGammaMap, fallbackFillColor);
      if (!mesh) continue;
      root.add(mesh);
    }

    if (!root.children.length) return;
    wallsRoot = root;
    scene.add(root);
  } catch (err) {
    console.error("[GlbViewerWidget] rebuildWalls3d failed", err);
  }
}

function computeRenderableSceneBounds() {
  if (!scene) return null;
  const bounds = new THREE.Box3();
  let hasRenderable = false;

  scene.traverse((obj) => {
    if (!obj?.visible) return;
    if (axesHelper && obj === axesHelper) return;
    if (!obj.isMesh && !obj.isLine && !obj.isPoints) return;
    if (!obj.geometry) return;
    bounds.expandByObject(obj);
    hasRenderable = true;
  });

  if (!hasRenderable || bounds.isEmpty()) return null;
  return bounds;
}

function fitCameraToBounds(bounds, viewDir = null) {
  if (!camera || !controls || !bounds) return;

  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  bounds.getSize(size);
  bounds.getCenter(center);

  const fov = THREE.MathUtils.degToRad(camera.fov || 45);
  const fitHeight = size.y / Math.max(Math.tan(fov * 0.5), 1e-3);
  const fitWidth =
    size.x /
    Math.max(Math.tan(fov * 0.5) * Math.max(camera.aspect, 1e-3), 1e-3);
  const fitDepth = size.z;
  const distance = Math.max(fitHeight, fitWidth, fitDepth, 0.5) * 0.7;

  const dir = (viewDir || new THREE.Vector3(1, 0.65, 1)).clone().normalize();

  camera.up.set(0, 1, 0);
  if (Math.abs(dir.y) > 0.9) camera.up.set(0, 0, -1);

  camera.position.copy(center).addScaledVector(dir, distance * 1.5);
  controls.target.copy(center);
  camera.near = Math.max(distance / 500, 0.01);
  camera.far = Math.max(distance * 50, 100);
  camera.updateProjectionMatrix();
  controls.update();

  if (axesHelper) {
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    const a = THREE.MathUtils.clamp(maxDim * 0.35, 0.25, 6);
    axesHelper.scale.setScalar(a);
  }
}

function fitCameraToAll(viewDir = null) {
  fitCameraToBounds(computeRenderableSceneBounds(), viewDir);
}

const isMax = ref(false);
const viewOpen = ref(false);

let prevSize = null;
let baseSize = { w: 260, h: 190 };

function stop() {
  if (raf) cancelAnimationFrame(raf);
  raf = 0;
}

function disposeScene(obj) {
  if (!obj) return;
  obj.traverse((n) => {
    if (n.geometry) n.geometry.dispose?.();
    if (n.material) {
      const mats = Array.isArray(n.material) ? n.material : [n.material];
      for (const m of mats) {
        m.map?.dispose?.();
        m.normalMap?.dispose?.();
        m.roughnessMap?.dispose?.();
        m.metalnessMap?.dispose?.();
        m.aoMap?.dispose?.();
        m.emissiveMap?.dispose?.();
        m.alphaMap?.dispose?.();
        m.dispose?.();
      }
    }
  });
}

function resizeToHost() {
  if (!renderer || !camera || !hostEl.value) return;
  const r = hostEl.value.getBoundingClientRect();
  const w = Math.max(1, Math.floor(r.width));
  const h = Math.max(1, Math.floor(r.height));
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

function setWidgetSizePx(w, h) {
  if (!widgetEl.value) return;
  widgetEl.value.style.width = `${Math.round(w)}px`;
  widgetEl.value.style.height = `${Math.round(h)}px`;
}

function getWidgetSizePx() {
  if (!widgetEl.value) return { w: 260, h: 190 };
  const r = widgetEl.value.getBoundingClientRect();
  return { w: r.width, h: r.height };
}

function getMaxSizePx() {
  const pad = 12;
  const parent = widgetEl.value?.offsetParent;
  if (!parent) return { w: 520, h: 420 };
  const r = parent.getBoundingClientRect();
  let rightLimit = r.right - pad;

  const blockers = [
    document.querySelector(".subRail"),
    document.querySelector(".menuPanel"),
    document.querySelector(".toolDock"),
  ].filter(Boolean);

  for (const el of blockers) {
    const b = el.getBoundingClientRect();
    const overlapsY = b.bottom > r.top && b.top < r.bottom;
    if (!overlapsY) continue;
    if (b.left > r.left + pad && b.left < rightLimit) {
      rightLimit = b.left - pad;
    }
  }

  const maxW = Math.max(180, rightLimit - (r.left + pad));
  const maxH = Math.max(130, r.height - pad * 2);
  return { w: maxW, h: maxH };
}

function goSmall() {
  viewOpen.value = false;
  isMax.value = false;
  setWidgetSizePx(baseSize.w, baseSize.h);
}

function goMax() {
  if (isMax.value) return;
  prevSize = getWidgetSizePx();
  isMax.value = true;
  viewOpen.value = false;
  const mx = getMaxSizePx();
  setWidgetSizePx(mx.w, mx.h);
}

function setViewDir(dx, dy, dz) {
  if (!camera || !controls) return;
  const v = new THREE.Vector3(dx, dy, dz).normalize();
  fitCameraToAll(v);
}

function onCanvasDoubleClick() {
  fitCameraToAll();
}

function toggleViewMenu() {
  viewOpen.value = !viewOpen.value;
}

async function loadGlb(url) {
  const loader = new GLTFLoader();
  const gltf = await loader.loadAsync(url);
  return gltf;
}

function applyModel2dTransformTo3d(transform) {
  if (!modelRoot || !modelBasePosition) return;

  const xMm = Number.isFinite(transform?.x) ? transform.x : 0;
  const yMm = Number.isFinite(transform?.y) ? transform.y : 0;
  const rotRad = Number.isFinite(transform?.rotRad) ? transform.rotRad : 0;
  const mPerMm = 0.001;

  modelRoot.position.set(
    modelBasePosition.x + xMm * mPerMm,
    modelBasePosition.y,
    modelBasePosition.z - yMm * mPerMm
  );
  modelRoot.rotation.y = modelBaseRotationY + rotRad;
}

watch(
  () => props.model2dTransform,
  (t) => {
    applyModel2dTransformTo3d(t);
  },
  { immediate: true }
);

watch(
  () => props.walls2d,
  (snap) => {
    rebuildWalls3d(snap);
  },
  { immediate: true, deep: true }
);

watch(
  () => [props.walls2d?.state?.axisXColor, props.walls2d?.state?.axisYColor, props.walls2d?.state?.axisZColor],
  () => {
    applyAxesHelperColors();
  },
  { immediate: true }
);

function projectModelTo2DLines(root) {
  if (!root) return [];
  root.updateMatrixWorld(true);

  const mmPerUnit = 1000;

  const uniq = new Map();
  const tmpA = new THREE.Vector3();
  const tmpB = new THREE.Vector3();
  const tmpAw = new THREE.Vector3();
  const tmpBw = new THREE.Vector3();

  const maxSeg = 12000;

  root.traverse((obj) => {
    if (!obj || !obj.isMesh || !obj.geometry) return;
    const geom = obj.geometry;
        const edges = new THREE.EdgesGeometry(geom, 15);
    const pos = edges.attributes?.position;
    if (!pos || !pos.array) return;

    const arr = pos.array;
    const m = obj.matrixWorld;
    for (let i = 0; i + 5 < arr.length; i += 6) {
      tmpA.set(arr[i + 0], arr[i + 1], arr[i + 2]);
      tmpB.set(arr[i + 3], arr[i + 4], arr[i + 5]);
      tmpAw.copy(tmpA).applyMatrix4(m);
      tmpBw.copy(tmpB).applyMatrix4(m);

      const ax = Math.round(tmpAw.x * mmPerUnit);
      const ay = Math.round(-tmpAw.z * mmPerUnit);
      const bx = Math.round(tmpBw.x * mmPerUnit);
      const by = Math.round(-tmpBw.z * mmPerUnit);

      if (ax === bx && ay === by) continue;

      let x1 = ax,
        y1 = ay,
        x2 = bx,
        y2 = by;
      if (x1 > x2 || (x1 === x2 && y1 > y2)) {
        x1 = bx;
        y1 = by;
        x2 = ax;
        y2 = ay;
      }
      const key = `${x1},${y1},${x2},${y2}`;
      if (!uniq.has(key)) {
        uniq.set(key, { ax: x1, ay: y1, bx: x2, by: y2 });
        if (uniq.size >= maxSeg) break;
      }
    }
  });

  return Array.from(uniq.values());
}

onMounted(async () => {
  const canvas = canvasEl.value;
  const host = hostEl.value;
  if (!canvas || !host) return;

  renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
    preserveDrawingBuffer: false,
  });
  renderer.setPixelRatio(Math.min(2, window.devicePixelRatio || 1));

  scene = new THREE.Scene();
  scene.background = null;

  // ✅ محورهای X/Y/Z
  axesHelper = createPlanAlignedAxesHelper(1);
  applyAxesHelperColors();
  scene.add(axesHelper);

  camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  camera.position.set(2.2, 1.6, 2.2);

  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.rotateSpeed = 0.7;
  controls.zoomSpeed = 0.9;
  controls.panSpeed = 0.7;
  controls.screenSpacePanning = true;

  const hemi = new THREE.HemisphereLight(0xffffff, 0x334155, 1.0);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 0.9);
  dir.position.set(3, 6, 4);
  scene.add(dir);

  rebuildWalls3d(props.walls2d);

  try {
    const gltf = await loadGlb(props.src);
    const root = gltf.scene || gltf.scenes?.[0];
    if (root) {
      modelRoot = root;
      modelBasePosition = root.position.clone();
      modelBaseRotationY = root.rotation.y || 0;
      scene.add(root);
      applyModel2dTransformTo3d(props.model2dTransform);

      try {
        const lines = projectModelTo2DLines(root);
        emit("model2d", {
          lines,
          opts: { color: "#8a98a3", lineWidthPx: 1, dash: [4, 7], alpha: 0.5 },
        });
      } catch (_) {}

      fitCameraToAll();
    }
  } catch (_) {
    // ignore
  }

  baseSize = getWidgetSizePx();

  resizeToHost();
  ro = new ResizeObserver(() => {
    resizeToHost();
  });
  ro.observe(host);

  widgetRo = new ResizeObserver(() => {
    resizeToHost();
  });
  widgetRo.observe(widgetEl.value);

  canvas.addEventListener("dblclick", onCanvasDoubleClick);

  const loop = () => {
    raf = requestAnimationFrame(loop);
    controls?.update?.();
    renderer?.render(scene, camera);
  };
  loop();
});

onBeforeUnmount(() => {
  stop();
  canvasEl.value?.removeEventListener?.("dblclick", onCanvasDoubleClick);
  if (ro) ro.disconnect();
  ro = null;
  if (widgetRo) widgetRo.disconnect();
  widgetRo = null;

  try {
    controls?.dispose?.();
  } catch (_) {
    // no-op
  }
  controls = null;

  try {
    disposeScene(scene);
  } catch (_) {
    // no-op
  }

  try {
    renderer?.dispose?.();
  } catch (_) {
    // no-op
  }

  renderer = null;
  scene = null;
  camera = null;
  modelRoot = null;
  modelBasePosition = null;
  clearWalls3d();

  try {
    axesHelper?.removeFromParent?.();
  } catch (_) {
    // no-op
  }
  axesHelper = null;
});

</script>

<template>
  <div ref="widgetEl" class="glbWidget" :class="{ 'is-max': isMax }" @mouseenter="$emit('mouseenter')" @mouseleave="$emit('mouseleave')">
    <div class="glbWidget__head" dir="rtl">
      <div class="glbWidget__headBtns">
        <button type="button" class="glbWidget__btn" title="کوچک" @click="goSmall">–</button>
        <button type="button" class="glbWidget__btn" title="بزرگ" @click="goMax">□</button>
      </div>
      <div ref="hostEl" class="glbWidget__host">
        <canvas ref="canvasEl" class="glbWidget__canvas"></canvas>

        <div class="glbWidget__view" @mouseenter.stop @mouseleave.stop>
          <button type="button" class="glbWidget__viewBtn" title="نما" @click="toggleViewMenu">
            <img class="glbWidget__viewIcon" src="/icons/viewpoint.png" alt="" />
          </button>
          <div v-if="viewOpen" class="glbWidget__viewMenu">
            <button class="glbWidget__viewItem" type="button" @click="setViewDir(0, 0, 1)">روبه‌رو</button>
            <button class="glbWidget__viewItem" type="button" @click="setViewDir(0, 0, -1)">پشت</button>
            <button class="glbWidget__viewItem" type="button" @click="setViewDir(1, 0, 0)">راست</button>
            <button class="glbWidget__viewItem" type="button" @click="setViewDir(-1, 0, 0)">چپ</button>
            <button class="glbWidget__viewItem" type="button" @click="setViewDir(0, 1, 0)">بالا</button>
            <button class="glbWidget__viewItem" type="button" @click="setViewDir(0, -1, 0)">پایین</button>
            <div class="glbWidget__viewSep"></div>
            <button class="glbWidget__viewItem" type="button" @click="setViewDir(1, 1, 1)">ایزو NE</button>
            <button class="glbWidget__viewItem" type="button" @click="setViewDir(-1, 1, 1)">ایزو NW</button>
            <button class="glbWidget__viewItem" type="button" @click="setViewDir(1, 1, -1)">ایزو SE</button>
            <button class="glbWidget__viewItem" type="button" @click="setViewDir(-1, 1, -1)">ایزو SW</button>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div class="glbWallAttrs glbWallAttrs--panel" dir="rtl" @mouseenter="$emit('mouseenter')" @mouseleave="$emit('mouseleave')">
    <div class="glbWallAttrs__head">
      <div class="menuPanel__title glbWallAttrs__title">صفات</div>
      <div v-if="isGroupEditMode" class="glbWallAttrs__groupLabel">ویرایش گروهی</div>
    </div>
    <div class="glbWallAttrs__sep"></div>

    <template v-if="wallMetrics">
      <div v-if="selectedObjectTitle" class="glbWallAttrs__objectTitle">{{ selectedObjectTitle }}</div>
      <div class="glbWallAttrs__editor glbWallAttrs__editor--attrs">
        <label class="glbWallAttrs__editRow">
          <span>طول (cm)</span>
          <input
            class="glbWallAttrs__input"
            type="number"
            min="1"
            step="0.1"
            :value="isGroupEditMode ? '' : wallMetrics.lengthCm"
            :disabled="isGroupEditMode"
            @input="patchWallStyleDraft({ lengthCm: +$event.target.value })"
          />
        </label>
        <label v-if="showThicknessField" class="glbWallAttrs__editRow">
          <span>ضخامت (cm)</span>
          <input
            class="glbWallAttrs__input"
            type="number"
            min="0.1"
            step="0.5"
            :value="wallStyleDraft.thicknessCm"
            @input="patchWallStyleDraft({ thicknessCm: +$event.target.value })"
          />
        </label>
        <label v-if="showHeightField" class="glbWallAttrs__editRow">
          <span>ارتفاع (cm)</span>
          <input
            class="glbWallAttrs__input"
            type="number"
            min="1"
            step="1"
            :value="wallStyleDraft.heightCm"
            @input="patchWallStyleDraft({ heightCm: +$event.target.value })"
          />
        </label>
        <label v-if="showFloorDistanceField" class="glbWallAttrs__editRow">
          <span>فاصله از کف (cm)</span>
          <input
            class="glbWallAttrs__input"
            type="number"
            min="0"
            step="0.1"
            :value="wallStyleDraft.floorOffsetCm"
            @input="patchWallStyleDraft({ floorOffsetCm: +$event.target.value })"
          />
        </label>
        <label v-if="showThicknessField" class="glbWallAttrs__editRow">
          <span>{{ colorFieldLabel }}</span>
          <input
            class="glbWallAttrs__color"
            type="color"
            :value="wallStyleDraft.color"
            @input="patchWallStyleDraft({ color: $event.target.value })"
          />
        </label>
        <label v-if="showFloorOffsetField" class="glbWallAttrs__editRow">
          <span>کف‌افست (cm)</span>
          <input
            class="glbWallAttrs__input"
            type="number"
            step="0.1"
            :value="wallStyleDraft.floorOffsetCm"
            @input="patchWallStyleDraft({ floorOffsetCm: +$event.target.value })"
          />
        </label>
      </div>

      <div class="glbWallAttrs__sep"></div>

      <div class="menuPanel__title glbWallAttrs__title glbWallAttrs__title--secondary">مختصات</div>
      <div class="glbWallAttrs__editor">
        <div class="glbWallAttrs__pointTitle">جابجایی محوری</div>
        <div class="glbWallAttrs__editRow glbWallAttrs__axisSingleRow">
          <div class="glbWallAttrs__axisInputWrap">
            <input
              class="glbWallAttrs__input glbWallAttrs__moveInput glbWallAttrs__moveInput--axis"
              type="text"
              inputmode="decimal"
              :disabled="selectedWallCount === 0"
              :value="getCoordFieldValue('moveY', wallMoveDeltaCm.y)"
              @input="setCoordFieldDraft('moveY', $event.target.value)"
              @blur="commitMoveDeltaInput('y', 'moveY')"
              @keydown.enter.prevent="commitMoveDeltaInput('y', 'moveY'); moveWallByAxis('y')"
            />
            <span class="glbWallAttrs__axisTag" :style="axisTagStyles.y">Y</span>
          </div>
          <div class="glbWallAttrs__axisInputWrap">
            <input
              class="glbWallAttrs__input glbWallAttrs__moveInput glbWallAttrs__moveInput--axis"
              type="text"
              inputmode="decimal"
              :disabled="selectedWallCount === 0"
              :value="getCoordFieldValue('moveX', wallMoveDeltaCm.x)"
              @input="setCoordFieldDraft('moveX', $event.target.value)"
              @blur="commitMoveDeltaInput('x', 'moveX')"
              @keydown.enter.prevent="commitMoveDeltaInput('x', 'moveX'); moveWallByAxis('x')"
            />
            <span class="glbWallAttrs__axisTag" :style="axisTagStyles.x">X</span>
          </div>
        </div>

        <div class="glbWallAttrs__pointTitle">نقطه مرکز</div>
        <div class="glbWallAttrs__editRow">
          <div class="glbWallAttrs__coordGrid">
            <input
              class="glbWallAttrs__input"
              type="text"
              inputmode="decimal"
              :value="getCoordFieldValue('centerX', isGroupEditMode ? '' : wallCoordPoints?.center?.x)"
              :disabled="isGroupEditMode || !wallCoordPoints"
              @input="setCoordFieldDraft('centerX', $event.target.value)"
              @blur="commitCenterCoordInput('x', 'centerX')"
              @keydown.enter.prevent="commitCenterCoordInput('x', 'centerX')"
            />
            <input
              class="glbWallAttrs__input"
              type="text"
              inputmode="decimal"
              :value="getCoordFieldValue('centerY', isGroupEditMode ? '' : wallCoordPoints?.center?.y)"
              :disabled="isGroupEditMode || !wallCoordPoints"
              @input="setCoordFieldDraft('centerY', $event.target.value)"
              @blur="commitCenterCoordInput('y', 'centerY')"
              @keydown.enter.prevent="commitCenterCoordInput('y', 'centerY')"
            />
          </div>
        </div>

        <div class="glbWallAttrs__pointTitle">نقطه پایین چپ</div>
        <div class="glbWallAttrs__editRow">
          <div class="glbWallAttrs__coordGrid">
            <input
              class="glbWallAttrs__input"
              type="text"
              inputmode="decimal"
              :value="getCoordFieldValue('blX', isGroupEditMode ? '' : wallCoordPoints?.bottomLeft?.x)"
              :disabled="isGroupEditMode || !wallCoordPoints"
              @input="setCoordFieldDraft('blX', $event.target.value)"
              @blur="commitPointCoordInput(wallCoordPoints.bottomLeftKey, 'x', 'blX')"
              @keydown.enter.prevent="commitPointCoordInput(wallCoordPoints.bottomLeftKey, 'x', 'blX')"
            />
            <input
              class="glbWallAttrs__input"
              type="text"
              inputmode="decimal"
              :value="getCoordFieldValue('blY', isGroupEditMode ? '' : wallCoordPoints?.bottomLeft?.y)"
              :disabled="isGroupEditMode || !wallCoordPoints"
              @input="setCoordFieldDraft('blY', $event.target.value)"
              @blur="commitPointCoordInput(wallCoordPoints.bottomLeftKey, 'y', 'blY')"
              @keydown.enter.prevent="commitPointCoordInput(wallCoordPoints.bottomLeftKey, 'y', 'blY')"
            />
          </div>
        </div>

        <div class="glbWallAttrs__pointTitle">نقطه بالا راست</div>
        <div class="glbWallAttrs__editRow">
          <div class="glbWallAttrs__coordGrid">
            <input
              class="glbWallAttrs__input"
              type="text"
              inputmode="decimal"
              :value="getCoordFieldValue('trX', isGroupEditMode ? '' : wallCoordPoints?.topRight?.x)"
              :disabled="isGroupEditMode || !wallCoordPoints"
              @input="setCoordFieldDraft('trX', $event.target.value)"
              @blur="commitPointCoordInput(wallCoordPoints.topRightKey, 'x', 'trX')"
              @keydown.enter.prevent="commitPointCoordInput(wallCoordPoints.topRightKey, 'x', 'trX')"
            />
            <input
              class="glbWallAttrs__input"
              type="text"
              inputmode="decimal"
              :value="getCoordFieldValue('trY', isGroupEditMode ? '' : wallCoordPoints?.topRight?.y)"
              :disabled="isGroupEditMode || !wallCoordPoints"
              @input="setCoordFieldDraft('trY', $event.target.value)"
              @blur="commitPointCoordInput(wallCoordPoints.topRightKey, 'y', 'trY')"
              @keydown.enter.prevent="commitPointCoordInput(wallCoordPoints.topRightKey, 'y', 'trY')"
            />
          </div>
        </div>
      </div>
    </template>

    <div v-else class="menuPanel__hint glbWallAttrs__hint--soft">ترسیم خود را انتخاب نمایید</div>
  </div>
</template>
