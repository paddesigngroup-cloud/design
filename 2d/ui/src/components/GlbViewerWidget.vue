<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
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
});

const emit = defineEmits(["mouseenter", "mouseleave", "model2d"]);

const widgetEl = ref(null);
const hostEl = ref(null);
const canvasEl = ref(null);

let renderer = null;
let scene = null;
let camera = null;
let controls = null;
let raf = 0;
let ro = null;
let modelRoot = null;
let modelBasePosition = null;
let modelBaseRotationY = 0;
let wallsRoot = null;

let axesHelper = null;

const DEFAULT_WALL_HEIGHT_M = 2.8;
const DEFAULT_MITER_LIMIT = 10;

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

function rebuildWalls3d(snapshot) {
  if (!scene) return;
  clearWalls3d();

  const nodes = Array.isArray(snapshot?.nodes) ? snapshot.nodes : [];
  const walls = Array.isArray(snapshot?.walls) ? snapshot.walls : [];
  if (!nodes.length || !walls.length) return;

  const byId = new Map(nodes.map((n) => [n.id, n]));
  const root = new THREE.Group();
  root.name = "walls2d-extruded";
  const wallMat = new THREE.MeshStandardMaterial({
    color: 0xc7ccd1,
        roughness: 0.86,
    metalness: 0.05,
  });

  const jointGammaMap = buildJointGammaMap(walls, byId);

  for (const w of walls) {
    const corners = computeTrimmedWallCorners(w, byId, jointGammaMap);
    if (!corners) continue;
    const mesh = makeWallExtrudedMesh(corners, DEFAULT_WALL_HEIGHT_M, wallMat.clone());
    root.add(mesh);
  }

  if (!root.children.length) return;
  wallsRoot = root;
  scene.add(root);
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

function toggleMax() {
  if (isMax.value) {
    isMax.value = false;
    if (prevSize) setWidgetSizePx(prevSize.w, prevSize.h);
    return;
  }
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
  axesHelper = new THREE.AxesHelper(1);
  axesHelper.renderOrder = 999;
  axesHelper.traverse((o) => {
    if (!o.material) return;
    o.material.depthTest = false;
    o.material.depthWrite = false;
    o.material.transparent = true;
    o.material.opacity = 0.9;
  });
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
  ro = new ResizeObserver(() => resizeToHost());
  ro.observe(host);
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

  try {
    controls?.dispose?.();
  } catch (_) {}
  controls = null;

  try {
    disposeScene(scene);
  } catch (_) {}

  try {
    renderer?.dispose?.();
  } catch (_) {}

  renderer = null;
  scene = null;
  camera = null;
  modelRoot = null;
  modelBasePosition = null;
  clearWalls3d();

  try {
    axesHelper?.removeFromParent?.();
  } catch (_) {}
  axesHelper = null;
});
</script>

<template>
  <div
    ref="widgetEl"
    class="glbWidget"
    :class="{ 'is-max': isMax }"
    @mouseenter="$emit('mouseenter')"
    @mouseleave="$emit('mouseleave')"
  >
    <div class="glbWidget__head" dir="rtl">
      <div class="glbWidget__headBtns">
        <button type="button" class="glbWidget__btn" title="کوچک" @click="goSmall">–</button>
        <button type="button" class="glbWidget__btn" title="بزرگ" @click="toggleMax">□</button>
      </div>
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
</template>
