<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { editorRef, model2dTransformRef } from "./editor/editor_store.js";
import GlbViewerWidget from "./components/GlbViewerWidget.vue";
import { useDialogService } from "./dialog_service.js";
import { WALL_READY_PRESETS, buildPresetLines, getPresetIconWalls } from "./features/wall_preset_drag.js";

const activeTool = ref("select");
const snapOn = ref(true);
const showDimensions = ref(true);
const showOffsetWalls = ref(true);
const showObjectAxes = ref(false);
const walls3dSnapshot = ref({
  nodes: [],
  walls: [],
  selection: { selectedWallId: null, selectedWallIds: [], selectedHiddenId: null, selectedHiddenIds: [] },
  metrics: {
    nodes: [],
    walls: [],
    selection: { selectedWallId: null, selectedWallIds: [] },
    entityType: "wall",
  },
  state: { wallHeightMm: 2800, axisXColor: "#9CC9B4", axisYColor: "#BCC8EB", axisZColor: "#0000FF" },
});
const stepModes = ref({
  line: true,
  degree: false,
});
const snapModes = ref({
  corner: true,
  mid: true,
  center: true,
  edge: true,
  wallMagnet: true,
  ortho: true,
});
const isAnySnapModeOn = computed(() => Object.values(snapModes.value).some(Boolean));
const isAnyStepModeOn = computed(() => Object.values(stepModes.value).some(Boolean));
const quickMenuOpen = ref(null); // "snaps" | "steps" | null
const { dialogState, alert: showAlert, confirm: showConfirm, prompt: showPrompt, resolveConfirm, close: closeDialog } = useDialogService();

const activeMenu = ref(null); // menuId | null
const openMenuPanel = ref(null); // menuId | null
const drawUiLock = ref(false); // while drawing, keep submenus closed until Esc
const designMenuTool = ref(null); // "wall" | "hidden" | "dimension" | "beam" | "column" | null
const wallStyleDraft = ref({ thicknessCm: 12, heightCm: 300, floorOffsetCm: 0, color: "#A6A6A6" });
const selectedWallStyle = ref(null);
const wallStyleDraftTouched = ref(false);

const topbarEl = ref(null);
const mainEl = ref(null);
const stageEl = ref(null);
const stageCardEl = ref(null);
const homeBtnEl = ref(null);
const menuPanelEl = ref(null);
const mainMenuBtnEl = ref(null);
const designBtnEl = ref(null);
const catalogBtnEl = ref(null);

const route = useRoute();
const router = useRouter();
const isSettings = computed(() => route.path === "/settings");
const isHome = computed(() => route.path === "/");
const showStageOverlays = computed(() => route.name === "floorplan");

const STORAGE_PROJECTS_KEY = "designkp_projects_v1";
const projects = ref([]); // [{id,name,ts,state}]
const openMode = ref("menu"); // "menu" | "open"

const menuTitles = {
  menu: "منو",
  design: "طراحی",
  catalog: "کاتالوگ",
  construction: "شیوه ساخت",
  material: "جنس",
  cutting: "لیست برش",
  machinery: "ماشین کاری",
  price: "قیمت گذاری",
  report: "گزارشات",
  sheet: "شیت بندی",
  profile: "حساب کاربری",
};
const menuIcons = {
  menu: "/icons/main-menu.png",
  design: "/icons/design.png",
  catalog: "/icons/catalog.png",
  construction: "/icons/construction-_method.png",
  material: "/icons/material.png",
  cutting: "/icons/cutting_list.png",
  machinery: "/icons/machinery.png",
  price: "/icons/price.png",
  report: "/icons/report.png",
  sheet: "/icons/sheet.png",
  profile: "/icons/profile.png",
};
const openMenuTitle = computed(() => (openMenuPanel.value ? menuTitles[openMenuPanel.value] || "" : ""));
const openMenuIcon = computed(() => (openMenuPanel.value ? menuIcons[openMenuPanel.value] || "" : ""));
const isMenuPanelOpen = computed(() => !!openMenuPanel.value);
const allowedSubRailMenus = new Set(["menu", "design", "catalog"]);
const shouldShowSubRail = computed(() => {
  const p = openMenuPanel.value;
  // Always show when no menu is open (sticks to main menu icon).
  // When a menu is open, only show for the first 3 menus (menu/design/catalog).
  if (!p) return true;
  return allowedSubRailMenus.has(p);
});
const subRailAttach = computed(() => {
  const p = openMenuPanel.value;
  if (p && allowedSubRailMenus.has(p)) return "panel";
  return "main";
});

const activeSubRail = ref(null); // toolId | null
const subRailItems = [
  { id: "wall", icon: "/icons/wall.png", title: "دیوار" },
  { id: "door", icon: "/icons/door.png", title: "درب" },
  { id: "window", icon: "/icons/window.png", title: "پنجره" },
  { id: "signs", icon: "/icons/signs.png", title: "علائم" },
  { id: "cabinet", icon: "/icons/cabinet.png", title: "کابینت" },
  { id: "refrigrator", icon: "/icons/refrigrator.png", title: "یخچال" },
  { id: "sink", icon: "/icons/sink.png", title: "سینک" },
  { id: "cooker", icon: "/icons/cooker_kitchen.png", title: "اجاق" },
  { id: "hood", icon: "/icons/cook_extraction.png", title: "هود" },
  { id: "microwave", icon: "/icons/microwave.png", title: "مایکروویو" },
  { id: "chandelier", icon: "/icons/chandelier.png", title: "لوستر" },
  { id: "vertical_piece", icon: "/icons/vertical_piece.png", title: "قطعه عمودی" },
  { id: "horizontal_piece", icon: "/icons/horizontal_piece.png", title: "قطعه افقی" },
];
const activeSubRailTitle = computed(() => {
  const id = activeSubRail.value;
  if (!id) return "";
  const it = subRailItems.find((x) => x.id === id);
  return it ? it.title : "";
});

const designMenuTools = [
  { id: "wall", icon: "/icons/drawing_wall.png", title: "دیوار", mapsToTool: "wall" },
  { id: "hidden", icon: "/icons/drawing_hidden_wall.png", title: "خط راهنما", mapsToTool: "hidden" },
  { id: "dimension", icon: "/icons/drawing_dimension.png", title: "اندازه گذاری", mapsToTool: "dimension" },
  { id: "beam", icon: "/icons/beam.png", title: "تیر", mapsToTool: "beam" },
  { id: "column", icon: "/icons/column.png", title: "ستون", mapsToTool: null },
];

const wallPresets = WALL_READY_PRESETS;
const presetDrag = ref({ active: false, preset: null, clientX: 0, clientY: 0, startX: 0, startY: 0, enteredStage: false });
const snapMenuItems = [
  { id: "corner", title: "گوشه", icon: "/icons/corner_point.png" },
  { id: "mid", title: "وسط ضلع", icon: "/icons/midpoint.png" },
  { id: "center", title: "مرکز", icon: "/icons/ax_point.png" },
  { id: "edge", title: "لبه", icon: "/icons/edge_snap.png" },
  { id: "wallMagnet", title: "جذب دیوار", icon: "/icons/magnet.png" },
  { id: "ortho", title: "راستا (راست کلیک)", icon: "/icons/ortho_line.png" },
];

function applyEditorPatch(patch) {
  editorRef.value?.setState?.(patch);
}

function normalizeStepModes(statePatch = {}) {
  const hasLine = typeof statePatch.stepLineEnabled === "boolean";
  const hasDegree = typeof statePatch.stepDegreeEnabled === "boolean";
  if (hasLine || hasDegree) {
    return {
      line: hasLine ? !!statePatch.stepLineEnabled : false,
      degree: hasDegree ? !!statePatch.stepDegreeEnabled : false,
    };
  }
  const enabled = statePatch.stepDrawEnabled !== false;
  if (!enabled) return { line: false, degree: false };
  const mode = statePatch.stepDrawMode === "degree" ? "degree" : "line";
  return { line: mode === "line", degree: mode === "degree" };
}

function getStepPatch(nextModes) {
  const modes = {
    line: !!nextModes?.line,
    degree: !!nextModes?.degree,
  };
  const anyOn = modes.line || modes.degree;
  const mode = modes.degree ? "degree" : "line";
  return {
    stepLineEnabled: modes.line,
    stepDegreeEnabled: modes.degree,
    stepDrawEnabled: anyOn,
    stepDrawMode: mode,
  };
}

function syncQuickStateFromEditor() {
  const full = editorRef.value?.getState?.();
  const s = full?.state;
  if (!s) return;
  showDimensions.value = s.showDimensions !== false;
  showOffsetWalls.value = !!s.offsetWallEnabled;
  showObjectAxes.value = !!s.showObjectAxes;
  const wallNodes = Array.isArray(full?.graphSnap?.nodes) ? full.graphSnap.nodes : [];
  const hiddenNodes = Array.isArray(full?.hiddenGraphSnap?.nodes) ? full.hiddenGraphSnap.nodes : [];
  const walls = Array.isArray(full?.graphSnap?.walls) ? full.graphSnap.walls : [];
  const hiddenWalls = Array.isArray(full?.hiddenGraphSnap?.walls) ? full.hiddenGraphSnap.walls : [];
  const selectedWallIds = Array.isArray(full?.selection?.selectedWallIds) ? full.selection.selectedWallIds : [];
  const selectedHiddenIds = Array.isArray(full?.selection?.selectedHiddenIds) ? full.selection.selectedHiddenIds : [];
  const selectedWallId = full?.selection?.selectedWallId || selectedWallIds[0] || null;
  const selectedHiddenId = full?.selection?.selectedHiddenId || selectedHiddenIds[0] || null;
  const beamNodes = Array.isArray(full?.beamGraphSnap?.nodes) ? full.beamGraphSnap.nodes : [];
  const beams = Array.isArray(full?.beamGraphSnap?.walls) ? full.beamGraphSnap.walls : [];
  const selectedBeamIds = Array.isArray(full?.selection?.selectedBeamIds) ? full.selection.selectedBeamIds : [];
  const selectedBeamId = full?.selection?.selectedBeamId || selectedBeamIds[0] || null;
  const selectedWall = (selectedWallId || selectedWallIds[0]) ? walls.find((w) => w.id === (selectedWallId || selectedWallIds[0])) : null;
  const selectedHidden = (selectedHiddenId || selectedHiddenIds[0]) ? hiddenWalls.find((w) => w.id === (selectedHiddenId || selectedHiddenIds[0])) : null;
  const selectedBeam = (selectedBeamId || selectedBeamIds[0]) ? beams.find((w) => w.id === (selectedBeamId || selectedBeamIds[0])) : null;
  const selectedWallCount = selectedWallIds.length > 0 ? selectedWallIds.length : (selectedWallId ? 1 : 0);
  const selectedHiddenCount = selectedHiddenIds.length > 0 ? selectedHiddenIds.length : (selectedHiddenId ? 1 : 0);
  const selectedBeamCount = selectedBeamIds.length > 0 ? selectedBeamIds.length : (selectedBeamId ? 1 : 0);
  const hasWallSelection = !!(selectedWall || selectedWallIds.length > 0);
  const hasHiddenSelection = !!(selectedHidden || selectedHiddenIds.length > 0);
  const hasBeamSelection = !!(selectedBeam || selectedBeamIds.length > 0);
  const selectedLinearEntity = selectedWall || selectedBeam;
  const selectedElementType = String(selectedLinearEntity?.elementType || "").toLowerCase();
  const inferredEntityType = selectedElementType === "column" ? "column" : (selectedElementType === "beam" ? "beam" : "wall");
  const metricsEntityType = hasBeamSelection ? "beam" : hasWallSelection ? inferredEntityType : hasHiddenSelection ? "hidden" : "wall";
  const selectedCount =
    (metricsEntityType === "hidden") ? selectedHiddenCount
      : (metricsEntityType === "beam") ? selectedBeamCount
        : selectedWallCount;

  walls3dSnapshot.value = {
    nodes: wallNodes,
    walls,
    selection: {
      selectedWallId: full?.selection?.selectedWallId || null,
      selectedWallIds,
      selectedHiddenId: full?.selection?.selectedHiddenId || null,
      selectedHiddenIds,
      selectedBeamId: full?.selection?.selectedBeamId || null,
      selectedBeamIds,
    },
    metrics: {
      nodes: metricsEntityType === "hidden" ? hiddenNodes : metricsEntityType === "beam" ? beamNodes : wallNodes,
      walls: metricsEntityType === "hidden" ? hiddenWalls : metricsEntityType === "beam" ? beams : walls,
      selection: {
        selectedWallId: metricsEntityType === "hidden" ? selectedHiddenId : metricsEntityType === "beam" ? selectedBeamId : selectedWallId,
        selectedWallIds: metricsEntityType === "hidden" ? selectedHiddenIds : selectedWallIds,
      },
      entityType: metricsEntityType,
    },
    state: {
      wallHeightMm: Number.isFinite(s?.wallHeightMm) ? s.wallHeightMm : 2800,
      wallFillColor: (typeof s?.wallFillColor === "string" && s.wallFillColor) ? s.wallFillColor : "#A6A6A6",
      wall3dColor: (typeof s?.wall3dColor === "string" && s.wall3dColor) ? s.wall3dColor : "#C7CCD1",
      axisXColor: (typeof s?.axisXColor === "string" && s.axisXColor) ? s.axisXColor : "#9CC9B4",
      axisYColor: (typeof s?.axisYColor === "string" && s.axisYColor) ? s.axisYColor : "#BCC8EB",
      axisZColor: (typeof s?.axisZColor === "string" && s.axisZColor) ? s.axisZColor : "#0000FF",
      activeTool: s?.activeTool || "select",
      isWallDrawing: !!full?.tools?.wall?.isDrawing,
    },
  };

  if (!wallStyleDraftTouched.value) {
    const defaultThicknessCm = (Number.isFinite(Number(s?.wallThicknessMm)) ? Number(s.wallThicknessMm) : 120) / 10;
    const defaultHeightCm = (Number.isFinite(Number(s?.wallHeightMm)) ? Number(s.wallHeightMm) : 3000) / 10;
    const defaultBeamThicknessCm = (Number.isFinite(Number(s?.beamThicknessMm)) ? Number(s.beamThicknessMm) : 400) / 10;
    const defaultBeamHeightCm = (Number.isFinite(Number(s?.beamHeightMm)) ? Number(s.beamHeightMm) : 200) / 10;
    const defaultBeamFloorOffsetCm = (Number.isFinite(Number(s?.beamFloorOffsetMm)) ? Number(s.beamFloorOffsetMm) : 2600) / 10;
    const defaultColumnWidthCm = (Number.isFinite(Number(s?.columnWidthMm)) ? Number(s.columnWidthMm) : 500) / 10;
    const defaultColumnDepthCm = (Number.isFinite(Number(s?.columnDepthMm)) ? Number(s.columnDepthMm) : 400) / 10;
    const defaultColumnHeightCm = (Number.isFinite(Number(s?.columnHeightMm)) ? Number(s.columnHeightMm) : 2800) / 10;
    const defaultColumnColor = (typeof s?.column3dColor === "string" && s.column3dColor) ? s.column3dColor : "#C7CCD1";
    const defaultColor = (typeof s?.wall3dColor === "string" && s.wall3dColor) ? s.wall3dColor : "#C7CCD1";

    const selectedObj = (metricsEntityType === "hidden") ? selectedHidden : (metricsEntityType === "beam" ? selectedBeam : selectedWall);
    const selectedName = String(selectedObj?.name || "").trim();
    const isBeamSelection = selectedElementType === "beam" || /^Beam\s+/i.test(selectedName);
    const isColumnSelection = selectedElementType === "column" || /^Column\s+/i.test(selectedName);
    const fallbackThicknessCm = isColumnSelection ? defaultColumnDepthCm : (isBeamSelection ? defaultBeamThicknessCm : defaultThicknessCm);
    const fallbackHeightCm = isColumnSelection ? defaultColumnHeightCm : (isBeamSelection ? defaultBeamHeightCm : defaultHeightCm);
    const fallbackFloorOffsetCm = isBeamSelection ? defaultBeamFloorOffsetCm : 0;
    const fallbackColor = isColumnSelection ? defaultColumnColor : defaultColor;
    wallStyleDraft.value = selectedObj
      ? {
          thicknessCm: (Number(selectedObj.thickness) || (fallbackThicknessCm * 10)) / 10,
          heightCm: (Number(selectedObj.heightMm) || (fallbackHeightCm * 10)) / 10,
          floorOffsetCm: (Number(selectedObj.floorOffsetMm) || (fallbackFloorOffsetCm * 10)) / 10,
          color: (typeof selectedObj.color3d === "string" && selectedObj.color3d) ? selectedObj.color3d : fallbackColor,
          floorOffsetCm: (Number(selectedObj.floorOffsetMm) || 0) / 10,
        }
      : {
          thicknessCm: defaultThicknessCm,
          heightCm: defaultHeightCm,
          floorOffsetCm: 0,
          color: defaultColor,
        };
  }

  const selectedEntity = (metricsEntityType === "hidden") ? selectedHidden : (metricsEntityType === "beam") ? selectedBeam : selectedWall;
  if (selectedEntity) {
    const srcNodes = (metricsEntityType === "hidden") ? hiddenNodes : (metricsEntityType === "beam") ? beamNodes : wallNodes;
    const byId = new Map(srcNodes.map((n) => [n.id, n]));
    const na = byId.get(selectedEntity.a);
    const nb = byId.get(selectedEntity.b);
    const lenMm = (na && nb) ? Math.hypot(nb.x - na.x, nb.y - na.y) : 0;
    selectedWallStyle.value = {
      id: selectedEntity.id,
      name: selectedEntity.name || selectedEntity.id,
      entityType: metricsEntityType,
      thicknessCm: (Number(selectedEntity.thickness) || 120) / 10,
      heightCm: (Number(selectedEntity.heightMm) || Number(s?.wallHeightMm) || 3000) / 10,
      floorOffsetCm: (Number(selectedEntity.floorOffsetMm) || 0) / 10,
      lengthCm: lenMm / 10,
      color: (typeof selectedEntity.color3d === "string" && selectedEntity.color3d)
        ? selectedEntity.color3d
        : ((typeof s?.wall3dColor === "string" && s.wall3dColor) ? s.wall3dColor : "#C7CCD1"),
      a: selectedEntity.a,
      b: selectedEntity.b,
      selectedCount,
      isGroupEdit: selectedCount > 1,
    };
  } else {
    selectedWallStyle.value = null;
  }
  if (quickMenuOpen.value !== "steps") {
    stepModes.value = normalizeStepModes(s);
  }
  snapModes.value = {
    corner: s.snapCornerEnabled !== false,
    mid: s.snapMidEnabled !== false,
    center: s.snapCenterEnabled !== false,
    edge: s.snapEdgeEnabled !== false,
    wallMagnet: s.wallMagnetEnabled !== false,
    ortho: s.orthoEnabled !== false,
  };
  snapOn.value = Object.values(snapModes.value).some(Boolean);
}

function clampWallStyleDraft() {
  const t = Math.max(0.1, Number(wallStyleDraft.value.thicknessCm) || 12);
  const h = Math.max(1, Number(wallStyleDraft.value.heightCm) || 300);
  const f = Math.max(0, Number(wallStyleDraft.value.floorOffsetCm) || 0);
  const c = String(wallStyleDraft.value.color || "#A6A6A6");
  wallStyleDraft.value = { thicknessCm: Math.round(t * 10) / 10, heightCm: Math.round(h), floorOffsetCm: Math.round(f), color: c };
}

function updateWallStyleDraft(next) {
  wallStyleDraftTouched.value = true;
  const draft = {
    thicknessCm: Number(next?.thicknessCm ?? wallStyleDraft.value.thicknessCm),
    heightCm: Number(next?.heightCm ?? wallStyleDraft.value.heightCm),
    floorOffsetCm: Number(next?.floorOffsetCm ?? wallStyleDraft.value.floorOffsetCm),
    color: String(next?.color ?? wallStyleDraft.value.color),
  };
  wallStyleDraft.value = draft;
  clampWallStyleDraft();

  const thicknessMm = Math.max(1, wallStyleDraft.value.thicknessCm * 10);
  const heightMm = Math.max(1, wallStyleDraft.value.heightCm * 10);
  const color3d = wallStyleDraft.value.color;
  const floorOffsetMm = Math.max(0, wallStyleDraft.value.floorOffsetCm * 10);
  const lengthMm = Number.isFinite(Number(next?.lengthCm)) ? Math.max(10, Number(next.lengthCm) * 10) : null;
  const entityType = selectedWallStyle.value?.entityType || "wall";
  const selectedName = String(selectedWallStyle.value?.name || "").trim();
  const selectedEntityType = selectedWallStyle.value?.entityType || "wall";
  const isBeamEntity = selectedEntityType === "beam" || /^Beam\s+/i.test(selectedName);
  const isColumnEntity = selectedEntityType === "column" || /^Column\s+/i.test(selectedName);

  // Only update global wall defaults when no wall is selected.
  if (entityType !== "hidden" && !selectedWallStyle.value?.id) {
    if (isColumnEntity || designMenuTool.value === "column") {
      editorRef.value?.setState?.({
        columnWidthMm: lengthMm ?? Math.max(10, Number(wallStyleDraft.value.thicknessCm) * 10),
        columnDepthMm: thicknessMm,
        columnHeightMm: heightMm,
        column3dColor: color3d,
      });
    } else if (isBeamEntity || designMenuTool.value === "beam") {
      editorRef.value?.setState?.({
        beamThicknessMm: thicknessMm,
        beamHeightMm: heightMm,
        beamFloorOffsetMm: floorOffsetMm,
      });
    } else {
      editorRef.value?.setState?.({
        wallThicknessMm: thicknessMm,
        wallHeightMm: heightMm,
        wall3dColor: color3d,
      });
    }
  }

  const selectedId = selectedWallStyle.value?.id;
  const isGroupEdit = !!selectedWallStyle.value?.isGroupEdit;
  if (selectedId) {
    if (entityType === "hidden") {
      if (!isGroupEdit && Number.isFinite(lengthMm)) editorRef.value?.setSelectedHiddenLength?.(lengthMm);
    } else if (entityType === "beam" || entityType === "column") {
      editorRef.value?.setSelectedBeamStyle?.({ thicknessMm, heightMm, fillColor: color3d, floorOffsetMm });
      if (!isGroupEdit && Number.isFinite(lengthMm)) editorRef.value?.setSelectedBeamLength?.(lengthMm);
    } else {
      editorRef.value?.setSelectedWallStyle?.({ thicknessMm, heightMm, floorOffsetMm, fillColor: color3d });
      if (!isGroupEdit && Number.isFinite(lengthMm)) editorRef.value?.setSelectedWallLength?.(lengthMm);
    }
  }
  wallStyleDraftTouched.value = false;
}



function updateSelectedWallCoords(patch) {
  const toMm = (v) => Number(v) * 10;
  const entityType = selectedWallStyle.value?.entityType || "wall";
  const dxMm = Number.isFinite(Number(patch?.dxCm)) ? toMm(patch.dxCm) : null;
  const dyMm = Number.isFinite(Number(patch?.dyCm)) ? toMm(patch.dyCm) : null;
  if (dxMm !== null || dyMm !== null) {
    if (entityType === "hidden") {
      editorRef.value?.moveSelectedHiddenWallsBy?.({
        dxMm: dxMm ?? 0,
        dyMm: dyMm ?? 0,
      });
    } else if (entityType === "beam") {
      if (editorRef.value?.moveSelectedBeamsBy) {
        editorRef.value.moveSelectedBeamsBy({ dxMm: dxMm ?? 0, dyMm: dyMm ?? 0 });
      } else {
        editorRef.value?.moveSelectedWallsBy?.({ dxMm: dxMm ?? 0, dyMm: dyMm ?? 0 });
      }
    } else {
      editorRef.value?.moveSelectedWallsBy?.({
        dxMm: dxMm ?? 0,
        dyMm: dyMm ?? 0,
      });
    }
    return;
  }

  const payload = {};
  if (Number.isFinite(Number(patch?.axCm))) payload.axMm = toMm(patch.axCm);
  if (Number.isFinite(Number(patch?.ayCm))) payload.ayMm = toMm(patch.ayCm);
  if (Number.isFinite(Number(patch?.bxCm))) payload.bxMm = toMm(patch.bxCm);
  if (Number.isFinite(Number(patch?.byCm))) payload.byMm = toMm(patch.byCm);
  if (entityType === "hidden") editorRef.value?.setSelectedHiddenCoords?.(payload);
  else if (entityType === "beam") editorRef.value?.setSelectedBeamCoords?.(payload);
  else editorRef.value?.setSelectedWallCoords?.(payload);
}


async function doCopyWallsJson() {
  const full = editorRef.value?.getState?.();
  const nodes = Array.isArray(full?.graphSnap?.nodes) ? full.graphSnap.nodes : [];
  const walls = Array.isArray(full?.graphSnap?.walls) ? full.graphSnap.walls : [];
  const payload = {
    exportedAt: new Date().toISOString(),
    unit: "mm",
    wallsCount: walls.length,
    nodesCount: nodes.length,
    nodes,
    walls,
  };
  const text = JSON.stringify(payload, null, 2);

  try {
    await navigator.clipboard.writeText(text);
    showAlert("JSON دیوارها کپی شد. لطفا برای من ارسال کنید.", { title: "کپی موفق" });
  } catch (_) {
    await showPrompt("کپی خودکار ممکن نبود. متن زیر را دستی کپی کنید:", text, { title: "کپی JSON دیوارها" });
  }
}

function toggleQuickMenu(menuId) {
  closeMenuPanel();
  quickMenuOpen.value = quickMenuOpen.value === menuId ? null : menuId;
}

function closeQuickMenus() {
  quickMenuOpen.value = null;
}

function toggleDimensions() {
  closeMenuPanel();
  const next = !showDimensions.value;
  showDimensions.value = next;
  applyEditorPatch({ showDimensions: next });
}

function toggleOffsets() {
  closeMenuPanel();
  const next = !showOffsetWalls.value;
  showOffsetWalls.value = next;
  applyEditorPatch({ offsetWallEnabled: next });
}

function toggleObjectAxes() {
  closeMenuPanel();
  const next = !showObjectAxes.value;
  showObjectAxes.value = next;
  applyEditorPatch({ showObjectAxes: next });
}

function toggleSnapMaster() {
  closeMenuPanel();
  const next = !isAnySnapModeOn.value;
  snapOn.value = next;
  editorRef.value?.setSnapOn?.(next);
  snapModes.value = { corner: next, mid: next, center: next, edge: next, wallMagnet: next, ortho: next };
  applyEditorPatch({
    snapOn: next,
    snapCornerEnabled: next,
    snapMidEnabled: next,
    snapCenterEnabled: next,
    snapEdgeEnabled: next,
    wallMagnetEnabled: next,
    orthoEnabled: next,
  });
}

function toggleSnapMode(id) {
  closeMenuPanel();
  const next = !snapModes.value[id];
  snapModes.value = { ...snapModes.value, [id]: next };
  const patch = {};
  if (id === "corner") patch.snapCornerEnabled = next;
  else if (id === "mid") patch.snapMidEnabled = next;
  else if (id === "center") patch.snapCenterEnabled = next;
  else if (id === "edge") patch.snapEdgeEnabled = next;
  else if (id === "wallMagnet") patch.wallMagnetEnabled = next;
  else if (id === "ortho") patch.orthoEnabled = next;

  const anyOn = Object.values(snapModes.value).some(Boolean);
  snapOn.value = anyOn;
  patch.snapOn = anyOn;
  applyEditorPatch(patch);
}

function toggleStepMaster() {
  closeMenuPanel();
  const next = !isAnyStepModeOn.value;
  const modes = { line: next, degree: next };
  stepModes.value = modes;
  applyEditorPatch(getStepPatch(modes));
}

function toggleStepMode(id) {
  closeMenuPanel();
  const next = !stepModes.value[id];
  const modes = { ...stepModes.value, [id]: next };
  stepModes.value = modes;
  applyEditorPatch(getStepPatch(modes));
}

function loadProjects() {
  try {
    const raw = localStorage.getItem(STORAGE_PROJECTS_KEY);
    if (!raw) return;
    const arr = JSON.parse(raw);
    if (Array.isArray(arr)) projects.value = arr;
  } catch (_) {}
}
function saveProjects() {
  try {
    localStorage.setItem(STORAGE_PROJECTS_KEY, JSON.stringify(projects.value));
  } catch (_) {}
}
loadProjects();

function getEditorState() {
  try {
    return editorRef.value?.getState?.() || null;
  } catch (_) {
    return null;
  }
}
function isEditorEmpty() {
  const s = getEditorState();
  if (!s) return true;
  // Expect shape from wall_app.js getState()
  const hasWalls = (s?.graphSnap?.walls?.length || 0) > 0;
  const hasHidden = (s?.hiddenGraphSnap?.walls?.length || 0) > 0;
  const hasDims = (s?.dimensions?.length || 0) > 0;
  return !(hasWalls || hasHidden || hasDims);
}

async function doNewDesign() {
  if (!editorRef.value) return;
  if (!isEditorEmpty()) {
    const ok = await showConfirm("طرح فعلی ذخیره نشده است. بدون ذخیره پاک شود؟", { title: "طرح جدید" });
    if (!ok) return;
  }
  editorRef.value.clearAll?.();
  editorRef.value.goOrigin?.();
}

async function doSaveProject() {
  if (!editorRef.value) return;
  const state = getEditorState();
  if (!state) return;
  const rawName = await showPrompt("نام طرح را وارد کنید:", "طرح جدید", { title: "ذخیره طرح" });
  const name = (rawName || "").trim();
  if (!name) return;
  const id = `${Date.now()}_${Math.random().toString(16).slice(2)}`;
  projects.value.unshift({ id, name, ts: Date.now(), state });
  projects.value = projects.value.slice(0, 50);
  saveProjects();
}

function doOpenPicker() {
  openMode.value = "open";
}
function doOpenProject(p) {
  if (!editorRef.value?.setState || !p?.state) return;
  editorRef.value.setState(p.state);
  syncQuickStateFromEditor();
  openMode.value = "menu";
}
async function doRenameProject(p) {
  const current = String(p?.name || "");
  const raw = await showPrompt("نام جدید طرح:", current, { title: "تغییر نام طرح" });
  if (raw == null) return;
  const nextName = String(raw || "").trim();
  if (!nextName || nextName === current) return;
  projects.value = projects.value.map((x) => (x.id === p.id ? { ...x, name: nextName } : x));
  saveProjects();
}

async function doDeleteProject(p) {
  const ok = await showConfirm(`طرح «${p?.name || "بدون نام"}» حذف شود؟`, { title: "حذف طرح" });
  if (!ok) return;
  projects.value = projects.value.filter((x) => x.id !== p.id);
  saveProjects();
}

async function doExportJsonToClipboard() {
  const s = getEditorState();
  if (!s) return;
  const txt = JSON.stringify(s);
  try {
    await navigator.clipboard.writeText(txt);
    showAlert("خروجی JSON در کلیپ‌بورد کپی شد.", { title: "خروجی" });
  } catch (_) {
    await showPrompt("کپی خودکار انجام نشد. متن زیر را کپی کنید:", txt, { title: "خروجی" });
  }
}

function doPrint() {
  window.print();
}

function doMessages() {
  showAlert("پیام‌ها: به زودی.", { title: "پیام‌ها" });
}

function openMenuPanelAt(menuId, anchorEl, mode = "menu") {
  activeMenu.value = menuId;
  openMenuPanel.value = menuId;
  openMode.value = mode;
  if (anchorEl) scheduleMenuPanelPosition(anchorEl);
  scheduleSubRailPosition();
}

function doOpenFromTopbar() {
  // Open the main menu directly in "open" mode (online/localStorage picker).
  openMenuPanelAt("menu", mainMenuBtnEl.value, "open");
}
function doSaveFromTopbar() {
  // Keep the main menu closed; just save the current state (online/localStorage).
  doSaveProject();
}
function doShareFromTopbar() {
  // Share = export JSON to clipboard (for now).
  doExportJsonToClipboard();
}
function doServicesFromTopbar() {
  showAlert("سفارش خدمات برش: به زودی.", { title: "خدمات" });
}
function doBuyFromTopbar() {
  showAlert("سفارش پیش ساخته: به زودی.", { title: "خرید" });
}

function doZoomIn() {
  editorRef.value?.zoomIn?.();
}
function doZoomOut() {
  editorRef.value?.zoomOut?.();
}
function doSeeAll() {
  editorRef.value?.fitView?.();
}
function doSeeOrigin() {
  editorRef.value?.goOrigin?.();
}

async function setTool(tool) {
  activeTool.value = tool;

  const isDrawingTool = tool === "wall" || tool === "hidden" || tool === "dimension" || tool === "beam";
  if (route.path !== "/" && isDrawingTool) {
    await router.push("/");
  }

  if (tool === "wall") editorRef.value?.setActiveTool?.("wall");
  else if (tool === "hidden") editorRef.value?.setActiveTool?.("hidden");
  else if (tool === "dimension") editorRef.value?.setActiveTool?.("dim");
  else if (tool === "beam") editorRef.value?.setActiveTool?.("beam");
}

async function setDesignMenuTool(id) {
  designMenuTool.value = id;
  const it = designMenuTools.find((x) => x.id === id);
  if (it?.mapsToTool) await setTool(it.mapsToTool);
  else if (id === "column") await setTool("select");

  const mode =
    (id === "wall") ? "wall" :
    (id === "hidden") ? "hidden" :
    (id === "dimension") ? "dim" :
    (id === "beam") ? "beam" :
    null;
  editorRef.value?.setUiCursorMode?.(mode);

  if (id === "beam") {
    const st = editorRef.value?.getState?.()?.state || {};
    wallStyleDraftTouched.value = false;
    wallStyleDraft.value = {
      thicknessCm: (Number.isFinite(Number(st?.beamThicknessMm)) ? Number(st.beamThicknessMm) : 400) / 10,
      heightCm: (Number.isFinite(Number(st?.beamHeightMm)) ? Number(st.beamHeightMm) : 200) / 10,
      floorOffsetCm: (Number.isFinite(Number(st?.beamFloorOffsetMm)) ? Number(st.beamFloorOffsetMm) : 2600) / 10,
      color: String(st?.beam3dColor || st?.wall3dColor || "#C7CCD1"),
    };
  } else if (id === "column") {
    const st = editorRef.value?.getState?.()?.state || {};
    wallStyleDraftTouched.value = false;
    wallStyleDraft.value = {
      thicknessCm: (Number.isFinite(Number(st?.columnDepthMm)) ? Number(st.columnDepthMm) : 400) / 10,
      heightCm: (Number.isFinite(Number(st?.columnHeightMm)) ? Number(st.columnHeightMm) : 2800) / 10,
      floorOffsetCm: 0,
      color: String(st?.column3dColor || "#C7CCD1"),
      lengthCm: (Number.isFinite(Number(st?.columnWidthMm)) ? Number(st.columnWidthMm) : 500) / 10,
    };
  } else if (id === "wall") {
    const st = editorRef.value?.getState?.()?.state || {};
    wallStyleDraftTouched.value = false;
    wallStyleDraft.value = {
      thicknessCm: (Number.isFinite(Number(st?.wallThicknessMm)) ? Number(st.wallThicknessMm) : 120) / 10,
      heightCm: (Number.isFinite(Number(st?.wallHeightMm)) ? Number(st.wallHeightMm) : 3000) / 10,
      floorOffsetCm: 0,
      color: String(st?.wall3dColor || "#C7CCD1"),
    };
  }
}

function doUndo() {
  editorRef.value?.undo?.();
}
function doRedo() {
  editorRef.value?.redo?.();
}

function goHome() {
  router.push("/");
}
function goSettings() {
  closeQuickMenus();
  closeMenuPanel();
  activeSubRail.value = null;
  router.push("/settings");
}


watch(
  () => route.path,
  (path) => {
    if (path !== "/settings") return;
    // Settings page keeps global menus/toolbars visible, but submenus must start closed.
    closeQuickMenus();
    closeMenuPanel();
    activeSubRail.value = null;
    drawUiLock.value = false;
  },
  { immediate: true }
);

function setMenu(menuId) {
  activeMenu.value = menuId;
  openMenuPanel.value = menuId;
}

function closeMenuPanel() {
  openMenuPanel.value = null;
  activeMenu.value = null;
  activeSubRail.value = null;
  openMode.value = "menu";
  editorRef.value?.setInputEnabled?.(true);
  scheduleSubRailPosition();
}

function disable2dInput() {
  editorRef.value?.setInputEnabled?.(false);
}
function enable2dInput() {
  editorRef.value?.setInputEnabled?.(true);
}

function onGlbModel2d(payload) {
  const lines = payload?.lines;
  if (!Array.isArray(lines)) return;
  editorRef.value?.setModel2dLines?.(lines, payload?.opts || null);
}

function startWallPresetDrag(ev, preset) {
  if (!preset || !ev?.isPrimary) return;
  presetDrag.value = {
    active: true,
    preset,
    clientX: ev.clientX,
    clientY: ev.clientY,
    startX: ev.clientX,
    startY: ev.clientY,
    enteredStage: false,
  };
  disable2dInput();
  window.addEventListener("pointermove", onPresetPointerMove);
  window.addEventListener("pointerup", onPresetPointerUp, { once: true });
}

function onPresetPointerMove(ev) {
  if (!presetDrag.value.active) return;
  const stageRect = stageEl.value?.getBoundingClientRect();
  const inStage = !!stageRect
    && ev.clientX >= stageRect.left && ev.clientX <= stageRect.right
    && ev.clientY >= stageRect.top && ev.clientY <= stageRect.bottom;
  presetDrag.value = {
    ...presetDrag.value,
    clientX: ev.clientX,
    clientY: ev.clientY,
    enteredStage: presetDrag.value.enteredStage || inStage,
  };
}

function startColumnPresetDrag(ev) {
  if (!ev?.isPrimary) return;
  startWallPresetDrag(ev, { id: "column", title: "ستون", kind: "column", type: "column" });
}

function onDesignToolPointerDown(it, ev) {
  if (!it || it.id !== "column") return;
  setDesignMenuTool("column");
  startColumnPresetDrag(ev);
}

function isColumnPreset(preset) {
  return String(preset?.type || "").toLowerCase() === "column" || String(preset?.kind || "").toLowerCase() === "column";
}

function onPresetPointerUp(ev) {
  const stageRect = stageEl.value?.getBoundingClientRect();
  const inStage = !!stageRect && ev.clientX >= stageRect.left && ev.clientX <= stageRect.right
    && ev.clientY >= stageRect.top && ev.clientY <= stageRect.bottom;
  const dragDx = ev.clientX - (presetDrag.value.startX || ev.clientX);
  const dragDy = ev.clientY - (presetDrag.value.startY || ev.clientY);
  const movedEnough = Math.hypot(dragDx, dragDy) >= 12;

  const preset = presetDrag.value.preset;
  const isColumnDrop = isColumnPreset(preset);
  const columnEnteredStage = !!presetDrag.value.enteredStage;
  const shouldPlaceColumn = !!preset && isColumnDrop && (inStage || columnEnteredStage);
  const shouldPlaceWallPreset = !!preset && !isColumnDrop && inStage && movedEnough && presetDrag.value.enteredStage;

  if (shouldPlaceColumn) {
    const dropX = inStage ? ev.clientX : presetDrag.value.clientX;
    const dropY = inStage ? ev.clientY : presetDrag.value.clientY;
    editorRef.value?.placeColumnAtClient?.(dropX, dropY);
  } else if (shouldPlaceWallPreset) {
    const lines = buildPresetLines(preset.kind);
    if (designMenuTool.value === "beam" && editorRef.value?.placeBeamPresetAtClient) {
      editorRef.value.placeBeamPresetAtClient(lines, ev.clientX, ev.clientY);
    } else {
      editorRef.value?.placeWallPresetAtClient?.(lines, ev.clientX, ev.clientY);
    }
  }
  presetDrag.value = { active: false, preset: null, clientX: 0, clientY: 0, startX: 0, startY: 0, enteredStage: false };
  window.removeEventListener("pointermove", onPresetPointerMove);
  enable2dInput();
}

function toggleMenu(menuId, e) {
  // While drawing, keep submenus closed (AutoCAD-like).
  if (drawUiLock.value && route.path === "/") return;
  if (openMenuPanel.value === menuId) {
    openMenuPanel.value = null;
    activeMenu.value = null;
    activeSubRail.value = null;
    openMode.value = "menu";
    scheduleSubRailPosition();
    return;
  }
  setMenu(menuId);
  if (e?.currentTarget) scheduleMenuPanelPosition(e.currentTarget);
  // If the panel is already open, keep the rail aligned even if positioning doesn't change.
  scheduleSubRailPosition();
}

let _menuRaf = 0;
function scheduleMenuPanelPosition(anchorEl) {
  if (!mainEl.value || !anchorEl) return;
  if (_menuRaf) cancelAnimationFrame(_menuRaf);
  _menuRaf = requestAnimationFrame(() => {
    _menuRaf = 0;
    positionMenuPanel(anchorEl);
    // After panel top is adjusted, align the sub-rail to the panel.
    positionSubRail();
  });
}

function positionMenuPanel(anchorEl) {
  if (!mainEl.value || !menuPanelEl.value || !anchorEl) return;
  const mainRect = mainEl.value.getBoundingClientRect();
  const a = anchorEl.getBoundingClientRect();

  // First pass: place top aligned to the clicked button.
  let top = a.top - mainRect.top;
  // Clamp after measuring panel height.
  const p = menuPanelEl.value.getBoundingClientRect();
  const pad = 10;
  const maxTop = Math.max(pad, mainRect.height - p.height - pad);
  top = Math.max(pad, Math.min(maxTop, top));
  mainEl.value.style.setProperty("--menuPanelTop", `${Math.round(top)}px`);
}

let _subRaf = 0;
function scheduleSubRailPosition() {
  if (_subRaf) cancelAnimationFrame(_subRaf);
  _subRaf = requestAnimationFrame(() => {
    _subRaf = 0;
    positionSubRail();
  });
}

function positionSubRail() {
  if (!mainEl.value) return;
  if (!shouldShowSubRail.value) return;
  const mainRect = mainEl.value.getBoundingClientRect();
  const pad = 10;
  let top = pad;
  let right = null;
  const gapPanel = 6; // small visual gap between design toolbar and submenu panel
  const gapMain = 0;  // when no menu is open: hug the 2D stage edge (user request)

  if (openMenuPanel.value && allowedSubRailMenus.has(openMenuPanel.value) && menuPanelEl.value) {
    // Align to the opened submenu panel.
    const p = menuPanelEl.value.getBoundingClientRect();
    top = p.top - mainRect.top;
    // Stick to the panel's left edge (works even when the panel is shrink-wrapped).
    right = (mainRect.right - p.left) + gapPanel;
  } else if (stageEl.value) {
    // No submenu open: stick to the 2D stage's right edge (flush with canvas area).
    const s = stageEl.value.getBoundingClientRect();
    right = (mainRect.right - s.right) + gapMain;
  } else if (mainMenuBtnEl.value) {
    // No submenu open: stick to the main menu icon.
    const a = mainMenuBtnEl.value.getBoundingClientRect();
    top = a.top - mainRect.top;
    right = (mainRect.right - a.left) + gapPanel;
  }

  top = Math.max(pad, Math.min(mainRect.height - pad - 10, top));
  mainEl.value.style.setProperty("--subRailTop", `${Math.round(top)}px`);
  if (typeof right === "number" && isFinite(right)) {
    // Clamp so it never goes off-screen to the left.
    right = Math.max(pad, Math.min(mainRect.width - pad - 10, right));
    mainEl.value.style.setProperty("--subRailRight", `${Math.round(right)}px`);
  } else {
    mainEl.value.style.removeProperty("--subRailRight");
  }
}

function setSubRail(id) {
  activeSubRail.value = id;
  // Selecting a design toolbar item behaves like opening the Design menu.
  activeMenu.value = "design";
  openMenuPanel.value = "design";
  openMode.value = "menu";
  if (designBtnEl.value) scheduleMenuPanelPosition(designBtnEl.value);
  scheduleSubRailPosition();
}

let _ro = null;
let _raf = 0;
let _shiftPx = 0;
let _quickSyncTimer = 0;
let _quickOutsidePointerDown = null;
function updateTopbarShift() {
  if (!topbarEl.value || !homeBtnEl.value) return;
  const stageHost = stageCardEl.value || stageEl.value;
  if (!stageHost) return;
  const stageRect = stageHost.getBoundingClientRect();
  const homeRect = homeBtnEl.value.getBoundingClientRect();
  const stageCenterX = stageRect.left + stageRect.width / 2;
  const homeCenterX = homeRect.left + homeRect.width / 2;
  const delta = stageCenterX - homeCenterX;

  // Additive update to avoid dependency on current CSS shift.
  _shiftPx = (_shiftPx || 0) + delta;
  // Clamp to something sane (prevents runaway if DOM is temporarily weird).
  _shiftPx = Math.max(-800, Math.min(800, _shiftPx));
  topbarEl.value.style.setProperty("--shiftPx", `${_shiftPx}px`);
}

function scheduleShift() {
  if (_raf) cancelAnimationFrame(_raf);
  _raf = requestAnimationFrame(() => {
    _raf = 0;
    updateTopbarShift();
  });
}

onMounted(() => {
  window.__designkpDialogs = {
    alert: (msg, opts) => showAlert(msg, opts),
    confirm: (msg, opts) => showConfirm(msg, opts),
    prompt: (msg, defaultValue, opts) => showPrompt(msg, defaultValue, opts),
  };
  // Run twice to settle after first layout.
  scheduleShift();
  setTimeout(scheduleShift, 0);
  scheduleSubRailPosition();
  syncQuickStateFromEditor();
  _quickSyncTimer = window.setInterval(syncQuickStateFromEditor, 350);

  _quickOutsidePointerDown = (e) => {
    const el = e.target;
    if (!(el instanceof Element)) return;
    if (el.closest(".stageQuickBar")) return;
    closeQuickMenus();
  };
  window.addEventListener("pointerdown", _quickOutsidePointerDown, true);

  window.addEventListener("resize", scheduleShift);
  window.addEventListener("resize", scheduleSubRailPosition);
  if (typeof ResizeObserver !== "undefined" && stageEl.value) {
    _ro = new ResizeObserver(() => scheduleShift());
    _ro.observe(stageEl.value);
  }

  const onEsc = (e) => {
    if (String(e.key || "") !== "Escape") return;
    const t = e.target;
    const tag = (t?.tagName || "").toUpperCase();
    if (t?.isContentEditable || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    // If we were drawing, the first Esc ends drawing (engine handles it) and re-opens Design menu.
    // The next Esc (when not drawing) closes all menus and clears selection.
    if (drawUiLock.value) {
      drawUiLock.value = false;
      openMode.value = "menu";
      activeMenu.value = "design";
      openMenuPanel.value = "design";
      if (designBtnEl.value) scheduleMenuPanelPosition(designBtnEl.value);
      scheduleSubRailPosition();
      // Also clear focus so browser focus-ring doesn't look like a "selection".
      try { document.activeElement?.blur?.(); } catch (_) {}
      return;
    }

    // Reset UI selection state: menus closed and icons unselected.
    openMenuPanel.value = null;
    activeMenu.value = null;
    activeSubRail.value = null;
    designMenuTool.value = null;
    editorRef.value?.setUiCursorMode?.(null);
    editorRef.value?.setActiveTool?.("select");
    openMode.value = "menu";
    editorRef.value?.setInputEnabled?.(true);
    // Also clear focus so browser focus-ring doesn't look like a "selection".
    try {
      document.activeElement?.blur?.();
    } catch (_) {}
    scheduleSubRailPosition();
  };
  window.addEventListener("keydown", onEsc, true);
  // store for cleanup
  window.__designkpOnEsc = onEsc;

  function getDrawingStatus() {
    const st = editorRef.value?.getState?.();
    const tool = st?.state?.activeTool;
    const tools = st?.tools || null;
    const isDrawing =
      (tool === "wall") ? !!tools?.wall?.isDrawing :
      (tool === "hidden") ? !!tools?.hidden?.isDrawing :
      (tool === "dim") ? !!tools?.dim?.isDrawing :
      false;
    return { tool, isDrawing };
  }

  function syncLocksOnReturn() {
    // If we left while hovering a menu, mouseleave may not fire; force-enable input.
    editorRef.value?.setInputEnabled?.(true);
    const { isDrawing } = getDrawingStatus();
    if (!isDrawing) drawUiLock.value = false;
  }

  const onFocus = () => syncLocksOnReturn();
  const onVisibilityChange = () => {
    if (!document.hidden) syncLocksOnReturn();
  };
  const onBlur = () => {
    // Defensive: don't leave the engine in a permanently disabled-input state.
    editorRef.value?.setInputEnabled?.(true);
  };

  window.addEventListener("focus", onFocus, true);
  window.addEventListener("blur", onBlur, true);
  document.addEventListener("visibilitychange", onVisibilityChange, true);
  window.__designkpOnFocus = onFocus;
  window.__designkpOnBlur = onBlur;
  window.__designkpOnVis = onVisibilityChange;

  // Keep UI closed while a draw command is active. We intentionally do not auto-unlock;
  // Esc controls the state machine (AutoCAD-like).
  let _drawLockRaf = 0;
  const drawLockLoop = () => {
    _drawLockRaf = requestAnimationFrame(drawLockLoop);

    const { isDrawing } = getDrawingStatus();
    if (isDrawing && !drawUiLock.value) {
      drawUiLock.value = true;
      openMenuPanel.value = null;
      activeMenu.value = null;
      openMode.value = "menu";
      scheduleSubRailPosition();
      return;
    }

    // If we're locked, keep submenus closed even if something tries to open them.
    if (drawUiLock.value && openMenuPanel.value) {
      openMenuPanel.value = null;
      activeMenu.value = null;
      openMode.value = "menu";
      scheduleSubRailPosition();
    }
  };
  _drawLockRaf = requestAnimationFrame(drawLockLoop);

  const onStagePointerDown = (ev) => {
    if (drawUiLock.value && route.path === "/") return;
    const el = ev.target;
    if (!(el instanceof Element)) return;
    // Only when clicking into the 2D canvas.
    if (!el.closest(".fpCanvas")) return;

    const before = getDrawingStatus();
    if (before.tool !== "wall" && before.tool !== "hidden" && before.tool !== "dim") return;

    // Only lock UI if the click actually starts/continues a draw command (not pan/zoom/select).
    setTimeout(() => {
      const after = getDrawingStatus();
      if (!after.isDrawing) return;

      drawUiLock.value = true;
      openMenuPanel.value = null;
      activeMenu.value = null;
      openMode.value = "menu";
      scheduleSubRailPosition();
    }, 0);
  };
  // Capture so it runs before inner handlers; we only read + close panels.
  window.addEventListener("pointerdown", onStagePointerDown, true);
  window.__designkpOnStagePointerDown = onStagePointerDown;
  window.__designkpDrawLockRaf = _drawLockRaf;
});

onBeforeUnmount(() => {
  window.removeEventListener("pointermove", onPresetPointerMove);
  if (window.__designkpDialogs) delete window.__designkpDialogs;
  window.removeEventListener("resize", scheduleShift);
  window.removeEventListener("resize", scheduleSubRailPosition);
  if (_quickSyncTimer) {
    clearInterval(_quickSyncTimer);
    _quickSyncTimer = 0;
  }
  if (_quickOutsidePointerDown) {
    window.removeEventListener("pointerdown", _quickOutsidePointerDown, true);
    _quickOutsidePointerDown = null;
  }
  if (_ro) _ro.disconnect();
  _ro = null;
  if (_raf) cancelAnimationFrame(_raf);
  _raf = 0;
  if (_menuRaf) cancelAnimationFrame(_menuRaf);
  _menuRaf = 0;
  if (_subRaf) cancelAnimationFrame(_subRaf);
  _subRaf = 0;
  if (window.__designkpOnEsc) {
    window.removeEventListener("keydown", window.__designkpOnEsc, true);
    delete window.__designkpOnEsc;
  }
  if (window.__designkpOnFocus) {
    window.removeEventListener("focus", window.__designkpOnFocus, true);
    delete window.__designkpOnFocus;
  }
  if (window.__designkpOnBlur) {
    window.removeEventListener("blur", window.__designkpOnBlur, true);
    delete window.__designkpOnBlur;
  }
  if (window.__designkpOnVis) {
    document.removeEventListener("visibilitychange", window.__designkpOnVis, true);
    delete window.__designkpOnVis;
  }
  if (window.__designkpOnStagePointerDown) {
    window.removeEventListener("pointerdown", window.__designkpOnStagePointerDown, true);
    delete window.__designkpOnStagePointerDown;
  }
  if (window.__designkpDrawLockRaf) {
    try { cancelAnimationFrame(window.__designkpDrawLockRaf); } catch (_) {}
    delete window.__designkpDrawLockRaf;
  }
});
</script>

<template>
  <div class="app">
    <header ref="topbarEl" class="topbar">
      <div class="topbar__leftIcons" aria-label="Quick Actions">
        <button class="iconbtn iconbtn--sm" title="پیام ها" @click="doMessages">
          <img src="/icons/notification.png" alt="" />
        </button>
        <button class="iconbtn iconbtn--sm" title="ذخیره" @click="doSaveFromTopbar">
          <img src="/icons/save.png" alt="" />
        </button>
        <button class="iconbtn iconbtn--sm" title="باز کردن" @click="doOpenFromTopbar">
          <img src="/icons/open.png" alt="" />
        </button>
        <button class="iconbtn iconbtn--sm" title="اشتراک گذاری" @click="doShareFromTopbar">
          <img src="/icons/share.png" alt="" />
        </button>
        <button class="iconbtn iconbtn--sm iconbtn--pop" title="سفارش خدمات برش" @click="doServicesFromTopbar">
          <img src="/icons/services.png" alt="" />
        </button>
        <button class="iconbtn iconbtn--sm iconbtn--pop" title="سفارش پیش ساخته" @click="doBuyFromTopbar">
          <img src="/icons/buy.png" alt="" />
        </button>
      </div>

      <div class="topbar__icons" aria-label="Top Icons">
        <button class="iconbtn" :class="{ 'is-active': isSettings }" title="تنظیمات" @click="goSettings">
          <img src="/icons/setting.png" alt="" />
        </button>
        <button class="iconbtn" title="چسباندن">
          <img src="/icons/paste.png" alt="" />
        </button>
        <button class="iconbtn" title="کپی">
          <img src="/icons/copy.png" alt="" />
        </button>
        <button class="iconbtn" title="لایه ها">
          <img src="/icons/layers.png" alt="" />
        </button>
        <button class="iconbtn" title="بازگردانی" @click="doUndo">
          <img src="/icons/undo.png" alt="" />
        </button>
        <button ref="homeBtnEl" class="iconbtn" :class="{ 'is-active': isHome }" title="خانه" @click="goHome">
          <img src="/icons/home.png" alt="" />
        </button>
        <button class="iconbtn" title="باز انجام" @click="doRedo">
          <img src="/icons/redo.png" alt="" />
        </button>
        <button class="iconbtn" title="درب">
          <img src="/icons/door_styles.png" alt="" />
        </button>
        <button class="iconbtn" title="داخلی">
          <img src="/icons/enternal.png" alt="" />
        </button>
        <button class="iconbtn" title="سه بعدی">
          <img src="/icons/3d_viewer.png" alt="" />
        </button>
        <button class="iconbtn" title="شیت بندی">
          <img src="/icons/sheet.png" alt="" />
        </button>
      </div>

      <!-- App logo aligned with the fixed right rail column -->
      <button type="button" class="topbar__railLogo" title="DesignKP">
        <img src="/icons/LOGO.png" alt="DesignKP" />
      </button>
    </header>

    <div ref="mainEl" class="main">
      <!-- Slim left-of-submenu rail (always visible; attaches to submenu when open, else to main menu icon) -->
      <aside
        v-if="shouldShowSubRail"
        class="subRail"
        :class="subRailAttach === 'panel' ? 'subRail--panel' : 'subRail--main'"
        aria-label="Sub Rail"
        @mouseenter="disable2dInput"
        @mouseleave="enable2dInput"
      >
        <button
          v-for="it in subRailItems"
          :key="it.id"
          type="button"
          class="subTool"
          :class="{ 'is-active': activeSubRail === it.id }"
          :title="it.title"
          @click="setSubRail(it.id)"
        >
          <img :src="it.icon" alt="" />
        </button>
      </aside>

      <!-- Right-side menu content opens as an overlay above the 2D stage (does not push anything). -->
      <aside
        ref="menuPanelEl"
        v-if="openMenuPanel"
        class="menuPanel"
        :class="{ 'menuPanel--auto': openMenuPanel === 'menu' && openMode === 'menu' }"
        aria-label="Menu Panel"
        @mouseenter="disable2dInput"
        @mouseleave="enable2dInput"
      >
        <div class="menuPanel__head">
          <div class="menuPanel__titleRow">
            <img v-if="openMenuIcon" class="menuPanel__icon" :src="openMenuIcon" alt="" />
            <div class="menuPanel__title">{{ openMenuTitle }}</div>
          </div>
          <button type="button" class="menuPanel__close" title="بستن" @click="closeMenuPanel">×</button>
        </div>
        <div class="menuPanel__body">
          <!-- Main menu content -->
          <template v-if="openMenuPanel === 'menu'">
            <div v-if="openMode === 'menu'" class="menuList">
              <button class="menuItem" type="button" @click="doNewDesign">طرح جدید</button>
              <button class="menuItem" type="button" @click="doOpenPicker">باز کردن</button>
              <button class="menuItem" type="button" @click="doSaveProject">ذخیره</button>
              <button class="menuItem" type="button" @click="doExportJsonToClipboard">خروجی</button>
              <button class="menuItem" type="button" @click="doPrint">پرینت</button>
              <button class="menuItem" type="button" @click="goSettings">تنظیمات</button>
              <button class="menuItem" type="button" @click="setMenu('profile')">حساب کاربری</button>
              <button class="menuItem" type="button" @click="doMessages">پیام ها</button>
            </div>

            <div v-else class="menuList">
              <div class="menuPanel__hint">طرح‌های ذخیره‌شده (آنلاین/LocalStorage)</div>
              <div v-if="projects.length === 0" class="menuPanel__hint">هیچ طرحی ذخیره نشده.</div>
              <div v-for="p in projects" :key="p.id" class="menuRow">
                <button class="menuItem menuItem--grow" type="button" @click="doOpenProject(p)">
                  {{ p.name }}
                </button>
                <button class="menuItem" type="button" title="تغییر نام" @click="doRenameProject(p)">
                  نام
                </button>
                <button class="menuItem menuItem--danger" type="button" title="حذف" @click="doDeleteProject(p)">
                  حذف
                </button>
              </div>
              <button class="menuItem" type="button" @click="openMode='menu'">بازگشت</button>
            </div>
          </template>

          <template v-else-if="openMenuPanel === 'design'">
            <div class="designMenu">
              <div class="designMenu__grid" aria-label="Design Tools Grid">
                <button
                  v-for="it in designMenuTools"
                  :key="it.id"
                  type="button"
                  class="designToolBtn"
                  :class="{ 'is-active': designMenuTool === it.id }"
                  :title="it.title"
                  @pointerdown="onDesignToolPointerDown(it, $event)"
                  @click="setDesignMenuTool(it.id)"
                >
                  <img :src="it.icon" alt="" />
                </button>
                <!-- keep 2x3 grid: add one empty cell -->
                <div class="designToolBtn designToolBtn--empty" aria-hidden="true"></div>
              </div>

              <div class="designMenu__sep" role="separator"></div>

              <div class="designMenu__presetsHead">مدل های دیوار</div>
              <div class="designMenu__presets" aria-label="Wall Presets">
                <button
                  v-for="p in wallPresets"
                  :key="p.id"
                  type="button"
                  class="presetTile"
                  :title="p.title"
                  @pointerdown.prevent="startWallPresetDrag($event, p)"
                >
                  <svg class="presetTile__svg" viewBox="0 0 44 44" aria-hidden="true">
                    <g fill="none" stroke="#111827" stroke-linecap="square" stroke-linejoin="miter">
                      <line
                        v-for="(w,idx) in getPresetIconWalls(p.kind)"
                        :key="`edge-${p.id}-${idx}`"
                        :x1="w.x1"
                        :y1="w.y1"
                        :x2="w.x2"
                        :y2="w.y2"
                        :stroke-width="w.sw + 1.5"
                      />
                    </g>
                    <g fill="none" stroke="#A6A6A6" stroke-linecap="square" stroke-linejoin="miter">
                      <line
                        v-for="(w,idx) in getPresetIconWalls(p.kind)"
                        :key="`fill-${p.id}-${idx}`"
                        :x1="w.x1"
                        :y1="w.y1"
                        :x2="w.x2"
                        :y2="w.y2"
                        :stroke-width="w.sw"
                      />
                    </g>
                  </svg>
                </button>
              </div>
            </div>
          </template>

          <div v-else class="menuPanel__hint">محتوای این بخش در حال تکمیل است.</div>
        </div>
      </aside>

      <section ref="stageEl" class="stage">
        <div ref="stageCardEl" class="stage__card">
          <div v-if="showStageOverlays" class="stageQuickBar" @mouseenter="disable2dInput" @mouseleave="enable2dInput">
            <button
              class="iconbtn iconbtn--sm stageQuickBar__btn"
              :class="{ 'is-active': showDimensions }"
              title="نمایش اندازه گذاری"
              @click="toggleDimensions"
            >
              <img src="/icons/turn_dim.png" alt="" />
            </button>

            <button
              class="iconbtn iconbtn--sm stageQuickBar__btn"
              :class="{ 'is-active': showOffsetWalls }"
              title="نمایش خط راهنما"
              @click="toggleOffsets"
            >
              <img src="/icons/turn_offset.png" alt="" />
            </button>

            <button
              class="iconbtn iconbtn--sm stageQuickBar__btn"
              :class="{ 'is-active': showObjectAxes }"
              title="نمایش محور"
              @click="toggleObjectAxes"
            >
              <img src="/icons/ax_point.png" alt="" />
            </button>

            <!--
            <button
              class="iconbtn iconbtn--sm stageQuickBar__btn"
              title="کپی JSON دیوارها (تستی)"
              @click="doCopyWallsJson"
            >
              <img src="/icons/copy.png" alt="" />
            </button>
            -->

            <div class="stageQuickBar__ddWrap">
              <button
                class="iconbtn iconbtn--sm stageQuickBar__btn"
                :class="{ 'is-active': isAnySnapModeOn }"
                title="نمایش نقاط جذب"
                @click="toggleQuickMenu('snaps')"
              >
                <img src="/icons/turn_snaps.png" alt="" />
              </button>
              <div v-if="quickMenuOpen === 'snaps'" class="stageQuickDrop">
                <div class="stageQuickDrop__head">
                  <span>نقاط جذب</span>
                  <button type="button" class="stageQuickDrop__headBtn" @click="toggleSnapMaster">
                    {{ isAnySnapModeOn ? "خاموش کن" : "روشن کن" }}
                  </button>
                </div>
                <div
                  v-for="it in snapMenuItems"
                  :key="it.id"
                  class="stageQuickDrop__row"
                >
                  <div class="stageQuickDrop__label">
                    <img :src="it.icon" alt="" />
                    <span>{{ it.title }}</span>
                  </div>
                  <button
                    type="button"
                    class="snapToggle"
                    :class="{ 'is-on': snapModes[it.id] }"
                    @click="toggleSnapMode(it.id)"
                  >
                    <span class="snapToggle__knob"></span>
                  </button>
                </div>
              </div>
            </div>

            <div class="stageQuickBar__ddWrap">
              <button
                class="iconbtn iconbtn--sm stageQuickBar__btn"
                :class="{ 'is-active': isAnyStepModeOn }"
                title="رسم گام یه گام"
                @click="toggleQuickMenu('steps')"
              >
                <img src="/icons/step_by_step.png" alt="" />
              </button>
              <div v-if="quickMenuOpen === 'steps'" class="stageQuickDrop stageQuickDrop--steps" @click.stop>
                <div class="stageQuickDrop__head">
                  <span>رسم گام به گام</span>
                  <button type="button" class="stageQuickDrop__headBtn" @click.stop="toggleStepMaster">
                    {{ isAnyStepModeOn ? "خاموش کن" : "روشن کن" }}
                  </button>
                </div>
                <div class="stageQuickDrop__row">
                  <div class="stageQuickDrop__label">
                    <img src="/icons/step_line.png" alt="" />
                    <span>خط</span>
                  </div>
                  <button
                    type="button"
                    class="snapToggle"
                    :class="{ 'is-on': stepModes.line }"
                    @click.stop="toggleStepMode('line')"
                  >
                    <span class="snapToggle__knob"></span>
                  </button>
                </div>
                <div class="stageQuickDrop__row">
                  <div class="stageQuickDrop__label">
                    <img src="/icons/step_degree.png" alt="" />
                    <span>زاویه</span>
                  </div>
                  <button
                    type="button"
                    class="snapToggle"
                    :class="{ 'is-on': stepModes.degree }"
                    @click.stop="toggleStepMode('degree')"
                  >
                    <span class="snapToggle__knob"></span>
                  </button>
                </div>
              </div>
            </div>
          </div>

          <RouterView v-slot="{ Component }">
            <KeepAlive>
              <component :is="Component" />
            </KeepAlive>
          </RouterView>

          <div
            v-if="presetDrag.active"
            class="presetDragGhost"
            :style="{ left: `${presetDrag.clientX}px`, top: `${presetDrag.clientY}px` }"
            aria-hidden="true"
          >
            <img v-if="isColumnPreset(presetDrag.preset)" class="presetDragGhost__icon" src="/icons/column.png" alt="" />
            <svg v-else class="presetDragGhost__svg" viewBox="0 0 44 44">
              <g fill="none" stroke="#111827" stroke-linecap="square" stroke-linejoin="miter">
                <line
                  v-for="(w,idx) in getPresetIconWalls(presetDrag.preset?.kind)"
                  :key="`ghost-edge-${idx}`"
                  :x1="w.x1"
                  :y1="w.y1"
                  :x2="w.x2"
                  :y2="w.y2"
                  :stroke-width="w.sw + 1.5"
                />
              </g>
              <g fill="none" stroke="#A6A6A6" stroke-linecap="square" stroke-linejoin="miter">
                <line
                  v-for="(w,idx) in getPresetIconWalls(presetDrag.preset?.kind)"
                  :key="`ghost-fill-${idx}`"
                  :x1="w.x1"
                  :y1="w.y1"
                  :x2="w.x2"
                  :y2="w.y2"
                  :stroke-width="w.sw"
                />
              </g>
            </svg>
          </div>

          <GlbViewerWidget
            v-if="showStageOverlays"
            src="/models/1_z1.glb"
            :model2d-transform="model2dTransformRef"
            :walls2d="walls3dSnapshot"
            :wall-style-draft="wallStyleDraft"
            :selected-wall-style="selectedWallStyle"
            @update:wallStyleDraft="updateWallStyleDraft"
            @update:selectedWallCoords="updateSelectedWallCoords"
            @model2d="onGlbModel2d"
            @mouseenter="disable2dInput"
            @mouseleave="enable2dInput"
          />

          <div v-if="showStageOverlays" class="stageBottom" aria-label="Stage Bottom Bar" @mouseenter="disable2dInput" @mouseleave="enable2dInput">
            <button class="iconbtn iconbtn--sm" title="بزرگنمایی" @click="doZoomIn">
              <img src="/icons/zoom-in.png" alt="" />
            </button>
            <button class="iconbtn iconbtn--sm" title="کوچکنمایی" @click="doZoomOut">
              <img src="/icons/zoom-out.png" alt="" />
            </button>
            <button class="iconbtn iconbtn--sm" title="نمایش همه" @click="doSeeAll">
              <img src="/icons/see_all.png" alt="" />
            </button>
            <button class="iconbtn iconbtn--sm" title="رفتن به 0.0" @click="doSeeOrigin">
              <img src="/icons/see_o.o.png" alt="" />
            </button>
          </div>
        </div>
      </section>

      <div class="toolDock" aria-label="Right Tool Dock">
        <nav class="toolRail" aria-label="Tools">
          <div class="toolRail__main" aria-label="Menu">
            <button
              ref="mainMenuBtnEl"
              type="button"
              class="tool"
              :class="{ 'is-active': activeMenu === 'menu' }"
              title="منو"
              @click="toggleMenu('menu', $event)"
            >
              <img src="/icons/main-menu.png" alt="" />
            </button>
            <button
              ref="designBtnEl"
              type="button"
              class="tool"
              :class="{ 'is-active': activeMenu === 'design' }"
              title="طراحی"
              @click="toggleMenu('design', $event)"
            >
              <img src="/icons/design.png" alt="" />
            </button>
            <button
              ref="catalogBtnEl"
              type="button"
              class="tool"
              :class="{ 'is-active': activeMenu === 'catalog' }"
              title="کاتالوگ"
              @click="toggleMenu('catalog', $event)"
            >
              <img src="/icons/catalog.png" alt="" />
            </button>
            <button
              type="button"
              class="tool"
              :class="{ 'is-active': activeMenu === 'construction' }"
              title="شیوه ساخت"
              @click="toggleMenu('construction', $event)"
            >
              <img src="/icons/construction-_method.png" alt="" />
            </button>
            <button
              type="button"
              class="tool"
              :class="{ 'is-active': activeMenu === 'material' }"
              title="جنس"
              @click="toggleMenu('material', $event)"
            >
              <img src="/icons/material.png" alt="" />
            </button>
            <button
              type="button"
              class="tool"
              :class="{ 'is-active': activeMenu === 'cutting' }"
              title="لیست برش"
              @click="toggleMenu('cutting', $event)"
            >
              <img src="/icons/cutting_list.png" alt="" />
            </button>
            <button
              type="button"
              class="tool"
              :class="{ 'is-active': activeMenu === 'machinery' }"
              title="ماشین کاری"
              @click="toggleMenu('machinery', $event)"
            >
              <img src="/icons/machinery.png" alt="" />
            </button>
            <button
              type="button"
              class="tool"
              :class="{ 'is-active': activeMenu === 'price' }"
              title="قیمت گذاری"
              @click="toggleMenu('price', $event)"
            >
              <img src="/icons/price.png" alt="" />
            </button>
            <button
              type="button"
              class="tool"
              :class="{ 'is-active': activeMenu === 'report' }"
              title="گزارشات"
              @click="toggleMenu('report', $event)"
            >
              <img src="/icons/report.png" alt="" />
            </button>
            <button
              type="button"
              class="tool"
              :class="{ 'is-active': activeMenu === 'sheet' }"
              title="شیت بندی"
              @click="toggleMenu('sheet', $event)"
            >
              <img src="/icons/sheet.png" alt="" />
            </button>
          </div>

          <div class="toolRail__bottom" aria-label="Bottom">
            <button
              type="button"
              class="tool tool--small"
              :class="{ 'is-active': activeMenu === 'profile' }"
              title="حساب کاربری"
              @click="setMenu('profile')"
            >
              <img src="/icons/profile.png" alt="" />
            </button>
            <button
              type="button"
              class="tool tool--collapse tool--small"
              :class="{ 'is-open': isMenuPanelOpen }"
              :title="isMenuPanelOpen ? 'بستن' : 'باز'"
              @click="closeMenuPanel"
            >
              <img src="/icons/left-arrow.png" alt="" />
            </button>
          </div>
        </nav>
      </div>
    </div>
  </div>

  <div v-if="dialogState.open" class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="dialogState.mode === 'alert' ? closeDialog() : null"></div>
    <div class="appDialog__card" dir="rtl">
      <div v-if="dialogState.title" class="appDialog__title">{{ dialogState.title }}</div>
      <div class="appDialog__msg">{{ dialogState.message }}</div>
      <input
        v-if="dialogState.mode === 'prompt'"
        v-model="dialogState.inputValue"
        class="appDialog__input"
        type="text"
        @keydown.enter.prevent="resolveConfirm(true)"
      />
      <div class="appDialog__actions">
        <button v-if="dialogState.mode !== 'alert'" type="button" class="menuItem" @click="resolveConfirm(false)">{{ dialogState.cancelText }}</button>
        <button type="button" class="menuItem" @click="resolveConfirm(true)">{{ dialogState.confirmText }}</button>
      </div>
    </div>
  </div>

</template>
