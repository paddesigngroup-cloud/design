import { DEFAULT_DOOR_MODEL_URL, getDoorModelBoundsMm, getFallbackDoorModelBoundsMm } from "./door_model_asset.js";

const RAW_DOOR_PRESETS = [
  {
    id: "single_90",
    title: "تک لنگه ۹۰",
    widthMm: 900,
    heightMm: 2200,
    sillHeightMm: 0,
    frameThicknessMm: 50,
    frameDepthMm: 120,
  },
  {
    id: "single_100",
    title: "تک لنگه ۱۰۰",
    widthMm: 1000,
    heightMm: 2300,
    sillHeightMm: 0,
    frameThicknessMm: 60,
    frameDepthMm: 140,
  },
  {
    id: "double_140",
    title: "دو لنگه ۱۴۰",
    widthMm: 1400,
    heightMm: 2400,
    sillHeightMm: 0,
    frameThicknessMm: 60,
    frameDepthMm: 160,
  },
];

export const DOOR_READY_PRESETS = RAW_DOOR_PRESETS.map((preset) => ({
  ...preset,
  kind: preset.id,
  modelUrl: DEFAULT_DOOR_MODEL_URL,
}));

function resolveDoorPreset(kindOrPreset) {
  if (kindOrPreset && typeof kindOrPreset === "object") return kindOrPreset;
  return DOOR_READY_PRESETS.find((preset) => preset.id === kindOrPreset) || DOOR_READY_PRESETS[0] || null;
}

export function getDoorPreset(kind) {
  const preset = resolveDoorPreset(kind);
  if (!preset) return null;
  return {
    ...preset,
    modelUrl: String(preset.modelUrl || DEFAULT_DOOR_MODEL_URL).trim() || DEFAULT_DOOR_MODEL_URL,
  };
}

function getPresetBoundsMm(preset) {
  const fromModel = preset?.modelBoundsMm;
  if (fromModel && typeof fromModel === "object") {
    return {
      widthMm: Math.max(10, Number(fromModel.widthMm) || Number(preset?.widthMm) || 900),
      heightMm: Math.max(10, Number(fromModel.heightMm) || Number(preset?.heightMm) || 2200),
      depthMm: Math.max(10, Number(fromModel.depthMm) || Number(preset?.frameDepthMm) || 120),
    };
  }
  const fallback = getFallbackDoorModelBoundsMm();
  return {
    widthMm: Math.max(10, Number(preset?.widthMm) || fallback.widthMm),
    heightMm: Math.max(10, Number(preset?.heightMm) || fallback.heightMm),
    depthMm: Math.max(10, Number(preset?.frameDepthMm) || fallback.depthMm),
  };
}

export function buildDoorPresetPayload(kindOrPreset) {
  const preset = getDoorPreset(kindOrPreset);
  if (!preset) return null;
  const boundsMm = getPresetBoundsMm(preset);
  return {
    presetId: preset.id,
    name: preset.title,
    widthMm: boundsMm.widthMm,
    heightMm: boundsMm.heightMm,
    sillHeightMm: preset.sillHeightMm,
    frameThicknessMm: preset.frameThicknessMm,
    frameDepthMm: Math.max(boundsMm.depthMm, Number(preset.frameDepthMm) || boundsMm.depthMm),
    modelUrl: String(preset.modelUrl || DEFAULT_DOOR_MODEL_URL).trim() || DEFAULT_DOOR_MODEL_URL,
    modelBoundsMm: boundsMm,
  };
}

export async function buildDoorPresetPayloadAsync(kindOrPreset) {
  const preset = getDoorPreset(kindOrPreset);
  if (!preset) return null;
  const modelUrl = String(preset.modelUrl || DEFAULT_DOOR_MODEL_URL).trim() || DEFAULT_DOOR_MODEL_URL;
  const boundsMm = await getDoorModelBoundsMm(modelUrl);
  return buildDoorPresetPayload({
    ...preset,
    modelUrl,
    modelBoundsMm: boundsMm,
    widthMm: boundsMm.widthMm,
    heightMm: boundsMm.heightMm,
    frameDepthMm: Math.max(boundsMm.depthMm, Number(preset.frameDepthMm) || boundsMm.depthMm),
  });
}

export function primeDoorPresetModel(kindOrPreset) {
  const preset = getDoorPreset(kindOrPreset);
  if (!preset) return Promise.resolve(null);
  const modelUrl = String(preset.modelUrl || DEFAULT_DOOR_MODEL_URL).trim() || DEFAULT_DOOR_MODEL_URL;
  return getDoorModelBoundsMm(modelUrl).then((boundsMm) => ({
    ...preset,
    modelUrl,
    modelBoundsMm: boundsMm,
    widthMm: boundsMm.widthMm,
    heightMm: boundsMm.heightMm,
    frameDepthMm: Math.max(boundsMm.depthMm, Number(preset.frameDepthMm) || boundsMm.depthMm),
  }));
}

export function buildDoorPresetPreviewLines(kindOrPreset) {
  const preset = getDoorPreset(kindOrPreset);
  if (!preset) return [];
  const boundsMm = getPresetBoundsMm(preset);
  const half = boundsMm.widthMm * 0.5;
  const frame = Math.max(30, Number(preset.frameThicknessMm) || 50);
  return [
    { ax: -half, ay: 0, bx: half, by: 0, thickness: frame, name: preset.title },
    { ax: -half, ay: -frame * 1.2, bx: -half, by: frame * 1.2, thickness: frame * 0.35, name: "" },
    { ax: half, ay: -frame * 1.2, bx: half, by: frame * 1.2, thickness: frame * 0.35, name: "" },
  ];
}

export function getDoorPresetIconLines(kindOrPreset) {
  const preset = getDoorPreset(kindOrPreset);
  if (!preset) return [];
  const boundsMm = getPresetBoundsMm(preset);
  const width = Math.max(1, Number(boundsMm.widthMm) || 900);
  const half = width * 0.5;
  const frame = Math.max(30, Number(preset.frameThicknessMm) || 50);
  const scale = Math.min(32 / width, 1);
  const toX = (x) => 22 + x * scale;
  const toY = (y) => 22 - y * scale;
  return [
    { x1: toX(-half), y1: toY(0), x2: toX(half), y2: toY(0), sw: Math.max(2, frame * scale) },
    { x1: toX(-half), y1: toY(-frame), x2: toX(-half), y2: toY(frame), sw: Math.max(1.5, frame * scale * 0.35) },
    { x1: toX(half), y1: toY(-frame), x2: toX(half), y2: toY(frame), sw: Math.max(1.5, frame * scale * 0.35) },
  ];
}
