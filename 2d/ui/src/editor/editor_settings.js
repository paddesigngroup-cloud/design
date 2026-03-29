export const EDITOR_SETTINGS_DEFAULTS = Object.freeze({
  unit: "cm",
  snapOn: true,
  snapCornerEnabled: true,
  snapMidEnabled: true,
  snapCenterEnabled: true,
  snapEdgeEnabled: true,
  wallMagnetEnabled: true,
  orthoEnabled: true,
  stepDrawMode: "line",
  stepDrawEnabled: true,
  stepLineEnabled: true,
  stepDegreeEnabled: false,
  stepLineCm: 5,
  stepAngleDeg: 10,
  dimSnapProfileEnabled: false,
  dimSnapLineProfile: { origin: true, corner: true, mid: true, center: true, edge: true },
  dimSnapOffsetProfile: { origin: true, corner: true, mid: true, center: true, edge: true },
  meterDivisions: 10,
  majorEvery: 10,
  bgColor: "#FFFFFF",
  minorColor: "#E6E6E6",
  majorColor: "#A3A3A3",
  axisXColor: "#9CC9B4",
  axisYColor: "#BCC8EB",
  axisZColor: "#0000FF",
  showObjectAxes: false,
  wallFillColor: "#A6A6A6",
  wallEdgeColor: "#000000",
  wallTextColor: "#FFFFFF",
  wallHeightColor: "#4B5563",
  wall3dColor: "#C7CCD1",
  beamThicknessMm: 400,
  beamHeightMm: 200,
  beamFloorOffsetMm: 2600,
  beamFillColor: "#A6A6A6",
  beamEdgeColor: "#000000",
  beamTextColor: "#FFFFFF",
  beam3dColor: "#C7CCD1",
  columnWidthMm: 500,
  columnDepthMm: 400,
  columnHeightMm: 2800,
  columnFillColor: "#A6A6A6",
  columnEdgeColor: "#000000",
  columnTextColor: "#FFFFFF",
  column3dColor: "#C7CCD1",
  wallThicknessMm: 120,
  wallHeightMm: 3000,
  hiddenWallThicknessMm: 1,
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
  miterLimit: 10,
  showGammaDebug: false,
});

function cloneProfile(value, fallback) {
  const source = value && typeof value === "object" ? value : fallback;
  return {
    origin: source.origin !== false,
    corner: source.corner !== false,
    mid: source.mid !== false,
    center: source.center !== false,
    edge: source.edge !== false,
  };
}

function cloneDash(value, fallback) {
  const source = Array.isArray(value) && value.length ? value : fallback;
  return source
    .map((item) => Math.max(0, Number(item) || 0))
    .filter((item) => Number.isFinite(item));
}

function normalizeString(value, fallback) {
  const text = String(value ?? "").trim();
  return text || fallback;
}

function normalizeBool(value, fallback) {
  return typeof value === "boolean" ? value : fallback;
}

function normalizeNumber(value, fallback, min = null) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  if (min != null && parsed < min) return fallback;
  return parsed;
}

export function normalizeEditorSettingsState(input = {}) {
  const source = input && typeof input === "object" ? input : {};
  return {
    unit: normalizeString(source.unit, EDITOR_SETTINGS_DEFAULTS.unit),
    snapOn: normalizeBool(source.snapOn, EDITOR_SETTINGS_DEFAULTS.snapOn),
    snapCornerEnabled: normalizeBool(source.snapCornerEnabled, EDITOR_SETTINGS_DEFAULTS.snapCornerEnabled),
    snapMidEnabled: normalizeBool(source.snapMidEnabled, EDITOR_SETTINGS_DEFAULTS.snapMidEnabled),
    snapCenterEnabled: normalizeBool(source.snapCenterEnabled, EDITOR_SETTINGS_DEFAULTS.snapCenterEnabled),
    snapEdgeEnabled: normalizeBool(source.snapEdgeEnabled, EDITOR_SETTINGS_DEFAULTS.snapEdgeEnabled),
    wallMagnetEnabled: normalizeBool(source.wallMagnetEnabled, EDITOR_SETTINGS_DEFAULTS.wallMagnetEnabled),
    orthoEnabled: normalizeBool(source.orthoEnabled, EDITOR_SETTINGS_DEFAULTS.orthoEnabled),
    stepDrawMode: normalizeString(source.stepDrawMode, EDITOR_SETTINGS_DEFAULTS.stepDrawMode) === "degree" ? "degree" : "line",
    stepDrawEnabled: normalizeBool(source.stepDrawEnabled, EDITOR_SETTINGS_DEFAULTS.stepDrawEnabled),
    stepLineEnabled: normalizeBool(source.stepLineEnabled, EDITOR_SETTINGS_DEFAULTS.stepLineEnabled),
    stepDegreeEnabled: normalizeBool(source.stepDegreeEnabled, EDITOR_SETTINGS_DEFAULTS.stepDegreeEnabled),
    stepLineCm: normalizeNumber(source.stepLineCm, EDITOR_SETTINGS_DEFAULTS.stepLineCm, 0.1),
    stepAngleDeg: normalizeNumber(source.stepAngleDeg, EDITOR_SETTINGS_DEFAULTS.stepAngleDeg, 0.1),
    dimSnapProfileEnabled: normalizeBool(source.dimSnapProfileEnabled, EDITOR_SETTINGS_DEFAULTS.dimSnapProfileEnabled),
    dimSnapLineProfile: cloneProfile(source.dimSnapLineProfile, EDITOR_SETTINGS_DEFAULTS.dimSnapLineProfile),
    dimSnapOffsetProfile: cloneProfile(source.dimSnapOffsetProfile, EDITOR_SETTINGS_DEFAULTS.dimSnapOffsetProfile),
    meterDivisions: normalizeNumber(source.meterDivisions, EDITOR_SETTINGS_DEFAULTS.meterDivisions, 1),
    majorEvery: normalizeNumber(source.majorEvery, EDITOR_SETTINGS_DEFAULTS.majorEvery, 1),
    bgColor: normalizeString(source.bgColor, EDITOR_SETTINGS_DEFAULTS.bgColor),
    minorColor: normalizeString(source.minorColor, EDITOR_SETTINGS_DEFAULTS.minorColor),
    majorColor: normalizeString(source.majorColor, EDITOR_SETTINGS_DEFAULTS.majorColor),
    axisXColor: normalizeString(source.axisXColor, EDITOR_SETTINGS_DEFAULTS.axisXColor),
    axisYColor: normalizeString(source.axisYColor, EDITOR_SETTINGS_DEFAULTS.axisYColor),
    axisZColor: normalizeString(source.axisZColor, EDITOR_SETTINGS_DEFAULTS.axisZColor),
    showObjectAxes: normalizeBool(source.showObjectAxes, EDITOR_SETTINGS_DEFAULTS.showObjectAxes),
    wallFillColor: normalizeString(source.wallFillColor, EDITOR_SETTINGS_DEFAULTS.wallFillColor),
    wallEdgeColor: normalizeString(source.wallEdgeColor, EDITOR_SETTINGS_DEFAULTS.wallEdgeColor),
    wallTextColor: normalizeString(source.wallTextColor, EDITOR_SETTINGS_DEFAULTS.wallTextColor),
    wallHeightColor: normalizeString(source.wallHeightColor, EDITOR_SETTINGS_DEFAULTS.wallHeightColor),
    wall3dColor: normalizeString(source.wall3dColor, EDITOR_SETTINGS_DEFAULTS.wall3dColor),
    beamThicknessMm: normalizeNumber(source.beamThicknessMm, EDITOR_SETTINGS_DEFAULTS.beamThicknessMm, 1),
    beamHeightMm: normalizeNumber(source.beamHeightMm, EDITOR_SETTINGS_DEFAULTS.beamHeightMm, 1),
    beamFloorOffsetMm: normalizeNumber(source.beamFloorOffsetMm, EDITOR_SETTINGS_DEFAULTS.beamFloorOffsetMm, 0),
    beamFillColor: normalizeString(source.beamFillColor, EDITOR_SETTINGS_DEFAULTS.beamFillColor),
    beamEdgeColor: normalizeString(source.beamEdgeColor, EDITOR_SETTINGS_DEFAULTS.beamEdgeColor),
    beamTextColor: normalizeString(source.beamTextColor, EDITOR_SETTINGS_DEFAULTS.beamTextColor),
    beam3dColor: normalizeString(source.beam3dColor, EDITOR_SETTINGS_DEFAULTS.beam3dColor),
    columnWidthMm: normalizeNumber(source.columnWidthMm, EDITOR_SETTINGS_DEFAULTS.columnWidthMm, 1),
    columnDepthMm: normalizeNumber(source.columnDepthMm, EDITOR_SETTINGS_DEFAULTS.columnDepthMm, 1),
    columnHeightMm: normalizeNumber(source.columnHeightMm, EDITOR_SETTINGS_DEFAULTS.columnHeightMm, 1),
    columnFillColor: normalizeString(source.columnFillColor, EDITOR_SETTINGS_DEFAULTS.columnFillColor),
    columnEdgeColor: normalizeString(source.columnEdgeColor, EDITOR_SETTINGS_DEFAULTS.columnEdgeColor),
    columnTextColor: normalizeString(source.columnTextColor, EDITOR_SETTINGS_DEFAULTS.columnTextColor),
    column3dColor: normalizeString(source.column3dColor, EDITOR_SETTINGS_DEFAULTS.column3dColor),
    wallThicknessMm: normalizeNumber(source.wallThicknessMm, EDITOR_SETTINGS_DEFAULTS.wallThicknessMm, 1),
    wallHeightMm: normalizeNumber(source.wallHeightMm, EDITOR_SETTINGS_DEFAULTS.wallHeightMm, 1),
    hiddenWallThicknessMm: normalizeNumber(source.hiddenWallThicknessMm, EDITOR_SETTINGS_DEFAULTS.hiddenWallThicknessMm, 0.1),
    hiddenWallColor: normalizeString(source.hiddenWallColor, EDITOR_SETTINGS_DEFAULTS.hiddenWallColor),
    hiddenWallLineWidthPx: normalizeNumber(source.hiddenWallLineWidthPx, EDITOR_SETTINGS_DEFAULTS.hiddenWallLineWidthPx, 1),
    hiddenWallDash: cloneDash(source.hiddenWallDash, EDITOR_SETTINGS_DEFAULTS.hiddenWallDash),
    dimColor: normalizeString(source.dimColor, EDITOR_SETTINGS_DEFAULTS.dimColor),
    dimFontPx: normalizeNumber(source.dimFontPx, EDITOR_SETTINGS_DEFAULTS.dimFontPx, 1),
    dimLineWidthPx: normalizeNumber(source.dimLineWidthPx, EDITOR_SETTINGS_DEFAULTS.dimLineWidthPx, 1),
    dimOffsetMm: normalizeNumber(source.dimOffsetMm, EDITOR_SETTINGS_DEFAULTS.dimOffsetMm, 0),
    dimTickPx: normalizeNumber(source.dimTickPx, EDITOR_SETTINGS_DEFAULTS.dimTickPx, 1),
    dimGapTextPx: normalizeNumber(source.dimGapTextPx, EDITOR_SETTINGS_DEFAULTS.dimGapTextPx, 0),
    dimTextPadPx: normalizeNumber(source.dimTextPadPx, EDITOR_SETTINGS_DEFAULTS.dimTextPadPx, 0),
    showDimensions: normalizeBool(source.showDimensions, EDITOR_SETTINGS_DEFAULTS.showDimensions),
    angleColor: normalizeString(source.angleColor, EDITOR_SETTINGS_DEFAULTS.angleColor),
    angleFontPx: normalizeNumber(source.angleFontPx, EDITOR_SETTINGS_DEFAULTS.angleFontPx, 1),
    angleRadiusPx: normalizeNumber(source.angleRadiusPx, EDITOR_SETTINGS_DEFAULTS.angleRadiusPx, 1),
    angleArcWidthPx: normalizeNumber(source.angleArcWidthPx, EDITOR_SETTINGS_DEFAULTS.angleArcWidthPx, 1),
    offsetWallEnabled: normalizeBool(source.offsetWallEnabled, EDITOR_SETTINGS_DEFAULTS.offsetWallEnabled),
    offsetWallDistanceMm: normalizeNumber(source.offsetWallDistanceMm, EDITOR_SETTINGS_DEFAULTS.offsetWallDistanceMm, 0),
    offsetWallColor: normalizeString(source.offsetWallColor, EDITOR_SETTINGS_DEFAULTS.offsetWallColor),
    offsetWallLineWidthPx: normalizeNumber(source.offsetWallLineWidthPx, EDITOR_SETTINGS_DEFAULTS.offsetWallLineWidthPx, 1),
    offsetWallDash: cloneDash(source.offsetWallDash, EDITOR_SETTINGS_DEFAULTS.offsetWallDash),
    fontFamily: normalizeString(source.fontFamily, EDITOR_SETTINGS_DEFAULTS.fontFamily),
    wallNameFontPx: normalizeNumber(source.wallNameFontPx, EDITOR_SETTINGS_DEFAULTS.wallNameFontPx, 1),
    miterLimit: normalizeNumber(source.miterLimit, EDITOR_SETTINGS_DEFAULTS.miterLimit, 1),
    showGammaDebug: normalizeBool(source.showGammaDebug, EDITOR_SETTINGS_DEFAULTS.showGammaDebug),
  };
}

export function editorSettingsStateToPayload(input = {}) {
  const state = normalizeEditorSettingsState(input);
  return {
    generalSettings: {
      unit: state.unit,
      fontFamily: state.fontFamily,
      wallNameFontPx: state.wallNameFontPx,
    },
    gridSettings: {
      meterDivisions: state.meterDivisions,
      majorEvery: state.majorEvery,
      bgColor: state.bgColor,
      minorColor: state.minorColor,
      majorColor: state.majorColor,
      axisXColor: state.axisXColor,
      axisYColor: state.axisYColor,
      axisZColor: state.axisZColor,
    },
    snapSettings: {
      snapOn: state.snapOn,
      snapCornerEnabled: state.snapCornerEnabled,
      snapMidEnabled: state.snapMidEnabled,
      snapCenterEnabled: state.snapCenterEnabled,
      snapEdgeEnabled: state.snapEdgeEnabled,
      wallMagnetEnabled: state.wallMagnetEnabled,
      orthoEnabled: state.orthoEnabled,
      dimSnapProfileEnabled: state.dimSnapProfileEnabled,
      dimSnapLineProfile: cloneProfile(state.dimSnapLineProfile, EDITOR_SETTINGS_DEFAULTS.dimSnapLineProfile),
      dimSnapOffsetProfile: cloneProfile(state.dimSnapOffsetProfile, EDITOR_SETTINGS_DEFAULTS.dimSnapOffsetProfile),
    },
    draftingSettings: {
      stepDrawMode: state.stepDrawMode,
      stepDrawEnabled: state.stepDrawEnabled,
      stepLineEnabled: state.stepLineEnabled,
      stepDegreeEnabled: state.stepDegreeEnabled,
      stepLineCm: state.stepLineCm,
      stepAngleDeg: state.stepAngleDeg,
      showObjectAxes: state.showObjectAxes,
      miterLimit: state.miterLimit,
      showGammaDebug: state.showGammaDebug,
    },
    wallDefaults: {
      wallThicknessMm: state.wallThicknessMm,
      wallHeightMm: state.wallHeightMm,
      wallFillColor: state.wallFillColor,
      wallEdgeColor: state.wallEdgeColor,
      wallTextColor: state.wallTextColor,
      wallHeightColor: state.wallHeightColor,
      wall3dColor: state.wall3dColor,
    },
    beamDefaults: {
      beamThicknessMm: state.beamThicknessMm,
      beamHeightMm: state.beamHeightMm,
      beamFloorOffsetMm: state.beamFloorOffsetMm,
      beamFillColor: state.beamFillColor,
      beamEdgeColor: state.beamEdgeColor,
      beamTextColor: state.beamTextColor,
      beam3dColor: state.beam3dColor,
    },
    columnDefaults: {
      columnWidthMm: state.columnWidthMm,
      columnDepthMm: state.columnDepthMm,
      columnHeightMm: state.columnHeightMm,
      columnFillColor: state.columnFillColor,
      columnEdgeColor: state.columnEdgeColor,
      columnTextColor: state.columnTextColor,
      column3dColor: state.column3dColor,
    },
    hiddenDefaults: {
      hiddenWallThicknessMm: state.hiddenWallThicknessMm,
      hiddenWallColor: state.hiddenWallColor,
      hiddenWallLineWidthPx: state.hiddenWallLineWidthPx,
      hiddenWallDash: cloneDash(state.hiddenWallDash, EDITOR_SETTINGS_DEFAULTS.hiddenWallDash),
    },
    dimensionDefaults: {
      dimColor: state.dimColor,
      dimFontPx: state.dimFontPx,
      dimLineWidthPx: state.dimLineWidthPx,
      dimOffsetMm: state.dimOffsetMm,
      dimTickPx: state.dimTickPx,
      dimGapTextPx: state.dimGapTextPx,
      dimTextPadPx: state.dimTextPadPx,
      showDimensions: state.showDimensions,
    },
    angleDefaults: {
      angleColor: state.angleColor,
      angleFontPx: state.angleFontPx,
      angleRadiusPx: state.angleRadiusPx,
      angleArcWidthPx: state.angleArcWidthPx,
    },
    offsetWallSettings: {
      offsetWallEnabled: state.offsetWallEnabled,
      offsetWallDistanceMm: state.offsetWallDistanceMm,
      offsetWallColor: state.offsetWallColor,
      offsetWallLineWidthPx: state.offsetWallLineWidthPx,
      offsetWallDash: cloneDash(state.offsetWallDash, EDITOR_SETTINGS_DEFAULTS.offsetWallDash),
    },
  };
}

export function editorSettingsPayloadToState(payload = {}) {
  const source = payload && typeof payload === "object" ? payload : {};
  return normalizeEditorSettingsState({
    ...EDITOR_SETTINGS_DEFAULTS,
    ...(source.generalSettings || {}),
    ...(source.gridSettings || {}),
    ...(source.snapSettings || {}),
    ...(source.draftingSettings || {}),
    ...(source.wallDefaults || {}),
    ...(source.beamDefaults || {}),
    ...(source.columnDefaults || {}),
    ...(source.hiddenDefaults || {}),
    ...(source.dimensionDefaults || {}),
    ...(source.angleDefaults || {}),
    ...(source.offsetWallSettings || {}),
  });
}

export function settingsViewStateFromEditorState(state = {}) {
  const flat = normalizeEditorSettingsState(state);
  return {
    unit: flat.unit,
    wallThicknessMm: flat.wallThicknessMm,
    wallHeightMm: flat.wallHeightMm,
    hiddenWallThicknessMm: flat.hiddenWallThicknessMm,
    beamThicknessMm: flat.beamThicknessMm,
    beamHeightMm: flat.beamHeightMm,
    beamFloorOffsetMm: flat.beamFloorOffsetMm,
    columnWidthMm: flat.columnWidthMm,
    columnDepthMm: flat.columnDepthMm,
    columnHeightMm: flat.columnHeightMm,
    dimOffsetMm: flat.dimOffsetMm,
    dimFontPx: flat.dimFontPx,
    dimLineWidthPx: flat.dimLineWidthPx,
    meterDivisions: flat.meterDivisions,
    majorEvery: flat.majorEvery,
    fontFamily: flat.fontFamily,
    wallNameFontPx: flat.wallNameFontPx,
    angleFontPx: flat.angleFontPx,
    snapOn: flat.snapOn,
    showDimensions: flat.showDimensions,
    stepDrawEnabled: flat.stepDrawEnabled,
    stepLineCm: flat.stepLineCm,
    stepAngleDeg: flat.stepAngleDeg,
    snapCornerEnabled: flat.snapCornerEnabled,
    snapMidEnabled: flat.snapMidEnabled,
    snapCenterEnabled: flat.snapCenterEnabled,
    snapEdgeEnabled: flat.snapEdgeEnabled,
    wallMagnetEnabled: flat.wallMagnetEnabled,
    bgColor: flat.bgColor,
    minorColor: flat.minorColor,
    majorColor: flat.majorColor,
    axisXColor: flat.axisXColor,
    axisYColor: flat.axisYColor,
    axisZColor: flat.axisZColor,
    wallFillColor: flat.wallFillColor,
    wallEdgeColor: flat.wallEdgeColor,
    wallTextColor: flat.wallTextColor,
    wall3dColor: flat.wall3dColor,
    beamFillColor: flat.beamFillColor,
    beamEdgeColor: flat.beamEdgeColor,
    beamTextColor: flat.beamTextColor,
    beam3dColor: flat.beam3dColor,
    columnFillColor: flat.columnFillColor,
    columnEdgeColor: flat.columnEdgeColor,
    columnTextColor: flat.columnTextColor,
    column3dColor: flat.column3dColor,
    dimColor: flat.dimColor,
    hiddenWallColor: flat.hiddenWallColor,
    offsetWallEnabled: flat.offsetWallEnabled,
    offsetWallDistanceMm: flat.offsetWallDistanceMm,
  };
}

export async function fetchPersistedEditorSettings(adminId, userId) {
  const res = await fetch(
    `/api/editor-settings?admin_id=${encodeURIComponent(adminId)}&user_id=${encodeURIComponent(userId)}`
  );
  if (!res.ok) {
    throw new Error("editor-settings-fetch-failed");
  }
  return await res.json();
}

export async function savePersistedEditorSettings(adminId, userId, payload) {
  const res = await fetch(
    `/api/editor-settings?admin_id=${encodeURIComponent(adminId)}&user_id=${encodeURIComponent(userId)}`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }
  );
  if (!res.ok) {
    throw new Error("editor-settings-save-failed");
  }
  return await res.json();
}
