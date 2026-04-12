import * as THREE from "three";
import { GLTFLoader } from "three/examples/jsm/loaders/GLTFLoader.js";

export const DEFAULT_DOOR_MODEL_URL = "/door.glb";

const DEFAULT_FALLBACK_BOUNDS_MM = Object.freeze({
  widthMm: 900,
  heightMm: 2070,
  depthMm: 150,
});

let doorModelAssetPromise = null;
let doorModelAssetResolved = null;
const doorModelAssetCache = new Map();

function normalizeBoundsMm(bounds) {
  const normalizeDimension = (value, fallback, min, max) => {
    let next = Number(value);
    if (!Number.isFinite(next) || next <= 0) next = fallback;
    while (next > max * 10) next /= 10;
    if (!Number.isFinite(next) || next < min || next > max) next = fallback;
    return next;
  };
  const widthMm = normalizeDimension(bounds?.widthMm, DEFAULT_FALLBACK_BOUNDS_MM.widthMm, 300, 3000);
  const heightMm = normalizeDimension(bounds?.heightMm, 2070, 1500, 4000);
  const depthMm = normalizeDimension(bounds?.depthMm, DEFAULT_FALLBACK_BOUNDS_MM.depthMm, 20, 500);
  return { widthMm, heightMm, depthMm };
}

function cloneMaterialOrArray(material) {
  if (Array.isArray(material)) return material.map((item) => item?.clone?.() || item);
  return material?.clone?.() || material;
}

function cloneSceneGraph(root) {
  const clone = root.clone(true);
  clone.traverse((obj) => {
    if (obj?.isMesh) {
      obj.material = cloneMaterialOrArray(obj.material);
      obj.castShadow = true;
      obj.receiveShadow = true;
    }
  });
  return clone;
}

function buildNormalizedDoorScene(sourceRoot) {
  const root = cloneSceneGraph(sourceRoot);
  root.updateMatrixWorld(true);
  const box = new THREE.Box3().setFromObject(root);
  const size = new THREE.Vector3();
  const center = new THREE.Vector3();
  box.getSize(size);
  box.getCenter(center);
  root.position.x -= center.x;
  root.position.y -= box.min.y;
  root.position.z -= center.z;
  root.updateMatrixWorld(true);
  return {
    scene: root,
    boundsMm: normalizeBoundsMm({
      widthMm: size.x * 1000,
      heightMm: size.y * 1000,
      depthMm: size.z * 1000,
    }),
  };
}

export function getFallbackDoorModelBoundsMm() {
  return { ...DEFAULT_FALLBACK_BOUNDS_MM };
}

export function peekDoorModelAsset(modelUrl = DEFAULT_DOOR_MODEL_URL) {
  const url = String(modelUrl || DEFAULT_DOOR_MODEL_URL).trim() || DEFAULT_DOOR_MODEL_URL;
  const cached = doorModelAssetCache.get(url)?.resolved
    || (doorModelAssetResolved && doorModelAssetResolved.url === url ? doorModelAssetResolved : null);
  if (!cached) return null;
  return {
    ...cached,
    boundsMm: normalizeBoundsMm(cached.boundsMm),
  };
}

export function cloneDoorModelSceneSync(modelUrl = DEFAULT_DOOR_MODEL_URL) {
  const asset = peekDoorModelAsset(modelUrl);
  if (!asset?.templateScene) return null;
  return {
    scene: cloneSceneGraph(asset.templateScene),
    boundsMm: normalizeBoundsMm(asset.boundsMm),
    url: asset.url,
  };
}

export async function loadDoorModelAsset(modelUrl = DEFAULT_DOOR_MODEL_URL) {
  const url = String(modelUrl || DEFAULT_DOOR_MODEL_URL).trim() || DEFAULT_DOOR_MODEL_URL;
  const cached = doorModelAssetCache.get(url);
  if (cached?.resolved) {
    return {
      ...cached.resolved,
      boundsMm: normalizeBoundsMm(cached.resolved.boundsMm),
    };
  }
  if (cached?.promise) return cached.promise;
  const nextPromise = (async () => {
    const loader = new GLTFLoader();
    const gltf = await loader.loadAsync(url);
    const sourceRoot = gltf?.scene || gltf?.scenes?.[0];
    if (!sourceRoot) throw new Error("door-model-scene-missing");
    const normalized = buildNormalizedDoorScene(sourceRoot);
    const resolved = {
      url,
      templateScene: normalized.scene,
      boundsMm: normalizeBoundsMm(normalized.boundsMm),
    };
    doorModelAssetResolved = resolved;
    doorModelAssetCache.set(url, {
      promise: null,
      resolved,
    });
    return {
      ...resolved,
      boundsMm: normalizeBoundsMm(resolved.boundsMm),
    };
  })();
  doorModelAssetPromise = nextPromise;
  doorModelAssetCache.set(url, {
    promise: nextPromise,
    resolved: null,
  });
  try {
    return await nextPromise;
  } finally {
    const latest = doorModelAssetCache.get(url);
    if (latest && latest.promise === nextPromise) {
      doorModelAssetCache.set(url, {
        promise: null,
        resolved: latest.resolved,
      });
    }
    if (doorModelAssetPromise === nextPromise) doorModelAssetPromise = null;
  }
}

export async function getDoorModelBoundsMm(modelUrl = DEFAULT_DOOR_MODEL_URL) {
  try {
    const asset = await loadDoorModelAsset(modelUrl);
    return normalizeBoundsMm(asset?.boundsMm);
  } catch (_) {
    return getFallbackDoorModelBoundsMm();
  }
}

export async function cloneDoorModelScene(modelUrl = DEFAULT_DOOR_MODEL_URL) {
  const asset = await loadDoorModelAsset(modelUrl);
  const scene = cloneSceneGraph(asset.templateScene);
  return {
    scene,
    boundsMm: normalizeBoundsMm(asset.boundsMm),
    url: asset.url,
  };
}
