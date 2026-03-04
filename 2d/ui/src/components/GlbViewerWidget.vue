<script setup>
import { onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";

const props = defineProps({
  src: { type: String, required: true },
  model2dTransform: {
    type: Object,
    default: () => ({ x: 0, y: 0 }),
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
let wallsRoot = null;

let axesHelper = null;

const DEFAULT_WALL_HEIGHT_M = 2.8;

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

  for (const w of walls) {
    const a = byId.get(w.a);
    const b = byId.get(w.b);
    if (!a || !b) continue;

    const dx = (b.x - a.x) * 0.001;
    const dz = -(b.y - a.y) * 0.001;
    const length = Math.hypot(dx, dz);
    if (!Number.isFinite(length) || length <= 0.001) continue;

    const thicknessM = Math.max(0.02, (Number(w.thickness) || 120) * 0.001);
    const g = new THREE.BoxGeometry(length, DEFAULT_WALL_HEIGHT_M, thicknessM);
    const mesh = new THREE.Mesh(g, wallMat.clone());

    const midX = ((a.x + b.x) * 0.5) * 0.001;
    const midZ = -((a.y + b.y) * 0.5) * 0.001;
    mesh.position.set(midX, DEFAULT_WALL_HEIGHT_M * 0.5, midZ);
    mesh.rotation.y = Math.atan2(dz, dx);
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
  const mPerMm = 0.001;

  modelRoot.position.set(
    modelBasePosition.x + xMm * mPerMm,
    modelBasePosition.y,
    modelBasePosition.z - yMm * mPerMm
  );
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