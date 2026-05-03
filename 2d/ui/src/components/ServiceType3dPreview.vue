<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { LineMaterial } from "three/examples/jsm/lines/LineMaterial.js";
import { LineSegments2 } from "three/examples/jsm/lines/LineSegments2.js";
import { LineSegmentsGeometry } from "three/examples/jsm/lines/LineSegmentsGeometry.js";
import { mergeVertices } from "three/examples/jsm/utils/BufferGeometryUtils.js";
import { CSG } from "three-csg-ts";

const props = defineProps({
  scene: {
    type: Object,
    default: null,
  },
});

const hostEl = ref(null);
const canvasEl = ref(null);

let renderer = null;
let scene3d = null;
let camera = null;
let controls = null;
let animationFrameId = 0;
let resizeObserver = null;
let previewRoot = null;

const PREVIEW_EDGE_WIDTH_PX = 0.55;
const PREVIEW_EDGE_OPACITY = 0.68;
const PREVIEW_EDGE_COLOR = "#2F2F2F";

const hasRenderableScene = computed(() => {
  const source = props.scene || {};
  return Number(source?.part?.width) > 0 && Number(source?.part?.length) > 0 && Number(source?.part?.thickness) > 0;
});

function disposeMaterial(material) {
  if (!material) return;
  if (Array.isArray(material)) {
    material.forEach(disposeMaterial);
    return;
  }
  material.dispose?.();
}

function clearPreviewRoot() {
  if (!previewRoot || !scene3d) return;
  previewRoot.traverse((child) => {
    child.geometry?.dispose?.();
    disposeMaterial(child.material);
  });
  scene3d.remove(previewRoot);
  previewRoot = null;
}

function mmToM(value) {
  return (Number(value) || 0) * 0.001;
}

function getRendererViewportSize() {
  if (!renderer || !hostEl.value) return new THREE.Vector2(1, 1);
  const rect = hostEl.value.getBoundingClientRect();
  return new THREE.Vector2(
    Math.max(1, Math.floor(rect.width)),
    Math.max(1, Math.floor(rect.height))
  );
}

function buildProfileShape(points) {
  const pts = (Array.isArray(points) ? points : [])
    .map((point) => ({
      x: mmToM(point?.x),
      y: mmToM(point?.y),
    }));
  if (pts.length < 3) return null;
  const shape = new THREE.Shape();
  shape.moveTo(pts[0].x, pts[0].y);
  for (let index = 1; index < pts.length; index += 1) {
    shape.lineTo(pts[index].x, pts[index].y);
  }
  shape.closePath();
  return shape;
}

function createPartMesh(part) {
  const geometry = new THREE.BoxGeometry(mmToM(part.width), mmToM(part.thickness), mmToM(part.length));
  const material = new THREE.MeshStandardMaterial({
    color: "#d7eff0",
    metalness: 0.08,
    roughness: 0.62,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.updateMatrix();
  return mesh;
}

function createStyledLineSegments(featureSegments) {
  if (!Array.isArray(featureSegments) || !featureSegments.length) return null;
  const lineGeometry = new LineSegmentsGeometry();
  lineGeometry.setPositions(featureSegments);
  const lineMaterial = new LineMaterial({
    color: new THREE.Color(PREVIEW_EDGE_COLOR),
    transparent: true,
    opacity: PREVIEW_EDGE_OPACITY,
    linewidth: PREVIEW_EDGE_WIDTH_PX,
    worldUnits: false,
    depthTest: true,
    depthWrite: false,
  });
  lineMaterial.resolution.copy(getRendererViewportSize());
  const edgeLines = new LineSegments2(lineGeometry, lineMaterial);
  edgeLines.userData.isPreviewEdge = true;
  return edgeLines;
}

function createPartEdgeLines(part) {
  const geometry = new THREE.BoxGeometry(mmToM(part.width), mmToM(part.thickness), mmToM(part.length));
  const edges = new THREE.EdgesGeometry(geometry, 1);
  geometry.dispose();
  const pos = edges.getAttribute?.("position");
  const featureSegments = pos?.array ? Array.from(pos.array) : [];
  edges.dispose();
  return createStyledLineSegments(featureSegments);
}

function createOpeningOutline(sceneInput) {
  const cutter = sceneInput?.cutter || {};
  if (!cutter.hasVisibleSubtraction || cutter.workingDiameter <= 0 || cutter.workingDepth <= 0) return null;
  const part = sceneInput?.part || {};
  const widthM = mmToM(part.width);
  const thicknessM = mmToM(part.thickness);
  const lengthM = mmToM(part.length);
  const x0 = (-widthM * 0.5) + mmToM(cutter.axisAligned);
  const y0 = (-thicknessM * 0.5) + mmToM(cutter.axisOpposite);
  const z0 = (-lengthM * 0.5) + mmToM(cutter.axisOpposite);
  const segments = [];

  const addLoop = (points) => {
    if (!Array.isArray(points) || points.length < 2) return;
    for (let i = 0; i < points.length; i += 1) {
      const start = points[i];
      const end = points[(i + 1) % points.length];
      segments.push(start.x, start.y, start.z, end.x, end.y, end.z);
    }
  };

  if (cutter.shape === "circle") {
    const radius = Math.max(0.0005, mmToM(cutter.workingDiameter) * 0.5);
    const steps = 48;
    const points = [];
    for (let i = 0; i < steps; i += 1) {
      const angle = (i / steps) * Math.PI * 2;
      const cos = Math.cos(angle) * radius;
      const sin = Math.sin(angle) * radius;
      if (cutter.serviceLocation === "thickness") {
        points.push(new THREE.Vector3(x0 + cos, y0 + sin, lengthM * 0.5));
      } else {
        const faceY = cutter.serviceLocation === "back" ? -thicknessM * 0.5 : thicknessM * 0.5;
        points.push(new THREE.Vector3(x0 + cos, faceY, z0 + sin));
      }
    }
    addLoop(points);
    return createStyledLineSegments(segments);
  }

  const profilePoints = Array.isArray(cutter.profilePoints) ? cutter.profilePoints : [];
  const points = profilePoints.map((point) => {
    const px = x0 + mmToM(point?.x);
    if (cutter.serviceLocation === "thickness") {
      return new THREE.Vector3(px, y0 + mmToM(point?.y), lengthM * 0.5);
    }
    const faceY = cutter.serviceLocation === "back" ? -thicknessM * 0.5 : thicknessM * 0.5;
    return new THREE.Vector3(px, faceY, z0 + mmToM(point?.y));
  });
  addLoop(points);
  return createStyledLineSegments(segments);
}

function createCircleCutter(sceneInput) {
  const cutter = sceneInput?.cutter || {};
  const radius = Math.max(0.0005, mmToM(cutter.workingDiameter) * 0.5);
  const depth = Math.max(0.0005, mmToM(cutter.workingDepth));
  const part = sceneInput?.part || {};
  const widthM = mmToM(part.width);
  const thicknessM = mmToM(part.thickness);
  const lengthM = mmToM(part.length);
  const x = (-widthM * 0.5) + mmToM(cutter.axisAligned);
  const oppositeM = mmToM(cutter.axisOpposite);
  const geometry = new THREE.CylinderGeometry(radius, radius, depth + 0.0002, 48);
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: "#fb923c" }));
  if (cutter.serviceLocation === "thickness") {
    const y = (-thicknessM * 0.5) + oppositeM;
    const z = (lengthM * 0.5) - (depth * 0.5);
    mesh.rotation.x = Math.PI * 0.5;
    mesh.position.set(x, y, z);
  } else {
    const z = (-lengthM * 0.5) + oppositeM;
    const y = cutter.serviceLocation === "back"
      ? (-thicknessM * 0.5) + (depth * 0.5)
      : (thicknessM * 0.5) - (depth * 0.5);
    mesh.position.set(x, y, z);
  }
  mesh.updateMatrix();
  return mesh;
}

function createProfileCutter(sceneInput) {
  const cutter = sceneInput?.cutter || {};
  const depth = Math.max(0.0005, mmToM(cutter.workingDepth));
  const part = sceneInput?.part || {};
  const widthM = mmToM(part.width);
  const thicknessM = mmToM(part.thickness);
  const lengthM = mmToM(part.length);
  const x = (-widthM * 0.5) + mmToM(cutter.axisAligned);
  const oppositeM = mmToM(cutter.axisOpposite);
  const shape = buildProfileShape(cutter.profilePoints);
  if (!shape) return null;
  const geometry = new THREE.ExtrudeGeometry(shape, {
    depth,
    bevelEnabled: false,
    curveSegments: 24,
    steps: 1,
  });
  geometry.computeVertexNormals();
  const mesh = new THREE.Mesh(geometry, new THREE.MeshStandardMaterial({ color: "#fb923c" }));
  if (cutter.serviceLocation === "thickness") {
    const y = (-thicknessM * 0.5) + oppositeM;
    const z = (lengthM * 0.5) - depth;
    mesh.position.set(x, y, z);
  } else {
    const z = (-lengthM * 0.5) + oppositeM;
    if (cutter.serviceLocation === "back") {
      mesh.rotation.x = -Math.PI * 0.5;
      mesh.position.set(x, -thicknessM * 0.5, z);
    } else {
      mesh.rotation.x = Math.PI * 0.5;
      mesh.position.set(x, thicknessM * 0.5, z);
    }
  }
  mesh.updateMatrix();
  return mesh;
}

function createCutterMesh(sceneInput) {
  const cutter = sceneInput?.cutter || {};
  if (!cutter.hasVisibleSubtraction || cutter.workingDiameter <= 0 || cutter.workingDepth <= 0) return null;
  if (cutter.shape === "circle") return createCircleCutter(sceneInput);
  return createProfileCutter(sceneInput);
}

function cleanupBooleanResultGeometry(sourceGeometry) {
  if (!sourceGeometry) return null;
  let geometry = sourceGeometry.clone();
  if (typeof geometry.toNonIndexed === "function" && geometry.index) {
    geometry = geometry.toNonIndexed();
  }
  try {
    geometry = mergeVertices(geometry, 1e-5);
  } catch (_) {
    // Ignore merge failures and keep the raw geometry as fallback.
  }
  geometry.computeVertexNormals();
  geometry.computeBoundingBox?.();
  geometry.computeBoundingSphere?.();
  return geometry;
}

function buildPreviewGroup(sceneInput) {
  const group = new THREE.Group();
  const baseMesh = createPartMesh(sceneInput.part);
  let renderMesh = baseMesh;
  const cutterMesh = createCutterMesh(sceneInput);
  if (cutterMesh) {
    try {
      renderMesh = CSG.subtract(baseMesh, cutterMesh);
      const cleanedGeometry = cleanupBooleanResultGeometry(renderMesh.geometry);
      if (cleanedGeometry) {
        renderMesh.geometry.dispose?.();
        renderMesh.geometry = cleanedGeometry;
      }
      renderMesh.material = new THREE.MeshStandardMaterial({
        color: "#d7eff0",
        metalness: 0.08,
        roughness: 0.62,
      });
      renderMesh.updateMatrix();
      baseMesh.geometry.dispose();
      disposeMaterial(baseMesh.material);
      cutterMesh.geometry.dispose();
      disposeMaterial(cutterMesh.material);
    } catch (_) {
      renderMesh = baseMesh;
    }
  }
  group.add(renderMesh);
  const partEdgeLines = createPartEdgeLines(sceneInput.part);
  if (partEdgeLines) group.add(partEdgeLines);
  const openingOutline = createOpeningOutline(sceneInput);
  if (openingOutline) group.add(openingOutline);

  return group;
}

function syncPreviewEdgeResolution() {
  if (!previewRoot) return;
  const resolution = getRendererViewportSize();
  previewRoot.traverse((obj) => {
    if (!obj?.userData?.isPreviewEdge) return;
    const material = obj.material;
    if (!material?.resolution) return;
    material.resolution.copy(resolution);
    material.needsUpdate = true;
  });
}

function fitCameraToObject(target) {
  if (!camera || !controls || !target) return;
  const bounds = new THREE.Box3().setFromObject(target);
  if (bounds.isEmpty()) return;
  const size = bounds.getSize(new THREE.Vector3());
  const center = bounds.getCenter(new THREE.Vector3());
  const maxDim = Math.max(size.x, size.y, size.z, 0.001);
  const distance = Math.max(0.42, maxDim * 2.2);
  camera.position.copy(center).add(new THREE.Vector3(1, 0.9, 1.25).normalize().multiplyScalar(distance));
  camera.near = Math.max(0.001, distance / 100);
  camera.far = Math.max(10, distance * 20);
  camera.updateProjectionMatrix();
  controls.target.copy(center);
  controls.update();
}

function rebuildScene() {
  if (!scene3d) return;
  clearPreviewRoot();
  if (!hasRenderableScene.value || !props.scene) return;
  previewRoot = buildPreviewGroup(props.scene);
  scene3d.add(previewRoot);
  fitCameraToObject(previewRoot);
}

function resizeRenderer() {
  const host = hostEl.value;
  const canvas = canvasEl.value;
  if (!host || !canvas || !renderer || !camera) return;
  const width = Math.max(180, Math.round(host.clientWidth || 0));
  const height = Math.max(180, Math.round(host.clientHeight || 0));
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(width, height, false);
  camera.aspect = width / Math.max(1, height);
  camera.updateProjectionMatrix();
  syncPreviewEdgeResolution();
}

function animate() {
  animationFrameId = window.requestAnimationFrame(animate);
  controls?.update?.();
  renderer?.render?.(scene3d, camera);
}

onMounted(() => {
  const canvas = canvasEl.value;
  const host = hostEl.value;
  if (!canvas || !host) return;
  renderer = new THREE.WebGLRenderer({
    canvas,
    antialias: true,
    alpha: true,
  });
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.setClearColor(0xffffff, 0);

  scene3d = new THREE.Scene();
  camera = new THREE.PerspectiveCamera(34, 1, 0.001, 100);

  const ambient = new THREE.HemisphereLight(0xffffff, 0xdbeafe, 1.05);
  scene3d.add(ambient);

  const key = new THREE.DirectionalLight(0xffffff, 1.15);
  key.position.set(2.4, 3.2, 2.1);
  scene3d.add(key);

  const fill = new THREE.DirectionalLight(0xffffff, 0.55);
  fill.position.set(-2, 1.5, -1.8);
  scene3d.add(fill);

  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.06;
  controls.rotateSpeed = 0.9;
  controls.zoomSpeed = 0.95;
  controls.panSpeed = 0.8;
  controls.screenSpacePanning = true;
  controls.minDistance = 0.08;
  controls.maxDistance = 6;

  resizeRenderer();
  rebuildScene();
  animate();

  resizeObserver = new ResizeObserver(() => {
    resizeRenderer();
    if (previewRoot) fitCameraToObject(previewRoot);
  });
  resizeObserver.observe(host);
});

watch(
  () => props.scene,
  () => {
    rebuildScene();
  },
  { deep: true }
);

onBeforeUnmount(() => {
  if (animationFrameId) window.cancelAnimationFrame(animationFrameId);
  resizeObserver?.disconnect?.();
  clearPreviewRoot();
  controls?.dispose?.();
  renderer?.dispose?.();
  scene3d = null;
  camera = null;
  controls = null;
  renderer = null;
});
</script>

<template>
  <div ref="hostEl" class="serviceType3dPreview">
    <canvas ref="canvasEl" class="serviceType3dPreview__canvas"></canvas>
  </div>
</template>

<style scoped>
.serviceType3dPreview {
  position: relative;
  width: 100%;
  min-height: 200px;
  border-radius: 14px;
  overflow: hidden;
  background:
    radial-gradient(circle at top left, rgba(20, 184, 166, 0.12), transparent 34%),
    linear-gradient(180deg, rgba(255, 255, 255, 0.96), rgba(248, 250, 252, 0.94));
}

.serviceType3dPreview__canvas {
  width: 100%;
  height: 100%;
  display: block;
  min-height: 200px;
}
</style>
