<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import {
  editorRef,
  model2dTransformRef,
  editorViewportRef,
  passiveModelSelectionHandlerRef,
  passiveModelSelectionStateRef,
  passiveModelTransformStateRef,
  activeModelDeleteHandlerRef,
  orderDesignDeleteHandlerRef,
  orderDesignDuplicateHandlerRef,
  orderDesignMirrorHandlerRef,
  externalHistoryCaptureHandlerRef,
  externalHistoryRestoreHandlerRef,
  fitAllHandlerRef,
} from "./editor/editor_store.js";
import GlbViewerWidget from "./components/GlbViewerWidget.vue";
import { useDialogService } from "./dialog_service.js";
import { WALL_READY_PRESETS, buildPresetLines, getPresetIconWalls } from "./features/wall_preset_drag.js";
import { DOOR_READY_PRESETS, buildDoorPresetPayloadAsync, buildDoorPresetPreviewLines, getDoorPresetIconLines, primeDoorPresetModel } from "./features/door_preset_drag.js";
import { DEFAULT_DOOR_MODEL_URL, getDoorModelBoundsMm, getFallbackDoorModelBoundsMm } from "./features/door_model_asset.js";
import {
  buildInteriorAnnotationRecord,
  clampAxisAnnotation,
  collectInteriorSnapPoints,
  createEmptyInteriorLibraryAnnotations,
  formatInteriorDimensionValue,
  hitTestInteriorAnnotationList,
  isInteriorAnnotationMeaningful,
  removeSelectedInteriorAnnotation,
  snapInteriorPointToGeometry,
} from "./features/interior_library_annotations.js";
import { CURRENT_ADMIN_ID, CURRENT_BOOTSTRAP_USER_ID, CURRENT_BOOTSTRAP_USER_NAME, PART_KINDS_CATALOG } from "./features/part_kinds_catalog.js";

const activeTool = ref("select");
const snapOn = ref(true);
const showDimensions = ref(true);
const showOffsetWalls = ref(true);
const showObjectAxes = ref(false);
const currentEditorDisplayUnitState = ref("cm");
const orderDesignGeometryCache = new Map();
const walls3dSnapshot = ref({
  nodes: [],
  walls: [],
  doors: [],
  selection: {
    selectedWallId: null,
    selectedWallIds: [],
    selectedHiddenId: null,
    selectedHiddenIds: [],
    selectedDoorId: null,
    selectedDoorIds: [],
    selectedPassiveModelId: null,
    selectedPassiveModelIds: [],
    selectedModelOutline: false,
  },
  metrics: {
    nodes: [],
    walls: [],
    selection: {
      selectedWallId: null,
      selectedWallIds: [],
      selectedPassiveModelId: null,
      selectedPassiveModelIds: [],
      selectedModelOutline: false,
    },
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
const stageGlbViewerRef = ref(null);
const interiorLibraryFrontSvgEl = ref(null);
const homeBtnEl = ref(null);
const menuPanelEl = ref(null);
const mainMenuBtnEl = ref(null);
const designBtnEl = ref(null);
const catalogBtnEl = ref(null);

const route = useRoute();
const router = useRouter();
fitAllHandlerRef.value = () => {
  stageGlbViewerRef.value?.fitCameraToAll?.();
};
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
  { id: "door", icon: "/icons/door.png", title: "درب", mapsToTool: "door" },
  { id: "hidden", icon: "/icons/drawing_hidden_wall.png", title: "خط راهنما", mapsToTool: "hidden" },
  { id: "dimension", icon: "/icons/drawing_dimension.png", title: "اندازه گذاری", mapsToTool: "dimension" },
  { id: "beam", icon: "/icons/beam.png", title: "تیر", mapsToTool: "beam" },
  { id: "column", icon: "/icons/column.png", title: "ستون", mapsToTool: null },
];
const wallDesignMenuTools = designMenuTools.filter((it) => it.id !== "door");

const wallPresets = WALL_READY_PRESETS;
const doorPresets = DOOR_READY_PRESETS;
const doorAssetLibrary = ref([
  {
    id: "door-glb-sample",
    title: "نمونه درب سه بعدی",
    modelUrl: DEFAULT_DOOR_MODEL_URL,
    modelBoundsMm: getFallbackDoorModelBoundsMm(),
    outlineColor: "#8B6B4A",
  },
]);
const doorScenePlacements = ref([]);
let doorScenePlacementSeed = 1;
let presetDragSessionSeed = 0;
function normalizeDoorDimensionMm(value, fallback, { min, max }) {
  let next = Number(value);
  if (!Number.isFinite(next) || next <= 0) next = fallback;
  while (next > max * 10) next /= 10;
  if (!Number.isFinite(next) || next < min || next > max) next = fallback;
  return next;
}

function sanitizeDoorBoundsMm(boundsMm) {
  return {
    widthMm: normalizeDoorDimensionMm(boundsMm?.widthMm, 900, { min: 300, max: 3000 }),
    heightMm: normalizeDoorDimensionMm(boundsMm?.heightMm, 2070, { min: 1500, max: 4000 }),
    depthMm: normalizeDoorDimensionMm(boundsMm?.depthMm, 150, { min: 20, max: 500 }),
  };
}

function createEmptyPresetDragState() {
  return {
    active: false,
    type: null,
    preset: null,
    design: null,
    clientX: 0,
    clientY: 0,
    startX: 0,
    startY: 0,
    enteredStage: false,
    leftPanel: false,
    sessionId: 0,
    createdOrderDesignId: "",
    dragBootstrapping: false,
    dragStarted: false,
    previousActiveOrderDesignId: "",
    previousActivePlacement: null,
    releasePending: false,
    releaseClientX: 0,
    releaseClientY: 0,
  };
}
const presetDrag = ref(createEmptyPresetDragState());
const PRESET_PREVIEW_MIN_DRAG_PX = 12;
const DEFAULT_FRONT_VIEW_WIDTH = 760;
const DEFAULT_FRONT_VIEW_HEIGHT = 460;
const snapMenuItems = [
  { id: "corner", title: "گوشه", icon: "/icons/corner_point.png" },
  { id: "mid", title: "وسط ضلع", icon: "/icons/midpoint.png" },
  { id: "center", title: "مرکز", icon: "/icons/ax_point.png" },
  { id: "edge", title: "لبه", icon: "/icons/edge_snap.png" },
  { id: "wallMagnet", title: "جذب دیوار", icon: "/icons/magnet.png" },
  { id: "ortho", title: "راستا (راست کلیک)", icon: "/icons/ortho_line.png" },
];
const currentAdminId = ref(CURRENT_ADMIN_ID);
const currentBootstrapUserId = ref(CURRENT_BOOTSTRAP_USER_ID);
const currentBootstrapUserName = ref(CURRENT_BOOTSTRAP_USER_NAME);
const activeOrder = ref(null);
const ordersCatalog = ref([]);
const ordersLoading = ref(false);
const ordersSaving = ref(false);
const orderEntryOpen = ref(false);
const orderEntryTab = ref("create");
const orderDraftMode = ref("create");
const orderDraft = ref({ order_name: "", notes: "", status: "draft" });
const orderDrawingLoading = ref(false);
const orderOpening = ref(false);
const orderOpeningLabel = ref("");
const cabinetDesignCatalog = ref([]);
const cabinetDesignCatalogLoading = ref(false);
const cabinetDesignCatalogLoadedForAdmin = ref("");
const orderDesignCatalog = ref([]);
const orderDesignCatalogLoading = ref(false);
const orderDesignCatalogLoadedForOrderId = ref("");
let orderDesignCatalogLoadRequestSeq = 0;
let orderDesignCatalogReloadQueued = false;
const interiorLibraryOpen = ref(false);
const interiorLibraryForcedOrderDesignId = ref("");
const interiorInstanceEditorOpen = ref(false);
const interiorInstanceEditorDraft = ref(null);
const interiorInstanceEditorActiveGroupId = ref("");
const interiorLibraryControllerTestMode = ref(false);
const interiorLibraryControllerEditingId = ref("");
const interiorLibraryControllerInputDraft = ref("");
const interiorLibraryHoveredControllerId = ref("");
const interiorLibraryControllerDraftValues = ref(null);
const interiorLibraryControllerPointerState = ref({
  mode: "idle",
  pointerId: null,
  controllerId: "",
  startPoint: null,
  startPan: null,
  startValues: null,
  pointerToAnchor: null,
  dirty: false,
});
const interiorLibraryPreviewMode = ref("front2d");
const interiorLibraryFrontZoom = ref(1);
const interiorLibraryPreview3dRef = ref(null);
const interiorLibraryPreviewOpacity = ref(100);
const interiorLibraryShowInnerLines = ref(true);
const interiorLibraryShowDimensions = ref(true);
const interiorLibraryShowGuideAnnotations = ref(true);
const interiorLibraryAnnotationTool = ref(null);
const interiorLibraryAnnotations = ref(createEmptyInteriorLibraryAnnotations());
const interiorLibraryAnnotationDraft = ref(null);
const interiorLibrarySelectedAnnotation = ref(null);
const interiorLibraryCurrentSnapPoint = ref(null);
const interiorLibraryCursorPoint = ref(null);
const interiorLibrarySelectedInstanceId = ref("");
const interiorLibraryHoveredInstanceId = ref("");
const interiorLibraryPickerPreviewInstanceId = ref("");
const interiorLibraryHoverMode = ref(null);
const interiorLibraryOverlapPickerState = ref({
  visible: false,
  items: [],
  clientX: 0,
  clientY: 0,
});
const interiorLibraryFrontPan = ref({ x: 0, y: 0 });
const interiorLibraryFrontPanning = ref(false);
const interiorLibraryViewerCursorPoint = ref(null);
const interiorLibraryModelPanning = ref(false);
let interiorLibraryFrontPanSession = null;
let interiorLibraryFrontLastMiddleClickMs = 0;
const orderDesignEditorOpen = ref(false);
const orderDesignEditorDraft = ref(null);
const orderDesignSavingIds = ref([]);
const orderDesignPlacements = ref([]);
const stageCabinetPlaceholderBoxes = ref([]);
const activeCabinetDesignId = ref(null);
const activeDoorAssetId = ref(null);
const activeStageOrderDesignSelected = ref(false);
const selectedStageOrderDesignIds = ref([]);
const selectedStageDoorAssetIds = ref([]);
const hoveredCabinetDesignId = ref(null);
const hoveredConstructionDesignId = ref(null);
const cabinetDesignDropLoading = ref(false);
const cabinetDesignDropLoadingTitle = ref("");
const cabinetDesignDropLoadingMode = ref("add");
const ORDER_DRAWING_AUTOSAVE_DEBOUNCE_MS = 900;
let _orderDrawingSaveTimeout = 0;
let _orderDesignPlacementSyncPaused = false;
const editorViewportState = editorViewportRef;
const constructionWizardOpen = ref(false);
const constructionStep = ref("templates");
const PART_FORMULA_FIELDS = [
  { key: "formula_l", label: "فرمول L" },
  { key: "formula_w", label: "فرمول W" },
  { key: "formula_width", label: "فرمول Width" },
  { key: "formula_depth", label: "فرمول Depth" },
  { key: "formula_height", label: "فرمول Height" },
  { key: "formula_cx", label: "فرمول Cx" },
  { key: "formula_cy", label: "فرمول Cy" },
  { key: "formula_cz", label: "فرمول Cz" },
];
const INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH = "width_controler_internal_group_parts";
const INTERNAL_GROUP_CONTROLLER_TYPE_OPTIONS = [
  { value: INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH, label: "کنترلر قطعات عرضی" },
];
const INTERNAL_GROUP_CONTROLLER_DEFINITIONS = {
  [INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH]: [
    { key: "left", label: "کنترلر ضلع چپ" },
    { key: "top", label: "کنترلر ضلع بالا" },
    { key: "right", label: "کنترلر ضلع راست" },
    { key: "bottom_offset", label: "کنترلر ارتفاع کل" },
  ],
};
const editableTemplates = ref([]);
const editableCategories = ref([]);
const editablePartKinds = ref(PART_KINDS_CATALOG.map((item) => ({ ...item })));
const editableParamGroups = ref([]);
const editableParams = ref([]);
const editableSubCategories = ref([]);
const editableSubCategoryDesigns = ref([]);
const editableInternalPartGroups = ref([]);
const editableBaseFormulas = ref([]);
const editablePartFormulas = ref([]);
const subCategoryDefaultsEditorOpen = ref(false);
const subCategoryDefaultsEditorRowId = ref(null);
const subCategoryDefaultsEditorDraft = ref({});
const subCategoryDefaultsEditorOverridesDraft = ref({});
const subCategoryDefaultIconPreviewUrls = ref({});
const subCategoryDefaultsActiveGroupId = ref("");
const subCategoryDefaultIconInputEl = ref(null);
const subCategoryDefaultIconTargetCode = ref("");
const subCategoryDefaultIconTargetField = ref("icon_path");
const subCategoryDefaultIconUploadingKey = ref("");
const subCategoryUserPreviewOpen = ref(false);
const subCategoryUserPreviewRowId = ref(null);
const subCategoryUserPreviewValues = ref({});
const subCategoryUserPreviewActiveGroupId = ref("");
const subCategoryDesignEditorOpen = ref(false);
const subCategoryDesignEditorDraft = ref(null);
const subCategoryDesignEditorPreview = ref(null);
const subCategoryDesignPreviewLoading = ref(false);
const subCategoryDesignPreviewError = ref("");
const subCategoryDesignPreviewRequestSeq = ref(0);
const subCategoryDesignEditorSaving = ref(false);
const internalPartGroupEditorOpen = ref(false);
const internalPartGroupEditorDraft = ref(null);
const internalPartGroupParamGroupsOpen = ref(false);
const internalPartGroupDefaultsEditorOpen = ref(false);
const internalPartGroupDefaultsEditorRowId = ref(null);
const internalPartGroupDefaultsEditorGroups = ref([]);
const internalPartGroupDefaultsValues = ref({});
const internalPartGroupDefaultsActiveGroupId = ref("");
const internalPartGroupDefaultsApplying = ref(false);
const internalPartGroupControllerEditorOpen = ref(false);
const internalPartGroupControllerEditorRowId = ref(null);
const internalPartGroupControllerEditorType = ref("");
const internalPartGroupControllerEditorBindings = ref({});
const internalPartGroupControllerEditorApplying = ref(false);
const baseFormulaBuilderOpen = ref(false);
const baseFormulaBuilderMode = ref("create");
const baseFormulaBuilderEntity = ref("base_formulas");
const baseFormulaBuilderTargetRowId = ref(null);
const baseFormulaBuilderTargetField = ref("formula");
const baseFormulaBuilderDraft = ref(null);
const baseFormulaBuilderTokens = ref([]);
const baseFormulaBuilderSyncWarning = ref("");
const baseFormulaBuilderNumberInput = ref("");
const constructionLoading = ref(false);
const constructionSavingIds = ref([]);
const constructionDeletingIds = ref([]);
const constructionDeletedTemplateIds = ref([]);
const constructionDeletedCategoryIds = ref([]);
const constructionDeletedPartKindIds = ref([]);
const constructionDeletedParamGroupIds = ref([]);
const constructionDeletedParamIds = ref([]);
const constructionDeletedSubCategoryIds = ref([]);
const DEFAULT_SUB_CATEGORY_DESIGN_OUTLINE_COLOR = "#7A4A2B";
const constructionDeletedSubCategoryDesignIds = ref([]);
const constructionDeletedBaseFormulaIds = ref([]);
const constructionDeletedPartFormulaIds = ref([]);
const constructionImportInputEl = ref(null);
const constructionParamsTableWrapEl = ref(null);
const interiorLibraryAddingGroupKey = ref("");
const interiorInstanceEditorApplying = ref(false);
const INTERIOR_LIBRARY_FRONT_ZOOM_MIN = 0.1;
const INTERIOR_LIBRARY_FRONT_ZOOM_MAX = 20000;
const INTERIOR_LIBRARY_FRONT_ZOOM_FACTOR = 1.18;
const INTERIOR_LIBRARY_DOUBLE_CLICK_ZOOM_FACTOR = 1.6;
function isOrderDesignSaving(designId) {
  const key = String(designId || "").trim();
  return !!key && orderDesignSavingIds.value.includes(key);
}
function setInteriorLibraryPreviewMode(mode) {
  interiorLibraryPreviewMode.value = mode === "model3d" ? "model3d" : "front2d";
  if (interiorLibraryPreviewMode.value === "model3d") {
    nextTick(() => {
      resetInteriorLibraryPreviewView();
      setInteriorLibraryPreviewOpacity(interiorLibraryPreviewOpacity.value);
    });
    return;
  }
  resetInteriorLibraryPreviewView();
}
function changeInteriorLibraryFrontZoom(nextZoom) {
  const boundedZoom = Math.min(
    INTERIOR_LIBRARY_FRONT_ZOOM_MAX,
    Math.max(
      INTERIOR_LIBRARY_FRONT_ZOOM_MIN,
      Number(nextZoom) || 1
    )
  );
  interiorLibraryFrontZoom.value = boundedZoom;
}
function zoomInteriorLibraryFrontIn() {
  if (interiorLibraryPreviewMode.value === "model3d") {
    interiorLibraryPreview3dRef.value?.zoomIn?.();
    return;
  }
  changeInteriorLibraryFrontZoom((Number(interiorLibraryFrontZoom.value) || 1) * INTERIOR_LIBRARY_FRONT_ZOOM_FACTOR);
}
function zoomInteriorLibraryFrontOut() {
  if (interiorLibraryPreviewMode.value === "model3d") {
    interiorLibraryPreview3dRef.value?.zoomOut?.();
    return;
  }
  changeInteriorLibraryFrontZoom((Number(interiorLibraryFrontZoom.value) || 1) / INTERIOR_LIBRARY_FRONT_ZOOM_FACTOR);
}
function handleInteriorLibraryPreviewWheel(event) {
  const deltaY = Number(event?.deltaY) || 0;
  if (!Number.isFinite(deltaY) || deltaY === 0) return;
  if (interiorLibraryPreviewMode.value === "model3d") return;
  if (interiorLibraryPreviewMode.value !== "front2d") return;
  if (deltaY < 0) {
    zoomInteriorLibraryFrontIn();
  } else {
    zoomInteriorLibraryFrontOut();
  }
}
function stopInteriorLibraryFrontPan() {
  interiorLibraryFrontPanSession = null;
  interiorLibraryFrontPanning.value = false;
  window.removeEventListener("pointermove", onInteriorLibraryFrontPanMove);
  window.removeEventListener("pointerup", onInteriorLibraryFrontPanUp);
}
function onInteriorLibraryFrontPanMove(event) {
  const session = interiorLibraryFrontPanSession;
  if (!session) return;
  const rectWidth = Math.max(1, Number(session.rectWidth) || 1);
  const rectHeight = Math.max(1, Number(session.rectHeight) || 1);
  const zoom = Math.min(
    INTERIOR_LIBRARY_FRONT_ZOOM_MAX,
    Math.max(INTERIOR_LIBRARY_FRONT_ZOOM_MIN, Number(interiorLibraryFrontZoom.value) || 1)
  );
  const viewWidth = FRONT_VIEW_WIDTH / zoom;
  const viewHeight = FRONT_VIEW_HEIGHT / zoom;
  const dx = Number(event?.clientX) - session.startClientX;
  const dy = Number(event?.clientY) - session.startClientY;
  interiorLibraryFrontPan.value = {
    x: session.startPanX - (dx / rectWidth) * viewWidth,
    y: session.startPanY - (dy / rectHeight) * viewHeight,
  };
}
function onInteriorLibraryFrontPanUp() {
  stopInteriorLibraryFrontPan();
}
function startInteriorLibraryFrontPan(event) {
  if (interiorLibraryPreviewMode.value !== "front2d" || Number(event?.button) !== 1) return;
  const now = performance.now();
  if (now - interiorLibraryFrontLastMiddleClickMs <= 300) {
    interiorLibraryFrontLastMiddleClickMs = 0;
    event.preventDefault();
    focusInteriorLibraryPreviewCloser();
    return;
  }
  interiorLibraryFrontLastMiddleClickMs = now;
  const currentTarget = event?.currentTarget;
  const rect = currentTarget?.getBoundingClientRect?.();
  interiorLibraryFrontPanSession = {
    startClientX: Number(event.clientX) || 0,
    startClientY: Number(event.clientY) || 0,
    startPanX: Number(interiorLibraryFrontPan.value?.x) || 0,
    startPanY: Number(interiorLibraryFrontPan.value?.y) || 0,
    rectWidth: rect?.width || currentTarget?.clientWidth || 1,
    rectHeight: rect?.height || currentTarget?.clientHeight || 1,
  };
  interiorLibraryFrontPanning.value = true;
  event.preventDefault();
  window.addEventListener("pointermove", onInteriorLibraryFrontPanMove);
  window.addEventListener("pointerup", onInteriorLibraryFrontPanUp, { once: true });
}
function resetInteriorLibraryPreviewView() {
  if (interiorLibraryPreviewMode.value === "model3d") {
    interiorLibraryModelPanning.value = false;
    interiorLibraryPreview3dRef.value?.fitCameraToAll?.();
    return;
  }
  interiorLibraryFrontZoom.value = 1;
  interiorLibraryFrontPan.value = { x: 0, y: 0 };
  stopInteriorLibraryFrontPan();
}
function focusInteriorLibraryPreviewCloser() {
  if (interiorLibraryPreviewMode.value === "model3d") {
    interiorLibraryPreview3dRef.value?.fitCameraToAll?.();
    interiorLibraryPreview3dRef.value?.zoomByFactor?.(INTERIOR_LIBRARY_DOUBLE_CLICK_ZOOM_FACTOR);
    return;
  }
  interiorLibraryFrontZoom.value = INTERIOR_LIBRARY_DOUBLE_CLICK_ZOOM_FACTOR;
  interiorLibraryFrontPan.value = { x: 0, y: 0 };
  stopInteriorLibraryFrontPan();
}
function setInteriorLibraryPreviewOpacity(value) {
  const nextValue = Math.max(0, Math.min(100, Number(value) || 0));
  interiorLibraryPreviewOpacity.value = nextValue;
  interiorLibraryPreview3dRef.value?.setPlaceholderOpacity?.(nextValue);
}
function toggleInteriorLibraryGuideTool() {
  interiorLibraryShowInnerLines.value = !interiorLibraryShowInnerLines.value;
}
function toggleInteriorLibraryDimensionsVisibility() {
  interiorLibraryShowDimensions.value = !interiorLibraryShowDimensions.value;
}
function toggleInteriorLibraryGuideAnnotationsVisibility() {
  interiorLibraryShowGuideAnnotations.value = !interiorLibraryShowGuideAnnotations.value;
}
function toggleInteriorLibraryDimensionTool() {
  interiorLibraryAnnotationTool.value = interiorLibraryAnnotationTool.value === "dimension" ? null : "dimension";
  interiorLibrarySelectedAnnotation.value = null;
  interiorLibraryAnnotationDraft.value = null;
}
function toggleInteriorLibraryGuideAnnotationTool() {
  interiorLibraryAnnotationTool.value = interiorLibraryAnnotationTool.value === "guide" ? null : "guide";
  interiorLibrarySelectedAnnotation.value = null;
  interiorLibraryAnnotationDraft.value = null;
}
function resetInteriorLibraryAnnotations() {
  interiorLibraryAnnotations.value = createEmptyInteriorLibraryAnnotations();
  interiorLibraryAnnotationDraft.value = null;
  interiorLibrarySelectedAnnotation.value = null;
  interiorLibraryAnnotationTool.value = null;
  interiorLibraryShowDimensions.value = true;
  interiorLibraryShowGuideAnnotations.value = true;
  interiorLibraryCurrentSnapPoint.value = null;
  interiorLibrarySelectedInstanceId.value = "";
  interiorLibraryHoveredInstanceId.value = "";
  interiorLibraryPickerPreviewInstanceId.value = "";
  interiorLibraryHoverMode.value = null;
  hideInteriorLibraryOverlapPicker();
}
function cancelInteriorLibraryAnnotationDrawing() {
  interiorLibraryAnnotationDraft.value = null;
  interiorLibraryAnnotationTool.value = null;
  interiorLibrarySelectedAnnotation.value = null;
  interiorLibraryCurrentSnapPoint.value = null;
  interiorLibraryCursorPoint.value = null;
  interiorLibraryHoverMode.value = null;
}
function getInteriorLibraryFrontSvgPoint(event) {
  const svgEl = interiorLibraryFrontSvgEl.value;
  if (!svgEl || !event) return null;
  const rect = svgEl.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const clientX = Number(event.clientX);
  const clientY = Number(event.clientY);
  if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) return null;
  const viewBox = interiorLibraryFrontSvgViewBox.value.split(/\s+/).map(Number);
  if (viewBox.length !== 4 || viewBox.some((value) => !Number.isFinite(value))) return null;
  const [vx, vy, vw, vh] = viewBox;
  return {
    x: vx + ((clientX - rect.left) / rect.width) * vw,
    y: vy + ((clientY - rect.top) / rect.height) * vh,
  };
}
function getInteriorLibrarySnappedFrontPoint(point) {
  const rawPoint = point && typeof point === "object"
    ? { x: Number(point.x) || 0, y: Number(point.y) || 0 }
    : null;
  if (!rawPoint) {
    interiorLibraryCurrentSnapPoint.value = null;
    return null;
  }
  const snapped = snapInteriorPointToGeometry(
    rawPoint,
    interiorLibraryFrontSnapLines.value,
    interiorLibraryFrontSnapTolerance.value
  );
  interiorLibraryCurrentSnapPoint.value = snapped?.point
    ? {
        x: Number(snapped.point.x) || 0,
        y: Number(snapped.point.y) || 0,
        kind: snapped.kind === "edge" ? "edge" : "corner",
      }
    : null;
  return interiorLibraryCurrentSnapPoint.value
    ? { x: interiorLibraryCurrentSnapPoint.value.x, y: interiorLibraryCurrentSnapPoint.value.y }
    : rawPoint;
}
function syncInteriorLibraryCursorPoint(rawPoint, snappedPoint = null) {
  const source = snappedPoint && typeof snappedPoint === "object"
    ? snappedPoint
    : rawPoint;
  interiorLibraryCursorPoint.value = source && typeof source === "object"
    ? {
        x: Number(source.x) || 0,
        y: Number(source.y) || 0,
      }
    : null;
}
function clearInteriorLibraryCursorPoint() {
  interiorLibraryCursorPoint.value = null;
}
function syncInteriorLibraryViewerCursorPoint(event) {
  const wrapEl = interiorLibraryViewerWrapEl.value;
  if (!wrapEl || !event) {
    interiorLibraryViewerCursorPoint.value = null;
    return;
  }
  const rect = wrapEl.getBoundingClientRect();
  if (!rect.width || !rect.height) {
    interiorLibraryViewerCursorPoint.value = null;
    return;
  }
  const clientX = Number(event.clientX);
  const clientY = Number(event.clientY);
  if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) {
    interiorLibraryViewerCursorPoint.value = null;
    return;
  }
  interiorLibraryViewerCursorPoint.value = {
    x: Math.max(0, Math.min(rect.width, clientX - rect.left)),
    y: Math.max(0, Math.min(rect.height, clientY - rect.top)),
  };
}
function clearInteriorLibraryViewerCursorPoint() {
  interiorLibraryViewerCursorPoint.value = null;
}
function createInteriorLibraryAnnotationDraft(type, point) {
  return {
    type: type === "guide" ? "guide" : "dimension",
    startPoint: { x: Number(point?.x) || 0, y: Number(point?.y) || 0 },
    currentPoint: { x: Number(point?.x) || 0, y: Number(point?.y) || 0 },
  };
}
function measureInteriorAnnotationMm(annotation) {
  const projection = interiorLibraryPreviewProjection.value;
  if (!annotation?.start || !annotation?.end || !projection?.unprojectPoint) return Math.max(0, Number(annotation?.value) || 0);
  const start = projection.unprojectPoint(annotation.start);
  const end = projection.unprojectPoint(annotation.end);
  if (!start || !end) return Math.max(0, Number(annotation?.value) || 0);
  return String(annotation?.axis || "").trim() === "vertical"
    ? Math.abs(Number(end.z) - Number(start.z))
    : Math.abs(Number(end.x) - Number(start.x));
}
function buildInteriorLibraryAnnotationRecord(type, startPoint, currentPoint) {
  const record = buildInteriorAnnotationRecord(type, startPoint, currentPoint);
  if (record.type === "dimension") {
    record.valueMm = measureInteriorAnnotationMm(record);
  }
  return record;
}
function updateInteriorLibraryAnnotationDraft(point) {
  if (!interiorLibraryAnnotationDraft.value) return;
  interiorLibraryAnnotationDraft.value = {
    ...interiorLibraryAnnotationDraft.value,
    currentPoint: { x: Number(point?.x) || 0, y: Number(point?.y) || 0 },
  };
}
function commitInteriorLibraryAnnotationDraft() {
  const draft = interiorLibraryAnnotationDraft.value;
  if (!draft?.type || !draft?.startPoint || !draft?.currentPoint) return;
  const nextRecord = buildInteriorLibraryAnnotationRecord(draft.type, draft.startPoint, draft.currentPoint);
  if (!isInteriorAnnotationMeaningful(nextRecord)) {
    interiorLibraryAnnotationDraft.value = null;
    return;
  }
  interiorLibraryAnnotations.value = nextRecord.type === "guide"
    ? {
        ...interiorLibraryAnnotations.value,
        guides: [...(interiorLibraryAnnotations.value.guides || []), nextRecord],
      }
    : {
        ...interiorLibraryAnnotations.value,
        dimensions: [...(interiorLibraryAnnotations.value.dimensions || []), nextRecord],
      };
  interiorLibrarySelectedAnnotation.value = { type: nextRecord.type, id: nextRecord.id };
  interiorLibraryAnnotationDraft.value = null;
  interiorLibraryCurrentSnapPoint.value = null;
}
function clearInteriorLibraryAnnotationSelection() {
  interiorLibrarySelectedAnnotation.value = null;
}
function clearInteriorLibraryInstanceSelection() {
  interiorLibrarySelectedInstanceId.value = "";
}
function removeSelectedInteriorLibraryAnnotation() {
  if (!interiorLibrarySelectedAnnotation.value) return;
  interiorLibraryAnnotations.value = removeSelectedInteriorAnnotation(
    interiorLibraryAnnotations.value,
    interiorLibrarySelectedAnnotation.value
  );
  interiorLibrarySelectedAnnotation.value = null;
}
function hideInteriorLibraryOverlapPicker() {
  interiorLibraryOverlapPickerState.value = {
    visible: false,
    items: [],
    clientX: 0,
    clientY: 0,
  };
  interiorLibraryPickerPreviewInstanceId.value = "";
}
function showInteriorLibraryOverlapPicker(clientX, clientY, items) {
  interiorLibraryOverlapPickerState.value = {
    visible: true,
    items: Array.isArray(items) ? items.slice() : [],
    clientX: Number(clientX) || 0,
    clientY: Number(clientY) || 0,
  };
  interiorLibraryPickerPreviewInstanceId.value = "";
}
function setInteriorLibraryOverlapPreview(instanceId) {
  interiorLibraryPickerPreviewInstanceId.value = String(instanceId || "").trim();
}
function clearInteriorLibraryOverlapPreview() {
  interiorLibraryPickerPreviewInstanceId.value = "";
}
function selectInteriorLibraryOverlapItem(hit) {
  const instanceId = String(hit?.id || "").trim();
  if (!instanceId) return;
  selectInteriorLibraryInstance(instanceId);
  hideInteriorLibraryOverlapPicker();
}
function getInteriorLibraryOverlapPickerStyle() {
  const state = interiorLibraryOverlapPickerState.value || {};
  const menuWidth = 320;
  const gutter = 8;
  const viewportWidth = typeof window !== "undefined" ? window.innerWidth : 0;
  const viewportHeight = typeof window !== "undefined" ? window.innerHeight : 0;
  const estimatedHeight = Math.min(
    360,
    52 + ((Array.isArray(state.items) ? state.items.length : 0) * 88)
  );
  const left = Math.max(gutter, Math.min((Number(state.clientX) || 0) + 10, viewportWidth - menuWidth - gutter));
  const top = Math.max(gutter, Math.min((Number(state.clientY) || 0) + 10, viewportHeight - estimatedHeight - gutter));
  return {
    left: `${Math.round(left)}px`,
    top: `${Math.round(top)}px`,
  };
}
function selectInteriorLibraryInstance(instanceId) {
  interiorLibrarySelectedInstanceId.value = String(instanceId || "").trim();
  interiorLibrarySelectedAnnotation.value = null;
  clearInteriorLibraryOverlapPreview();
}
function distancePointToSegmentLocal(point, start, end) {
  const px = Number(point?.x) || 0;
  const py = Number(point?.y) || 0;
  const ax = Number(start?.x) || 0;
  const ay = Number(start?.y) || 0;
  const bx = Number(end?.x) || 0;
  const by = Number(end?.y) || 0;
  const dx = bx - ax;
  const dy = by - ay;
  const lenSq = dx * dx + dy * dy;
  if (lenSq <= 0.0001) return Math.hypot(px - ax, py - ay);
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lenSq));
  const cx = ax + dx * t;
  const cy = ay + dy * t;
  return Math.hypot(px - cx, py - cy);
}
function pointInInteriorRect(point, rect, padding = 0) {
  if (!rect) return false;
  const px = Number(point?.x) || 0;
  const py = Number(point?.y) || 0;
  return (
    px >= Number(rect.x) - padding &&
    px <= Number(rect.x) + Number(rect.w) + padding &&
    py >= Number(rect.y) - padding &&
    py <= Number(rect.y) + Number(rect.h) + padding
  );
}
function collectInteriorInstanceHits(point) {
  const target = { x: Number(point?.x) || 0, y: Number(point?.y) || 0 };
  const hits = [];
  for (const instance of interiorLibraryPreviewInstances2d.value) {
    if (!instance?.boundsRect) continue;
    const inside = pointInInteriorRect(target, instance.boundsRect, 0);
    let minDistance = Infinity;
    for (const line of instance.outerLines || []) {
      minDistance = Math.min(
        minDistance,
        distancePointToSegmentLocal(
          target,
          { x: line.x1, y: line.y1 },
          { x: line.x2, y: line.y2 }
        )
      );
    }
    for (const line of instance.innerLines || []) {
      minDistance = Math.min(
        minDistance,
        distancePointToSegmentLocal(
          target,
          { x: line.x1, y: line.y1 },
          { x: line.x2, y: line.y2 }
        )
      );
    }
    if (!inside && minDistance > 10) continue;
    hits.push({
      id: String(instance.id || "").trim(),
      instanceCode: String(instance.instanceCode || "").trim(),
      title: String(instance.groupTitle || instance.instanceCode || instance.id || "قطعه داخلی").trim(),
      lineColor: String(instance.lineColor || "").trim(),
      distance: inside ? Math.min(minDistance, 0) : minDistance,
      visualOrder: Number(instance.visualOrder) || 0,
    });
  }
  return hits.sort((a, b) => {
    if (Math.abs(a.distance - b.distance) > 0.01) return a.distance - b.distance;
    return b.visualOrder - a.visualOrder;
  });
}
function updateInteriorLibraryHoverState(point) {
  if (interiorLibraryControllerPointerState.value.mode === "controller") return;
  if (hitTestInteriorLibraryController(point)) {
    interiorLibraryHoverMode.value = "clicker";
    interiorLibraryHoveredInstanceId.value = "";
    clearInteriorLibraryOverlapPreview();
    return;
  }
  if (!point || interiorLibraryAnnotationTool.value) {
    interiorLibraryHoverMode.value = null;
    interiorLibraryHoveredInstanceId.value = "";
    clearInteriorLibraryOverlapPreview();
    return;
  }
  const rendered = interiorLibraryRenderedAnnotations.value;
  const hitDimension = interiorLibraryShowDimensions.value
    ? hitTestInteriorAnnotationList(rendered.dimensions, point, 12)
    : null;
  const hitGuide = !hitDimension && interiorLibraryShowGuideAnnotations.value
    ? hitTestInteriorAnnotationList(rendered.guides, point, 10)
    : null;
  const instanceHits = !hitDimension && !hitGuide ? collectInteriorInstanceHits(point) : [];
  const previewId = String(interiorLibraryPickerPreviewInstanceId.value || "").trim();
  interiorLibraryHoveredInstanceId.value = previewId || instanceHits[0]?.id || "";
  interiorLibraryHoverMode.value = (hitDimension || hitGuide || instanceHits.length) ? "clicker" : null;
}

function hitTestInteriorLibraryController(point) {
  for (let index = interiorLibraryControllerVisuals.value.length - 1; index >= 0; index -= 1) {
    const item = interiorLibraryControllerVisuals.value[index];
    const hotspot = getInteriorControllerMatchingHotspot(point, item);
    if (hotspot) {
      return { ...item, activeHotspot: hotspot };
    }
  }
  return null;
}

function clearInteriorLibraryControllerEditing() {
  interiorLibraryControllerEditingId.value = "";
  interiorLibraryControllerInputDraft.value = "";
}

function clearInteriorLibraryControllerDraftValues() {
  interiorLibraryControllerDraftValues.value = null;
}

function beginInteriorLibraryControllerEditing(controllerId) {
  if (!controllerId || !interiorLibraryControllerState.value.enabled) return;
  interiorLibraryControllerEditingId.value = String(controllerId || "").trim();
  interiorLibraryControllerInputDraft.value = formatInteriorControllerRawValue(interiorLibraryControllerParamValues.value?.[controllerId]);
  nextTick(() => {
    const inputEl = interiorLibraryViewerWrapEl.value?.querySelector?.(`[data-interior-controller-input="${controllerId}"]`);
    inputEl?.focus?.();
    inputEl?.select?.();
  });
}

function updateInteriorInstanceFromControllerValues(nextValues) {
  const instance = activeInteriorLibrarySelectedInstance.value;
  if (!instance?.id) return null;
  const bindings = interiorLibraryControllerBindingMap.value;
  const nextParamValues = { ...(instance.param_values || {}) };
  for (const [controllerId, valueMm] of Object.entries(nextValues || {})) {
    const paramCode = String(bindings?.[controllerId]?.param_code || "").trim();
    if (!paramCode) continue;
    nextParamValues[paramCode] = String(Math.max(0, Number(valueMm) || 0));
  }
  const nextInstance = normalizeInteriorInstanceRecord({
    ...instance,
    param_values: nextParamValues,
  });
  if (!nextInstance) return null;
  if (subCategoryDesignEditorOpen.value) {
    syncInteriorInstanceInDraft(nextInstance);
    syncOpenSubCategoryDesignDraftToCollection();
  } else {
    syncInteriorInstanceInOrderDesignCollection(activeInteriorLibraryOrderDesign.value?.id, nextInstance);
  }
  return nextInstance;
}

function applyInteriorLibraryControllerInput(controllerId, nextValueMm) {
  const frame = interiorLibraryControllerFrameRect.value;
  const values = interiorLibraryControllerParamValues.value;
  if (!frame || !Number.isFinite(nextValueMm)) return false;
  const safeValue = Math.max(0, Number(nextValueMm) || 0);
  const nextValues = {
    left: Number(values.left) || 0,
    top: Number(values.top) || 0,
    right: Number(values.right) || 0,
    bottom_offset: Number(values.bottom_offset) || 0,
  };
  const frameWidth = Math.max(0, frame.maxX - frame.minX);
  const frameHeight = Math.max(0, frame.maxZ - frame.minZ);
  const minWidth = 240;
  const minHeight = 1;
  if (controllerId === "left") {
    nextValues.left = Math.min(Math.max(0, safeValue), Math.max(0, frameWidth - nextValues.right - minWidth));
  } else if (controllerId === "right") {
    nextValues.right = Math.min(Math.max(0, safeValue), Math.max(0, frameWidth - nextValues.left - minWidth));
  } else if (controllerId === "top") {
    nextValues.top = Math.min(Math.max(minHeight, safeValue), Math.max(minHeight, frameHeight - nextValues.bottom_offset));
  } else if (controllerId === "bottom_offset") {
    nextValues.bottom_offset = Math.min(Math.max(0, safeValue), Math.max(0, frameHeight - nextValues.top));
  } else {
    return false;
  }
  return !!updateInteriorInstanceFromControllerValues(nextValues);
}

async function persistActiveInteriorLibraryControllerInstance() {
  const instance = activeInteriorLibrarySelectedInstance.value;
  if (!instance?.id) return;
  if (subCategoryDesignEditorOpen.value) {
    const draft = subCategoryDesignEditorDraft.value;
    if (!draft?.id) return;
    const res = await fetch(
      `/api/sub-category-designs/${encodeURIComponent(String(draft.id))}/interior-instances/${encodeURIComponent(String(instance.id))}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          placement_z: Number(instance.placement_z) || 0,
          ui_order: Math.max(0, Number(instance.ui_order) || 0),
          instance_code: String(instance.instance_code || "").trim() || "interior",
          line_color: instance.line_color ? normalizeHexColor(instance.line_color, DEFAULT_INTERIOR_LINE_COLOR) : null,
          param_values: Object.fromEntries(
            Object.entries(instance.param_values || {}).map(([key, value]) => [key, value == null ? null : String(value)])
          ),
        }),
      }
    );
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره کنترلر نمونه داخلی انجام نشد."));
    syncInteriorInstanceInDraft(await res.json());
    syncOpenSubCategoryDesignDraftToCollection();
    await refreshSubCategoryDesignPreview();
    return;
  }
  const orderDesign = activeInteriorLibraryOrderDesign.value;
  if (!orderDesign?.id) return;
  const res = await fetch(
    `/api/order-designs/${encodeURIComponent(String(orderDesign.id))}/interior-instances/${encodeURIComponent(String(instance.id))}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        placement_z: Number(instance.placement_z) || 0,
        ui_order: Math.max(0, Number(instance.ui_order) || 0),
        instance_code: String(instance.instance_code || "").trim() || "interior",
        line_color: instance.line_color ? normalizeHexColor(instance.line_color, DEFAULT_INTERIOR_LINE_COLOR) : null,
        param_values: Object.fromEntries(
          Object.entries(instance.param_values || {}).map(([key, value]) => [key, value == null ? null : String(value)])
        ),
      }),
    }
  );
  if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره کنترلر نمونه داخلی طرح ثبت‌شده انجام نشد."));
  syncInteriorInstanceInOrderDesignCollection(orderDesign.id, await res.json());
  await refreshOrderDesignGeometryFromServer(orderDesign.id);
}

function commitInteriorLibraryControllerEditing() {
  const controllerId = String(interiorLibraryControllerEditingId.value || "").trim();
  if (!controllerId) return;
  const nextValueMm = parseInteriorControllerInputToMm(interiorLibraryControllerInputDraft.value);
  if (nextValueMm == null) {
    clearInteriorLibraryControllerEditing();
    return;
  }
  const applied = applyInteriorLibraryControllerInput(controllerId, nextValueMm);
  clearInteriorLibraryControllerEditing();
  if (!applied) return;
  persistActiveInteriorLibraryControllerInstance().catch((error) => {
    showAlert(error?.message || "ذخیره کنترلر نمونه داخلی انجام نشد.", { title: "خطا" });
  });
}

function beginInteriorLibraryControllerDrag(controllerId, event) {
  const point = getInteriorLibraryFrontSvgPoint(event);
  const controller = interiorLibraryControllerVisuals.value.find((item) => item.id === controllerId);
  if (!point || !controller?.anchor) return;
  interiorLibraryHoveredControllerId.value = String(controllerId || "").trim();
  interiorLibraryControllerDraftValues.value = { ...interiorLibraryControllerParamValues.value };
  interiorLibraryControllerPointerState.value = {
    mode: "controller",
    pointerId: event.pointerId,
    controllerId: String(controllerId || "").trim(),
    startPoint: point,
    startPan: null,
    startValues: { ...interiorLibraryControllerParamValues.value },
    pointerToAnchor: {
      x: (Number(point.x) || 0) - (Number(controller.anchor.x) || 0),
      y: (Number(point.y) || 0) - (Number(controller.anchor.y) || 0),
    },
    dirty: false,
  };
  interiorLibraryFrontSvgEl.value?.setPointerCapture?.(event.pointerId);
}

function handleInteriorLibraryControllerPointerDown(controllerId, event) {
  if (Number(event?.button) === 1) return;
  if (Number(event?.button) !== 0) return;
  beginInteriorLibraryControllerDrag(controllerId, event);
}

function handleInteriorLibraryControllerValuePointerDown(event) {
  if (Number(event?.button) === 1) return;
  event?.stopPropagation?.();
}

function stopInteriorLibraryControllerDrag() {
  if (interiorLibraryControllerPointerState.value.pointerId != null) {
    interiorLibraryFrontSvgEl.value?.releasePointerCapture?.(interiorLibraryControllerPointerState.value.pointerId);
  }
  const dirty = !!interiorLibraryControllerPointerState.value.dirty;
  const activeControllerId = String(interiorLibraryControllerPointerState.value.controllerId || "").trim();
  const draftValues = interiorLibraryControllerDraftValues.value ? { ...interiorLibraryControllerDraftValues.value } : null;
  interiorLibraryControllerPointerState.value = {
    mode: "idle",
    pointerId: null,
    controllerId: "",
    startPoint: null,
    startPan: null,
    startValues: null,
    pointerToAnchor: null,
    dirty: false,
  };
  interiorLibraryHoveredControllerId.value = activeControllerId;
  clearInteriorLibraryControllerDraftValues();
  if (!dirty) return;
  if (!draftValues || !updateInteriorInstanceFromControllerValues(draftValues)) return;
  persistActiveInteriorLibraryControllerInstance().catch((error) => {
    showAlert(error?.message || "ذخیره کنترلر نمونه داخلی انجام نشد.", { title: "خطا" });
  });
}

function applyInteriorLibraryControllerDrag(controllerId, currentPoint) {
  const state = interiorLibraryControllerPointerState.value;
  const frame = interiorLibraryControllerFrameRect.value;
  const startValues = state.startValues;
  if (!frame || !startValues || !currentPoint) return;
  const pointerToAnchor = state.pointerToAnchor || { x: 0, y: 0 };
  const anchorX = (Number(currentPoint.x) || 0) - (Number(pointerToAnchor.x) || 0);
  const anchorY = (Number(currentPoint.y) || 0) - (Number(pointerToAnchor.y) || 0);
  const snappedX = snapInteriorControllerAxis(controllerId, anchorX);
  const snappedY = snapInteriorControllerAxis(controllerId, anchorY);
  const frameWidth = Math.max(0, frame.maxX - frame.minX);
  const frameHeight = Math.max(0, frame.maxZ - frame.minZ);
  const minWidth = 240;
  const minHeight = 1;
  const nextValues = {
    left: Number(startValues.left) || 0,
    top: Number(startValues.top) || 0,
    right: Number(startValues.right) || 0,
    bottom_offset: Number(startValues.bottom_offset) || 0,
  };
  if (controllerId === "left") {
    const leftMm = (snappedX - frame.x) / frame.scale;
    nextValues.left = Math.min(Math.max(0, leftMm), Math.max(0, frameWidth - nextValues.right - minWidth));
  } else if (controllerId === "right") {
    const rightMm = ((frame.x + frame.w) - snappedX) / frame.scale;
    nextValues.right = Math.min(Math.max(0, rightMm), Math.max(0, frameWidth - nextValues.left - minWidth));
  } else if (controllerId === "top") {
    const topMm = ((frame.y + frame.h) - (Number(startValues.bottom_offset) || 0) * frame.scale - snappedY) / frame.scale;
    nextValues.top = Math.min(Math.max(minHeight, topMm), Math.max(minHeight, frameHeight - nextValues.bottom_offset));
  } else if (controllerId === "bottom_offset") {
    const bottomMm = ((frame.y + frame.h) - snappedY) / frame.scale - (Number(startValues.top) || 0);
    nextValues.bottom_offset = Math.min(Math.max(0, bottomMm), Math.max(0, frameHeight - nextValues.top));
  }
  interiorLibraryControllerDraftValues.value = nextValues;
  interiorLibraryControllerPointerState.value = {
    ...state,
    dirty: true,
  };
}
function onInteriorLibraryFrontSvgPointerDown(event) {
  if (interiorLibraryPreviewMode.value !== "front2d" || Number(event?.button) !== 0) return;
  if (interiorLibraryControllerState.value.enabled) {
    const controllerHit = hitTestInteriorLibraryController(getInteriorLibraryFrontSvgPoint(event));
    if (controllerHit) {
      beginInteriorLibraryControllerDrag(controllerHit.id, event);
      event.preventDefault();
      event.stopPropagation();
      return;
    }
  }
  const rawPoint = getInteriorLibraryFrontSvgPoint(event);
  if (!rawPoint) return;
  syncInteriorLibraryCursorPoint(rawPoint, interiorLibraryCurrentSnapPoint.value);
  const rendered = interiorLibraryRenderedAnnotations.value;
  const hitDimension = interiorLibraryShowDimensions.value
    ? hitTestInteriorAnnotationList(rendered.dimensions, rawPoint, 12)
    : null;
  const hitGuide = !hitDimension && interiorLibraryShowGuideAnnotations.value
    ? hitTestInteriorAnnotationList(rendered.guides, rawPoint, 10)
    : null;
  if (hitDimension || hitGuide) {
    interiorLibrarySelectedAnnotation.value = {
      type: hitDimension ? "dimension" : "guide",
      id: String((hitDimension || hitGuide)?.id || ""),
    };
    clearInteriorLibraryInstanceSelection();
    interiorLibraryAnnotationDraft.value = null;
    interiorLibraryCurrentSnapPoint.value = null;
    hideInteriorLibraryOverlapPicker();
    event.preventDefault();
    event.stopPropagation();
    return;
  }
  if (!interiorLibraryAnnotationTool.value) {
    const instanceHits = collectInteriorInstanceHits(rawPoint);
    if (instanceHits.length) {
      if (instanceHits.length === 1) {
        selectInteriorLibraryInstance(instanceHits[0].id);
        hideInteriorLibraryOverlapPicker();
        interiorLibraryCurrentSnapPoint.value = null;
        event.preventDefault();
        event.stopPropagation();
        return;
      }
      showInteriorLibraryOverlapPicker(event.clientX, event.clientY, instanceHits);
      interiorLibraryCurrentSnapPoint.value = null;
      event.preventDefault();
      event.stopPropagation();
      return;
    }
    hideInteriorLibraryOverlapPicker();
    clearInteriorLibraryAnnotationSelection();
    clearInteriorLibraryInstanceSelection();
    interiorLibraryCurrentSnapPoint.value = null;
    return;
  }
  hideInteriorLibraryOverlapPicker();
  const point = getInteriorLibrarySnappedFrontPoint(rawPoint);
  if (!point) return;
  if (!interiorLibraryAnnotationDraft.value) {
    interiorLibraryAnnotationDraft.value = createInteriorLibraryAnnotationDraft(interiorLibraryAnnotationTool.value, point);
  } else {
    updateInteriorLibraryAnnotationDraft(point);
    commitInteriorLibraryAnnotationDraft();
  }
  event.preventDefault();
  event.stopPropagation();
}
function onInteriorLibraryOverlapPickerPointerDown(event) {
  event.stopPropagation();
}
function onInteriorLibraryOverlapPickerLeave() {
  clearInteriorLibraryOverlapPreview();
}
function onInteriorLibraryFrontSvgPointerMove(event) {
  const rawPoint = getInteriorLibraryFrontSvgPoint(event);
  if (!rawPoint) return;
  if (interiorLibraryControllerPointerState.value.mode === "controller") {
    syncInteriorLibraryCursorPoint(rawPoint, null);
    applyInteriorLibraryControllerDrag(interiorLibraryControllerPointerState.value.controllerId, rawPoint);
    return;
  }
  const controllerHit = hitTestInteriorLibraryController(rawPoint);
  interiorLibraryHoveredControllerId.value = controllerHit?.id || "";
  if (!interiorLibraryAnnotationTool.value) {
    interiorLibraryCurrentSnapPoint.value = null;
    syncInteriorLibraryCursorPoint(rawPoint, null);
    updateInteriorLibraryHoverState(rawPoint);
    return;
  }
  hideInteriorLibraryOverlapPicker();
  const point = getInteriorLibrarySnappedFrontPoint(rawPoint);
  syncInteriorLibraryCursorPoint(rawPoint, point);
  interiorLibraryHoverMode.value = null;
  interiorLibraryHoveredInstanceId.value = "";
  if (!point) return;
  if (!interiorLibraryAnnotationDraft.value) return;
  updateInteriorLibraryAnnotationDraft(point);
}
function onInteriorLibraryFrontSvgPointerLeave() {
  if (interiorLibraryControllerPointerState.value.mode === "controller") return;
  interiorLibraryCurrentSnapPoint.value = null;
  clearInteriorLibraryCursorPoint();
  interiorLibraryHoverMode.value = null;
  interiorLibraryHoveredInstanceId.value = "";
  interiorLibraryHoveredControllerId.value = "";
  clearInteriorLibraryOverlapPreview();
}

function onInteriorLibraryFrontSvgPointerUp() {
  if (interiorLibraryControllerPointerState.value.mode === "controller") {
    stopInteriorLibraryControllerDrag();
  }
}

function onInteriorLibraryFrontSvgPointerCancel() {
  if (interiorLibraryControllerPointerState.value.mode === "controller") {
    stopInteriorLibraryControllerDrag();
  }
}
function stopInteriorLibraryModelPanCursor() {
  interiorLibraryModelPanning.value = false;
  window.removeEventListener("pointerup", stopInteriorLibraryModelPanCursor);
  window.removeEventListener("pointercancel", stopInteriorLibraryModelPanCursor);
}
function onInteriorLibraryViewerPointerMove(event) {
  if (interiorLibraryPreviewMode.value === "model3d") {
    syncInteriorLibraryViewerCursorPoint(event);
    return;
  }
  if (interiorLibraryPreviewMode.value === "front2d" && interiorLibraryFrontPanning.value) {
    const rawPoint = getInteriorLibraryFrontSvgPoint(event);
    if (rawPoint) syncInteriorLibraryCursorPoint(rawPoint, null);
  }
}
function onInteriorLibraryViewerPointerLeave() {
  clearInteriorLibraryViewerCursorPoint();
  if (interiorLibraryPreviewMode.value === "model3d") {
    stopInteriorLibraryModelPanCursor();
  }
}
function onInteriorLibraryViewerPointerDown(event) {
  if (interiorLibraryPreviewMode.value === "model3d") {
    syncInteriorLibraryViewerCursorPoint(event);
    if (Number(event?.button) === 1 || Number(event?.button) === 2) {
      interiorLibraryModelPanning.value = true;
      window.addEventListener("pointerup", stopInteriorLibraryModelPanCursor, { once: true });
      window.addEventListener("pointercancel", stopInteriorLibraryModelPanCursor, { once: true });
    }
    return;
  }
  startInteriorLibraryFrontPan(event);
}
function getInteriorLibraryAddingGroupKey(group) {
  const groupId = String(group?.id || "").trim();
  if (!groupId) return "";
  return `${subCategoryDesignEditorOpen.value ? "subcat" : "order"}:${groupId}`;
}
function isAddingInteriorGroup(group) {
  return String(interiorLibraryAddingGroupKey.value || "") === getInteriorLibraryAddingGroupKey(group);
}
const paramGroupIconInputEl = ref(null);
const constructionImportPreviewRows = ref([]);
const constructionImportFileName = ref("");
const constructionImportPreviewKind = ref(null);
const activeParamGroupIconRowId = ref(null);
const constructionUploadingIconRowId = ref(null);
const constructionTables = [
  { id: "templates", title: "تمپلیت‌ها", status: "active" },
  { id: "categories", title: "دسته‌بندی‌ها", status: "active" },
  { id: "part_kinds", title: "انواع قطعات", status: "active" },
  { id: "param_groups", title: "گروه پارامترها", status: "active" },
  { id: "params", title: "پارامترها", status: "active" },
  { id: "sub_categories", title: "ساب‌کت‌ها", status: "active" },
  { id: "sub_category_designs", title: "طرح‌های ساب‌کت", status: "active" },
  { id: "internal_part_groups", title: "گروه قطعات داخلی", status: "active" },
  { id: "base_formulas", title: "فرمول های پایه", status: "active" },
  { id: "part_formulas", title: "فرمول های قطعات", status: "active" },
];
const constructionTemplates = computed(() =>
  editableTemplates.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => {
      const orderDelta = (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
      if (orderDelta !== 0) return orderDelta;
      return (Number(a.temp_id) || 0) - (Number(b.temp_id) || 0);
    })
);
const systemTemplatesCount = computed(() => constructionTemplates.value.filter((item) => item.admin_id === null).length);
const adminTemplatesCount = computed(() => constructionTemplates.value.filter((item) => item.admin_id === currentAdminId.value).length);
const constructionTemplateDuplicateState = computed(() => buildDuplicateState(editableTemplates.value, ["temp_id", "temp_title"]));
const constructionCategories = computed(() =>
  editableCategories.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => {
      const orderDelta = (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
      if (orderDelta !== 0) return orderDelta;
      return (Number(a.cat_id) || 0) - (Number(b.cat_id) || 0);
    })
);
const systemCategoriesCount = computed(() => constructionCategories.value.filter((item) => item.admin_id === null).length);
const adminCategoriesCount = computed(() => constructionCategories.value.filter((item) => item.admin_id === currentAdminId.value).length);
const constructionCategoryDuplicateState = computed(() => buildDuplicateState(editableCategories.value, ["cat_id"]));
const constructionSubCategories = computed(() =>
  editableSubCategories.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => {
      const orderDelta = (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
      if (orderDelta !== 0) return orderDelta;
      return (Number(a.sub_cat_id) || 0) - (Number(b.sub_cat_id) || 0);
    })
);
const constructionSubCategoryDesigns = computed(() =>
  editableSubCategoryDesigns.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => {
      if (!!a.is_system !== !!b.is_system) return a.is_system ? -1 : 1;
      const orderDelta = (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
      if (orderDelta !== 0) return orderDelta;
        return (Number(a.design_id) || 0) - (Number(b.design_id) || 0);
    })
);
const systemSubCategoryDesignsCount = computed(() => constructionSubCategoryDesigns.value.filter((item) => item.admin_id === null).length);
const adminSubCategoryDesignsCount = computed(() => constructionSubCategoryDesigns.value.filter((item) => item.admin_id === currentAdminId.value).length);
const systemSubCategoriesCount = computed(() => constructionSubCategories.value.filter((item) => item.admin_id === null).length);
const adminSubCategoriesCount = computed(() => constructionSubCategories.value.filter((item) => item.admin_id === currentAdminId.value).length);
const constructionSubCategoryDuplicateState = computed(() => buildDuplicateState(editableSubCategories.value, ["sub_cat_id"]));
const constructionPartKinds = computed(() =>
  editablePartKinds.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => {
      const orderDelta = (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
      if (orderDelta !== 0) return orderDelta;
      return String(a.org_part_kind_title || a.title || "").localeCompare(
        String(b.org_part_kind_title || b.title || ""),
        "fa"
      );
    })
);
const constructionInternalPartGroups = computed(() =>
  editableInternalPartGroups.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => {
      if (!!a.is_system !== !!b.is_system) return a.is_system ? -1 : 1;
      const orderDelta = (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
      if (orderDelta !== 0) return orderDelta;
      return (Number(a.group_id) || 0) - (Number(b.group_id) || 0);
    })
);
const constructionPartKindsById = computed(() =>
  new Map(constructionPartKinds.value.map((item) => [Number(item.part_kind_id) || 0, item]))
);
const constructionPartKindOptions = computed(() =>
  constructionPartKinds.value.map((item) => ({
    value: Number(item.part_kind_id) || 0,
    label: `${toPersianDigits(item.part_kind_id)} - ${String(item.org_part_kind_title || item.title || "").trim()}`,
  }))
);
const systemPartKindsCount = computed(() => constructionPartKinds.value.filter((item) => item.admin_id === null).length);
const adminPartKindsCount = computed(() => constructionPartKinds.value.filter((item) => item.admin_id === currentAdminId.value).length);
const internalPartKindsCount = computed(() => constructionPartKinds.value.filter((item) => normalizeBooleanFlag(item.is_internal, false)).length);
const constructionPartKindDuplicateState = computed(() => buildDuplicateState(editablePartKinds.value, ["part_kind_id", "part_kind_code"]));
const constructionHasPendingChanges = computed(
  () =>
    constructionDeletedPartKindIds.value.length > 0 ||
    constructionDeletedTemplateIds.value.length > 0 ||
    constructionDeletedCategoryIds.value.length > 0 ||
    constructionDeletedParamGroupIds.value.length > 0 ||
    constructionDeletedParamIds.value.length > 0 ||
    constructionDeletedSubCategoryIds.value.length > 0 ||
    constructionDeletedBaseFormulaIds.value.length > 0 ||
    constructionDeletedPartFormulaIds.value.length > 0 ||
    editableTemplates.value.some((item) => !!item.__isNew || !!item.__dirty) ||
    editableCategories.value.some((item) => !!item.__isNew || !!item.__dirty) ||
    editablePartKinds.value.some((item) => !!item.__isNew || !!item.__dirty) ||
    editableParamGroups.value.some((item) => !!item.__isNew || !!item.__dirty) ||
    editableParams.value.some((item) => !!item.__isNew || !!item.__dirty) ||
    editableSubCategories.value.some((item) => !!item.__isNew || !!item.__dirty) ||
    editableBaseFormulas.value.some((item) => !!item.__isNew || !!item.__dirty) ||
    editablePartFormulas.value.some((item) => !!item.__isNew || !!item.__dirty)
);
const constructionImportPreviewCount = computed(() => constructionImportPreviewRows.value.length);
const constructionParamGroups = computed(() =>
  editableParamGroups.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => {
      const orderDelta = (Number(a.ui_order) || 0) - (Number(b.ui_order) || 0);
      if (orderDelta !== 0) return orderDelta;
      return (Number(a.param_group_id) || 0) - (Number(b.param_group_id) || 0);
    })
);
const systemParamGroupsCount = computed(() => constructionParamGroups.value.filter((item) => item.admin_id === null).length);
const adminParamGroupsCount = computed(() => constructionParamGroups.value.filter((item) => item.admin_id === currentAdminId.value).length);
const constructionParams = computed(() =>
  editableParams.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => {
      const orderDelta = (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
      if (orderDelta !== 0) return orderDelta;
      return (Number(a.param_id) || 0) - (Number(b.param_id) || 0);
    })
);
const systemParamsCount = computed(() => constructionParams.value.filter((item) => item.admin_id === null).length);
const adminParamsCount = computed(() => constructionParams.value.filter((item) => item.admin_id === currentAdminId.value).length);
const constructionBaseFormulas = computed(() =>
  editableBaseFormulas.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => {
      const orderDelta = (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
      if (orderDelta !== 0) return orderDelta;
      return (Number(a.fo_id) || 0) - (Number(b.fo_id) || 0);
    })
);
const systemBaseFormulasCount = computed(() => constructionBaseFormulas.value.filter((item) => item.admin_id === null).length);
const adminBaseFormulasCount = computed(() => constructionBaseFormulas.value.filter((item) => item.admin_id === currentAdminId.value).length);
const constructionPartFormulas = computed(() =>
  editablePartFormulas.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => {
      const orderDelta = (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0);
      if (orderDelta !== 0) return orderDelta;
      return (Number(a.part_formula_id) || 0) - (Number(b.part_formula_id) || 0);
    })
);
const systemPartFormulasCount = computed(() => constructionPartFormulas.value.filter((item) => item.admin_id === null).length);
const adminPartFormulasCount = computed(() => constructionPartFormulas.value.filter((item) => item.admin_id === currentAdminId.value).length);
const constructionTemplateOptions = computed(() =>
  constructionTemplates.value.map((item) => ({
    value: Number(item.temp_id),
    label: `${toPersianDigits(item.temp_id)} - ${String(item.temp_title || "").trim()}`,
  }))
);
const constructionSubCategoryParamColumns = computed(() =>
  constructionParams.value.map((item) => ({
    key: String(item.param_code || "").trim(),
    label: String(item.param_title_fa || item.title || item.param_code || "").trim(),
  })).filter((item) => item.key)
);
const constructionSubCategoryParamMetaByCode = computed(() =>
  Object.fromEntries(
    constructionSubCategoryParamColumns.value.map((item) => [
      item.key,
      { label: item.label || item.key },
    ])
  )
);
const constructionParamsByCode = computed(() =>
  new Map(
    constructionParams.value
      .map((item) => [String(item.param_code || "").trim(), item])
      .filter(([code]) => code)
  )
);
const constructionSubCategoryParamTree = computed(() => {
  const groupsById = new Map(
    constructionParamGroups.value.map((group) => [
      String(group.param_group_id),
      {
        id: String(group.param_group_id),
        title: String(group.org_param_group_title || group.title || group.param_group_code || `گروه ${group.param_group_id}` || "").trim(),
        iconFileName: normalizeIconFileName(group.param_group_icon_path),
        iconUrl: normalizeIconFileName(group.param_group_icon_path)
          ? `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/icons/${encodeURIComponent(normalizeIconFileName(group.param_group_icon_path))}`
          : "",
        order: Number.isFinite(Number(group.ui_order)) ? Number(group.ui_order) : Number(group.param_group_id) || 0,
        showInOrderAttrs: normalizeBooleanFlag(group.show_in_order_attrs, true),
        items: [],
      },
    ])
  );
  const ungroupedKey = "__ungrouped__";
  for (const param of constructionParams.value) {
    const key = String(param.param_code || "").trim();
    if (!key) continue;
    const groupId = String(param.param_group_id ?? "").trim();
    if (groupId && !groupsById.has(groupId)) {
      groupsById.set(groupId, {
        id: groupId,
        title: `گروه ${toPersianDigits(groupId)}`,
        iconFileName: "",
        iconUrl: "",
        order: Number(groupId) || Number.MAX_SAFE_INTEGER - 1,
        items: [],
      });
    }
    if (!groupId && !groupsById.has(ungroupedKey)) {
      groupsById.set(ungroupedKey, {
        id: ungroupedKey,
        title: "بدون گروه",
        iconFileName: "",
        iconUrl: "",
        order: Number.MAX_SAFE_INTEGER,
        items: [],
      });
    }
    const target = groupsById.get(groupId || ungroupedKey);
    if (!target) continue;
    target.items.push({
      key,
      label: String(param.param_title_fa || param.title || key).trim(),
      code: key,
      order: Number.isFinite(Number(param.ui_order))
        ? Number(param.ui_order)
        : Number.isFinite(Number(param.sort_order))
          ? Number(param.sort_order)
          : Number(param.param_id) || 0,
      id: Number(param.param_id) || 0,
    });
  }
  return Array.from(groupsById.values())
    .map((group) => ({
      ...group,
      items: group.items
        .slice()
        .sort((a, b) => {
          const orderDelta = a.order - b.order;
          if (orderDelta !== 0) return orderDelta;
          return a.id - b.id;
        }),
    }))
    .filter((group) => group.items.length)
    .sort((a, b) => {
      const orderDelta = a.order - b.order;
      if (orderDelta !== 0) return orderDelta;
      return a.title.localeCompare(b.title, "fa");
    });
});
const activeSubCategoryDefaultsRow = computed(() =>
  editableSubCategories.value.find((item) => String(item.id) === String(subCategoryDefaultsEditorRowId.value)) || null
);
const activeSubCategoryDefaultsGroup = computed(() =>
  constructionSubCategoryParamTree.value.find((group) => String(group.id) === String(subCategoryDefaultsActiveGroupId.value))
  || constructionSubCategoryParamTree.value[0]
  || null
);
const activeSubCategoryDefaultsCount = computed(() =>
  Object.values(subCategoryDefaultsEditorDraft.value || {}).filter((value) => String(value || "").trim()).length
);
const activeInternalPartGroupDefaultsRow = computed(() =>
  editableInternalPartGroups.value.find((item) => String(item.id) === String(internalPartGroupDefaultsEditorRowId.value)) || null
);
const activeInternalPartGroupDefaultsGroups = computed(() => internalPartGroupDefaultsEditorGroups.value);
const activeInternalPartGroupDefaultsGroup = computed(() =>
  activeInternalPartGroupDefaultsGroups.value.find((group) => String(group.id) === String(internalPartGroupDefaultsActiveGroupId.value))
  || activeInternalPartGroupDefaultsGroups.value[0]
  || null
);
const activeInternalPartGroupControllerRow = computed(() =>
  editableInternalPartGroups.value.find((item) => String(item.id) === String(internalPartGroupControllerEditorRowId.value)) || null
);
const activeInteriorInstanceEditorGroups = computed(() => buildInteriorInstanceGroups(interiorInstanceEditorDraft.value));
const activeInteriorInstanceEditorGroup = computed(() =>
  activeInteriorInstanceEditorGroups.value.find((group) => String(group.id) === String(interiorInstanceEditorActiveGroupId.value))
  || activeInteriorInstanceEditorGroups.value[0]
  || null
);
const constructionSubCategoryDesignSubCategoryOptions = computed(() =>
  constructionSubCategories.value.map((item) => ({
    value: String(item.id),
    label: `${toPersianDigits(item.temp_id)} / ${toPersianDigits(item.cat_id)} / ${toPersianDigits(item.sub_cat_id)} - ${String(item.sub_cat_title || "").trim()}`,
  }))
);
const constructionSubCategoryDesignPartFormulaOptions = computed(() =>
  constructionPartFormulas.value
    .filter((item) => {
      const partKind = constructionPartKindsById.value.get(Number(item.part_kind_id) || 0);
      return !normalizeBooleanFlag(partKind?.is_internal, false);
    })
    .map((item) => ({
      id: Number(item.part_formula_id),
      title: String(item.part_title || item.title || item.part_code || "").trim(),
      code: String(item.part_code || "").trim(),
      partKindId: Number(item.part_kind_id) || 0,
      uiOrder: Number(item.sort_order) || Number(item.part_formula_id) || 0,
    }))
);
const constructionInteriorPartFormulaOptions = computed(() =>
  constructionPartFormulas.value
    .filter((item) => {
      const partKind = constructionPartKindsById.value.get(Number(item.part_kind_id) || 0);
      return normalizeBooleanFlag(partKind?.is_internal, false);
    })
    .map((item) => {
      const partKind = constructionPartKindsById.value.get(Number(item.part_kind_id) || 0);
      return {
        id: Number(item.part_formula_id),
        title: String(item.part_title || item.title || item.part_code || "").trim(),
        code: String(item.part_code || "").trim(),
        partKindTitle: String(partKind?.org_part_kind_title || partKind?.title || "").trim(),
      };
    })
);
const constructionInternalParamGroupOptions = computed(() =>
  constructionParamGroups.value
    .map((item) => ({
      id: Number(item.param_group_id),
      title: String(item.org_param_group_title || item.title || item.param_group_code || "").trim(),
      code: String(item.param_group_code || item.code || "").trim(),
      iconPath: normalizeIconFileName(item.param_group_icon_path) || "",
      uiOrder: Number(item.ui_order) || Number(item.param_group_id) || 0,
    }))
    .filter((item) => item.id > 0 && item.title)
    .sort((a, b) => a.uiOrder - b.uiOrder || a.id - b.id)
);
const constructionInternalPartGroupsById = computed(() =>
  new Map(
    constructionInternalPartGroups.value
      .map((item) => [String(item.id), item])
      .filter(([id]) => id)
  )
);
const activeInteriorLibrarySubCategory = computed(() => {
  const subCategoryId = String(subCategoryDesignEditorDraft.value?.sub_category_id || "").trim();
  if (!subCategoryId) return null;
  return constructionSubCategories.value.find((item) => String(item.id) === subCategoryId) || null;
});
const activeInteriorLibraryOrderDesignId = computed(() => {
  if (subCategoryDesignEditorOpen.value) return "";
  const forcedId = String(interiorLibraryForcedOrderDesignId.value || "").trim();
  if (forcedId) return forcedId;
  return String(activeCabinetDesignId.value || "").trim();
});
const activeInteriorLibraryOrderDesign = computed(() => {
  if (subCategoryDesignEditorOpen.value) return null;
  const targetId = activeInteriorLibraryOrderDesignId.value;
  if (!targetId) return null;
  return orderDesignCatalog.value.find((item) => String(item.id) === targetId) || null;
});
const activeInteriorLibrarySourceDesign = computed(() => {
  if (subCategoryDesignEditorOpen.value) return null;
  const sourceId = String(activeInteriorLibraryOrderDesign.value?.sub_category_design_id || "").trim();
  if (!sourceId) return null;
  return editableSubCategoryDesigns.value.find((item) => String(item.id) === sourceId)
    || cabinetDesignCatalog.value.find((item) => String(item.id) === sourceId)
    || null;
});
const activeInteriorLibraryTargetId = computed(() =>
  subCategoryDesignEditorOpen.value
    ? String(subCategoryDesignEditorDraft.value?.id || "").trim()
    : String(activeInteriorLibraryOrderDesign.value?.id || "").trim()
);
const activeInteriorLibraryInstances = computed(() =>
  subCategoryDesignEditorOpen.value
    ? (subCategoryDesignEditorDraft.value?.interior_instances || [])
    : (activeInteriorLibraryOrderDesign.value?.interior_instances || [])
);
const activeInteriorLibraryBaseParamValues = computed(() => {
  if (subCategoryDesignEditorOpen.value) {
    if (subCategoryDesignEditorPreview.value?.resolved_params) {
      return Object.fromEntries(
        Object.entries(subCategoryDesignEditorPreview.value.resolved_params || {}).map(([key, value]) => [String(key), value == null ? "" : String(value)])
      );
    }
    return Object.fromEntries(
      Object.entries(activeInteriorLibrarySubCategory.value?.param_defaults || {}).map(([key, value]) => [String(key), value == null ? "" : String(value)])
    );
  }
  return Object.fromEntries(
    Object.entries(activeInteriorLibraryOrderDesign.value?.order_attr_values || {}).map(([key, value]) => [String(key), value == null ? "" : String(value)])
  );
});
const FRONT_VIEW_WIDTH = DEFAULT_FRONT_VIEW_WIDTH;
const FRONT_VIEW_HEIGHT = DEFAULT_FRONT_VIEW_HEIGHT;
const FRONT_VIEW_PAD = 28;
const DEFAULT_INTERIOR_LINE_COLOR = "#8A98A3";
const interiorLibraryViewerWrapEl = ref(null);
const interiorLibraryFrontViewport = ref({
  width: DEFAULT_FRONT_VIEW_WIDTH,
  height: DEFAULT_FRONT_VIEW_HEIGHT,
});
let interiorLibraryFrontViewportObserver = null;

function syncInteriorLibraryFrontViewport() {
  const el = interiorLibraryViewerWrapEl.value;
  if (!el) {
    interiorLibraryFrontViewport.value = {
      width: DEFAULT_FRONT_VIEW_WIDTH,
      height: DEFAULT_FRONT_VIEW_HEIGHT,
    };
    return;
  }
  const styles = window.getComputedStyle(el);
  const padX = (parseFloat(styles.paddingLeft) || 0) + (parseFloat(styles.paddingRight) || 0);
  const padY = (parseFloat(styles.paddingTop) || 0) + (parseFloat(styles.paddingBottom) || 0);
  interiorLibraryFrontViewport.value = {
    width: Math.max(320, Math.round(el.clientWidth - padX)),
    height: Math.max(320, Math.round(el.clientHeight - padY)),
  };
}

function getViewerBoxesFromPartSnapshots(partSnapshots) {
  return (Array.isArray(partSnapshots) ? partSnapshots : [])
    .map((row) => row?.viewer_payload?.box)
    .filter((box) => box && typeof box === "object")
    .map((box) => ({ ...(box || {}) }));
}

function getViewerBoxesFromPreviewParts(parts) {
  return (Array.isArray(parts) ? parts : [])
    .map((row) => row?.viewer_payload?.box)
    .filter((box) => box && typeof box === "object")
    .map((box) => ({ ...(box || {}) }));
}

function getViewerBoxesFromInteriorInstance(instance) {
  const directBoxes = (Array.isArray(instance?.viewer_boxes) ? instance.viewer_boxes : [])
    .filter((box) => box && typeof box === "object")
    .map((box) => ({ ...(box || {}) }));
  if (directBoxes.length) return directBoxes;

  const snapshotBoxes = getViewerBoxesFromPartSnapshots(instance?.part_snapshots || []);
  if (snapshotBoxes.length) return snapshotBoxes;

  const fallbackBox = instance?.interior_box_snapshot;
  if (fallbackBox && typeof fallbackBox === "object" && Object.keys(fallbackBox).length) {
    return [{ ...(fallbackBox || {}) }];
  }

  return [];
}

function buildFrontViewLinesFromBoxes(boxes) {
  const normalized = Array.isArray(boxes) ? boxes.map(normalizeCabinetBox) : [];
  if (!normalized.length) {
    return { outer: [], inner: [], bounds: null };
  }
  let minX = Infinity;
  let maxX = -Infinity;
  let minZ = Infinity;
  let maxZ = -Infinity;
  const inner = [];
  for (const box of normalized) {
    const halfW = box.width * 0.5;
    const halfH = box.height * 0.5;
    const x1 = box.cx - halfW;
    const x2 = box.cx + halfW;
    const z1 = box.cz - halfH;
    const z2 = box.cz + halfH;
    minX = Math.min(minX, x1);
    maxX = Math.max(maxX, x2);
    minZ = Math.min(minZ, z1);
    maxZ = Math.max(maxZ, z2);
    inner.push(
      { ax: x1, az: z1, bx: x2, bz: z1 },
      { ax: x2, az: z1, bx: x2, bz: z2 },
      { ax: x2, az: z2, bx: x1, bz: z2 },
      { ax: x1, az: z2, bx: x1, bz: z1 },
    );
  }
  const bounds = { minX, maxX, minZ, maxZ };
  const outer = [
    { ax: minX, az: minZ, bx: maxX, bz: minZ },
    { ax: maxX, az: minZ, bx: maxX, bz: maxZ },
    { ax: maxX, az: maxZ, bx: minX, bz: maxZ },
    { ax: minX, az: maxZ, bx: minX, bz: minZ },
  ];
  return { outer, inner, bounds };
}

const activeInteriorLibraryViewerBoxes = computed(() => {
  if (subCategoryDesignEditorOpen.value) {
    return subCategoryDesignEditorPreview.value?.viewer_boxes || [];
  }
  const mergedBoxes = Array.isArray(activeInteriorLibraryOrderDesign.value?.viewer_boxes)
    ? activeInteriorLibraryOrderDesign.value.viewer_boxes
    : [];
  if (mergedBoxes.length) return mergedBoxes;
  const rootBoxes = getViewerBoxesFromPartSnapshots(activeInteriorLibraryOrderDesign.value?.part_snapshots || []);
  if (rootBoxes.length) return rootBoxes;
  const sourceBoxes = Array.isArray(activeInteriorLibrarySourceDesign.value?.preview?.viewer_boxes)
    ? activeInteriorLibrarySourceDesign.value.preview.viewer_boxes
    : [];
  return sourceBoxes;
});
const activeInteriorLibraryStructureViewerBoxes = computed(() => {
  if (subCategoryDesignEditorOpen.value) {
    return getViewerBoxesFromPreviewParts(subCategoryDesignEditorPreview.value?.parts || []);
  }
  const rootBoxes = getViewerBoxesFromPartSnapshots(activeInteriorLibraryOrderDesign.value?.part_snapshots || []);
  if (rootBoxes.length) return rootBoxes;
  const sourceBoxes = getViewerBoxesFromPreviewParts(activeInteriorLibrarySourceDesign.value?.preview?.parts || []);
  if (sourceBoxes.length) return sourceBoxes;
  return [];
});
const interiorLibraryFrontView = computed(() =>
  buildFrontViewLinesFromBoxes(activeInteriorLibraryStructureViewerBoxes.value || [])
);
const interiorLibraryPreviewProjection = computed(() => {
  const bounds = interiorLibraryFrontView.value?.bounds;
  if (!bounds) return null;
  const width = Math.max(320, Number(interiorLibraryFrontViewport.value?.width) || FRONT_VIEW_WIDTH);
  const height = Math.max(320, Number(interiorLibraryFrontViewport.value?.height) || FRONT_VIEW_HEIGHT);
  const pad = FRONT_VIEW_PAD;
  const spanX = Math.max(1, bounds.maxX - bounds.minX);
  const spanZ = Math.max(1, bounds.maxZ - bounds.minZ);
  const scale = Math.min((width - pad * 2) / spanX, (height - pad * 2) / spanZ);
  const cx = (bounds.minX + bounds.maxX) * 0.5;
  const cz = (bounds.minZ + bounds.maxZ) * 0.5;
  return {
    scale,
    centerX: cx,
    centerZ: cz,
    project(line, sw, dashed = false) {
      return {
        x1: width * 0.5 + (Number(line.ax) - cx) * scale,
        y1: height * 0.5 - (Number(line.az) - cz) * scale,
        x2: width * 0.5 + (Number(line.bx) - cx) * scale,
        y2: height * 0.5 - (Number(line.bz) - cz) * scale,
        sw,
        dashed,
      };
    },
    unprojectPoint(point) {
      const x = Number(point?.x);
      const y = Number(point?.y);
      if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(scale) || scale <= 0) return null;
      return {
        x: cx + (x - width * 0.5) / scale,
        z: cz - (y - height * 0.5) / scale,
      };
    },
  };
});
const interiorLibraryPreviewSvgLines = computed(() => {
  const data = interiorLibraryFrontView.value;
  const projection = interiorLibraryPreviewProjection.value;
  if (!data?.bounds || !projection) return { outer: [], inner: [] };
  return {
    outer: (data.outer || []).map((line) => projection.project(line, 2.2, false)),
    inner: (data.inner || []).map((line) => projection.project(line, 1.2, true)),
  };
});
function resolveInteriorInstanceLineColor(instance) {
  const group = constructionInternalPartGroupsById.value.get(String(instance?.internal_part_group_id || "").trim());
  return normalizeHexColor(
    instance?.line_color
    || group?.line_color
    || DEFAULT_INTERIOR_LINE_COLOR,
    DEFAULT_INTERIOR_LINE_COLOR
  );
}
const interiorLibraryPreviewInstanceSvgLines = computed(() => {
  const projection = interiorLibraryPreviewProjection.value;
  if (!projection) return [];
  return activeInteriorLibraryInstances.value
    .slice()
    .sort((a, b) => (Number(a?.ui_order) || 0) - (Number(b?.ui_order) || 0) || String(a?.instance_code || "").localeCompare(String(b?.instance_code || ""), "fa"))
    .flatMap((instance) => {
      const lineColor = resolveInteriorInstanceLineColor(instance);
      return buildFrontViewLinesFromBoxes(getViewerBoxesFromInteriorInstance(instance)).inner.map((line, index) => ({
        ...projection.project(line, 1.15, true),
        color: lineColor,
        key: `${String(instance?.id || instance?.instance_code || "instance")}-${index}`,
      }));
    });
});
const interiorLibraryPreviewInstances2d = computed(() => {
  const projection = interiorLibraryPreviewProjection.value;
  if (!projection) return [];
  return activeInteriorLibraryInstances.value
    .slice()
    .sort((a, b) => (Number(a?.ui_order) || 0) - (Number(b?.ui_order) || 0) || String(a?.instance_code || "").localeCompare(String(b?.instance_code || ""), "fa"))
    .map((instance, index) => {
      const data = buildFrontViewLinesFromBoxes(getViewerBoxesFromInteriorInstance(instance));
      if (!data?.bounds) return null;
      const group = constructionInternalPartGroupsById.value.get(String(instance?.internal_part_group_id || ""));
      const lineColor = resolveInteriorInstanceLineColor(instance);
      const outerLines = (data.outer || []).map((line) => projection.project(line, 1.8, false));
      const innerLines = (data.inner || []).map((line) => projection.project(line, 1.15, true));
      const x1 = projection.project({ ax: data.bounds.minX, az: data.bounds.minZ, bx: data.bounds.minX, bz: data.bounds.minZ }, 1, false).x1;
      const y1 = projection.project({ ax: data.bounds.minX, az: data.bounds.maxZ, bx: data.bounds.minX, bz: data.bounds.maxZ }, 1, false).y1;
      const x2 = projection.project({ ax: data.bounds.maxX, az: data.bounds.minZ, bx: data.bounds.maxX, bz: data.bounds.minZ }, 1, false).x1;
      const y2 = projection.project({ ax: data.bounds.minX, az: data.bounds.minZ, bx: data.bounds.minX, bz: data.bounds.minZ }, 1, false).y1;
      return {
        id: String(instance?.id || "").trim(),
        instanceCode: String(instance?.instance_code || "").trim(),
        groupTitle: String(group?.group_title || group?.title || instance?.instance_code || "قطعه داخلی").trim(),
        lineColor,
        visualOrder: index,
        outerLines,
        innerLines,
        boundsRect: {
          x: Math.min(x1, x2),
          y: Math.min(y1, y2),
          w: Math.abs(x2 - x1),
          h: Math.abs(y2 - y1),
        },
      };
    })
    .filter(Boolean);
});
const interiorLibraryControllerVisualScale = computed(() => {
  const zoom = Math.min(
    INTERIOR_LIBRARY_FRONT_ZOOM_MAX,
    Math.max(INTERIOR_LIBRARY_FRONT_ZOOM_MIN, Number(interiorLibraryFrontZoom.value) || 1)
  );
  return 1 / zoom;
});
const activeInteriorLibrarySelectedInstance = computed(() =>
  activeInteriorLibraryInstances.value.find((item) => String(item?.id || "").trim() === String(interiorLibrarySelectedInstanceId.value || "").trim()) || null
);
const activeInteriorLibrarySelectedGroup = computed(() =>
  constructionInternalPartGroupsById.value.get(String(activeInteriorLibrarySelectedInstance.value?.internal_part_group_id || "").trim()) || null
);
const interiorLibraryControllerDefinitions = computed(() =>
  getInternalPartGroupControllerDefinitions(activeInteriorLibrarySelectedGroup.value?.controller_type)
);
const interiorLibraryControllerBindingMap = computed(() => {
  const group = activeInteriorLibrarySelectedGroup.value;
  if (!group) return {};
  const allowedCodes = new Set(getInternalPartGroupSelectedParamColumns(group).map((column) => column.key));
  return normalizeInternalPartGroupControllerBindings(group.controller_type, group.controller_bindings, allowedCodes);
});
const interiorLibraryControllerFrameRect = computed(() => {
  const projection = interiorLibraryPreviewProjection.value;
  const bounds = interiorLibraryFrontView.value?.bounds;
  if (!projection || !bounds) return null;
  const left = projection.project({ ax: bounds.minX, az: bounds.minZ, bx: bounds.minX, bz: bounds.minZ }, 1, false).x1;
  const right = projection.project({ ax: bounds.maxX, az: bounds.minZ, bx: bounds.maxX, bz: bounds.minZ }, 1, false).x1;
  const top = projection.project({ ax: bounds.minX, az: bounds.maxZ, bx: bounds.minX, bz: bounds.maxZ }, 1, false).y1;
  const bottom = projection.project({ ax: bounds.minX, az: bounds.minZ, bx: bounds.minX, bz: bounds.minZ }, 1, false).y1;
  return {
    x: Math.min(left, right),
    y: Math.min(top, bottom),
    w: Math.abs(right - left),
    h: Math.abs(bottom - top),
    minX: Number(bounds.minX) || 0,
    maxX: Number(bounds.maxX) || 0,
    minZ: Number(bounds.minZ) || 0,
    maxZ: Number(bounds.maxZ) || 0,
    scale: Number(projection.scale) || 1,
  };
});
const interiorLibraryControllerOverlays = computed(() => {
  const frame = interiorLibraryControllerFrameRect.value;
  if (!frame || interiorLibraryPreviewMode.value !== "front2d") return [];
  return activeInteriorLibraryInstances.value
    .map((instance) => buildInteriorLibraryControllerOverlayForInstance(instance, frame))
    .filter(Boolean);
});
const interiorLibrarySelectedControllerOverlay = computed(() =>
  interiorLibraryControllerOverlays.value.find(
    (item) => String(item?.instanceId || "") === String(activeInteriorLibrarySelectedInstance.value?.id || "")
  ) || null
);
const interiorLibraryControllerParamValues = computed(() => interiorLibraryControllerDraftValues.value || interiorLibrarySelectedControllerOverlay.value?.values || {});
const interiorLibraryControllerRect = computed(() =>
  buildInteriorLibraryControllerRectFromFrameValues(
    interiorLibraryControllerFrameRect.value,
    interiorLibraryControllerParamValues.value,
  ) || interiorLibrarySelectedControllerOverlay.value?.rect || null
);
const interiorLibraryControllerState = computed(() => {
  const group = activeInteriorLibrarySelectedGroup.value;
  const instance = activeInteriorLibrarySelectedInstance.value;
  const enabled = interiorLibraryPreviewMode.value === "front2d" && !!interiorLibrarySelectedControllerOverlay.value;
  const hasAllBindings = interiorLibraryControllerDefinitions.value.length > 0
    && interiorLibraryControllerDefinitions.value.every((definition) => String(interiorLibraryControllerBindingMap.value?.[definition.key]?.param_code || "").trim());
  let message = "";
  if (interiorLibraryControllerTestMode.value && interiorLibraryPreviewMode.value === "front2d") {
    if (!instance) message = "برای نمایش کنترلرها، ابتدا یک نمونه داخلی را انتخاب کنید.";
    else if (!group || normalizeInternalPartGroupControllerType(group?.controller_type) !== INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH) message = "برای این نمونه، کنترلر قطعات عرضی روی گروه داخلی تنظیم نشده است.";
    else if (!hasAllBindings) message = "اتصال هر ۴ پارامتر کنترلر برای این گروه کامل نیست.";
    else if (!interiorLibrarySelectedControllerOverlay.value?.rect) message = "مقادیر کنترلرهای این نمونه قابل محاسبه نیست.";
  }
  return { enabled, message };
});
const interiorLibraryControllerVisuals = computed(() => {
  if (!interiorLibraryControllerState.value.enabled || !interiorLibraryControllerRect.value) return [];
  const rect = interiorLibraryControllerRect.value;
  const scale = interiorLibraryControllerVisualScale.value;
  const horizontal = { w: 92 * scale, h: 32 * scale, inputW: 62.5 * scale, inputH: 22.5 * scale };
  const vertical = { w: 28 * scale, h: 76 * scale, inputW: 62.5 * scale, inputH: 22.5 * scale };
  return [
    {
      id: "left",
      kind: "horizontal",
      direction: "left",
      anchor: { x: rect.x, y: rect.y + (rect.h * 0.5) },
      x: rect.x - (horizontal.w * 0.5),
      y: rect.y + (rect.h * 0.5) - (horizontal.h * 0.5),
      ...horizontal,
    },
    {
      id: "top",
      kind: "vertical",
      direction: "up",
      anchor: { x: rect.x + (rect.w * 0.5), y: rect.y },
      x: rect.x + (rect.w * 0.5) - (vertical.w * 0.5),
      y: rect.y - (vertical.h * 0.5),
      ...vertical,
    },
    {
      id: "right",
      kind: "horizontal",
      direction: "right",
      anchor: { x: rect.x + rect.w, y: rect.y + (rect.h * 0.5) },
      x: rect.x + rect.w - (horizontal.w * 0.5),
      y: rect.y + (rect.h * 0.5) - (horizontal.h * 0.5),
      ...horizontal,
    },
    {
      id: "bottom_offset",
      kind: "vertical",
      direction: "up",
      anchor: { x: rect.x + (rect.w * 0.5), y: rect.y + rect.h },
      x: rect.x + (rect.w * 0.5) - (vertical.w * 0.5),
      y: rect.y + rect.h - (vertical.h * 0.5),
      ...vertical,
    },
  ];
});
const interiorLibraryFrontSnapLines = computed(() => {
  const outer = (interiorLibraryPreviewSvgLines.value?.outer || []).map((line) => ({
    x1: Number(line?.x1) || 0,
    y1: Number(line?.y1) || 0,
    x2: Number(line?.x2) || 0,
    y2: Number(line?.y2) || 0,
  }));
  const designInner = (interiorLibraryShowInnerLines.value ? (interiorLibraryPreviewSvgLines.value?.inner || []) : []).map((line) => ({
    x1: Number(line?.x1) || 0,
    y1: Number(line?.y1) || 0,
    x2: Number(line?.x2) || 0,
    y2: Number(line?.y2) || 0,
  }));
  const interiorInstanceLines = interiorLibraryPreviewInstances2d.value.flatMap((instance) => ([
    ...((instance?.outerLines || []).map((line) => ({
      x1: Number(line?.x1) || 0,
      y1: Number(line?.y1) || 0,
      x2: Number(line?.x2) || 0,
      y2: Number(line?.y2) || 0,
    }))),
    ...((instance?.innerLines || []).map((line) => ({
      x1: Number(line?.x1) || 0,
      y1: Number(line?.y1) || 0,
      x2: Number(line?.x2) || 0,
      y2: Number(line?.y2) || 0,
    }))),
  ]));
  return [...outer, ...designInner, ...interiorInstanceLines];
});
const interiorLibraryFrontSnapPoints = computed(() =>
  collectInteriorSnapPoints(interiorLibraryFrontSnapLines.value)
);

function buildInteriorControllerSnapLineKey(line) {
  const values = [
    Number(line?.x1) || 0,
    Number(line?.y1) || 0,
    Number(line?.x2) || 0,
    Number(line?.y2) || 0,
  ];
  const forward = values.map((value) => value.toFixed(3)).join("|");
  const reversed = [values[2], values[3], values[0], values[1]].map((value) => value.toFixed(3)).join("|");
  return forward < reversed ? forward : reversed;
}

const interiorLibraryControllerSnapLines = computed(() => {
  const selectedId = String(interiorLibrarySelectedInstanceId.value || "").trim();
  const selectedInstance = interiorLibraryPreviewInstances2d.value.find((instance) => String(instance?.id || "").trim() === selectedId);
  const selectedLineKeys = new Set([
    ...((selectedInstance?.outerLines || []).map((line) => buildInteriorControllerSnapLineKey(line))),
    ...((selectedInstance?.innerLines || []).map((line) => buildInteriorControllerSnapLineKey(line))),
  ]);
  const outer = (interiorLibraryPreviewSvgLines.value?.outer || []).map((line) => ({
    x1: Number(line?.x1) || 0,
    y1: Number(line?.y1) || 0,
    x2: Number(line?.x2) || 0,
    y2: Number(line?.y2) || 0,
  }));
  const designInner = (interiorLibraryShowInnerLines.value ? (interiorLibraryPreviewSvgLines.value?.inner || []) : [])
    .map((line) => ({
      x1: Number(line?.x1) || 0,
      y1: Number(line?.y1) || 0,
      x2: Number(line?.x2) || 0,
      y2: Number(line?.y2) || 0,
    }))
    .filter((line) => !selectedLineKeys.has(buildInteriorControllerSnapLineKey(line)));
  const interiorInstanceLines = interiorLibraryPreviewInstances2d.value
    .filter((instance) => String(instance?.id || "").trim() !== selectedId)
    .flatMap((instance) => ([
      ...((instance?.outerLines || []).map((line) => ({
        x1: Number(line?.x1) || 0,
        y1: Number(line?.y1) || 0,
        x2: Number(line?.x2) || 0,
        y2: Number(line?.y2) || 0,
      }))),
      ...((instance?.innerLines || []).map((line) => ({
        x1: Number(line?.x1) || 0,
        y1: Number(line?.y1) || 0,
        x2: Number(line?.x2) || 0,
        y2: Number(line?.y2) || 0,
      }))),
    ]));
  return [...outer, ...designInner, ...interiorInstanceLines];
});
const interiorLibraryControllerSnapPoints = computed(() =>
  collectInteriorSnapPoints(interiorLibraryControllerSnapLines.value)
);
const interiorLibraryFrontSnapTolerance = computed(() => {
  const viewBox = String(interiorLibraryFrontSvgViewBox.value || "").split(/\s+/).map(Number);
  const viewportWidth = Math.max(320, Number(interiorLibraryFrontViewport.value?.width) || FRONT_VIEW_WIDTH);
  const width = Number.isFinite(viewBox[2]) ? viewBox[2] : viewportWidth;
  return Math.max(6, (width / FRONT_VIEW_WIDTH) * 12);
});
const interiorLibraryFrontSvgViewBox = computed(() => {
  const zoom = Math.min(
    INTERIOR_LIBRARY_FRONT_ZOOM_MAX,
    Math.max(INTERIOR_LIBRARY_FRONT_ZOOM_MIN, Number(interiorLibraryFrontZoom.value) || 1)
  );
  const viewportWidth = Math.max(320, Number(interiorLibraryFrontViewport.value?.width) || FRONT_VIEW_WIDTH);
  const viewportHeight = Math.max(320, Number(interiorLibraryFrontViewport.value?.height) || FRONT_VIEW_HEIGHT);
  const width = viewportWidth / zoom;
  const height = viewportHeight / zoom;
  const panX = Number(interiorLibraryFrontPan.value?.x) || 0;
  const panY = Number(interiorLibraryFrontPan.value?.y) || 0;
  return `${(viewportWidth - width) * 0.5 + panX} ${(viewportHeight - height) * 0.5 + panY} ${width} ${height}`;
});
const interiorLibraryFrontSvgViewBoxRect = computed(() => {
  const parts = String(interiorLibraryFrontSvgViewBox.value || "").split(/\s+/).map(Number);
  return {
    x: Number.isFinite(parts[0]) ? parts[0] : 0,
    y: Number.isFinite(parts[1]) ? parts[1] : 0,
    width: Number.isFinite(parts[2]) ? parts[2] : FRONT_VIEW_WIDTH,
    height: Number.isFinite(parts[3]) ? parts[3] : FRONT_VIEW_HEIGHT,
  };
});
const interiorLibraryAnnotationColors = computed(() => ({
  dimension: String(walls3dSnapshot.value?.state?.dimColor || "#E8A559").trim() || "#E8A559",
  guide: String(walls3dSnapshot.value?.state?.hiddenWallColor || "#D8D4D4").trim() || "#D8D4D4",
  selected: "#2F7FD3",
}));
function buildRenderedInteriorAnnotation(item, type) {
  const start = { x: Number(item?.start?.x) || 0, y: Number(item?.start?.y) || 0 };
  const end = { x: Number(item?.end?.x) || 0, y: Number(item?.end?.y) || 0 };
  const axis = String(item?.axis || "").trim() === "vertical" ? "vertical" : "horizontal";
  const offset = axis === "horizontal" ? -24 : 24;
  const tick = 8;
  const screenStart = axis === "horizontal"
    ? { x: start.x, y: start.y + offset }
    : { x: start.x + offset, y: start.y };
  const screenEnd = axis === "horizontal"
    ? { x: end.x, y: end.y + offset }
    : { x: end.x + offset, y: end.y };
  const extensionA = axis === "horizontal"
    ? { x1: start.x, y1: start.y, x2: screenStart.x, y2: screenStart.y }
    : { x1: start.x, y1: start.y, x2: screenStart.x, y2: screenStart.y };
  const extensionB = axis === "horizontal"
    ? { x1: end.x, y1: end.y, x2: screenEnd.x, y2: screenEnd.y }
    : { x1: end.x, y1: end.y, x2: screenEnd.x, y2: screenEnd.y };
  const tickA = axis === "horizontal"
    ? { x1: screenStart.x, y1: screenStart.y - tick, x2: screenStart.x, y2: screenStart.y + tick }
    : { x1: screenStart.x - tick, y1: screenStart.y, x2: screenStart.x + tick, y2: screenStart.y };
  const tickB = axis === "horizontal"
    ? { x1: screenEnd.x, y1: screenEnd.y - tick, x2: screenEnd.x, y2: screenEnd.y + tick }
    : { x1: screenEnd.x - tick, y1: screenEnd.y, x2: screenEnd.x + tick, y2: screenEnd.y };
  const center = {
    x: (screenStart.x + screenEnd.x) * 0.5,
    y: (screenStart.y + screenEnd.y) * 0.5,
  };
  const selected = String(interiorLibrarySelectedAnnotation.value?.type || "") === type
    && String(interiorLibrarySelectedAnnotation.value?.id || "") === String(item?.id || "");
  return {
    ...item,
    axis,
    screenStart,
    screenEnd,
    extensionA,
    extensionB,
    tickA,
    tickB,
    text: type === "dimension" ? formatInteriorDimensionValue(item?.valueMm ?? item?.value, "mm") : "",
    textX: center.x,
    textY: axis === "horizontal" ? center.y - 10 : center.y - 14,
    selected,
  };
}
const interiorLibraryRenderedAnnotations = computed(() => {
  const dimensions = (interiorLibraryAnnotations.value?.dimensions || []).map((item) => buildRenderedInteriorAnnotation(item, "dimension"));
  const guides = (interiorLibraryAnnotations.value?.guides || []).map((item) => buildRenderedInteriorAnnotation(item, "guide"));
  let draftDimension = null;
  let draftGuide = null;
  if (interiorLibraryAnnotationDraft.value?.type && interiorLibraryAnnotationDraft.value?.startPoint && interiorLibraryAnnotationDraft.value?.currentPoint) {
    const draftRecord = buildInteriorLibraryAnnotationRecord(
      interiorLibraryAnnotationDraft.value.type,
      interiorLibraryAnnotationDraft.value.startPoint,
      interiorLibraryAnnotationDraft.value.currentPoint
    );
    if (isInteriorAnnotationMeaningful(draftRecord)) {
      const renderedDraft = buildRenderedInteriorAnnotation(draftRecord, draftRecord.type);
      if (draftRecord.type === "dimension") draftDimension = renderedDraft;
      else draftGuide = renderedDraft;
    }
  }
  return { dimensions, guides, draftDimension, draftGuide };
});
const interiorLibraryFrontCursorClass = computed(() => {
  if (interiorLibraryControllerPointerState.value.mode === "controller") {
    return interiorLibraryControllerPointerState.value.controllerId === "left" || interiorLibraryControllerPointerState.value.controllerId === "right"
      ? "is-drag-horizontal"
      : "is-drag-vertical";
  }
  if (interiorLibraryFrontPanning.value && interiorLibraryPreviewMode.value === "front2d") return "is-panning";
  if (interiorLibraryPreviewMode.value === "model3d" && interiorLibraryModelPanning.value) return "is-panning";
  if (interiorLibraryHoveredControllerId.value === "left" || interiorLibraryHoveredControllerId.value === "right") return "is-resize-horizontal";
  if (interiorLibraryHoveredControllerId.value === "top" || interiorLibraryHoveredControllerId.value === "bottom_offset") return "is-resize-vertical";
  if (interiorLibraryAnnotationTool.value === "dimension") return "is-drawing-dimension";
  if (interiorLibraryAnnotationTool.value === "guide") return "is-drawing-guide";
  if (interiorLibraryHoverMode.value === "clicker") return "is-clickable";
  return "is-idle";
});
const interiorLibraryFrontShowPanCursor = computed(() =>
  interiorLibraryPreviewMode.value === "front2d"
  && interiorLibraryFrontPanning.value
  && !!interiorLibraryCursorPoint.value
);
const interiorLibraryCursorVisualScale = computed(() => {
  const zoom = Math.min(
    INTERIOR_LIBRARY_FRONT_ZOOM_MAX,
    Math.max(INTERIOR_LIBRARY_FRONT_ZOOM_MIN, Number(interiorLibraryFrontZoom.value) || 1)
  );
  return 1 / zoom;
});
const interiorLibraryOverlayCursorIcon = computed(() => {
  if (interiorLibraryFrontPanning.value || !interiorLibraryCursorPoint.value) return "";
  if (interiorLibraryAnnotationTool.value === "dimension" || interiorLibraryAnnotationTool.value === "guide") return "";
  if (interiorLibraryHoverMode.value === "clicker") return "/icons/clicker_32.png";
  return "/icons/cursor_32.png";
});
const interiorLibraryOverlayCursorOffset = computed(() => {
  const scale = Number(interiorLibraryCursorVisualScale.value) || 1;
  const icon = String(interiorLibraryOverlayCursorIcon.value || "");
  if (icon.includes("clicker_32")) {
    return { x: 13.5 * scale, y: 1.5 * scale, size: 32 * scale };
  }
  return { x: 4.5 * scale, y: 3.5 * scale, size: 32 * scale };
});
const interiorLibraryModelCursorStyle = computed(() => {
  const point = interiorLibraryViewerCursorPoint.value;
  if (!point) return null;
  return {
    left: `${Math.round(Number(point.x) || 0)}px`,
    top: `${Math.round(Number(point.y) || 0)}px`,
    transform: "translate(-50%, -50%)",
  };
});
const interiorLibraryShouldShowSnapMarkers = computed(() =>
  (interiorLibraryAnnotationTool.value === "dimension" || interiorLibraryAnnotationTool.value === "guide")
);
watch(interiorLibraryAnnotationTool, (tool) => {
  if (tool === "dimension" || tool === "guide") {
    hideInteriorLibraryOverlapPicker();
    return;
  }
  interiorLibraryAnnotationDraft.value = null;
  interiorLibraryCurrentSnapPoint.value = null;
});
watch(interiorLibraryPreviewMode, () => {
  hideInteriorLibraryOverlapPicker();
  stopInteriorLibraryModelPanCursor();
  clearInteriorLibraryViewerCursorPoint();
  nextTick(() => {
    syncInteriorLibraryFrontViewport();
  });
});
watch(interiorLibraryViewerWrapEl, (el) => {
  if (interiorLibraryFrontViewportObserver) {
    interiorLibraryFrontViewportObserver.disconnect();
    interiorLibraryFrontViewportObserver = null;
  }
  if (typeof ResizeObserver !== "undefined" && el) {
    interiorLibraryFrontViewportObserver = new ResizeObserver(() => {
      syncInteriorLibraryFrontViewport();
    });
    interiorLibraryFrontViewportObserver.observe(el);
  }
  nextTick(() => {
    syncInteriorLibraryFrontViewport();
  });
}, { flush: "post" });
watch(activeInteriorLibraryInstances, (items) => {
  const ids = new Set((Array.isArray(items) ? items : []).map((item) => String(item?.id || "").trim()).filter(Boolean));
  if (interiorLibrarySelectedInstanceId.value && !ids.has(String(interiorLibrarySelectedInstanceId.value))) {
    interiorLibrarySelectedInstanceId.value = "";
  }
  if (interiorLibraryHoveredInstanceId.value && !ids.has(String(interiorLibraryHoveredInstanceId.value))) {
    interiorLibraryHoveredInstanceId.value = "";
  }
  if (interiorLibraryPickerPreviewInstanceId.value && !ids.has(String(interiorLibraryPickerPreviewInstanceId.value))) {
    interiorLibraryPickerPreviewInstanceId.value = "";
  }
  const pickerItems = Array.isArray(interiorLibraryOverlapPickerState.value?.items)
    ? interiorLibraryOverlapPickerState.value.items
    : [];
  if (pickerItems.length && pickerItems.some((item) => !ids.has(String(item?.id || "").trim()))) {
    hideInteriorLibraryOverlapPicker();
  }
}, { immediate: true });
watch(activeInteriorLibrarySelectedInstance, () => {
  clearInteriorLibraryControllerEditing();
  clearInteriorLibraryControllerDraftValues();
  interiorLibraryHoveredControllerId.value = "";
  if (interiorLibraryControllerPointerState.value.mode === "controller") {
    stopInteriorLibraryControllerDrag();
  }
});

function extractFormulaNamesLocal(expression) {
  return Array.from(new Set(String(expression || "").match(/[A-Za-z_][A-Za-z0-9_]*/g) || []));
}

function collectInternalGroupParamCodesLocal(group) {
  const formulasById = new Map(
    constructionPartFormulas.value.map((item) => [Number(item.part_formula_id) || 0, item])
  );
  const baseFormulaMap = new Map(
    constructionBaseFormulas.value.map((item) => [String(item.param_formula || "").trim(), String(item.formula || "")])
  );
  const paramCodeSet = new Set(
    constructionParams.value.map((item) => String(item.param_code || "").trim()).filter(Boolean)
  );
  const pending = [];
  for (const part of Array.isArray(group?.parts) ? group.parts : []) {
    const formula = formulasById.get(Number(part.part_formula_id) || 0);
    if (!formula) continue;
    for (const field of PART_FORMULA_FIELDS) {
      pending.push(...extractFormulaNamesLocal(formula[field.key] || formula[field] || ""));
    }
  }
  const resolved = new Set();
  const visited = new Set();
  while (pending.length) {
    const name = String(pending.pop() || "").trim();
    if (!name || visited.has(name)) continue;
    visited.add(name);
    if (paramCodeSet.has(name)) {
      resolved.add(name);
      continue;
    }
    const nested = baseFormulaMap.get(name);
    if (nested) pending.push(...extractFormulaNamesLocal(nested));
  }
  return Array.from(resolved);
}

function buildInternalGroupDefaultsTree(group) {
  if (!group) return [];
  const selectedParamGroupIds = new Set(
    (Array.isArray(group.param_groups) ? group.param_groups : [])
      .filter((row) => row?.enabled !== false && Number(row?.param_group_id) > 0)
      .map((row) => String(Number(row.param_group_id)))
  );
  return constructionSubCategoryParamTree.value
    .filter((row) => selectedParamGroupIds.has(String(row.id)))
    .map((row) => ({
      ...row,
      items: row.items.map((column) => {
        const baseLabel = column.label || column.key;
        const override = normalizeInternalPartGroupParamOverride(group.param_overrides?.[column.key], baseLabel);
        return {
          ...column,
          displayTitle: String(override.display_title || baseLabel).trim() || column.key,
          descriptionText: String(override.description_text || "").trim(),
          inputMode: override.input_mode === "binary" ? "binary" : "value",
          iconUrl: getSubCategoryDefaultIconUrl(override.icon_path),
          binaryOffLabel: String(override.binary_off_label || "").trim() || "0",
          binaryOnLabel: String(override.binary_on_label || "").trim() || "1",
          binaryOffIconUrl: getSubCategoryDefaultIconUrl(override.binary_off_icon_path),
          binaryOnIconUrl: getSubCategoryDefaultIconUrl(override.binary_on_icon_path),
          value: String(group.param_defaults?.[column.key] ?? "").trim(),
        };
      }),
    }))
    .filter((row) => row.items.length > 0);
}

function buildInteriorInstanceGroups(instance) {
  const groupsById = new Map();
  const sourceInternalGroup = constructionInternalPartGroupsById.value.get(String(instance?.internal_part_group_id || "").trim());
  for (const [key, meta] of Object.entries(instance?.param_meta || {})) {
    const code = String(key || "").trim();
    if (!code) continue;
    const groupId = String(meta?.group_id || "").trim() || "__ungrouped__";
    const sourceGroup = constructionSubCategoryParamTree.value.find((row) => String(row.id) === groupId);
    const baseLabel = constructionSubCategoryParamMetaByCode.value[code]?.label || code;
    const fallbackOverride = normalizeInternalPartGroupParamOverride(sourceInternalGroup?.param_overrides?.[code], baseLabel);
    const groupIconFileName = normalizeIconFileName(meta?.group_icon_path) || sourceGroup?.iconFileName || "";
    if (!groupsById.has(groupId)) {
      groupsById.set(groupId, {
        id: groupId,
        title: String(meta?.group_title || sourceGroup?.title || "بدون گروه").trim(),
        iconUrl: groupIconFileName ? getSubCategoryDefaultIconUrl(groupIconFileName) : "",
        order: Number(meta?.group_ui_order) || 0,
        items: [],
      });
    }
    const groupEntry = groupsById.get(groupId);
    if (groupEntry && !groupEntry.iconUrl && groupIconFileName) {
      groupEntry.iconUrl = getSubCategoryDefaultIconUrl(groupIconFileName);
    }
    groupEntry.items.push({
      key: code,
      displayTitle: String(meta?.label || fallbackOverride.display_title || baseLabel).trim() || code,
      descriptionText: String(meta?.description_text || fallbackOverride.description_text || "").trim(),
      inputMode: meta?.input_mode === "binary" ? "binary" : "value",
      iconUrl: getSubCategoryDefaultIconUrl(meta?.icon_path || fallbackOverride.icon_path),
      binaryOffLabel: String(meta?.binary_off_label || fallbackOverride.binary_off_label || "").trim() || "0",
      binaryOnLabel: String(meta?.binary_on_label || fallbackOverride.binary_on_label || "").trim() || "1",
      binaryOffIconUrl: getSubCategoryDefaultIconUrl(meta?.binary_off_icon_path || fallbackOverride.binary_off_icon_path),
      binaryOnIconUrl: getSubCategoryDefaultIconUrl(meta?.binary_on_icon_path || fallbackOverride.binary_on_icon_path),
      value: getInteriorInstanceEffectiveValue(instance, code),
      order: Number(meta?.param_ui_order) || 0,
    });
  }
  return Array.from(groupsById.values())
    .map((group) => ({
      ...group,
      items: group.items.sort((a, b) => a.order - b.order || a.displayTitle.localeCompare(b.displayTitle, "fa")),
    }))
    .sort((a, b) => a.order - b.order || a.title.localeCompare(b.title, "fa"));
}

function getInteriorInstanceEffectiveValue(instance, code) {
  const key = String(code || "").trim();
  if (!key) return "";
  const ownValues = instance?.param_values || {};
  if (Object.prototype.hasOwnProperty.call(ownValues, key)) {
    const ownValue = ownValues[key];
    if (ownValue != null && String(ownValue).trim() !== "") {
      return String(ownValue).trim();
    }
    if (String(ownValue) === "0") return "0";
  }
  const group = constructionInternalPartGroupsById.value.get(String(instance?.internal_part_group_id || "").trim());
  const groupDefaults = group?.param_defaults || {};
  if (Object.prototype.hasOwnProperty.call(groupDefaults, key)) {
    const groupValue = groupDefaults[key];
    if (groupValue != null && String(groupValue).trim() !== "") {
      return String(groupValue).trim();
    }
    if (String(groupValue) === "0") return "0";
  }
  const baseValue = activeInteriorLibraryBaseParamValues.value?.[key];
  if (baseValue != null && String(baseValue).trim() !== "") {
    return String(baseValue).trim();
  }
  if (String(baseValue) === "0") return "0";
  return "";
}

function normalizeInteriorControllerNumericText(value) {
  return String(value ?? "")
    .trim()
    .replace(/[۰-۹]/g, (digit) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)))
    .replace(/[٫،]/g, ".");
}

function parseInteriorControllerMm(value) {
  const numeric = Number.parseFloat(normalizeInteriorControllerNumericText(value));
  return Number.isFinite(numeric) ? numeric : null;
}

function formatInteriorControllerRawValue(valueMm, unit = currentEditorDisplayUnit.value) {
  const numeric = Math.max(0, Number(valueMm) || 0);
  const normalizedUnit = String(unit || "cm").trim().toLowerCase();
  if (normalizedUnit === "mm") return String(Math.round(numeric));
  if (normalizedUnit === "inch") return (numeric / 25.4).toFixed(2);
  return (numeric / 10).toFixed(1);
}

function formatInteriorControllerDisplayValue(valueMm) {
  return `${formatInteriorControllerRawValue(valueMm)} ${String(currentEditorDisplayUnit.value || "cm").trim().toLowerCase()}`;
}

function parseInteriorControllerInputToMm(value) {
  const numeric = Number.parseFloat(normalizeInteriorControllerNumericText(value));
  if (!Number.isFinite(numeric)) return null;
  const unit = String(currentEditorDisplayUnit.value || "cm").trim().toLowerCase();
  if (unit === "mm") return numeric;
  if (unit === "inch") return numeric * 25.4;
  return numeric * 10;
}

function buildInteriorLibraryControllerRectFromFrameValues(frame, values) {
  if (!frame) return null;
  const left = Number(values?.left);
  const right = Number(values?.right);
  const top = Number(values?.top);
  const bottomOffset = Number(values?.bottom_offset);
  if (![left, right, top, bottomOffset].every(Number.isFinite)) return null;
  const widthMm = Math.max(0, (frame.maxX - frame.minX) - left - right);
  const heightMm = Math.max(0, top);
  const x = frame.x + (left * frame.scale);
  const w = widthMm * frame.scale;
  const h = heightMm * frame.scale;
  const bottomMm = frame.minZ + bottomOffset;
  const y = frame.y + ((frame.maxZ - (bottomMm + heightMm)) * frame.scale);
  return { x, y, w, h, left, right, top, bottom_offset: bottomOffset };
}

function deriveInteriorLibraryControllerValuesFromGeometry(instance, frame) {
  if (!instance || !frame) return null;
  const data = buildFrontViewLinesFromBoxes(getViewerBoxesFromInteriorInstance(instance));
  const bounds = data?.bounds;
  if (!bounds) return null;
  return {
    left: Math.max(0, (Number(bounds.minX) || 0) - frame.minX),
    right: Math.max(0, frame.maxX - (Number(bounds.maxX) || 0)),
    top: Math.max(0, (Number(bounds.maxZ) || 0) - (Number(bounds.minZ) || 0)),
    bottom_offset: Math.max(0, (Number(bounds.minZ) || 0) - frame.minZ),
  };
}

function buildInteriorLibraryControllerOverlayForInstance(instance, frame) {
  const group = constructionInternalPartGroupsById.value.get(String(instance?.internal_part_group_id || "").trim());
  if (!group || normalizeInternalPartGroupControllerType(group.controller_type) !== INTERNAL_GROUP_CONTROLLER_TYPE_WIDTH) return null;
  const definitions = getInternalPartGroupControllerDefinitions(group.controller_type);
  if (!definitions.length) return null;
  const allowedCodes = new Set(getInternalPartGroupSelectedParamColumns(group).map((column) => column.key));
  const bindings = normalizeInternalPartGroupControllerBindings(group.controller_type, group.controller_bindings, allowedCodes);
  if (!definitions.every((definition) => String(bindings?.[definition.key]?.param_code || "").trim())) return null;
  const geometryValues = deriveInteriorLibraryControllerValuesFromGeometry(instance, frame) || {};
  const values = Object.fromEntries(
    definitions.map((definition) => {
      const paramCode = String(bindings?.[definition.key]?.param_code || "").trim();
      const rawValue = paramCode ? getInteriorInstanceEffectiveValue(instance, paramCode) : "";
      const parsedValue = parseInteriorControllerMm(rawValue);
      return [definition.key, Number.isFinite(parsedValue) ? parsedValue : geometryValues[definition.key]];
    })
  );
  const rect = buildInteriorLibraryControllerRectFromFrameValues(frame, values);
  if (!rect) return null;
  return {
    instanceId: String(instance?.id || "").trim(),
    groupId: String(group?.id || "").trim(),
    groupCode: String(group?.code || "").trim(),
    groupTitle: String(group?.group_title || group?.title || "").trim(),
    bindings,
    values,
    rect,
  };
}

function pointInInteriorControllerRect(point, rect, pad = 0) {
  const x = Number(point?.x) || 0;
  const y = Number(point?.y) || 0;
  return (
    x >= (Number(rect?.x) || 0) - pad &&
    x <= (Number(rect?.x) || 0) + (Number(rect?.w) || 0) + pad &&
    y >= (Number(rect?.y) || 0) - pad &&
    y <= (Number(rect?.y) || 0) + (Number(rect?.h) || 0) + pad
  );
}

function pointInInteriorControllerHotspot(point, controller) {
  return !!getInteriorControllerMatchingHotspot(point, controller);
}

function getInteriorControllerMatchingHotspot(point, controller) {
  const x = Number(point?.x) || 0;
  const y = Number(point?.y) || 0;
  return getInteriorControllerHotspots(controller).find((hotspot) => {
    const hx = Number(hotspot?.x);
    const hy = Number(hotspot?.y);
    const radius = Number(hotspot?.radius);
    if (!Number.isFinite(hx) || !Number.isFinite(hy) || !Number.isFinite(radius)) return false;
    return Math.hypot(x - hx, y - hy) <= radius;
  }) || null;
}

function getInteriorControllerHotspots(controller) {
  const scale = Number(interiorLibraryControllerVisualScale.value) || 1;
  const radius = 12 * scale;
  if (controller?.kind === "horizontal") {
    const centerY = (Number(controller?.y) || 0) + ((Number(controller?.h) || 0) * 0.5);
    return [
      { x: Number(controller?.x) || 0, y: centerY, radius },
      { x: (Number(controller?.x) || 0) + (Number(controller?.w) || 0), y: centerY, radius },
    ];
  }
  const centerX = (Number(controller?.x) || 0) + ((Number(controller?.w) || 0) * 0.5);
  return [
    { x: centerX, y: Number(controller?.y) || 0, radius },
    { x: centerX, y: (Number(controller?.y) || 0) + (Number(controller?.h) || 0), radius },
  ];
}

function snapInteriorControllerAxis(controllerId, axisValue) {
  const tolerance = Number(interiorLibraryFrontSnapTolerance.value) || 0;
  const isHorizontalAxis = controllerId === "left" || controllerId === "right";
  const lineCandidates = interiorLibraryControllerSnapLines.value
    .map((line) => {
      const x1 = Number(line?.x1) || 0;
      const y1 = Number(line?.y1) || 0;
      const x2 = Number(line?.x2) || 0;
      const y2 = Number(line?.y2) || 0;
      if (isHorizontalAxis) {
        if (Math.abs(x1 - x2) <= tolerance) return (x1 + x2) * 0.5;
        return null;
      }
      if (Math.abs(y1 - y2) <= tolerance) return (y1 + y2) * 0.5;
      return null;
    })
    .filter((value) => Number.isFinite(value));
  const pointCandidates = interiorLibraryControllerSnapPoints.value
    .map((point) => isHorizontalAxis ? Number(point?.x) : Number(point?.y))
    .filter((value) => Number.isFinite(value));
  let bestValue = Number(axisValue) || 0;
  let bestDistance = tolerance + 0.0001;
  for (const candidate of [...lineCandidates, ...pointCandidates]) {
    const distance = Math.abs(candidate - axisValue);
    if (distance <= tolerance && distance < bestDistance) {
      bestDistance = distance;
      bestValue = candidate;
    }
  }
  return bestValue;
}

function buildInteriorControllerHorizontalArrowPath(direction, x, y, width, height) {
  const head = Math.min(width * 0.28, height * 0.92);
  const shaftInset = Math.max(head, height * 0.42);
  const centerY = y + height * 0.5;
  const shaftHalf = height * 0.22;
  const topY = centerY - shaftHalf;
  const bottomY = centerY + shaftHalf;
  const headTop = centerY - height * 0.5;
  const headBottom = centerY + height * 0.5;
  const leftTip = x;
  const rightTip = x + width;
  const leftJoin = x + shaftInset;
  const rightJoin = x + width - shaftInset;
  return `M ${leftJoin} ${headTop} L ${leftTip} ${centerY} L ${leftJoin} ${headBottom} L ${leftJoin} ${bottomY} L ${rightJoin} ${bottomY} L ${rightJoin} ${headBottom} L ${rightTip} ${centerY} L ${rightJoin} ${headTop} L ${rightJoin} ${topY} L ${leftJoin} ${topY} Z`;
}

function buildInteriorControllerVerticalArrowPath(direction, x, y, width, height) {
  const head = Math.min(height * 0.28, width * 0.92);
  const shaftInset = Math.max(head, width * 0.42);
  const centerX = x + width * 0.5;
  const shaftHalf = width * 0.22;
  const leftX = centerX - shaftHalf;
  const rightX = centerX + shaftHalf;
  const headLeft = centerX - width * 0.5;
  const headRight = centerX + width * 0.5;
  const topTip = y;
  const bottomTip = y + height;
  const topJoin = y + shaftInset;
  const bottomJoin = y + height - shaftInset;
  return `M ${headLeft} ${topJoin} L ${centerX} ${topTip} L ${headRight} ${topJoin} L ${rightX} ${topJoin} L ${rightX} ${bottomJoin} L ${headRight} ${bottomJoin} L ${centerX} ${bottomTip} L ${headLeft} ${bottomJoin} L ${leftX} ${bottomJoin} L ${leftX} ${topJoin} Z`;
}

const interiorLibraryGroupCards = computed(() => {
  const groups = constructionInternalPartGroups.value;
  return groups.map((group) => {
    const groupTree = buildInternalGroupDefaultsTree(group);
    return {
      ...group,
      lineColor: normalizeHexColor(group.line_color, DEFAULT_INTERIOR_LINE_COLOR),
      groupTree,
      relatedGroups: groupTree.map((row) => ({ id: String(row.id), title: row.title, count: row.items.length })),
      paramCount: groupTree.reduce((sum, row) => sum + row.items.length, 0),
    };
  });
});
const interiorLibraryInstanceCards = computed(() =>
  activeInteriorLibraryInstances.value
    .slice()
    .sort((a, b) => (Number(a?.ui_order) || 0) - (Number(b?.ui_order) || 0) || String(a?.instance_code || "").localeCompare(String(b?.instance_code || ""), "fa"))
    .map((instance) => {
    const group = constructionInternalPartGroupsById.value.get(String(instance.internal_part_group_id));
    const groups = buildInteriorInstanceGroups(instance);
    return {
      ...instance,
      groupTitle: String(group?.group_title || group?.title || instance.instance_code || "گروه داخلی").trim(),
      groupCode: String(group?.code || "").trim(),
      lineColor: resolveInteriorInstanceLineColor(instance),
      groups,
    };
  })
);
const activeInteriorLibraryOutlineColor = computed(() => {
  if (subCategoryDesignEditorOpen.value) {
    return normalizeHexColor(subCategoryDesignEditorPreview.value?.design_outline_color);
  }
  return normalizeHexColor(
    activeInteriorLibraryOrderDesign.value?.design_outline_color
    || activeInteriorLibrarySourceDesign.value?.design_outline_color
    || activeInteriorLibrarySourceDesign.value?.preview?.design_outline_color
  );
});
const interiorLibraryPreviewPanelTitle = computed(() =>
  interiorLibraryPreviewMode.value === "model3d" ? "نمای سه بعدی" : "نمای روبه‌رو طرح"
);
function getSelectedOrderDesignSourceLocal() {
  const ids = [];
  const push = (value) => {
    const key = String(value || "").trim();
    if (key && !ids.includes(key)) ids.push(key);
  };
  if (activeStageOrderDesignSelected.value && activeCabinetDesignId.value) push(activeCabinetDesignId.value);
  for (const id of selectedStageOrderDesignIds.value) push(id);
  if (!ids.length) {
    return orderDesignCatalog.value.find((item) => String(item.id) === String(activeCabinetDesignId.value || "")) || null;
  }
  return orderDesignCatalog.value.find((item) => String(item.id) === String(ids[0])) || null;
}

function getConstructionPartKindInternalLabel(partKindId) {
  const partKind = constructionPartKindsById.value.get(Number(partKindId) || 0);
  return normalizeBooleanFlag(partKind?.is_internal, false) ? "داخلی" : "سازه";
}
const activeSubCategoryUserPreviewRow = computed(() =>
  editableSubCategories.value.find((item) => String(item.id) === String(subCategoryUserPreviewRowId.value)) || null
);
const activeSubCategoryUserPreviewGroups = computed(() => {
  const row = activeSubCategoryUserPreviewRow.value;
  if (!row) return [];
  return constructionSubCategoryParamTree.value
    .map((group) => ({
      ...group,
      items: group.items.map((column) => {
        const baseLabel = column.label || column.key;
        const override = normalizeInternalPartGroupParamOverride(row.param_overrides?.[column.key], baseLabel);
        const displayTitle = String(override.display_title || baseLabel).trim() || column.key;
        const descriptionText = String(override.description_text || "").trim();
        const inputMode = override.input_mode === "binary" ? "binary" : "value";
        return {
          ...column,
          displayTitle,
          descriptionText,
          iconUrl: getSubCategoryDefaultIconUrl(override.icon_path),
          inputMode,
          binaryOffLabel: String(override.binary_off_label || "").trim() || "0",
          binaryOnLabel: String(override.binary_on_label || "").trim() || "1",
          binaryOffIconUrl: getSubCategoryDefaultIconUrl(override.binary_off_icon_path),
          binaryOnIconUrl: getSubCategoryDefaultIconUrl(override.binary_on_icon_path),
        };
      }),
    }))
    .filter((group) => group.items.length > 0);
});
const activeSubCategoryUserPreviewGroup = computed(() =>
  activeSubCategoryUserPreviewGroups.value.find((group) => String(group.id) === String(subCategoryUserPreviewActiveGroupId.value))
  || activeSubCategoryUserPreviewGroups.value[0]
  || null
);
const formulaBuilderAvailableParams = computed(() =>
  editableParams.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0))
    .map((item) => ({
      value: String(item.param_code || "").trim(),
      label: `${String(item.param_code || "").trim()} - ${String(item.param_title_fa || item.title || "").trim()}`,
      kind: "param",
    }))
    .filter((item) => item.value)
);
const formulaBuilderAvailableBaseFormulas = computed(() =>
  editableBaseFormulas.value
    .filter((item) => item.admin_id === null || item.admin_id === currentAdminId.value)
    .slice()
    .sort((a, b) => (Number(a.sort_order) || 0) - (Number(b.sort_order) || 0))
    .map((item) => ({
      value: String(item.param_formula || "").trim(),
      label: `${String(item.param_formula || "").trim()} - ${String(item.title || "فرمول پایه").trim()}`,
      kind: "base_formula",
    }))
    .filter((item) => item.value)
);
const formulaBuilderAvailableIdentifiers = computed(() => {
  if (baseFormulaBuilderEntity.value === "part_formulas") {
    return [...formulaBuilderAvailableBaseFormulas.value, ...formulaBuilderAvailableParams.value];
  }
  return formulaBuilderAvailableParams.value;
});
const formulaBuilderKnownCodes = computed(() => new Set(formulaBuilderAvailableIdentifiers.value.map((item) => item.value)));
const baseFormulaBuilderValidationErrors = computed(() => {
  const draft = baseFormulaBuilderDraft.value;
  if (!draft) return [];
  const currentField = String(baseFormulaBuilderTargetField.value || "formula");
  if (baseFormulaBuilderEntity.value === "part_formulas") {
    const errors = getPartFormulaValidationErrors(draft, baseFormulaBuilderTargetRowId.value);
    const expression = String(draft[currentField] || "").trim();
    if (!expression) errors.unshift(`عبارت ${PART_FORMULA_FIELDS.find((item) => item.key === currentField)?.label || "فرمول"} خالی است.`);
    return [...new Set(errors)];
  }
  const errors = validateFormulaExpression(String(draft.formula || "").trim(), formulaBuilderKnownCodes.value, { identifierLabel: "پارامتر" });
  const foId = Number(draft.fo_id);
  const paramFormula = String(draft.param_formula || "").trim().toLowerCase();
  if (!Number.isInteger(foId) || foId < 1) errors.unshift("شناسه فرمول پایه معتبر نیست.");
  if (!paramFormula) errors.unshift("کد فرمول پایه خالی است.");
  for (const item of editableBaseFormulas.value) {
    if (String(item.id) === String(baseFormulaBuilderTargetRowId.value)) continue;
    if (Number(item.fo_id) === foId) errors.unshift("شناسه فرمول پایه تکراری است.");
    if (String(item.param_formula || "").trim().toLowerCase() === paramFormula) errors.unshift("کد فرمول پایه تکراری است.");
  }
  return [...new Set(errors)];
});
const isBaseFormulaBuilderApplyDisabled = computed(() => !baseFormulaBuilderDraft.value || baseFormulaBuilderValidationErrors.value.length > 0);
const constructionParamGroupDuplicateState = computed(() => buildDuplicateState(editableParamGroups.value, ["param_group_id", "param_group_code"]));
const constructionParamDuplicateState = computed(() => buildDuplicateState(editableParams.value, ["param_id", "param_code"]));
const constructionBaseFormulaDuplicateState = computed(() => buildDuplicateState(editableBaseFormulas.value, ["fo_id", "param_formula"]));
const constructionPartFormulaDuplicateState = computed(() => buildDuplicateState(editablePartFormulas.value, ["part_formula_id", "part_code"]));
const baseFormulaCodeWidthCh = computed(() => {
  const liveCodes = constructionBaseFormulas.value.map((item) => String(item?.param_formula || "").trim().length);
  const previewCodes = constructionImportPreviewKind.value === "base_formulas"
    ? constructionImportPreviewRows.value.map((item) => String(item?.param_formula || "").trim().length)
    : [];
  return Math.max(3, ...liveCodes, ...previewCodes);
});
const partFormulaKnownCodes = computed(() => new Set([
  ...formulaBuilderAvailableParams.value.map((item) => item.value),
  ...formulaBuilderAvailableBaseFormulas.value.map((item) => item.value),
]));
const formulaBuilderFieldOptions = computed(() => (
  baseFormulaBuilderEntity.value === "part_formulas"
    ? PART_FORMULA_FIELDS
    : [{ key: "formula", label: "فرمول" }]
));
const formulaBuilderCurrentFieldLabel = computed(() => (
  formulaBuilderFieldOptions.value.find((item) => item.key === baseFormulaBuilderTargetField.value)?.label || "فرمول"
));
const formulaBuilderDialogTitle = computed(() => (
  baseFormulaBuilderEntity.value === "part_formulas" ? "سازنده فرمول قطعه" : "سازنده فرمول پایه"
));
const formulaBuilderHintText = computed(() => (
  baseFormulaBuilderEntity.value === "part_formulas"
    ? "در فرمول قطعات می‌توانید هم از پارامترها و هم از کد فرمول‌های پایه استفاده کنید. اعداد ثابت مجازند و پرانتزها باید کامل باشند."
    : "فقط از پارامترهای معتبر همین ساختار استفاده کنید. اعداد ثابت مجازند و پرانتزها باید کامل باشند."
));

function openConstructionWizard() {
  constructionWizardOpen.value = true;
  constructionStep.value = "templates";
  activeMenu.value = "construction";
  openMenuPanel.value = null;
  openMode.value = "menu";
  loadConstructionTemplates();
  loadConstructionCategories();
  loadConstructionPartKinds();
  loadConstructionParamGroups();
  loadConstructionParams();
  loadConstructionSubCategories();
  loadConstructionSubCategoryDesigns();
  loadConstructionInternalPartGroups();
  loadConstructionBaseFormulas();
  loadConstructionPartFormulas();
  constructionDeletedTemplateIds.value = [];
  constructionDeletedCategoryIds.value = [];
  constructionDeletedPartKindIds.value = [];
  constructionDeletedParamGroupIds.value = [];
  constructionDeletedParamIds.value = [];
  constructionDeletedSubCategoryIds.value = [];
  constructionDeletedBaseFormulaIds.value = [];
  constructionDeletedPartFormulaIds.value = [];
}

function addConstructionPartKind() {
  createConstructionPartKind();
}

function removeConstructionPartKind(id) {
  deleteConstructionPartKind(id);
}

async function closeConstructionWizard() {
  if (constructionHasPendingChanges.value) {
    const ok = await showConfirm("تغییرات ذخیره نشده‌اند. پنجره بدون ذخیره بسته شود؟", {
      title: "بستن شیوه ساخت",
      confirmText: "بستن بدون ذخیره",
      cancelText: "بازگشت",
    });
    if (!ok) return;
    await cleanupStagedParamGroupUploads();
    await loadConstructionTemplates();
    await loadConstructionCategories();
    await loadConstructionSubCategories();
    await loadConstructionPartKinds();
    await loadConstructionParamGroups();
    await loadConstructionParams();
    await loadConstructionSubCategories();
    await loadConstructionSubCategoryDesigns();
    await loadConstructionInternalPartGroups();
    await loadConstructionBaseFormulas();
    await loadConstructionPartFormulas();
  }
  constructionWizardOpen.value = false;
  if (activeMenu.value === "construction") activeMenu.value = null;
}

function normalizeTemplatePayload(item) {
  return {
    admin_id: item.admin_id,
    temp_id: Number(item.temp_id),
    temp_title: String(item.temp_title || "").trim(),
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.temp_id),
    is_system: !!item.is_system,
  };
}

function normalizeCategoryPayload(item) {
  return {
    admin_id: item.admin_id,
    temp_id: Number(item.temp_id),
    cat_id: Number(item.cat_id),
    cat_title: String(item.cat_title || "").trim(),
    design_outline_color: normalizeHexColor(item.design_outline_color),
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.cat_id),
    is_system: !!item.is_system,
  };
}

function normalizeHexColor(value, fallback = DEFAULT_SUB_CATEGORY_DESIGN_OUTLINE_COLOR) {
  const raw = String(value || "").trim();
  if (!raw) return fallback;
  const normalized = raw.startsWith("#") ? raw : `#${raw}`;
  return /^#[0-9A-Fa-f]{6}$/.test(normalized) ? normalized.toUpperCase() : fallback;
}

function normalizeSubCategoryPayload(item) {
  return {
    admin_id: item.admin_id,
    temp_id: Number(item.temp_id),
    cat_id: Number(item.cat_id),
    sub_cat_id: Number(item.sub_cat_id),
    sub_cat_title: String(item.sub_cat_title || "").trim(),
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.sub_cat_id),
    is_system: !!item.is_system,
    param_defaults: Object.fromEntries(
      constructionSubCategoryParamColumns.value.map((column) => [
        column.key,
        String(item.param_defaults?.[column.key] ?? "").trim(),
      ])
    ),
    param_overrides: Object.fromEntries(
      constructionSubCategoryParamColumns.value.map((column) => {
        const baseLabel = constructionSubCategoryParamMetaByCode.value[column.key]?.label || column.key;
        const override = item.param_overrides?.[column.key] || {};
        return [column.key, {
          display_title: String(override.display_title || "").trim() || baseLabel,
          description_text: String(override.description_text || "").trim(),
          icon_path: normalizeIconFileName(override.icon_path) || null,
          input_mode: override.input_mode === "binary" ? "binary" : "value",
          binary_off_label: String(override.binary_off_label || "").trim() || "0",
          binary_on_label: String(override.binary_on_label || "").trim() || "1",
          binary_off_icon_path: normalizeIconFileName(override.binary_off_icon_path) || null,
          binary_on_icon_path: normalizeIconFileName(override.binary_on_icon_path) || null,
        }];
      })
    ),
  };
}

function normalizeSubCategoryDesignPayload(item) {
  return {
    admin_id: item.admin_id,
    sub_category_id: item.sub_category_id,
    design_id: Number(item.design_id),
    design_title: String(item.design_title || "").trim(),
    code: String(item.code || "").trim(),
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.design_id),
    is_system: !!item.is_system,
    parts: (Array.isArray(item.parts) ? item.parts : [])
      .filter((part) => Number(part?.part_formula_id) > 0)
      .map((part, index) => ({
        part_formula_id: Number(part.part_formula_id),
        enabled: part.enabled !== false,
        ui_order: Number.isFinite(Number(part.ui_order)) ? Number(part.ui_order) : index,
      })),
  };
}

function normalizePartKindPayload(item) {
  return {
    admin_id: item.admin_id,
    part_kind_id: Number(item.part_kind_id),
    part_kind_code: String(item.part_kind_code || "").trim(),
    org_part_kind_title: String(item.org_part_kind_title || "").trim(),
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.part_kind_id),
    is_internal: normalizeBooleanFlag(item.is_internal, false),
    is_system: !!item.is_system,
  };
}

function normalizeInternalPartGroupPayload(item) {
  const selectedParamGroupIds = new Set(
    (Array.isArray(item.param_groups) ? item.param_groups : [])
      .filter((group) => group?.enabled !== false && Number(group?.param_group_id) > 0)
      .map((group) => Number(group.param_group_id))
  );
  const allowedParamCodes = new Set(
    constructionParams.value
      .filter((param) => selectedParamGroupIds.has(Number(param?.param_group_id)))
      .map((param) => String(param.param_code || "").trim())
      .filter(Boolean)
  );
  const controllerType = normalizeInternalPartGroupControllerType(item.controller_type);
  const controllerBindings = normalizeInternalPartGroupControllerBindings(
    controllerType,
    item.controller_bindings,
    allowedParamCodes,
  );
  return {
    admin_id: item.admin_id,
    group_id: Number(item.group_id),
    group_title: String(item.group_title || "").trim(),
    code: String(item.code || "").trim(),
    line_color: normalizeHexColor(item.line_color, DEFAULT_INTERIOR_LINE_COLOR),
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.group_id),
    is_system: !!item.is_system,
    parts: (Array.isArray(item.parts) ? item.parts : [])
      .filter((part) => Number(part?.part_formula_id) > 0)
      .map((part, index) => ({
        part_formula_id: Number(part.part_formula_id),
        enabled: part.enabled !== false,
        ui_order: Number.isFinite(Number(part.ui_order)) ? Number(part.ui_order) : index,
      })),
    param_groups: (Array.isArray(item.param_groups) ? item.param_groups : [])
      .filter((group) => Number(group?.param_group_id) > 0)
      .map((group, index) => ({
        param_group_id: Number(group.param_group_id),
        enabled: group.enabled !== false,
        ui_order: Number.isFinite(Number(group.ui_order)) ? Number(group.ui_order) : index,
      })),
    param_defaults: Object.fromEntries(
      Object.entries(item.param_defaults || {})
        .filter(([key]) => allowedParamCodes.has(String(key || "").trim()))
        .map(([key, value]) => [String(key || "").trim(), value == null ? null : String(value)])
    ),
    param_overrides: Object.fromEntries(
      Object.entries(item.param_overrides || {})
        .filter(([key]) => allowedParamCodes.has(String(key || "").trim()))
        .map(([key, override]) => {
          const baseLabel = constructionSubCategoryParamMetaByCode.value[String(key || "").trim()]?.label || String(key || "").trim();
          return [String(key || "").trim(), {
            display_title: String(override?.display_title || "").trim() || baseLabel,
            description_text: String(override?.description_text || "").trim(),
            icon_path: normalizeIconFileName(override?.icon_path) || "",
            input_mode: override?.input_mode === "binary" ? "binary" : "value",
            binary_off_label: String(override?.binary_off_label || "").trim() || "0",
            binary_on_label: String(override?.binary_on_label || "").trim() || "1",
            binary_off_icon_path: normalizeIconFileName(override?.binary_off_icon_path) || "",
            binary_on_icon_path: normalizeIconFileName(override?.binary_on_icon_path) || "",
          }];
        })
    ),
    controller_type: controllerType || null,
    controller_bindings: controllerBindings,
  };
}

function normalizeInteriorInstanceRecord(item) {
  if (!item || !item.id) return null;
  return {
    ...item,
    id: String(item.id),
    internal_part_group_id: String(item.internal_part_group_id || ""),
    instance_code: String(item.instance_code || "").trim(),
    line_color: item.line_color ? normalizeHexColor(item.line_color, DEFAULT_INTERIOR_LINE_COLOR) : "",
    ui_order: Number(item.ui_order) || 0,
    placement_z: Number(item.placement_z) || 0,
    interior_box_snapshot: { ...(item.interior_box_snapshot || {}) },
    param_values: Object.fromEntries(
      Object.entries(item.param_values || {}).map(([key, value]) => [key, value == null ? "" : String(value)])
    ),
    param_meta: Object.fromEntries(
      Object.entries(item.param_meta || {}).map(([key, value]) => [key, { ...(value || {}) }])
    ),
    part_snapshots: Array.isArray(item.part_snapshots) ? item.part_snapshots.map((row) => ({ ...(row || {}) })) : [],
    viewer_boxes: Array.isArray(item.viewer_boxes) ? item.viewer_boxes.map((row) => ({ ...(row || {}) })) : [],
    status: String(item.status || "draft").trim() || "draft",
  };
}

function toPersianDigits(value) {
  return String(value ?? "").replace(/\d/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
}

function normalizeIconFileName(value) {
  const text = String(value ?? "").trim();
  if (!text) return "";
  return text.split("?")[0].split("/").pop() || "";
}

const DEFAULT_SUB_CATEGORY_PARAM_ICON = `data:image/svg+xml;utf8,${encodeURIComponent(
  `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
    <rect width="64" height="64" rx="18" fill="#fff4cc"/>
    <path d="M32 12c-9.39 0-17 7.61-17 17 0 6.34 3.49 11.87 8.66 14.79 1.56.88 2.34 2.15 2.34 3.81V49h12v-1.4c0-1.66.78-2.93 2.34-3.81C45.51 40.87 49 35.34 49 29c0-9.39-7.61-17-17-17Z" fill="#ffcf33"/>
    <path d="M26 53h12a4 4 0 0 1-4 4h-4a4 4 0 0 1-4-4Z" fill="#4a4a4a"/>
    <rect x="25" y="49" width="14" height="4" rx="2" fill="#6b6b6b"/>
    <path d="M32 8v5M14 29H9m46 0h-5M18.22 15.22l3.54 3.54m20.48-3.54-3.54 3.54" stroke="#e1a800" stroke-width="3" stroke-linecap="round"/>
  </svg>`
)}`;

function hasParamGroupIcon(item) {
  return !!normalizeIconFileName(item?.param_group_icon_path);
}

function isStagedParamGroupIcon(value) {
  return normalizeIconFileName(value).startsWith("staged-");
}

function getParamGroupIconTooltip(item) {
  const fileName = normalizeIconFileName(item?.param_group_icon_path);
  if (!fileName) return "آیکون خالی است. برای آپلود کلیک کنید.";
  return `آیکون بارگذاری شده: ${fileName}`;
}

function getParamGroupOptionIconUrl(fileName) {
  const normalized = normalizeIconFileName(fileName);
  if (!normalized) return "";
  return `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/icons/${encodeURIComponent(normalized)}`;
}

function isUploadingParamGroupIcon(item) {
  return String(constructionUploadingIconRowId.value || "") === String(item?.id || "");
}

function getSubCategoryDefaultIconUrl(fileName) {
  const normalized = normalizeIconFileName(fileName);
  if (!normalized) return DEFAULT_SUB_CATEGORY_PARAM_ICON;
  return `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/icons/${encodeURIComponent(normalized)}`;
}

function getSubCategoryDefaultIconKey(paramCode, field = "icon_path") {
  const key = String(paramCode || "").trim();
  const normalizedField = String(field || "icon_path").trim() || "icon_path";
  if (!key) return "";
  return `${key}::${normalizedField}`;
}

function getSubCategoryDefaultPreviewUrl(paramCode, fileName, field = "icon_path") {
  const key = getSubCategoryDefaultIconKey(paramCode, field);
  const previewUrl = String(subCategoryDefaultIconPreviewUrls.value?.[key] || "").trim();
  if (previewUrl) return previewUrl;
  return getSubCategoryDefaultIconUrl(fileName);
}

function handleSubCategoryDefaultIconError(event) {
  const imgEl = event?.target;
  if (!imgEl || imgEl.dataset?.fallbackApplied === "1") return;
  imgEl.dataset.fallbackApplied = "1";
  imgEl.src = DEFAULT_SUB_CATEGORY_PARAM_ICON;
}

function revokeSubCategoryDefaultIconPreview(paramCode, field = "icon_path") {
  const key = getSubCategoryDefaultIconKey(paramCode, field);
  if (!key) return;
  const previewUrl = String(subCategoryDefaultIconPreviewUrls.value?.[key] || "").trim();
  if (previewUrl.startsWith("blob:")) URL.revokeObjectURL(previewUrl);
  delete subCategoryDefaultIconPreviewUrls.value[key];
}

function clearSubCategoryDefaultIconPreviews() {
  for (const key of Object.keys(subCategoryDefaultIconPreviewUrls.value || {})) {
    revokeSubCategoryDefaultIconPreview(key);
  }
  subCategoryDefaultIconPreviewUrls.value = {};
}

function isUploadingSubCategoryDefaultIcon(paramCode, field = "icon_path") {
  return String(subCategoryDefaultIconUploadingKey.value || "") === getSubCategoryDefaultIconKey(paramCode, field);
}

function triggerSubCategoryDefaultIconUpload(paramCode, field = "icon_path") {
  if (!paramCode || isUploadingSubCategoryDefaultIcon(paramCode, field)) return;
  subCategoryDefaultIconTargetCode.value = String(paramCode);
  subCategoryDefaultIconTargetField.value = String(field || "icon_path").trim() || "icon_path";
  subCategoryDefaultIconInputEl.value?.click?.();
}

function getSubCategoryDefaultIconTooltip(paramCode, field = "icon_path") {
  if (isUploadingSubCategoryDefaultIcon(paramCode, field)) return "در حال آپلود آیکون...";
  const fileName = normalizeIconFileName(subCategoryDefaultsEditorOverridesDraft.value?.[paramCode]?.[field]);
  if (!fileName) return "آیکون خالی است. برای آپلود کلیک کنید.";
  return `آیکون بارگذاری شده: ${fileName}`;
}

async function onSubCategoryDefaultIconFileChange(event) {
  const file = event?.target?.files?.[0];
  const paramCode = String(subCategoryDefaultIconTargetCode.value || "").trim();
  const field = String(subCategoryDefaultIconTargetField.value || "icon_path").trim() || "icon_path";
  const uploadKey = getSubCategoryDefaultIconKey(paramCode, field);
  if (!file || !paramCode || !uploadKey) return;
  const previousIconFileName = normalizeIconFileName(subCategoryDefaultsEditorOverridesDraft.value?.[paramCode]?.[field]);
  subCategoryDefaultIconUploadingKey.value = uploadKey;
  revokeSubCategoryDefaultIconPreview(paramCode, field);
  subCategoryDefaultIconPreviewUrls.value[uploadKey] = URL.createObjectURL(file);
  try {
    const formData = new FormData();
    formData.append("file", file);
    const slugHint = encodeURIComponent(`subcat-${field.replaceAll("_path", "").replaceAll("_", "-")}-${paramCode}`);
    const res = await fetch(`/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/param-group-icons?slug_hint=${slugHint}`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error("upload-failed");
    const payload = await res.json();
    if (!subCategoryDefaultsEditorOverridesDraft.value[paramCode]) {
      subCategoryDefaultsEditorOverridesDraft.value[paramCode] = {
        display_title: constructionSubCategoryParamMetaByCode.value[paramCode]?.label || paramCode,
        description_text: "",
        icon_path: "",
        input_mode: "value",
        binary_off_label: "0",
        binary_on_label: "1",
        binary_off_icon_path: "",
        binary_on_icon_path: "",
      };
    }
    if (isStagedParamGroupIcon(previousIconFileName)) {
      await discardStagedParamGroupIcon(previousIconFileName);
    }
    subCategoryDefaultsEditorOverridesDraft.value[paramCode][field] = normalizeIconFileName(payload.file_name || payload.icon_path) || "";
  } catch (_) {
    revokeSubCategoryDefaultIconPreview(paramCode, field);
    showAlert("آپلود آیکون پارامتر انجام نشد.", { title: "آیکون پارامتر" });
  } finally {
    subCategoryDefaultIconUploadingKey.value = "";
    subCategoryDefaultIconTargetCode.value = "";
    subCategoryDefaultIconTargetField.value = "icon_path";
    if (subCategoryDefaultIconInputEl.value) subCategoryDefaultIconInputEl.value.value = "";
  }
}

async function discardStagedParamGroupIcon(fileName) {
  const normalized = normalizeIconFileName(fileName);
  if (!normalized || !isStagedParamGroupIcon(normalized)) return;
  try {
    await fetch(`/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/param-group-icons/${encodeURIComponent(normalized)}`, {
      method: "DELETE",
    });
  } catch (_) {
    // Best-effort cleanup for staged uploads.
  }
}

async function cleanupStagedParamGroupUploads() {
  try {
    await fetch(`/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/param-group-icons`, {
      method: "DELETE",
    });
  } catch (_) {
    const stagedFileNames = [
      ...new Set(
        [
          ...editableParamGroups.value.map((item) => normalizeIconFileName(item?.param_group_icon_path)),
          ...editableSubCategories.value.flatMap((item) =>
            Object.values(item?.param_overrides || {}).flatMap((override) => [
              normalizeIconFileName(override?.icon_path),
              normalizeIconFileName(override?.binary_off_icon_path),
              normalizeIconFileName(override?.binary_on_icon_path),
            ])
          ),
          ...Object.values(subCategoryDefaultsEditorOverridesDraft.value || {}).flatMap((override) => [
            normalizeIconFileName(override?.icon_path),
            normalizeIconFileName(override?.binary_off_icon_path),
            normalizeIconFileName(override?.binary_on_icon_path),
          ]),
        ].filter((value) => isStagedParamGroupIcon(value))
      ),
    ];
    for (const fileName of stagedFileNames) {
      await discardStagedParamGroupIcon(fileName);
    }
  }
}

function buildPartKindDraft(item, overrides = {}) {
  return {
    ...item,
    ...overrides,
  };
}

function normalizeBooleanFlag(value, fallback = false) {
  if (typeof value === "boolean") return value;
  if (typeof value === "number") return value !== 0;
  const text = String(value ?? "").trim().toLowerCase();
  if (!text) return !!fallback;
  if (["1", "true", "yes", "on"].includes(text)) return true;
  if (["0", "false", "no", "off"].includes(text)) return false;
  return !!fallback;
}

function normalizeDuplicateValue(field, value) {
  if (field.endsWith("_id")) {
    const numericValue = Number(value);
    return Number.isInteger(numericValue) && numericValue > 0 ? String(numericValue) : "";
  }
  return String(value || "").trim().toLowerCase();
}

function buildDuplicateState(items, fields) {
  const counts = Object.fromEntries(fields.map((field) => [field, new Map()]));
  for (const item of items) {
    for (const field of fields) {
      const normalized = normalizeDuplicateValue(field, item?.[field]);
      if (!normalized) continue;
      counts[field].set(normalized, (counts[field].get(normalized) || 0) + 1);
    }
  }
  return counts;
}

function hasDuplicateValue(item, field, state) {
  const normalized = normalizeDuplicateValue(field, item?.[field]);
  if (!normalized) return false;
  return (state?.[field]?.get(normalized) || 0) > 1;
}

function getDuplicateInputTone(item, field, state) {
  const normalized = normalizeDuplicateValue(field, item?.[field]);
  if (!normalized) return null;
  return hasDuplicateValue(item, field, state) ? "duplicate" : "unique";
}

function getConstructionParamGroupDuplicateMessage(item) {
  const duplicateState = constructionParamGroupDuplicateState.value;
  if (!Number.isInteger(Number(item?.param_group_id)) || Number(item.param_group_id) < 1) {
    return { tone: "bad", text: "شناسه نامعتبر است" };
  }
  if (!String(item?.param_group_code || "").trim()) {
    return { tone: "bad", text: "کد خالی است" };
  }
  if (hasDuplicateValue(item, "param_group_id", duplicateState) || hasDuplicateValue(item, "param_group_code", duplicateState)) {
    return { tone: "bad", text: "تکراری است" };
  }
  return { tone: "good", text: "تکراری نیست" };
}

function getConstructionTemplateDuplicateMessage(item) {
  const duplicateState = constructionTemplateDuplicateState.value;
  if (!Number.isInteger(Number(item?.temp_id)) || Number(item.temp_id) < 1) {
    return { tone: "bad", text: "شناسه نامعتبر است" };
  }
  if (!String(item?.temp_title || "").trim()) {
    return { tone: "bad", text: "عنوان خالی است" };
  }
  if (hasDuplicateValue(item, "temp_id", duplicateState) || hasDuplicateValue(item, "temp_title", duplicateState)) {
    return { tone: "bad", text: "تکراری است" };
  }
  return { tone: "good", text: "تکراری نیست" };
}

function getConstructionCategoryDuplicateMessage(item) {
  const duplicateState = constructionCategoryDuplicateState.value;
  if (!Number.isInteger(Number(item?.temp_id)) || Number(item.temp_id) < 1) {
    return { tone: "bad", text: "تمپلیت نامعتبر است" };
  }
  if (!Number.isInteger(Number(item?.cat_id)) || Number(item.cat_id) < 1) {
    return { tone: "bad", text: "شناسه نامعتبر است" };
  }
  if (!String(item?.cat_title || "").trim()) {
    return { tone: "bad", text: "عنوان خالی است" };
  }
  const duplicateTitleCount = editableCategories.value.filter((row) => (
    Number(row?.temp_id) === Number(item?.temp_id) &&
    String(row?.admin_id || "system") === String(item?.admin_id || "system") &&
    String(row?.cat_title || "").trim().toLowerCase() === String(item?.cat_title || "").trim().toLowerCase()
  )).length;
  if (hasDuplicateValue(item, "cat_id", duplicateState) || duplicateTitleCount > 1) {
    return { tone: "bad", text: "تکراری است" };
  }
  return { tone: "good", text: "تکراری نیست" };
}

function getConstructionSubCategoryDuplicateMessage(item) {
  const duplicateState = constructionSubCategoryDuplicateState.value;
  if (!Number.isInteger(Number(item?.temp_id)) || Number(item.temp_id) < 1) {
    return { tone: "bad", text: "تمپلیت نامعتبر است" };
  }
  if (!Number.isInteger(Number(item?.cat_id)) || Number(item.cat_id) < 1) {
    return { tone: "bad", text: "دسته نامعتبر است" };
  }
  if (!Number.isInteger(Number(item?.sub_cat_id)) || Number(item.sub_cat_id) < 1) {
    return { tone: "bad", text: "شناسه نامعتبر است" };
  }
  if (!String(item?.sub_cat_title || "").trim()) {
    return { tone: "bad", text: "عنوان خالی است" };
  }
  const duplicateTitleCount = editableSubCategories.value.filter((row) => (
    Number(row?.cat_id) === Number(item?.cat_id) &&
    String(row?.admin_id || "system") === String(item?.admin_id || "system") &&
    String(row?.sub_cat_title || "").trim().toLowerCase() === String(item?.sub_cat_title || "").trim().toLowerCase()
  )).length;
  if (hasDuplicateValue(item, "sub_cat_id", duplicateState) || duplicateTitleCount > 1) {
    return { tone: "bad", text: "تکراری است" };
  }
  return { tone: "good", text: "تکراری نیست" };
}

function getConstructionParamDuplicateMessage(item) {
  const duplicateState = constructionParamDuplicateState.value;
  if (!Number.isInteger(Number(item?.param_id)) || Number(item.param_id) < 1) {
    return { tone: "bad", text: "شناسه نامعتبر است" };
  }
  if (!String(item?.param_code || "").trim()) {
    return { tone: "bad", text: "کد خالی است" };
  }
  if (hasDuplicateValue(item, "param_id", duplicateState) || hasDuplicateValue(item, "param_code", duplicateState)) {
    return { tone: "bad", text: "تکراری است" };
  }
  return { tone: "good", text: "تکراری نیست" };
}

function getConstructionBaseFormulaDuplicateMessage(item) {
  const duplicateState = constructionBaseFormulaDuplicateState.value;
  if (!Number.isInteger(Number(item?.fo_id)) || Number(item.fo_id) < 1) {
    return { tone: "bad", text: "شناسه نامعتبر است" };
  }
  if (!String(item?.param_formula || "").trim()) {
    return { tone: "bad", text: "کد خالی است" };
  }
  if (hasDuplicateValue(item, "fo_id", duplicateState) || hasDuplicateValue(item, "param_formula", duplicateState)) {
    return { tone: "bad", text: "تکراری است" };
  }
  return { tone: "good", text: "تکراری نیست" };
}

function getConstructionPartFormulaDuplicateMessage(item) {
  const duplicateState = constructionPartFormulaDuplicateState.value;
  if (!Number.isInteger(Number(item?.part_formula_id)) || Number(item.part_formula_id) < 1) {
    return { tone: "bad", text: "شناسه نامعتبر است" };
  }
  if (!String(item?.part_code || "").trim()) {
    return { tone: "bad", text: "کد خالی است" };
  }
  const pairKey = `${Number(item?.part_kind_id) || 0}:${Number(item?.part_sub_kind_id) || 0}:${String(item?.admin_id || "system")}`;
  const duplicatePairCount = editablePartFormulas.value.filter((row) => {
    const rowKey = `${Number(row?.part_kind_id) || 0}:${Number(row?.part_sub_kind_id) || 0}:${String(row?.admin_id || "system")}`;
    return rowKey === pairKey;
  }).length;
  if (
    hasDuplicateValue(item, "part_formula_id", duplicateState) ||
    hasDuplicateValue(item, "part_code", duplicateState) ||
    duplicatePairCount > 1
  ) {
    return { tone: "bad", text: "تکراری است" };
  }
  return { tone: "good", text: "تکراری نیست" };
}

function getBaseFormulaCodeCellStyle() {
  const widthCh = baseFormulaCodeWidthCh.value;
  return {
    width: `calc(${widthCh}ch + 36px)`,
    minWidth: `calc(${widthCh}ch + 36px)`,
    maxWidth: `calc(${widthCh}ch + 36px)`,
  };
}

function getBaseFormulaCodeInputStyle() {
  return {
    width: `calc(${baseFormulaCodeWidthCh.value}ch + 20px)`,
    minWidth: `calc(${baseFormulaCodeWidthCh.value}ch + 20px)`,
  };
}

function createBaseFormulaDraft(item, overrides = {}) {
  return {
    ...item,
    ...overrides,
  };
}

function createPartFormulaDraft(item, overrides = {}) {
  return {
    ...item,
    ...overrides,
  };
}

function buildNewBaseFormulaDraft() {
  const nextId = editableBaseFormulas.value.reduce((max, item) => Math.max(max, Number(item.fo_id) || 0), 0) + 1;
  return createBaseFormulaDraft({
    id: `draft-base-formula-row-${Date.now()}-${nextId}`,
    admin_id: currentAdminId.value,
    fo_id: nextId,
    param_formula: `f${nextId}`,
    formula: "(u_f_o)",
    code: `f${nextId}`,
    title: `f${nextId}`,
    sort_order: nextId,
    is_system: false,
    __isNew: true,
    __dirty: false,
  });
}

function buildNewPartFormulaDraft() {
  const nextId = editablePartFormulas.value.reduce((max, item) => Math.max(max, Number(item.part_formula_id) || 0), 0) + 1;
  const defaultPartKindId = Number(constructionPartKinds.value[0]?.part_kind_id) || 1;
  const basePayload = {
    id: `draft-part-formula-row-${Date.now()}-${nextId}`,
    admin_id: null,
    part_formula_id: nextId,
    part_kind_id: defaultPartKindId,
    part_sub_kind_id: nextId,
    part_code: `part_${nextId}`,
    part_title: `قطعه ${toPersianDigits(nextId)}`,
    code: `part_${nextId}`,
    title: `قطعه ${toPersianDigits(nextId)}`,
    sort_order: nextId,
    is_system: true,
    __isNew: true,
    __dirty: false,
  };
  for (const field of PART_FORMULA_FIELDS) {
    basePayload[field.key] = "(1)";
  }
  return createPartFormulaDraft(basePayload);
}

function formulaTokenToText(token) {
  return String(token?.value || "");
}

function serializeFormulaTokens(tokens) {
  return tokens.map(formulaTokenToText).join("");
}

function isFormulaNumberToken(value) {
  return /^-?(?:\d+(?:\.\d+)?|\.\d+)$/.test(String(value || "").trim());
}

function normalizeBaseFormulaNumberInput(value) {
  return String(value || "").replace(/[^\d.\-]/g, "").replace(/(?!^)-/g, "");
}

function tokenizeFormulaExpression(expression) {
  const source = String(expression || "").trim();
  if (!source) return { tokens: [], errors: [] };
  const tokens = [];
  let index = 0;
  while (index < source.length) {
    const char = source[index];
    if (/\s/.test(char)) {
      index += 1;
      continue;
    }
    const previousToken = tokens[tokens.length - 1] || null;
    const canReadNegativeNumber = char === "-" && (!previousToken || previousToken.value === "(" || ["+", "-", "*", "/"].includes(previousToken.value));
    if (/[A-Za-z_]/.test(char)) {
      let end = index + 1;
      while (end < source.length && /[A-Za-z0-9_]/.test(source[end])) end += 1;
      tokens.push({ type: "identifier", value: source.slice(index, end) });
      index = end;
      continue;
    }
    if (/\d|\./.test(char) || canReadNegativeNumber) {
      let end = index + (canReadNegativeNumber ? 1 : 0);
      let hasDigit = false;
      let hasDot = false;
      while (end < source.length) {
        const current = source[end];
        if (/\d/.test(current)) {
          hasDigit = true;
          end += 1;
          continue;
        }
        if (current === "." && !hasDot) {
          hasDot = true;
          end += 1;
          continue;
        }
        break;
      }
      const value = source.slice(index, end);
      if (hasDigit && isFormulaNumberToken(value)) {
        tokens.push({ type: "number", value });
        index = end;
        continue;
      }
    }
    if ("()+-*/".includes(char)) {
      tokens.push({ type: char === "(" || char === ")" ? "paren" : "operator", value: char });
      index += 1;
      continue;
    }
    return {
      tokens: [],
      errors: [`عبارت فرمول نزدیک «${source.slice(index, index + 12)}» معتبر نیست.`],
    };
  }
  return { tokens, errors: [] };
}

function validateFormulaExpression(expression, knownCodes = new Set(), options = {}) {
  const text = String(expression || "").trim();
  if (!text) return ["عبارت فرمول خالی است."];
  const identifierLabel = String(options.identifierLabel || "کد");

  const { tokens, errors } = tokenizeFormulaExpression(text);
  if (errors.length) return errors;

  const result = [];
  let depth = 0;
  let expectingOperand = true;
  let previousValue = null;

  for (const token of tokens) {
    if (expectingOperand) {
      if (token.value === "(") {
        depth += 1;
      } else if (token.type === "identifier") {
        if (knownCodes.size > 0 && !knownCodes.has(token.value)) {
          result.push(`${identifierLabel} «${token.value}» شناخته‌شده نیست.`);
          break;
        }
        expectingOperand = false;
      } else if (token.type === "number") {
        expectingOperand = false;
      } else if (token.value === ")") {
        result.push("پرانتزها متوازن نیستند.");
        break;
      } else {
        result.push(previousValue ? "دو عملگر یا ترتیب نامعتبر در فرمول وجود دارد." : "فرمول نمی‌تواند با عملگر شروع شود.");
        break;
      }
    } else if (token.value === ")") {
      if (previousValue === "(") {
        result.push("پرانتز خالی مجاز نیست.");
        break;
      }
      depth -= 1;
      if (depth < 0) {
        result.push("پرانتزها متوازن نیستند.");
        break;
      }
    } else if (["+","-","*","/"].includes(token.value)) {
      expectingOperand = true;
    } else if (token.value === "(") {
      result.push("الگوی فرمول نامعتبر است.");
      break;
    } else {
      result.push("الگوی فرمول نامعتبر است.");
      break;
    }

    previousValue = token.value;
  }

  if (!result.length && expectingOperand) result.push("فرمول نمی‌تواند با عملگر تمام شود.");
  if (!result.length && depth !== 0) result.push("پرانتزها متوازن نیستند.");
  return result;
}

function getPartFormulaValidationErrors(item, currentId = null) {
  const errors = [];
  const partFormulaId = Number(item?.part_formula_id);
  const partKindId = Number(item?.part_kind_id);
  const partSubKindId = Number(item?.part_sub_kind_id);
  const partCode = String(item?.part_code || "").trim();
  const partTitle = String(item?.part_title || "").trim();
  if (!Number.isInteger(partFormulaId) || partFormulaId < 1) errors.push("شناسه فرمول قطعه معتبر نیست.");
  if (!Number.isInteger(partKindId) || partKindId < 1) errors.push("نوع قطعه معتبر نیست.");
  if (!Number.isInteger(partSubKindId) || partSubKindId < 1) errors.push("زیرنوع قطعه معتبر نیست.");
  if (!partCode) errors.push("کد قطعه خالی است.");
  if (!partTitle) errors.push("عنوان قطعه خالی است.");
  const scopedRows = editablePartFormulas.value.filter((row) => String(row.id) !== String(currentId));
  if (scopedRows.some((row) => Number(row.part_formula_id) === partFormulaId)) errors.push("شناسه فرمول قطعه تکراری است.");
  if (scopedRows.some((row) => String(row.part_code || "").trim().toLowerCase() === partCode.toLowerCase())) errors.push("کد قطعه تکراری است.");
  if (
    scopedRows.some((row) =>
      Number(row.part_kind_id) === partKindId &&
      Number(row.part_sub_kind_id) === partSubKindId &&
      String(row.admin_id || "") === String(item?.admin_id || "")
    )
  ) {
    errors.push("ترکیب نوع قطعه و زیرنوع قطعه تکراری است.");
  }
  for (const field of PART_FORMULA_FIELDS) {
    const expression = String(item?.[field.key] || "").trim();
    if (!expression) {
      errors.push(`${field.label} خالی است.`);
      continue;
    }
    const formulaErrors = validateFormulaExpression(expression, partFormulaKnownCodes.value, { identifierLabel: "کد" });
    if (formulaErrors.length > 0) {
      errors.push(`${field.label}: ${formulaErrors[0]}`);
      break;
    }
  }
  return [...new Set(errors)];
}

function syncBaseFormulaBuilderFromFormulaText(options = {}) {
  const draft = baseFormulaBuilderDraft.value;
  if (!draft) return;
  const fieldName = String(baseFormulaBuilderTargetField.value || "formula");
  const parsed = tokenizeFormulaExpression(draft[fieldName]);
  if (parsed.errors.length) {
    if (!options.silent) baseFormulaBuilderSyncWarning.value = "عبارت دستی کامل parse نشد. می‌توانید ادامه را تایپ کنید یا از پاک‌سازی tokenها استفاده کنید.";
    return;
  }
  baseFormulaBuilderTokens.value = parsed.tokens;
  baseFormulaBuilderSyncWarning.value = "";
}

function updateBaseFormulaBuilderFormula(text, options = {}) {
  if (!baseFormulaBuilderDraft.value) return;
  const fieldName = String(baseFormulaBuilderTargetField.value || "formula");
  baseFormulaBuilderDraft.value[fieldName] = text;
  if (options.syncTokens !== false) syncBaseFormulaBuilderFromFormulaText({ silent: options.silent });
}

function openBaseFormulaBuilder(item, mode = "edit", options = {}) {
  baseFormulaBuilderMode.value = mode;
  baseFormulaBuilderEntity.value = options.entity || "base_formulas";
  baseFormulaBuilderTargetRowId.value = item?.id ?? null;
  baseFormulaBuilderTargetField.value = options.field || "formula";
  baseFormulaBuilderDraft.value = baseFormulaBuilderEntity.value === "part_formulas"
    ? createPartFormulaDraft(item)
    : createBaseFormulaDraft(item);
  baseFormulaBuilderNumberInput.value = "";
  baseFormulaBuilderTokens.value = [];
  baseFormulaBuilderOpen.value = true;
  syncBaseFormulaBuilderFromFormulaText({ silent: true });
}

async function closeBaseFormulaBuilder() {
  const draft = baseFormulaBuilderDraft.value;
  if (!baseFormulaBuilderOpen.value || !draft) {
    baseFormulaBuilderOpen.value = false;
    return;
  }
  const originalRows = baseFormulaBuilderEntity.value === "part_formulas" ? editablePartFormulas.value : editableBaseFormulas.value;
  const original = originalRows.find((item) => String(item.id) === String(baseFormulaBuilderTargetRowId.value));
  const hasChanges = baseFormulaBuilderMode.value === "create"
    ? Object.entries(draft).some(([key, value]) => !key.startsWith("__") && String(value ?? "").trim() !== "")
    : !!original && JSON.stringify({
      ...original,
      __isNew: undefined,
      __dirty: undefined,
    }) !== JSON.stringify({
      ...draft,
      __isNew: undefined,
      __dirty: undefined,
    });
  if (hasChanges) {
    const ok = await showConfirm("تغییرات سازنده فرمول اعمال نشده‌اند. پنجره بسته شود؟", {
      title: "بستن سازنده فرمول",
      confirmText: "بستن",
      cancelText: "بازگشت",
    });
    if (!ok) return;
  }
  baseFormulaBuilderOpen.value = false;
  baseFormulaBuilderDraft.value = null;
  baseFormulaBuilderTargetRowId.value = null;
  baseFormulaBuilderTargetField.value = "formula";
  baseFormulaBuilderEntity.value = "base_formulas";
  baseFormulaBuilderTokens.value = [];
  baseFormulaBuilderSyncWarning.value = "";
  baseFormulaBuilderNumberInput.value = "";
}

function appendBaseFormulaToken(type, value) {
  const nextToken = { type, value: String(value) };
  const nextTokens = [...baseFormulaBuilderTokens.value, nextToken];
  baseFormulaBuilderTokens.value = nextTokens;
  updateBaseFormulaBuilderFormula(serializeFormulaTokens(nextTokens), { syncTokens: false, silent: true });
  baseFormulaBuilderSyncWarning.value = "";
}

function removeLastBaseFormulaToken() {
  if (!baseFormulaBuilderTokens.value.length) return;
  const nextTokens = baseFormulaBuilderTokens.value.slice(0, -1);
  baseFormulaBuilderTokens.value = nextTokens;
  updateBaseFormulaBuilderFormula(serializeFormulaTokens(nextTokens), { syncTokens: false, silent: true });
  baseFormulaBuilderSyncWarning.value = "";
}

function clearBaseFormulaTokens() {
  baseFormulaBuilderTokens.value = [];
  updateBaseFormulaBuilderFormula("", { syncTokens: false, silent: true });
  baseFormulaBuilderSyncWarning.value = "";
}

function addBaseFormulaBuilderNumber() {
  const value = String(baseFormulaBuilderNumberInput.value || "").trim();
  if (!isFormulaNumberToken(value)) return;
  appendBaseFormulaToken("number", value);
  baseFormulaBuilderNumberInput.value = "";
}

function applyBaseFormulaBuilder() {
  const draft = baseFormulaBuilderDraft.value;
  if (!draft || baseFormulaBuilderValidationErrors.value.length > 0) return;
  if (baseFormulaBuilderEntity.value === "part_formulas") {
    const normalized = createPartFormulaDraft(draft, {
      part_code: String(draft.part_code || "").trim(),
      part_title: String(draft.part_title || "").trim(),
      code: String(draft.part_code || "").trim(),
      title: String(draft.part_title || "").trim(),
      sort_order: Number.isFinite(Number(draft.sort_order)) ? Number(draft.sort_order) : Number(draft.part_formula_id),
      is_system: draft.admin_id === null,
    });
    for (const field of PART_FORMULA_FIELDS) {
      normalized[field.key] = String(draft[field.key] || "").trim();
    }
    if (baseFormulaBuilderMode.value === "create") {
      editablePartFormulas.value = [...editablePartFormulas.value, normalized];
    } else {
      editablePartFormulas.value = editablePartFormulas.value.map((item) => {
        if (String(item.id) !== String(baseFormulaBuilderTargetRowId.value)) return item;
        return createPartFormulaDraft(normalized, {
          __isNew: !!item.__isNew,
          __dirty: item.__isNew ? false : true,
        });
      });
    }
  } else {
  const normalized = createBaseFormulaDraft(draft, {
    param_formula: String(draft.param_formula || "").trim(),
    formula: String(draft.formula || "").trim(),
    code: String(draft.param_formula || "").trim(),
    title: String(draft.param_formula || "").trim(),
    sort_order: Number.isFinite(Number(draft.sort_order)) ? Number(draft.sort_order) : Number(draft.fo_id),
    is_system: draft.admin_id === null,
  });
  if (baseFormulaBuilderMode.value === "create") {
    editableBaseFormulas.value = [...editableBaseFormulas.value, normalized];
  } else {
    editableBaseFormulas.value = editableBaseFormulas.value.map((item) => {
      if (String(item.id) !== String(baseFormulaBuilderTargetRowId.value)) return item;
      return createBaseFormulaDraft(normalized, {
        __isNew: !!item.__isNew,
        __dirty: item.__isNew ? false : true,
      });
    });
  }
  }
  baseFormulaBuilderOpen.value = false;
  baseFormulaBuilderDraft.value = null;
  baseFormulaBuilderTargetRowId.value = null;
  baseFormulaBuilderTargetField.value = "formula";
  baseFormulaBuilderEntity.value = "base_formulas";
  baseFormulaBuilderTokens.value = [];
  baseFormulaBuilderSyncWarning.value = "";
  baseFormulaBuilderNumberInput.value = "";
}

function withConstructionDraftState(item) {
  return buildPartKindDraft(item, { __isNew: false, __dirty: false });
}

function getConstructionOwnerBadge(item) {
  if (item?.admin_id === null || item?.is_system) {
    return { text: "سیستم", tone: "system" };
  }
  return { text: "ادمین اختصاصی", tone: "admin" };
}

function getConstructionSubCategoryByDesign(item) {
  if (!item) return null;
  return constructionSubCategories.value.find((row) =>
    String(row.id) === String(item.sub_category_id)
    || Number(row.sub_cat_id) === Number(item.sub_cat_id)
  ) || null;
}

function getConstructionSubCategoryTitleByDesign(item) {
  const subCategory = getConstructionSubCategoryByDesign(item);
  return String(
    subCategory?.sub_cat_title
    || subCategory?.title
    || item?.sub_cat_title
    || item?.title
    || ""
  ).trim();
}

function syncSubCategoryDesignDraftSubCategoryFields(item) {
  if (!item) return item;
  const subCategory = editableSubCategories.value.find((row) => String(row.id) === String(item.sub_category_id));
  if (!subCategory) return item;
  item.temp_id = Number(subCategory.temp_id) || 0;
  item.cat_id = Number(subCategory.cat_id) || 0;
  item.sub_cat_id = Number(subCategory.sub_cat_id) || 0;
  item.sub_cat_title = String(subCategory.sub_cat_title || "").trim();
  return item;
}

function buildNewSubCategoryDesignDraft() {
  const nextId = editableSubCategoryDesigns.value.reduce((max, item) => Math.max(max, Number(item.design_id) || 0), 0) + 1;
  const fallbackSubCategory = constructionSubCategories.value[0] || null;
  return syncSubCategoryDesignDraftSubCategoryFields({
    id: null,
    admin_id: null,
    sub_category_id: fallbackSubCategory?.id || "",
    temp_id: Number(fallbackSubCategory?.temp_id) || 0,
    cat_id: Number(fallbackSubCategory?.cat_id) || 0,
    sub_cat_id: Number(fallbackSubCategory?.sub_cat_id) || 0,
    sub_cat_title: String(fallbackSubCategory?.sub_cat_title || "").trim(),
    design_id: nextId,
    design_title: `طرح ${toPersianDigits(nextId)}`,
    code: `sub_category_design_${nextId}`,
    sort_order: nextId,
    is_system: true,
    parts: [],
    interior_instances: [],
  });
}

function buildNewInternalPartGroupDraft() {
  const nextId = editableInternalPartGroups.value.reduce((max, item) => Math.max(max, Number(item.group_id) || 0), 0) + 1;
  return ensureInternalPartGroupControllerConfig({
    id: null,
    admin_id: null,
    group_id: nextId,
    group_title: `گروه داخلی ${toPersianDigits(nextId)}`,
    code: `internal_part_group_${nextId}`,
    line_color: DEFAULT_INTERIOR_LINE_COLOR,
    sort_order: nextId,
    is_system: true,
    parts: [],
    param_groups: [],
    param_defaults: {},
    param_overrides: {},
    controller_type: "",
    controller_bindings: {},
  });
}

function resetSubCategoryDesignEditorState() {
  subCategoryDesignEditorOpen.value = false;
  subCategoryDesignEditorDraft.value = null;
  subCategoryDesignEditorPreview.value = null;
  subCategoryDesignPreviewLoading.value = false;
  subCategoryDesignPreviewError.value = "";
  subCategoryDesignEditorSaving.value = false;
}

function closeSubCategoryDesignEditor() {
  if (subCategoryDesignEditorSaving.value) return;
  resetSubCategoryDesignEditorState();
}

function closeInternalPartGroupEditor() {
  internalPartGroupEditorOpen.value = false;
  internalPartGroupEditorDraft.value = null;
  internalPartGroupParamGroupsOpen.value = false;
}

function hasInternalPartGroupDefaultsChanges() {
  const row = activeInternalPartGroupDefaultsRow.value;
  if (!row) return false;
  return getInternalPartGroupSelectedParamColumns(row).some((column) => {
    const override = row.param_overrides?.[column.key] || {};
    const nextValue = String(internalPartGroupDefaultsValues.value?.[column.key] ?? "").trim();
    const prevValue = String(row.param_defaults?.[column.key] ?? "").trim();
    if (override.input_mode === "binary") {
      return (nextValue === "1" ? "1" : "0") !== (prevValue === "1" ? "1" : "0");
    }
    return nextValue !== prevValue;
  });
}

function resetInternalPartGroupDefaultsEditorState() {
  internalPartGroupDefaultsEditorOpen.value = false;
  internalPartGroupDefaultsEditorRowId.value = null;
  internalPartGroupDefaultsEditorGroups.value = [];
  internalPartGroupDefaultsValues.value = {};
  internalPartGroupDefaultsActiveGroupId.value = "";
  internalPartGroupDefaultsApplying.value = false;
}

async function closeInternalPartGroupDefaultsEditor() {
  if (internalPartGroupDefaultsApplying.value) return;
  if (hasInternalPartGroupDefaultsChanges()) {
    const ok = await showConfirm("تغییرات پیش‌فرض‌های گروه داخلی اعمال نشده‌اند. پنجره بسته شود؟", {
      title: "بستن پیش‌فرض‌ها",
      confirmText: "بستن",
      cancelText: "بازگشت",
    });
    if (!ok) return;
  }
  resetInternalPartGroupDefaultsEditorState();
}

function resetInternalPartGroupControllerEditorState() {
  internalPartGroupControllerEditorOpen.value = false;
  internalPartGroupControllerEditorRowId.value = null;
  internalPartGroupControllerEditorType.value = "";
  internalPartGroupControllerEditorBindings.value = {};
  internalPartGroupControllerEditorApplying.value = false;
}

function getInternalPartGroupControllerEditorBindingsNormalized() {
  const row = activeInternalPartGroupControllerRow.value;
  const allowedCodes = row ? new Set(getInternalPartGroupSelectedParamColumns(row).map((column) => column.key)) : new Set();
  return normalizeInternalPartGroupControllerBindings(
    internalPartGroupControllerEditorType.value,
    internalPartGroupControllerEditorBindings.value,
    allowedCodes,
  );
}

function hasInternalPartGroupControllerChanges() {
  const row = activeInternalPartGroupControllerRow.value;
  if (!row) return false;
  const currentType = normalizeInternalPartGroupControllerType(row.controller_type);
  const nextType = normalizeInternalPartGroupControllerType(internalPartGroupControllerEditorType.value);
  if (currentType !== nextType) return true;
  const currentBindings = normalizeInternalPartGroupControllerBindings(currentType, row.controller_bindings);
  const nextBindings = getInternalPartGroupControllerEditorBindingsNormalized();
  const keys = new Set([
    ...Object.keys(currentBindings || {}),
    ...Object.keys(nextBindings || {}),
  ]);
  return Array.from(keys).some((key) =>
    String(currentBindings?.[key]?.param_code || "").trim() !== String(nextBindings?.[key]?.param_code || "").trim()
  );
}

async function closeInternalPartGroupControllerEditor() {
  if (internalPartGroupControllerEditorApplying.value) return;
  if (hasInternalPartGroupControllerChanges()) {
    const ok = await showConfirm("تغییرات کنترلر گروه اعمال نشده‌اند. پنجره بسته شود؟", {
      title: "بستن کنترلر گروه",
      confirmText: "بستن",
      cancelText: "بازگشت",
    });
    if (!ok) return;
  }
  resetInternalPartGroupControllerEditorState();
}

function syncInternalPartGroupControllerEditorBindings() {
  internalPartGroupControllerEditorBindings.value = normalizeInternalPartGroupControllerBindings(
    internalPartGroupControllerEditorType.value,
    internalPartGroupControllerEditorBindings.value,
  );
}

function openInternalPartGroupControllerEditor(item) {
  const row = findEditableInternalPartGroupById(item?.id);
  if (!row?.id) return;
  ensureInternalPartGroupParamDefaults(row);
  ensureInternalPartGroupControllerConfig(row);
  internalPartGroupControllerEditorRowId.value = row.id;
  internalPartGroupControllerEditorType.value = normalizeInternalPartGroupControllerType(row.controller_type);
  internalPartGroupControllerEditorBindings.value = normalizeInternalPartGroupControllerBindings(
    row.controller_type,
    row.controller_bindings,
  );
  internalPartGroupControllerEditorOpen.value = true;
}

function updateInternalPartGroupControllerEditorType(value) {
  internalPartGroupControllerEditorType.value = normalizeInternalPartGroupControllerType(value);
  syncInternalPartGroupControllerEditorBindings();
}

async function applyInternalPartGroupControllerEditor() {
  const row = activeInternalPartGroupControllerRow.value;
  if (!row || internalPartGroupControllerEditorApplying.value) return;
  internalPartGroupControllerEditorApplying.value = true;
  ensureInternalPartGroupParamDefaults(row);
  ensureInternalPartGroupControllerConfig(row);
  row.controller_type = normalizeInternalPartGroupControllerType(internalPartGroupControllerEditorType.value);
  row.controller_bindings = getInternalPartGroupControllerEditorBindingsNormalized();
  try {
    await persistInternalPartGroupRow(row);
  } catch (error) {
    showAlert(error?.message || "ذخیره کنترلر گروه قطعات داخلی انجام نشد.", { title: "خطا" });
    internalPartGroupControllerEditorApplying.value = false;
    return;
  }
  resetInternalPartGroupControllerEditorState();
}

function findEditableInternalPartGroupById(value) {
  const id = String(value || "").trim();
  if (!id) return null;
  return editableInternalPartGroups.value.find((row) => String(row?.id || "").trim() === id) || null;
}


async function refreshSubCategoryDesignPreview() {
  const draft = subCategoryDesignEditorDraft.value;
  if (!draft?.sub_category_id) {
    subCategoryDesignEditorPreview.value = null;
    return;
  }
  const seq = subCategoryDesignPreviewRequestSeq.value + 1;
  subCategoryDesignPreviewRequestSeq.value = seq;
  subCategoryDesignPreviewLoading.value = true;
  subCategoryDesignPreviewError.value = "";
  try {
    const res = await fetch("/api/sub-category-designs/preview-draft", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        admin_id: draft.admin_id ?? currentAdminId.value,
        sub_category_id: draft.sub_category_id,
        parts: normalizeSubCategoryDesignPayload(draft).parts,
        interior_instances: (Array.isArray(draft.interior_instances) ? draft.interior_instances : []).map((item) => ({
          id: item.id || null,
          internal_part_group_id: item.internal_part_group_id,
          instance_code: String(item.instance_code || "").trim() || "interior",
          line_color: item.line_color ? normalizeHexColor(item.line_color, DEFAULT_INTERIOR_LINE_COLOR) : null,
          ui_order: Number(item.ui_order) || 0,
          placement_z: Number(item.placement_z) || 0,
          interior_box_snapshot: { ...(item.interior_box_snapshot || {}) },
          param_values: Object.fromEntries(
            Object.entries(item.param_values || {}).map(([key, value]) => [key, value == null ? null : String(value)])
          ),
          param_meta: Object.fromEntries(
            Object.entries(item.param_meta || {}).map(([key, value]) => [key, { ...(value || {}) }])
          ),
        })),
      }),
    });
    if (!res.ok) {
      throw new Error(await readApiErrorMessage(res, "پیش‌نمایش طرح ساخته نشد."));
    }
    const payload = await res.json();
    if (seq !== subCategoryDesignPreviewRequestSeq.value) return;
    subCategoryDesignEditorPreview.value = payload;
  } catch (error) {
    if (seq !== subCategoryDesignPreviewRequestSeq.value) return;
    subCategoryDesignEditorPreview.value = null;
    subCategoryDesignPreviewError.value = error?.message || "پیش‌نمایش طرح ساخته نشد.";
  } finally {
    if (seq === subCategoryDesignPreviewRequestSeq.value) {
      subCategoryDesignPreviewLoading.value = false;
    }
  }
}

async function loadConstructionSubCategoryDesigns() {
  try {
    const url = `/api/sub-category-designs?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    const items = await res.json();
    editableSubCategoryDesigns.value = (await Promise.all(
      items.map(async (item) => withConstructionDraftState(await enrichDesignWithPreview(item)))
    ));
    constructionDeletedSubCategoryDesignIds.value = [];
  } catch (_) {
    showAlert("خواندن جدول طرح‌های ساب‌کت از دیتابیس انجام نشد.", { title: "خطا" });
  }
}

function normalizeCabinetBox(box) {
  return {
    width: Math.max(1, Number(box?.width) || 0),
    depth: Math.max(1, Number(box?.depth) || 0),
    height: Math.max(1, Number(box?.height) || 0),
    cx: Number(box?.cx) || 0,
    cy: Number(box?.cy) || 0,
    cz: Number(box?.cz) || 0,
  };
}

function normalizeOrderDesignPlacement(item) {
  const orderDesignId = String(item?.orderDesignId || item?.order_design_id || item?.id || "").trim();
  if (!orderDesignId) return null;
  return {
    orderDesignId,
    x: Number.isFinite(Number(item?.x)) ? Number(item.x) : 0,
    y: Number.isFinite(Number(item?.y)) ? Number(item.y) : 0,
    rotRad: Number.isFinite(Number(item?.rotRad)) ? Number(item.rotRad) : 0,
    mirrorX: 1,
  };
}

function buildModel2dLinesFromBoxes(boxes) {
  const lines = [];
  for (const rawBox of Array.isArray(boxes) ? boxes : []) {
    const box = normalizeCabinetBox(rawBox);
    const halfW = box.width * 0.5;
    const halfD = box.depth * 0.5;
    const x1 = box.cx - halfW;
    const x2 = box.cx + halfW;
    const y1 = box.cy - halfD;
    const y2 = box.cy + halfD;
    lines.push(
      { ax: x1, ay: y1, bx: x2, by: y1, thickness: 18, label: "" },
      { ax: x2, ay: y1, bx: x2, by: y2, thickness: 18, label: "" },
      { ax: x2, ay: y2, bx: x1, by: y2, thickness: 18, label: "" },
      { ax: x1, ay: y2, bx: x1, by: y1, thickness: 18, label: "" },
    );
  }
  return lines;
}

function buildModel2dOutlineFromBoxes(boxes) {
  const bounds = getCabinetBoxesBounds(boxes);
  if (!bounds) return [];
  return [
    { x: bounds.minX, y: bounds.minY },
    { x: bounds.maxX, y: bounds.minY },
    { x: bounds.maxX, y: bounds.maxY },
    { x: bounds.minX, y: bounds.maxY },
  ];
}

function getCachedOrderDesignGeometry(item) {
  if (!item) return { lines: [], outline: [] };
  const cacheKey = `${String(item.id || "").trim()}::${String(item.snapshot_checksum || "").trim()}::${Array.isArray(item.viewer_boxes) ? item.viewer_boxes.length : 0}`;
  const cached = orderDesignGeometryCache.get(cacheKey);
  if (cached) return cached;
  const next = {
    lines: buildModel2dLinesFromBoxes(item.viewer_boxes || []),
    outline: buildModel2dOutlineFromBoxes(item.viewer_boxes || []),
  };
  orderDesignGeometryCache.set(cacheKey, next);
  return next;
}

function getLinesBounds(lines) {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const l of Array.isArray(lines) ? lines : []) {
    minX = Math.min(minX, Number(l?.ax), Number(l?.bx));
    maxX = Math.max(maxX, Number(l?.ax), Number(l?.bx));
    minY = Math.min(minY, Number(l?.ay), Number(l?.by));
    maxY = Math.max(maxY, Number(l?.ay), Number(l?.by));
  }
  if (!isFinite(minX) || !isFinite(maxX) || !isFinite(minY) || !isFinite(maxY)) return null;
  return { minX, maxX, minY, maxY };
}

function getLinesIconWalls(lines) {
  const bounds = getLinesBounds(lines);
  if (!bounds) return [];
  const iconSize = 44;
  const iconPad = 4;
  const spanX = Math.max(1, bounds.maxX - bounds.minX);
  const spanY = Math.max(1, bounds.maxY - bounds.minY);
  const scale = Math.min((iconSize - iconPad * 2) / spanX, (iconSize - iconPad * 2) / spanY);
  const cx = (bounds.minX + bounds.maxX) * 0.5;
  const cy = (bounds.minY + bounds.maxY) * 0.5;
  return lines.map((l) => ({
    x1: iconSize * 0.5 + (Number(l.ax) - cx) * scale,
    y1: iconSize * 0.5 - (Number(l.ay) - cy) * scale,
    x2: iconSize * 0.5 + (Number(l.bx) - cx) * scale,
    y2: iconSize * 0.5 - (Number(l.by) - cy) * scale,
    sw: Math.max(2, (Number(l.thickness) || 18) * scale),
  }));
}

function getCabinetBoxesBounds(boxes) {
  return getLinesBounds(buildModel2dLinesFromBoxes(boxes));
}

function clientPointToStageWorld(clientX, clientY) {
  const full = editorRef.value?.getState?.();
  const st = full?.state || {};
  const zoom = Number(st.zoom);
  const offsetX = Number(st.offsetX);
  const offsetY = Number(st.offsetY);
  const stageRect = stageEl.value?.getBoundingClientRect();
  if (!stageRect || !Number.isFinite(zoom) || zoom <= 0 || !Number.isFinite(offsetX) || !Number.isFinite(offsetY)) {
    return null;
  }
  const stageX = clientX - stageRect.left;
  const stageY = clientY - stageRect.top;
  return {
    x: (stageX - offsetX) / zoom,
    y: -(stageY - offsetY) / zoom,
  };
}

function getCabinetDesignPreviewLines(design) {
  return buildModel2dLinesFromBoxes(design?.preview?.viewer_boxes || []);
}

function getCabinetDesignIconWalls(design) {
  return getLinesIconWalls(getCabinetDesignPreviewLines(design));
}


async function fetchSubCategoryDesignPreview(designId) {
  const previewRes = await fetch(`/api/sub-category-designs/${encodeURIComponent(String(designId))}/preview`);
  if (!previewRes.ok) throw new Error("preview-failed");
  return await previewRes.json();
}

async function enrichDesignWithPreview(item) {
  try {
    const preview = await fetchSubCategoryDesignPreview(item.id);
    return {
      ...item,
      design_outline_color: normalizeHexColor(item.design_outline_color || preview?.design_outline_color),
      sub_cat_title: getConstructionSubCategoryTitleByDesign(item),
      preview,
    };
  } catch (_) {
    return {
      ...item,
      design_outline_color: normalizeHexColor(item.design_outline_color),
      sub_cat_title: getConstructionSubCategoryTitleByDesign(item),
      preview: null,
    };
  }
}

function normalizeOrderDesignRecord(item) {
  if (!item || !item.id) return null;
  return {
    ...item,
    id: String(item.id),
    order_id: String(item.order_id || ""),
    sub_category_design_id: String(item.sub_category_design_id || ""),
    sub_category_id: String(item.sub_category_id || ""),
    design_outline_color: normalizeHexColor(item.design_outline_color),
    design_code: String(item.design_code || "").trim(),
    design_title: String(item.design_title || "").trim(),
    instance_code: String(item.instance_code || "").trim(),
    status: String(item.status || "draft").trim() || "draft",
    sort_order: Number(item.sort_order) || 0,
    snapshot_checksum: String(item.snapshot_checksum || "").trim(),
    order_attr_values: Object.fromEntries(
      Object.entries(item.order_attr_values || {}).map(([key, value]) => [key, value == null ? "" : String(value)])
    ),
    order_attr_meta: Object.fromEntries(
      Object.entries(item.order_attr_meta || {}).map(([key, value]) => [key, { ...(value || {}) }])
    ),
    part_snapshots: Array.isArray(item.part_snapshots) ? item.part_snapshots.map((row) => ({ ...(row || {}) })) : [],
    viewer_boxes: Array.isArray(item.viewer_boxes) ? item.viewer_boxes.map((row) => ({ ...(row || {}) })) : [],
    interior_instances: Array.isArray(item.interior_instances) ? item.interior_instances.map(normalizeInteriorInstanceRecord).filter(Boolean) : [],
  };
}

function sortOrderDesignCatalogRecords(items) {
  return items
    .slice()
    .sort((a, b) => {
      const orderDelta = (Number(a?.sort_order) || 0) - (Number(b?.sort_order) || 0);
      if (orderDelta !== 0) return orderDelta;
      return String(a?.id || "").localeCompare(String(b?.id || ""), "fa");
    });
}

async function loadCabinetDesignCatalog(force = false) {
  const adminKey = String(currentAdminId.value || "");
  if (cabinetDesignCatalogLoading.value) return;
  if (!force && cabinetDesignCatalogLoadedForAdmin.value === adminKey && cabinetDesignCatalog.value.length) return;

  cabinetDesignCatalogLoading.value = true;
  try {
    const listRes = await fetch(`/api/sub-category-designs?admin_id=${encodeURIComponent(currentAdminId.value)}`);
    if (!listRes.ok) {
      throw new Error(await readApiErrorMessage(listRes, "خواندن طرح‌های کابینت انجام نشد."));
    }
    const items = await listRes.json();
    cabinetDesignCatalog.value = await Promise.all(items.map((item) => enrichDesignWithPreview(item)));
    cabinetDesignCatalogLoadedForAdmin.value = adminKey;
  } catch (error) {
    cabinetDesignCatalog.value = [];
    showAlert(error?.message || "خواندن طرح‌های کابینت از دیتابیس انجام نشد.", { title: "خطا" });
  } finally {
    cabinetDesignCatalogLoading.value = false;
  }
}

async function loadOrderDesignCatalog(force = false) {
  const orderId = String(activeOrder.value?.id || "");
  if (!orderId) {
    orderDesignCatalog.value = [];
    orderDesignCatalogLoadedForOrderId.value = "";
    orderDesignPlacements.value = [];
    stageCabinetPlaceholderBoxes.value = [];
    activeCabinetDesignId.value = null;
    activeStageOrderDesignSelected.value = false;
    selectedStageOrderDesignIds.value = [];
    return;
  }
  if (orderDesignCatalogLoading.value) {
    if (force) orderDesignCatalogReloadQueued = true;
    return;
  }
  if (!force && orderDesignCatalogLoadedForOrderId.value === orderId) return;
  orderDesignCatalogLoading.value = true;
  const requestSeq = ++orderDesignCatalogLoadRequestSeq;
  try {
    const res = await fetch(`/api/order-designs?order_id=${encodeURIComponent(orderId)}`);
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "خواندن طرح‌های سفارش انجام نشد."));
    const nextItems = sortOrderDesignCatalogRecords((await res.json()).map(normalizeOrderDesignRecord).filter(Boolean));
    if (requestSeq !== orderDesignCatalogLoadRequestSeq) return;
    orderDesignCatalog.value = nextItems;
    const validIds = new Set(orderDesignCatalog.value.map((item) => String(item.id)));
    orderDesignPlacements.value = orderDesignPlacements.value.filter((placement) => validIds.has(String(placement.orderDesignId)));
    orderDesignCatalogLoadedForOrderId.value = orderId;
  } catch (error) {
    if (requestSeq !== orderDesignCatalogLoadRequestSeq) return;
    orderDesignCatalog.value = [];
    orderDesignCatalogLoadedForOrderId.value = "";
    showAlert(error?.message || "خواندن طرح‌های سفارش انجام نشد.", { title: "خطا" });
  } finally {
    orderDesignCatalogLoading.value = false;
    if (orderDesignCatalogReloadQueued) {
      orderDesignCatalogReloadQueued = false;
      await loadOrderDesignCatalog(true);
    }
  }
}

async function loadConstructionInternalPartGroups() {
  try {
    const url = `/api/internal-part-groups?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    editableInternalPartGroups.value = (await res.json()).map((item) =>
      ensureInternalPartGroupControllerConfig(
        ensureInternalPartGroupParamDefaults(withConstructionDraftState({
          ...item,
          line_color: normalizeHexColor(item.line_color, DEFAULT_INTERIOR_LINE_COLOR),
          param_groups: Array.isArray(item.param_groups) ? item.param_groups.map((group) => ({
            ...group,
            param_group_id: Number(group.param_group_id),
            param_group_code: String(group.param_group_code || "").trim(),
            param_group_title: String(group.param_group_title || "").trim(),
            param_group_icon_path: normalizeIconFileName(group.param_group_icon_path) || "",
            enabled: group.enabled !== false,
            ui_order: Number(group.ui_order) || 0,
          })) : [],
          param_defaults: Object.fromEntries(
            Object.entries(item.param_defaults || {}).map(([key, value]) => [String(key || "").trim(), value == null ? "" : String(value)])
          ),
          param_overrides: Object.fromEntries(
            Object.entries(item.param_overrides || {}).map(([key, override]) => [String(key || "").trim(), {
              display_title: String(override?.display_title || "").trim(),
              description_text: String(override?.description_text || "").trim(),
              icon_path: normalizeIconFileName(override?.icon_path) || "",
              input_mode: override?.input_mode === "binary" ? "binary" : "value",
              binary_off_label: String(override?.binary_off_label || "").trim() || "0",
              binary_on_label: String(override?.binary_on_label || "").trim() || "1",
              binary_off_icon_path: normalizeIconFileName(override?.binary_off_icon_path) || "",
              binary_on_icon_path: normalizeIconFileName(override?.binary_on_icon_path) || "",
            }])
          ),
          controller_type: normalizeInternalPartGroupControllerType(item.controller_type),
          controller_bindings: normalizeInternalPartGroupControllerBindings(item.controller_type, item.controller_bindings),
        }))
      )
    );
  } catch (_) {
    showAlert("خواندن جدول گروه قطعات داخلی از دیتابیس انجام نشد.", { title: "خطا" });
  }
}

function reconcileActiveOrderDesignSelection() {
  const activeId = String(activeCabinetDesignId.value || "").trim();
  if (!activeId) return false;
  const target = orderDesignCatalog.value.find((item) => String(item.id) === activeId);
  if (!target?.viewer_boxes?.length) return false;
  stageCabinetPlaceholderBoxes.value = target.viewer_boxes.map(normalizeCabinetBox);
  const placement = getOrderDesignPlacement(target.id) || getCurrentModel2dTransform();
  const restored = restoreActiveOrderDesignToEditor(target, placement);
  if (!restored) {
    editorRef.value?.selectModelOutline?.();
  }
  return true;
}

async function createOrderDesignFromSource(sourceDesign, { instanceCode = "", designTitle = "", orderAttrValues = {} } = {}) {
  const orderId = String(activeOrder.value?.id || "").trim();
  if (!orderId) {
    openOrderEntry();
    throw new Error("ابتدا یک سفارش فعال انتخاب کنید.");
  }
  const res = await fetch("/api/order-designs", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      order_id: orderId,
      sub_category_design_id: sourceDesign.id,
      instance_code: String(instanceCode || "").trim() || null,
      design_title: String(designTitle || sourceDesign.design_title || "").trim() || null,
      order_attr_values: orderAttrValues,
    }),
  });
  if (!res.ok) throw new Error(await readApiErrorMessage(res, "افزودن طرح به سفارش انجام نشد."));
  const freshCreated = upsertOrderDesignCatalogItem(await res.json());
  if (!freshCreated) throw new Error("طرح سفارش ساخته شد اما پاسخ معتبر برنگشت.");
  orderDesignCatalogLoadedForOrderId.value = orderId;
  if (String(activeCabinetDesignId.value || "") === String(freshCreated.id)) {
    stageCabinetPlaceholderBoxes.value = (freshCreated.viewer_boxes || []).map(normalizeCabinetBox);
  }
  return freshCreated;
}

function openOrderDesignEditor(item) {
  const normalized = normalizeOrderDesignRecord(item);
  if (!normalized) return;
  orderDesignEditorDraft.value = {
    ...normalized,
    order_attr_values: { ...(normalized.order_attr_values || {}) },
    order_attr_meta: { ...(normalized.order_attr_meta || {}) },
  };
  orderDesignEditorOpen.value = true;
}

function closeOrderDesignEditor() {
  orderDesignEditorOpen.value = false;
  orderDesignEditorDraft.value = null;
}

function getOrderDesignAttrEntries(item) {
  const meta = item?.order_attr_meta || {};
  const values = item?.order_attr_values || {};
  return Object.keys(meta)
    .map((key) => ({
      key,
      meta: meta[key] || {},
      value: values[key] ?? "",
    }))
    .sort((a, b) => {
      const groupDelta = (Number(a.meta.group_ui_order) || 0) - (Number(b.meta.group_ui_order) || 0);
      if (groupDelta !== 0) return groupDelta;
      const paramDelta = (Number(a.meta.param_ui_order) || 0) - (Number(b.meta.param_ui_order) || 0);
      if (paramDelta !== 0) return paramDelta;
      const idDelta = (Number(a.meta.param_id) || 0) - (Number(b.meta.param_id) || 0);
      if (idDelta !== 0) return idDelta;
      return String(a.meta.label || a.key).localeCompare(String(b.meta.label || b.key), "fa");
    });
}

async function persistOrderDesignRecord(item, nextAttrValues = null) {
  const target = normalizeOrderDesignRecord(item);
  if (!target?.id) return null;
  const payload = {
    design_title: String(target.design_title || "").trim(),
    instance_code: String(target.instance_code || "").trim(),
    sort_order: Number(target.sort_order) || 0,
    status: String(target.status || "draft"),
    order_attr_values: nextAttrValues || target.order_attr_values || {},
  };
  const res = await fetch(`/api/order-designs/${encodeURIComponent(String(target.id))}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره صفات طرح سفارش انجام نشد."));
  return normalizeOrderDesignRecord(await res.json());
}

async function updateActiveOrderDesignAttr({ key, value }) {
  const attrKey = String(key || "").trim();
  const normalizedValue = value == null ? "" : String(value);
  const targetIds = selectedOrderDesignIds.value.length
    ? selectedOrderDesignIds.value.slice()
    : (activeStageOrderDesign.value?.id ? [String(activeStageOrderDesign.value.id)] : []);
  if (!attrKey || !targetIds.length) return;

  const targets = targetIds
    .map((id) => orderDesignCatalog.value.find((item) => String(item.id) === String(id)))
    .filter(Boolean);
  if (!targets.length) return;

  const changedTargets = targets.filter((item) => {
    const currentValue = item?.order_attr_values?.[attrKey] == null ? "" : String(item.order_attr_values[attrKey]);
    return currentValue !== normalizedValue && !isOrderDesignSaving(item.id);
  });
  if (!changedTargets.length) return;

  const placementById = new Map(
    changedTargets.map((item) => [
      String(item.id),
      String(activeCabinetDesignId.value || "") === String(item.id)
        ? (activeStageOrderPlacement.value || getCurrentModel2dTransform())
        : getOrderDesignPlacement(item.id),
    ])
  );

  const savingIds = changedTargets.map((item) => String(item.id));
  orderDesignSavingIds.value = [...new Set([...orderDesignSavingIds.value, ...savingIds])];
  const nextValuesById = new Map();
  for (const item of changedTargets) {
    nextValuesById.set(String(item.id), {
      ...(item.order_attr_values || {}),
      [attrKey]: normalizedValue,
    });
  }
  orderDesignCatalog.value = orderDesignCatalog.value.map((item) => {
    const nextValues = nextValuesById.get(String(item.id));
    return nextValues ? { ...item, order_attr_values: nextValues } : item;
  });

  const shouldToggleStageLoading = !cabinetDesignDropLoading.value;
  if (shouldToggleStageLoading) {
    cabinetDesignDropLoadingMode.value = "edit";
    cabinetDesignDropLoading.value = true;
    cabinetDesignDropLoadingTitle.value =
      changedTargets.length > 1
        ? `${changedTargets.length} طرح سفارش`
        : String(changedTargets[0]?.design_title || changedTargets[0]?.instance_code || "").trim();
  }
  try {
    for (const item of changedTargets) {
      const fresh = await persistOrderDesignRecord(item, nextValuesById.get(String(item.id)) || {});
      if (fresh) {
        upsertOrderDesignCatalogItem(fresh);
        if (String(activeCabinetDesignId.value || "") === String(fresh.id)) {
          stageCabinetPlaceholderBoxes.value = (fresh.viewer_boxes || []).map(normalizeCabinetBox);
          restoreActiveOrderDesignToEditor(fresh, placementById.get(String(fresh.id)) || null);
        }
      }
    }
    await saveActiveOrderDrawing();
  } catch (error) {
    showAlert(error?.message || "ذخیره صفات طرح سفارش انجام نشد.", { title: "خطا" });
    await loadOrderDesignCatalog(true);
  } finally {
    orderDesignSavingIds.value = orderDesignSavingIds.value.filter((id) => !savingIds.includes(id));
    if (shouldToggleStageLoading) {
      cabinetDesignDropLoading.value = false;
      cabinetDesignDropLoadingTitle.value = "";
      cabinetDesignDropLoadingMode.value = "add";
    }
  }
}

async function saveOrderDesignEditor() {
  const draft = orderDesignEditorDraft.value;
  if (!draft?.id || cabinetDesignDropLoading.value) return;
  const designTitle = String(draft.design_title || "").trim();
  const instanceCode = String(draft.instance_code || "").trim();
  if (!designTitle) {
    showAlert("عنوان طرح سفارش نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
    return;
  }
  if (!instanceCode) {
    showAlert("کد نمونه نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
    return;
  }
  const activePlacement = getOrderDesignPlacement(draft.id) || getCurrentModel2dTransform();
  cabinetDesignDropLoadingMode.value = "edit";
  cabinetDesignDropLoading.value = true;
  cabinetDesignDropLoadingTitle.value = designTitle || instanceCode;
  try {
    const fresh = await persistOrderDesignRecord({
      ...draft,
      design_title: designTitle,
      instance_code: instanceCode,
    });
    if (fresh) {
      upsertOrderDesignCatalogItem(fresh);
      if (String(activeCabinetDesignId.value || "") === String(fresh.id)) {
        stageCabinetPlaceholderBoxes.value = (fresh.viewer_boxes || []).map(normalizeCabinetBox);
        restoreActiveOrderDesignToEditor(fresh, activePlacement);
        await saveActiveOrderDrawing();
      }
    } else {
      await loadOrderDesignCatalog(true);
    }
    closeOrderDesignEditor();
    showAlert("طرح سفارش ذخیره شد.", { title: "ذخیره طرح" });
  } catch (error) {
    showAlert(error?.message || "ذخیره طرح سفارش انجام نشد.", { title: "خطا" });
  } finally {
    cabinetDesignDropLoading.value = false;
    cabinetDesignDropLoadingTitle.value = "";
    cabinetDesignDropLoadingMode.value = "add";
  }
}

async function deleteOrderDesign(item) {
  const target = normalizeOrderDesignRecord(item);
  if (!target?.id) return;
  try {
    await deleteOrderDesignsByIds([target.id], {
      confirmMode: "single",
      successMessage: null,
    });
  } catch (error) {
    showAlert(error?.message || "حذف طرح سفارش انجام نشد.", { title: "خطا" });
  }
}

async function deleteActiveOrderDesignFromStage() {
  const target = activeStageOrderDesign.value;
  if (!target?.id) return;
  try {
    await deleteOrderDesignsByIds([target.id], {
      confirmMode: "single",
      successMessage: null,
    });
  } catch (error) {
    showAlert(error?.message || "حذف طرح سفارش انجام نشد.", { title: "خطا" });
  }
}

function localDesignToWorld(linesOrPoints, placement = null, kind = "lines") {
  const normalized = Array.isArray(linesOrPoints) ? linesOrPoints.map((entry) => ({ ...(entry || {}) })) : [];
  if (!normalized.length) return [];
  const tx = Number.isFinite(Number(placement?.x)) ? Number(placement.x) : 0;
  const ty = Number.isFinite(Number(placement?.y)) ? Number(placement.y) : 0;
  const rotRad = Number.isFinite(Number(placement?.rotRad)) ? Number(placement.rotRad) : 0;
  const cos = Math.cos(rotRad);
  const sin = Math.sin(rotRad);
  const mapPoint = (x, y) => {
    const rawX = Number(x) || 0;
    const dx = rawX;
    const dy = Number(y);
    return {
      x: (dx * cos - dy * sin) + tx,
      y: (dx * sin + dy * cos) + ty,
    };
  };
  if (kind === "points") {
    return normalized.map((point) => {
      const next = mapPoint(point.x, point.y);
      return {
        ...point,
        x: next.x,
        y: next.y,
      };
    });
  }
  return normalized.map((line) => {
    const a = mapPoint(line.ax, line.ay);
    const b = mapPoint(line.bx, line.by);
    return {
      ...line,
      ax: a.x,
      ay: a.y,
      bx: b.x,
      by: b.y,
    };
  });
}

function upsertOrderDesignPlacement(item) {
  const next = normalizeOrderDesignPlacement(item);
  if (!next) return;
  const index = orderDesignPlacements.value.findIndex((placement) => String(placement.orderDesignId) === String(next.orderDesignId));
  if (index >= 0) {
    orderDesignPlacements.value = orderDesignPlacements.value.map((placement, placementIndex) =>
      placementIndex === index ? { ...placement, ...next } : placement
    );
    return;
  }
  orderDesignPlacements.value = [...orderDesignPlacements.value, next];
}

function removeOrderDesignPlacement(orderDesignId) {
  const key = String(orderDesignId || "").trim();
  if (!key) return;
  orderDesignPlacements.value = orderDesignPlacements.value.filter((placement) => String(placement.orderDesignId) !== key);
}

function getOrderDesignPlacement(orderDesignId) {
  return orderDesignPlacements.value.find((placement) => String(placement.orderDesignId) === String(orderDesignId || "").trim()) || null;
}

function getCurrentModel2dTransform() {
  return {
    x: Number.isFinite(Number(model2dTransformRef.value?.x)) ? Number(model2dTransformRef.value.x) : 0,
    y: Number.isFinite(Number(model2dTransformRef.value?.y)) ? Number(model2dTransformRef.value.y) : 0,
    rotRad: Number.isFinite(Number(model2dTransformRef.value?.rotRad)) ? Number(model2dTransformRef.value.rotRad) : 0,
    mirrorX: 1,
  };
}

function getCurrentEditorModelPlacement() {
  const full = editorRef.value?.getState?.();
  const snap = full?.model2dSnap || null;
  if (snap) {
      return {
        x: Number.isFinite(Number(snap.offsetXmm)) ? Number(snap.offsetXmm) : 0,
        y: Number.isFinite(Number(snap.offsetYmm)) ? Number(snap.offsetYmm) : 0,
        rotRad: Number.isFinite(Number(snap.rotationRad)) ? Number(snap.rotationRad) : 0,
        mirrorX: 1,
      };
  }
  return getCurrentModel2dTransform();
}

function normalizeDoorScenePlacement(item) {
  const id = String(item?.id || "").trim();
  const modelUrl = String(item?.modelUrl || "").trim();
  if (!id || !modelUrl) return null;
  const modelBoundsMm = sanitizeDoorBoundsMm(item?.modelBoundsMm || getFallbackDoorModelBoundsMm());
  return {
    id,
    title: String(item?.title || "").trim() || "Door",
    modelUrl,
    modelBoundsMm,
    outlineColor: normalizeHexColor(item?.outlineColor || "#8B6B4A"),
    x: Number.isFinite(Number(item?.x)) ? Number(item.x) : 0,
    y: Number.isFinite(Number(item?.y)) ? Number(item.y) : 0,
    rotRad: Number.isFinite(Number(item?.rotRad)) ? Number(item.rotRad) : 0,
    floorOffsetMm: Math.max(0, Number(item?.floorOffsetMm) || 0),
    mirrorX: 1,
  };
}

function upsertDoorScenePlacement(item) {
  const next = normalizeDoorScenePlacement(item);
  if (!next) return;
  const index = doorScenePlacements.value.findIndex((placement) => String(placement.id) === String(next.id));
  if (index >= 0) {
    doorScenePlacements.value = doorScenePlacements.value.map((placement, placementIndex) =>
      placementIndex === index ? { ...placement, ...next } : placement
    );
    return;
  }
  doorScenePlacements.value = [...doorScenePlacements.value, next];
}

function getDoorScenePlacement(id) {
  const key = String(id || "").trim();
  if (!key) return null;
  return doorScenePlacements.value.find((placement) => String(placement.id) === key) || null;
}

function persistCurrentActiveDoorAssetPlacement() {
  const activeId = String(activeDoorAssetId.value || "").trim();
  if (!activeId) return;
  const current = getDoorScenePlacement(activeId);
  if (!current) return;
  upsertDoorScenePlacement({
    ...current,
    ...getCurrentEditorModelPlacement(),
  });
}

function syncActiveDoorAssetToEditor(item, placement = null) {
  const target = normalizeDoorScenePlacement(item);
  if (!target) return false;
  const nextPlacement = normalizeDoorScenePlacement({
    ...target,
    ...(placement || {}),
  }) || target;
  const geometry = buildDoorAssetPlanGeometry(target.modelBoundsMm);
  const worldLines = localDesignToWorld(geometry.lines, nextPlacement, "lines");
  const worldOutline = localDesignToWorld(geometry.outline, nextPlacement, "points");
  if (!editorRef.value?.setModel2dLines) return false;
  editorRef.value.setModel2dLines(worldLines, {
    outline: worldOutline,
    outlineColor: target.outlineColor,
    designId: target.id,
    designCode: null,
    designTitle: target.title,
    instanceCode: null,
    displayName: target.title,
    offsetXmm: nextPlacement.x,
    offsetYmm: nextPlacement.y,
    rotationRad: nextPlacement.rotRad,
    mirrorX: 1,
  }, false);
  editorRef.value?.selectModelOutline?.();
  activeCabinetDesignId.value = null;
  stageCabinetPlaceholderBoxes.value = [];
  activeDoorAssetId.value = target.id;
  activeStageOrderDesignSelected.value = false;
  selectedStageOrderDesignIds.value = [];
  selectedStageDoorAssetIds.value = [target.id];
  upsertDoorScenePlacement(nextPlacement);
  syncQuickStateFromEditor();
  return true;
}

function restoreActiveDoorAssetToEditor(item, placement = null) {
  const target = normalizeDoorScenePlacement(item);
  if (!target) return false;
  persistCurrentActiveOrderDesignPlacement();
  persistCurrentActiveDoorAssetPlacement();
  if (syncActiveDoorAssetToEditor(target, placement)) return true;
  const nextPlacement = normalizeDoorScenePlacement({
    ...target,
    ...(placement || {}),
  }) || target;
  const geometry = buildDoorAssetPlanGeometry(target.modelBoundsMm);
  const worldLines = localDesignToWorld(geometry.lines, nextPlacement, "lines");
  const worldOutline = localDesignToWorld(geometry.outline, nextPlacement, "points");
  const full = editorRef.value?.getState?.();
  const nextSnapshot = {
    ...full,
    model2dSnap: {
      ...(full?.model2dSnap || {}),
      lines: worldLines,
      outline: worldOutline,
      outlineColor: target.outlineColor,
      designId: target.id,
      designCode: null,
      designTitle: target.title,
      instanceCode: null,
      displayName: target.title,
      offsetXmm: nextPlacement.x,
      offsetYmm: nextPlacement.y,
      rotationRad: nextPlacement.rotRad,
      mirrorX: 1,
    },
  };
  let restored = false;
  if (editorRef.value?.restoreSnapshot) {
    restored = !!editorRef.value.restoreSnapshot(nextSnapshot);
  } else if (editorRef.value?.setModel2dLines) {
    editorRef.value.setModel2dLines(worldLines, {
      outline: worldOutline,
      outlineColor: target.outlineColor,
      designId: target.id,
      designTitle: target.title,
      displayName: target.title,
      offsetXmm: nextPlacement.x,
      offsetYmm: nextPlacement.y,
      rotationRad: nextPlacement.rotRad,
      mirrorX: 1,
    }, false);
    restored = true;
  }
  if (!restored) return false;
  editorRef.value?.selectModelOutline?.();
  activeCabinetDesignId.value = null;
  stageCabinetPlaceholderBoxes.value = [];
  activeDoorAssetId.value = target.id;
  activeStageOrderDesignSelected.value = false;
  selectedStageOrderDesignIds.value = [];
  selectedStageDoorAssetIds.value = [target.id];
  upsertDoorScenePlacement(nextPlacement);
  syncQuickStateFromEditor();
  return true;
}

function getOrderDesignPlacementForId(orderDesignId) {
  const key = String(orderDesignId || "").trim();
  if (!key) return null;
  if (String(activeCabinetDesignId.value || "") === key) {
    return {
      orderDesignId: key,
      ...getCurrentEditorModelPlacement(),
    };
  }
  return getOrderDesignPlacement(key);
}

function computeOrderDesignBounds(boxes, placement = null) {
  const bounds = getCabinetBoxesBounds(boxes);
  if (!bounds) return null;
  const outline = localDesignToWorld([
    { x: bounds.minX, y: bounds.minY },
    { x: bounds.maxX, y: bounds.minY },
    { x: bounds.maxX, y: bounds.maxY },
    { x: bounds.minX, y: bounds.maxY },
  ], placement, "points");
  if (!outline.length) return null;
  const xs = outline.map((pt) => Number(pt.x) || 0);
  const ys = outline.map((pt) => Number(pt.y) || 0);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return {
    minX,
    maxX,
    minY,
    maxY,
    centerX: (minX + maxX) * 0.5,
    centerY: (minY + maxY) * 0.5,
  };
}

function getSingleSelectedOrderDesignContext() {
  const summary = getEditorSelectionSummary();
  if (!summary.isSingleDesign || summary.isMixed || summary.totalCount !== 1) return null;
  const designId = String(summary.designIds[0] || activeCabinetDesignId.value || "").trim();
  if (!designId) return null;
  const design = orderDesignCatalog.value.find((item) => String(item.id) === designId) || getSelectedOrderDesignSourceLocal() || null;
  if (!design?.viewer_boxes?.length) return null;
  const placement = getOrderDesignPlacementForId(designId);
  if (!placement) return null;
  const bounds = computeOrderDesignBounds(design.viewer_boxes, placement);
  if (!bounds) return null;
  return { designId, design, placement, bounds, summary };
}

function persistCurrentActiveOrderDesignPlacement() {
  const activeId = String(activeCabinetDesignId.value || "").trim();
  if (!activeId) return;
  upsertOrderDesignPlacement({
    orderDesignId: activeId,
    ...getCurrentEditorModelPlacement(),
  });
}

function restoreActiveOrderDesignToEditor(item, placement = null) {
  const target = normalizeOrderDesignRecord(item);
  if (!target?.viewer_boxes?.length) return false;
  persistCurrentActiveOrderDesignPlacement();
  const nextPlacement = normalizeOrderDesignPlacement({
    orderDesignId: target.id,
    ...(placement || {}),
  }) || { orderDesignId: target.id, x: 0, y: 0, rotRad: 0, mirrorX: 1 };
  const geometry = getCachedOrderDesignGeometry(target);
  const worldLines = localDesignToWorld(geometry.lines, nextPlacement, "lines");
  const worldOutline = localDesignToWorld(geometry.outline, nextPlacement, "points");
  const full = editorRef.value?.getState?.();
  const nextSnapshot = {
    ...full,
    model2dSnap: {
      ...(full.model2dSnap || {}),
      lines: worldLines,
      outline: worldOutline,
      outlineColor: normalizeHexColor(target.design_outline_color),
      designId: target.id,
      designCode: String(target.design_code || "").trim() || null,
      designTitle: String(target.design_title || "").trim() || null,
      instanceCode: String(target.instance_code || "").trim() || null,
      displayName:
        String(target.design_title || "").trim() ||
        String(target.instance_code || "").trim() ||
        String(target.id || "").trim() ||
        null,
      offsetXmm: nextPlacement.x,
      offsetYmm: nextPlacement.y,
      rotationRad: nextPlacement.rotRad,
      mirrorX: 1,
    },
  };
  let restored = false;
  _orderDesignPlacementSyncPaused = true;
  try {
    activeCabinetDesignId.value = target.id;
    if (full && editorRef.value?.restoreSnapshot) {
      restored = !!editorRef.value.restoreSnapshot(nextSnapshot);
    }
    if (!restored && editorRef.value?.setModel2dLines) {
      editorRef.value.setModel2dLines(worldLines, {
        outlineColor: normalizeHexColor(target.design_outline_color),
        designId: target.id,
        designCode: String(target.design_code || "").trim() || null,
        designTitle: String(target.design_title || "").trim() || null,
        instanceCode: String(target.instance_code || "").trim() || null,
        displayName:
          String(target.design_title || "").trim() ||
          String(target.instance_code || "").trim() ||
          String(target.id || "").trim() ||
          null,
      }, false);
      model2dTransformRef.value = {
        x: nextPlacement.x,
        y: nextPlacement.y,
        rotRad: nextPlacement.rotRad,
        mirrorX: 1,
      };
      restored = true;
    }
  } finally {
    _orderDesignPlacementSyncPaused = false;
  }
  if (restored) {
    upsertOrderDesignPlacement(nextPlacement);
    editorRef.value?.selectModelOutline?.();
  }
  return restored;
}

async function deleteOrderDesignSilentlyById(orderDesignId) {
  const key = String(orderDesignId || "").trim();
  if (!key) return;
  const res = await fetch(`/api/order-designs/${encodeURIComponent(key)}`, { method: "DELETE" });
  if (!res.ok) throw new Error(await readApiErrorMessage(res, "حذف طرح سفارش انجام نشد."));
  orderDesignCatalog.value = orderDesignCatalog.value.filter((item) => String(item.id) !== key);
  removeOrderDesignPlacement(key);
}

function buildOrderDesignDeleteConfirmMessage(targets, options = {}) {
  const count = Array.isArray(targets) ? targets.length : 0;
  const summary = options.selectionSummary || null;
  const lines = [];
  if (count > 0) {
    if (count === 1) {
      const target = targets[0] || null;
      lines.push(`نمونه «${target?.instance_code || target?.design_title || "طرح"}» حذف شود؟`);
    } else {
      lines.push(`${count} طرح سفارش انتخاب‌شده حذف شوند؟`);
    }
    lines.push("این حذف از صفحه و دیتابیس انجام می‌شود.");
  }
  if (summary?.wallCount > 0) lines.push(summary.wallCount === 1 ? "۱ دیوار هم حذف می‌شود." : `${summary.wallCount} دیوار هم حذف می‌شوند.`);
  if (summary?.columnCount > 0) lines.push(summary.columnCount === 1 ? "۱ ستون هم حذف می‌شود." : `${summary.columnCount} ستون هم حذف می‌شوند.`);
  if (summary?.beamCount > 0) lines.push(summary.beamCount === 1 ? "۱ تیر هم حذف می‌شود." : `${summary.beamCount} تیر هم حذف می‌شوند.`);
  if (summary?.hiddenCount > 0) lines.push(summary.hiddenCount === 1 ? "۱ خط مخفی هم حذف می‌شود." : `${summary.hiddenCount} خط مخفی هم حذف می‌شوند.`);
  if (summary?.dimensionCount > 0) lines.push(summary.dimensionCount === 1 ? "۱ اندازه هم حذف می‌شود." : `${summary.dimensionCount} اندازه هم حذف می‌شوند.`);
  return lines.join("\n");
}

async function deleteOrderDesignsByIds(designIds, options = {}) {
  const uniqueIds = [...new Set(normalizeSelectionIds(designIds))];
  if (!uniqueIds.length) return false;
  const targets = uniqueIds
    .map((id) => orderDesignCatalog.value.find((item) => String(item.id) === String(id)) || null)
    .filter(Boolean);
  if (!targets.length) return false;
  if (!options.skipConfirm) {
    const ok = await showConfirm(buildOrderDesignDeleteConfirmMessage(targets, options), {
      title: uniqueIds.length > 1 ? "حذف گروهی طرح سفارش" : "حذف طرح سفارش",
      confirmText: "حذف",
      cancelText: "انصراف",
    });
    if (!ok) return false;
  }

  for (const id of uniqueIds) {
    const res = await fetch(`/api/order-designs/${encodeURIComponent(id)}`, { method: "DELETE" });
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "حذف طرح سفارش انجام نشد."));
  }

  const deletedIdSet = new Set(uniqueIds);
  orderDesignCatalog.value = orderDesignCatalog.value.filter((item) => !deletedIdSet.has(String(item.id)));
  orderDesignPlacements.value = orderDesignPlacements.value.filter((placement) => !deletedIdSet.has(String(placement.orderDesignId)));
  selectedStageOrderDesignIds.value = selectedStageOrderDesignIds.value.filter((id) => !deletedIdSet.has(String(id)));

  const activeDeleted = deletedIdSet.has(String(activeCabinetDesignId.value || ""));
  if (activeDeleted) {
    stageCabinetPlaceholderBoxes.value = [];
    activeCabinetDesignId.value = null;
    activeStageOrderDesignSelected.value = false;
    editorRef.value?.clearModel2dLines?.(false);
  }

  await loadOrderDesignCatalog(true);
  await saveActiveOrderDrawing().catch(() => {});

  if (options.successMessage) {
    showAlert(options.successMessage, { title: "حذف طرح سفارش" });
  }
  return true;
}

async function restoreOrderDesignById(orderDesignId) {
  const key = String(orderDesignId || "").trim();
  if (!key) return null;
  const res = await fetch(`/api/order-designs/${encodeURIComponent(key)}/restore`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await readApiErrorMessage(res, "بازگردانی طرح سفارش انجام نشد."));
  return normalizeOrderDesignRecord(await res.json());
}

async function duplicateOrderDesignById(orderDesignId) {
  const key = String(orderDesignId || "").trim();
  if (!key) return null;
  const res = await fetch(`/api/order-designs/${encodeURIComponent(key)}/duplicate`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await readApiErrorMessage(res, "کپی طرح سفارش انجام نشد."));
  return normalizeOrderDesignRecord(await res.json());
}

function cloneOrderDesignHistoryRecord(item) {
  return normalizeOrderDesignRecord(item);
}

function buildOrderDesignHistoryRestorePayload(item) {
  const target = normalizeOrderDesignRecord(item);
  if (!target?.id) return null;
  return {
    design_title: String(target.design_title || "").trim(),
    instance_code: String(target.instance_code || "").trim(),
    sort_order: Number(target.sort_order) || 0,
    status: String(target.status || "draft").trim() || "draft",
    order_attr_values: { ...(target.order_attr_values || {}) },
    interior_instances: (Array.isArray(target.interior_instances) ? target.interior_instances : [])
      .map((instance) => normalizeInteriorInstanceRecord(instance))
      .filter(Boolean)
      .map((instance) => ({
        id: String(instance.id),
        internal_part_group_id: String(instance.internal_part_group_id || ""),
        instance_code: String(instance.instance_code || "").trim(),
        ui_order: Number(instance.ui_order) || 0,
        placement_z: Number(instance.placement_z) || 0,
        param_values: { ...(instance.param_values || {}) },
        status: String(instance.status || "draft").trim() || "draft",
      })),
  };
}

async function restoreOrderDesignSnapshotRecord(item) {
  const target = normalizeOrderDesignRecord(item);
  if (!target?.id) return null;
  const payload = buildOrderDesignHistoryRestorePayload(target);
  if (!payload) return null;
  const res = await fetch(`/api/order-designs/${encodeURIComponent(String(target.id))}/history-restore`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) throw new Error(await readApiErrorMessage(res, "بازگردانی وضعیت طرح سفارش انجام نشد."));
  return normalizeOrderDesignRecord(await res.json());
}

function captureOrderDesignHistoryState() {
  return {
    orderId: String(activeOrder.value?.id || "").trim() || null,
    orderDesignIds: orderDesignCatalog.value.map((item) => String(item.id || "").trim()).filter(Boolean),
    orderDesigns: orderDesignCatalog.value.map((item) => cloneOrderDesignHistoryRecord(item)).filter(Boolean),
    orderDesignPlacements: orderDesignPlacements.value.map((item) => ({ ...(item || {}) })),
    activeCabinetDesignId: String(activeCabinetDesignId.value || "").trim() || null,
    selectedStageOrderDesignIds: selectedOrderDesignIds.value.map((id) => String(id || "").trim()).filter(Boolean),
    activeStageOrderDesignSelected: !!activeStageOrderDesignSelected.value,
    stageCabinetPlaceholderBoxes: (Array.isArray(stageCabinetPlaceholderBoxes.value) ? stageCabinetPlaceholderBoxes.value : []).map((box) => ({ ...(box || {}) })),
  };
}

function reflectPointAcrossAxis(point, axisStart, axisEnd) {
  const px = Number(point?.x) || 0;
  const py = Number(point?.y) || 0;
  const ax = Number(axisStart?.x) || 0;
  const ay = Number(axisStart?.y) || 0;
  const bx = Number(axisEnd?.x) || 0;
  const by = Number(axisEnd?.y) || 0;
  const dx = bx - ax;
  const dy = by - ay;
  const lenSq = dx * dx + dy * dy;
  if (lenSq <= 1e-9) return { x: px, y: py };
  const t = ((px - ax) * dx + (py - ay) * dy) / lenSq;
  const projX = ax + t * dx;
  const projY = ay + t * dy;
  return { x: projX * 2 - px, y: projY * 2 - py };
}

function upsertOrderDesignCatalogItem(item) {
  const normalized = normalizeOrderDesignRecord(item);
  if (!normalized?.id) return null;
  const nextItems = orderDesignCatalog.value.filter((row) => String(row.id) !== String(normalized.id));
  nextItems.push(normalized);
  orderDesignCatalog.value = sortOrderDesignCatalogRecords(nextItems);
  return normalized;
}

async function restoreOrderDesignHistoryState(snapshot = null) {
  const targetOrderId = String(snapshot?.orderId || "").trim();
  const currentOrderId = String(activeOrder.value?.id || "").trim();
  if (!targetOrderId || !currentOrderId || targetOrderId !== currentOrderId) return;

  const targetDesigns = Array.isArray(snapshot?.orderDesigns)
    ? snapshot.orderDesigns.map((item) => cloneOrderDesignHistoryRecord(item)).filter(Boolean)
    : [];
  await loadOrderDesignCatalog(true);
  const currentIds = orderDesignCatalog.value.map((item) => String(item.id || "").trim()).filter(Boolean);
  const currentIdSet = new Set(currentIds);
  const targetIds = targetDesigns.length
    ? targetDesigns.map((item) => String(item.id || "").trim()).filter((id) => currentIdSet.has(id))
    : [...new Set(normalizeSelectionIds(snapshot?.orderDesignIds))].filter((id) => currentIdSet.has(id));
  const targetIdSet = new Set(targetIds);

  if (targetDesigns.length) {
    const restoredItems = [];
    for (const design of sortOrderDesignCatalogRecords(targetDesigns.filter((item) => currentIdSet.has(String(item.id || "").trim())))) {
      const restored = await restoreOrderDesignSnapshotRecord(design);
      if (restored) restoredItems.push(restored);
    }
    if (restoredItems.length) {
      const byId = new Map(orderDesignCatalog.value.map((item) => [String(item.id), item]));
      for (const item of restoredItems) {
        byId.set(String(item.id), item);
      }
      orderDesignCatalog.value = sortOrderDesignCatalogRecords([...byId.values()]);
    }
  }
  const nextPlacements = Array.isArray(snapshot?.orderDesignPlacements)
    ? snapshot.orderDesignPlacements
        .map(normalizeOrderDesignPlacement)
        .filter((item) => item && targetIdSet.has(String(item.orderDesignId || "")))
    : [];
  orderDesignPlacements.value = nextPlacements;
  const nextActiveDesignId = targetIdSet.has(String(snapshot?.activeCabinetDesignId || "").trim())
    ? String(snapshot?.activeCabinetDesignId || "").trim()
    : null;
  activeCabinetDesignId.value = nextActiveDesignId;
  activeStageOrderDesignSelected.value = !!snapshot?.activeStageOrderDesignSelected && !!nextActiveDesignId;
  selectedStageOrderDesignIds.value = Array.isArray(snapshot?.selectedStageOrderDesignIds)
    ? snapshot.selectedStageOrderDesignIds
        .map((id) => String(id || "").trim())
        .filter((id) => targetIdSet.has(id))
    : [];
  stageCabinetPlaceholderBoxes.value = Array.isArray(snapshot?.stageCabinetPlaceholderBoxes)
    ? snapshot.stageCabinetPlaceholderBoxes.map((box) => normalizeCabinetBox(box)).filter(Boolean)
    : [];
  await nextTick();
  if (!reconcileActiveOrderDesignSelection()) {
    stageCabinetPlaceholderBoxes.value = [];
    activeCabinetDesignId.value = null;
    activeStageOrderDesignSelected.value = false;
    selectedStageOrderDesignIds.value = [];
    editorRef.value?.clearModel2dLines?.(false);
  }
}

async function handleStageOrderDesignDuplicateRequest(payload = null) {
  const activeId = payload?.activeDesignSelected ? String(activeCabinetDesignId.value || "").trim() : "";
  const passiveIds = normalizeSelectionIds(payload?.passiveDesignIds);
  const sourceIds = [...new Set([activeId, ...passiveIds].filter(Boolean))];
  const delta = {
    x: Number.isFinite(Number(payload?.delta?.x)) ? Number(payload.delta.x) : 0,
    y: Number.isFinite(Number(payload?.delta?.y)) ? Number(payload.delta.y) : 0,
    rotRad: 0,
    mirrorX: 1,
  };
  if (!sourceIds.length) return { createdIds: [] };

  persistCurrentActiveOrderDesignPlacement();
  const createdItems = [];
  const sourceItems = sourceIds
    .map((id) => orderDesignCatalog.value.find((item) => String(item.id) === String(id)) || null)
    .filter(Boolean);
  const shouldToggleStageLoading = !cabinetDesignDropLoading.value;
  if (shouldToggleStageLoading) {
    cabinetDesignDropLoadingMode.value = "duplicate";
    cabinetDesignDropLoading.value = true;
    cabinetDesignDropLoadingTitle.value =
      sourceItems.length > 1
        ? `${sourceItems.length} طرح سفارش`
        : String(sourceItems[0]?.design_title || sourceItems[0]?.instance_code || "").trim();
  }
  try {
    for (const sourceId of sourceIds) {
      const created = await duplicateOrderDesignById(sourceId);
      if (!created?.id) continue;
      createdItems.push(created);
      const sourcePlacement = getOrderDesignPlacementForId(sourceId) || { x: 0, y: 0, rotRad: 0, mirrorX: 1 };
      upsertOrderDesignPlacement({
        orderDesignId: created.id,
        x: (Number(sourcePlacement.x) || 0) + delta.x,
        y: (Number(sourcePlacement.y) || 0) + delta.y,
        rotRad: Number(sourcePlacement.rotRad) || 0,
        mirrorX: Number(sourcePlacement.mirrorX) === -1 ? -1 : 1,
      });
    }
    if (createdItems.length) {
      const byId = new Map(orderDesignCatalog.value.map((item) => [String(item.id), item]));
      for (const item of createdItems) byId.set(String(item.id), item);
      orderDesignCatalog.value = sortOrderDesignCatalogRecords([...byId.values()]);
      await nextTick();
      await saveActiveOrderDrawing();
    }
    return {
      createdIds: createdItems.map((item) => String(item.id || "").trim()).filter(Boolean),
    };
  } catch (error) {
    await loadOrderDesignCatalog(true).catch(() => {});
    throw error;
  } finally {
    if (shouldToggleStageLoading) {
      cabinetDesignDropLoading.value = false;
      cabinetDesignDropLoadingTitle.value = "";
      cabinetDesignDropLoadingMode.value = "add";
    }
  }
}

async function handleStageOrderDesignDeleteRequest(payload = null) {
  const activeId = payload?.activeDesignSelected ? String(activeCabinetDesignId.value || "").trim() : "";
  const passiveIds = normalizeSelectionIds(payload?.passiveDesignIds);
  const designIds = [...new Set([activeId, ...passiveIds].filter(Boolean))];
  if (!designIds.length) return false;
  try {
    return await deleteOrderDesignsByIds(designIds, {
      skipConfirm: true,
      selectionSummary: payload?.selectionSummary || null,
      successMessage: null,
    });
  } catch (error) {
    showAlert(error?.message || "حذف طرح سفارش انجام نشد.", { title: "خطا" });
    return false;
  }
}

async function rollbackTransientCabinetDesignDrag(dragState) {
  const transientId = String(dragState?.createdOrderDesignId || "").trim();
  if (!transientId) return;
  try {
    await deleteOrderDesignSilentlyById(transientId);
  } catch (error) {
    await loadOrderDesignCatalog(true).catch(() => {});
    showAlert(error?.message || "برگرداندن طرح موقت انجام نشد.", { title: "خطا" });
  }

  const previousId = String(dragState?.previousActiveOrderDesignId || "").trim();
  const previousPlacement = dragState?.previousActivePlacement || null;
  const previousItem = previousId
    ? orderDesignCatalog.value.find((item) => String(item.id) === previousId) || null
    : null;

  if (previousItem?.viewer_boxes?.length) {
    stageCabinetPlaceholderBoxes.value = previousItem.viewer_boxes.map(normalizeCabinetBox);
    restoreActiveOrderDesignToEditor(previousItem, previousPlacement || getOrderDesignPlacement(previousId));
  } else {
    stageCabinetPlaceholderBoxes.value = [];
    activeCabinetDesignId.value = null;
    activeStageOrderDesignSelected.value = false;
    selectedStageOrderDesignIds.value = [];
    editorRef.value?.clearModel2dLines?.(false);
  }
  syncQuickStateFromEditor();
}

function finishPresetDragSession() {
  presetDrag.value = createEmptyPresetDragState();
  window.removeEventListener("pointermove", onPresetPointerMove);
  window.removeEventListener("pointerup", onPresetPointerUp);
  enable2dInput();
}

async function ensureCabinetDesignDragPlacement(clientX, clientY) {
  const drag = presetDrag.value;
  if (!drag.active || drag.type !== "cabinetDesign" || drag.dragBootstrapping || drag.createdOrderDesignId) return false;
  const sessionId = drag.sessionId;
  const previousActiveOrderDesignId = String(activeCabinetDesignId.value || "").trim();
  const previousActivePlacement = previousActiveOrderDesignId
    ? { ...(getOrderDesignPlacement(previousActiveOrderDesignId) || getCurrentEditorModelPlacement()) }
    : null;
  presetDrag.value = {
    ...drag,
    dragBootstrapping: true,
    previousActiveOrderDesignId,
    previousActivePlacement,
  };
  cabinetDesignDropLoadingMode.value = "add";
  cabinetDesignDropLoading.value = true;
  cabinetDesignDropLoadingTitle.value = String(drag.design?.design_title || "").trim();
  try {
    const createdOrderDesign = await createOrderDesignFromSource(drag.design);
    const currentDrag = presetDrag.value;
    if (!currentDrag.active || currentDrag.sessionId !== sessionId || currentDrag.type !== "cabinetDesign") {
      if (createdOrderDesign?.id) {
        await deleteOrderDesignSilentlyById(createdOrderDesign.id).catch(() => loadOrderDesignCatalog(true).catch(() => {}));
      }
      return false;
    }
    const latestClientX = Number.isFinite(Number(presetDrag.value.clientX)) ? Number(presetDrag.value.clientX) : clientX;
    const latestClientY = Number.isFinite(Number(presetDrag.value.clientY)) ? Number(presetDrag.value.clientY) : clientY;
    const localBoxes = (createdOrderDesign?.viewer_boxes || []).map(normalizeCabinetBox);
    const dropWorld = clientPointToStageWorld(latestClientX, latestClientY);
    const placement = normalizeOrderDesignPlacement({
      orderDesignId: createdOrderDesign?.id || "",
      x: Number(dropWorld?.x) || 0,
      y: Number(dropWorld?.y) || 0,
      rotRad: 0,
    }) || { orderDesignId: createdOrderDesign?.id || "", x: 0, y: 0, rotRad: 0, mirrorX: 1 };
    stageCabinetPlaceholderBoxes.value = localBoxes;
    if (createdOrderDesign?.id) {
      upsertOrderDesignPlacement(placement);
    }
    const restored = restoreActiveOrderDesignToEditor(createdOrderDesign, placement);
    await nextTick();
    presetDrag.value = {
      ...presetDrag.value,
      createdOrderDesignId: String(createdOrderDesign?.id || ""),
      dragBootstrapping: false,
      dragStarted: restored,
      previousActiveOrderDesignId,
      previousActivePlacement,
    };
    syncQuickStateFromEditor();
    if (presetDrag.value.releasePending) {
      const releaseX = Number.isFinite(Number(presetDrag.value.releaseClientX)) ? Number(presetDrag.value.releaseClientX) : latestClientX;
      const releaseY = Number.isFinite(Number(presetDrag.value.releaseClientY)) ? Number(presetDrag.value.releaseClientY) : latestClientY;
      const stageRect = stageEl.value?.getBoundingClientRect();
      const inStage = !!stageRect && releaseX >= stageRect.left && releaseX <= stageRect.right
        && releaseY >= stageRect.top && releaseY <= stageRect.bottom;
      const commit = inStage
        && Math.hypot(releaseX - (presetDrag.value.startX || releaseX), releaseY - (presetDrag.value.startY || releaseY)) >= PRESET_PREVIEW_MIN_DRAG_PX
        && presetDrag.value.enteredStage
        && presetDrag.value.leftPanel;
      if (commit) {
        enable2dInput();
        const dragStarted = !!editorRef.value?.beginModelDragAtClient?.(releaseX, releaseY);
        if (dragStarted) {
          editorRef.value?.updateModelDragAtClient?.(releaseX, releaseY);
        }
        syncQuickStateFromEditor();
      } else {
        await rollbackTransientCabinetDesignDrag({ ...presetDrag.value });
      }
      finishPresetDragSession();
    }
    return true;
  } catch (error) {
    if (presetDrag.value.active && presetDrag.value.sessionId === sessionId) {
      showAlert(error?.message || "افزودن طرح به سفارش انجام نشد.", { title: "خطا" });
      presetDrag.value = {
        ...presetDrag.value,
        dragBootstrapping: false,
      };
    }
    return false;
  } finally {
    cabinetDesignDropLoading.value = false;
    cabinetDesignDropLoadingTitle.value = "";
    cabinetDesignDropLoadingMode.value = "add";
  }
}

function placeOrderDesignOnStage(item) {
  const target = normalizeOrderDesignRecord(item);
  if (!target?.viewer_boxes?.length) return;
  stageCabinetPlaceholderBoxes.value = target.viewer_boxes.map(normalizeCabinetBox);
  restoreActiveOrderDesignToEditor(target, getOrderDesignPlacement(target.id));
  saveActiveOrderDrawing().catch(() => {});
}

function activateOrderDesignFromStage(orderDesignId) {
  const key = String(orderDesignId || "").trim();
  if (!key) return;
  const target = orderDesignCatalog.value.find((item) => String(item.id) === key);
  if (!target?.viewer_boxes?.length) return;
  const alreadyActive = String(activeCabinetDesignId.value || "") === key;
  stageCabinetPlaceholderBoxes.value = target.viewer_boxes.map(normalizeCabinetBox);
  const restored = restoreActiveOrderDesignToEditor(target, getOrderDesignPlacement(target.id));
  if (!restored && alreadyActive) {
    editorRef.value?.selectModelOutline?.();
  }
  saveActiveOrderDrawing().catch(() => {});
}

function activatePassiveStageModel(modelId) {
  const key = String(modelId || "").trim();
  if (!key) return;
  const doorItem = doorScenePlacements.value.find((item) => String(item.id) === key) || null;
  if (doorItem) {
    restoreActiveDoorAssetToEditor(doorItem, getDoorScenePlacement(key));
    return;
  }
  activateOrderDesignFromStage(key);
}

passiveModelSelectionHandlerRef.value = activatePassiveStageModel;
activeModelDeleteHandlerRef.value = deleteActiveOrderDesignFromStage;
orderDesignDeleteHandlerRef.value = handleStageOrderDesignDeleteRequest;
orderDesignDuplicateHandlerRef.value = handleStageOrderDesignDuplicateRequest;
orderDesignMirrorHandlerRef.value = null;
externalHistoryCaptureHandlerRef.value = captureOrderDesignHistoryState;
externalHistoryRestoreHandlerRef.value = restoreOrderDesignHistoryState;

function clearStageOrderDesignPlacement({ persist = true } = {}) {
  const hadStageDesign =
    !!String(activeCabinetDesignId.value || "").trim() ||
    (Array.isArray(stageCabinetPlaceholderBoxes.value) && stageCabinetPlaceholderBoxes.value.length > 0);
  if (!hadStageDesign) return;
  removeOrderDesignPlacement(activeCabinetDesignId.value);
  stageCabinetPlaceholderBoxes.value = [];
  activeCabinetDesignId.value = null;
  activeStageOrderDesignSelected.value = false;
  selectedStageOrderDesignIds.value = [];
  if (persist && activeOrder.value?.id) {
    saveActiveOrderDrawing().catch(() => {});
  }
}

async function openSubCategoryDesignEditor(item = null) {
  const draft = item
    ? syncSubCategoryDesignDraftSubCategoryFields({
        id: item.id,
        admin_id: item.admin_id,
        sub_category_id: item.sub_category_id,
        temp_id: item.temp_id,
        cat_id: item.cat_id,
        sub_cat_id: item.sub_cat_id,
        sub_cat_title: item.sub_cat_title,
        design_id: item.design_id,
        design_title: item.design_title,
        code: item.code,
        sort_order: item.sort_order,
        is_system: item.is_system,
        parts: Array.isArray(item.parts) ? item.parts.map((part) => ({
          part_formula_id: Number(part.part_formula_id),
          enabled: part.enabled !== false,
          ui_order: Number(part.ui_order) || 0,
        })) : [],
        interior_instances: Array.isArray(item.interior_instances) ? item.interior_instances.map(normalizeInteriorInstanceRecord).filter(Boolean) : [],
      })
    : buildNewSubCategoryDesignDraft();
  subCategoryDesignEditorDraft.value = draft;
  subCategoryDesignEditorPreview.value = null;
  subCategoryDesignPreviewError.value = "";
  subCategoryDesignEditorOpen.value = true;
  await refreshSubCategoryDesignPreview();
}

function openInternalPartGroupEditor(item = null) {
  internalPartGroupEditorDraft.value = item
    ? {
        id: item.id,
        admin_id: item.admin_id,
        group_id: item.group_id,
        group_title: item.group_title,
        code: item.code,
        line_color: normalizeHexColor(item.line_color, DEFAULT_INTERIOR_LINE_COLOR),
        sort_order: item.sort_order,
        is_system: item.is_system,
        parts: Array.isArray(item.parts) ? item.parts.map((part) => ({
          part_formula_id: Number(part.part_formula_id),
          enabled: part.enabled !== false,
          ui_order: Number(part.ui_order) || 0,
        })) : [],
        param_groups: Array.isArray(item.param_groups) ? item.param_groups.map((group) => ({
          param_group_id: Number(group.param_group_id),
          param_group_code: String(group.param_group_code || "").trim(),
          param_group_title: String(group.param_group_title || "").trim(),
          param_group_icon_path: normalizeIconFileName(group.param_group_icon_path) || "",
          enabled: group.enabled !== false,
          ui_order: Number(group.ui_order) || 0,
        })) : [],
        param_defaults: Object.fromEntries(
          Object.entries(item.param_defaults || {}).map(([key, value]) => [String(key || "").trim(), value == null ? "" : String(value)])
        ),
        param_overrides: Object.fromEntries(
          Object.entries(item.param_overrides || {}).map(([key, override]) => [String(key || "").trim(), {
            display_title: String(override?.display_title || "").trim(),
            description_text: String(override?.description_text || "").trim(),
            icon_path: normalizeIconFileName(override?.icon_path) || "",
            input_mode: override?.input_mode === "binary" ? "binary" : "value",
            binary_off_label: String(override?.binary_off_label || "").trim() || "0",
            binary_on_label: String(override?.binary_on_label || "").trim() || "1",
            binary_off_icon_path: normalizeIconFileName(override?.binary_off_icon_path) || "",
            binary_on_icon_path: normalizeIconFileName(override?.binary_on_icon_path) || "",
          }])
        ),
        controller_type: normalizeInternalPartGroupControllerType(item.controller_type),
        controller_bindings: normalizeInternalPartGroupControllerBindings(item.controller_type, item.controller_bindings),
      }
    : buildNewInternalPartGroupDraft();
  ensureInternalPartGroupParamDefaults(internalPartGroupEditorDraft.value);
  ensureInternalPartGroupControllerConfig(internalPartGroupEditorDraft.value);
  internalPartGroupParamGroupsOpen.value = false;
  internalPartGroupEditorOpen.value = true;
}

function openInternalPartGroupDefaultsEditor(item) {
  const row = findEditableInternalPartGroupById(item?.id);
  if (!row?.id) return;
  ensureInternalPartGroupParamDefaults(row);
  const selectedColumns = getInternalPartGroupSelectedParamColumns(row);
  if (!selectedColumns.length) {
    showAlert("برای این گروه داخلی هنوز گروه پارامتری انتخاب نشده است.", { title: "پیش‌فرض گروه داخلی" });
    return;
  }
  internalPartGroupDefaultsEditorRowId.value = row.id;
  internalPartGroupDefaultsValues.value = Object.fromEntries(
    selectedColumns.map((column) => {
      const override = row.param_overrides?.[column.key] || {};
      const value = String(row.param_defaults?.[column.key] ?? "").trim();
      return [
        column.key,
        override.input_mode === "binary" ? (value === "1" ? "1" : "0") : value,
      ];
    })
  );
  internalPartGroupDefaultsEditorGroups.value = buildInternalPartGroupDefaultsGroups(row);
  internalPartGroupDefaultsActiveGroupId.value = String(row.param_groups?.find((group) => group?.enabled !== false)?.param_group_id || "");
  if (!internalPartGroupDefaultsActiveGroupId.value) {
    internalPartGroupDefaultsActiveGroupId.value = internalPartGroupDefaultsEditorGroups.value[0]?.id || "";
  }
  internalPartGroupDefaultsEditorOpen.value = true;
}

function selectInteriorInstanceEditorGroup(groupId) {
  interiorInstanceEditorActiveGroupId.value = String(groupId || "");
}

function setInteriorInstanceBinaryValue(paramCode, value) {
  const key = String(paramCode || "").trim();
  if (!key || !interiorInstanceEditorDraft.value) return;
  interiorInstanceEditorDraft.value.param_values = {
    ...(interiorInstanceEditorDraft.value.param_values || {}),
    [key]: String(value) === "1" ? "1" : "0",
  };
}

function syncInteriorInstanceInDraft(instance) {
  const draft = subCategoryDesignEditorDraft.value;
  if (!draft) return;
  const normalized = normalizeInteriorInstanceRecord(instance);
  if (!normalized) return;
  const existingIndex = (draft.interior_instances || []).findIndex((row) => String(row.id) === String(normalized.id));
  if (existingIndex === -1) {
    draft.interior_instances = [...(draft.interior_instances || []), normalized];
    return;
  }
  draft.interior_instances = (draft.interior_instances || []).map((row, index) => index === existingIndex ? normalized : row);
}

function syncOpenSubCategoryDesignDraftToCollection() {
  const draft = subCategoryDesignEditorDraft.value;
  if (!draft?.id) return;
  editableSubCategoryDesigns.value = editableSubCategoryDesigns.value.map((item) =>
    String(item.id) === String(draft.id)
      ? {
          ...item,
          interior_instances: (draft.interior_instances || []).map((row) => normalizeInteriorInstanceRecord(row)).filter(Boolean),
        }
      : item
  );
}

function syncOrderDesignInCollection(item) {
  const normalized = normalizeOrderDesignRecord(item);
  if (!normalized?.id) return null;
  const existingIndex = orderDesignCatalog.value.findIndex((row) => String(row.id) === String(normalized.id));
  if (existingIndex === -1) {
    orderDesignCatalog.value = sortOrderDesignCatalogRecords([...orderDesignCatalog.value, normalized]);
    return normalized;
  }
  orderDesignCatalog.value = sortOrderDesignCatalogRecords(
    orderDesignCatalog.value.map((row, index) => index === existingIndex ? normalized : row)
  );
  return normalized;
}

async function refreshOrderDesignGeometryFromServer(orderDesignId, { updateStage = true } = {}) {
  const key = String(orderDesignId || "").trim();
  if (!key) return null;
  const res = await fetch(`/api/order-designs/${encodeURIComponent(key)}/recompute`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(await readApiErrorMessage(res, "بازسازی نمایش طرح سفارش انجام نشد."));
  const fresh = syncOrderDesignInCollection(await res.json());
  if (!fresh) return null;
  if (updateStage && String(activeCabinetDesignId.value || "") === String(fresh.id)) {
    const placement = getOrderDesignPlacement(fresh.id) || getCurrentEditorModelPlacement();
    stageCabinetPlaceholderBoxes.value = (fresh.viewer_boxes || []).map(normalizeCabinetBox);
    restoreActiveOrderDesignToEditor(fresh, placement);
  }
  return fresh;
}

function syncInteriorInstanceInOrderDesignCollection(orderDesignId, instance) {
  const targetId = String(orderDesignId || "").trim();
  const normalized = normalizeInteriorInstanceRecord(instance);
  if (!targetId || !normalized?.id) return null;
  orderDesignCatalog.value = sortOrderDesignCatalogRecords(
    orderDesignCatalog.value.map((item) => {
      if (String(item.id) !== targetId) return item;
      const interiors = Array.isArray(item.interior_instances) ? item.interior_instances : [];
      const existingIndex = interiors.findIndex((row) => String(row.id) === String(normalized.id));
      const nextInteriors = existingIndex === -1
        ? [...interiors, normalized]
        : interiors.map((row, index) => index === existingIndex ? normalized : row);
      return {
        ...item,
        interior_instances: nextInteriors
          .slice()
          .sort((a, b) => {
            const orderDelta = (Number(a.ui_order) || 0) - (Number(b.ui_order) || 0);
            if (orderDelta !== 0) return orderDelta;
            return String(a.instance_code || "").localeCompare(String(b.instance_code || ""), "fa");
          }),
      };
    })
  );
  if (String(orderDesignEditorDraft.value?.id || "") === targetId) {
    const interiors = Array.isArray(orderDesignEditorDraft.value?.interior_instances) ? orderDesignEditorDraft.value.interior_instances : [];
    const existingIndex = interiors.findIndex((row) => String(row.id) === String(normalized.id));
    orderDesignEditorDraft.value = {
      ...orderDesignEditorDraft.value,
      interior_instances: existingIndex === -1
        ? [...interiors, normalized]
        : interiors.map((row, index) => index === existingIndex ? normalized : row),
    };
  }
  return normalized;
}

function removeInteriorInstanceFromOrderDesignCollection(orderDesignId, instanceId) {
  const targetId = String(orderDesignId || "").trim();
  const interiorId = String(instanceId || "").trim();
  if (!targetId || !interiorId) return;
  orderDesignCatalog.value = sortOrderDesignCatalogRecords(
    orderDesignCatalog.value.map((item) =>
      String(item.id) === targetId
        ? {
            ...item,
            interior_instances: (item.interior_instances || []).filter((row) => String(row.id) !== interiorId),
          }
        : item
    )
  );
  if (String(orderDesignEditorDraft.value?.id || "") === targetId) {
    orderDesignEditorDraft.value = {
      ...orderDesignEditorDraft.value,
      interior_instances: (orderDesignEditorDraft.value?.interior_instances || []).filter((row) => String(row.id) !== interiorId),
    };
  }
}

async function addInteriorGroupToDesign(group) {
  if (isAddingInteriorGroup(group)) return;
  const loadingKey = getInteriorLibraryAddingGroupKey(group);
  if (subCategoryDesignEditorOpen.value) {
    const draft = subCategoryDesignEditorDraft.value;
    if (!draft?.id) {
      showAlert("ابتدا خود طرح ساب‌کت را ذخیره کنید، سپس گروه داخلی را به آن اضافه کنید.", { title: "قطعات داخلی" });
      return;
    }
    interiorLibraryAddingGroupKey.value = loadingKey;
    try {
      const res = await fetch(`/api/sub-category-designs/${encodeURIComponent(String(draft.id))}/interior-instances`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          internal_part_group_id: group.id,
          line_color: normalizeHexColor(group.line_color, DEFAULT_INTERIOR_LINE_COLOR),
          placement_z: 0,
        }),
      });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "افزودن گروه داخلی به طرح انجام نشد."));
      syncInteriorInstanceInDraft(await res.json());
      syncOpenSubCategoryDesignDraftToCollection();
      await refreshSubCategoryDesignPreview();
    } catch (error) {
      showAlert(error?.message || "افزودن گروه داخلی به طرح انجام نشد.", { title: "خطا" });
    } finally {
      interiorLibraryAddingGroupKey.value = "";
    }
    return;
  }
  const orderDesign = activeInteriorLibraryOrderDesign.value;
  if (!orderDesign?.id) {
    showAlert("ابتدا یک طرح ثبت‌شده را انتخاب کنید.", { title: "قطعات داخلی" });
    return;
  }
  interiorLibraryAddingGroupKey.value = loadingKey;
  try {
    const res = await fetch(`/api/order-designs/${encodeURIComponent(String(orderDesign.id))}/interior-instances`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        internal_part_group_id: group.id,
        line_color: normalizeHexColor(group.line_color, DEFAULT_INTERIOR_LINE_COLOR),
        placement_z: 0,
      }),
    });
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "افزودن گروه داخلی به طرح ثبت‌شده انجام نشد."));
    syncInteriorInstanceInOrderDesignCollection(orderDesign.id, await res.json());
    await refreshOrderDesignGeometryFromServer(orderDesign.id);
  } catch (error) {
    showAlert(error?.message || "افزودن گروه داخلی به طرح ثبت‌شده انجام نشد.", { title: "خطا" });
  } finally {
    interiorLibraryAddingGroupKey.value = "";
  }
}

function openInteriorInstanceEditor(instance) {
  const normalized = normalizeInteriorInstanceRecord(instance);
  if (!normalized) return;
  selectInteriorLibraryInstance(normalized.id);
  const effectiveParamValues = Object.fromEntries(
    Object.keys(normalized.param_meta || {}).map((key) => [key, getInteriorInstanceEffectiveValue(normalized, key)])
  );
  interiorInstanceEditorDraft.value = {
    ...normalized,
    line_color: normalized.line_color || resolveInteriorInstanceLineColor(normalized),
    interior_box_snapshot: { ...(normalized.interior_box_snapshot || {}) },
    param_values: {
      ...effectiveParamValues,
      ...Object.fromEntries(Object.entries(normalized.param_values || {}).map(([key, value]) => [key, String(value ?? "")])),
    },
    param_meta: Object.fromEntries(Object.entries(normalized.param_meta || {}).map(([key, value]) => [key, { ...(value || {}) }])),
    part_snapshots: Array.isArray(normalized.part_snapshots) ? normalized.part_snapshots.map((row) => ({ ...(row || {}) })) : [],
    viewer_boxes: Array.isArray(normalized.viewer_boxes) ? normalized.viewer_boxes.map((row) => ({ ...(row || {}) })) : [],
  };
  interiorInstanceEditorActiveGroupId.value = activeInteriorInstanceEditorGroups.value[0]?.id || "";
  interiorInstanceEditorOpen.value = true;
}

function resetInteriorInstanceEditorState() {
  interiorInstanceEditorOpen.value = false;
  interiorInstanceEditorDraft.value = null;
  interiorInstanceEditorActiveGroupId.value = "";
  interiorInstanceEditorApplying.value = false;
}

function closeInteriorInstanceEditor() {
  if (interiorInstanceEditorApplying.value) return;
  resetInteriorInstanceEditorState();
}

async function applyInteriorInstanceEditor() {
  const instance = interiorInstanceEditorDraft.value;
  if (!instance?.id || interiorInstanceEditorApplying.value) return;
  interiorInstanceEditorApplying.value = true;
  if (subCategoryDesignEditorOpen.value) {
    const draft = subCategoryDesignEditorDraft.value;
    if (!draft?.id) {
      interiorInstanceEditorApplying.value = false;
      return;
    }
    try {
      const res = await fetch(
        `/api/sub-category-designs/${encodeURIComponent(String(draft.id))}/interior-instances/${encodeURIComponent(String(instance.id))}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            placement_z: Number(instance.placement_z) || 0,
            ui_order: Math.max(0, Number(instance.ui_order) || 0),
            instance_code: String(instance.instance_code || "").trim() || "interior",
            line_color: instance.line_color ? normalizeHexColor(instance.line_color, DEFAULT_INTERIOR_LINE_COLOR) : null,
            param_values: Object.fromEntries(
              Object.entries(instance.param_values || {}).map(([key, value]) => [key, value == null ? null : String(value)])
            ),
          }),
        }
      );
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره تنظیمات نمونه داخلی انجام نشد."));
      syncInteriorInstanceInDraft(await res.json());
      syncOpenSubCategoryDesignDraftToCollection();
      resetInteriorInstanceEditorState();
      await refreshSubCategoryDesignPreview();
    } catch (error) {
      showAlert(error?.message || "ذخیره تنظیمات نمونه داخلی انجام نشد.", { title: "خطا" });
    } finally {
      interiorInstanceEditorApplying.value = false;
    }
    return;
  }
  const orderDesign = activeInteriorLibraryOrderDesign.value;
  if (!orderDesign?.id) {
    interiorInstanceEditorApplying.value = false;
    return;
  }
  try {
    const res = await fetch(
      `/api/order-designs/${encodeURIComponent(String(orderDesign.id))}/interior-instances/${encodeURIComponent(String(instance.id))}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          placement_z: Number(instance.placement_z) || 0,
          ui_order: Math.max(0, Number(instance.ui_order) || 0),
          instance_code: String(instance.instance_code || "").trim() || "interior",
          line_color: instance.line_color ? normalizeHexColor(instance.line_color, DEFAULT_INTERIOR_LINE_COLOR) : null,
          param_values: Object.fromEntries(
            Object.entries(instance.param_values || {}).map(([key, value]) => [key, value == null ? null : String(value)])
          ),
        }),
      }
    );
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره تنظیمات نمونه داخلی طرح ثبت‌شده انجام نشد."));
    syncInteriorInstanceInOrderDesignCollection(orderDesign.id, await res.json());
    await refreshOrderDesignGeometryFromServer(orderDesign.id);
    resetInteriorInstanceEditorState();
  } catch (error) {
    showAlert(error?.message || "ذخیره تنظیمات نمونه داخلی طرح ثبت‌شده انجام نشد.", { title: "خطا" });
  } finally {
    interiorInstanceEditorApplying.value = false;
  }
}

async function applyInteriorInstanceLineColor(instance, lineColor) {
  const normalized = normalizeInteriorInstanceRecord({
    ...(instance || {}),
    line_color: lineColor ? normalizeHexColor(lineColor, DEFAULT_INTERIOR_LINE_COLOR) : "",
  });
  if (!normalized?.id) return;
  if (subCategoryDesignEditorOpen.value) {
    const draft = subCategoryDesignEditorDraft.value;
    if (!draft?.id) return;
    try {
      const res = await fetch(
        `/api/sub-category-designs/${encodeURIComponent(String(draft.id))}/interior-instances/${encodeURIComponent(String(normalized.id))}`,
        {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            placement_z: Number(normalized.placement_z) || 0,
            ui_order: Math.max(0, Number(normalized.ui_order) || 0),
            instance_code: String(normalized.instance_code || "").trim() || "interior",
            line_color: normalized.line_color ? normalizeHexColor(normalized.line_color, DEFAULT_INTERIOR_LINE_COLOR) : null,
            param_values: Object.fromEntries(
              Object.entries(normalized.param_values || {}).map(([key, value]) => [key, value == null ? null : String(value)])
            ),
          }),
        }
      );
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره رنگ خطوط نمونه داخلی انجام نشد."));
      syncInteriorInstanceInDraft(await res.json());
      syncOpenSubCategoryDesignDraftToCollection();
      await refreshSubCategoryDesignPreview();
    } catch (error) {
      showAlert(error?.message || "ذخیره رنگ خطوط نمونه داخلی انجام نشد.", { title: "خطا" });
    }
    return;
  }
  const orderDesign = activeInteriorLibraryOrderDesign.value;
  if (!orderDesign?.id) return;
  try {
    const res = await fetch(
      `/api/order-designs/${encodeURIComponent(String(orderDesign.id))}/interior-instances/${encodeURIComponent(String(normalized.id))}`,
      {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          placement_z: Number(normalized.placement_z) || 0,
          ui_order: Math.max(0, Number(normalized.ui_order) || 0),
          instance_code: String(normalized.instance_code || "").trim() || "interior",
          line_color: normalized.line_color ? normalizeHexColor(normalized.line_color, DEFAULT_INTERIOR_LINE_COLOR) : null,
          param_values: Object.fromEntries(
            Object.entries(normalized.param_values || {}).map(([key, value]) => [key, value == null ? null : String(value)])
          ),
        }),
      }
    );
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره رنگ خطوط نمونه داخلی انجام نشد."));
    syncInteriorInstanceInOrderDesignCollection(orderDesign.id, await res.json());
    await refreshOrderDesignGeometryFromServer(orderDesign.id);
  } catch (error) {
    showAlert(error?.message || "ذخیره رنگ خطوط نمونه داخلی انجام نشد.", { title: "خطا" });
  }
}

function previewInteriorInstanceLineColor(instance, lineColor) {
  const normalizedColor = lineColor ? normalizeHexColor(lineColor, DEFAULT_INTERIOR_LINE_COLOR) : "";
  const instanceId = String(instance?.id || "").trim();
  if (!instanceId) return;
  if (subCategoryDesignEditorOpen.value) {
    const draft = subCategoryDesignEditorDraft.value;
    if (!draft) return;
    draft.interior_instances = (draft.interior_instances || []).map((row) =>
      String(row?.id || "") === instanceId
        ? {
            ...row,
            line_color: normalizedColor,
          }
        : row
    );
    syncOpenSubCategoryDesignDraftToCollection();
    return;
  }
  const orderDesignId = String(activeInteriorLibraryOrderDesign.value?.id || "").trim();
  if (!orderDesignId) return;
  orderDesignCatalog.value = sortOrderDesignCatalogRecords(
    orderDesignCatalog.value.map((design) =>
      String(design?.id || "") === orderDesignId
        ? {
            ...design,
            interior_instances: (design.interior_instances || []).map((row) =>
              String(row?.id || "") === instanceId
                ? {
                    ...row,
                    line_color: normalizedColor,
                  }
                : row
            ),
          }
        : design
    )
  );
}

function previewConstructionInternalPartGroupLineColor(item, lineColor) {
  if (!item) return;
  const normalizedColor = normalizeHexColor(lineColor, DEFAULT_INTERIOR_LINE_COLOR);
  item.line_color = normalizedColor;
  if (internalPartGroupEditorDraft.value && String(internalPartGroupEditorDraft.value.id || "") === String(item.id || "")) {
    internalPartGroupEditorDraft.value.line_color = normalizedColor;
  }
}

async function saveConstructionInternalPartGroupLineColor(item) {
  if (!item?.id) return;
  const payload = normalizeInternalPartGroupPayload(item);
  const saveKey = String(item.id);
  constructionSavingIds.value = [...new Set([...constructionSavingIds.value, saveKey])];
  try {
    const res = await fetch(`/api/internal-part-groups/${encodeURIComponent(saveKey)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره رنگ پیش‌فرض گروه داخلی انجام نشد."));
    const saved = await res.json();
    editableInternalPartGroups.value = editableInternalPartGroups.value.map((row) =>
      String(row.id) === saveKey
        ? ensureInternalPartGroupParamDefaults(withConstructionDraftState({
            ...saved,
            line_color: normalizeHexColor(saved.line_color, DEFAULT_INTERIOR_LINE_COLOR),
            param_groups: Array.isArray(saved.param_groups) ? saved.param_groups.map((group) => ({
              ...group,
              param_group_id: Number(group.param_group_id),
              param_group_code: String(group.param_group_code || "").trim(),
              param_group_title: String(group.param_group_title || "").trim(),
              param_group_icon_path: normalizeIconFileName(group.param_group_icon_path) || "",
              enabled: group.enabled !== false,
              ui_order: Number(group.ui_order) || 0,
            })) : [],
            param_defaults: Object.fromEntries(
              Object.entries(saved.param_defaults || {}).map(([key, value]) => [String(key || "").trim(), value == null ? "" : String(value)])
            ),
            param_overrides: Object.fromEntries(
              Object.entries(saved.param_overrides || {}).map(([key, override]) => [String(key || "").trim(), {
                display_title: String(override?.display_title || "").trim(),
                description_text: String(override?.description_text || "").trim(),
                icon_path: normalizeIconFileName(override?.icon_path) || "",
                input_mode: override?.input_mode === "binary" ? "binary" : "value",
                binary_off_label: String(override?.binary_off_label || "").trim() || "0",
                binary_on_label: String(override?.binary_on_label || "").trim() || "1",
                binary_off_icon_path: normalizeIconFileName(override?.binary_off_icon_path) || "",
                binary_on_icon_path: normalizeIconFileName(override?.binary_on_icon_path) || "",
              }])
            ),
          }))
        : row
    );
    if (internalPartGroupEditorDraft.value && String(internalPartGroupEditorDraft.value.id || "") === saveKey) {
      internalPartGroupEditorDraft.value.line_color = normalizeHexColor(saved.line_color, DEFAULT_INTERIOR_LINE_COLOR);
    }
  } catch (error) {
    showAlert(error?.message || "ذخیره رنگ پیش‌فرض گروه داخلی انجام نشد.", { title: "خطا" });
  } finally {
    constructionSavingIds.value = constructionSavingIds.value.filter((value) => value !== saveKey);
  }
}

async function deleteInteriorInstanceFromDesign(instance) {
  if (!instance?.id) return;
  const ok = await showConfirm("این نمونه داخلی از طرح حذف شود؟", {
    title: "حذف نمونه داخلی",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  if (subCategoryDesignEditorOpen.value) {
    const draft = subCategoryDesignEditorDraft.value;
    if (!draft?.id) return;
    try {
      const res = await fetch(
        `/api/sub-category-designs/${encodeURIComponent(String(draft.id))}/interior-instances/${encodeURIComponent(String(instance.id))}`,
        { method: "DELETE" }
      );
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "حذف نمونه داخلی انجام نشد."));
      draft.interior_instances = (draft.interior_instances || []).filter((row) => String(row.id) !== String(instance.id));
      if (String(interiorLibrarySelectedInstanceId.value || "") === String(instance.id || "")) {
        interiorLibrarySelectedInstanceId.value = "";
      }
      syncOpenSubCategoryDesignDraftToCollection();
      if (String(interiorInstanceEditorDraft.value?.id || "") === String(instance.id)) {
        closeInteriorInstanceEditor();
      }
      await refreshSubCategoryDesignPreview();
    } catch (error) {
      showAlert(error?.message || "حذف نمونه داخلی انجام نشد.", { title: "خطا" });
    }
    return;
  }
  const orderDesign = activeInteriorLibraryOrderDesign.value;
  if (!orderDesign?.id) return;
  try {
    const res = await fetch(
      `/api/order-designs/${encodeURIComponent(String(orderDesign.id))}/interior-instances/${encodeURIComponent(String(instance.id))}`,
      { method: "DELETE" }
    );
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "حذف نمونه داخلی طرح ثبت‌شده انجام نشد."));
    removeInteriorInstanceFromOrderDesignCollection(orderDesign.id, instance.id);
    if (String(interiorLibrarySelectedInstanceId.value || "") === String(instance.id || "")) {
      interiorLibrarySelectedInstanceId.value = "";
    }
    await refreshOrderDesignGeometryFromServer(orderDesign.id);
    if (String(interiorInstanceEditorDraft.value?.id || "") === String(instance.id)) {
      closeInteriorInstanceEditor();
    }
  } catch (error) {
    showAlert(error?.message || "حذف نمونه داخلی طرح ثبت‌شده انجام نشد.", { title: "خطا" });
  }
}

function onSubCategoryDesignSubCategoryChange() {
  syncSubCategoryDesignDraftSubCategoryFields(subCategoryDesignEditorDraft.value);
  refreshSubCategoryDesignPreview();
}

function openSubCategoryAdminDefaultsFromDesignEditor() {
  const draft = subCategoryDesignEditorDraft.value;
  if (!draft?.sub_category_id) return;
  const target = constructionSubCategories.value.find((item) => String(item.id) === String(draft.sub_category_id));
  if (!target) {
    showAlert("ساب‌کت انتخاب‌شده در جدول ساب‌کت‌ها پیدا نشد.", { title: "پیش‌فرض ادمین" });
    return;
  }
  openSubCategoryUserPreview(target);
}

function isPartFormulaSelectedInDesign(partFormulaId) {
  return !!subCategoryDesignEditorDraft.value?.parts?.some((part) => Number(part.part_formula_id) === Number(partFormulaId) && part.enabled !== false);
}

function togglePartFormulaInDesign(partFormulaId) {
  const draft = subCategoryDesignEditorDraft.value;
  if (!draft) return;
  const existing = draft.parts.find((part) => Number(part.part_formula_id) === Number(partFormulaId));
  if (existing) {
    draft.parts = draft.parts.filter((part) => Number(part.part_formula_id) !== Number(partFormulaId));
  } else {
    const formula = constructionSubCategoryDesignPartFormulaOptions.value.find((item) => Number(item.id) === Number(partFormulaId));
    draft.parts = [
      ...draft.parts,
      {
        part_formula_id: Number(partFormulaId),
        enabled: true,
        ui_order: Number(formula?.uiOrder) || draft.parts.length,
      },
    ];
  }
  refreshSubCategoryDesignPreview();
}

function isInternalPartFormulaSelectedInGroup(partFormulaId) {
  return !!internalPartGroupEditorDraft.value?.parts?.some((part) => Number(part.part_formula_id) === Number(partFormulaId) && part.enabled !== false);
}

function togglePartFormulaInInternalGroup(partFormulaId) {
  const draft = internalPartGroupEditorDraft.value;
  if (!draft) return;
  const existing = draft.parts.find((part) => Number(part.part_formula_id) === Number(partFormulaId));
  if (existing) {
    draft.parts = draft.parts.filter((part) => Number(part.part_formula_id) !== Number(partFormulaId));
  } else {
    const formula = constructionInteriorPartFormulaOptions.value.find((item) => Number(item.id) === Number(partFormulaId));
    draft.parts = [
      ...draft.parts,
      {
        part_formula_id: Number(partFormulaId),
        enabled: true,
        ui_order: draft.parts.length || Number(formula?.id) || 0,
      },
    ];
  }
}

async function saveSubCategoryDesignEditor() {
  const draft = subCategoryDesignEditorDraft.value;
  if (!draft || subCategoryDesignEditorSaving.value) return;
  const designId = Number(draft.design_id);
  if (!Number.isInteger(designId) || designId < 1) {
    showAlert("شناسه طرح باید معتبر و بزرگ‌تر از صفر باشد.", { title: "اعتبارسنجی" });
    return;
  }
  const title = String(draft.design_title || "").trim();
  const code = String(draft.code || "").trim();
  if (!title) {
    showAlert("عنوان طرح نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
    return;
  }
  if (!code) {
    showAlert("کد طرح نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
    return;
  }
  if (!draft.sub_category_id) {
    showAlert("برای طرح باید یک ساب‌کت انتخاب شود.", { title: "اعتبارسنجی" });
    return;
  }
  const duplicate = editableSubCategoryDesigns.value.some((item) => Number(item.design_id) === designId && String(item.id) !== String(draft.id || ""));
  if (duplicate) {
    showAlert("شناسه طرح تکراری است.", { title: "اعتبارسنجی" });
    return;
  }
  const duplicateCode = editableSubCategoryDesigns.value.some((item) => String(item.code || "").trim() === code && String(item.id) !== String(draft.id || ""));
  if (duplicateCode) {
    showAlert("کد طرح تکراری است.", { title: "اعتبارسنجی" });
    return;
  }
  const payload = normalizeSubCategoryDesignPayload(draft);
  subCategoryDesignEditorSaving.value = true;
  try {
    const res = await fetch(
      draft.id ? `/api/sub-category-designs/${encodeURIComponent(String(draft.id))}` : "/api/sub-category-designs",
      {
        method: draft.id ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره طرح ساب‌کت انجام نشد."));
    await loadConstructionSubCategoryDesigns();
    await loadCabinetDesignCatalog(true);
    if (activeOrder.value?.id) {
      await loadOrderDesignCatalog(true);
    }
    resetSubCategoryDesignEditorState();
    showAlert("طرح ساب‌کت با موفقیت ذخیره شد.", { title: "ذخیره تغییرات" });
  } catch (error) {
    showAlert(error?.message || "ذخیره طرح ساب‌کت انجام نشد.", { title: "خطا" });
  } finally {
    subCategoryDesignEditorSaving.value = false;
  }
}

async function deleteConstructionSubCategoryDesign(id) {
  const ok = await showConfirm("این طرح ساب‌کت حذف شود؟", {
    title: "حذف طرح",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  try {
    const res = await fetch(`/api/sub-category-designs/${encodeURIComponent(String(id))}`, { method: "DELETE" });
    if (!res.ok) throw new Error("delete-failed");
    await loadConstructionSubCategoryDesigns();
  } catch (_) {
    showAlert("حذف طرح ساب‌کت انجام نشد.", { title: "خطا" });
  }
}

async function toggleConstructionSubCategoryDesignScope(item) {
  if (!item?.id) return;
  const saveKey = String(item.id);
  constructionSavingIds.value = [...new Set([...constructionSavingIds.value, saveKey])];
  try {
    const res = await fetch(`/api/sub-category-designs/${encodeURIComponent(saveKey)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(normalizeSubCategoryDesignPayload({
        ...item,
        admin_id: item.admin_id === null ? currentAdminId.value : null,
        is_system: item.admin_id !== null,
      })),
    });
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "تغییر وضعیت مالکیت طرح ساب‌کت انجام نشد."));
    await loadConstructionSubCategoryDesigns();
  } catch (error) {
    showAlert(error?.message || "تغییر وضعیت مالکیت طرح ساب‌کت انجام نشد.", { title: "خطا" });
  } finally {
    constructionSavingIds.value = constructionSavingIds.value.filter((value) => value !== saveKey);
  }
}

function markConstructionPartKindDirty(item) {
  if (!item || item.__isNew) return;
  item.__dirty = true;
}

function toggleConstructionPartKindScope(item) {
  item.admin_id = item.admin_id === null ? currentAdminId.value : null;
  item.is_system = item.admin_id === null;
  if (!item.__isNew) item.__dirty = true;
}

async function toggleConstructionPartKindInternalById(partKindId) {
  const target = editablePartKinds.value.find((item) => Number(item.part_kind_id) === Number(partKindId));
  if (!target) return;
  const nextValue = !normalizeBooleanFlag(target.is_internal, false);
  if (target.__isNew) {
    target.is_internal = nextValue;
    return;
  }

  const saveKey = String(target.id);
  constructionSavingIds.value = [...new Set([...constructionSavingIds.value, saveKey])];
  try {
    const res = await fetch(`/api/part-kinds/${encodeURIComponent(saveKey)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(normalizePartKindPayload({
        ...target,
        is_internal: nextValue,
      })),
    });
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره وضعیت داخلی قطعه انجام نشد."));
    const saved = withConstructionDraftState(await res.json());
    editablePartKinds.value = editablePartKinds.value.map((item) =>
      String(item.id) === saveKey ? { ...saved, is_internal: normalizeBooleanFlag(saved.is_internal, false) } : item
    );
  } catch (error) {
    showAlert(error?.message || "ذخیره وضعیت داخلی قطعه انجام نشد.", { title: "خطا" });
  } finally {
    constructionSavingIds.value = constructionSavingIds.value.filter((value) => value !== saveKey);
  }
}

async function saveInternalPartGroupEditor() {
  const draft = internalPartGroupEditorDraft.value;
  if (!draft) return;
  const groupId = Number(draft.group_id);
  const title = String(draft.group_title || "").trim();
  const code = String(draft.code || "").trim();
  if (!Number.isInteger(groupId) || groupId < 1) {
    showAlert("شناسه گروه باید معتبر و بزرگ‌تر از صفر باشد.", { title: "اعتبارسنجی" });
    return;
  }
  if (!title) {
    showAlert("عنوان گروه نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
    return;
  }
  if (!code) {
    showAlert("کد گروه نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
    return;
  }
  const duplicate = editableInternalPartGroups.value.some((item) => Number(item.group_id) === groupId && String(item.id) !== String(draft.id || ""));
  if (duplicate) {
    showAlert("شناسه گروه تکراری است.", { title: "اعتبارسنجی" });
    return;
  }
  const duplicateCode = editableInternalPartGroups.value.some((item) => String(item.code || "").trim() === code && String(item.id) !== String(draft.id || ""));
  if (duplicateCode) {
    showAlert("کد گروه تکراری است.", { title: "اعتبارسنجی" });
    return;
  }
  const payload = normalizeInternalPartGroupPayload(draft);
  try {
    const res = await fetch(
      draft.id ? `/api/internal-part-groups/${encodeURIComponent(String(draft.id))}` : "/api/internal-part-groups",
      {
        method: draft.id ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }
    );
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره گروه قطعات داخلی انجام نشد."));
    await loadConstructionInternalPartGroups();
    closeInternalPartGroupEditor();
    showAlert("گروه قطعات داخلی با موفقیت ذخیره شد.", { title: "ذخیره تغییرات" });
  } catch (error) {
    showAlert(error?.message || "ذخیره گروه قطعات داخلی انجام نشد.", { title: "خطا" });
  }
}

async function deleteConstructionInternalPartGroup(id) {
  const item = editableInternalPartGroups.value.find((row) => String(row.id) === String(id));
  if (!item) return;
  const ok = await showConfirm(`گروه «${item.group_title || item.title || "بدون عنوان"}» حذف شود؟`, {
    title: "حذف گروه قطعات داخلی",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  try {
    const res = await fetch(`/api/internal-part-groups/${encodeURIComponent(String(id))}`, { method: "DELETE" });
    if (!res.ok) throw new Error("delete-failed");
    await loadConstructionInternalPartGroups();
  } catch (_) {
    showAlert("حذف گروه قطعات داخلی انجام نشد.", { title: "خطا" });
  }
}

function normalizeParamGroupPayload(item) {
  return {
    admin_id: item.admin_id,
    param_group_id: Number(item.param_group_id),
    param_group_code: String(item.param_group_code || "").trim(),
    org_param_group_title: String(item.org_param_group_title || "").trim(),
    param_group_icon_path: normalizeIconFileName(item.param_group_icon_path) || null,
    show_in_order_attrs: normalizeBooleanFlag(item.show_in_order_attrs, true),
    ui_order: Number.isFinite(Number(item.ui_order)) ? Number(item.ui_order) : 0,
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.param_group_id),
    is_system: !!item.is_system,
  };
}

function markConstructionParamGroupDirty(item) {
  if (!item || item.__isNew) return;
  item.__dirty = true;
}

function toggleConstructionParamGroupScope(item) {
  item.admin_id = item.admin_id === null ? currentAdminId.value : null;
  item.is_system = item.admin_id === null;
  if (!item.__isNew) item.__dirty = true;
}

function validateConstructionParamGroups() {
  for (const item of editableParamGroups.value) {
    const paramGroupId = Number(item.param_group_id);
    const code = String(item.param_group_code || "").trim();
    const title = String(item.org_param_group_title || "").trim();
    if (!Number.isInteger(paramGroupId) || paramGroupId < 1) {
      showAlert("برای همه گروه‌های پارامتر شناسه معتبر و بزرگ‌تر از صفر وارد کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!code || !title) {
      showAlert("کد و عنوان گروه پارامتر نباید خالی باشند.", { title: "اعتبارسنجی" });
      return false;
    }
  }
  const ids = editableParamGroups.value.map((item) => Number(item.param_group_id));
  if (new Set(ids).size !== ids.length) {
    showAlert("شناسه گروه پارامتر باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  const codes = editableParamGroups.value.map((item) => String(item.param_group_code || "").trim().toLowerCase());
  if (new Set(codes).size !== codes.length) {
    showAlert("کد گروه پارامتر باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  return true;
}

function normalizeParamPayload(item) {
  return {
    admin_id: item.admin_id,
    param_id: Number(item.param_id),
    part_kind_id: Number(item.part_kind_id),
    param_code: String(item.param_code || "").trim(),
    param_title_en: String(item.param_title_en || "").trim(),
    param_title_fa: String(item.param_title_fa || "").trim(),
    param_group_id: Number(item.param_group_id),
    interior_value_mode: "formula",
    ui_order: Number.isFinite(Number(item.ui_order)) ? Number(item.ui_order) : 0,
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.param_id),
    is_system: !!item.is_system,
  };
}

function normalizeBaseFormulaPayload(item) {
  return {
    admin_id: item.admin_id,
    fo_id: Number(item.fo_id),
    param_formula: String(item.param_formula || "").trim(),
    formula: String(item.formula || "").trim(),
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.fo_id),
    is_system: !!item.is_system,
  };
}

function normalizePartFormulaPayload(item) {
  const payload = {
    admin_id: item.admin_id,
    part_formula_id: Number(item.part_formula_id),
    part_kind_id: Number(item.part_kind_id),
    part_sub_kind_id: Number(item.part_sub_kind_id),
    part_code: String(item.part_code || "").trim(),
    part_title: String(item.part_title || "").trim(),
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.part_formula_id),
    is_system: !!item.is_system,
  };
  for (const field of PART_FORMULA_FIELDS) {
    payload[field.key] = String(item[field.key] || "").trim();
  }
  return payload;
}

function markConstructionParamDirty(item) {
  if (!item || item.__isNew) return;
  item.__dirty = true;
}

function markConstructionTemplateDirty(item) {
  if (!item || item.__isNew) return;
  item.__dirty = true;
}

function markConstructionCategoryDirty(item) {
  if (!item || item.__isNew) return;
  item.__dirty = true;
}

function markConstructionSubCategoryDirty(item) {
  if (!item || item.__isNew) return;
  item.__dirty = true;
}

function markConstructionBaseFormulaDirty(item) {
  if (!item || item.__isNew) return;
  item.__dirty = true;
}

function markConstructionPartFormulaDirty(item) {
  if (!item || item.__isNew) return;
  item.__dirty = true;
}

function toggleConstructionParamScope(item) {
  item.admin_id = item.admin_id === null ? currentAdminId.value : null;
  item.is_system = item.admin_id === null;
  if (!item.__isNew) item.__dirty = true;
}

function toggleConstructionBaseFormulaScope(item) {
  item.admin_id = item.admin_id === null ? currentAdminId.value : null;
  item.is_system = item.admin_id === null;
  if (!item.__isNew) item.__dirty = true;
}

function toggleConstructionTemplateScope(item) {
  item.admin_id = item.admin_id === null ? currentAdminId.value : null;
  item.is_system = item.admin_id === null;
  if (!item.__isNew) item.__dirty = true;
}

function toggleConstructionCategoryScope(item) {
  item.admin_id = item.admin_id === null ? currentAdminId.value : null;
  item.is_system = item.admin_id === null;
  if (!item.__isNew) item.__dirty = true;
}

function hasSubCategoryScopeTitleConflict(item) {
  const title = String(item?.sub_cat_title || "").trim().toLowerCase();
  if (!title) return false;
  return editableSubCategories.value.some((row) =>
    String(row?.id) !== String(item?.id) &&
    Number(row?.cat_id) === Number(item?.cat_id) &&
    String(row?.admin_id || "system") === String(item?.admin_id || "system") &&
    String(row?.sub_cat_title || "").trim().toLowerCase() === title
  );
}

function toggleConstructionSubCategoryScope(item) {
  const previousAdminId = item.admin_id;
  const previousIsSystem = item.is_system;
  item.admin_id = item.admin_id === null ? currentAdminId.value : null;
  item.is_system = item.admin_id === null;
  if (hasSubCategoryScopeTitleConflict(item)) {
    item.admin_id = previousAdminId;
    item.is_system = previousIsSystem;
    showAlert("در نوع مالک انتخاب‌شده، ساب‌کت دیگری با همین عنوان و همین دسته وجود دارد.", { title: "اعتبارسنجی" });
    return;
  }
  if (!item.__isNew) item.__dirty = true;
}

function validateConstructionTemplates() {
  for (const item of editableTemplates.value) {
    const tempId = Number(item.temp_id);
    const tempTitle = String(item.temp_title || "").trim();
    if (!Number.isInteger(tempId) || tempId < 1) {
      showAlert("برای همه تمپلیت‌ها شناسه معتبر و بزرگ‌تر از صفر وارد کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!tempTitle) {
      showAlert("عنوان تمپلیت نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
      return false;
    }
  }
  const ids = editableTemplates.value.map((item) => Number(item.temp_id));
  if (new Set(ids).size !== ids.length) {
    showAlert("شناسه تمپلیت باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  const titles = editableTemplates.value.map((item) => String(item.temp_title || "").trim().toLowerCase());
  if (new Set(titles).size !== titles.length) {
    showAlert("عنوان تمپلیت باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  return true;
}

function validateConstructionCategories() {
  const templateIds = new Set(constructionTemplates.value.map((item) => Number(item.temp_id)).filter((value) => Number.isInteger(value) && value > 0));
  for (const item of editableCategories.value) {
    const tempId = Number(item.temp_id);
    const catId = Number(item.cat_id);
    const catTitle = String(item.cat_title || "").trim();
    if (!Number.isInteger(tempId) || tempId < 1 || !templateIds.has(tempId)) {
      showAlert("برای همه دسته‌ها یک تمپلیت معتبر از جدول تمپلیت‌ها انتخاب کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!Number.isInteger(catId) || catId < 1) {
      showAlert("برای همه دسته‌ها شناسه معتبر و بزرگ‌تر از صفر وارد کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!catTitle) {
      showAlert("عنوان دسته نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
      return false;
    }
    if (normalizeHexColor(item.design_outline_color) !== String(item.design_outline_color || "").trim().toUpperCase()) {
      showAlert("رنگ بدنه سه‌بعدی دسته باید با فرمت HEX مثل #7A4A2B وارد شود.", { title: "اعتبارسنجی" });
      return false;
    }
  }
  const ids = editableCategories.value.map((item) => Number(item.cat_id));
  if (new Set(ids).size !== ids.length) {
    showAlert("شناسه دسته باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  const scopedTitles = editableCategories.value.map((item) => `${Number(item.temp_id)}::${String(item.admin_id || "system")}::${String(item.cat_title || "").trim().toLowerCase()}`);
  if (new Set(scopedTitles).size !== scopedTitles.length) {
    showAlert("عنوان دسته در هر تمپلیت و محدوده مالک باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  return true;
}

function getConstructionCategoryOptions(tempId) {
  return constructionCategories.value
    .filter((item) => Number(item.temp_id) === Number(tempId))
    .map((item) => ({
      value: Number(item.cat_id),
      label: `${toPersianDigits(item.cat_id)} - ${String(item.cat_title || "").trim()}`,
    }));
}

function ensureSubCategoryParamDefaults(item) {
  if (!item.param_defaults || typeof item.param_defaults !== "object") {
    item.param_defaults = {};
  }
  if (!item.param_overrides || typeof item.param_overrides !== "object") {
    item.param_overrides = {};
  }
  for (const column of constructionSubCategoryParamColumns.value) {
    if (!(column.key in item.param_defaults)) {
      item.param_defaults[column.key] = "";
    }
    const baseLabel = constructionSubCategoryParamMetaByCode.value[column.key]?.label || column.key;
    if (!item.param_overrides[column.key] || typeof item.param_overrides[column.key] !== "object") {
      item.param_overrides[column.key] = {
        display_title: baseLabel,
        description_text: "",
        icon_path: "",
        input_mode: "value",
        binary_off_label: "0",
        binary_on_label: "1",
        binary_off_icon_path: "",
        binary_on_icon_path: "",
      };
      continue;
    }
    item.param_overrides[column.key] = {
      display_title: String(item.param_overrides[column.key].display_title || "").trim() || baseLabel,
      description_text: String(item.param_overrides[column.key].description_text || "").trim(),
      icon_path: normalizeIconFileName(item.param_overrides[column.key].icon_path) || "",
      input_mode: item.param_overrides[column.key].input_mode === "binary" ? "binary" : "value",
      binary_off_label: String(item.param_overrides[column.key].binary_off_label || "").trim() || "0",
      binary_on_label: String(item.param_overrides[column.key].binary_on_label || "").trim() || "1",
      binary_off_icon_path: normalizeIconFileName(item.param_overrides[column.key].binary_off_icon_path) || "",
      binary_on_icon_path: normalizeIconFileName(item.param_overrides[column.key].binary_on_icon_path) || "",
    };
  }
  return item;
}

function cloneSubCategoryDefaultsSeed(source) {
  const seeded = ensureSubCategoryParamDefaults({
    param_defaults: Object.fromEntries(
      constructionSubCategoryParamColumns.value.map((column) => [
        column.key,
        String(source?.param_defaults?.[column.key] ?? ""),
      ])
    ),
    param_overrides: Object.fromEntries(
      constructionSubCategoryParamColumns.value.map((column) => {
        const baseLabel = constructionSubCategoryParamMetaByCode.value[column.key]?.label || column.key;
        const override = source?.param_overrides?.[column.key] || {};
        return [column.key, {
          display_title: String(override.display_title || "").trim() || baseLabel,
          description_text: String(override.description_text || "").trim(),
          icon_path: normalizeIconFileName(override.icon_path) || "",
          input_mode: override.input_mode === "binary" ? "binary" : "value",
          binary_off_label: String(override.binary_off_label || "").trim() || "0",
          binary_on_label: String(override.binary_on_label || "").trim() || "1",
          binary_off_icon_path: normalizeIconFileName(override.binary_off_icon_path) || "",
          binary_on_icon_path: normalizeIconFileName(override.binary_on_icon_path) || "",
        }];
      })
    ),
  });
  return {
    param_defaults: { ...(seeded.param_defaults || {}) },
    param_overrides: Object.fromEntries(
      Object.entries(seeded.param_overrides || {}).map(([key, value]) => [key, { ...(value || {}) }])
    ),
  };
}

function getInternalPartGroupSelectedParamColumns(item) {
  const selectedParamGroupIds = new Set(
    (Array.isArray(item?.param_groups) ? item.param_groups : [])
      .filter((group) => group?.enabled !== false && Number(group?.param_group_id) > 0)
      .map((group) => Number(group.param_group_id))
  );
  if (!selectedParamGroupIds.size) return [];
  return constructionParams.value
    .filter((param) => selectedParamGroupIds.has(Number(param?.param_group_id)))
    .map((param) => ({
      key: String(param.param_code || "").trim(),
      label: String(param.param_title_fa || param.title || param.param_code || "").trim(),
    }))
    .filter((item) => item.key);
}

function ensureInternalPartGroupParamDefaults(item) {
  if (!item) return item;
  if (!item.param_defaults || typeof item.param_defaults !== "object") {
    item.param_defaults = {};
  }
  if (!item.param_overrides || typeof item.param_overrides !== "object") {
    item.param_overrides = {};
  }
  for (const column of getInternalPartGroupSelectedParamColumns(item)) {
    if (!(column.key in item.param_defaults)) {
      item.param_defaults[column.key] = "";
    }
    const baseLabel = constructionSubCategoryParamMetaByCode.value[column.key]?.label || column.key;
    if (!item.param_overrides[column.key] || typeof item.param_overrides[column.key] !== "object") {
      item.param_overrides[column.key] = {
        display_title: baseLabel,
        description_text: "",
        icon_path: "",
        input_mode: "value",
        binary_off_label: "0",
        binary_on_label: "1",
        binary_off_icon_path: "",
        binary_on_icon_path: "",
      };
      continue;
    }
    item.param_overrides[column.key] = {
      display_title: String(item.param_overrides[column.key].display_title || "").trim() || baseLabel,
      description_text: String(item.param_overrides[column.key].description_text || "").trim(),
      icon_path: normalizeIconFileName(item.param_overrides[column.key].icon_path) || "",
      input_mode: item.param_overrides[column.key].input_mode === "binary" ? "binary" : "value",
      binary_off_label: String(item.param_overrides[column.key].binary_off_label || "").trim() || "0",
      binary_on_label: String(item.param_overrides[column.key].binary_on_label || "").trim() || "1",
      binary_off_icon_path: normalizeIconFileName(item.param_overrides[column.key].binary_off_icon_path) || "",
      binary_on_icon_path: normalizeIconFileName(item.param_overrides[column.key].binary_on_icon_path) || "",
    };
  }
  const seededByCode = new Map();
  const selectedColumns = getInternalPartGroupSelectedParamColumns(item);
  for (const subCategory of constructionSubCategories.value) {
    ensureSubCategoryParamDefaults(subCategory);
    for (const column of selectedColumns) {
      if (seededByCode.has(column.key)) continue;
      const baseLabel = constructionSubCategoryParamMetaByCode.value[column.key]?.label || column.key;
      const override = subCategory.param_overrides?.[column.key] || {};
      seededByCode.set(column.key, {
        value: String(subCategory.param_defaults?.[column.key] ?? "").trim(),
        override: {
          display_title: String(override.display_title || "").trim() || baseLabel,
          description_text: String(override.description_text || "").trim(),
          icon_path: normalizeIconFileName(override.icon_path) || "",
          input_mode: override.input_mode === "binary" ? "binary" : "value",
          binary_off_label: String(override.binary_off_label || "").trim() || "0",
          binary_on_label: String(override.binary_on_label || "").trim() || "1",
          binary_off_icon_path: normalizeIconFileName(override.binary_off_icon_path) || "",
          binary_on_icon_path: normalizeIconFileName(override.binary_on_icon_path) || "",
        },
      });
    }
    if (seededByCode.size >= selectedColumns.length) break;
  }
  for (const column of selectedColumns) {
    const baseLabel = constructionSubCategoryParamMetaByCode.value[column.key]?.label || column.key;
    const seeded = seededByCode.get(column.key);
    if (!seeded) continue;
    const currentValue = String(item.param_defaults?.[column.key] ?? "").trim();
    const currentOverride = normalizeInternalPartGroupParamOverride(item.param_overrides?.[column.key], baseLabel);
    const currentDisplayTitle = String(currentOverride.display_title || "").trim() || baseLabel;
    if (!currentValue && seeded.value) {
      item.param_defaults[column.key] = seeded.value;
    }
    if (!currentDisplayTitle || currentDisplayTitle === baseLabel) {
      currentOverride.display_title = String(seeded.override.display_title || "").trim() || baseLabel;
    }
    if (!currentOverride.description_text && seeded.override.description_text) {
      currentOverride.description_text = seeded.override.description_text;
    }
    if (!currentOverride.icon_path && seeded.override.icon_path) {
      currentOverride.icon_path = seeded.override.icon_path;
    }
    if (currentOverride.input_mode !== "binary" && seeded.override.input_mode === "binary") {
      currentOverride.input_mode = "binary";
    }
    if ((String(currentOverride.binary_off_label || "").trim() || "0") === "0" && seeded.override.binary_off_label && seeded.override.binary_off_label !== "0") {
      currentOverride.binary_off_label = seeded.override.binary_off_label;
    }
    if ((String(currentOverride.binary_on_label || "").trim() || "1") === "1" && seeded.override.binary_on_label && seeded.override.binary_on_label !== "1") {
      currentOverride.binary_on_label = seeded.override.binary_on_label;
    }
    if (!currentOverride.binary_off_icon_path && seeded.override.binary_off_icon_path) {
      currentOverride.binary_off_icon_path = seeded.override.binary_off_icon_path;
    }
    if (!currentOverride.binary_on_icon_path && seeded.override.binary_on_icon_path) {
      currentOverride.binary_on_icon_path = seeded.override.binary_on_icon_path;
    }
    item.param_overrides[column.key] = currentOverride;
    if (currentOverride.input_mode === "binary") {
      const normalizedBinaryValue = String(item.param_defaults?.[column.key] ?? "").trim();
      item.param_defaults[column.key] = normalizedBinaryValue === "1" ? "1" : "0";
    }
  }
  return item;
}

function normalizeInternalPartGroupControllerType(value) {
  const normalized = String(value || "").trim();
  return INTERNAL_GROUP_CONTROLLER_TYPE_OPTIONS.some((item) => item.value === normalized) ? normalized : "";
}

function buildInternalPartGroupControllerBindingsByType(controllerType) {
  const normalizedType = normalizeInternalPartGroupControllerType(controllerType);
  const definitions = INTERNAL_GROUP_CONTROLLER_DEFINITIONS[normalizedType] || [];
  return Object.fromEntries(
    definitions.map((definition) => [definition.key, { param_code: null }])
  );
}

function normalizeInternalPartGroupControllerBindings(controllerType, bindings, allowedCodes = null) {
  const normalizedType = normalizeInternalPartGroupControllerType(controllerType);
  if (!normalizedType) return {};
  const definitions = INTERNAL_GROUP_CONTROLLER_DEFINITIONS[normalizedType] || [];
  const allowed = allowedCodes instanceof Set ? allowedCodes : null;
  return Object.fromEntries(
    definitions.map((definition) => {
      const rawParamCode = String(bindings?.[definition.key]?.param_code || "").trim();
      const normalizedParamCode = rawParamCode && (!allowed || allowed.has(rawParamCode)) ? rawParamCode : null;
      return [definition.key, { param_code: normalizedParamCode }];
    })
  );
}

function ensureInternalPartGroupControllerConfig(item) {
  if (!item) return item;
  const allowedCodes = new Set(getInternalPartGroupSelectedParamColumns(item).map((column) => column.key));
  item.controller_type = normalizeInternalPartGroupControllerType(item.controller_type);
  item.controller_bindings = normalizeInternalPartGroupControllerBindings(
    item.controller_type,
    item.controller_bindings,
    allowedCodes,
  );
  return item;
}

function getInternalPartGroupControllerDefinitions(controllerType) {
  return (INTERNAL_GROUP_CONTROLLER_DEFINITIONS[normalizeInternalPartGroupControllerType(controllerType)] || []).map((item) => ({ ...item }));
}

function getInternalPartGroupControllerParamOptions(row) {
  return getInternalPartGroupSelectedParamColumns(row).map((column) => ({
    value: column.key,
    label: column.label || column.key,
  }));
}

function getInternalPartGroupControllerTypeLabel(value) {
  const normalized = normalizeInternalPartGroupControllerType(value);
  return INTERNAL_GROUP_CONTROLLER_TYPE_OPTIONS.find((item) => item.value === normalized)?.label || "";
}

function getInternalPartGroupControllerSummary(item) {
  const controllerType = normalizeInternalPartGroupControllerType(item?.controller_type);
  if (!controllerType) {
    return { text: "بدون کنترلر", detail: "", connected: 0, total: 0 };
  }
  const definitions = getInternalPartGroupControllerDefinitions(controllerType);
  const allowedCodes = new Set(getInternalPartGroupSelectedParamColumns(item).map((column) => column.key));
  const bindings = normalizeInternalPartGroupControllerBindings(controllerType, item?.controller_bindings, allowedCodes);
  const connected = definitions.filter((definition) => String(bindings?.[definition.key]?.param_code || "").trim()).length;
  return {
    text: `${toPersianDigits(connected)} / ${toPersianDigits(definitions.length)} متصل`,
    detail: getInternalPartGroupControllerTypeLabel(controllerType),
    connected,
    total: definitions.length,
  };
}

function buildInternalPartGroupDefaultsGroups(row) {
  if (!row) return [];
  const selectedParamGroupIds = new Set(
    (Array.isArray(row.param_groups) ? row.param_groups : [])
      .filter((group) => group?.enabled !== false && Number(group?.param_group_id) > 0)
      .map((group) => String(Number(group.param_group_id)))
  );
  if (!selectedParamGroupIds.size) return [];
  return constructionSubCategoryParamTree.value
    .filter((group) => selectedParamGroupIds.has(String(group.id)))
    .map((group) => ({
      ...group,
      iconUrl: group.iconUrl || (group.iconFileName ? getSubCategoryDefaultIconUrl(group.iconFileName) : ""),
      items: group.items.map((column) => {
        const baseLabel = column.label || column.key;
        const override = normalizeInternalPartGroupParamOverride(row.param_overrides?.[column.key], baseLabel);
        const displayTitle = String(override.display_title || baseLabel).trim() || column.key;
        const descriptionText = String(override.description_text || "").trim();
        const inputMode = override.input_mode === "binary" ? "binary" : "value";
        return {
          ...column,
          displayTitle,
          descriptionText,
          iconUrl: getSubCategoryDefaultIconUrl(override.icon_path),
          inputMode,
          binaryOffLabel: String(override.binary_off_label || "").trim() || "0",
          binaryOnLabel: String(override.binary_on_label || "").trim() || "1",
          binaryOffIconUrl: getSubCategoryDefaultIconUrl(override.binary_off_icon_path),
          binaryOnIconUrl: getSubCategoryDefaultIconUrl(override.binary_on_icon_path),
        };
      }),
    }))
    .filter((group) => group.items.length > 0);
}

function normalizeInternalPartGroupParamOverride(override, baseLabel) {
  return {
    display_title: String(override?.display_title || "").trim() || baseLabel,
    description_text: String(override?.description_text || "").trim(),
    icon_path: normalizeIconFileName(override?.icon_path) || "",
    input_mode: override?.input_mode === "binary" ? "binary" : "value",
    binary_off_label: String(override?.binary_off_label || "").trim() || "0",
    binary_on_label: String(override?.binary_on_label || "").trim() || "1",
    binary_off_icon_path: normalizeIconFileName(override?.binary_off_icon_path) || "",
    binary_on_icon_path: normalizeIconFileName(override?.binary_on_icon_path) || "",
  };
}

function getInternalPartGroupDefaultsSummary(item) {
  const columns = getInternalPartGroupSelectedParamColumns(item);
  const total = columns.length;
  const filled = columns.filter((column) => String(item?.param_defaults?.[column.key] ?? "").trim()).length;
  return {
    filled,
    total,
    text: total ? `${toPersianDigits(filled)} / ${toPersianDigits(total)}` : "بدون پارامتر",
  };
}

function getSubCategoryDefaultsSummary(item) {
  const total = constructionSubCategoryParamColumns.value.length;
  const filled = Object.values(item?.param_defaults || {}).filter((value) => String(value || "").trim()).length;
  return {
    filled,
    total,
    text: total ? `${toPersianDigits(filled)} / ${toPersianDigits(total)}` : "بدون پارامتر",
  };
}

function openSubCategoryDefaultsEditor(item) {
  ensureSubCategoryParamDefaults(item);
  clearSubCategoryDefaultIconPreviews();
  subCategoryDefaultsEditorRowId.value = item.id;
  subCategoryDefaultsEditorDraft.value = Object.fromEntries(
    constructionSubCategoryParamColumns.value.map((column) => [
      column.key,
      String(item.param_defaults?.[column.key] ?? ""),
    ])
  );
  subCategoryDefaultsEditorOverridesDraft.value = Object.fromEntries(
    constructionSubCategoryParamColumns.value.map((column) => {
      const baseLabel = constructionSubCategoryParamMetaByCode.value[column.key]?.label || column.key;
      const override = item.param_overrides?.[column.key] || {};
      return [column.key, {
        display_title: String(override.display_title || "").trim() || baseLabel,
        description_text: String(override.description_text || "").trim(),
        icon_path: normalizeIconFileName(override.icon_path) || "",
        input_mode: override.input_mode === "binary" ? "binary" : "value",
        binary_off_label: String(override.binary_off_label || "").trim() || "0",
        binary_on_label: String(override.binary_on_label || "").trim() || "1",
        binary_off_icon_path: normalizeIconFileName(override.binary_off_icon_path) || "",
        binary_on_icon_path: normalizeIconFileName(override.binary_on_icon_path) || "",
      }];
    })
  );
  subCategoryDefaultsActiveGroupId.value = constructionSubCategoryParamTree.value[0]?.id || "";
  subCategoryDefaultsEditorOpen.value = true;
}

function selectSubCategoryDefaultsGroup(groupId) {
  subCategoryDefaultsActiveGroupId.value = String(groupId || "");
}

async function closeSubCategoryDefaultsEditor() {
  const row = activeSubCategoryDefaultsRow.value;
  const original = row?.param_defaults || {};
  const originalOverrides = row?.param_overrides || {};
  const changed = constructionSubCategoryParamColumns.value.some(
    (column) => {
      const baseLabel = constructionSubCategoryParamMetaByCode.value[column.key]?.label || column.key;
      const nextOverride = subCategoryDefaultsEditorOverridesDraft.value?.[column.key] || {};
      const prevOverride = originalOverrides[column.key] || {};
      return String(original[column.key] ?? "").trim() !== String(subCategoryDefaultsEditorDraft.value?.[column.key] ?? "").trim()
        || String(prevOverride.display_title || "").trim() !== String(nextOverride.display_title || "").trim()
        || String(prevOverride.description_text || "").trim() !== String(nextOverride.description_text || "").trim()
        || String(normalizeIconFileName(prevOverride.icon_path) || "").trim() !== String(normalizeIconFileName(nextOverride.icon_path) || "").trim()
        || String(prevOverride.input_mode || "value") !== String(nextOverride.input_mode || "value")
        || String(normalizeIconFileName(prevOverride.binary_off_icon_path) || "").trim() !== String(normalizeIconFileName(nextOverride.binary_off_icon_path) || "").trim()
        || String(normalizeIconFileName(prevOverride.binary_on_icon_path) || "").trim() !== String(normalizeIconFileName(nextOverride.binary_on_icon_path) || "").trim()
        || String(prevOverride.binary_off_label || "0").trim() !== String(nextOverride.binary_off_label || "0").trim()
        || String(prevOverride.binary_on_label || "1").trim() !== String(nextOverride.binary_on_label || "1").trim()
        || !String(nextOverride.display_title || "").trim()
        || String(nextOverride.display_title || "").trim() === "";
    }
  );
  if (changed) {
    const ok = await showConfirm("تغییرات پیش‌فرض‌ها اعمال نشده‌اند. پنجره بسته شود؟", {
      title: "بستن پیش‌فرض‌ها",
      confirmText: "بستن",
      cancelText: "بازگشت",
    });
    if (!ok) return;
  }
  subCategoryDefaultsEditorOpen.value = false;
  subCategoryDefaultsEditorRowId.value = null;
  subCategoryDefaultsEditorDraft.value = {};
  subCategoryDefaultsEditorOverridesDraft.value = {};
  clearSubCategoryDefaultIconPreviews();
  subCategoryDefaultsActiveGroupId.value = "";
}

async function persistSubCategoryRow(row) {
  if (!row?.id) throw new Error("Sub-category row is missing.");
  const payload = normalizeSubCategoryPayload(row);
  const res = await fetch(`/api/sub-categories/${encodeURIComponent(String(row.id))}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await readApiErrorMessage(res, "ذخیره پیش‌فرض‌های ساب‌کت انجام نشد."));
  }
  const savedRow = ensureSubCategoryParamDefaults(withConstructionDraftState(await res.json()));
  editableSubCategories.value = editableSubCategories.value.map((item) =>
    String(item.id) === String(savedRow.id) ? savedRow : item
  );
  if (
    subCategoryDesignEditorOpen.value &&
    subCategoryDesignEditorDraft.value &&
    String(subCategoryDesignEditorDraft.value.sub_category_id) === String(savedRow.id)
  ) {
    syncSubCategoryDesignDraftSubCategoryFields(subCategoryDesignEditorDraft.value);
    await refreshSubCategoryDesignPreview();
  }
  return savedRow;
}

async function applySubCategoryDefaultsEditor() {
  const row = activeSubCategoryDefaultsRow.value;
  if (!row) return;
  ensureSubCategoryParamDefaults(row);
  for (const column of constructionSubCategoryParamColumns.value) {
    row.param_defaults[column.key] = String(subCategoryDefaultsEditorDraft.value?.[column.key] ?? "").trim();
    const baseLabel = constructionSubCategoryParamMetaByCode.value[column.key]?.label || column.key;
    const nextOverride = subCategoryDefaultsEditorOverridesDraft.value?.[column.key] || {};
    row.param_overrides[column.key] = {
      display_title: String(nextOverride.display_title || "").trim() || baseLabel,
      description_text: String(nextOverride.description_text || "").trim(),
      icon_path: normalizeIconFileName(nextOverride.icon_path) || "",
      input_mode: nextOverride.input_mode === "binary" ? "binary" : "value",
      binary_off_label: String(nextOverride.binary_off_label || "").trim() || "0",
      binary_on_label: String(nextOverride.binary_on_label || "").trim() || "1",
      binary_off_icon_path: normalizeIconFileName(nextOverride.binary_off_icon_path) || "",
      binary_on_icon_path: normalizeIconFileName(nextOverride.binary_on_icon_path) || "",
    };
    if (row.param_overrides[column.key].input_mode === "binary") {
      const current = String(row.param_defaults[column.key] ?? "").trim();
      row.param_defaults[column.key] = current === "1" ? "1" : "0";
    }
  }
  markConstructionSubCategoryDirty(row);
  try {
    await persistSubCategoryRow(row);
  } catch (error) {
    showAlert(error?.message || "ذخیره پیش‌فرض‌های ساب‌کت انجام نشد.", { title: "خطا" });
    return;
  }
  clearSubCategoryDefaultIconPreviews();
  subCategoryDefaultsEditorOpen.value = false;
  subCategoryDefaultsEditorRowId.value = null;
  subCategoryDefaultsEditorDraft.value = {};
  subCategoryDefaultsEditorOverridesDraft.value = {};
  subCategoryDefaultsActiveGroupId.value = "";
}

function openSubCategoryUserPreview(item) {
  ensureSubCategoryParamDefaults(item);
  subCategoryUserPreviewRowId.value = item.id;
  subCategoryUserPreviewValues.value = Object.fromEntries(
    constructionSubCategoryParamColumns.value.map((column) => {
      const override = item.param_overrides?.[column.key] || {};
      const value = String(item.param_defaults?.[column.key] ?? "").trim();
      return [
        column.key,
        override.input_mode === "binary"
          ? (value === "1" ? "1" : "0")
          : value,
      ];
    })
  );
  subCategoryUserPreviewActiveGroupId.value = constructionSubCategoryParamTree.value[0]?.id || "";
  subCategoryUserPreviewOpen.value = true;
}

function hasSubCategoryUserPreviewChanges() {
  const row = activeSubCategoryUserPreviewRow.value;
  if (!row) return false;
  return constructionSubCategoryParamColumns.value.some((column) => {
    const override = row.param_overrides?.[column.key] || {};
    const nextValue = String(subCategoryUserPreviewValues.value?.[column.key] ?? "").trim();
    const prevValue = String(row.param_defaults?.[column.key] ?? "").trim();
    if (override.input_mode === "binary") {
      return (nextValue === "1" ? "1" : "0") !== (prevValue === "1" ? "1" : "0");
    }
    return nextValue !== prevValue;
  });
}

async function closeSubCategoryUserPreview() {
  if (hasSubCategoryUserPreviewChanges()) {
    const ok = await showConfirm("تغییرات پیش‌فرض‌ها اعمال نشده‌اند. پنجره بسته شود؟", {
      title: "بستن پیش‌فرض‌ها",
      confirmText: "بستن",
      cancelText: "بازگشت",
    });
    if (!ok) return;
  }
  subCategoryUserPreviewOpen.value = false;
  subCategoryUserPreviewRowId.value = null;
  subCategoryUserPreviewValues.value = {};
  subCategoryUserPreviewActiveGroupId.value = "";
}

async function applySubCategoryUserPreview() {
  const row = activeSubCategoryUserPreviewRow.value;
  if (!row) return;
  ensureSubCategoryParamDefaults(row);
  for (const column of constructionSubCategoryParamColumns.value) {
    const override = row.param_overrides?.[column.key] || {};
    const nextValue = String(subCategoryUserPreviewValues.value?.[column.key] ?? "").trim();
    row.param_defaults[column.key] = override.input_mode === "binary"
      ? (nextValue === "1" ? "1" : "0")
      : nextValue;
  }
  markConstructionSubCategoryDirty(row);
  try {
    await persistSubCategoryRow(row);
  } catch (error) {
    showAlert(error?.message || "ذخیره پیش‌فرض‌های ساب‌کت انجام نشد.", { title: "خطا" });
    return;
  }
  subCategoryUserPreviewOpen.value = false;
  subCategoryUserPreviewRowId.value = null;
  subCategoryUserPreviewValues.value = {};
  subCategoryUserPreviewActiveGroupId.value = "";
}

function setSubCategoryUserPreviewBinaryValue(paramCode, value) {
  if (!paramCode) return;
  subCategoryUserPreviewValues.value = {
    ...subCategoryUserPreviewValues.value,
    [paramCode]: String(value) === "1" ? "1" : "0",
  };
}

function selectSubCategoryUserPreviewGroup(groupId) {
  subCategoryUserPreviewActiveGroupId.value = String(groupId || "");
}

function selectInternalPartGroupDefaultsGroup(groupId) {
  internalPartGroupDefaultsActiveGroupId.value = String(groupId || "");
}

function setInternalPartGroupBinaryDefault(paramCode, value) {
  const key = String(paramCode || "").trim();
  if (!key) return;
  internalPartGroupDefaultsValues.value = {
    ...internalPartGroupDefaultsValues.value,
    [key]: String(value) === "1" ? "1" : "0",
  };
}

async function persistInternalPartGroupRow(row) {
  if (!row?.id) throw new Error("Internal part group row is missing.");
  const payload = normalizeInternalPartGroupPayload(row);
  const res = await fetch(`/api/internal-part-groups/${encodeURIComponent(String(row.id))}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    throw new Error(await readApiErrorMessage(res, "ذخیره پیش‌فرض‌های گروه قطعات داخلی انجام نشد."));
  }
  const savedRow = ensureInternalPartGroupControllerConfig(ensureInternalPartGroupParamDefaults(withConstructionDraftState(await res.json())));
  editableInternalPartGroups.value = editableInternalPartGroups.value.map((item) =>
    String(item.id) === String(savedRow.id) ? savedRow : item
  );
  return savedRow;
}

async function applyInternalPartGroupDefaultsEditor() {
  const row = activeInternalPartGroupDefaultsRow.value;
  if (!row || internalPartGroupDefaultsApplying.value) return;
  internalPartGroupDefaultsApplying.value = true;
  ensureInternalPartGroupParamDefaults(row);
  for (const column of getInternalPartGroupSelectedParamColumns(row)) {
    const override = row.param_overrides?.[column.key] || {};
    const nextValue = String(internalPartGroupDefaultsValues.value?.[column.key] ?? "").trim();
    row.param_defaults[column.key] = override.input_mode === "binary"
      ? (nextValue === "1" ? "1" : "0")
      : nextValue;
  }
  try {
    await persistInternalPartGroupRow(row);
  } catch (error) {
    showAlert(error?.message || "ذخیره پیش‌فرض‌های گروه قطعات داخلی انجام نشد.", { title: "خطا" });
    internalPartGroupDefaultsApplying.value = false;
    return;
  }
  resetInternalPartGroupDefaultsEditorState();
}

function setSubCategoryDefaultInputMode(paramCode, mode) {
  const key = String(paramCode || "").trim();
  if (!key || !subCategoryDefaultsEditorOverridesDraft.value[key]) return;
  subCategoryDefaultsEditorOverridesDraft.value[key].input_mode = mode === "binary" ? "binary" : "value";
  subCategoryDefaultsEditorOverridesDraft.value[key].binary_off_label = String(subCategoryDefaultsEditorOverridesDraft.value[key].binary_off_label || "").trim() || "0";
  subCategoryDefaultsEditorOverridesDraft.value[key].binary_on_label = String(subCategoryDefaultsEditorOverridesDraft.value[key].binary_on_label || "").trim() || "1";
  if (subCategoryDefaultsEditorOverridesDraft.value[key].input_mode === "binary") {
    const current = String(subCategoryDefaultsEditorDraft.value?.[key] ?? "").trim();
    subCategoryDefaultsEditorDraft.value[key] = current === "1" ? "1" : "0";
  }
}

function setSubCategoryBinaryDefault(paramCode, value) {
  const key = String(paramCode || "").trim();
  if (!key) return;
  subCategoryDefaultsEditorDraft.value[key] = String(value) === "1" ? "1" : "0";
}

function validateConstructionSubCategories() {
  const templateIds = new Set(constructionTemplates.value.map((item) => Number(item.temp_id)).filter((value) => Number.isInteger(value) && value > 0));
  const categoryPairs = new Set(
    constructionCategories.value.map((item) => `${Number(item.temp_id)}::${Number(item.cat_id)}`)
  );
  for (const item of editableSubCategories.value) {
    const tempId = Number(item.temp_id);
    const catId = Number(item.cat_id);
    const subCatId = Number(item.sub_cat_id);
    const title = String(item.sub_cat_title || "").trim();
    if (!Number.isInteger(tempId) || tempId < 1 || !templateIds.has(tempId)) {
      showAlert("برای همه ساب‌کت‌ها یک تمپلیت معتبر انتخاب کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!Number.isInteger(catId) || catId < 1 || !categoryPairs.has(`${tempId}::${catId}`)) {
      showAlert("برای همه ساب‌کت‌ها یک دسته معتبر انتخاب کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!Number.isInteger(subCatId) || subCatId < 1) {
      showAlert("برای همه ساب‌کت‌ها شناسه معتبر و بزرگ‌تر از صفر وارد کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!title) {
      showAlert("عنوان ساب‌کت نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
      return false;
    }
  }
  const ids = editableSubCategories.value.map((item) => Number(item.sub_cat_id));
  if (new Set(ids).size !== ids.length) {
    showAlert("شناسه ساب‌کت باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  const scopedTitles = editableSubCategories.value.map((item) => `${Number(item.cat_id)}::${String(item.admin_id || "system")}::${String(item.sub_cat_title || "").trim().toLowerCase()}`);
  if (new Set(scopedTitles).size !== scopedTitles.length) {
    showAlert("عنوان ساب‌کت در هر دسته و محدوده مالک باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  return true;
}

function toggleConstructionPartFormulaScope(item) {
  item.admin_id = item.admin_id === null ? currentAdminId.value : null;
  item.is_system = item.admin_id === null;
  if (!item.__isNew) item.__dirty = true;
}

function validateConstructionParams() {
  for (const item of editableParams.value) {
    const paramId = Number(item.param_id);
    const partKindId = Number(item.part_kind_id);
    const paramGroupId = Number(item.param_group_id);
    const sortOrder = Number(item.sort_order);
    const paramCode = String(item.param_code || "").trim();
    const titleEn = String(item.param_title_en || "").trim();
    const titleFa = String(item.param_title_fa || "").trim();
    if (!Number.isInteger(paramId) || paramId < 1) {
      showAlert("برای همه پارامترها شناسه معتبر و بزرگ‌تر از صفر وارد کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!Number.isInteger(partKindId) || partKindId < 1) {
      showAlert("برای همه پارامترها آی‌دی نوع قطعه معتبر وارد کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!Number.isInteger(paramGroupId) || paramGroupId < 1) {
      showAlert("برای همه پارامترها آی‌دی گروه پارامتر معتبر وارد کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!paramCode || !titleEn || !titleFa) {
      showAlert("کد، عنوان انگلیسی و عنوان فارسی پارامتر نباید خالی باشند.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!Number.isInteger(sortOrder) || sortOrder < 0) {
      showAlert("برای همه پارامترها ترتیب مرتب‌سازی معتبر و صفر یا بزرگ‌تر وارد کنید.", { title: "اعتبارسنجی" });
      return false;
    }
  }
  const ids = editableParams.value.map((item) => Number(item.param_id));
  if (new Set(ids).size !== ids.length) {
    showAlert("شناسه پارامتر باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  const codes = editableParams.value.map((item) => String(item.param_code || "").trim().toLowerCase());
  if (new Set(codes).size !== codes.length) {
    showAlert("کد پارامتر باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  return true;
}

function validateConstructionBaseFormulas() {
  for (const item of editableBaseFormulas.value) {
    const foId = Number(item.fo_id);
    const paramFormula = String(item.param_formula || "").trim();
    const formula = String(item.formula || "").trim();
    if (!Number.isInteger(foId) || foId < 1) {
      showAlert("برای همه فرمول‌های پایه شناسه معتبر و بزرگ‌تر از صفر وارد کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!paramFormula || !formula) {
      showAlert("کد فرمول و عبارت فرمول نباید خالی باشند.", { title: "اعتبارسنجی" });
      return false;
    }
    const formulaErrors = validateFormulaExpression(formula, new Set(editableParams.value
      .filter((param) => param.admin_id === null || param.admin_id === currentAdminId.value)
      .map((param) => String(param.param_code || "").trim())
      .filter(Boolean)));
    if (formulaErrors.length > 0) {
      showAlert(formulaErrors[0], { title: "اعتبارسنجی" });
      return false;
    }
  }
  const ids = editableBaseFormulas.value.map((item) => Number(item.fo_id));
  if (new Set(ids).size !== ids.length) {
    showAlert("شناسه فرمول پایه باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  const codes = editableBaseFormulas.value.map((item) => String(item.param_formula || "").trim().toLowerCase());
  if (new Set(codes).size !== codes.length) {
    showAlert("کد فرمول پایه باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  return true;
}

function validateConstructionPartFormulas() {
  for (const item of editablePartFormulas.value) {
    const errors = getPartFormulaValidationErrors(item, item.id);
    if (errors.length > 0) {
      showAlert(errors[0], { title: "اعتبارسنجی" });
      return false;
    }
  }
  return true;
}

function validateConstructionPartKinds() {
  for (const item of editablePartKinds.value) {
    const partKindId = Number(item.part_kind_id);
    const partKindCode = String(item.part_kind_code || "").trim();
    const orgTitle = String(item.org_part_kind_title || "").trim();
    if (!Number.isInteger(partKindId) || partKindId < 1) {
      showAlert("برای همه ردیف‌ها شناسه معتبر و بزرگ‌تر از صفر وارد کنید.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!partKindCode) {
      showAlert("کد نوع قطعه نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
      return false;
    }
    if (!orgTitle) {
      showAlert("عنوان نوع قطعه نمی‌تواند خالی باشد.", { title: "اعتبارسنجی" });
      return false;
    }
  }
  const ids = editablePartKinds.value.map((item) => Number(item.part_kind_id));
  if (new Set(ids).size !== ids.length) {
    showAlert("شناسه نوع قطعه باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  const codes = editablePartKinds.value.map((item) => String(item.part_kind_code || "").trim().toLowerCase());
  if (new Set(codes).size !== codes.length) {
    showAlert("کد نوع قطعه باید یکتا باشد.", { title: "اعتبارسنجی" });
    return false;
  }
  return true;
}

function getConstructionCsvHeaders() {
  if (constructionStep.value === "templates") {
    return ["temp_id", "temp_title", "admin_mode"];
  }
  if (constructionStep.value === "categories") {
    return ["temp_id", "cat_id", "cat_title", "design_outline_color", "admin_mode"];
  }
  if (constructionStep.value === "sub_categories") {
    return [
      "temp_id",
      "cat_id",
      "sub_cat_id",
      "sub_cat_title",
      ...constructionSubCategoryParamColumns.value.flatMap((item) => [
        item.key,
        `${item.key}__display_title`,
        `${item.key}__description_text`,
        `${item.key}__icon_path`,
        `${item.key}__input_mode`,
        `${item.key}__binary_off_label`,
        `${item.key}__binary_on_label`,
        `${item.key}__binary_off_icon_path`,
        `${item.key}__binary_on_icon_path`,
      ]),
      "admin_mode",
    ];
  }
  if (constructionStep.value === "part_formulas") {
    return ["part_formula_id", "part_kind_id", "part_sub_kind_id", "part_code", "part_title", ...PART_FORMULA_FIELDS.map((item) => item.key), "admin_mode"];
  }
  if (constructionStep.value === "base_formulas") {
    return ["fo_id", "param_formula", "formula", "admin_mode"];
  }
  if (constructionStep.value === "params") {
    return ["param_id", "part_kind_id", "param_code", "param_title_en", "param_title_fa", "param_group_id", "ui_order", "admin_mode"];
  }
  if (constructionStep.value === "param_groups") {
    return ["param_group_id", "param_group_code", "org_param_group_title", "param_group_icon_path", "ui_order", "show_in_order_attrs", "admin_mode"];
  }
  return ["part_kind_id", "part_kind_code", "org_part_kind_title", "is_internal", "admin_mode"];
}

function getConstructionCsvRows(items = null) {
  if (constructionStep.value === "templates") {
    const rows = items || constructionTemplates.value;
    return rows.map((item) => [
      Number(item.temp_id) || "",
      String(item.temp_title || "").trim(),
      item.admin_id === null ? "system" : "admin",
    ]);
  }
  if (constructionStep.value === "categories") {
    const rows = items || constructionCategories.value;
    return rows.map((item) => [
      Number(item.temp_id) || "",
      Number(item.cat_id) || "",
      String(item.cat_title || "").trim(),
      normalizeHexColor(item.design_outline_color),
      item.admin_id === null ? "system" : "admin",
    ]);
  }
  if (constructionStep.value === "sub_categories") {
    const rows = items || constructionSubCategories.value;
    return rows.map((item) => [
      Number(item.temp_id) || "",
      Number(item.cat_id) || "",
      Number(item.sub_cat_id) || "",
      String(item.sub_cat_title || "").trim(),
      ...constructionSubCategoryParamColumns.value.flatMap((column) => {
        const override = item.param_overrides?.[column.key] || {};
        return [
          String(item.param_defaults?.[column.key] ?? "").trim(),
          String(override.display_title || "").trim(),
          String(override.description_text || "").trim(),
          normalizeIconFileName(override.icon_path) || "",
          override.input_mode === "binary" ? "binary" : "value",
          String(override.binary_off_label || "").trim() || "0",
          String(override.binary_on_label || "").trim() || "1",
          normalizeIconFileName(override.binary_off_icon_path) || "",
          normalizeIconFileName(override.binary_on_icon_path) || "",
        ];
      }),
      item.admin_id === null ? "system" : "admin",
    ]);
  }
  if (constructionStep.value === "part_formulas") {
    const rows = items || constructionPartFormulas.value;
    return rows.map((item) => [
      Number(item.part_formula_id) || "",
      Number(item.part_kind_id) || "",
      Number(item.part_sub_kind_id) || "",
      String(item.part_code || "").trim(),
      String(item.part_title || "").trim(),
      ...PART_FORMULA_FIELDS.map((field) => String(item[field.key] || "").trim()),
      item.admin_id === null ? "system" : "admin",
    ]);
  }
  if (constructionStep.value === "base_formulas") {
    const rows = items || constructionBaseFormulas.value;
    return rows.map((item) => [
      Number(item.fo_id) || "",
      String(item.param_formula || "").trim(),
      String(item.formula || "").trim(),
      item.admin_id === null ? "system" : "admin",
    ]);
  }
  if (constructionStep.value === "params") {
    const rows = items || constructionParams.value;
    return rows.map((item) => [
      Number(item.param_id) || "",
      Number(item.part_kind_id) || "",
      String(item.param_code || "").trim(),
      String(item.param_title_en || "").trim(),
      String(item.param_title_fa || "").trim(),
      Number(item.param_group_id) || "",
      Number(item.ui_order) || 0,
      item.admin_id === null ? "system" : "admin",
    ]);
  }
  if (constructionStep.value === "param_groups") {
    const rows = items || constructionParamGroups.value;
      return rows.map((item) => [
        Number(item.param_group_id) || "",
        String(item.param_group_code || "").trim(),
        String(item.org_param_group_title || "").trim(),
        normalizeIconFileName(item.param_group_icon_path),
        Number(item.ui_order) || 0,
        normalizeBooleanFlag(item.show_in_order_attrs, true) ? 1 : 0,
        item.admin_id === null ? "system" : "admin",
      ]);
  }
  const rows = items || constructionPartKinds.value;
  return rows.map((item) => [
    Number(item.part_kind_id) || "",
    String(item.part_kind_code || "").trim(),
    String(item.org_part_kind_title || "").trim(),
    normalizeBooleanFlag(item.is_internal, false) ? 1 : 0,
    item.admin_id === null ? "system" : "admin",
  ]);
}

function getConstructionImportFileName() {
  if (constructionStep.value === "templates") return "templates_excel_template.csv";
  if (constructionStep.value === "categories") return "categories_excel_template.csv";
  if (constructionStep.value === "sub_categories") return "sub_categories_excel_template.csv";
  if (constructionStep.value === "part_formulas") return "part_formulas_excel_template.csv";
  if (constructionStep.value === "base_formulas") return "base_formulas_excel_template.csv";
  if (constructionStep.value === "params") return "params_excel_template.csv";
  if (constructionStep.value === "param_groups") return "param_groups_excel_template.csv";
  return "part_kinds_excel_template.csv";
}

function getConstructionImportTitle() {
  if (constructionStep.value === "templates") return "جدول تمپلیت‌ها";
  if (constructionStep.value === "categories") return "جدول دسته‌بندی‌ها";
  if (constructionStep.value === "sub_categories") return "جدول ساب‌کت‌ها";
  if (constructionStep.value === "part_formulas") return "جدول فرمول‌های قطعات";
  if (constructionStep.value === "base_formulas") return "جدول فرمول‌های پایه";
  if (constructionStep.value === "params") return "جدول پارامترها";
  return constructionStep.value === "param_groups" ? "جدول گروه پارامترها" : "جدول انواع قطعات";
}

function getConstructionImportErrorText() {
  if (constructionStep.value === "templates") {
    return "خواندن فایل اکسل تمپلیت‌ها انجام نشد. فقط فایل CSV خروجی همین جدول را آپلود کنید.";
  }
  if (constructionStep.value === "categories") {
    return "خواندن فایل اکسل دسته‌بندی‌ها انجام نشد. فقط فایل CSV خروجی همین جدول را آپلود کنید.";
  }
  if (constructionStep.value === "sub_categories") {
    return "خواندن فایل اکسل ساب‌کت‌ها انجام نشد. فقط فایل CSV خروجی همین جدول را آپلود کنید.";
  }
  if (constructionStep.value === "part_formulas") {
    return "خواندن فایل اکسل فرمول‌های قطعات انجام نشد. فقط فایل CSV خروجی همین جدول را آپلود کنید.";
  }
  if (constructionStep.value === "base_formulas") {
    return "خواندن فایل اکسل فرمول‌های پایه انجام نشد. فقط فایل CSV خروجی همین جدول را آپلود کنید.";
  }
  if (constructionStep.value === "params") {
    return "خواندن فایل اکسل پارامترها انجام نشد. فقط فایل CSV خروجی همین جدول را آپلود کنید.";
  }
  return constructionStep.value === "param_groups"
    ? "خواندن فایل اکسل گروه پارامترها انجام نشد. فقط فایل CSV خروجی همین جدول را آپلود کنید."
    : "خواندن فایل اکسل انجام نشد. فقط فایل CSV خروجی همین جدول را آپلود کنید.";
}

function escapeCsvCell(value) {
  const text = String(value ?? "");
  if (/[",\r\n]/.test(text)) {
    return `"${text.replaceAll('"', '""')}"`;
  }
  return text;
}

function buildCsvText(headers, rows) {
  const lines = [
    headers.map(escapeCsvCell).join(","),
    ...rows.map((row) => row.map(escapeCsvCell).join(",")),
  ];
  return `\uFEFF${lines.join("\r\n")}`;
}

function parseCsvText(text) {
  const rows = [];
  let current = [];
  let value = "";
  let inQuotes = false;
  const source = String(text || "").replace(/^\uFEFF/, "");
  for (let i = 0; i < source.length; i += 1) {
    const char = source[i];
    const next = source[i + 1];
    if (char === '"') {
      if (inQuotes && next === '"') {
        value += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === "," && !inQuotes) {
      current.push(value);
      value = "";
      continue;
    }
    if ((char === "\n" || char === "\r") && !inQuotes) {
      if (char === "\r" && next === "\n") i += 1;
      current.push(value);
      rows.push(current);
      current = [];
      value = "";
      continue;
    }
    value += char;
  }
  if (value.length > 0 || current.length > 0) {
    current.push(value);
    rows.push(current);
  }
  return rows.filter((row) => row.some((cell) => String(cell || "").trim() !== ""));
}

function triggerConstructionImport() {
  constructionImportInputEl.value?.click?.();
}

function clearConstructionImportPreview() {
  constructionImportPreviewRows.value = [];
  constructionImportFileName.value = "";
  constructionImportPreviewKind.value = null;
  if (constructionImportInputEl.value) constructionImportInputEl.value.value = "";
}

async function downloadConstructionExcelTemplate() {
  const path = constructionStep.value === "templates"
    ? `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/tables/templates/export`
    : constructionStep.value === "categories"
    ? `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/tables/categories/export`
    : constructionStep.value === "sub_categories"
    ? `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/tables/sub-categories/export`
    : constructionStep.value === "part_formulas"
    ? `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/tables/part-formulas/export`
    : constructionStep.value === "base_formulas"
    ? `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/tables/base-formulas/export`
    : constructionStep.value === "params"
      ? `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/tables/params/export`
      : constructionStep.value === "param_groups"
        ? `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/tables/param-groups/export`
        : `/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/tables/part-kinds/export`;
  try {
    const response = await fetch(path);
    if (!response.ok) throw new Error("download-failed");
    const blob = await response.blob();
    const fileName = getConstructionImportFileName();
    const objectUrl = window.URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = objectUrl;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.URL.revokeObjectURL(objectUrl);
  } catch (_) {
    showAlert(`دانلود فایل ${getConstructionImportTitle()} انجام نشد. از روشن بودن backend و بارگذاری کامل سرورها مطمئن شوید.`, {
      title: "دانلود اکسل",
    });
  }
}

async function onConstructionImportFileChange(event) {
  const file = event?.target?.files?.[0];
  if (!file) return;
  try {
    const text = await file.text();
    const rows = parseCsvText(text);
    if (rows.length < 2) throw new Error("empty-file");
    const headers = rows[0].map((value) => String(value || "").trim());
    const expected = getConstructionCsvHeaders();
    if (expected.some((header, index) => headers[index] !== header)) {
      throw new Error("invalid-headers");
    }
    let previewRows = [];
    if (constructionStep.value === "templates") {
      previewRows = rows.slice(1).map((row, index) => {
        const tempId = Number(row[0]);
        const tempTitle = String(row[1] || "").trim();
        const adminMode = String(row[2] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
        return {
          lineNo: index + 2,
          temp_id: tempId,
          temp_title: tempTitle,
          admin_mode: adminMode,
        };
      });
    } else if (constructionStep.value === "categories") {
      previewRows = rows.slice(1).map((row, index) => {
        const tempId = Number(row[0]);
        const catId = Number(row[1]);
        const catTitle = String(row[2] || "").trim();
        const designOutlineColor = normalizeHexColor(row[3]);
        const adminMode = String(row[4] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
        return {
          lineNo: index + 2,
          temp_id: tempId,
          cat_id: catId,
          cat_title: catTitle,
          design_outline_color: designOutlineColor,
          admin_mode: adminMode,
        };
      });
    } else if (constructionStep.value === "sub_categories") {
      const fixedColumnCount = 4;
      const perParamColumnCount = 9;
      const adminModeIndex = fixedColumnCount + (constructionSubCategoryParamColumns.value.length * perParamColumnCount);
      previewRows = rows.slice(1).map((row, index) => {
        const paramDefaults = {};
        const paramOverrides = {};
        constructionSubCategoryParamColumns.value.forEach((column, paramIndex) => {
          const offset = fixedColumnCount + (paramIndex * perParamColumnCount);
          paramDefaults[column.key] = String(row[offset] || "").trim();
          paramOverrides[column.key] = {
            display_title: String(row[offset + 1] || "").trim(),
            description_text: String(row[offset + 2] || "").trim(),
            icon_path: normalizeIconFileName(row[offset + 3]) || "",
            input_mode: String(row[offset + 4] || "").trim().toLowerCase() === "binary" ? "binary" : "value",
            binary_off_label: String(row[offset + 5] || "").trim() || "0",
            binary_on_label: String(row[offset + 6] || "").trim() || "1",
            binary_off_icon_path: normalizeIconFileName(row[offset + 7]) || "",
            binary_on_icon_path: normalizeIconFileName(row[offset + 8]) || "",
          };
        });
        return {
          lineNo: index + 2,
          temp_id: Number(row[0]),
          cat_id: Number(row[1]),
          sub_cat_id: Number(row[2]),
          sub_cat_title: String(row[3] || "").trim(),
          param_defaults: paramDefaults,
          param_overrides: paramOverrides,
          admin_mode: String(row[adminModeIndex] || "admin").trim().toLowerCase() === "system" ? "system" : "admin",
        };
      });
    } else if (constructionStep.value === "part_formulas") {
      const adminModeIndex = 5 + PART_FORMULA_FIELDS.length;
      previewRows = rows.slice(1).map((row, index) => {
        const adminMode = String(row[adminModeIndex] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
        return {
          lineNo: index + 2,
          part_formula_id: Number(row[0]),
          part_kind_id: Number(row[1]),
          part_sub_kind_id: Number(row[2]),
          part_code: String(row[3] || "").trim(),
          part_title: String(row[4] || "").trim(),
          formula_l: String(row[5] || "").trim(),
          formula_w: String(row[6] || "").trim(),
          formula_width: String(row[7] || "").trim(),
          formula_depth: String(row[8] || "").trim(),
          formula_height: String(row[9] || "").trim(),
          formula_cx: String(row[10] || "").trim(),
          formula_cy: String(row[11] || "").trim(),
          formula_cz: String(row[12] || "").trim(),
          admin_mode: adminMode,
        };
      });
    } else if (constructionStep.value === "params") {
      previewRows = rows.slice(1).map((row, index) => {
        const adminMode = String(row[7] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
        return {
          lineNo: index + 2,
          param_id: Number(row[0]),
          part_kind_id: Number(row[1]),
          param_code: String(row[2] || "").trim(),
          param_title_en: String(row[3] || "").trim(),
          param_title_fa: String(row[4] || "").trim(),
          param_group_id: Number(row[5]),
          interior_value_mode: "formula",
          ui_order: Number(row[6]),
          admin_mode: adminMode,
        };
      });
    } else if (constructionStep.value === "base_formulas") {
      previewRows = rows.slice(1).map((row, index) => {
        const foId = Number(row[0]);
        const paramFormula = String(row[1] || "").trim();
        const formula = String(row[2] || "").trim();
        const adminMode = String(row[3] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
        return {
          lineNo: index + 2,
          fo_id: foId,
          param_formula: paramFormula,
          formula,
          admin_mode: adminMode,
        };
      });
    } else if (constructionStep.value === "params") {
      previewRows = rows.slice(1).map((row, index) => {
        const paramId = Number(row[0]);
        const partKindId = Number(row[1]);
        const paramCode = String(row[2] || "").trim();
        const paramTitleEn = String(row[3] || "").trim();
        const paramTitleFa = String(row[4] || "").trim();
        const paramGroupId = Number(row[5]);
        const uiOrder = Number(row[6]);
        const adminMode = String(row[7] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
        return {
          lineNo: index + 2,
          param_id: paramId,
          part_kind_id: partKindId,
          param_code: paramCode,
          param_title_en: paramTitleEn,
          param_title_fa: paramTitleFa,
          param_group_id: paramGroupId,
          ui_order: uiOrder,
          admin_mode: adminMode,
        };
      });
    } else if (constructionStep.value === "param_groups") {
      previewRows = rows.slice(1).map((row, index) => {
        const paramGroupId = Number(row[0]);
        const paramGroupCode = String(row[1] || "").trim();
        const orgTitle = String(row[2] || "").trim();
        const iconPath = String(row[3] || "").trim();
        const uiOrder = Number(row[4]);
        const showInOrderAttrs = normalizeBooleanFlag(row[5], true);
        const adminMode = String(row[6] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
        return {
          lineNo: index + 2,
          param_group_id: paramGroupId,
          param_group_code: paramGroupCode,
          org_param_group_title: orgTitle,
          param_group_icon_path: normalizeIconFileName(iconPath),
          ui_order: uiOrder,
          show_in_order_attrs: showInOrderAttrs,
          admin_mode: adminMode,
        };
      });
    } else {
      previewRows = rows.slice(1).map((row, index) => {
        const partKindId = Number(row[0]);
        const partKindCode = String(row[1] || "").trim();
        const orgPartKindTitle = String(row[2] || "").trim();
        const isInternal = normalizeBooleanFlag(row[3], false);
        const adminMode = String(row[4] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
        return {
          lineNo: index + 2,
          part_kind_id: partKindId,
          part_kind_code: partKindCode,
          org_part_kind_title: orgPartKindTitle,
          is_internal: isInternal,
          admin_mode: adminMode,
        };
      });
    }
    if (!previewRows.length) throw new Error("empty-file");
    const invalidRow = constructionStep.value === "templates"
      ? previewRows.find(
          (row) =>
            !Number.isInteger(row.temp_id) ||
            row.temp_id < 1 ||
            !row.temp_title
        )
      : constructionStep.value === "categories"
      ? previewRows.find(
          (row) =>
            !Number.isInteger(row.temp_id) ||
            row.temp_id < 1 ||
            !Number.isInteger(row.cat_id) ||
            row.cat_id < 1 ||
            !row.cat_title
        )
      : constructionStep.value === "sub_categories"
      ? previewRows.find(
          (row) =>
            !Number.isInteger(row.temp_id) ||
            row.temp_id < 1 ||
            !Number.isInteger(row.cat_id) ||
            row.cat_id < 1 ||
            !Number.isInteger(row.sub_cat_id) ||
            row.sub_cat_id < 1 ||
            !row.sub_cat_title
        )
      : constructionStep.value === "part_formulas"
      ? previewRows.find(
          (row) =>
            !Number.isInteger(row.part_formula_id) ||
            row.part_formula_id < 1 ||
            !Number.isInteger(row.part_kind_id) ||
            row.part_kind_id < 1 ||
            !Number.isInteger(row.part_sub_kind_id) ||
            row.part_sub_kind_id < 1 ||
            !row.part_code ||
            !row.part_title ||
            PART_FORMULA_FIELDS.some((field) => !String(row[field.key] || "").trim())
        )
      : constructionStep.value === "base_formulas"
      ? previewRows.find(
          (row) =>
            !Number.isInteger(row.fo_id) ||
            row.fo_id < 1 ||
            !row.param_formula ||
            !row.formula
        )
      : constructionStep.value === "params"
      ? previewRows.find(
          (row) =>
            !Number.isInteger(row.param_id) ||
            row.param_id < 1 ||
            !Number.isInteger(row.part_kind_id) ||
            row.part_kind_id < 1 ||
            !row.param_code ||
            !row.param_title_en ||
            !row.param_title_fa ||
            !Number.isInteger(row.param_group_id) ||
            row.param_group_id < 1 ||
            !Number.isFinite(row.ui_order)
        )
      : constructionStep.value === "param_groups"
      ? previewRows.find(
          (row) =>
            !Number.isInteger(row.param_group_id) ||
            row.param_group_id < 1 ||
            !row.param_group_code ||
            !row.org_param_group_title ||
            !Number.isFinite(row.ui_order) ||
            typeof row.show_in_order_attrs !== "boolean"
        )
      : previewRows.find(
          (row) =>
            !Number.isInteger(row.part_kind_id) ||
            row.part_kind_id < 1 ||
            !row.part_kind_code ||
            !row.org_part_kind_title ||
            typeof row.is_internal !== "boolean"
        );
    if (invalidRow) {
      throw new Error(`invalid-row-${invalidRow.lineNo}`);
    }
    constructionImportPreviewRows.value = previewRows;
    constructionImportFileName.value = file.name;
    constructionImportPreviewKind.value = constructionStep.value;
  } catch (error) {
    clearConstructionImportPreview();
    showAlert(getConstructionImportErrorText(), { title: "آپلود فایل" });
  }
}

function buildImportedConstructionDrafts(rows) {
  const existingByPartKindId = new Map(editablePartKinds.value.map((item) => [Number(item.part_kind_id), item]));
  const nextRows = rows.map((row, index) => {
    const existing = existingByPartKindId.get(Number(row.part_kind_id));
    const adminId = row.admin_mode === "system" ? null : currentAdminId.value;
    const nextPayload = {
      admin_id: adminId,
      part_kind_id: Number(row.part_kind_id),
      part_kind_code: String(row.part_kind_code || "").trim(),
      org_part_kind_title: String(row.org_part_kind_title || "").trim(),
      code: String(row.part_kind_code || "").trim(),
      title: String(row.org_part_kind_title || "").trim(),
      sort_order: index + 1,
      is_internal: normalizeBooleanFlag(row.is_internal, false),
      is_system: adminId === null,
    };
    if (!existing) {
      return buildPartKindDraft(nextPayload, {
        id: `draft-import-${Date.now()}-${index}`,
        __isNew: true,
        __dirty: false,
      });
    }
    const changed =
      existing.admin_id !== nextPayload.admin_id ||
      Number(existing.part_kind_id) !== nextPayload.part_kind_id ||
      String(existing.part_kind_code || "").trim() !== nextPayload.part_kind_code ||
      String(existing.org_part_kind_title || "").trim() !== nextPayload.org_part_kind_title ||
      Number(existing.sort_order) !== nextPayload.sort_order ||
      normalizeBooleanFlag(existing.is_internal, false) !== nextPayload.is_internal ||
      !!existing.is_system !== nextPayload.is_system;
    return buildPartKindDraft(existing, {
      ...nextPayload,
      __isNew: false,
      __dirty: changed,
    });
  });

  const importedExistingIds = new Set(
    nextRows.filter((item) => !item.__isNew).map((item) => String(item.id))
  );
  const deletedIds = editablePartKinds.value
    .filter((item) => !item.__isNew && !importedExistingIds.has(String(item.id)))
    .map((item) => String(item.id));

  return { nextRows, deletedIds };
}

function buildImportedConstructionTemplateDrafts(rows) {
  const existingById = new Map(editableTemplates.value.map((item) => [Number(item.temp_id), item]));
  const nextRows = rows.map((row, index) => {
    const existing = existingById.get(Number(row.temp_id));
    const adminId = row.admin_mode === "system" ? null : currentAdminId.value;
    const nextPayload = {
      admin_id: adminId,
      temp_id: Number(row.temp_id),
      temp_title: String(row.temp_title || "").trim(),
      code: `template_${Number(row.temp_id)}`,
      title: String(row.temp_title || "").trim(),
      sort_order: index + 1,
      is_system: adminId === null,
    };
    if (!existing) {
      return buildPartKindDraft(nextPayload, {
        id: `draft-template-${Date.now()}-${index}`,
        __isNew: true,
        __dirty: false,
      });
    }
    const changed =
      existing.admin_id !== nextPayload.admin_id ||
      Number(existing.temp_id) !== nextPayload.temp_id ||
      String(existing.temp_title || "").trim() !== nextPayload.temp_title ||
      Number(existing.sort_order) !== nextPayload.sort_order ||
      !!existing.is_system !== nextPayload.is_system;
    return buildPartKindDraft(existing, {
      ...nextPayload,
      __isNew: false,
      __dirty: changed,
    });
  });
  const importedExistingIds = new Set(nextRows.filter((item) => !item.__isNew).map((item) => String(item.id)));
  const deletedIds = editableTemplates.value
    .filter((item) => !item.__isNew && !importedExistingIds.has(String(item.id)))
    .map((item) => String(item.id));
  return { nextRows, deletedIds };
}

function buildImportedConstructionParamGroupDrafts(rows) {
  const existingById = new Map(editableParamGroups.value.map((item) => [Number(item.param_group_id), item]));
  const nextRows = rows.map((row, index) => {
    const existing = existingById.get(Number(row.param_group_id));
    const adminId = row.admin_mode === "system" ? null : currentAdminId.value;
    const nextPayload = {
      admin_id: adminId,
      param_group_id: Number(row.param_group_id),
      param_group_code: String(row.param_group_code || "").trim(),
      org_param_group_title: String(row.org_param_group_title || "").trim(),
      param_group_icon_path: normalizeIconFileName(row.param_group_icon_path) || null,
      ui_order: Number(row.ui_order),
      show_in_order_attrs: normalizeBooleanFlag(row.show_in_order_attrs, true),
      code: String(row.param_group_code || "").trim(),
      title: String(row.org_param_group_title || "").trim(),
      sort_order: index + 1,
      is_system: adminId === null,
    };
    if (!existing) {
      return buildPartKindDraft(nextPayload, {
        id: `draft-param-import-${Date.now()}-${index}`,
        __isNew: true,
        __dirty: false,
      });
    }
    const changed =
      existing.admin_id !== nextPayload.admin_id ||
      Number(existing.param_group_id) !== nextPayload.param_group_id ||
      String(existing.param_group_code || "").trim() !== nextPayload.param_group_code ||
      String(existing.org_param_group_title || "").trim() !== nextPayload.org_param_group_title ||
      normalizeIconFileName(existing.param_group_icon_path) !== normalizeIconFileName(nextPayload.param_group_icon_path) ||
      Number(existing.ui_order) !== nextPayload.ui_order ||
      normalizeBooleanFlag(existing.show_in_order_attrs, true) !== nextPayload.show_in_order_attrs ||
      Number(existing.sort_order) !== nextPayload.sort_order ||
      !!existing.is_system !== nextPayload.is_system;
    return buildPartKindDraft(existing, {
      ...nextPayload,
      __isNew: false,
      __dirty: changed,
    });
  });
  const importedExistingIds = new Set(nextRows.filter((item) => !item.__isNew).map((item) => String(item.id)));
  const deletedIds = editableParamGroups.value
    .filter((item) => !item.__isNew && !importedExistingIds.has(String(item.id)))
    .map((item) => String(item.id));
  return { nextRows, deletedIds };
}

function buildImportedConstructionParamDrafts(rows) {
  const existingById = new Map(editableParams.value.map((item) => [Number(item.param_id), item]));
  const nextRows = rows.map((row, index) => {
    const existing = existingById.get(Number(row.param_id));
    const adminId = row.admin_mode === "system" ? null : currentAdminId.value;
    const nextPayload = {
      admin_id: adminId,
      param_id: Number(row.param_id),
      part_kind_id: Number(row.part_kind_id),
      param_code: String(row.param_code || "").trim(),
      param_title_en: String(row.param_title_en || "").trim(),
      param_title_fa: String(row.param_title_fa || "").trim(),
      param_group_id: Number(row.param_group_id),
      interior_value_mode: "formula",
      ui_order: Number(row.ui_order),
      code: String(row.param_code || "").trim(),
      title: String(row.param_title_fa || "").trim(),
      sort_order: index + 1,
      is_system: adminId === null,
    };
    if (!existing) {
      return buildPartKindDraft(nextPayload, {
        id: `draft-param-${Date.now()}-${index}`,
        __isNew: true,
        __dirty: false,
      });
    }
    const changed =
      existing.admin_id !== nextPayload.admin_id ||
      Number(existing.param_id) !== nextPayload.param_id ||
      Number(existing.part_kind_id) !== nextPayload.part_kind_id ||
      String(existing.param_code || "").trim() !== nextPayload.param_code ||
      String(existing.param_title_en || "").trim() !== nextPayload.param_title_en ||
      String(existing.param_title_fa || "").trim() !== nextPayload.param_title_fa ||
      Number(existing.param_group_id) !== nextPayload.param_group_id ||
      Number(existing.ui_order) !== nextPayload.ui_order ||
      Number(existing.sort_order) !== nextPayload.sort_order ||
      !!existing.is_system !== nextPayload.is_system;
    return buildPartKindDraft(existing, {
      ...nextPayload,
      __isNew: false,
      __dirty: changed,
    });
  });
  const importedExistingIds = new Set(nextRows.filter((item) => !item.__isNew).map((item) => String(item.id)));
  const deletedIds = editableParams.value
    .filter((item) => !item.__isNew && !importedExistingIds.has(String(item.id)))
    .map((item) => String(item.id));
  return { nextRows, deletedIds };
}

function buildImportedConstructionBaseFormulaDrafts(rows) {
  const existingById = new Map(editableBaseFormulas.value.map((item) => [Number(item.fo_id), item]));
  const nextRows = rows.map((row, index) => {
    const existing = existingById.get(Number(row.fo_id));
    const adminId = row.admin_mode === "system" ? null : currentAdminId.value;
    const nextPayload = {
      admin_id: adminId,
      fo_id: Number(row.fo_id),
      param_formula: String(row.param_formula || "").trim(),
      formula: String(row.formula || "").trim(),
      code: String(row.param_formula || "").trim(),
      title: String(row.param_formula || "").trim(),
      sort_order: index + 1,
      is_system: adminId === null,
    };
    if (!existing) {
      return buildPartKindDraft(nextPayload, {
        id: `draft-base-formula-${Date.now()}-${index}`,
        __isNew: true,
        __dirty: false,
      });
    }
    const changed =
      existing.admin_id !== nextPayload.admin_id ||
      Number(existing.fo_id) !== nextPayload.fo_id ||
      String(existing.param_formula || "").trim() !== nextPayload.param_formula ||
      String(existing.formula || "").trim() !== nextPayload.formula ||
      Number(existing.sort_order) !== nextPayload.sort_order ||
      !!existing.is_system !== nextPayload.is_system;
    return buildPartKindDraft(existing, {
      ...nextPayload,
      __isNew: false,
      __dirty: changed,
    });
  });
  const importedExistingIds = new Set(nextRows.filter((item) => !item.__isNew).map((item) => String(item.id)));
  const deletedIds = editableBaseFormulas.value
    .filter((item) => !item.__isNew && !importedExistingIds.has(String(item.id)))
    .map((item) => String(item.id));
  return { nextRows, deletedIds };
}

function buildImportedConstructionPartFormulaDrafts(rows) {
  const existingById = new Map(editablePartFormulas.value.map((item) => [Number(item.part_formula_id), item]));
  const nextRows = rows.map((row, index) => {
    const existing = existingById.get(Number(row.part_formula_id));
    const adminId = row.admin_mode === "system" ? null : currentAdminId.value;
    const nextPayload = {
      admin_id: adminId,
      part_formula_id: Number(row.part_formula_id),
      part_kind_id: Number(row.part_kind_id),
      part_sub_kind_id: Number(row.part_sub_kind_id),
      part_code: String(row.part_code || "").trim(),
      part_title: String(row.part_title || "").trim(),
      code: String(row.part_code || "").trim(),
      title: String(row.part_title || "").trim(),
      sort_order: index + 1,
      is_system: adminId === null,
    };
    for (const field of PART_FORMULA_FIELDS) {
      nextPayload[field.key] = String(row[field.key] || "").trim();
    }
    if (!existing) {
      return buildPartKindDraft(nextPayload, {
        id: `draft-part-formula-${Date.now()}-${index}`,
        __isNew: true,
        __dirty: false,
      });
    }
    const changed = (
      existing.admin_id !== nextPayload.admin_id ||
      Number(existing.part_formula_id) !== nextPayload.part_formula_id ||
      Number(existing.part_kind_id) !== nextPayload.part_kind_id ||
      Number(existing.part_sub_kind_id) !== nextPayload.part_sub_kind_id ||
      String(existing.part_code || "").trim() !== nextPayload.part_code ||
      String(existing.part_title || "").trim() !== nextPayload.part_title ||
      Number(existing.sort_order) !== nextPayload.sort_order ||
      !!existing.is_system !== nextPayload.is_system ||
      PART_FORMULA_FIELDS.some((field) => String(existing[field.key] || "").trim() !== nextPayload[field.key])
    );
    return buildPartKindDraft(existing, {
      ...nextPayload,
      __isNew: false,
      __dirty: changed,
    });
  });
  const importedExistingIds = new Set(nextRows.filter((item) => !item.__isNew).map((item) => String(item.id)));
  const deletedIds = editablePartFormulas.value
    .filter((item) => !item.__isNew && !importedExistingIds.has(String(item.id)))
    .map((item) => String(item.id));
  return { nextRows, deletedIds };
}

function buildImportedConstructionCategoryDrafts(rows) {
  const existingById = new Map(editableCategories.value.map((item) => [Number(item.cat_id), item]));
  const nextRows = rows.map((row, index) => {
    const existing = existingById.get(Number(row.cat_id));
    const adminId = row.admin_mode === "system" ? null : currentAdminId.value;
    const nextPayload = {
      admin_id: adminId,
      temp_id: Number(row.temp_id),
      cat_id: Number(row.cat_id),
      cat_title: String(row.cat_title || "").trim(),
      design_outline_color: normalizeHexColor(row.design_outline_color),
      code: `category_${Number(row.cat_id)}`,
      title: String(row.cat_title || "").trim(),
      sort_order: index + 1,
      is_system: adminId === null,
    };
    if (!existing) {
      return buildPartKindDraft(nextPayload, {
        id: `draft-category-${Date.now()}-${index}`,
        __isNew: true,
        __dirty: false,
      });
    }
    const changed =
      existing.admin_id !== nextPayload.admin_id ||
      Number(existing.temp_id) !== nextPayload.temp_id ||
      Number(existing.cat_id) !== nextPayload.cat_id ||
      String(existing.cat_title || "").trim() !== nextPayload.cat_title ||
      normalizeHexColor(existing.design_outline_color) !== nextPayload.design_outline_color ||
      Number(existing.sort_order) !== nextPayload.sort_order ||
      !!existing.is_system !== nextPayload.is_system;
    return buildPartKindDraft(existing, {
      ...nextPayload,
      __isNew: false,
      __dirty: changed,
    });
  });
  const importedExistingIds = new Set(nextRows.filter((item) => !item.__isNew).map((item) => String(item.id)));
  const deletedIds = editableCategories.value
    .filter((item) => !item.__isNew && !importedExistingIds.has(String(item.id)))
    .map((item) => String(item.id));
  return { nextRows, deletedIds };
}

function buildImportedConstructionSubCategoryDrafts(rows) {
  const existingById = new Map(editableSubCategories.value.map((item) => [Number(item.sub_cat_id), item]));
  const nextRows = rows.map((row, index) => {
    const existing = existingById.get(Number(row.sub_cat_id));
    const adminId = row.admin_mode === "system" ? null : currentAdminId.value;
    const nextPayload = {
      admin_id: adminId,
      temp_id: Number(row.temp_id),
      cat_id: Number(row.cat_id),
      sub_cat_id: Number(row.sub_cat_id),
      sub_cat_title: String(row.sub_cat_title || "").trim(),
      code: `sub_category_${Number(row.sub_cat_id)}`,
      title: String(row.sub_cat_title || "").trim(),
      sort_order: index + 1,
      is_system: adminId === null,
      param_defaults: { ...(row.param_defaults || {}) },
      param_overrides: row.param_overrides ? { ...(row.param_overrides || {}) } : existing?.param_overrides ? { ...(existing.param_overrides || {}) } : {},
    };
    if (!existing) {
      return ensureSubCategoryParamDefaults(buildPartKindDraft(nextPayload, {
        id: `draft-sub-category-${Date.now()}-${index}`,
        __isNew: true,
        __dirty: false,
      }));
    }
    const existingDefaults = existing.param_defaults || {};
    const existingOverrides = existing.param_overrides || {};
    const changed =
      existing.admin_id !== nextPayload.admin_id ||
      Number(existing.temp_id) !== nextPayload.temp_id ||
      Number(existing.cat_id) !== nextPayload.cat_id ||
      Number(existing.sub_cat_id) !== nextPayload.sub_cat_id ||
      String(existing.sub_cat_title || "").trim() !== nextPayload.sub_cat_title ||
      Number(existing.sort_order) !== nextPayload.sort_order ||
      !!existing.is_system !== nextPayload.is_system ||
      constructionSubCategoryParamColumns.value.some((column) => {
        const prevOverride = existingOverrides[column.key] || {};
        const nextOverride = nextPayload.param_overrides[column.key] || {};
        return String(existingDefaults[column.key] ?? "").trim() !== String(nextPayload.param_defaults[column.key] ?? "").trim()
          || String(prevOverride.display_title || "").trim() !== String(nextOverride.display_title || "").trim()
          || String(prevOverride.description_text || "").trim() !== String(nextOverride.description_text || "").trim()
          || String(normalizeIconFileName(prevOverride.icon_path) || "") !== String(normalizeIconFileName(nextOverride.icon_path) || "")
          || String(prevOverride.input_mode || "value") !== String(nextOverride.input_mode || "value")
          || String(prevOverride.binary_off_label || "0").trim() !== String(nextOverride.binary_off_label || "0").trim()
          || String(prevOverride.binary_on_label || "1").trim() !== String(nextOverride.binary_on_label || "1").trim()
          || String(normalizeIconFileName(prevOverride.binary_off_icon_path) || "") !== String(normalizeIconFileName(nextOverride.binary_off_icon_path) || "")
          || String(normalizeIconFileName(prevOverride.binary_on_icon_path) || "") !== String(normalizeIconFileName(nextOverride.binary_on_icon_path) || "");
      });
    return ensureSubCategoryParamDefaults(buildPartKindDraft(existing, {
      ...nextPayload,
      __isNew: false,
      __dirty: changed,
    }));
  });
  const importedExistingIds = new Set(nextRows.filter((item) => !item.__isNew).map((item) => String(item.id)));
  const deletedIds = editableSubCategories.value
    .filter((item) => !item.__isNew && !importedExistingIds.has(String(item.id)))
    .map((item) => String(item.id));
  return { nextRows, deletedIds };
}

async function loadConstructionTemplates() {
  constructionLoading.value = true;
  try {
    const url = `/api/templates?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    editableTemplates.value = (await res.json()).map(withConstructionDraftState);
    constructionDeletedTemplateIds.value = [];
  } catch (_) {
    showAlert("خواندن جدول تمپلیت‌ها از دیتابیس انجام نشد.", { title: "خطا" });
  } finally {
    constructionLoading.value = false;
  }
}

async function loadConstructionCategories() {
  try {
    const url = `/api/categories?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    editableCategories.value = (await res.json()).map((item) => withConstructionDraftState({
      ...item,
      design_outline_color: normalizeHexColor(item.design_outline_color),
    }));
    constructionDeletedCategoryIds.value = [];
  } catch (_) {
    showAlert("خواندن جدول دسته‌بندی‌ها از دیتابیس انجام نشد.", { title: "خطا" });
  }
}

async function loadConstructionPartKinds() {
  constructionLoading.value = true;
  try {
    const url = `/api/part-kinds?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    editablePartKinds.value = (await res.json()).map((item) => withConstructionDraftState({
      ...item,
      is_internal: normalizeBooleanFlag(item.is_internal, false),
    }));
    constructionDeletedPartKindIds.value = [];
  } catch (_) {
    showAlert("خواندن جدول انواع قطعات از دیتابیس انجام نشد.", { title: "خطا" });
  } finally {
    constructionLoading.value = false;
  }
}

async function loadConstructionParamGroups() {
  try {
    const url = `/api/param-groups?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    editableParamGroups.value = (await res.json()).map((item) =>
      withConstructionDraftState({
        ...item,
        param_group_icon_path: normalizeIconFileName(item.param_group_icon_path),
        show_in_order_attrs: normalizeBooleanFlag(item.show_in_order_attrs, true),
      })
    );
    constructionDeletedParamGroupIds.value = [];
  } catch (_) {
    showAlert("خواندن جدول گروه پارامترها از دیتابیس انجام نشد.", { title: "خطا" });
  }
}

async function loadConstructionParams() {
  try {
    const url = `/api/params?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    editableParams.value = (await res.json()).map((item) =>
      withConstructionDraftState({
        ...item,
        interior_value_mode: "formula",
      })
    );
    constructionDeletedParamIds.value = [];
  } catch (_) {
    showAlert("خواندن جدول پارامترها از دیتابیس انجام نشد.", { title: "خطا" });
  }
}

async function loadConstructionSubCategories() {
  try {
    const url = `/api/sub-categories?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    editableSubCategories.value = (await res.json()).map((item) => ensureSubCategoryParamDefaults(withConstructionDraftState(item)));
    constructionDeletedSubCategoryIds.value = [];
  } catch (_) {
    showAlert("خواندن جدول ساب‌کت‌ها از دیتابیس انجام نشد.", { title: "خطا" });
  }
}

async function loadConstructionBaseFormulas() {
  try {
    const url = `/api/base-formulas?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    editableBaseFormulas.value = (await res.json()).map(withConstructionDraftState);
    constructionDeletedBaseFormulaIds.value = [];
  } catch (_) {
    showAlert("خواندن جدول فرمول‌های پایه از دیتابیس انجام نشد.", { title: "خطا" });
  }
}

async function loadConstructionPartFormulas() {
  try {
    const url = `/api/part-formulas?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    editablePartFormulas.value = (await res.json()).map(withConstructionDraftState);
    constructionDeletedPartFormulaIds.value = [];
  } catch (_) {
    showAlert("خواندن جدول فرمول‌های قطعات از دیتابیس انجام نشد.", { title: "خطا" });
  }
}

function addConstructionTemplate() {
  const nextId = editableTemplates.value.reduce((max, item) => Math.max(max, Number(item.temp_id) || 0), 0) + 1;
  editableTemplates.value = [
    ...editableTemplates.value,
    {
      id: `draft-template-row-${Date.now()}-${nextId}`,
      admin_id: null,
      temp_id: nextId,
      temp_title: `تمپلیت ${toPersianDigits(nextId)}`,
      code: `template_${nextId}`,
      title: `تمپلیت ${toPersianDigits(nextId)}`,
      sort_order: nextId,
      is_system: true,
      __isNew: true,
      __dirty: false,
    },
  ];
}

function addConstructionCategory() {
  const nextId = editableCategories.value.reduce((max, item) => Math.max(max, Number(item.cat_id) || 0), 0) + 1;
  const fallbackTemplateId = Number(constructionTemplateOptions.value[0]?.value) || 1;
  editableCategories.value = [
    ...editableCategories.value,
    {
      id: `draft-category-row-${Date.now()}-${nextId}`,
      admin_id: currentAdminId.value,
      temp_id: fallbackTemplateId,
      cat_id: nextId,
      cat_title: `دسته ${toPersianDigits(nextId)}`,
      design_outline_color: DEFAULT_SUB_CATEGORY_DESIGN_OUTLINE_COLOR,
      code: `category_${nextId}`,
      title: `دسته ${toPersianDigits(nextId)}`,
      sort_order: nextId,
      is_system: false,
      __isNew: true,
      __dirty: false,
    },
  ];
}

function addConstructionSubCategory() {
  const nextId = editableSubCategories.value.reduce((max, item) => Math.max(max, Number(item.sub_cat_id) || 0), 0) + 1;
  const fallbackCategory = constructionCategories.value[0];
  const latestSubCategory = constructionSubCategories.value[constructionSubCategories.value.length - 1] || null;
  const clonedDefaults = cloneSubCategoryDefaultsSeed(latestSubCategory);
  editableSubCategories.value = [
    ...editableSubCategories.value,
    ensureSubCategoryParamDefaults({
      id: `draft-sub-category-row-${Date.now()}-${nextId}`,
      admin_id: currentAdminId.value,
      temp_id: Number(fallbackCategory?.temp_id) || 1,
      cat_id: Number(fallbackCategory?.cat_id) || 1,
      sub_cat_id: nextId,
      sub_cat_title: `ساب‌کت ${toPersianDigits(nextId)}`,
      code: `sub_category_${nextId}`,
      title: `ساب‌کت ${toPersianDigits(nextId)}`,
      sort_order: nextId,
      is_system: false,
      param_defaults: clonedDefaults.param_defaults,
      param_overrides: clonedDefaults.param_overrides,
      __isNew: true,
      __dirty: false,
    }),
  ];
}

async function createConstructionPartKind() {
  const nextId = editablePartKinds.value.reduce((max, item) => Math.max(max, Number(item.part_kind_id) || 0), 0) + 1;
  editablePartKinds.value = [
    ...editablePartKinds.value,
    {
      id: `draft-${Date.now()}-${nextId}`,
      admin_id: currentAdminId.value,
      part_kind_id: nextId,
      part_kind_code: `custom_part_${nextId}`,
      org_part_kind_title: `نوع قطعه ${nextId}`,
      code: `custom_part_${nextId}`,
      title: `نوع قطعه ${nextId}`,
      sort_order: nextId,
      is_internal: false,
      is_system: false,
      __isNew: true,
      __dirty: false,
    },
  ];
}

function addConstructionParamGroup() {
  const nextId = editableParamGroups.value.reduce((max, item) => Math.max(max, Number(item.param_group_id) || 0), 0) + 1;
  editableParamGroups.value = [
    ...editableParamGroups.value,
    {
      id: `draft-param-group-${Date.now()}-${nextId}`,
      admin_id: currentAdminId.value,
      param_group_id: nextId,
      param_group_code: `param_group_${nextId}`,
      org_param_group_title: `گروه پارامتر ${toPersianDigits(nextId)}`,
      param_group_icon_path: "",
      ui_order: nextId - 1,
      show_in_order_attrs: true,
      code: `param_group_${nextId}`,
      title: `گروه پارامتر ${toPersianDigits(nextId)}`,
      sort_order: nextId,
      is_system: false,
      __isNew: true,
      __dirty: false,
    },
  ];
}

function addConstructionParam() {
  const nextId = editableParams.value.reduce((max, item) => Math.max(max, Number(item.param_id) || 0), 0) + 1;
  const nextSortOrder = editableParams.value.reduce((max, item) => Math.max(max, Number(item.sort_order) || 0), 0) + 1;
  const draftId = `draft-param-row-${Date.now()}-${nextId}`;
  editableParams.value = [
    ...editableParams.value,
    {
      id: draftId,
      admin_id: currentAdminId.value,
      param_id: nextId,
      part_kind_id: 1,
      param_code: `param_${nextId}`,
      param_title_en: `param_${nextId}`,
      param_title_fa: `پارامتر ${toPersianDigits(nextId)}`,
      param_group_id: 1,
      interior_value_mode: "formula",
      ui_order: 1,
      code: `param_${nextId}`,
      title: `پارامتر ${toPersianDigits(nextId)}`,
      sort_order: nextSortOrder,
      is_system: false,
      __isNew: true,
      __dirty: false,
    },
  ];
  nextTick(() => {
    const wrapEl = constructionParamsTableWrapEl.value;
    if (!wrapEl) return;
    const rowEl = wrapEl.querySelector(`[data-row-id="${draftId}"]`);
    if (rowEl && typeof rowEl.scrollIntoView === "function") {
      rowEl.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
      return;
    }
    wrapEl.scrollTo?.({ top: 0, behavior: "smooth" });
  });
}

function addConstructionBaseFormula() {
  openBaseFormulaBuilder(buildNewBaseFormulaDraft(), "create");
}

function addConstructionPartFormula() {
  openBaseFormulaBuilder(buildNewPartFormulaDraft(), "create", {
    entity: "part_formulas",
    field: "formula_l",
  });
}

async function readApiErrorMessage(response, fallbackMessage) {
  try {
    const payload = await response.json();
    if (typeof payload?.detail === "string" && payload.detail.trim()) return payload.detail.trim();
  } catch (_) {
    // ignore parsing errors and use fallback below
  }
  return fallbackMessage;
}

async function saveConstructionPartKinds(options = {}) {
  if (!constructionHasPendingChanges.value) {
    showAlert("تغییری برای ذخیره وجود ندارد.", { title: "ذخیره تغییرات" });
    return;
  }
  if (!validateConstructionPartKinds()) return;
  if (!options.skipConfirm) {
    const ok = await showConfirm("تغییرات جدول انواع قطعات در دیتابیس ذخیره شود؟", {
      title: "ذخیره تغییرات",
      confirmText: "ذخیره",
      cancelText: "انصراف",
    });
    if (!ok) return;
  }

  const draftIds = editablePartKinds.value
    .filter((item) => item.__isNew)
    .map((item) => String(item.id));
  const dirtyIds = editablePartKinds.value
    .filter((item) => !item.__isNew && item.__dirty)
    .map((item) => String(item.id));
  constructionSavingIds.value = [...new Set([...draftIds, ...dirtyIds])];
  try {
    for (const id of constructionDeletedPartKindIds.value) {
      const res = await fetch(`/api/part-kinds/${encodeURIComponent(String(id))}`, {
        method: "DELETE",
      });
      if (!res.ok) throw new Error("delete-failed");
    }

    for (const item of editablePartKinds.value.filter((row) => row.__isNew)) {
      const res = await fetch("/api/part-kinds", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizePartKindPayload(item)),
      });
      if (!res.ok) throw new Error("create-failed");
    }

    for (const item of editablePartKinds.value.filter((row) => !row.__isNew && row.__dirty)) {
      const res = await fetch(`/api/part-kinds/${encodeURIComponent(String(item.id))}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizePartKindPayload(item)),
      });
      if (!res.ok) throw new Error("save-failed");
    }

    await loadConstructionPartKinds();
    showAlert(options.successMessage || "تغییرات جدول انواع قطعات با موفقیت ذخیره شد.", {
      title: options.successTitle || "ذخیره تغییرات",
    });
  } catch (_) {
    showAlert("ذخیره تغییرات جدول انواع قطعات در دیتابیس انجام نشد.", { title: "خطا" });
    await loadConstructionPartKinds();
  } finally {
    constructionSavingIds.value = [];
  }
}

async function saveConstructionTemplates(options = {}) {
  if (!(constructionDeletedTemplateIds.value.length > 0 || editableTemplates.value.some((item) => !!item.__isNew || !!item.__dirty))) {
    showAlert("تغییری برای ذخیره وجود ندارد.", { title: "ذخیره تغییرات" });
    return;
  }
  if (!validateConstructionTemplates()) return;
  if (!options.skipConfirm) {
    const ok = await showConfirm("تغییرات جدول تمپلیت‌ها در دیتابیس ذخیره شود؟", {
      title: "ذخیره تغییرات",
      confirmText: "ذخیره",
      cancelText: "انصراف",
    });
    if (!ok) return;
  }
  const draftIds = editableTemplates.value.filter((item) => item.__isNew).map((item) => String(item.id));
  const dirtyIds = editableTemplates.value.filter((item) => !item.__isNew && item.__dirty).map((item) => String(item.id));
  constructionSavingIds.value = [...new Set([...draftIds, ...dirtyIds])];
  try {
    for (const id of constructionDeletedTemplateIds.value) {
      const res = await fetch(`/api/templates/${encodeURIComponent(String(id))}`, { method: "DELETE" });
      if (!res.ok) throw new Error("delete-failed");
    }
    for (const item of editableTemplates.value.filter((row) => row.__isNew)) {
      const res = await fetch("/api/templates", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeTemplatePayload(item)),
      });
      if (!res.ok) throw new Error("create-failed");
    }
    for (const item of editableTemplates.value.filter((row) => !row.__isNew && row.__dirty)) {
      const res = await fetch(`/api/templates/${encodeURIComponent(String(item.id))}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeTemplatePayload(item)),
      });
      if (!res.ok) throw new Error("save-failed");
    }
    await loadConstructionTemplates();
    await loadConstructionCategories();
    showAlert(options.successMessage || "تغییرات جدول تمپلیت‌ها با موفقیت ذخیره شد.", {
      title: options.successTitle || "ذخیره تغییرات",
    });
  } catch (_) {
    showAlert("ذخیره تغییرات جدول تمپلیت‌ها در دیتابیس انجام نشد.", { title: "خطا" });
    await loadConstructionTemplates();
    await loadConstructionCategories();
    await loadConstructionSubCategories();
  } finally {
    constructionSavingIds.value = [];
  }
}

async function saveConstructionCategories(options = {}) {
  if (!(constructionDeletedCategoryIds.value.length > 0 || editableCategories.value.some((item) => !!item.__isNew || !!item.__dirty))) {
    showAlert("تغییری برای ذخیره وجود ندارد.", { title: "ذخیره تغییرات" });
    return;
  }
  if (!validateConstructionCategories()) return;
  if (!options.skipConfirm) {
    const ok = await showConfirm("تغییرات جدول دسته‌بندی‌ها در دیتابیس ذخیره شود؟", {
      title: "ذخیره تغییرات",
      confirmText: "ذخیره",
      cancelText: "انصراف",
    });
    if (!ok) return;
  }
  const draftIds = editableCategories.value.filter((item) => item.__isNew).map((item) => String(item.id));
  const dirtyIds = editableCategories.value.filter((item) => !item.__isNew && item.__dirty).map((item) => String(item.id));
  constructionSavingIds.value = [...new Set([...draftIds, ...dirtyIds])];
  try {
    for (const id of constructionDeletedCategoryIds.value) {
      const res = await fetch(`/api/categories/${encodeURIComponent(String(id))}`, { method: "DELETE" });
      if (!res.ok) throw new Error("delete-failed");
    }
    for (const item of editableCategories.value.filter((row) => row.__isNew)) {
      const res = await fetch("/api/categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeCategoryPayload(item)),
      });
      if (!res.ok) throw new Error("create-failed");
    }
    for (const item of editableCategories.value.filter((row) => !row.__isNew && row.__dirty)) {
      const res = await fetch(`/api/categories/${encodeURIComponent(String(item.id))}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeCategoryPayload(item)),
      });
      if (!res.ok) throw new Error("save-failed");
    }
    await loadConstructionCategories();
    await loadConstructionSubCategories();
    await loadCabinetDesignCatalog(true);
    if (activeOrder.value?.id) await loadOrderDesignCatalog(true);
    showAlert(options.successMessage || "تغییرات جدول دسته‌بندی‌ها با موفقیت ذخیره شد.", {
      title: options.successTitle || "ذخیره تغییرات",
    });
  } catch (_) {
    showAlert("ذخیره تغییرات جدول دسته‌بندی‌ها در دیتابیس انجام نشد.", { title: "خطا" });
    await loadConstructionCategories();
    await loadConstructionSubCategories();
    await loadCabinetDesignCatalog(true);
    if (activeOrder.value?.id) await loadOrderDesignCatalog(true);
  } finally {
    constructionSavingIds.value = [];
  }
}

async function saveConstructionSubCategories(options = {}) {
  if (!(constructionDeletedSubCategoryIds.value.length > 0 || editableSubCategories.value.some((item) => !!item.__isNew || !!item.__dirty))) {
    showAlert("تغییری برای ذخیره وجود ندارد.", { title: "ذخیره تغییرات" });
    return;
  }
  if (!validateConstructionSubCategories()) return;
  if (!options.skipConfirm) {
    const ok = await showConfirm("تغییرات جدول ساب‌کت‌ها در دیتابیس ذخیره شود؟", {
      title: "ذخیره تغییرات",
      confirmText: "ذخیره",
      cancelText: "انصراف",
    });
    if (!ok) return;
  }
  const draftIds = editableSubCategories.value.filter((item) => item.__isNew).map((item) => String(item.id));
  const dirtyIds = editableSubCategories.value.filter((item) => !item.__isNew && item.__dirty).map((item) => String(item.id));
  constructionSavingIds.value = [...new Set([...draftIds, ...dirtyIds])];
  try {
    for (const id of constructionDeletedSubCategoryIds.value) {
      const res = await fetch(`/api/sub-categories/${encodeURIComponent(String(id))}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "حذف ساب‌کت انجام نشد."));
    }
    for (const item of editableSubCategories.value.filter((row) => row.__isNew)) {
      const res = await fetch("/api/sub-categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeSubCategoryPayload(item)),
      });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "ایجاد ساب‌کت انجام نشد."));
    }
    for (const item of editableSubCategories.value.filter((row) => !row.__isNew && row.__dirty)) {
      const res = await fetch(`/api/sub-categories/${encodeURIComponent(String(item.id))}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeSubCategoryPayload(item)),
      });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "ذخیره ساب‌کت انجام نشد."));
    }
    await loadConstructionSubCategories();
    showAlert(options.successMessage || "تغییرات جدول ساب‌کت‌ها با موفقیت ذخیره شد.", {
      title: options.successTitle || "ذخیره تغییرات",
    });
  } catch (error) {
    showAlert(error?.message || "ذخیره تغییرات جدول ساب‌کت‌ها در دیتابیس انجام نشد.", { title: "خطا" });
    await loadConstructionSubCategories();
  } finally {
    constructionSavingIds.value = [];
  }
}

async function saveConstructionParamGroups(options = {}) {
  if (!(constructionDeletedParamGroupIds.value.length > 0 || editableParamGroups.value.some((item) => !!item.__isNew || !!item.__dirty))) {
    showAlert("تغییری برای ذخیره وجود ندارد.", { title: "ذخیره تغییرات" });
    return;
  }
  if (!validateConstructionParamGroups()) return;
  if (!options.skipConfirm) {
    const ok = await showConfirm("تغییرات جدول گروه پارامترها در دیتابیس ذخیره شود؟", {
      title: "ذخیره تغییرات",
      confirmText: "ذخیره",
      cancelText: "انصراف",
    });
    if (!ok) return;
  }
  const draftIds = editableParamGroups.value.filter((item) => item.__isNew).map((item) => String(item.id));
  const dirtyIds = editableParamGroups.value.filter((item) => !item.__isNew && item.__dirty).map((item) => String(item.id));
  constructionSavingIds.value = [...new Set([...draftIds, ...dirtyIds])];
  try {
    for (const id of constructionDeletedParamGroupIds.value) {
      const res = await fetch(`/api/param-groups/${encodeURIComponent(String(id))}`, { method: "DELETE" });
      if (!res.ok) throw new Error("delete-failed");
    }
    for (const item of editableParamGroups.value.filter((row) => row.__isNew)) {
      const res = await fetch("/api/param-groups", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeParamGroupPayload(item)),
      });
      if (!res.ok) throw new Error("create-failed");
    }
    for (const item of editableParamGroups.value.filter((row) => !row.__isNew && row.__dirty)) {
      const res = await fetch(`/api/param-groups/${encodeURIComponent(String(item.id))}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeParamGroupPayload(item)),
      });
      if (!res.ok) throw new Error("save-failed");
    }
    await loadConstructionParamGroups();
    showAlert(options.successMessage || "تغییرات جدول گروه پارامترها با موفقیت ذخیره شد.", {
      title: options.successTitle || "ذخیره تغییرات",
    });
  } catch (_) {
    showAlert("ذخیره تغییرات جدول گروه پارامترها در دیتابیس انجام نشد.", { title: "خطا" });
    await loadConstructionParamGroups();
  } finally {
    constructionSavingIds.value = [];
  }
}

async function saveConstructionParams(options = {}) {
  if (!(constructionDeletedParamIds.value.length > 0 || editableParams.value.some((item) => !!item.__isNew || !!item.__dirty))) {
    showAlert("تغییری برای ذخیره وجود ندارد.", { title: "ذخیره تغییرات" });
    return;
  }
  if (!validateConstructionParams()) return;
  if (!options.skipConfirm) {
    const ok = await showConfirm("تغییرات جدول پارامترها در دیتابیس ذخیره شود؟", {
      title: "ذخیره تغییرات",
      confirmText: "ذخیره",
      cancelText: "انصراف",
    });
    if (!ok) return;
  }
  const draftIds = editableParams.value.filter((item) => item.__isNew).map((item) => String(item.id));
  const dirtyIds = editableParams.value.filter((item) => !item.__isNew && item.__dirty).map((item) => String(item.id));
  constructionSavingIds.value = [...new Set([...draftIds, ...dirtyIds])];
  try {
    for (const id of constructionDeletedParamIds.value) {
      const res = await fetch(`/api/params/${encodeURIComponent(String(id))}`, { method: "DELETE" });
      if (!res.ok) throw new Error("delete-failed");
    }
    for (const item of editableParams.value.filter((row) => row.__isNew)) {
      const res = await fetch("/api/params", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeParamPayload(item)),
      });
      if (!res.ok) throw new Error("create-failed");
    }
    for (const item of editableParams.value.filter((row) => !row.__isNew && row.__dirty)) {
      const res = await fetch(`/api/params/${encodeURIComponent(String(item.id))}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeParamPayload(item)),
      });
      if (!res.ok) throw new Error("save-failed");
    }
    await loadConstructionParams();
    await loadConstructionSubCategories();
    showAlert(options.successMessage || "تغییرات جدول پارامترها با موفقیت ذخیره شد.", {
      title: options.successTitle || "ذخیره تغییرات",
    });
  } catch (_) {
    showAlert("ذخیره تغییرات جدول پارامترها در دیتابیس انجام نشد.", { title: "خطا" });
    await loadConstructionParams();
    await loadConstructionSubCategories();
  } finally {
    constructionSavingIds.value = [];
  }
}

async function saveConstructionBaseFormulas(options = {}) {
  if (!(constructionDeletedBaseFormulaIds.value.length > 0 || editableBaseFormulas.value.some((item) => !!item.__isNew || !!item.__dirty))) {
    showAlert("تغییری برای ذخیره وجود ندارد.", { title: "ذخیره تغییرات" });
    return;
  }
  if (!validateConstructionBaseFormulas()) return;
  if (!options.skipConfirm) {
    const ok = await showConfirm("تغییرات جدول فرمول‌های پایه در دیتابیس ذخیره شود؟", {
      title: "ذخیره تغییرات",
      confirmText: "ذخیره",
      cancelText: "انصراف",
    });
    if (!ok) return;
  }
  const draftIds = editableBaseFormulas.value.filter((item) => item.__isNew).map((item) => String(item.id));
  const dirtyIds = editableBaseFormulas.value.filter((item) => !item.__isNew && item.__dirty).map((item) => String(item.id));
  constructionSavingIds.value = [...new Set([...draftIds, ...dirtyIds])];
  try {
    for (const id of constructionDeletedBaseFormulaIds.value) {
      const res = await fetch(`/api/base-formulas/${encodeURIComponent(String(id))}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "delete-failed"));
    }
    for (const item of editableBaseFormulas.value.filter((row) => row.__isNew)) {
      const res = await fetch("/api/base-formulas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeBaseFormulaPayload(item)),
      });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "create-failed"));
    }
    for (const item of editableBaseFormulas.value.filter((row) => !row.__isNew && row.__dirty)) {
      const res = await fetch(`/api/base-formulas/${encodeURIComponent(String(item.id))}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeBaseFormulaPayload(item)),
      });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "save-failed"));
    }
    await loadConstructionBaseFormulas();
    showAlert(options.successMessage || "تغییرات جدول فرمول‌های پایه با موفقیت ذخیره شد.", {
      title: options.successTitle || "ذخیره تغییرات",
    });
  } catch (error) {
    showAlert(error?.message || "ذخیره تغییرات جدول فرمول‌های پایه در دیتابیس انجام نشد.", { title: "خطا" });
    await loadConstructionBaseFormulas();
  } finally {
    constructionSavingIds.value = [];
  }
}

async function saveConstructionPartFormulas(options = {}) {
  if (!(constructionDeletedPartFormulaIds.value.length > 0 || editablePartFormulas.value.some((item) => !!item.__isNew || !!item.__dirty))) {
    showAlert("تغییری برای ذخیره وجود ندارد.", { title: "ذخیره تغییرات" });
    return;
  }
  if (!validateConstructionPartFormulas()) return;
  if (!options.skipConfirm) {
    const ok = await showConfirm("تغییرات جدول فرمول‌های قطعات در دیتابیس ذخیره شود؟", {
      title: "ذخیره تغییرات",
      confirmText: "ذخیره",
      cancelText: "انصراف",
    });
    if (!ok) return;
  }
  const draftIds = editablePartFormulas.value.filter((item) => item.__isNew).map((item) => String(item.id));
  const dirtyIds = editablePartFormulas.value.filter((item) => !item.__isNew && item.__dirty).map((item) => String(item.id));
  constructionSavingIds.value = [...new Set([...draftIds, ...dirtyIds])];
  try {
    for (const id of constructionDeletedPartFormulaIds.value) {
      const res = await fetch(`/api/part-formulas/${encodeURIComponent(String(id))}`, { method: "DELETE" });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "delete-failed"));
    }
    for (const item of editablePartFormulas.value.filter((row) => row.__isNew)) {
      const res = await fetch("/api/part-formulas", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizePartFormulaPayload(item)),
      });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "create-failed"));
    }
    for (const item of editablePartFormulas.value.filter((row) => !row.__isNew && row.__dirty)) {
      const res = await fetch(`/api/part-formulas/${encodeURIComponent(String(item.id))}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizePartFormulaPayload(item)),
      });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "save-failed"));
    }
    await loadConstructionPartFormulas();
    showAlert(options.successMessage || "تغییرات جدول فرمول‌های قطعات با موفقیت ذخیره شد.", {
      title: options.successTitle || "ذخیره تغییرات",
    });
  } catch (error) {
    showAlert(error?.message || "ذخیره تغییرات جدول فرمول‌های قطعات در دیتابیس انجام نشد.", { title: "خطا" });
    await loadConstructionPartFormulas();
  } finally {
    constructionSavingIds.value = [];
  }
}

async function applyConstructionImportPreview() {
  if (!constructionImportPreviewRows.value.length) return;
  const ok = await showConfirm(`پیش‌نمایش فایل اکسل روی ${getConstructionImportTitle()} اعمال شود؟`, {
    title: "تایید بروزرسانی",
    confirmText: "اعمال",
    cancelText: "انصراف",
  });
  if (!ok) return;
  if (constructionImportPreviewKind.value === "params") {
    const { nextRows, deletedIds } = buildImportedConstructionParamDrafts(constructionImportPreviewRows.value);
    editableParams.value = nextRows;
    constructionDeletedParamIds.value = deletedIds;
    clearConstructionImportPreview();
    await saveConstructionParams({
      skipConfirm: true,
      successTitle: "آپلود فایل",
      successMessage: "فایل اکسل پارامترها با موفقیت روی جدول اعمال شد.",
    });
    return;
  }
  if (constructionImportPreviewKind.value === "templates") {
    const { nextRows, deletedIds } = buildImportedConstructionTemplateDrafts(constructionImportPreviewRows.value);
    editableTemplates.value = nextRows;
    constructionDeletedTemplateIds.value = deletedIds;
    clearConstructionImportPreview();
    await saveConstructionTemplates({
      skipConfirm: true,
      successTitle: "آپلود فایل",
      successMessage: "فایل اکسل تمپلیت‌ها با موفقیت روی جدول اعمال شد.",
    });
    return;
  }
  if (constructionImportPreviewKind.value === "categories") {
    const { nextRows, deletedIds } = buildImportedConstructionCategoryDrafts(constructionImportPreviewRows.value);
    editableCategories.value = nextRows;
    constructionDeletedCategoryIds.value = deletedIds;
    clearConstructionImportPreview();
    await saveConstructionCategories({
      skipConfirm: true,
      successTitle: "آپلود فایل",
      successMessage: "فایل اکسل دسته‌بندی‌ها با موفقیت روی جدول اعمال شد.",
    });
    return;
  }
  if (constructionImportPreviewKind.value === "sub_categories") {
    const { nextRows, deletedIds } = buildImportedConstructionSubCategoryDrafts(constructionImportPreviewRows.value);
    editableSubCategories.value = nextRows;
    constructionDeletedSubCategoryIds.value = deletedIds;
    clearConstructionImportPreview();
    await saveConstructionSubCategories({
      skipConfirm: true,
      successTitle: "آپلود فایل",
      successMessage: "فایل اکسل ساب‌کت‌ها با موفقیت روی جدول اعمال شد.",
    });
    return;
  }
  if (constructionImportPreviewKind.value === "param_groups") {
    await cleanupStagedParamGroupUploads();
    const { nextRows, deletedIds } = buildImportedConstructionParamGroupDrafts(constructionImportPreviewRows.value);
    editableParamGroups.value = nextRows;
    constructionDeletedParamGroupIds.value = deletedIds;
    clearConstructionImportPreview();
    await saveConstructionParamGroups({
      skipConfirm: true,
      successTitle: "آپلود فایل",
      successMessage: "فایل اکسل گروه پارامترها با موفقیت روی جدول اعمال شد.",
    });
    return;
  }
  if (constructionImportPreviewKind.value === "base_formulas") {
    const { nextRows, deletedIds } = buildImportedConstructionBaseFormulaDrafts(constructionImportPreviewRows.value);
    editableBaseFormulas.value = nextRows;
    constructionDeletedBaseFormulaIds.value = deletedIds;
    clearConstructionImportPreview();
    await saveConstructionBaseFormulas({
      skipConfirm: true,
      successTitle: "آپلود فایل",
      successMessage: "فایل اکسل فرمول‌های پایه با موفقیت روی جدول اعمال شد.",
    });
    return;
  }
  if (constructionImportPreviewKind.value === "part_formulas") {
    const { nextRows, deletedIds } = buildImportedConstructionPartFormulaDrafts(constructionImportPreviewRows.value);
    editablePartFormulas.value = nextRows;
    constructionDeletedPartFormulaIds.value = deletedIds;
    clearConstructionImportPreview();
    await saveConstructionPartFormulas({
      skipConfirm: true,
      successTitle: "آپلود فایل",
      successMessage: "فایل اکسل فرمول‌های قطعات با موفقیت روی جدول اعمال شد.",
    });
    return;
  }
  const { nextRows, deletedIds } = buildImportedConstructionDrafts(constructionImportPreviewRows.value);
  editablePartKinds.value = nextRows;
  constructionDeletedPartKindIds.value = deletedIds;
  clearConstructionImportPreview();
  await saveConstructionPartKinds({
    skipConfirm: true,
    successTitle: "آپلود فایل",
    successMessage: "فایل اکسل با موفقیت روی جدول اعمال شد.",
  });
}

async function deleteConstructionTemplate(id) {
  const item = editableTemplates.value.find((row) => String(row.id) === String(id));
  if (!item) return;
  const ok = await showConfirm(`تمپلیت «${item.temp_title || item.title || "بدون عنوان"}» حذف شود؟`, {
    title: "حذف تمپلیت",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  constructionDeletingIds.value = [...constructionDeletingIds.value, String(id)];
  try {
    editableTemplates.value = editableTemplates.value.filter((row) => String(row.id) !== String(id));
    if (!item.__isNew) {
      constructionDeletedTemplateIds.value = [...new Set([...constructionDeletedTemplateIds.value, String(id)])];
    }
  } catch (_) {
    showAlert("حذف تمپلیت از جدول انجام نشد.", { title: "خطا" });
  } finally {
    constructionDeletingIds.value = constructionDeletingIds.value.filter((value) => value !== String(id));
  }
}

async function deleteConstructionCategory(id) {
  const item = editableCategories.value.find((row) => String(row.id) === String(id));
  if (!item) return;
  const ok = await showConfirm(`دسته «${item.cat_title || item.title || "بدون عنوان"}» حذف شود؟`, {
    title: "حذف دسته",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  constructionDeletingIds.value = [...constructionDeletingIds.value, String(id)];
  try {
    editableCategories.value = editableCategories.value.filter((row) => String(row.id) !== String(id));
    if (!item.__isNew) {
      constructionDeletedCategoryIds.value = [...new Set([...constructionDeletedCategoryIds.value, String(id)])];
    }
  } catch (_) {
    showAlert("حذف دسته از جدول انجام نشد.", { title: "خطا" });
  } finally {
    constructionDeletingIds.value = constructionDeletingIds.value.filter((value) => value !== String(id));
  }
}

async function deleteConstructionSubCategory(id) {
  const item = editableSubCategories.value.find((row) => String(row.id) === String(id));
  if (!item) return;
  const ok = await showConfirm(`ساب‌کت «${item.sub_cat_title || item.title || "بدون عنوان"}» حذف شود؟`, {
    title: "حذف ساب‌کت",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  constructionDeletingIds.value = [...constructionDeletingIds.value, String(id)];
  try {
    editableSubCategories.value = editableSubCategories.value.filter((row) => String(row.id) !== String(id));
    if (!item.__isNew) {
      constructionDeletedSubCategoryIds.value = [...new Set([...constructionDeletedSubCategoryIds.value, String(id)])];
    }
  } catch (_) {
    showAlert("حذف ساب‌کت از جدول انجام نشد.", { title: "خطا" });
  } finally {
    constructionDeletingIds.value = constructionDeletingIds.value.filter((value) => value !== String(id));
  }
}

async function deleteConstructionPartKind(id) {
  const item = editablePartKinds.value.find((row) => String(row.id) === String(id));
  if (!item) return;
  const ok = await showConfirm(`نوع قطعه «${item.org_part_kind_title || item.title || "بدون عنوان"}» حذف شود؟`, {
    title: "حذف نوع قطعه",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  constructionDeletingIds.value = [...constructionDeletingIds.value, String(id)];
  try {
    editablePartKinds.value = editablePartKinds.value.filter((item) => String(item.id) !== String(id));
    if (!item.__isNew) {
      constructionDeletedPartKindIds.value = [...new Set([...constructionDeletedPartKindIds.value, String(id)])];
    }
  } catch (_) {
    showAlert("حذف نوع قطعه از جدول انجام نشد.", { title: "خطا" });
  } finally {
    constructionDeletingIds.value = constructionDeletingIds.value.filter((value) => value !== String(id));
  }
}

async function deleteConstructionParamGroup(id) {
  const item = editableParamGroups.value.find((row) => String(row.id) === String(id));
  if (!item) return;
  const ok = await showConfirm(`گروه پارامتر «${item.org_param_group_title || item.title || "بدون عنوان"}» حذف شود؟`, {
    title: "حذف گروه پارامتر",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  constructionDeletingIds.value = [...constructionDeletingIds.value, String(id)];
  try {
    await discardStagedParamGroupIcon(item.param_group_icon_path);
    editableParamGroups.value = editableParamGroups.value.filter((row) => String(row.id) !== String(id));
    if (!item.__isNew) {
      constructionDeletedParamGroupIds.value = [...new Set([...constructionDeletedParamGroupIds.value, String(id)])];
    }
  } catch (_) {
    showAlert("حذف گروه پارامتر از جدول انجام نشد.", { title: "خطا" });
  } finally {
    constructionDeletingIds.value = constructionDeletingIds.value.filter((value) => value !== String(id));
  }
}

async function deleteConstructionParam(id) {
  const item = editableParams.value.find((row) => String(row.id) === String(id));
  if (!item) return;
  const ok = await showConfirm(`پارامتر «${item.param_title_fa || item.param_title_en || "بدون عنوان"}» حذف شود؟`, {
    title: "حذف پارامتر",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  constructionDeletingIds.value = [...constructionDeletingIds.value, String(id)];
  try {
    editableParams.value = editableParams.value.filter((row) => String(row.id) !== String(id));
    if (!item.__isNew) {
      constructionDeletedParamIds.value = [...new Set([...constructionDeletedParamIds.value, String(id)])];
    }
  } catch (_) {
    showAlert("حذف پارامتر از جدول انجام نشد.", { title: "خطا" });
  } finally {
    constructionDeletingIds.value = constructionDeletingIds.value.filter((value) => value !== String(id));
  }
}

async function deleteConstructionBaseFormula(id) {
  const item = editableBaseFormulas.value.find((row) => String(row.id) === String(id));
  if (!item) return;
  const ok = await showConfirm(`فرمول پایه «${item.param_formula || item.title || "بدون عنوان"}» حذف شود؟`, {
    title: "حذف فرمول پایه",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  constructionDeletingIds.value = [...constructionDeletingIds.value, String(id)];
  try {
    editableBaseFormulas.value = editableBaseFormulas.value.filter((row) => String(row.id) !== String(id));
    if (!item.__isNew) {
      constructionDeletedBaseFormulaIds.value = [...new Set([...constructionDeletedBaseFormulaIds.value, String(id)])];
    }
  } catch (_) {
    showAlert("حذف فرمول پایه از جدول انجام نشد.", { title: "خطا" });
  } finally {
    constructionDeletingIds.value = constructionDeletingIds.value.filter((value) => value !== String(id));
  }
}

async function deleteConstructionPartFormula(id) {
  const item = editablePartFormulas.value.find((row) => String(row.id) === String(id));
  if (!item) return;
  const ok = await showConfirm(`فرمول قطعه «${item.part_code || item.title || "بدون عنوان"}» حذف شود؟`, {
    title: "حذف فرمول قطعه",
    confirmText: "حذف",
    cancelText: "انصراف",
  });
  if (!ok) return;
  constructionDeletingIds.value = [...constructionDeletingIds.value, String(id)];
  try {
    editablePartFormulas.value = editablePartFormulas.value.filter((row) => String(row.id) !== String(id));
    if (!item.__isNew) {
      constructionDeletedPartFormulaIds.value = [...new Set([...constructionDeletedPartFormulaIds.value, String(id)])];
    }
  } catch (_) {
    showAlert("حذف فرمول قطعه از جدول انجام نشد.", { title: "خطا" });
  } finally {
    constructionDeletingIds.value = constructionDeletingIds.value.filter((value) => value !== String(id));
  }
}

function triggerParamGroupIconUpload(item) {
  if (isUploadingParamGroupIcon(item)) return;
  activeParamGroupIconRowId.value = String(item.id);
  paramGroupIconInputEl.value?.click?.();
}

async function onParamGroupIconFileChange(event) {
  const file = event?.target?.files?.[0];
  const rowId = activeParamGroupIconRowId.value;
  if (!file || !rowId) return;
  const item = editableParamGroups.value.find((row) => String(row.id) === rowId);
  if (!item) return;
  const previousIconFileName = normalizeIconFileName(item.param_group_icon_path);
  constructionUploadingIconRowId.value = rowId;
  try {
    const formData = new FormData();
    formData.append("file", file);
    const slugHint = encodeURIComponent(String(item.param_group_code || `param-group-${item.param_group_id || "new"}`));
    const res = await fetch(`/api/admin-storage/${encodeURIComponent(currentAdminId.value)}/param-group-icons?slug_hint=${slugHint}`, {
      method: "POST",
      body: formData,
    });
    if (!res.ok) throw new Error("upload-failed");
    const payload = await res.json();
    if (isStagedParamGroupIcon(previousIconFileName)) {
      await discardStagedParamGroupIcon(previousIconFileName);
    }
    item.param_group_icon_path = normalizeIconFileName(payload.file_name || payload.icon_path);
    if (!item.__isNew) item.__dirty = true;
  } catch (_) {
    showAlert("آپلود آیکون انجام نشد. فقط فایل تصویری معتبر با اندازه استاندارد قابل قبول است.", { title: "آیکون گروه پارامتر" });
  } finally {
    constructionUploadingIconRowId.value = null;
    activeParamGroupIconRowId.value = null;
    if (paramGroupIconInputEl.value) paramGroupIconInputEl.value.value = "";
  }
}

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

function getSolidEntityType(entity) {
  const rawType = String(entity?.elementType || "").toLowerCase();
  const rawName = String(entity?.name || "").trim();
  if (rawType === "column" || /^c\d+$/i.test(rawName)) return "column";
  if (rawType === "beam" || /^beam\s+/i.test(rawName)) return "beam";
  return "wall";
}

function normalizeSelectionIds(ids) {
  return Array.isArray(ids)
    ? ids.map((id) => String(id || "").trim()).filter(Boolean)
    : [];
}

function getEditorSelectionSummary(full = null) {
  const state = full || editorRef.value?.getState?.() || null;
  const selection = state?.selection || {};
  const collectIds = (singleValue, manyValues) => {
    const next = normalizeSelectionIds(manyValues);
    const single = String(singleValue || "").trim();
    if (single && !next.includes(single)) next.unshift(single);
    return next;
  };
  const wallIds = collectIds(selection.selectedWallId, selection.selectedWallIds);
  const beamIds = collectIds(selection.selectedBeamId, selection.selectedBeamIds);
  const beamSet = new Set(beamIds);
  const wallOnlyIds = wallIds.filter((id) => !beamSet.has(id));
  const hiddenIds = collectIds(selection.selectedHiddenId, selection.selectedHiddenIds);
  const doorIds = collectIds(selection.selectedDoorId, selection.selectedDoorIds);
  const passiveModelIds = collectIds(selection.selectedPassiveModelId, selection.selectedPassiveModelIds);
  const designIds = normalizeSelectionIds(selectedOrderDesignIds.value);
  const hasActiveModel = !!selection.selectedModelOutline;
  const designCount = designIds.length > 0 ? designIds.length : (hasActiveModel && activeCabinetDesignId.value ? 1 : 0);
  const categoryCount = [
    wallOnlyIds.length > 0,
    beamIds.length > 0,
    hiddenIds.length > 0,
    doorIds.length > 0,
    designCount > 0,
  ].filter(Boolean).length;
  return {
    wallIds,
    wallOnlyIds,
    beamIds,
    hiddenIds,
    doorIds,
    passiveModelIds,
    designIds,
    hasActiveModel,
    designCount,
    totalCount: wallOnlyIds.length + beamIds.length + hiddenIds.length + doorIds.length + designCount,
    categoryCount,
    isMixed: categoryCount > 1,
    isSingleDesign: designCount === 1 && categoryCount === 1,
  };
}

function syncQuickStateFromEditor() {
  const full = editorRef.value?.getState?.();
  const s = full?.state;
  if (!s) return;
  currentEditorDisplayUnitState.value = ["mm", "inch"].includes(String(s.unit || "cm").trim().toLowerCase())
    ? String(s.unit || "cm").trim().toLowerCase()
    : "cm";
  activeStageOrderDesignSelected.value = !!full?.selection?.selectedModelOutline && !!activeCabinetDesignId.value;
  {
    const nextSelectedIds = [];
    const pushSelectedId = (value) => {
      const key = String(value || "").trim();
      if (key && !nextSelectedIds.includes(key)) nextSelectedIds.push(key);
    };
    pushSelectedId(full?.selection?.selectedPassiveModelId);
    if (Array.isArray(full?.selection?.selectedPassiveModelIds)) {
      for (const id of full.selection.selectedPassiveModelIds) pushSelectedId(id);
    }
    const orderIds = new Set(orderDesignCatalog.value.map((item) => String(item.id || "").trim()).filter(Boolean));
    const doorIds = new Set(doorScenePlacements.value.map((item) => String(item.id || "").trim()).filter(Boolean));
    selectedStageOrderDesignIds.value = nextSelectedIds.filter((id) => orderIds.has(id));
    selectedStageDoorAssetIds.value = nextSelectedIds.filter((id) => doorIds.has(id));
  }
  editorViewportState.value = {
    zoom: Number.isFinite(Number(s.zoom)) ? Number(s.zoom) : 1,
    offsetX: Number.isFinite(Number(s.offsetX)) ? Number(s.offsetX) : 0,
    offsetY: Number.isFinite(Number(s.offsetY)) ? Number(s.offsetY) : 0,
  };
  const model2dLines = Array.isArray(full?.model2dSnap?.lines) ? full.model2dSnap.lines : [];
  const restoredModelDesignId = String(full?.model2dSnap?.designId || "").trim();
  if (!model2dLines.length) {
    stageCabinetPlaceholderBoxes.value = [];
    activeCabinetDesignId.value = null;
    activeDoorAssetId.value = null;
    activeStageOrderDesignSelected.value = false;
    selectedStageOrderDesignIds.value = [];
    selectedStageDoorAssetIds.value = [];
  } else if (restoredModelDesignId && orderDesignCatalog.value.some((item) => String(item.id) === restoredModelDesignId)) {
    activeCabinetDesignId.value = restoredModelDesignId;
    activeDoorAssetId.value = null;
    const activeDesign = orderDesignCatalog.value.find((item) => String(item.id) === restoredModelDesignId) || null;
    if (activeDesign?.viewer_boxes?.length) {
      stageCabinetPlaceholderBoxes.value = activeDesign.viewer_boxes.map(normalizeCabinetBox);
    }
    upsertOrderDesignPlacement({
      orderDesignId: restoredModelDesignId,
      x: Number.isFinite(Number(full?.model2dSnap?.offsetXmm)) ? Number(full.model2dSnap.offsetXmm) : 0,
      y: Number.isFinite(Number(full?.model2dSnap?.offsetYmm)) ? Number(full.model2dSnap.offsetYmm) : 0,
      rotRad: Number.isFinite(Number(full?.model2dSnap?.rotationRad)) ? Number(full.model2dSnap.rotationRad) : 0,
    });
  } else if (restoredModelDesignId && doorScenePlacements.value.some((item) => String(item.id) === restoredModelDesignId)) {
    activeCabinetDesignId.value = null;
    activeDoorAssetId.value = restoredModelDesignId;
    activeStageOrderDesignSelected.value = false;
    stageCabinetPlaceholderBoxes.value = [];
    const current = getDoorScenePlacement(restoredModelDesignId);
    if (current) {
      upsertDoorScenePlacement({
        ...current,
        x: Number.isFinite(Number(full?.model2dSnap?.offsetXmm)) ? Number(full.model2dSnap.offsetXmm) : 0,
        y: Number.isFinite(Number(full?.model2dSnap?.offsetYmm)) ? Number(full.model2dSnap.offsetYmm) : 0,
        rotRad: Number.isFinite(Number(full?.model2dSnap?.rotationRad)) ? Number(full.model2dSnap.rotationRad) : 0,
      });
    }
  } else if (activeCabinetDesignId.value) {
    upsertOrderDesignPlacement({
      orderDesignId: activeCabinetDesignId.value,
      x: Number.isFinite(Number(full?.model2dSnap?.offsetXmm)) ? Number(full.model2dSnap.offsetXmm) : 0,
      y: Number.isFinite(Number(full?.model2dSnap?.offsetYmm)) ? Number(full.model2dSnap.offsetYmm) : 0,
      rotRad: Number.isFinite(Number(full?.model2dSnap?.rotationRad)) ? Number(full.model2dSnap.rotationRad) : 0,
    });
  } else if (activeDoorAssetId.value) {
    const current = getDoorScenePlacement(activeDoorAssetId.value);
    if (current) {
      upsertDoorScenePlacement({
        ...current,
        x: Number.isFinite(Number(full?.model2dSnap?.offsetXmm)) ? Number(full.model2dSnap.offsetXmm) : 0,
        y: Number.isFinite(Number(full?.model2dSnap?.offsetYmm)) ? Number(full.model2dSnap.offsetYmm) : 0,
        rotRad: Number.isFinite(Number(full?.model2dSnap?.rotationRad)) ? Number(full.model2dSnap.rotationRad) : 0,
      });
    }
  }
  showDimensions.value = s.showDimensions !== false;
  showOffsetWalls.value = !!s.offsetWallEnabled;
  showObjectAxes.value = !!s.showObjectAxes;
  const wallNodes = Array.isArray(full?.graphSnap?.nodes) ? full.graphSnap.nodes : [];
  const hiddenNodes = Array.isArray(full?.hiddenGraphSnap?.nodes) ? full.hiddenGraphSnap.nodes : [];
  const walls = Array.isArray(full?.graphSnap?.walls) ? full.graphSnap.walls : [];
  const hiddenWalls = Array.isArray(full?.hiddenGraphSnap?.walls) ? full.hiddenGraphSnap.walls : [];
  const doors = Array.isArray(full?.doors) ? full.doors : [];
  const selectedWallIds = Array.isArray(full?.selection?.selectedWallIds) ? full.selection.selectedWallIds : [];
  const selectedHiddenIds = Array.isArray(full?.selection?.selectedHiddenIds) ? full.selection.selectedHiddenIds : [];
  const selectedDoorIds = Array.isArray(full?.selection?.selectedDoorIds) ? full.selection.selectedDoorIds : [];
  const selectedPassiveModelIds = Array.isArray(full?.selection?.selectedPassiveModelIds) ? full.selection.selectedPassiveModelIds : [];
  const selectedWallId = full?.selection?.selectedWallId || selectedWallIds[0] || null;
  const selectedHiddenId = full?.selection?.selectedHiddenId || selectedHiddenIds[0] || null;
  const selectedDoorId = full?.selection?.selectedDoorId || selectedDoorIds[0] || null;
  const selectedPassiveModelId = full?.selection?.selectedPassiveModelId || selectedPassiveModelIds[0] || null;
  const beamNodes = Array.isArray(full?.beamGraphSnap?.nodes) ? full.beamGraphSnap.nodes : [];
  const beams = Array.isArray(full?.beamGraphSnap?.walls) ? full.beamGraphSnap.walls : [];
  const selectedBeamIds = Array.isArray(full?.selection?.selectedBeamIds) ? full.selection.selectedBeamIds : [];
  const selectedBeamId = full?.selection?.selectedBeamId || selectedBeamIds[0] || null;
  const selectedWall = selectedWallId ? walls.find((w) => w.id === selectedWallId) : null;
  const selectedHidden = selectedHiddenId ? hiddenWalls.find((w) => w.id === selectedHiddenId) : null;
  const selectedBeam = selectedBeamId ? beams.find((w) => w.id === selectedBeamId) : null;
  const selectedWallCount = selectedWallIds.length > 0 ? selectedWallIds.length : (selectedWallId ? 1 : 0);
  const selectedHiddenCount = selectedHiddenIds.length > 0 ? selectedHiddenIds.length : (selectedHiddenId ? 1 : 0);
  const selectedBeamCount = selectedBeamIds.length > 0 ? selectedBeamIds.length : (selectedBeamId ? 1 : 0);
  const selectedDoor = selectedDoorId ? doors.find((door) => door.id === selectedDoorId) : null;
  const selectedDoorCount = selectedDoorIds.length > 0 ? selectedDoorIds.length : (selectedDoorId ? 1 : 0);
  const hasActiveDoorAssetSelection = !!full?.selection?.selectedModelOutline && !!activeDoorAssetId.value;
  const selectedDoorAsset = hasActiveDoorAssetSelection
    ? getDoorScenePlacement(activeDoorAssetId.value)
    : (
      selectedStageDoorAssetIds.value.length === 1
        ? getDoorScenePlacement(selectedStageDoorAssetIds.value[0])
        : null
    );
  const selectedDoorAssetCount = hasActiveDoorAssetSelection
    ? 1
    : selectedStageDoorAssetIds.value.length;
  const hasWallSelection = !!(selectedWall || selectedWallIds.length > 0);
  const hasHiddenSelection = !!(selectedHidden || selectedHiddenIds.length > 0);
  const hasBeamSelection = !!(selectedBeam || selectedBeamIds.length > 0);
  const hasDoorSelection = !!(selectedDoor || selectedDoorIds.length > 0 || selectedDoorAsset || selectedStageDoorAssetIds.value.length > 0);
  const hasDesignSelection = !!(selectedOrderDesignIds.value.length > 0 || (!!full?.selection?.selectedModelOutline && !!activeCabinetDesignId.value));
  const selectedSolidEntityType = selectedWall ? getSolidEntityType(selectedWall) : "wall";
  const metricsEntityType =
    getEditorSelectionSummary(full).categoryCount > 1
      ? "mixed"
      : hasBeamSelection
        ? "beam"
        : hasDoorSelection
          ? "door"
        : hasWallSelection
          ? selectedSolidEntityType
          : hasHiddenSelection
            ? "hidden"
            : hasDesignSelection
              ? "design"
              : "wall";
  const selectedCount =
    (metricsEntityType === "hidden") ? selectedHiddenCount
      : (metricsEntityType === "beam") ? selectedBeamCount
        : (metricsEntityType === "door") ? Math.max(selectedDoorCount, selectedDoorAssetCount)
        : (metricsEntityType === "design") ? (selectedOrderDesignIds.value.length > 0 ? selectedOrderDesignIds.value.length : (full?.selection?.selectedModelOutline ? 1 : 0))
        : selectedWallCount;

  walls3dSnapshot.value = {
    nodes: wallNodes,
    walls,
    doors,
    selection: {
      selectedWallId: full?.selection?.selectedWallId || null,
      selectedWallIds,
      selectedHiddenId: full?.selection?.selectedHiddenId || null,
      selectedHiddenIds,
      selectedDoorId: full?.selection?.selectedDoorId || null,
      selectedDoorIds,
      selectedBeamId: full?.selection?.selectedBeamId || null,
      selectedBeamIds,
      selectedPassiveModelId,
      selectedPassiveModelIds,
      selectedModelOutline: !!full?.selection?.selectedModelOutline,
    },
    metrics: {
      nodes: metricsEntityType === "hidden" ? hiddenNodes : metricsEntityType === "beam" ? beamNodes : wallNodes,
      walls: metricsEntityType === "hidden" ? hiddenWalls : metricsEntityType === "beam" ? beams : walls,
      doors,
      selection: {
        selectedWallId: metricsEntityType === "hidden" ? selectedHiddenId : metricsEntityType === "beam" ? selectedBeamId : metricsEntityType === "door" ? selectedDoorId : selectedWallId,
        selectedWallIds: metricsEntityType === "hidden" ? selectedHiddenIds : metricsEntityType === "beam" ? selectedBeamIds : metricsEntityType === "door" ? selectedDoorIds : selectedWallIds,
        selectedDoorId,
        selectedDoorIds,
        selectedPassiveModelId,
        selectedPassiveModelIds,
        selectedModelOutline: !!full?.selection?.selectedModelOutline,
      },
      entityType: metricsEntityType,
    },
    state: {
      wallHeightMm: Number.isFinite(s?.wallHeightMm) ? s.wallHeightMm : 2800,
      wallFillColor: (typeof s?.wallFillColor === "string" && s.wallFillColor) ? s.wallFillColor : "#A6A6A6",
      wallFillOpacityPercent: Number.isFinite(Number(s?.wallFillOpacityPercent)) ? Number(s.wallFillOpacityPercent) : 90,
      beamFillColor: (typeof s?.beamFillColor === "string" && s.beamFillColor) ? s.beamFillColor : "#A6A6A6",
      beamFillOpacityPercent: Number.isFinite(Number(s?.beamFillOpacityPercent)) ? Number(s.beamFillOpacityPercent) : 20,
      wall3dColor: (typeof s?.wall3dColor === "string" && s.wall3dColor) ? s.wall3dColor : "#C7CCD1",
      beam3dColor: (typeof s?.beam3dColor === "string" && s.beam3dColor) ? s.beam3dColor : "#C7CCD1",
      columnFillColor: (typeof s?.columnFillColor === "string" && s.columnFillColor) ? s.columnFillColor : "#A6A6A6",
      columnFillOpacityPercent: Number.isFinite(Number(s?.columnFillOpacityPercent)) ? Number(s.columnFillOpacityPercent) : 90,
      column3dColor: (typeof s?.column3dColor === "string" && s.column3dColor) ? s.column3dColor : "#C7CCD1",
      columnWidthMm: Number.isFinite(Number(s?.columnWidthMm)) ? Number(s.columnWidthMm) : 500,
      columnDepthMm: Number.isFinite(Number(s?.columnDepthMm)) ? Number(s.columnDepthMm) : 400,
      columnHeightMm: Number.isFinite(Number(s?.columnHeightMm)) ? Number(s.columnHeightMm) : 2800,
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
    const defaultHiddenThicknessCm = (Number.isFinite(Number(s?.hiddenWallThicknessMm)) ? Number(s.hiddenWallThicknessMm) : 1) / 10;
    const defaultWallColor = (typeof s?.wall3dColor === "string" && s.wall3dColor) ? s.wall3dColor : "#C7CCD1";
    const defaultBeamColor = (typeof s?.beam3dColor === "string" && s.beam3dColor) ? s.beam3dColor : "#C7CCD1";
    const defaultColumnColor = (typeof s?.column3dColor === "string" && s.column3dColor) ? s.column3dColor : "#C7CCD1";
    const defaultColumnWidthCm = (Number.isFinite(Number(s?.columnWidthMm)) ? Number(s.columnWidthMm) : 500) / 10;
    const defaultColumnDepthCm = (Number.isFinite(Number(s?.columnDepthMm)) ? Number(s.columnDepthMm) : 400) / 10;
    const defaultColumnHeightCm = (Number.isFinite(Number(s?.columnHeightMm)) ? Number(s.columnHeightMm) : 2800) / 10;
    const defaultDoorWidthCm = 90;
    const defaultDoorHeightCm = 207;
    const defaultDoorThicknessCm = 15;
    const defaultDoorSillCm = 0;

    const selectedObj =
      (metricsEntityType === "hidden") ? selectedHidden
        : (metricsEntityType === "beam") ? selectedBeam
          : (metricsEntityType === "door") ? (selectedDoor || selectedDoorAsset)
          : selectedWall;
    const selectedDoorBoundsMm = metricsEntityType === "door"
      ? sanitizeDoorBoundsMm(selectedObj?.modelBoundsMm || {
          widthMm: selectedObj?.widthMm,
          heightMm: selectedObj?.heightMm,
          depthMm: selectedObj?.frameDepthMm,
        })
      : null;
    const selectedSolidType = getSolidEntityType(selectedObj);
    const fallbackThicknessCm =
      selectedSolidType === "beam" ? defaultBeamThicknessCm :
      selectedSolidType === "column" ? defaultColumnDepthCm :
      defaultThicknessCm;
    const fallbackHeightCm =
      selectedSolidType === "beam" ? defaultBeamHeightCm :
      selectedSolidType === "column" ? defaultColumnHeightCm :
      defaultHeightCm;
    const fallbackFloorOffsetCm = selectedSolidType === "beam" ? defaultBeamFloorOffsetCm : 0;
    const fallbackLengthCm = selectedSolidType === "column" ? defaultColumnWidthCm : null;
    const fallbackColor =
      selectedSolidType === "beam" ? defaultBeamColor :
      selectedSolidType === "column" ? defaultColumnColor :
      defaultWallColor;
    wallStyleDraft.value = selectedObj
      ? {
          thicknessCm: metricsEntityType === "door"
            ? (Number(selectedDoorBoundsMm?.depthMm) || (defaultDoorThicknessCm * 10)) / 10
            : (Number(selectedObj.thickness) || (fallbackThicknessCm * 10)) / 10,
          heightCm: metricsEntityType === "door"
            ? (Number(selectedDoorBoundsMm?.heightMm) || (fallbackHeightCm * 10)) / 10
            : (Number(selectedObj.heightMm) || (fallbackHeightCm * 10)) / 10,
          lengthCm: metricsEntityType === "door"
            ? (Number(selectedDoorBoundsMm?.widthMm) || (defaultDoorWidthCm * 10)) / 10
            : fallbackLengthCm,
          floorOffsetCm: metricsEntityType === "door"
            ? (Number(selectedObj.floorOffsetMm ?? selectedObj.sillHeightMm) || (defaultDoorSillCm * 10)) / 10
            : (Number(selectedObj.floorOffsetMm) || (fallbackFloorOffsetCm * 10)) / 10,
          color: (typeof selectedObj.color3d === "string" && selectedObj.color3d) ? selectedObj.color3d : fallbackColor,
        }
      : {
          thicknessCm:
            designMenuTool.value === "column" ? defaultColumnDepthCm
              : designMenuTool.value === "door" ? defaultDoorThicknessCm
              : designMenuTool.value === "beam" ? defaultBeamThicknessCm
                : designMenuTool.value === "hidden" ? defaultHiddenThicknessCm
                  : defaultThicknessCm,
          heightCm:
            designMenuTool.value === "column" ? defaultColumnHeightCm
              : designMenuTool.value === "door" ? defaultDoorHeightCm
              : designMenuTool.value === "beam" ? defaultBeamHeightCm
                : defaultHeightCm,
          lengthCm: designMenuTool.value === "column" ? defaultColumnWidthCm : designMenuTool.value === "door" ? defaultDoorWidthCm : null,
          floorOffsetCm: designMenuTool.value === "beam" ? defaultBeamFloorOffsetCm : designMenuTool.value === "door" ? defaultDoorSillCm : 0,
          color:
            designMenuTool.value === "column" ? defaultColumnColor
              : designMenuTool.value === "beam" ? defaultBeamColor
                : designMenuTool.value === "door" ? "#8B6B4A" : defaultWallColor,
        };
  }

  const selectedEntity = (metricsEntityType === "hidden") ? selectedHidden : (metricsEntityType === "beam") ? selectedBeam : (metricsEntityType === "door") ? (selectedDoor || selectedDoorAsset) : selectedWall;
  if (selectedEntity && metricsEntityType !== "mixed") {
    const selectedDoorBoundsMm = metricsEntityType === "door"
      ? sanitizeDoorBoundsMm(selectedEntity?.modelBoundsMm || {
          widthMm: selectedEntity?.widthMm,
          heightMm: selectedEntity?.heightMm,
          depthMm: selectedEntity?.frameDepthMm,
        })
      : null;
    const srcNodes = (metricsEntityType === "hidden") ? hiddenNodes : (metricsEntityType === "beam") ? beamNodes : wallNodes;
    const byId = new Map(srcNodes.map((n) => [n.id, n]));
    const na = byId.get(selectedEntity.a);
    const nb = byId.get(selectedEntity.b);
    const lenMm = (na && nb) ? Math.hypot(nb.x - na.x, nb.y - na.y) : 0;
    selectedWallStyle.value = {
      id: selectedEntity.id,
      name: selectedEntity.title || selectedEntity.name || selectedEntity.id,
      entityType: metricsEntityType,
      thicknessCm: metricsEntityType === "door"
        ? (Number(selectedDoorBoundsMm?.depthMm) || 150) / 10
        : (Number(selectedEntity.thickness) || 120) / 10,
      heightCm: metricsEntityType === "door"
        ? (Number(selectedDoorBoundsMm?.heightMm) || 2070) / 10
        : (Number(selectedEntity.heightMm)
        || (
          metricsEntityType === "beam" ? Number(s?.beamHeightMm)
            : metricsEntityType === "column" ? Number(s?.columnHeightMm)
              : Number(s?.wallHeightMm)
        )
        || 3000) / 10,
      floorOffsetCm: metricsEntityType === "door"
        ? (Number(selectedEntity.floorOffsetMm ?? selectedEntity.sillHeightMm) || 0) / 10
        : (Number(selectedEntity.floorOffsetMm) || 0) / 10,
      lengthCm: metricsEntityType === "door"
        ? (Number(selectedDoorBoundsMm?.widthMm) || 900) / 10
        : lenMm / 10,
      color: (typeof selectedEntity.color3d === "string" && selectedEntity.color3d)
        ? selectedEntity.color3d
        : (
          metricsEntityType === "beam"
            ? ((typeof s?.beam3dColor === "string" && s.beam3dColor) ? s.beam3dColor : "#C7CCD1")
            : (metricsEntityType === "column"
              ? ((typeof s?.column3dColor === "string" && s.column3dColor) ? s.column3dColor : "#C7CCD1")
              : ((typeof s?.wall3dColor === "string" && s.wall3dColor) ? s.wall3dColor : "#C7CCD1"))
        ),
      a: selectedEntity.a,
      b: selectedEntity.b,
      wallId: selectedEntity.wallId,
      wallName: selectedEntity.wallName || null,
      offsetCm: metricsEntityType === "door" ? (Number(selectedEntity.offsetMm) || 0) / 10 : null,
      modelBoundsMm: selectedDoorBoundsMm || selectedEntity.modelBoundsMm || null,
      floorOffsetMm: Number(selectedEntity.floorOffsetMm) || 0,
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
  const entityType = selectedWallStyle.value?.entityType || designMenuTool.value || "wall";
  const fallbackThickness = entityType === "column" ? 40 : entityType === "door" ? 12 : 12;
  const fallbackHeight = entityType === "column" ? 280 : entityType === "door" ? 220 : 300;
  const t = Math.max(0.1, Number(wallStyleDraft.value.thicknessCm) || fallbackThickness);
  const h = Math.max(1, Number(wallStyleDraft.value.heightCm) || fallbackHeight);
  const f = Math.max(0, Number(wallStyleDraft.value.floorOffsetCm) || 0);
  const c = String(wallStyleDraft.value.color || "#A6A6A6");
  const lengthRaw = Number(wallStyleDraft.value.lengthCm);
  const next = {
    thicknessCm: Math.round(t * 10) / 10,
    heightCm: Math.round(h),
    floorOffsetCm: Math.round(f * 10) / 10,
    color: c,
  };
  if (entityType === "column" || entityType === "door" || Number.isFinite(lengthRaw)) {
    next.lengthCm = Math.round((Math.max(0.1, lengthRaw || 50)) * 10) / 10;
  }
  wallStyleDraft.value = next;
}

function updateWallStyleDraft(next) {
  wallStyleDraftTouched.value = true;
  const draft = {
    thicknessCm: Number(next?.thicknessCm ?? wallStyleDraft.value.thicknessCm),
    heightCm: Number(next?.heightCm ?? wallStyleDraft.value.heightCm),
    floorOffsetCm: Number(next?.floorOffsetCm ?? wallStyleDraft.value.floorOffsetCm),
    color: String(next?.color ?? wallStyleDraft.value.color),
  };
  if ("lengthCm" in (next || {}) || "lengthCm" in wallStyleDraft.value) {
    draft.lengthCm = Number(next?.lengthCm ?? wallStyleDraft.value.lengthCm);
  }
  wallStyleDraft.value = draft;
  clampWallStyleDraft();

  const thicknessMm = Math.max(1, wallStyleDraft.value.thicknessCm * 10);
  const heightMm = Math.max(1, wallStyleDraft.value.heightCm * 10);
  const color3d = wallStyleDraft.value.color;
  const floorOffsetMm = Math.max(0, wallStyleDraft.value.floorOffsetCm * 10);
  const hasLengthPatch = Object.prototype.hasOwnProperty.call(next || {}, "lengthCm");
  const lengthMm = hasLengthPatch && Number.isFinite(Number(next?.lengthCm))
    ? Math.max(10, Number(next.lengthCm) * 10)
    : null;
  const entityType =
    selectedWallStyle.value?.entityType
    || (designMenuTool.value === "door" ? "door" : null)
    || (designMenuTool.value === "column" ? "column" : null)
    || (designMenuTool.value === "beam" ? "beam" : null)
    || "wall";
  const isBeamEntity = /^Beam\s+/i.test(String(selectedWallStyle.value?.name || "").trim());

  // Only update global wall defaults when no wall is selected.
  if (entityType !== "hidden" && entityType !== "door" && !selectedWallStyle.value?.id) {
    if (designMenuTool.value === "column") {
      editorRef.value?.setState?.({
        columnWidthMm: Number.isFinite(lengthMm) ? lengthMm : Math.max(10, (Number(wallStyleDraft.value.lengthCm) || 50) * 10),
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
    } else if (entityType === "door") {
      const selectedDoorAsset = activeDoorAssetId.value ? getDoorScenePlacement(activeDoorAssetId.value) : null;
      if (selectedDoorAsset) {
        const nextWidthMm = Number.isFinite(lengthMm) ? lengthMm : (Number(selectedDoorAsset?.modelBoundsMm?.widthMm) || 900);
        const nextDoor = {
          ...selectedDoorAsset,
          modelBoundsMm: {
            ...(selectedDoorAsset.modelBoundsMm || getFallbackDoorModelBoundsMm()),
            widthMm: nextWidthMm,
            heightMm,
            depthMm: thicknessMm,
          },
          floorOffsetMm,
        };
        upsertDoorScenePlacement(nextDoor);
        if (String(activeDoorAssetId.value || "") === String(nextDoor.id || "")) {
          syncActiveDoorAssetToEditor(nextDoor, nextDoor);
        }
      } else {
        editorRef.value?.setSelectedDoorStyle?.({
          widthMm: Number.isFinite(lengthMm) ? lengthMm : null,
          heightMm,
          sillHeightMm: floorOffsetMm,
        });
      }
    } else if (entityType === "beam") {
      editorRef.value?.setSelectedBeamStyle?.({ thicknessMm, heightMm, fillColor: color3d, floorOffsetMm });
      if (!isGroupEdit && Number.isFinite(lengthMm)) editorRef.value?.setSelectedBeamLength?.(lengthMm);
    } else if (entityType === "column") {
      editorRef.value?.setSelectedWallStyle?.({ thicknessMm, heightMm, fillColor: color3d });
      if (!isGroupEdit && Number.isFinite(lengthMm)) editorRef.value?.setSelectedWallLength?.(lengthMm);
    } else {
      editorRef.value?.setSelectedWallStyle?.({ thicknessMm, heightMm, floorOffsetMm, fillColor: color3d });
      if (!isGroupEdit && Number.isFinite(lengthMm)) editorRef.value?.setSelectedWallLength?.(lengthMm);
    }
  }
  wallStyleDraftTouched.value = false;
}



function updateSelectedWallCoords(patch) {
  const toMm = (v) => Number(v) * 10;
  const selectionSummary = getEditorSelectionSummary();
  const entityType = selectedWallStyle.value?.entityType || (selectionSummary.isMixed ? "mixed" : "wall");
  const dxMm = Number.isFinite(Number(patch?.dxCm)) ? toMm(patch.dxCm) : null;
  const dyMm = Number.isFinite(Number(patch?.dyCm)) ? toMm(patch.dyCm) : null;
  if (dxMm !== null || dyMm !== null) {
    if (entityType === "door") {
      if (activeDoorAssetId.value) {
        const current = getDoorScenePlacement(activeDoorAssetId.value);
        if (current) {
        const nextDoor = {
          ...current,
          x: current.x + (dxMm ?? 0),
          y: current.y + (dyMm ?? 0),
        };
        upsertDoorScenePlacement(nextDoor);
        syncActiveDoorAssetToEditor(nextDoor, nextDoor);
      }
      } else {
        editorRef.value?.moveSelectedDoorsBy?.({
          dxMm: dxMm ?? 0,
          dyMm: dyMm ?? 0,
        });
      }
    } else if (editorRef.value?.moveSelectionBy) {
      editorRef.value.moveSelectionBy({
        dxMm: dxMm ?? 0,
        dyMm: dyMm ?? 0,
      });
    } else if (entityType === "hidden") {
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

  if (entityType === "door") {
    const offsetCm = Number.isFinite(Number(patch?.offsetCm)) ? Number(patch.offsetCm) : null;
    if (activeDoorAssetId.value && offsetCm !== null) {
      const current = getDoorScenePlacement(activeDoorAssetId.value);
      if (current) {
        const nextDoor = {
          ...current,
          x: offsetCm * 10,
        };
        upsertDoorScenePlacement(nextDoor);
        syncActiveDoorAssetToEditor(nextDoor, nextDoor);
      }
    } else if (offsetCm !== null) {
      editorRef.value?.setSelectedDoorOffset?.(offsetCm * 10);
    }
    return;
  }

  const designContext = getSingleSelectedOrderDesignContext();
  if (designContext) {
    const axMm = Number.isFinite(Number(patch?.axCm)) ? toMm(patch.axCm) : null;
    const ayMm = Number.isFinite(Number(patch?.ayCm)) ? toMm(patch.ayCm) : null;
    const bxMm = Number.isFinite(Number(patch?.bxCm)) ? toMm(patch.bxCm) : null;
    const byMm = Number.isFinite(Number(patch?.byCm)) ? toMm(patch.byCm) : null;
    const dxCandidates = [];
    const dyCandidates = [];
    if (axMm !== null) dxCandidates.push(axMm - designContext.bounds.minX);
    if (bxMm !== null) dxCandidates.push(bxMm - designContext.bounds.maxX);
    if (ayMm !== null) dyCandidates.push(ayMm - designContext.bounds.minY);
    if (byMm !== null) dyCandidates.push(byMm - designContext.bounds.maxY);
    const nextDxMm = dxCandidates.length
      ? dxCandidates.reduce((sum, value) => sum + value, 0) / dxCandidates.length
      : 0;
    const nextDyMm = dyCandidates.length
      ? dyCandidates.reduce((sum, value) => sum + value, 0) / dyCandidates.length
      : 0;
    if (Math.abs(nextDxMm) > 1e-9 || Math.abs(nextDyMm) > 1e-9) {
      editorRef.value?.moveSelectionBy?.({
        dxMm: nextDxMm,
        dyMm: nextDyMm,
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


function buildSolidDebugBuckets(full) {
  const nodes = Array.isArray(full?.graphSnap?.nodes) ? full.graphSnap.nodes : [];
  const walls = Array.isArray(full?.graphSnap?.walls) ? full.graphSnap.walls : [];
  const byId = new Map(nodes.map((node) => [node.id, node]));
  const normalizeKind = (item) => {
    const rawType = String(item?.elementType || "").toLowerCase();
    const rawName = String(item?.name || "").trim();
    if (rawType === "column" || /^c\d+$/i.test(rawName)) return "column";
    if (rawType === "beam" || /^beam\s+/i.test(rawName)) return "beam";
    return "wall";
  };
  const hydrate = (item) => ({
    ...item,
    kind: normalizeKind(item),
    nodeA: byId.get(item?.a) || null,
    nodeB: byId.get(item?.b) || null,
  });
  return {
    nodes,
    walls: walls.filter((item) => normalizeKind(item) === "wall").map(hydrate),
    beams: walls.filter((item) => normalizeKind(item) === "beam").map(hydrate),
    columns: walls.filter((item) => normalizeKind(item) === "column").map(hydrate),
    all: walls.map(hydrate),
  };
}

function buildHiddenDebugBucket(full) {
  const nodes = Array.isArray(full?.hiddenGraphSnap?.nodes) ? full.hiddenGraphSnap.nodes : [];
  const walls = Array.isArray(full?.hiddenGraphSnap?.walls) ? full.hiddenGraphSnap.walls : [];
  const byId = new Map(nodes.map((node) => [node.id, node]));
  return {
    nodes,
    walls: walls.map((item) => ({
      ...item,
      kind: "hidden",
      nodeA: byId.get(item?.a) || null,
      nodeB: byId.get(item?.b) || null,
    })),
  };
}

function buildPersistedUiStateSnapshot() {
  return {
    orderDesignPlacements: orderDesignPlacements.value,
    stageCabinetPlaceholderBoxes: stageCabinetPlaceholderBoxes.value,
    activeCabinetDesignId: activeCabinetDesignId.value,
  };
}

function buildDebugJsonPayload({ includeExtendedUiState = true } = {}) {
  const full = editorRef.value?.getState?.();
  if (!full) return null;
  const solid = buildSolidDebugBuckets(full);
  const hidden = buildHiddenDebugBucket(full);
  const baseUiState = buildPersistedUiStateSnapshot();
  return {
    exportedAt: new Date().toISOString(),
    unit: "mm",
    counts: {
      solidNodes: solid.nodes.length,
      walls: solid.walls.length,
      beams: solid.beams.length,
      columns: solid.columns.length,
      hiddenNodes: hidden.nodes.length,
      hiddenWalls: hidden.walls.length,
      dimensions: Number(full?.counts?.dimensions) || 0,
    },
    editorState: full,
    objects2d: {
      walls: solid.walls,
      beams: solid.beams,
      columns: solid.columns,
      hiddenWalls: hidden.walls,
    },
    uiState: includeExtendedUiState
      ? {
          ...baseUiState,
          activeTool: activeTool.value,
          designMenuTool: designMenuTool.value,
          wallStyleDraft: wallStyleDraft.value,
          selectedWallStyle: selectedWallStyle.value,
          walls3dSnapshot: walls3dSnapshot.value,
        }
      : baseUiState,
  };
}

async function doCopyWallsJson() {
  const payload = buildDebugJsonPayload();
  if (!payload) return;
  const text = JSON.stringify(payload, null, 2);

  try {
    await navigator.clipboard.writeText(text);
    showAlert("JSON دیباگ دیوار، تیر و ستون کپی شد. برای من ارسال کنید.", { title: "کپی موفق" });
  } catch (_) {
    await showPrompt("کپی خودکار ممکن نبود. متن زیر را دستی کپی کنید:", text, { title: "کپی JSON دیباگ" });
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

const requiresOrderGate = computed(() => route.name === "floorplan");
const isOrderGateBlocking = computed(() => requiresOrderGate.value && !activeOrder.value);
const orderStatusOptions = [
  { value: "draft", label: "پیش نویس" },
  { value: "designing", label: "در حال طراحی" },
  { value: "submitted", label: "ثبت شده" },
  { value: "archived", label: "آرشیو" },
];
const orderStatusLabelMap = Object.fromEntries(orderStatusOptions.map((item) => [item.value, item.label]));
const activeOrderStatusLabel = computed(() => orderStatusLabelMap[String(activeOrder.value?.status || "draft")] || "پیش نویس");
const activeStageOrderDesign = computed(() =>
  orderDesignCatalog.value.find((item) => String(item.id) === String(activeCabinetDesignId.value || "")) || null
);
const selectedOrderDesignIds = computed(() => {
  const ids = [];
  const push = (value) => {
    const key = String(value || "").trim();
    if (key && !ids.includes(key)) ids.push(key);
  };
  if (activeStageOrderDesignSelected.value && activeCabinetDesignId.value) push(activeCabinetDesignId.value);
  for (const id of selectedStageOrderDesignIds.value) push(id);
  return ids;
});
const selectedOrderDesignSource = computed(() => {
  const ids = selectedOrderDesignIds.value;
  if (!ids.length) return activeStageOrderDesign.value;
  return orderDesignCatalog.value.find((item) => String(item.id) === String(ids[0])) || activeStageOrderDesign.value;
});
const activeStageOrderPlacement = computed(() => getOrderDesignPlacement(activeCabinetDesignId.value));
const draggedDoorAssetPreviewInstance = computed(() => {
  const drag = presetDrag.value;
  if (!drag?.active || drag.type !== "doorAsset" || !drag.preset?.modelUrl) return null;
  if (drag.dragBootstrapping || drag.createdDoorAssetId || cabinetDesignDropLoading.value) return null;
  const dx = drag.clientX - (drag.startX || drag.clientX);
  const dy = drag.clientY - (drag.startY || drag.clientY);
  if (Math.hypot(dx, dy) < PRESET_PREVIEW_MIN_DRAG_PX) return null;
  const dropWorld = clientPointToStageWorld(drag.clientX, drag.clientY);
  if (!dropWorld) return null;
  return {
    id: `door-drag-preview-${String(drag.preset.id || "door")}`,
    modelUrl: drag.preset.modelUrl,
    transform: {
      x: Number(dropWorld.x) || 0,
      y: Number(dropWorld.y) || 0,
      rotRad: 0,
    },
    dragPreview: true,
  };
});
const draggedCabinetPreviewInstance = computed(() => {
  const drag = presetDrag.value;
  if (!drag?.active || drag.type !== "cabinetDesign" || !drag.design?.preview?.viewer_boxes?.length) return null;
  if (drag.dragBootstrapping || drag.createdOrderDesignId || cabinetDesignDropLoading.value) return null;
  if (!drag.leftPanel) return null;

  const dx = drag.clientX - (drag.startX || drag.clientX);
  const dy = drag.clientY - (drag.startY || drag.clientY);
  if (Math.hypot(dx, dy) < PRESET_PREVIEW_MIN_DRAG_PX) return null;

  const dropWorld = clientPointToStageWorld(drag.clientX, drag.clientY);
  if (!dropWorld) return null;

  return {
    orderDesignId: `drag-preview-${String(drag.design.id || "cabinet")}`,
    boxes: drag.design.preview.viewer_boxes.map(normalizeCabinetBox),
    outlineColor: normalizeHexColor(drag.design.design_outline_color || drag.design.preview?.design_outline_color),
    transform: {
      x: Number(dropWorld.x) || 0,
      y: Number(dropWorld.y) || 0,
      rotRad: 0,
    },
    active: false,
    dragPreview: true,
  };
});
const stageOrderDesignInstances = computed(() =>
  [
    ...orderDesignPlacements.value
      .map((placement) => {
        const item = orderDesignCatalog.value.find((row) => String(row.id) === String(placement.orderDesignId));
        if (!item?.viewer_boxes?.length) return null;
        const isActive = String(item.id) === String(activeCabinetDesignId.value || "");
        const liveTransform = isActive ? getCurrentModel2dTransform() : null;
        return {
          orderDesignId: item.id,
          boxes: item.viewer_boxes.map(normalizeCabinetBox),
          outlineColor: normalizeHexColor(item.design_outline_color),
          transform: isActive
            ? {
                x: liveTransform.x,
                y: liveTransform.y,
                rotRad: liveTransform.rotRad,
                mirrorX: liveTransform.mirrorX,
              }
            : {
                x: placement.x,
                y: placement.y,
                rotRad: placement.rotRad,
                mirrorX: placement.mirrorX,
              },
          active: isActive,
        };
      })
      .filter(Boolean),
    ...(draggedCabinetPreviewInstance.value ? [draggedCabinetPreviewInstance.value] : []),
  ]
);
const stageDoorAssetInstances = computed(() => [
  ...doorScenePlacements.value
    .filter((placement) => String(placement.id) !== String(activeDoorAssetId.value || ""))
    .map((placement) => ({
      id: placement.id,
      modelUrl: placement.modelUrl,
      modelBoundsMm: placement.modelBoundsMm,
      transform: {
        x: placement.x,
        y: placement.y,
        rotRad: placement.rotRad,
        floorOffsetMm: placement.floorOffsetMm || 0,
      },
    })),
  ...(activeDoorAssetId.value
    ? (() => {
        const activePlacement = getDoorScenePlacement(activeDoorAssetId.value);
        if (!activePlacement) return [];
        const liveTransform = getCurrentModel2dTransform();
        return [{
          id: activePlacement.id,
          modelUrl: activePlacement.modelUrl,
          modelBoundsMm: activePlacement.modelBoundsMm,
          transform: {
            x: liveTransform.x,
            y: liveTransform.y,
            rotRad: liveTransform.rotRad,
            floorOffsetMm: activePlacement.floorOffsetMm || 0,
          },
        }];
      })()
    : []),
  ...(draggedDoorAssetPreviewInstance.value ? [draggedDoorAssetPreviewInstance.value] : []),
]);
const passiveStageOrderDesignModels = computed(() =>
  orderDesignPlacements.value
    .filter((placement) => String(placement.orderDesignId) !== String(activeCabinetDesignId.value || ""))
    .map((placement) => {
      const item = orderDesignCatalog.value.find((row) => String(row.id) === String(placement.orderDesignId));
      if (!item?.viewer_boxes?.length) return null;
      const geometry = getCachedOrderDesignGeometry(item);
      if (!geometry.outline.length || !geometry.lines.length) return null;
      return {
        id: placement.orderDesignId,
        geometrySpace: "local",
        lines: geometry.lines,
        outline: geometry.outline,
        transform: {
          x: placement.x,
          y: placement.y,
          rotRad: placement.rotRad,
          mirrorX: placement.mirrorX,
        },
        designCode: String(item.design_code || "").trim() || null,
        designTitle: String(item.design_title || "").trim() || null,
        instanceCode: String(item.instance_code || "").trim() || null,
        outlineColor: normalizeHexColor(item.design_outline_color),
        displayName:
          String(item.design_title || "").trim() ||
          String(item.instance_code || "").trim() ||
          String(placement.orderDesignId || "").trim() ||
          null,
      };
    })
    .filter((item) => item && item.outline.length >= 3 && item.lines.length >= 1)
);
function buildDoorAssetPlanGeometry(boundsMm) {
  const sanitized = sanitizeDoorBoundsMm(boundsMm);
  const widthMm = sanitized.widthMm;
  const depthMm = Math.max(40, sanitized.depthMm);
  const halfD = depthMm * 0.5;
  return {
    outline: [
      { x: 0, y: -halfD },
      { x: widthMm, y: -halfD },
      { x: widthMm, y: halfD },
      { x: 0, y: halfD },
    ],
    lines: [
      { ax: 0, ay: -halfD, bx: widthMm, by: -halfD },
      { ax: widthMm, ay: -halfD, bx: widthMm, by: halfD },
      { ax: widthMm, ay: halfD, bx: 0, by: halfD },
      { ax: 0, ay: halfD, bx: 0, by: -halfD },
      { ax: widthMm * 0.1, ay: 0, bx: widthMm * 0.9, by: 0 },
    ],
  };
}
const passiveDoorSceneModels = computed(() =>
  doorScenePlacements.value
    .filter((placement) => String(placement.id) !== String(activeDoorAssetId.value || ""))
    .map((placement) => {
      const geometry = buildDoorAssetPlanGeometry(placement.modelBoundsMm);
      return {
        id: placement.id,
      geometrySpace: "local",
      lines: geometry.lines,
      outline: geometry.outline,
      transform: {
        x: placement.x,
        y: placement.y,
        rotRad: placement.rotRad,
        mirrorX: 1,
      },
      designTitle: placement.title,
      displayName: placement.title,
      outlineColor: placement.outlineColor,
    };
  })
);
const isOrderDraftEditMode = computed(() => orderDraftMode.value === "edit");
const orderEntryPreviewNumber = computed(() => {
  if (isOrderDraftEditMode.value && activeOrder.value?.order_number) {
    return String(activeOrder.value.order_number);
  }
  const year = new Date().getFullYear();
  return `ORD-${year}-....`;
});
const orderEntryDisplayDate = computed(() =>
  formatOrderDate(isOrderDraftEditMode.value ? activeOrder.value?.submitted_at : new Date().toISOString())
);
const orderEntrySubmitLabel = computed(() =>
  ordersSaving.value
    ? isOrderDraftEditMode.value
      ? "در حال ذخیره..."
      : "در حال ثبت..."
    : isOrderDraftEditMode.value
      ? "ذخیره تغییرات سفارش"
      : "ثبت و ورود به طراحی"
);
const isActiveOrderHydrating = computed(() => orderOpening.value || orderDrawingLoading.value);

function normalizeOrderRecord(item) {
  if (!item) return null;
  return {
    id: String(item.id || ""),
    order_name: String(item.order_name || "").trim(),
    order_number: String(item.order_number || "").trim(),
    status: String(item.status || "draft").trim().toLowerCase(),
    notes: String(item.notes || "").trim(),
    submitted_at: String(item.submitted_at || ""),
    admin_id: String(item.admin_id || currentAdminId.value),
    admin_name: String(item.admin_name || currentAdminId.value).trim(),
    user_id: String(item.user_id || currentBootstrapUserId.value),
    user_name: String(item.user_name || currentBootstrapUserName.value).trim(),
  };
}

function buildOrderDrawingSavePayload() {
  const payload = buildDebugJsonPayload({ includeExtendedUiState: false });
  if (!payload) return null;
  return {
    drawing_payload: payload,
    walls_count: Number(payload?.counts?.walls) || 0,
    hidden_walls_count: Number(payload?.counts?.hiddenWalls) || 0,
    dimensions_count: Number(payload?.counts?.dimensions) || 0,
    beams_count: Number(payload?.counts?.beams) || 0,
    columns_count: Number(payload?.counts?.columns) || 0,
  };
}

function scheduleActiveOrderDrawingSave({ debounceMs = ORDER_DRAWING_AUTOSAVE_DEBOUNCE_MS } = {}) {
  if (_orderDrawingSaveTimeout) {
    clearTimeout(_orderDrawingSaveTimeout);
  }
  _orderDrawingSaveTimeout = window.setTimeout(() => {
    _orderDrawingSaveTimeout = 0;
    saveActiveOrderDrawing().catch(() => {});
  }, Math.max(0, Number(debounceMs) || 0));
}

function formatOrderDate(value) {
  const date = value ? new Date(value) : null;
  if (!date || Number.isNaN(date.getTime())) return "-";
  try {
    return new Intl.DateTimeFormat("fa-IR", {
      year: "numeric",
      month: "2-digit",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(date);
  } catch (_) {
    return date.toLocaleString();
  }
}

async function loadOrders() {
  ordersLoading.value = true;
  try {
    const res = await fetch(`/api/orders?admin_id=${encodeURIComponent(currentAdminId.value)}`);
    if (!res.ok) throw new Error("load-orders-failed");
    ordersCatalog.value = (await res.json()).map(normalizeOrderRecord).filter(Boolean);
    if (activeOrder.value) {
      const fresh = ordersCatalog.value.find((item) => item.id === activeOrder.value.id) || null;
      activeOrder.value = fresh;
    }
    if (!activeOrder.value) {
      orderEntryTab.value = ordersCatalog.value.length ? "list" : "create";
    }
  } catch (_) {
    showAlert("خواندن سفارش‌ها انجام نشد.", { title: "خطا" });
  } finally {
    ordersLoading.value = false;
  }
}

function openOrderEntry(tab = null) {
  if (tab) orderEntryTab.value = tab;
  else if (!activeOrder.value) orderEntryTab.value = ordersCatalog.value.length ? "list" : "create";
  orderEntryOpen.value = true;
}

function closeOrderEntry(force = false) {
  if (!force && !activeOrder.value && requiresOrderGate.value) return;
  orderEntryOpen.value = false;
}

function cancelPendingOrderDrawingSave() {
  if (_orderDrawingSaveTimeout) {
    clearTimeout(_orderDrawingSaveTimeout);
    _orderDrawingSaveTimeout = 0;
  }
}

function resetActiveOrderWorkspace({ clearEditor = true } = {}) {
  cancelPendingOrderDrawingSave();
  orderDesignCatalog.value = [];
  orderDesignCatalogLoadedForOrderId.value = "";
  orderDesignPlacements.value = [];
  stageCabinetPlaceholderBoxes.value = [];
  activeCabinetDesignId.value = null;
  activeStageOrderDesignSelected.value = false;
  selectedStageOrderDesignIds.value = [];
  if (clearEditor) {
    editorRef.value?.clearAll?.();
    editorRef.value?.goOrigin?.();
  }
}

async function ensureOrderGate() {
  if (!requiresOrderGate.value) return;
  if (!ordersCatalog.value.length && !ordersLoading.value) {
    await loadOrders();
  }
  if (!activeOrder.value) {
    openOrderEntry();
  }
}

function resetOrderDraft() {
  orderDraft.value = { order_name: "", notes: "", status: "draft" };
}

function hydrateOrderDraftFromOrder(item) {
  const normalized = normalizeOrderRecord(item);
  if (!normalized) {
    resetOrderDraft();
    return;
  }
  orderDraft.value = {
    order_name: String(normalized.order_name || "").trim(),
    notes: String(normalized.notes || "").trim(),
    status: String(normalized.status || "draft"),
  };
}

function openOrderCreate(defaultName = "طرح جدید") {
  orderDraftMode.value = "create";
  resetOrderDraft();
  orderDraft.value.order_name = String(defaultName || "طرح جدید").trim() || "طرح جدید";
  orderEntryTab.value = "create";
  orderEntryOpen.value = true;
}

function openOrderEditor() {
  if (!activeOrder.value) {
    openOrderEntry();
    return;
  }
  orderDraftMode.value = "edit";
  hydrateOrderDraftFromOrder(activeOrder.value);
  orderEntryTab.value = "create";
  orderEntryOpen.value = true;
}

async function handleMissingActiveOrder(message = "سفارش فعال دیگر در دیتابیس وجود ندارد. یکی از سفارش‌های موجود را دوباره انتخاب کنید.") {
  resetActiveOrderWorkspace();
  activeOrder.value = null;
  orderDraftMode.value = "create";
  resetOrderDraft();
  await loadOrders();
  openOrderEntry("list");
  showAlert(message, { title: "سفارش یافت نشد" });
}

async function loadOrderDrawing(orderId, { clearWhenMissing = true } = {}) {
  const normalizedOrderId = String(orderId || "").trim();
  if (!normalizedOrderId) return false;
  orderDrawingLoading.value = true;
  try {
    const res = await fetch(`/api/orders/${encodeURIComponent(normalizedOrderId)}/drawing`);
    if (res.status === 404) {
      if (clearWhenMissing) {
        editorRef.value?.clearAll?.();
        editorRef.value?.goOrigin?.();
      }
      return false;
    }
    if (!res.ok) {
      const message = await readApiErrorMessage(res, "خواندن ترسیمات سفارش انجام نشد.");
      if (res.status === 404 && /Order not found/i.test(message)) {
        await handleMissingActiveOrder();
        return false;
      }
      throw new Error(message);
    }
    const payload = await res.json();
    const snapshot = payload?.drawing_payload?.editorState || null;
    const savedUiState = payload?.drawing_payload?.uiState || {};
    if (snapshot && editorRef.value?.restoreSnapshot) {
      editorRef.value.restoreSnapshot(snapshot);
    } else if (clearWhenMissing) {
      editorRef.value?.clearAll?.();
      editorRef.value?.goOrigin?.();
    }
    const savedBoxes = Array.isArray(savedUiState?.stageCabinetPlaceholderBoxes)
      ? savedUiState.stageCabinetPlaceholderBoxes.map(normalizeCabinetBox)
      : [];
    stageCabinetPlaceholderBoxes.value = savedBoxes;
    orderDesignPlacements.value = Array.isArray(savedUiState?.orderDesignPlacements)
      ? savedUiState.orderDesignPlacements.map(normalizeOrderDesignPlacement).filter(Boolean)
      : [];
    activeCabinetDesignId.value = String(savedUiState?.activeCabinetDesignId || "").trim() || null;
    if (!orderDesignPlacements.value.length && activeCabinetDesignId.value) {
      upsertOrderDesignPlacement({
        orderDesignId: activeCabinetDesignId.value,
        ...getCurrentEditorModelPlacement(),
      });
    }
    syncQuickStateFromEditor();
    return true;
  } catch (error) {
    showAlert(error?.message || "خواندن ترسیمات سفارش انجام نشد.", { title: "خطا" });
    return false;
  } finally {
    orderDrawingLoading.value = false;
  }
}

function hasOrderDraftChanges() {
  if (!activeOrder.value || !isOrderDraftEditMode.value) return false;
  return (
    String(orderDraft.value.order_name || "").trim() !== String(activeOrder.value.order_name || "").trim() ||
    String(orderDraft.value.notes || "").trim() !== String(activeOrder.value.notes || "").trim() ||
    String(orderDraft.value.status || "draft") !== String(activeOrder.value.status || "draft")
  );
}

async function createOrder() {
  const orderName = String(orderDraft.value.order_name || "").trim();
  if (!orderName) {
    showAlert("نام سفارش را وارد کنید.", { title: "خطا" });
    return;
  }
  ordersSaving.value = true;
  try {
    const res = await fetch("/api/orders", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        admin_id: currentAdminId.value,
        user_id: currentBootstrapUserId.value,
        order_name: orderName,
        notes: String(orderDraft.value.notes || "").trim() || null,
        status: String(orderDraft.value.status || "draft"),
      }),
    });
    if (!res.ok) {
      let detail = "";
      try {
        const payload = await res.json();
        detail = String(payload?.detail || "").trim();
      } catch (_) {}
      throw new Error(detail || `create-order-failed-${res.status}`);
    }
    const created = normalizeOrderRecord(await res.json());
    resetActiveOrderWorkspace();
    activeOrder.value = created;
    orderDraftMode.value = "edit";
    hydrateOrderDraftFromOrder(created);
    await loadOrderDrawing(created.id, { clearWhenMissing: true });
    await loadOrders();
    await loadOrderDesignCatalog(true);
    closeOrderEntry(true);
  } catch (err) {
    const message = String(err?.message || "");
    if (message.includes("User not found")) {
      showAlert("کاربر bootstrap برای این ادمین در دیتابیس پیدا نشد. backend را با migration جدید بروزرسانی و restart کنید.", { title: "خطا" });
    } else if (message.includes("unique order number") || message.includes("409")) {
      showAlert("شماره سفارش تکراری شد. دوباره تلاش کنید یا backend را restart کنید تا generator جدید بارگذاری شود.", { title: "خطا" });
    } else {
      showAlert("ثبت سفارش انجام نشد.", { title: "خطا" });
    }
  } finally {
    ordersSaving.value = false;
  }
}

async function updateOrder() {
  const target = normalizeOrderRecord(activeOrder.value);
  if (!target?.id) {
    openOrderEntry();
    return;
  }
  const orderName = String(orderDraft.value.order_name || "").trim();
  if (!orderName) {
    showAlert("نام سفارش را وارد کنید.", { title: "خطا" });
    return;
  }
  if (!hasOrderDraftChanges()) {
    showAlert("تغییری برای ذخیره وجود ندارد.", { title: "ذخیره سفارش" });
    return;
  }
  ordersSaving.value = true;
  try {
    const res = await fetch(`/api/orders/${encodeURIComponent(target.id)}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        order_name: orderName,
        notes: String(orderDraft.value.notes || "").trim() || null,
        status: String(orderDraft.value.status || "draft"),
      }),
    });
    if (!res.ok) throw new Error(await readApiErrorMessage(res, "update-order-failed"));
    const updated = normalizeOrderRecord(await res.json());
    activeOrder.value = updated;
    orderDraftMode.value = "edit";
    hydrateOrderDraftFromOrder(updated);
    await loadOrders();
    closeOrderEntry(true);
    showAlert("آخرین تغییرات سفارش ذخیره شد.", { title: "ذخیره سفارش" });
  } catch (_) {
    showAlert("ذخیره سفارش انجام نشد.", { title: "خطا" });
  } finally {
    ordersSaving.value = false;
  }
}

async function saveActiveOrderDrawing() {
  if (orderOpening.value || orderDrawingLoading.value) {
    return false;
  }
  const target = normalizeOrderRecord(activeOrder.value);
  if (!target?.id) {
    openOrderEntry();
    return false;
  }
  const payload = buildOrderDrawingSavePayload();
  if (!payload) {
    showAlert("ترسیم فعالی برای ذخیره وجود ندارد.", { title: "ذخیره سفارش" });
    return false;
  }
  const res = await fetch(`/api/orders/${encodeURIComponent(target.id)}/drawing`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const message = await readApiErrorMessage(res, "ذخیره ترسیمات سفارش انجام نشد.");
    if (res.status === 404 && /Order not found/i.test(message)) {
      await handleMissingActiveOrder();
      return false;
    }
    throw new Error(message);
  }
  return true;
}

async function selectOrder(item) {
  orderOpening.value = true;
  orderOpeningLabel.value = String(item?.order_name || item?.order_number || "سفارش").trim() || "سفارش";
  try {
    resetActiveOrderWorkspace();
    activeOrder.value = normalizeOrderRecord(item);
    orderDraftMode.value = "edit";
    hydrateOrderDraftFromOrder(activeOrder.value);
    await Promise.all([
      loadOrderDrawing(activeOrder.value?.id, { clearWhenMissing: true }),
      loadOrderDesignCatalog(true),
    ]);
    reconcileActiveOrderDesignSelection();
    closeOrderEntry(true);
  } finally {
    orderOpening.value = false;
    orderOpeningLabel.value = "";
  }
}

function toggleInternalPartGroupParamGroupsPanel() {
  internalPartGroupParamGroupsOpen.value = !internalPartGroupParamGroupsOpen.value;
}

function isParamGroupSelectedInInternalGroup(paramGroupId) {
  return !!internalPartGroupEditorDraft.value?.param_groups?.some((group) => Number(group.param_group_id) === Number(paramGroupId) && group.enabled !== false);
}

function toggleParamGroupInInternalGroup(paramGroupId) {
  const draft = internalPartGroupEditorDraft.value;
  if (!draft) return;
  const existing = draft.param_groups.find((group) => Number(group.param_group_id) === Number(paramGroupId));
  if (existing) {
    draft.param_groups = draft.param_groups.filter((group) => Number(group.param_group_id) !== Number(paramGroupId));
  } else {
    const option = constructionInternalParamGroupOptions.value.find((item) => Number(item.id) === Number(paramGroupId));
    draft.param_groups = [
      ...draft.param_groups,
      {
        param_group_id: Number(paramGroupId),
        param_group_code: String(option?.code || "").trim(),
        param_group_title: String(option?.title || "").trim(),
        param_group_icon_path: normalizeIconFileName(option?.iconPath) || "",
        enabled: true,
        ui_order: draft.param_groups.length || Number(option?.uiOrder) || 0,
      },
    ];
  }
  ensureInternalPartGroupParamDefaults(draft);
}

async function archiveOrder(item) {
  const target = normalizeOrderRecord(item);
  if (!target?.id) return;
  const ok = await showConfirm(`سفارش «${target.order_name || target.order_number || "بدون نام"}» آرشیو شود؟`, { title: "آرشیو سفارش" });
  if (!ok) return;
  ordersSaving.value = true;
  try {
    const res = await fetch(`/api/orders/${encodeURIComponent(target.id)}`, { method: "DELETE" });
    if (!res.ok) throw new Error("archive-order-failed");
    if (activeOrder.value?.id === target.id) {
      resetActiveOrderWorkspace();
      activeOrder.value = null;
    }
    await loadOrders();
    await ensureOrderGate();
  } catch (_) {
    showAlert("آرشیو سفارش انجام نشد.", { title: "خطا" });
  } finally {
    ordersSaving.value = false;
  }
}

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
  const hasDims = (s?.dimensionsSnap?.length || s?.counts?.dimensions || 0) > 0;
  return !(hasWalls || hasHidden || hasDims);
}

function doNewDesign() {
  openOrderCreate("طرح جدید");
}

async function doSaveProject() {
  if (!activeOrder.value) {
    openOrderEntry();
    return;
  }
  const shouldSaveMeta = orderEntryOpen.value && orderEntryTab.value === "create" && isOrderDraftEditMode.value && hasOrderDraftChanges();
  ordersSaving.value = true;
  try {
    if (!isOrderDraftEditMode.value) {
      orderDraftMode.value = "edit";
      hydrateOrderDraftFromOrder(activeOrder.value);
    }
    if (shouldSaveMeta) {
      const res = await fetch(`/api/orders/${encodeURIComponent(activeOrder.value.id)}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          order_name: String(orderDraft.value.order_name || "").trim(),
          notes: String(orderDraft.value.notes || "").trim() || null,
          status: String(orderDraft.value.status || "draft"),
        }),
      });
      if (!res.ok) throw new Error(await readApiErrorMessage(res, "update-order-failed"));
      const updated = normalizeOrderRecord(await res.json());
      activeOrder.value = updated;
      hydrateOrderDraftFromOrder(updated);
    }
    await saveActiveOrderDrawing();
    await loadOrders();
    showAlert("آخرین تغییرات سفارش و ترسیمات آن ذخیره شد.", { title: "ذخیره سفارش" });
    if (orderEntryOpen.value && orderEntryTab.value === "create" && isOrderDraftEditMode.value) {
      closeOrderEntry(true);
    }
  } catch (error) {
    showAlert(error?.message || "ذخیره سفارش انجام نشد.", { title: "خطا" });
  } finally {
    ordersSaving.value = false;
  }
}

function doOpenPicker() {
  orderDraftMode.value = activeOrder.value ? "edit" : "create";
  openOrderEntry("list");
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
  doOpenPicker();
}
function doSaveFromTopbar() {
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
  editorRef.value?.fitSelectionOrAll?.();
  stageGlbViewerRef.value?.fitCameraToSelectionOrAll?.();
}
function doSeeOrigin() {
  editorRef.value?.goOrigin?.();
}

async function setTool(tool) {
  activeTool.value = tool;

  const isDrawingTool = tool === "wall" || tool === "hidden" || tool === "dimension" || tool === "beam" || tool === "door";
  if (route.path !== "/" && isDrawingTool) {
    await router.push("/");
  }

  if (tool === "wall") editorRef.value?.setActiveTool?.("wall");
  else if (tool === "door") editorRef.value?.setActiveTool?.("door");
  else if (tool === "hidden") editorRef.value?.setActiveTool?.("hidden");
  else if (tool === "dimension") editorRef.value?.setActiveTool?.("dim");
  else if (tool === "beam") editorRef.value?.setActiveTool?.("beam");
}

async function setDesignMenuTool(id) {
  designMenuTool.value = id;
  const it = designMenuTools.find((x) => x.id === id);
  if (it?.mapsToTool) await setTool(it.mapsToTool);

  const mode =
    (id === "wall") ? "wall" :
    (id === "door") ? "door" :
    (id === "hidden") ? "hidden" :
    (id === "dimension") ? "dim" :
    (id === "beam") ? "beam" :
    (id === "column") ? "clicker" :
    null;
  editorRef.value?.setUiCursorMode?.(mode);
  setDraftFromDesignTool(id);
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
  () => activeOrder.value?.id || "",
  async (orderId, previousId) => {
    if (orderId && orderId !== previousId) {
      await loadOrderDesignCatalog(true);
      reconcileActiveOrderDesignSelection();
      return;
    }
    if (!orderId) {
      orderDesignCatalog.value = [];
      orderDesignCatalogLoadedForOrderId.value = "";
      orderDesignPlacements.value = [];
      stageCabinetPlaceholderBoxes.value = [];
      activeCabinetDesignId.value = null;
      activeStageOrderDesignSelected.value = false;
      selectedStageOrderDesignIds.value = [];
    }
  }
);

watch(
  () => [
    String(activeCabinetDesignId.value || ""),
    String(activeOrder.value?.id || ""),
    orderDesignCatalog.value.length,
  ],
  () => {
    reconcileActiveOrderDesignSelection();
  }
);

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

onMounted(() => {
  getDoorModelBoundsMm(DEFAULT_DOOR_MODEL_URL)
    .then((boundsMm) => {
      doorAssetLibrary.value = doorAssetLibrary.value.map((item) => ({
        ...item,
        modelBoundsMm: boundsMm,
      }));
    })
    .catch(() => {});
  nextTick(() => {
    syncInteriorLibraryFrontViewport();
  });
});

watch(
  () => ({
    x: Number.isFinite(Number(model2dTransformRef.value?.x)) ? Number(model2dTransformRef.value.x) : 0,
    y: Number.isFinite(Number(model2dTransformRef.value?.y)) ? Number(model2dTransformRef.value.y) : 0,
    rotRad: Number.isFinite(Number(model2dTransformRef.value?.rotRad)) ? Number(model2dTransformRef.value.rotRad) : 0,
    mirrorX: 1,
  }),
  (transform) => {
    if (_orderDesignPlacementSyncPaused) return;
    if (activeCabinetDesignId.value) {
      upsertOrderDesignPlacement({
        orderDesignId: activeCabinetDesignId.value,
        ...transform,
      });
      return;
    }
    if (activeDoorAssetId.value) {
      const current = getDoorScenePlacement(activeDoorAssetId.value);
      if (!current) return;
      upsertDoorScenePlacement({
        ...current,
        ...transform,
      });
    }
  },
  { deep: true }
);

watch(
  () => ({
    editorReady: !!editorRef.value,
    models: [...passiveStageOrderDesignModels.value, ...passiveDoorSceneModels.value],
  }),
  ({ models }) => {
    editorRef.value?.setPassiveModels?.(models);
  },
  { deep: true, immediate: true }
);

watch(
  passiveModelSelectionStateRef,
  (ids) => {
    const orderIds = new Set(orderDesignCatalog.value.map((item) => String(item.id || "").trim()).filter(Boolean));
    const doorIds = new Set(doorScenePlacements.value.map((item) => String(item.id || "").trim()).filter(Boolean));
    const nextIds = Array.isArray(ids) ? ids.map((id) => String(id || "").trim()).filter(Boolean) : [];
    selectedStageOrderDesignIds.value = nextIds.filter((id) => orderIds.has(id));
    selectedStageDoorAssetIds.value = nextIds.filter((id) => doorIds.has(id));
  },
  { immediate: true }
);

watch(
  passiveModelTransformStateRef,
  (models) => {
    if (!Array.isArray(models) || !models.length) return;
    const validIds = new Set(orderDesignCatalog.value.map((item) => String(item.id || "").trim()).filter(Boolean));
    for (const model of models) {
      const orderDesignId = String(model?.id || "").trim();
      if (!orderDesignId || !validIds.has(orderDesignId)) continue;
      upsertOrderDesignPlacement({
        orderDesignId,
        x: Number.isFinite(Number(model?.x)) ? Number(model.x) : 0,
        y: Number.isFinite(Number(model?.y)) ? Number(model.y) : 0,
        rotRad: Number.isFinite(Number(model?.rotRad)) ? Number(model.rotRad) : 0,
        mirrorX: 1,
      });
    }
    let changedDoorPlacements = false;
    const nextDoorPlacements = doorScenePlacements.value.map((placement) => {
      const match = models.find((model) => String(model?.id || "") === String(placement.id || ""));
      if (!match) return placement;
      changedDoorPlacements = true;
      return {
        ...placement,
        x: Number.isFinite(Number(match?.x)) ? Number(match.x) : placement.x,
        y: Number.isFinite(Number(match?.y)) ? Number(match.y) : placement.y,
        rotRad: Number.isFinite(Number(match?.rotRad)) ? Number(match.rotRad) : placement.rotRad,
      };
    });
    if (changedDoorPlacements) doorScenePlacements.value = nextDoorPlacements;
  },
  { immediate: true, deep: true }
);

function setMenu(menuId) {
  activeMenu.value = menuId;
  openMenuPanel.value = menuId;
  closeInteriorLibrary();
}

function closeMenuPanel() {
  if (constructionWizardOpen.value) {
    closeConstructionWizard();
    scheduleSubRailPosition();
    return;
  }
  openMenuPanel.value = null;
  activeMenu.value = null;
  activeSubRail.value = null;
  closeInteriorLibrary();
  openMode.value = "menu";
  editorRef.value?.setInputEnabled?.(true);
  scheduleSubRailPosition();
}

async function openInteriorLibrary(targetOrderDesignId = "") {
  const nextTargetOrderDesignId = String(targetOrderDesignId || "").trim();
  const currentTargetOrderDesignId = String(activeInteriorLibraryOrderDesignId.value || "").trim();
  if (interiorLibraryOpen.value && (!nextTargetOrderDesignId || nextTargetOrderDesignId === currentTargetOrderDesignId)) {
    closeInteriorLibrary();
    return;
  }
  if (!subCategoryDesignEditorOpen.value) {
    const fallbackTargetId = String(getSelectedOrderDesignSourceLocal()?.id || "").trim();
    const resolvedTargetId = nextTargetOrderDesignId || fallbackTargetId;
    if (!resolvedTargetId) {
      showAlert("ابتدا یک طرح ثبت‌شده را انتخاب کنید.", { title: "قطعات داخلی" });
      return;
    }
    interiorLibraryForcedOrderDesignId.value = resolvedTargetId;
  } else {
    interiorLibraryForcedOrderDesignId.value = "";
  }
  if (!subCategoryDesignEditorOpen.value && !activeInteriorLibraryOrderDesign.value?.id) {
    showAlert("ابتدا یک طرح ثبت‌شده را انتخاب کنید.", { title: "قطعات داخلی" });
    return;
  }
  interiorLibraryOpen.value = true;
  interiorLibraryPreviewMode.value = "front2d";
  interiorLibraryFrontZoom.value = 1;
  interiorLibraryPreviewOpacity.value = 100;
  interiorLibraryShowInnerLines.value = true;
  resetInteriorLibraryAnnotations();
  interiorLibraryFrontPan.value = { x: 0, y: 0 };
  stopInteriorLibraryFrontPan();
  activeMenu.value = null;
  openMenuPanel.value = null;
  activeSubRail.value = null;
  openMode.value = "menu";
  await Promise.allSettled([
    loadConstructionInternalPartGroups(),
    loadConstructionSubCategoryDesigns(),
    loadConstructionPartKinds(),
    loadConstructionPartFormulas(),
  ]);
  if (!subCategoryDesignEditorOpen.value && activeOrder.value?.id) {
    await loadOrderDesignCatalog(true);
  }
  if (subCategoryDesignEditorOpen.value && !subCategoryDesignPreviewLoading.value) {
    await refreshSubCategoryDesignPreview();
  }
  scheduleSubRailPosition();
}

function openInteriorLibraryForDesign(orderDesignId) {
  return openInteriorLibrary(orderDesignId);
}

function closeInteriorLibrary() {
  interiorLibraryOpen.value = false;
  interiorLibraryControllerTestMode.value = false;
  interiorLibraryControllerEditingId.value = "";
  interiorLibraryControllerInputDraft.value = "";
  interiorLibraryControllerDraftValues.value = null;
  interiorLibraryHoveredControllerId.value = "";
  interiorLibraryControllerPointerState.value = {
    mode: "idle",
    pointerId: null,
    controllerId: "",
    startPoint: null,
    startPan: null,
    startValues: null,
    pointerToAnchor: null,
    dirty: false,
  };
  interiorLibraryForcedOrderDesignId.value = "";
  interiorLibraryPreviewMode.value = "front2d";
  interiorLibraryFrontZoom.value = 1;
  interiorLibraryPreviewOpacity.value = 100;
  interiorLibraryShowInnerLines.value = true;
  resetInteriorLibraryAnnotations();
  interiorLibraryFrontPan.value = { x: 0, y: 0 };
  stopInteriorLibraryFrontPan();
  closeInteriorInstanceEditor();
}

function openInteriorControllerTest() {
  if (!interiorLibraryControllerTestMode.value) {
    interiorLibraryPreviewMode.value = "front2d";
  }
  interiorLibraryControllerTestMode.value = !interiorLibraryControllerTestMode.value;
  interiorLibraryControllerEditingId.value = "";
  interiorLibraryControllerInputDraft.value = "";
  interiorLibraryControllerDraftValues.value = null;
  interiorLibraryHoveredControllerId.value = "";
}

function disable2dInput() {
  editorRef.value?.setInputEnabled?.(false);
}
function enable2dInput() {
  editorRef.value?.setInputEnabled?.(true);
}

function onGlbModel2d(payload) {
  if (Array.isArray(stageCabinetPlaceholderBoxes.value) && stageCabinetPlaceholderBoxes.value.length) return;
  const lines = payload?.lines;
  if (!Array.isArray(lines)) return;
  editorRef.value?.setModel2dLines?.(lines, payload?.opts || null);
}

function getEditorStateSnapshot() {
  return editorRef.value?.getState?.()?.state || {};
}
const currentEditorDisplayUnit = computed(() => {
  return currentEditorDisplayUnitState.value === "mm" || currentEditorDisplayUnitState.value === "inch"
    ? currentEditorDisplayUnitState.value
    : "cm";
});

function setDraftFromDesignTool(id) {
  const st = getEditorStateSnapshot();
  wallStyleDraftTouched.value = false;
  if (id === "beam") {
    wallStyleDraft.value = {
      thicknessCm: (Number.isFinite(Number(st?.beamThicknessMm)) ? Number(st.beamThicknessMm) : 400) / 10,
      heightCm: (Number.isFinite(Number(st?.beamHeightMm)) ? Number(st.beamHeightMm) : 200) / 10,
      floorOffsetCm: (Number.isFinite(Number(st?.beamFloorOffsetMm)) ? Number(st.beamFloorOffsetMm) : 2600) / 10,
      color: String(st?.beam3dColor || "#C7CCD1"),
    };
    return;
  }
  if (id === "column") {
    wallStyleDraft.value = {
      thicknessCm: (Number.isFinite(Number(st?.columnDepthMm)) ? Number(st.columnDepthMm) : 400) / 10,
      heightCm: (Number.isFinite(Number(st?.columnHeightMm)) ? Number(st.columnHeightMm) : 2800) / 10,
      floorOffsetCm: 0,
      lengthCm: (Number.isFinite(Number(st?.columnWidthMm)) ? Number(st.columnWidthMm) : 500) / 10,
      color: String(st?.column3dColor || "#C7CCD1"),
    };
    return;
  }
  if (id === "wall") {
    wallStyleDraft.value = {
      thicknessCm: (Number.isFinite(Number(st?.wallThicknessMm)) ? Number(st.wallThicknessMm) : 120) / 10,
      heightCm: (Number.isFinite(Number(st?.wallHeightMm)) ? Number(st.wallHeightMm) : 3000) / 10,
      floorOffsetCm: 0,
      color: String(st?.wall3dColor || "#C7CCD1"),
    };
    return;
  }
  if (id === "door") {
    wallStyleDraft.value = {
      lengthCm: 90,
      heightCm: 220,
      floorOffsetCm: 0,
      color: "#8B6B4A",
    };
  }
}

function startWallPresetDrag(ev, preset) {
  if (!preset || !ev?.isPrimary) return;
  presetDrag.value = {
    ...createEmptyPresetDragState(),
    active: true,
    type: "wallPreset",
    preset,
    clientX: ev.clientX,
    clientY: ev.clientY,
    startX: ev.clientX,
    startY: ev.clientY,
    sessionId: ++presetDragSessionSeed,
  };
  disable2dInput();
  window.addEventListener("pointermove", onPresetPointerMove);
  window.addEventListener("pointerup", onPresetPointerUp, { once: true });
}

function startDoorPresetDrag(ev, preset) {
  if (!preset || !ev?.isPrimary) return;
  designMenuTool.value = "door";
  const sessionId = ++presetDragSessionSeed;
  presetDrag.value = {
    ...createEmptyPresetDragState(),
    active: true,
    type: "doorPreset",
    preset,
    clientX: ev.clientX,
    clientY: ev.clientY,
    startX: ev.clientX,
    startY: ev.clientY,
    sessionId,
  };
  primeDoorPresetModel(preset).then((resolvedPreset) => {
    if (!resolvedPreset) return;
    if (!presetDrag.value?.active || presetDrag.value?.type !== "doorPreset") return;
    if (presetDrag.value?.sessionId !== sessionId) return;
    if (String(presetDrag.value?.preset?.id || "") !== String(preset.id || "")) return;
    presetDrag.value = {
      ...presetDrag.value,
      preset: resolvedPreset,
    };
  }).catch(() => {});
  disable2dInput();
  window.addEventListener("pointermove", onPresetPointerMove);
  window.addEventListener("pointerup", onPresetPointerUp, { once: true });
}

function startDoorAssetDrag(ev, item) {
  if (!item || !ev?.isPrimary) return;
  presetDrag.value = {
    ...createEmptyPresetDragState(),
    active: true,
    type: "doorAsset",
    preset: item,
    clientX: ev.clientX,
    clientY: ev.clientY,
    startX: ev.clientX,
    startY: ev.clientY,
    enteredStage: false,
    leftPanel: false,
    sessionId: ++presetDragSessionSeed,
  };
  disable2dInput();
  window.addEventListener("pointermove", onPresetPointerMove);
  window.addEventListener("pointerup", onPresetPointerUp, { once: true });
}

async function ensureDoorAssetDragPlacement(clientX, clientY) {
  const drag = { ...presetDrag.value };
  if (!drag.active || drag.type !== "doorAsset" || !drag.preset?.modelUrl || drag.dragBootstrapping) return false;
  const sessionId = drag.sessionId;
  const previousActiveDoorAssetId = String(activeDoorAssetId.value || "").trim();
  const previousActiveDoorPlacement = previousActiveDoorAssetId ? { ...(getDoorScenePlacement(previousActiveDoorAssetId) || getCurrentEditorModelPlacement()) } : null;
  presetDrag.value = {
    ...drag,
    dragBootstrapping: true,
    previousActiveDoorAssetId,
    previousActiveDoorPlacement,
  };
  cabinetDesignDropLoadingMode.value = "door";
  cabinetDesignDropLoading.value = true;
  cabinetDesignDropLoadingTitle.value = String(drag.preset?.title || "درب").trim();
  try {
    const currentDrag = presetDrag.value;
    if (!currentDrag.active || currentDrag.sessionId !== sessionId || currentDrag.type !== "doorAsset") return false;
    const latestClientX = Number.isFinite(Number(presetDrag.value.clientX)) ? Number(presetDrag.value.clientX) : clientX;
    const latestClientY = Number.isFinite(Number(presetDrag.value.clientY)) ? Number(presetDrag.value.clientY) : clientY;
    const dropWorld = clientPointToStageWorld(latestClientX, latestClientY);
    if (!dropWorld) return false;
    const boundsMm = drag.preset.modelBoundsMm || await getDoorModelBoundsMm(drag.preset.modelUrl);
    const nextId = `door-scene-${doorScenePlacementSeed++}`;
    const nextPlacement = normalizeDoorScenePlacement({
      id: nextId,
      title: drag.preset.title || "Door",
      modelUrl: drag.preset.modelUrl,
      modelBoundsMm: boundsMm,
      outlineColor: drag.preset.outlineColor || "#8B6B4A",
      x: Number(dropWorld.x) || 0,
      y: Number(dropWorld.y) || 0,
      rotRad: 0,
    });
    if (!nextPlacement) return false;
    upsertDoorScenePlacement(nextPlacement);
    const restored = restoreActiveDoorAssetToEditor(nextPlacement, nextPlacement);
    await nextTick();
    presetDrag.value = {
      ...presetDrag.value,
      createdDoorAssetId: nextId,
      dragBootstrapping: false,
      dragStarted: restored,
      previousActiveDoorAssetId,
      previousActiveDoorPlacement,
    };
    syncQuickStateFromEditor();
    if (presetDrag.value.releasePending) {
      const releaseX = Number.isFinite(Number(presetDrag.value.releaseClientX)) ? Number(presetDrag.value.releaseClientX) : latestClientX;
      const releaseY = Number.isFinite(Number(presetDrag.value.releaseClientY)) ? Number(presetDrag.value.releaseClientY) : latestClientY;
      const stageRect = stageEl.value?.getBoundingClientRect();
      const inStage = !!stageRect && releaseX >= stageRect.left && releaseX <= stageRect.right
        && releaseY >= stageRect.top && releaseY <= stageRect.bottom;
      const commit = inStage
        && Math.hypot(releaseX - (presetDrag.value.startX || releaseX), releaseY - (presetDrag.value.startY || releaseY)) >= PRESET_PREVIEW_MIN_DRAG_PX
        && presetDrag.value.enteredStage;
      if (commit) {
        enable2dInput();
        const dragStarted = !!editorRef.value?.beginModelDragAtClient?.(releaseX, releaseY);
        if (dragStarted) editorRef.value?.updateModelDragAtClient?.(releaseX, releaseY);
        syncQuickStateFromEditor();
      }
      finishPresetDragSession();
    }
    return true;
  } finally {
    cabinetDesignDropLoading.value = false;
    cabinetDesignDropLoadingTitle.value = "";
    cabinetDesignDropLoadingMode.value = "add";
  }
}

function startColumnDrag(ev) {
  if (!ev?.isPrimary) return;
  designMenuTool.value = "column";
  setDraftFromDesignTool("column");
  presetDrag.value = {
    ...createEmptyPresetDragState(),
    active: true,
    type: "column",
    clientX: ev.clientX,
    clientY: ev.clientY,
    startX: ev.clientX,
    startY: ev.clientY,
    sessionId: ++presetDragSessionSeed,
  };
  disable2dInput();
  window.addEventListener("pointermove", onPresetPointerMove);
  window.addEventListener("pointerup", onPresetPointerUp, { once: true });
}

function startCabinetDesignDrag(ev, design) {
  if (!ev?.isPrimary || !design?.preview?.viewer_boxes?.length) return;
  presetDrag.value = {
    ...createEmptyPresetDragState(),
    active: true,
    type: "cabinetDesign",
    design,
    clientX: ev.clientX,
    clientY: ev.clientY,
    startX: ev.clientX,
    startY: ev.clientY,
    sessionId: ++presetDragSessionSeed,
  };
  disable2dInput();
  window.addEventListener("pointermove", onPresetPointerMove);
  window.addEventListener("pointerup", onPresetPointerUp, { once: true });
}

async function onPresetPointerMove(ev) {
  if (!presetDrag.value.active) return;
  const stageRect = stageEl.value?.getBoundingClientRect();
  const panelRect = menuPanelEl.value?.getBoundingClientRect();
  const inStage = !!stageRect
    && ev.clientX >= stageRect.left && ev.clientX <= stageRect.right
    && ev.clientY >= stageRect.top && ev.clientY <= stageRect.bottom;
  const inPanel = !!panelRect
    && ev.clientX >= panelRect.left && ev.clientX <= panelRect.right
    && ev.clientY >= panelRect.top && ev.clientY <= panelRect.bottom;
  presetDrag.value = {
    ...presetDrag.value,
    clientX: ev.clientX,
    clientY: ev.clientY,
    enteredStage: presetDrag.value.enteredStage || inStage,
    leftPanel: presetDrag.value.leftPanel || !inPanel,
  };
  const drag = presetDrag.value;
  if (drag.type !== "cabinetDesign") return;
  const dragDx = ev.clientX - (drag.startX || ev.clientX);
  const dragDy = ev.clientY - (drag.startY || ev.clientY);
  const movedEnough = Math.hypot(dragDx, dragDy) >= PRESET_PREVIEW_MIN_DRAG_PX;
  const canDropCabinet = drag.leftPanel;
  if (!movedEnough || !canDropCabinet || (!inStage && !drag.enteredStage)) return;
}

async function onPresetPointerUp(ev) {
  let drag = { ...presetDrag.value };
  const stageRect = stageEl.value?.getBoundingClientRect();
  const inStage = !!stageRect && ev.clientX >= stageRect.left && ev.clientX <= stageRect.right
    && ev.clientY >= stageRect.top && ev.clientY <= stageRect.bottom;
  const dragDx = ev.clientX - (drag.startX || ev.clientX);
  const dragDy = ev.clientY - (drag.startY || ev.clientY);
  const movedEnough = Math.hypot(dragDx, dragDy) >= PRESET_PREVIEW_MIN_DRAG_PX;

  const canDropCabinet = drag.type !== "cabinetDesign" || drag.leftPanel;
  const shouldCommitCabinet = inStage && movedEnough && drag.enteredStage && canDropCabinet;
  if (inStage && movedEnough && drag.enteredStage && canDropCabinet) {
    if (drag.type === "column") {
      editorRef.value?.placeColumnAtClient?.(ev.clientX, ev.clientY);
    } else if (drag.type === "doorAsset" && drag.preset?.modelUrl) {
      presetDrag.value = {
        ...presetDrag.value,
        releasePending: true,
        releaseClientX: ev.clientX,
        releaseClientY: ev.clientY,
        clientX: ev.clientX,
        clientY: ev.clientY,
      };
      await ensureDoorAssetDragPlacement(ev.clientX, ev.clientY);
      return;
    } else if (drag.type === "doorPreset" && drag.preset) {
      const payload = await buildDoorPresetPayloadAsync(drag.preset);
      editorRef.value?.beginDoorPlacementAtClient?.(payload, ev.clientX, ev.clientY);
    } else if (drag.type === "cabinetDesign" && drag.design?.preview?.viewer_boxes?.length) {
      presetDrag.value = {
        ...presetDrag.value,
        releasePending: true,
        releaseClientX: ev.clientX,
        releaseClientY: ev.clientY,
        clientX: ev.clientX,
        clientY: ev.clientY,
      };
      await ensureCabinetDesignDragPlacement(ev.clientX, ev.clientY);
      return;
    } else if (drag.preset) {
      const lines = buildPresetLines(drag.preset.kind);
      editorRef.value?.placeWallPresetAtClient?.(lines, ev.clientX, ev.clientY);
    }
  }
  finishPresetDragSession();
}

const presetPreview = computed(() => {
  const drag = presetDrag.value;
  if (!drag.active) return null;
  if (drag.type !== "column" && !drag.preset && !drag.design) return null;
  if (drag.type === "cabinetDesign" && !drag.leftPanel) return null;
  if (drag.type === "cabinetDesign" && (drag.dragBootstrapping || drag.createdOrderDesignId || cabinetDesignDropLoading.value)) return null;

  const dx = drag.clientX - (drag.startX || drag.clientX);
  const dy = drag.clientY - (drag.startY || drag.clientY);
  const movedEnough = Math.hypot(dx, dy) >= PRESET_PREVIEW_MIN_DRAG_PX;
  if (!movedEnough) return null;

  const stageRect = stageEl.value?.getBoundingClientRect();
  if (!stageRect) return null;

  const stageX = drag.clientX - stageRect.left;
  const stageY = drag.clientY - stageRect.top;
  const insideStage = stageX >= 0 && stageY >= 0 && stageX <= stageRect.width && stageY <= stageRect.height;
  if (!insideStage && !drag.enteredStage) return null;

  const full = editorRef.value?.getState?.();
  const st = full?.state || {};
  const zoom = Number(st.zoom);
  const offsetX = Number(st.offsetX);
  const offsetY = Number(st.offsetY);
  if (!Number.isFinite(zoom) || !Number.isFinite(offsetX) || !Number.isFinite(offsetY) || zoom <= 0) return null;

  const lines = drag.type === "column"
    ? (() => {
        const widthMm = Math.max(10, Number(st?.columnWidthMm) || 500);
        return [{
          ax: -(widthMm * 0.5),
          ay: 0,
          bx: widthMm * 0.5,
          by: 0,
          thickness: Math.max(10, Number(st?.columnDepthMm) || 400),
          heightMm: Math.max(10, Number(st?.columnHeightMm) || 2800),
          name: "Column",
        }];
      })()
    : drag.type === "doorPreset"
      ? buildDoorPresetPreviewLines(drag.preset)
    : drag.type === "doorAsset"
      ? buildDoorPresetPreviewLines({
          id: drag.preset?.id,
          title: drag.preset?.title,
          frameThicknessMm: 50,
          modelBoundsMm: drag.preset?.modelBoundsMm || getFallbackDoorModelBoundsMm(),
        })
    : drag.type === "cabinetDesign"
      ? getCabinetDesignPreviewLines(drag.design)
    : buildPresetLines(drag.preset.kind);
  if (!Array.isArray(lines) || lines.length === 0) return null;

  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const l of lines) {
    minX = Math.min(minX, Number(l.ax), Number(l.bx));
    maxX = Math.max(maxX, Number(l.ax), Number(l.bx));
    minY = Math.min(minY, Number(l.ay), Number(l.by));
    maxY = Math.max(maxY, Number(l.ay), Number(l.by));
  }
  if (!isFinite(minX) || !isFinite(maxX) || !isFinite(minY) || !isFinite(maxY)) return null;

  const centerWorldX = (stageX - offsetX) / zoom;
  const centerWorldY = -(stageY - offsetY) / zoom;
  const cx = (minX + maxX) * 0.5;
  const cy = (minY + maxY) * 0.5;
  const previewFill = drag.type === "column"
    ? (walls3dSnapshot.value?.state?.columnFillColor || "#A6A6A6")
    : drag.type === "doorPreset"
      ? "#8B6B4A"
    : drag.type === "cabinetDesign"
      ? "#d3c7b7"
      : (walls3dSnapshot.value?.state?.wallFillColor || "#A6A6A6");
  const previewIdBase = drag.type === "column"
    ? "column-preview"
    : drag.type === "doorPreset"
      ? String(drag.preset?.id || "door-preview")
    : drag.type === "cabinetDesign"
      ? String(drag.design?.id || "cabinet-preview")
      : drag.preset.id;

  const screenLines = lines.map((l, idx) => {
    const ax = Number(l.ax) - cx + centerWorldX;
    const ay = Number(l.ay) - cy + centerWorldY;
    const bx = Number(l.bx) - cx + centerWorldX;
    const by = Number(l.by) - cy + centerWorldY;
    const x1 = ax * zoom + offsetX;
    const y1 = -ay * zoom + offsetY;
    const x2 = bx * zoom + offsetX;
    const y2 = -by * zoom + offsetY;
    const thickness = Math.max(1, Number(l.thickness) || Number(st.wallThicknessMm) || 120);
    const sw = Math.max(4, thickness * zoom);
    return {
      id: `${previewIdBase}-${idx}`,
      x1,
      y1,
      x2,
      y2,
      sw,
      label: drag.type === "column" ? `C${idx + 1}` : (l.label || l.name || ""),
      midX: (x1 + x2) * 0.5,
      midY: (y1 + y2) * 0.5,
      angle: Math.atan2(y2 - y1, x2 - x1) * 180 / Math.PI,
    };
  });

  return {
    width: stageRect.width,
    height: stageRect.height,
    lines: screenLines,
    fill: previewFill,
  };
});

function toggleMenu(menuId, e) {
  // While drawing, keep submenus closed (AutoCAD-like).
  if (drawUiLock.value && route.path === "/") return;
  if (menuId === "construction") {
    if (constructionWizardOpen.value) closeConstructionWizard();
    else openConstructionWizard();
    scheduleSubRailPosition();
    return;
  }
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
  closeInteriorLibrary();
  // Selecting a design toolbar item behaves like opening the Design menu.
  activeMenu.value = "design";
  openMenuPanel.value = "design";
  openMode.value = "menu";
  if (id === "cabinet") {
    loadCabinetDesignCatalog();
  }
  if (id === "door") {
    setDesignMenuTool("door");
  } else if (id === "wall" && designMenuTool.value === "door") {
    setDesignMenuTool("wall");
  }
  if (designBtnEl.value) scheduleMenuPanelPosition(designBtnEl.value);
  scheduleSubRailPosition();
}

let _ro = null;
let _raf = 0;
let _shiftPx = 0;
let _quickSyncTimer = 0;
let _quickOutsidePointerDown = null;
let _lastShortcutSaveAt = 0;
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

watch(
  () => route.fullPath,
  async () => {
    if (requiresOrderGate.value) {
      await ensureOrderGate();
    } else {
      closeOrderEntry(true);
    }
  }
);

watch(
  isOrderGateBlocking,
  (blocked) => {
    if (blocked) {
      editorRef.value?.setInputEnabled?.(false);
      closeQuickMenus();
    } else {
      editorRef.value?.setInputEnabled?.(true);
    }
  },
  { immediate: true }
);

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
  loadOrders().then(() => ensureOrderGate());
  _quickSyncTimer = window.setInterval(syncQuickStateFromEditor, 350);

  _quickOutsidePointerDown = (e) => {
    const el = e.target;
    if (!(el instanceof Element)) return;
    if (el.closest(".stageQuickBar")) return;
    if (interiorLibraryOverlapPickerState.value.visible && !el.closest(".subCategoryDesignEditor__overlapPicker")) {
      hideInteriorLibraryOverlapPicker();
    }
    closeQuickMenus();
  };
  window.addEventListener("pointerdown", _quickOutsidePointerDown, true);

  window.addEventListener("resize", scheduleShift);
  window.addEventListener("resize", scheduleSubRailPosition);
  if (typeof ResizeObserver !== "undefined" && stageEl.value) {
    _ro = new ResizeObserver(() => scheduleShift());
    _ro.observe(stageEl.value);
  }

  const triggerShortcutSave = () => {
    const now = Date.now();
    if (now - _lastShortcutSaveAt < 700) return;
    _lastShortcutSaveAt = now;
    if (route.path === "/settings") {
      window.dispatchEvent(new CustomEvent("designkp:save-settings"));
      return;
    }
    doSaveProject();
  };
  const onSaveShortcut = (e) => {
    if ((e.ctrlKey || e.metaKey) && !e.altKey && String(e.key || "").toLowerCase() === "s") {
      e.preventDefault();
      triggerShortcutSave();
    }
  };
  const onSaveShortcutEvent = () => {
    triggerShortcutSave();
  };
  window.addEventListener("keydown", onSaveShortcut, true);
  window.addEventListener("designkp:save-project", onSaveShortcutEvent, true);
  window.__designkpOnSaveShortcut = onSaveShortcut;
  window.__designkpOnSaveShortcutEvent = onSaveShortcutEvent;

  const onEsc = (e) => {
    if (String(e.key || "") !== "Escape") return;
    const t = e.target;
    const tag = (t?.tagName || "").toUpperCase();
    if (t?.isContentEditable || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (interiorLibraryOpen.value && interiorLibraryOverlapPickerState.value.visible) {
      hideInteriorLibraryOverlapPicker();
      e.preventDefault();
      e.stopPropagation();
      return;
    }
    if (interiorLibraryOpen.value && (interiorLibraryAnnotationDraft.value || interiorLibraryAnnotationTool.value)) {
      cancelInteriorLibraryAnnotationDrawing();
      e.preventDefault();
      e.stopPropagation();
      return;
    }
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
    constructionWizardOpen.value = false;
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

  const onInteriorLibraryDelete = (e) => {
    if (String(e.key || "") !== "Delete") return;
    if (!interiorLibraryOpen.value || interiorLibraryPreviewMode.value !== "front2d") return;
    const t = e.target;
    const tag = (t?.tagName || "").toUpperCase();
    if (t?.isContentEditable || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
    if (!interiorLibrarySelectedAnnotation.value) return;
    removeSelectedInteriorLibraryAnnotation();
    e.preventDefault();
    e.stopPropagation();
  };
  window.addEventListener("keydown", onInteriorLibraryDelete, true);
  window.__designkpOnInteriorLibraryDelete = onInteriorLibraryDelete;

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
  if (interiorLibraryFrontViewportObserver) {
    interiorLibraryFrontViewportObserver.disconnect();
    interiorLibraryFrontViewportObserver = null;
  }
  window.removeEventListener("pointermove", onPresetPointerMove);
  if (window.__designkpDialogs) delete window.__designkpDialogs;
  window.removeEventListener("resize", scheduleShift);
  window.removeEventListener("resize", scheduleSubRailPosition);
  if (_quickSyncTimer) {
    clearInterval(_quickSyncTimer);
    _quickSyncTimer = 0;
  }
  if (_orderDrawingSaveTimeout) {
    clearTimeout(_orderDrawingSaveTimeout);
    _orderDrawingSaveTimeout = 0;
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
  if (window.__designkpOnInteriorLibraryDelete) {
    window.removeEventListener("keydown", window.__designkpOnInteriorLibraryDelete, true);
    delete window.__designkpOnInteriorLibraryDelete;
  }
  if (window.__designkpOnSaveShortcut) {
    window.removeEventListener("keydown", window.__designkpOnSaveShortcut, true);
    delete window.__designkpOnSaveShortcut;
  }
  if (window.__designkpOnSaveShortcutEvent) {
    window.removeEventListener("designkp:save-project", window.__designkpOnSaveShortcutEvent, true);
    delete window.__designkpOnSaveShortcutEvent;
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
  stopInteriorLibraryFrontPan();
  fitAllHandlerRef.value = null;
  passiveModelSelectionHandlerRef.value = null;
  passiveModelSelectionStateRef.value = [];
  activeModelDeleteHandlerRef.value = null;
  orderDesignDeleteHandlerRef.value = null;
  orderDesignDuplicateHandlerRef.value = null;
  orderDesignMirrorHandlerRef.value = null;
  externalHistoryCaptureHandlerRef.value = null;
  externalHistoryRestoreHandlerRef.value = null;
  editorRef.value?.setPassiveModels?.([]);
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
        <button class="iconbtn" title="بازگردانی" @click="doUndo">
          <img src="/icons/undo.png" alt="" />
        </button>
        <button ref="homeBtnEl" class="iconbtn" :class="{ 'is-active': isHome }" title="خانه" @click="goHome">
          <img src="/icons/home.png" alt="" />
        </button>
        <button class="iconbtn" title="باز انجام" @click="doRedo">
          <img src="/icons/redo.png" alt="" />
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
            <div class="menuList">
              <button
                v-if="activeOrder"
                type="button"
                class="menuPanel__orderCard"
                :title="`${activeOrder.order_name} - ${activeOrder.order_number}`"
                @click="openOrderEditor()"
              >
                <span class="menuPanel__orderLabel">سفارش فعال</span>
                <span class="menuPanel__orderName">{{ activeOrder.order_name }}</span>
                <span class="menuPanel__orderMeta">{{ activeOrder.order_number }} / {{ activeOrderStatusLabel }}</span>
              </button>
              <button class="menuItem" type="button" @click="doNewDesign">طرح جدید</button>
              <button class="menuItem" type="button" @click="doOpenPicker">باز کردن</button>
              <button class="menuItem" type="button" @click="doSaveProject">ذخیره</button>
              <button class="menuItem" type="button" @click="doExportJsonToClipboard">خروجی</button>
              <button class="menuItem" type="button" @click="doPrint">پرینت</button>
              <button class="menuItem" type="button" @click="goSettings">تنظیمات</button>
              <button class="menuItem" type="button" @click="setMenu('profile')">حساب کاربری</button>
              <button class="menuItem" type="button" @click="doMessages">پیام ها</button>
            </div>
          </template>

          <template v-else-if="openMenuPanel === 'design'">
            <div class="designMenu">
              <template v-if="activeSubRail === 'wall'">
                <div class="designMenu__grid" aria-label="Design Tools Grid">
                  <button
                    v-for="it in wallDesignMenuTools"
                    :key="it.id"
                    type="button"
                    class="designToolBtn"
                    :class="{ 'is-active': designMenuTool === it.id }"
                    :title="it.title"
                    @pointerdown.prevent="it.id === 'column' ? startColumnDrag($event) : null"
                    @click="setDesignMenuTool(it.id)"
                  >
                    <img :src="it.icon" alt="" />
                  </button>
                  <div class="designToolBtn designToolBtn--empty" aria-hidden="true"></div>
                </div>
                <div class="designMenu__sep"></div>
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
              </template>
              <template v-else-if="activeSubRail === 'door'">
                <div class="designMenu__presetsHead">مدل های درب</div>
                <div class="designMenu__cabinetHint">مدل سه بعدی درب را بگیرید و داخل فضای دوبعدی رها کنید تا موقعیتش را همان لحظه در سه بعدی ببینید.</div>
                <div class="designMenu__cabinetList" aria-label="Door Designs">
                  <div
                    v-for="item in doorAssetLibrary"
                    :key="item.id"
                    class="cabinetDesignCard"
                    :title="item.title"
                    @pointerenter="hoveredCabinetDesignId = item.id"
                    @pointerleave="hoveredCabinetDesignId = null"
                    @pointerdown.prevent="startDoorAssetDrag($event, item)"
                  >
                    <div class="cabinetDesignCard__head">
                      <span class="cabinetDesignCard__title">{{ item.title }}</span>
                    </div>
                    <div class="cabinetDesignCard__meta">
                      <span>GLB Sample</span>
                    </div>
                    <div class="cabinetDesignCard__viewer" aria-hidden="true">
                      <GlbViewerWidget
                        src="/models/1_z1.glb"
                        :walls2d="{ nodes: [], walls: [], selection: { selectedWallId: null, selectedWallIds: [] }, state: {} }"
                        :asset-instances="[{ id: item.id, modelUrl: item.modelUrl, modelBoundsMm: item.modelBoundsMm, transform: { x: 0, y: 0, rotRad: 0 } }]"
                        :display-unit="currentEditorDisplayUnit"
                        :show-attrs-panel="false"
                        :embedded="true"
                        :preview-only="true"
                        :preview-active="hoveredCabinetDesignId === item.id"
                      />
                    </div>
                  </div>
                </div>
              </template>
              <template v-else-if="activeSubRail === 'cabinet'">
                <div class="designMenu__presetsHead">طرح های کابینت دیتابیس</div>
                <div class="designMenu__cabinetHint">طرح را بگیرید و داخل فضای دوبعدی رها کنید.</div>
                <div v-if="cabinetDesignCatalogLoading" class="designMenu__cabinetState">در حال خواندن طرح‌ها از دیتابیس...</div>
                <div v-else-if="cabinetDesignCatalog.length === 0" class="designMenu__cabinetState">فعلاً هیچ طرحی در دیتابیس پیدا نشد.</div>
                <div v-else class="designMenu__cabinetList" aria-label="Cabinet Designs">
                  <div
                    v-for="design in cabinetDesignCatalog"
                    :key="design.id"
                    class="cabinetDesignCard"
                    :class="{
                      'is-active': activeCabinetDesignId === design.id,
                      'is-selected': selectedOrderDesignIds.includes(String(design.id)),
                      'is-disabled': !design.preview?.viewer_boxes?.length,
                    }"
                    :title="design.design_title"
                    @pointerenter="hoveredCabinetDesignId = design.id"
                    @pointerleave="hoveredCabinetDesignId = null"
                    @pointerdown.prevent="design.preview?.viewer_boxes?.length ? startCabinetDesignDrag($event, design) : null"
                  >
                    <div class="cabinetDesignCard__head">
                      <span class="cabinetDesignCard__title">{{ design.design_title }}</span>
                    </div>
                    <div
                      v-if="getConstructionSubCategoryTitleByDesign(design) && getConstructionSubCategoryTitleByDesign(design) !== design.design_title"
                      class="cabinetDesignCard__meta"
                    >
                      <span>{{ getConstructionSubCategoryTitleByDesign(design) }}</span>
                    </div>
                    <div
                      v-if="design.preview?.viewer_boxes?.length"
                      class="cabinetDesignCard__viewer"
                      aria-hidden="true"
                    >
                      <GlbViewerWidget
                        src="/models/1_z1.glb"
                        :walls2d="{ nodes: [], walls: [], selection: { selectedWallId: null, selectedWallIds: [] }, state: {} }"
                        :placeholder-outline-color="normalizeHexColor(design.design_outline_color || design.preview?.design_outline_color)"
                        :placeholder-boxes="design.preview.viewer_boxes"
                        :display-unit="currentEditorDisplayUnit"
                        :show-attrs-panel="false"
                        :embedded="true"
                        :preview-only="true"
                        :preview-active="hoveredCabinetDesignId === design.id"
                      />
                    </div>
                    <div v-else class="cabinetDesignCard__empty">preview ندارد</div>
                  </div>
                </div>
              </template>
              <div v-else class="designMenu__cabinetState">این زیرمنو فعلاً خالی است.</div>
            </div>
          </template>

          <template v-else-if="openMenuPanel === 'construction'">
            <div class="constructionMenu">
              <div class="constructionMenu__summary">
                <div class="constructionMenu__summaryText">
                  <div class="constructionMenu__eyebrow">کنترل شیوه ساخت از جدول `part_kinds`</div>
                  <div class="constructionMenu__headline">انواع قطعات فعال برای ادمین جاری</div>
                </div>
                <div class="constructionMenu__stats">
                  <div class="constructionMenu__stat">
                    <span class="constructionMenu__statValue">{{ toPersianDigits(constructionPartKinds.length) }}</span>
                    <span class="constructionMenu__statLabel">کل</span>
                  </div>
                  <div class="constructionMenu__stat">
                    <span class="constructionMenu__statValue">{{ toPersianDigits(systemPartKindsCount) }}</span>
                    <span class="constructionMenu__statLabel">سیستمی</span>
                  </div>
                  <div class="constructionMenu__stat">
                    <span class="constructionMenu__statValue">{{ toPersianDigits(adminPartKindsCount) }}</span>
                    <span class="constructionMenu__statLabel">اختصاصی</span>
                  </div>
                </div>
              </div>

              <div class="constructionMenu__hint">
                این لیست فعلاً از mirror داده‌ی دیتابیس نمایش داده می‌شود و در فاز بعدی به API واقعی ادمین وصل خواهد شد.
              </div>

              <div class="constructionMenu__list" aria-label="Part Kinds">
                <article
                  v-for="item in constructionPartKinds"
                  :key="item.id"
                  class="constructionMenu__card"
                >
                  <div class="constructionMenu__cardHead">
                    <div class="constructionMenu__titleBlock">
                      <div class="constructionMenu__title">{{ item.org_part_kind_title }}</div>
                      <div class="constructionMenu__subtitle">{{ item.part_kind_code }}</div>
                    </div>
                    <span
                      class="constructionMenu__scope"
                      :class="item.admin_id === null ? 'constructionMenu__scope--system' : 'constructionMenu__scope--admin'"
                    >
                      {{ item.admin_id === null ? "سیستمی" : "اختصاصی ادمین" }}
                    </span>
                  </div>

                  <div class="constructionMenu__meta">
                    <div class="constructionMenu__metaRow">
                      <span class="constructionMenu__metaLabel">شناسه نوع</span>
                      <span class="constructionMenu__metaValue">{{ item.part_kind_id }}</span>
                    </div>
                    <div class="constructionMenu__metaRow">
                      <span class="constructionMenu__metaLabel">جایگاه</span>
                      <span class="constructionMenu__metaValue">{{ normalizeBooleanFlag(item.is_internal, false) ? "داخلی" : "سازه اصلی" }}</span>
                    </div>
                    <div class="constructionMenu__metaRow">
                      <span class="constructionMenu__metaLabel">کد اصلی</span>
                      <span class="constructionMenu__metaValue constructionMenu__metaValue--mono">{{ item.code }}</span>
                    </div>
                    <div class="constructionMenu__metaRow">
                      <span class="constructionMenu__metaLabel">مالک ساختار</span>
                      <span class="constructionMenu__metaValue constructionMenu__metaValue--mono">
                        {{ item.admin_id || "SYSTEM" }}
                      </span>
                    </div>
                  </div>
                </article>
              </div>
            </div>
          </template>

          <div v-else class="menuPanel__hint">محتوای این بخش در حال تکمیل است.</div>
        </div>
      </aside>

      <section ref="stageEl" class="stage">
        <div ref="stageCardEl" class="stage__card">
        <div v-if="isOrderGateBlocking" class="stageOrderGuard" @click="openOrderEntry()">
          <div class="stageOrderGuard__card">
            <div class="stageOrderGuard__title">قبل از طراحی، سفارش را انتخاب کنید</div>
            <div class="stageOrderGuard__text">برای شروع کار باید یک سفارش جدید بسازید یا یک سفارش موجود را انتخاب کنید.</div>
            <button type="button" class="menuItem" @click.stop="openOrderEntry()">
              ورود به سفارش
            </button>
          </div>
        </div>
        <div v-if="cabinetDesignDropLoading" class="stageDropLoading" aria-live="polite">
          <div class="stageDropLoading__card">
            <span class="stageDropLoading__spinner" aria-hidden="true"></span>
            <div class="stageDropLoading__title">
              {{
                cabinetDesignDropLoadingMode === "edit"
                  ? "در حال ویرایش طرح..."
                  : cabinetDesignDropLoadingMode === "duplicate"
                    ? "در حال کپی طرح..."
                    : cabinetDesignDropLoadingMode === "door"
                      ? "در حال افزودن درب به صحنه..."
                    : "در حال افزودن طرح به صحنه..."
              }}
            </div>
            <div v-if="cabinetDesignDropLoadingTitle" class="stageDropLoading__caption">{{ cabinetDesignDropLoadingTitle }}</div>
          </div>
        </div>
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
              title="کپی JSON دیباگ"
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

          <div v-if="presetPreview" class="presetStagePreview" aria-hidden="true">
            <svg
              class="presetStagePreview__svg"
              :viewBox="`0 0 ${presetPreview.width} ${presetPreview.height}`"
              :width="presetPreview.width"
              :height="presetPreview.height"
            >
              <g class="presetStagePreview__glow" stroke-linecap="square" stroke-linejoin="miter">
                <line
                  v-for="line in presetPreview.lines"
                  :key="`preview-glow-${line.id}`"
                  :x1="line.x1"
                  :y1="line.y1"
                  :x2="line.x2"
                  :y2="line.y2"
                  :stroke-width="line.sw + 18"
                />
              </g>
              <g class="presetStagePreview__edge" stroke-linecap="square" stroke-linejoin="miter">
                <line
                  v-for="line in presetPreview.lines"
                  :key="`preview-edge-${line.id}`"
                  :x1="line.x1"
                  :y1="line.y1"
                  :x2="line.x2"
                  :y2="line.y2"
                  :stroke-width="line.sw + 2"
                />
              </g>
              <g :stroke="presetPreview.fill" stroke-linecap="square" stroke-linejoin="miter">
                <line
                  v-for="line in presetPreview.lines"
                  :key="`preview-fill-${line.id}`"
                  :x1="line.x1"
                  :y1="line.y1"
                  :x2="line.x2"
                  :y2="line.y2"
                  :stroke-width="line.sw"
                />
              </g>
              <g class="presetStagePreview__labels">
                <text
                  v-for="line in presetPreview.lines"
                  :key="`preview-label-${line.id}`"
                  :x="line.midX"
                  :y="line.midY"
                  :transform="`rotate(${line.angle} ${line.midX} ${line.midY})`"
                >
                  {{ line.label }}
                </text>
              </g>
            </svg>
          </div>

          <GlbViewerWidget
            ref="stageGlbViewerRef"
            v-if="showStageOverlays"
            src="/models/1_z1.glb"
            :model2d-transform="model2dTransformRef"
            :walls2d="walls3dSnapshot"
            :asset-instances="stageDoorAssetInstances"
            :display-unit="currentEditorDisplayUnit"
            :order-design="selectedOrderDesignSource"
            :selected-order-design-ids="selectedOrderDesignIds"
            :order-param-groups="constructionParamGroups"
            :placeholder-instances="stageOrderDesignInstances"
            :placeholder-outline-color="normalizeHexColor(selectedOrderDesignSource?.design_outline_color)"
            :placeholder-boxes="stageCabinetPlaceholderBoxes"
            :wall-style-draft="wallStyleDraft"
            :selected-wall-style="selectedWallStyle"
            @update:wallStyleDraft="updateWallStyleDraft"
            @update:selectedWallCoords="updateSelectedWallCoords"
            @update:orderDesignAttr="updateActiveOrderDesignAttr"
            @openInteriorLibraryForDesign="openInteriorLibraryForDesign"
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

  <div v-if="constructionWizardOpen" class="constructionDialog" role="dialog" aria-modal="true">
    <div class="constructionDialog__backdrop" @click="closeConstructionWizard"></div>
    <div class="constructionDialog__card" dir="rtl">
      <div class="constructionDialog__head">
        <div class="constructionDialog__headActions">
          <button
            type="button"
            class="constructionDialog__headIconBtn"
            :class="{ 'is-disabled': !constructionHasPendingChanges || constructionSavingIds.length > 0 }"
            :disabled="!constructionHasPendingChanges || constructionSavingIds.length > 0"
            title="ذخیره تغییرات"
            @click="constructionStep === 'templates' ? saveConstructionTemplates() : constructionStep === 'categories' ? saveConstructionCategories() : constructionStep === 'sub_categories' ? saveConstructionSubCategories() : constructionStep === 'part_kinds' ? saveConstructionPartKinds() : constructionStep === 'param_groups' ? saveConstructionParamGroups() : constructionStep === 'params' ? saveConstructionParams() : constructionStep === 'base_formulas' ? saveConstructionBaseFormulas() : constructionStep === 'part_formulas' ? saveConstructionPartFormulas() : null"
          >
            <img src="/icons/construction-save.svg" alt="ذخیره" />
          </button>
          <button
            type="button"
            class="constructionDialog__headIconBtn"
            title="دانلود اکسل"
            :disabled="!['templates', 'categories', 'sub_categories', 'part_kinds', 'param_groups', 'params', 'base_formulas', 'part_formulas'].includes(constructionStep)"
            @click="downloadConstructionExcelTemplate"
          >
            <img src="/icons/construction-download.svg" alt="دانلود" />
          </button>
          <button
            type="button"
            class="constructionDialog__headIconBtn"
            title="آپلود اکسل"
            :disabled="!['templates', 'categories', 'sub_categories', 'part_kinds', 'param_groups', 'params', 'base_formulas', 'part_formulas'].includes(constructionStep)"
            @click="triggerConstructionImport"
          >
            <img src="/icons/construction-upload.svg" alt="آپلود" />
          </button>
        </div>
        <div class="constructionDialog__titleWrap">
          <div class="constructionDialog__eyebrow">کنترل مرحله‌ای جداول شیوه ساخت</div>
          <div class="constructionDialog__title menuPanel__title">مدیریت ساختار نرم افزار ادمین</div>
        </div>
        <button type="button" class="constructionDialog__close" title="بستن" @click="closeConstructionWizard">×</button>
      </div>

      <div class="constructionDialog__body">
        <aside class="constructionDialog__steps" aria-label="Construction Steps">
          <button
            v-for="step in constructionTables"
            :key="step.id"
            type="button"
            class="constructionDialog__step"
            :class="{
              'is-active': constructionStep === step.id,
              'is-planned': step.status !== 'active',
            }"
            @click="constructionStep = step.id"
          >
            <span class="constructionDialog__stepTitle">{{ step.title }}</span>
            <span class="constructionDialog__stepStatus">{{ step.status === "active" ? "فعال" : "بعدی" }}</span>
          </button>
        </aside>

        <section class="constructionDialog__content">
          <template v-if="constructionStep === 'templates'">
            <input
              ref="constructionImportInputEl"
              class="constructionDialog__fileInput"
              type="file"
              accept=".csv"
              @change="onConstructionImportFileChange"
            />
            <div class="constructionDialog__toolbar">
              <div class="constructionDialog__toolbarMain">
                <div class="constructionDialog__sectionTitle">جدول تمپلیت‌ها</div>
                <div class="constructionDialog__sectionHint">
                  هر ادمین می‌تواند خانواده‌های اصلی طراحی مثل کابینت، کمد و موارد مشابه را در این جدول تعریف و مدیریت کند.
                </div>
              </div>
              <div class="constructionDialog__toolbarActions">
                <button type="button" class="constructionDialog__textBtn" @click="addConstructionTemplate">افزودن تمپلیت</button>
              </div>
            </div>

            <div v-if="constructionLoading" class="constructionDialog__loading">در حال خواندن داده‌های جدول از دیتابیس...</div>

            <div v-if="constructionImportPreviewCount && constructionImportPreviewKind === 'templates'" class="constructionDialog__importPreview">
              <div class="constructionDialog__importHead">
                <div>
                  <div class="constructionDialog__sectionTitle">پیش‌نمایش فایل اکسل</div>
                  <div class="constructionDialog__sectionHint">
                    فایل {{ constructionImportFileName }} خوانده شد. قبل از بروزرسانی، جدول واردشده را بررسی و سپس تایید کنید.
                  </div>
                </div>
                <div class="constructionDialog__toolbarActions">
                  <button type="button" class="constructionDialog__textBtn" @click="clearConstructionImportPreview">لغو</button>
                  <button type="button" class="constructionDialog__textBtn is-primary" @click="applyConstructionImportPreview">
                    تایید بروزرسانی
                  </button>
                </div>
              </div>
              <div class="constructionDialog__previewMeta">
                <span>{{ constructionImportPreviewCount }} ردیف</span>
                <span>فایل CSV قابل ویرایش در Excel</span>
              </div>
              <div class="constructionDialog__previewTableWrap">
                <table class="constructionDialog__table constructionDialog__table--preview">
                  <thead>
                    <tr>
                      <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                      <th class="constructionDialog__col constructionDialog__col--title">عنوان</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in constructionImportPreviewRows" :key="`${row.lineNo}-${row.temp_id}`">
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.temp_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">{{ row.temp_title }}</td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ row.admin_mode === "system" ? "پیش‌فرض" : "اختصاصی ادمین" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(constructionTemplates.length) }}</span>
                <span class="constructionDialog__summaryLabel">کل</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(systemTemplatesCount) }}</span>
                <span class="constructionDialog__summaryLabel">پیش‌فرض</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(adminTemplatesCount) }}</span>
                <span class="constructionDialog__summaryLabel">اختصاصی</span>
              </div>
            </div>

            <div class="constructionDialog__tableWrap">
              <table class="constructionDialog__table">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان تمپلیت</th>
                    <th class="constructionDialog__col constructionDialog__col--owner">مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">نوع رکورد</th>
                    <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in constructionTemplates" :key="item.id">
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input v-model.number="item.temp_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionTemplateDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--title">
                      <input v-model="item.temp_title" class="constructionDialog__input" type="text" @input="markConstructionTemplateDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--owner">
                      <span class="constructionDialog__pill constructionDialog__pill--mono">{{ item.admin_id || "SYSTEM" }}</span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button type="button" class="constructionDialog__scopeBtn" :class="item.admin_id === null ? 'is-system' : 'is-admin'" @click="toggleConstructionTemplateScope(item)">
                        {{ item.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--actions">
                      <div class="constructionDialog__actionsCell">
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteConstructionTemplate(item.id)">×</button>
                        <span v-if="constructionDeletingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال حذف</span>
                        <span v-else-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال ذخیره</span>
                        <span v-else-if="item.__isNew" class="constructionDialog__saving constructionDialog__saving--compact">جدید</span>
                        <span v-else-if="item.__dirty" class="constructionDialog__saving constructionDialog__saving--compact">ذخیره نشده</span>
                        <span
                          class="constructionDialog__duplicateState constructionDialog__duplicateState--compact"
                          :class="`is-${getConstructionTemplateDuplicateMessage(item).tone}`"
                        >
                          {{ getConstructionTemplateDuplicateMessage(item).text }}
                        </span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="constructionDialog__sheetHint">
              این جدول خانواده‌های اصلی طراحی را نگه می‌دارد. ابتدا فایل CSV را دانلود کنید، در Excel ویرایش کنید، سپس همان فایل را دوباره آپلود و تایید کنید.
            </div>
          </template>

          <template v-else-if="constructionStep === 'categories'">
            <input
              ref="constructionImportInputEl"
              class="constructionDialog__fileInput"
              type="file"
              accept=".csv"
              @change="onConstructionImportFileChange"
            />
            <div class="constructionDialog__toolbar">
              <div class="constructionDialog__toolbarMain">
                <div class="constructionDialog__sectionTitle">جدول دسته‌بندی‌ها</div>
                <div class="constructionDialog__sectionHint">
                  هر دسته به یک تمپلیت وصل می‌شود و لایه بعدیِ ساختار طراحی را برای ادمین مشخص می‌کند.
                </div>
              </div>
              <div class="constructionDialog__toolbarActions">
                <button type="button" class="constructionDialog__textBtn" @click="addConstructionCategory">افزودن دسته</button>
              </div>
            </div>

            <div v-if="constructionLoading" class="constructionDialog__loading">در حال خواندن داده‌های جدول از دیتابیس...</div>

            <div v-if="constructionImportPreviewCount && constructionImportPreviewKind === 'categories'" class="constructionDialog__importPreview">
              <div class="constructionDialog__importHead">
                <div>
                  <div class="constructionDialog__sectionTitle">پیش‌نمایش فایل اکسل</div>
                  <div class="constructionDialog__sectionHint">
                    فایل {{ constructionImportFileName }} خوانده شد. قبل از بروزرسانی، جدول واردشده را بررسی و سپس تایید کنید.
                  </div>
                </div>
                <div class="constructionDialog__toolbarActions">
                  <button type="button" class="constructionDialog__textBtn" @click="clearConstructionImportPreview">لغو</button>
                  <button type="button" class="constructionDialog__textBtn is-primary" @click="applyConstructionImportPreview">
                    تایید بروزرسانی
                  </button>
                </div>
              </div>
              <div class="constructionDialog__previewMeta">
                <span>{{ constructionImportPreviewCount }} ردیف</span>
                <span>فایل CSV قابل ویرایش در Excel</span>
              </div>
              <div class="constructionDialog__previewTableWrap">
                <table class="constructionDialog__table constructionDialog__table--preview">
                  <thead>
                    <tr>
                      <th class="constructionDialog__col constructionDialog__col--id">تمپلیت</th>
                      <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                      <th class="constructionDialog__col constructionDialog__col--title">عنوان</th>
                      <th class="constructionDialog__col constructionDialog__col--outlineColor">رنگ بدنه سه‌بعدی</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in constructionImportPreviewRows" :key="`${row.lineNo}-${row.cat_id}`">
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.temp_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.cat_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">{{ row.cat_title }}</td>
                      <td class="constructionDialog__col constructionDialog__col--outlineColor">
                        <div class="constructionDialog__colorField">
                          <span class="constructionDialog__colorSwatch" :style="{ backgroundColor: normalizeHexColor(row.design_outline_color) }"></span>
                          <span class="constructionDialog__colorValue">{{ normalizeHexColor(row.design_outline_color) }}</span>
                        </div>
                      </td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ row.admin_mode === "system" ? "پیش‌فرض" : "اختصاصی ادمین" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(constructionCategories.length) }}</span>
                <span class="constructionDialog__summaryLabel">کل</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(systemCategoriesCount) }}</span>
                <span class="constructionDialog__summaryLabel">پیش‌فرض</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(adminCategoriesCount) }}</span>
                <span class="constructionDialog__summaryLabel">اختصاصی</span>
              </div>
            </div>

            <div class="constructionDialog__tableWrap">
              <table class="constructionDialog__table">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--id">تمپلیت</th>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان دسته</th>
                    <th class="constructionDialog__col constructionDialog__col--outlineColor">رنگ بدنه سه‌بعدی</th>
                    <th class="constructionDialog__col constructionDialog__col--owner">مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">نوع رکورد</th>
                    <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in constructionCategories" :key="item.id">
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <select v-model.number="item.temp_id" class="constructionDialog__input" @change="markConstructionCategoryDirty(item)">
                        <option v-for="template in constructionTemplateOptions" :key="template.value" :value="template.value">{{ template.label }}</option>
                      </select>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input v-model.number="item.cat_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionCategoryDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--title">
                      <input v-model="item.cat_title" class="constructionDialog__input" type="text" @input="markConstructionCategoryDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--outlineColor">
                      <div class="constructionDialog__colorEditor">
                        <input
                          v-model="item.design_outline_color"
                          class="constructionDialog__colorInput"
                          type="color"
                          @input="item.design_outline_color = normalizeHexColor(item.design_outline_color); markConstructionCategoryDirty(item)"
                        />
                        <input
                          v-model="item.design_outline_color"
                          class="constructionDialog__input constructionDialog__input--mono constructionDialog__colorHex"
                          type="text"
                          dir="ltr"
                          maxlength="7"
                          placeholder="#7A4A2B"
                          @change="item.design_outline_color = normalizeHexColor(item.design_outline_color); markConstructionCategoryDirty(item)"
                        />
                      </div>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--owner">
                      <span class="constructionDialog__pill constructionDialog__pill--mono">{{ item.admin_id || "SYSTEM" }}</span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button type="button" class="constructionDialog__scopeBtn" :class="item.admin_id === null ? 'is-system' : 'is-admin'" @click="toggleConstructionCategoryScope(item)">
                        {{ item.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--actions">
                      <div class="constructionDialog__actionsCell">
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteConstructionCategory(item.id)">×</button>
                        <span v-if="constructionDeletingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال حذف</span>
                        <span v-else-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال ذخیره</span>
                        <span v-else-if="item.__isNew" class="constructionDialog__saving constructionDialog__saving--compact">جدید</span>
                        <span v-else-if="item.__dirty" class="constructionDialog__saving constructionDialog__saving--compact">ذخیره نشده</span>
                        <span
                          class="constructionDialog__duplicateState constructionDialog__duplicateState--compact"
                          :class="`is-${getConstructionCategoryDuplicateMessage(item).tone}`"
                        >
                          {{ getConstructionCategoryDuplicateMessage(item).text }}
                        </span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="constructionDialog__sheetHint">
              این جدول زیرمجموعه مستقیم تمپلیت‌ها است. قبل از تعریف دسته، مطمئن شوید تمپلیت مقصد در مرحله قبل وجود دارد.
            </div>
          </template>

          <template v-else-if="constructionStep === 'part_kinds'">
            <input
              ref="constructionImportInputEl"
              class="constructionDialog__fileInput"
              type="file"
              accept=".csv"
              @change="onConstructionImportFileChange"
            />
            <div class="constructionDialog__toolbar">
              <div class="constructionDialog__toolbarMain">
                <div class="constructionDialog__sectionTitle">جدول انواع قطعات</div>
                <div class="constructionDialog__sectionHint">
                  پیش‌فرض‌ها از سمت ما تعریف می‌شوند و ادمین می‌تواند آن‌ها را برای ساختار نرم‌افزار خودش ویرایش، اضافه یا حذف کند.
                </div>
              </div>
              <div class="constructionDialog__toolbarActions">
                <button type="button" class="constructionDialog__textBtn" @click="addConstructionPartKind">افزودن نوع قطعه</button>
              </div>
            </div>

            <div v-if="constructionLoading" class="constructionDialog__loading">در حال خواندن داده‌های جدول از دیتابیس...</div>

            <div v-if="constructionImportPreviewCount && constructionImportPreviewKind === 'part_kinds'" class="constructionDialog__importPreview">
              <div class="constructionDialog__importHead">
                <div>
                  <div class="constructionDialog__sectionTitle">پیش‌نمایش فایل اکسل</div>
                  <div class="constructionDialog__sectionHint">
                    فایل {{ constructionImportFileName }} خوانده شد. قبل از بروزرسانی، جدول واردشده را بررسی و سپس تایید کنید.
                  </div>
                </div>
                <div class="constructionDialog__toolbarActions">
                  <button type="button" class="constructionDialog__textBtn" @click="clearConstructionImportPreview">لغو</button>
                  <button type="button" class="constructionDialog__textBtn is-primary" @click="applyConstructionImportPreview">
                    تایید بروزرسانی
                  </button>
                </div>
              </div>
              <div class="constructionDialog__previewMeta">
                <span>{{ constructionImportPreviewCount }} ردیف</span>
                <span>فایل CSV قابل ویرایش در Excel</span>
              </div>
              <div class="constructionDialog__previewTableWrap">
                <table class="constructionDialog__table constructionDialog__table--preview">
                  <thead>
                    <tr>
                      <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                      <th class="constructionDialog__col constructionDialog__col--code">کد</th>
                      <th class="constructionDialog__col constructionDialog__col--title">عنوان</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">داخلی</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in constructionImportPreviewRows" :key="`${row.lineNo}-${row.part_kind_id}`">
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.part_kind_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--code">{{ row.part_kind_code }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">{{ row.org_part_kind_title }}</td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ row.is_internal ? "داخلی" : "سازه" }}</td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ row.admin_mode === "system" ? "پیش‌فرض" : "اختصاصی ادمین" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(constructionPartKinds.length) }}</span>
                <span class="constructionDialog__summaryLabel">کل</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(systemPartKindsCount) }}</span>
                <span class="constructionDialog__summaryLabel">پیش‌فرض</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(adminPartKindsCount) }}</span>
                <span class="constructionDialog__summaryLabel">اختصاصی</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(internalPartKindsCount) }}</span>
                <span class="constructionDialog__summaryLabel">داخلی</span>
              </div>
            </div>

            <div class="constructionDialog__tableWrap">
              <table class="constructionDialog__table">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                    <th class="constructionDialog__col constructionDialog__col--code">کد</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">داخلی</th>
                    <th class="constructionDialog__col constructionDialog__col--owner">مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">نوع رکورد</th>
                    <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in constructionPartKinds" :key="item.id">
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input
                        v-model.number="item.part_kind_id"
                        class="constructionDialog__input"
                        type="number"
                        min="1"
                        step="1"
                        @input="markConstructionPartKindDirty(item)"
                      />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--code">
                      <input
                        v-model="item.part_kind_code"
                        :class="[
                          'constructionDialog__input',
                          'constructionDialog__input--mono',
                          `is-${getDuplicateInputTone(item, 'part_kind_code', constructionPartKindDuplicateState)}`
                        ]"
                        type="text"
                        @input="markConstructionPartKindDirty(item)"
                      />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--title">
                      <input
                        v-model="item.org_part_kind_title"
                        class="constructionDialog__input"
                        type="text"
                        @input="markConstructionPartKindDirty(item)"
                      />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button
                        type="button"
                        class="constructionDialog__scopeBtn"
                        :class="normalizeBooleanFlag(item.is_internal, false) ? 'is-admin' : 'is-system'"
                        @click="item.is_internal = !normalizeBooleanFlag(item.is_internal, false); markConstructionPartKindDirty(item)"
                      >
                        {{ normalizeBooleanFlag(item.is_internal, false) ? "داخلی" : "سازه" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--owner">
                      <span class="constructionDialog__pill constructionDialog__pill--mono">
                        {{ item.admin_id || "SYSTEM" }}
                      </span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button
                        type="button"
                        class="constructionDialog__scopeBtn"
                        :class="item.admin_id === null ? 'is-system' : 'is-admin'"
                        @click="toggleConstructionPartKindScope(item)"
                      >
                        {{ item.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--actions">
                      <div class="constructionDialog__actionsCell">
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="removeConstructionPartKind(item.id)">×</button>
                        <span v-if="constructionDeletingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال حذف</span>
                        <span v-else-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال ذخیره</span>
                        <span v-else-if="item.__isNew" class="constructionDialog__saving constructionDialog__saving--compact">جدید</span>
                        <span v-else-if="item.__dirty" class="constructionDialog__saving constructionDialog__saving--compact">ذخیره نشده</span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="constructionDialog__sheetHint">
              خروجی و ورودی اکسل این جدول به‌صورت CSV سازگار با Excel است. ابتدا فایل را دانلود کنید، در Excel ویرایش کنید، سپس دوباره همان فایل را آپلود و پیش‌نمایش را تایید کنید.
            </div>
          </template>

          <template v-else-if="constructionStep === 'param_groups'">
            <input
              ref="paramGroupIconInputEl"
              class="constructionDialog__fileInput"
              type="file"
              accept=".png,.jpg,.jpeg,.webp"
              @change="onParamGroupIconFileChange"
            />
            <div class="constructionDialog__toolbar">
              <div class="constructionDialog__toolbarMain">
                <div class="constructionDialog__sectionTitle">جدول گروه پارامترها</div>
                <div class="constructionDialog__sectionHint">
                  هر ادمین می‌تواند گروه‌های پارامتر خودش را تعریف و ترتیب نمایش آن‌ها را برای تمام کاربران زیرمجموعه‌اش کنترل کند.
                </div>
              </div>
              <div class="constructionDialog__toolbarActions">
                <button type="button" class="constructionDialog__textBtn" @click="addConstructionParamGroup">افزودن گروه پارامتر</button>
              </div>
            </div>

            <div v-if="constructionImportPreviewCount && constructionImportPreviewKind === 'param_groups'" class="constructionDialog__importPreview">
              <div class="constructionDialog__importHead">
                <div>
                  <div class="constructionDialog__sectionTitle">پیش‌نمایش فایل اکسل</div>
                  <div class="constructionDialog__sectionHint">
                    فایل {{ constructionImportFileName }} خوانده شد. قبل از بروزرسانی، جدول واردشده را بررسی و سپس تایید کنید.
                  </div>
                </div>
                <div class="constructionDialog__toolbarActions">
                  <button type="button" class="constructionDialog__textBtn" @click="clearConstructionImportPreview">لغو</button>
                  <button type="button" class="constructionDialog__textBtn is-primary" @click="applyConstructionImportPreview">
                    تایید بروزرسانی
                  </button>
                </div>
              </div>
              <div class="constructionDialog__previewMeta">
                <span>{{ toPersianDigits(constructionImportPreviewCount) }} ردیف</span>
                <span>فایل CSV قابل ویرایش در Excel</span>
              </div>
              <div class="constructionDialog__previewTableWrap">
                <table class="constructionDialog__table constructionDialog__table--preview">
                  <thead>
                    <tr>
                      <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                      <th class="constructionDialog__col constructionDialog__col--code">کد</th>
                      <th class="constructionDialog__col constructionDialog__col--title">عنوان</th>
                      <th class="constructionDialog__col constructionDialog__col--icon">آیکون</th>
                      <th class="constructionDialog__col constructionDialog__col--uiOrder">ترتیب UI</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">نمایش در سفارش</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in constructionImportPreviewRows" :key="`${row.lineNo}-${row.param_group_id}`">
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.param_group_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--code">{{ row.param_group_code }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">{{ row.org_param_group_title }}</td>
                      <td class="constructionDialog__col constructionDialog__col--icon">{{ row.param_group_icon_path || "-" }}</td>
                      <td class="constructionDialog__col constructionDialog__col--uiOrder">{{ row.ui_order }}</td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ row.show_in_order_attrs ? "نمایش" : "مخفی" }}</td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ row.admin_mode === "system" ? "پیش‌فرض" : "اختصاصی ادمین" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(constructionParamGroups.length) }}</span>
                <span class="constructionDialog__summaryLabel">کل</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(systemParamGroupsCount) }}</span>
                <span class="constructionDialog__summaryLabel">پیش‌فرض</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(adminParamGroupsCount) }}</span>
                <span class="constructionDialog__summaryLabel">اختصاصی</span>
              </div>
            </div>

            <div class="constructionDialog__tableWrap">
              <table class="constructionDialog__table">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                    <th class="constructionDialog__col constructionDialog__col--code">کد</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان</th>
                    <th class="constructionDialog__col constructionDialog__col--uiOrder">ترتیب UI</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">نمایش در سفارش</th>
                    <th class="constructionDialog__col constructionDialog__col--icon">آیکون</th>
                    <th class="constructionDialog__col constructionDialog__col--owner">مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">نوع رکورد</th>
                    <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in constructionParamGroups" :key="item.id">
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input v-model.number="item.param_group_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionParamGroupDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--code">
                      <input
                        v-model="item.param_group_code"
                        :class="[
                          'constructionDialog__input',
                          'constructionDialog__input--mono',
                          `is-${getDuplicateInputTone(item, 'param_group_code', constructionParamGroupDuplicateState)}`
                        ]"
                        type="text"
                        @input="markConstructionParamGroupDirty(item)"
                      />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--title">
                      <input v-model="item.org_param_group_title" class="constructionDialog__input" type="text" @input="markConstructionParamGroupDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--uiOrder">
                      <input v-model.number="item.ui_order" class="constructionDialog__input" type="number" min="0" step="1" @input="markConstructionParamGroupDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button
                        type="button"
                        class="constructionDialog__scopeBtn"
                        :class="normalizeBooleanFlag(item.show_in_order_attrs, true) ? 'is-admin' : 'is-system'"
                        @click="item.show_in_order_attrs = !normalizeBooleanFlag(item.show_in_order_attrs, true); markConstructionParamGroupDirty(item)"
                      >
                        {{ normalizeBooleanFlag(item.show_in_order_attrs, true) ? "نمایش" : "مخفی" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--icon">
                      <div class="constructionDialog__iconCell">
                        <button
                          type="button"
                          class="constructionDialog__miniBtn constructionDialog__iconUploadBtn"
                          :class="[hasParamGroupIcon(item) ? 'is-filled' : 'is-empty', isUploadingParamGroupIcon(item) ? 'is-loading' : '']"
                          :title="isUploadingParamGroupIcon(item) ? 'در حال آپلود آیکون...' : getParamGroupIconTooltip(item)"
                          :disabled="isUploadingParamGroupIcon(item)"
                          @click="triggerParamGroupIconUpload(item)"
                        >
                          <span v-if="isUploadingParamGroupIcon(item)" class="constructionDialog__spinner"></span>
                          <span v-else>↑</span>
                        </button>
                      </div>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--owner">
                      <span class="constructionDialog__pill constructionDialog__pill--mono">{{ item.admin_id || "SYSTEM" }}</span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button type="button" class="constructionDialog__scopeBtn" :class="item.admin_id === null ? 'is-system' : 'is-admin'" @click="toggleConstructionParamGroupScope(item)">
                        {{ item.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--actions">
                      <div class="constructionDialog__actionsCell">
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteConstructionParamGroup(item.id)">×</button>
                        <span v-if="constructionDeletingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال حذف</span>
                        <span v-else-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال ذخیره</span>
                        <span v-else-if="item.__isNew" class="constructionDialog__saving constructionDialog__saving--compact">جدید</span>
                        <span v-else-if="item.__dirty" class="constructionDialog__saving constructionDialog__saving--compact">ذخیره نشده</span>
                        <span
                          class="constructionDialog__duplicateState constructionDialog__duplicateState--compact"
                          :class="`is-${getConstructionParamGroupDuplicateMessage(item).tone}`"
                        >
                          {{ getConstructionParamGroupDuplicateMessage(item).text }}
                        </span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="constructionDialog__sheetHint">
              خروجی و ورودی اکسل این جدول به‌صورت CSV سازگار با Excel است. ابتدا فایل را دانلود کنید، در Excel ویرایش کنید، سپس دوباره همان فایل را آپلود و پیش‌نمایش را تایید کنید.
            </div>
          </template>

          <template v-else-if="constructionStep === 'params'">
            <input
              ref="constructionImportInputEl"
              class="constructionDialog__fileInput"
              type="file"
              accept=".csv"
              @change="onConstructionImportFileChange"
            />
            <div class="constructionDialog__toolbar">
              <div class="constructionDialog__toolbarMain">
                <div class="constructionDialog__sectionTitle">جدول پارامترها</div>
                <div class="constructionDialog__sectionHint">
                  هر ادمین می‌تواند پارامترهای هر نوع قطعه را تعریف، ویرایش و مرتب‌سازی کند و آن‌ها را به گروه پارامترهای واقعی سیستم وصل نگه دارد.
                </div>
              </div>
              <div class="constructionDialog__toolbarActions">
                <button type="button" class="constructionDialog__textBtn" @click="addConstructionParam">افزودن پارامتر</button>
              </div>
            </div>

            <div v-if="constructionImportPreviewCount && constructionImportPreviewKind === 'params'" class="constructionDialog__importPreview">
              <div class="constructionDialog__importHead">
                <div>
                  <div class="constructionDialog__sectionTitle">پیش‌نمایش فایل اکسل</div>
                  <div class="constructionDialog__sectionHint">
                    فایل {{ constructionImportFileName }} خوانده شد. قبل از بروزرسانی، جدول واردشده را بررسی و سپس تایید کنید.
                  </div>
                </div>
                <div class="constructionDialog__toolbarActions">
                  <button type="button" class="constructionDialog__textBtn" @click="clearConstructionImportPreview">لغو</button>
                  <button type="button" class="constructionDialog__textBtn is-primary" @click="applyConstructionImportPreview">
                    تایید بروزرسانی
                  </button>
                </div>
              </div>
              <div class="constructionDialog__previewMeta">
                <span>{{ toPersianDigits(constructionImportPreviewCount) }} ردیف</span>
                <span>فایل CSV قابل ویرایش در Excel</span>
              </div>
              <div class="constructionDialog__previewTableWrap">
                <table class="constructionDialog__table constructionDialog__table--preview">
                  <thead>
                    <tr>
                      <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                      <th class="constructionDialog__col constructionDialog__col--id">نوع قطعه</th>
                      <th class="constructionDialog__col constructionDialog__col--code">کد</th>
                      <th class="constructionDialog__col constructionDialog__col--title">عنوان EN</th>
                      <th class="constructionDialog__col constructionDialog__col--title">عنوان FA</th>
                      <th class="constructionDialog__col constructionDialog__col--id">گروه</th>
                      <th class="constructionDialog__col constructionDialog__col--uiOrder">ترتیب UI</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in constructionImportPreviewRows" :key="`${row.lineNo}-${row.param_id}`">
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.param_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.part_kind_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--code">{{ row.param_code }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">{{ row.param_title_en }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">{{ row.param_title_fa }}</td>
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.param_group_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--uiOrder">{{ row.ui_order }}</td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ row.admin_mode === "system" ? "پیش‌فرض" : "اختصاصی ادمین" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(constructionParams.length) }}</span>
                <span class="constructionDialog__summaryLabel">کل</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(systemParamsCount) }}</span>
                <span class="constructionDialog__summaryLabel">پیش‌فرض</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(adminParamsCount) }}</span>
                <span class="constructionDialog__summaryLabel">اختصاصی</span>
              </div>
            </div>

            <div class="constructionDialog__tableWrap">
              <table class="constructionDialog__table">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                    <th class="constructionDialog__col constructionDialog__col--id">نوع قطعه</th>
                    <th class="constructionDialog__col constructionDialog__col--code">کد</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان EN</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان FA</th>
                    <th class="constructionDialog__col constructionDialog__col--id">گروه</th>
                    <th class="constructionDialog__col constructionDialog__col--uiOrder">ترتیب UI</th>
                    <th class="constructionDialog__col constructionDialog__col--owner">مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">نوع رکورد</th>
                    <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in constructionParams" :key="item.id" :data-row-id="item.id">
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input v-model.number="item.param_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionParamDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input v-model.number="item.part_kind_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionParamDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--code">
                      <input
                        v-model="item.param_code"
                        :class="[
                          'constructionDialog__input',
                          'constructionDialog__input--mono',
                          `is-${getDuplicateInputTone(item, 'param_code', constructionParamDuplicateState)}`
                        ]"
                        type="text"
                        @input="markConstructionParamDirty(item)"
                      />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--title">
                      <input v-model="item.param_title_en" class="constructionDialog__input constructionDialog__input--mono" type="text" @input="markConstructionParamDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--title">
                      <input v-model="item.param_title_fa" class="constructionDialog__input" type="text" @input="markConstructionParamDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input v-model.number="item.param_group_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionParamDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--uiOrder">
                      <input v-model.number="item.ui_order" class="constructionDialog__input" type="number" min="0" step="1" @input="markConstructionParamDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--owner">
                      <span class="constructionDialog__pill constructionDialog__pill--mono">{{ item.admin_id || "SYSTEM" }}</span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button type="button" class="constructionDialog__scopeBtn" :class="item.admin_id === null ? 'is-system' : 'is-admin'" @click="toggleConstructionParamScope(item)">
                        {{ item.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--actions">
                      <div class="constructionDialog__actionsCell">
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteConstructionParam(item.id)">×</button>
                        <span v-if="constructionDeletingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال حذف</span>
                        <span v-else-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال ذخیره</span>
                        <span v-else-if="item.__isNew" class="constructionDialog__saving constructionDialog__saving--compact">جدید</span>
                        <span v-else-if="item.__dirty" class="constructionDialog__saving constructionDialog__saving--compact">ذخیره نشده</span>
                        <span
                          class="constructionDialog__duplicateState constructionDialog__duplicateState--compact"
                          :class="`is-${getConstructionParamDuplicateMessage(item).tone}`"
                        >
                          {{ getConstructionParamDuplicateMessage(item).text }}
                        </span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="constructionDialog__sheetHint">
              خروجی و ورودی اکسل این جدول به‌صورت CSV سازگار با Excel است. ابتدا فایل را دانلود کنید، در Excel ویرایش کنید، سپس دوباره همان فایل را آپلود و پیش‌نمایش را تایید کنید.
            </div>
          </template>

          <template v-else-if="constructionStep === 'sub_categories'">
            <input
              ref="constructionImportInputEl"
              class="constructionDialog__fileInput"
              type="file"
              accept=".csv"
              @change="onConstructionImportFileChange"
            />
            <div class="constructionDialog__toolbar">
              <div class="constructionDialog__toolbarMain">
                <div class="constructionDialog__sectionTitle">جدول ساب‌کت‌ها</div>
                <div class="constructionDialog__sectionHint">
                  هر ساب‌کت زیرمجموعه یک دسته است و پیش‌فرض همه پارامترهای همین ساختار را روی خودش نگه می‌دارد.
                </div>
              </div>
              <div class="constructionDialog__toolbarActions">
                <button type="button" class="constructionDialog__textBtn" @click="addConstructionSubCategory">افزودن ساب‌کت</button>
              </div>
            </div>

            <div v-if="constructionLoading" class="constructionDialog__loading">در حال خواندن داده‌های جدول از دیتابیس...</div>

            <div v-if="constructionImportPreviewCount && constructionImportPreviewKind === 'sub_categories'" class="constructionDialog__importPreview">
              <div class="constructionDialog__importHead">
                <div>
                  <div class="constructionDialog__sectionTitle">پیش‌نمایش فایل اکسل</div>
                  <div class="constructionDialog__sectionHint">
                    فایل {{ constructionImportFileName }} خوانده شد. قبل از بروزرسانی، جدول واردشده را بررسی و سپس تایید کنید.
                  </div>
                </div>
                <div class="constructionDialog__toolbarActions">
                  <button type="button" class="constructionDialog__textBtn" @click="clearConstructionImportPreview">لغو</button>
                  <button type="button" class="constructionDialog__textBtn is-primary" @click="applyConstructionImportPreview">
                    تایید بروزرسانی
                  </button>
                </div>
              </div>
              <div class="constructionDialog__previewMeta">
                <span>{{ constructionImportPreviewCount }} ردیف</span>
                <span>فایل CSV قابل ویرایش در Excel</span>
              </div>
              <div class="constructionDialog__previewTableWrap">
                <table class="constructionDialog__table constructionDialog__table--preview">
                  <thead>
                    <tr>
                      <th class="constructionDialog__col constructionDialog__col--id">تمپلیت</th>
                      <th class="constructionDialog__col constructionDialog__col--id">دسته</th>
                      <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                      <th class="constructionDialog__col constructionDialog__col--title">عنوان</th>
                      <th class="constructionDialog__col constructionDialog__col--title">پارامترهای مقداردهی‌شده</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in constructionImportPreviewRows" :key="`${row.lineNo}-${row.sub_cat_id}`">
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.temp_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.cat_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.sub_cat_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">{{ row.sub_cat_title }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">
                        {{ Object.values(row.param_defaults || {}).filter((value) => String(value || "").trim()).length }}
                      </td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ row.admin_mode === "system" ? "پیش‌فرض" : "اختصاصی ادمین" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(constructionSubCategories.length) }}</span>
                <span class="constructionDialog__summaryLabel">کل</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(systemSubCategoriesCount) }}</span>
                <span class="constructionDialog__summaryLabel">پیش‌فرض</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(adminSubCategoriesCount) }}</span>
                <span class="constructionDialog__summaryLabel">اختصاصی</span>
              </div>
            </div>

            <div class="constructionDialog__tableWrap">
              <table class="constructionDialog__table">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--id">تمپلیت</th>
                    <th class="constructionDialog__col constructionDialog__col--id">دسته</th>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان ساب‌کت</th>
                    <th class="constructionDialog__col constructionDialog__col--defaults">پیش‌فرض‌ها</th>
                    <th class="constructionDialog__col constructionDialog__col--owner">مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">نوع رکورد</th>
                    <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in constructionSubCategories" :key="item.id">
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <select
                        v-model.number="item.temp_id"
                        class="constructionDialog__input"
                        @change="item.cat_id = Number(getConstructionCategoryOptions(item.temp_id)[0]?.value) || item.cat_id; markConstructionSubCategoryDirty(item)"
                      >
                        <option v-for="template in constructionTemplateOptions" :key="template.value" :value="template.value">{{ template.label }}</option>
                      </select>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <select v-model.number="item.cat_id" class="constructionDialog__input" @change="markConstructionSubCategoryDirty(item)">
                        <option v-for="category in getConstructionCategoryOptions(item.temp_id)" :key="category.value" :value="category.value">{{ category.label }}</option>
                      </select>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input v-model.number="item.sub_cat_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionSubCategoryDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--title">
                      <input v-model="item.sub_cat_title" class="constructionDialog__input" type="text" @input="markConstructionSubCategoryDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--defaults">
                      <div class="constructionDialog__defaultsActions">
                        <button type="button" class="constructionDialog__defaultsBtn" :title="'تنظیمات پارامترهای ساب‌کت'" @click="openSubCategoryDefaultsEditor(item)">
                          <span class="constructionDialog__defaultsBtnValue">{{ getSubCategoryDefaultsSummary(item).text }}</span>
                          <span class="constructionDialog__defaultsBtnLabel">
                            <span class="constructionDialog__defaultsBtnIcon" aria-hidden="true">💡</span>
                          </span>
                        </button>
                        <button type="button" class="constructionDialog__defaultsPreviewBtn" @click="openSubCategoryUserPreview(item)">
                          پیش‌فرض
                        </button>
                      </div>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--owner">
                      <span class="constructionDialog__pill constructionDialog__pill--mono">{{ item.admin_id || "SYSTEM" }}</span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button type="button" class="constructionDialog__scopeBtn" :class="item.admin_id === null ? 'is-system' : 'is-admin'" @click="toggleConstructionSubCategoryScope(item)">
                        {{ item.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--actions">
                      <div class="constructionDialog__actionsCell">
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteConstructionSubCategory(item.id)">×</button>
                        <span v-if="constructionDeletingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال حذف</span>
                        <span v-else-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال ذخیره</span>
                        <span v-else-if="item.__isNew" class="constructionDialog__saving constructionDialog__saving--compact">جدید</span>
                        <span v-else-if="item.__dirty" class="constructionDialog__saving constructionDialog__saving--compact">ذخیره نشده</span>
                        <span
                          class="constructionDialog__duplicateState constructionDialog__duplicateState--compact"
                          :class="`is-${getConstructionSubCategoryDuplicateMessage(item).tone}`"
                        >
                          {{ getConstructionSubCategoryDuplicateMessage(item).text }}
                        </span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="constructionDialog__sheetHint">
              این جدول برای هر دسته، مدل‌های زیرمجموعه و مقدار پیش‌فرض همه پارامترها را نگه می‌دارد. هر پارامتر جدید بعد از بارگذاری دوباره این مرحله به‌صورت خودکار در ستون‌ها ظاهر می‌شود.
            </div>
          </template>

          <template v-else-if="constructionStep === 'sub_category_designs'">
            <div class="constructionDialog__toolbar">
              <div class="constructionDialog__toolbarMain">
                <div class="constructionDialog__sectionTitle">جدول طرح‌های ساب‌کت</div>
                <div class="constructionDialog__sectionHint">
                  در این جدول برای هر ساب‌کت سمپل طرح می‌سازید، قطعات را از فرمول‌های قطعه به آن نسبت می‌دهید و پیش‌نمایش سه‌بعدی را بر اساس پیش‌فرض‌های همان ساب‌کت می‌بینید.
                </div>
              </div>
              <div class="constructionDialog__toolbarActions">
                <button type="button" class="constructionDialog__textBtn" @click="openSubCategoryDesignEditor()">افزودن طرح</button>
              </div>
            </div>

            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(constructionSubCategoryDesigns.length) }}</span>
                <span class="constructionDialog__summaryLabel">کل طرح‌ها</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(systemSubCategoryDesignsCount) }}</span>
                <span class="constructionDialog__summaryLabel">سیستمی</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(adminSubCategoryDesignsCount) }}</span>
                <span class="constructionDialog__summaryLabel">اختصاصی</span>
              </div>
            </div>

            <div class="constructionDialog__tableWrap">
              <table class="constructionDialog__table constructionDialog__table--subDesigns">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--owner">مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--id">تمپلیت</th>
                    <th class="constructionDialog__col constructionDialog__col--id">دسته</th>
                    <th class="constructionDialog__col constructionDialog__col--title">ساب‌کت</th>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه طرح</th>
                    <th class="constructionDialog__col constructionDialog__col--code">کد طرح</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان طرح</th>
                    <th class="constructionDialog__col constructionDialog__col--preview">پیش‌نمایش</th>
                    <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in constructionSubCategoryDesigns" :key="item.id">
                    <td class="constructionDialog__col constructionDialog__col--owner">
                      <span
                        class="constructionDialog__pill constructionDialog__ownerBadge"
                        :class="getConstructionOwnerBadge(item).tone === 'system' ? 'constructionDialog__ownerBadge--system' : 'constructionDialog__ownerBadge--admin'"
                      >
                        {{ getConstructionOwnerBadge(item).text }}
                      </span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button
                        type="button"
                        class="constructionDialog__scopeBtn"
                        :class="item.admin_id === null ? 'is-system' : 'is-admin'"
                        @click="toggleConstructionSubCategoryDesignScope(item)"
                      >
                        {{ item.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--id">{{ toPersianDigits(item.temp_id) }}</td>
                    <td class="constructionDialog__col constructionDialog__col--id">{{ toPersianDigits(item.cat_id) }}</td>
                    <td class="constructionDialog__col constructionDialog__col--title">{{ getConstructionSubCategoryTitleByDesign(item) || toPersianDigits(item.sub_cat_id) }}</td>
                    <td class="constructionDialog__col constructionDialog__col--id">{{ toPersianDigits(item.design_id) }}</td>
                    <td class="constructionDialog__col constructionDialog__col--code">{{ item.code }}</td>
                    <td class="constructionDialog__col constructionDialog__col--title">{{ item.design_title }}</td>
                    <td class="constructionDialog__col constructionDialog__col--preview">
                      <div
                        v-if="item.preview?.viewer_boxes?.length"
                        class="constructionDialog__previewThumb"
                        @pointerenter="hoveredConstructionDesignId = item.id"
                        @pointerleave="hoveredConstructionDesignId = null"
                      >
                        <GlbViewerWidget
                          src="/models/1_z1.glb"
                          :walls2d="{ nodes: [], walls: [], selection: { selectedWallId: null, selectedWallIds: [] }, state: {} }"
                          :placeholder-outline-color="normalizeHexColor(item.design_outline_color || item.preview?.design_outline_color)"
                          :placeholder-boxes="item.preview.viewer_boxes"
                          :display-unit="currentEditorDisplayUnit"
                          :show-attrs-panel="false"
                          :embedded="true"
                          :preview-only="true"
                          :preview-active="hoveredConstructionDesignId === item.id"
                        />
                      </div>
                      <span v-else class="constructionDialog__previewEmpty">ندارد</span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--actions">
                      <div class="constructionDialog__actionsCell">
                        <button type="button" class="constructionDialog__textBtn" @click="openSubCategoryDesignEditor(item)">ویرایش طرح</button>
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteConstructionSubCategoryDesign(item.id)">×</button>
                        <span v-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال ذخیره</span>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="!constructionSubCategoryDesigns.length">
                    <td class="constructionDialog__col constructionDialog__col--title" colspan="10">هنوز طرحی برای ساب‌کت‌ها ثبت نشده است.</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="constructionDialog__sheetHint">
              ساخت و ویرایش قطعات طرح از پنجره ویرایش انجام می‌شود و ذخیره آن مستقیم در دیتابیس طرح‌های ساب‌کت اعمال می‌گردد.
            </div>
          </template>

          <template v-else-if="constructionStep === 'internal_part_groups'">
            <div class="constructionDialog__toolbar">
              <div class="constructionDialog__toolbarMain">
                <div class="constructionDialog__sectionTitle">جدول گروه قطعات داخلی</div>
                <div class="constructionDialog__sectionHint">
                  در این جدول از بین قطعات داخلی مثل کشو، طبقه و موارد مشابه گروه می‌سازید تا بعداً به‌صورت یک مجموعه قابل استفاده باشند.
                </div>
              </div>
              <div class="constructionDialog__toolbarActions">
                <button type="button" class="constructionDialog__textBtn" @click="openInternalPartGroupEditor()">افزودن گروه داخلی</button>
              </div>
            </div>

            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(constructionInternalPartGroups.length) }}</span>
                <span class="constructionDialog__summaryLabel">کل گروه‌ها</span>
              </div>
            </div>

            <div ref="constructionParamsTableWrapEl" class="constructionDialog__tableWrap">
              <table class="constructionDialog__table">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--owner">مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه گروه</th>
                    <th class="constructionDialog__col constructionDialog__col--code">کد گروه</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان گروه</th>
                    <th class="constructionDialog__col constructionDialog__col--outlineColor">رنگ خطوط</th>
                    <th class="constructionDialog__col constructionDialog__col--defaults">پیش‌فرض‌ها</th>
                    <th class="constructionDialog__col constructionDialog__col--defaults">کنترلر گروه</th>
                    <th class="constructionDialog__col constructionDialog__col--id">تعداد قطعات</th>
                    <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in constructionInternalPartGroups" :key="item.id">
                    <td class="constructionDialog__col constructionDialog__col--owner">
                      <span
                        class="constructionDialog__pill constructionDialog__ownerBadge"
                        :class="getConstructionOwnerBadge(item).tone === 'system' ? 'constructionDialog__ownerBadge--system' : 'constructionDialog__ownerBadge--admin'"
                      >
                        {{ getConstructionOwnerBadge(item).text }}
                      </span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--id">{{ toPersianDigits(item.group_id) }}</td>
                    <td class="constructionDialog__col constructionDialog__col--code">{{ item.code }}</td>
                    <td class="constructionDialog__col constructionDialog__col--title">{{ item.group_title }}</td>
                    <td class="constructionDialog__col constructionDialog__col--outlineColor">
                      <div class="constructionDialog__colorEditor">
                        <input
                          v-model="item.line_color"
                          class="constructionDialog__colorInput"
                          type="color"
                          @input="previewConstructionInternalPartGroupLineColor(item, item.line_color)"
                          @change="saveConstructionInternalPartGroupLineColor(item)"
                        />
                        <input
                          v-model="item.line_color"
                          class="constructionDialog__input constructionDialog__input--mono constructionDialog__colorHex"
                          type="text"
                          dir="ltr"
                          maxlength="7"
                          :placeholder="DEFAULT_INTERIOR_LINE_COLOR"
                          @input="previewConstructionInternalPartGroupLineColor(item, item.line_color)"
                          @change="saveConstructionInternalPartGroupLineColor(item)"
                        />
                      </div>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--defaults">
                      <div class="constructionDialog__defaultsActions">
                        <button type="button" class="constructionDialog__defaultsBtn" :title="'پیش‌فرض پارامترهای گروه داخلی'" @click="openInternalPartGroupDefaultsEditor(item)">
                          <span class="constructionDialog__defaultsBtnValue">{{ getInternalPartGroupDefaultsSummary(item).text }}</span>
                          <span class="constructionDialog__defaultsBtnLabel">مقادیر</span>
                        </button>
                      </div>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--defaults">
                      <div class="constructionDialog__defaultsActions">
                        <button type="button" class="constructionDialog__defaultsBtn" :title="'تنظیم نوع و اتصال کنترلرهای گروه داخلی'" @click="openInternalPartGroupControllerEditor(item)">
                          <span class="constructionDialog__defaultsBtnValue">{{ getInternalPartGroupControllerSummary(item).text }}</span>
                          <span class="constructionDialog__defaultsBtnLabel">
                            {{ getInternalPartGroupControllerSummary(item).detail || "کنترلر" }}
                          </span>
                        </button>
                      </div>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--id">{{ toPersianDigits(item.parts?.length || 0) }}</td>
                    <td class="constructionDialog__col constructionDialog__col--actions">
                      <div class="constructionDialog__actionsCell">
                        <button type="button" class="constructionDialog__textBtn" @click="openInternalPartGroupEditor(item)">ویرایش گروه</button>
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteConstructionInternalPartGroup(item.id)">×</button>
                      </div>
                    </td>
                  </tr>
                  <tr v-if="!constructionInternalPartGroups.length">
                    <td class="constructionDialog__col constructionDialog__col--title" colspan="9">هنوز گروهی برای قطعات داخلی ثبت نشده است.</td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="constructionDialog__sheetHint">
              ساخت و ویرایش گروه از پنجره ویرایش انجام می‌شود و سمت راست آن فقط قطعات داخلی را برای انتخاب نشان می‌دهد.
            </div>
          </template>

          <template v-else-if="constructionStep === 'base_formulas'">
            <input
              ref="constructionImportInputEl"
              class="constructionDialog__fileInput"
              type="file"
              accept=".csv"
              @change="onConstructionImportFileChange"
            />
            <div class="constructionDialog__toolbar">
              <div class="constructionDialog__toolbarMain">
                <div class="constructionDialog__sectionTitle">جدول فرمول‌های پایه</div>
                <div class="constructionDialog__sectionHint">
                  هر ادمین می‌تواند فرمول‌های پایه را بر اساس کد پارامترهای همان ساختار نگه‌داری و در صورت نیاز بازنویسی کند.
                </div>
              </div>
              <div class="constructionDialog__toolbarActions">
                <button type="button" class="constructionDialog__textBtn" @click="addConstructionBaseFormula">افزودن فرمول پایه</button>
              </div>
            </div>

            <div v-if="constructionImportPreviewCount && constructionImportPreviewKind === 'base_formulas'" class="constructionDialog__importPreview">
              <div class="constructionDialog__importHead">
                <div>
                  <div class="constructionDialog__sectionTitle">پیش‌نمایش فایل اکسل</div>
                  <div class="constructionDialog__sectionHint">
                    فایل {{ constructionImportFileName }} خوانده شد. قبل از بروزرسانی، جدول واردشده را بررسی و سپس تایید کنید.
                  </div>
                </div>
                <div class="constructionDialog__toolbarActions">
                  <button type="button" class="constructionDialog__textBtn" @click="clearConstructionImportPreview">لغو</button>
                  <button type="button" class="constructionDialog__textBtn is-primary" @click="applyConstructionImportPreview">
                    تایید بروزرسانی
                  </button>
                </div>
              </div>
              <div class="constructionDialog__previewMeta">
                <span>{{ toPersianDigits(constructionImportPreviewCount) }} ردیف</span>
                <span>فایل CSV قابل ویرایش در Excel</span>
              </div>
              <div class="constructionDialog__previewTableWrap">
                <table class="constructionDialog__table constructionDialog__table--preview">
                  <thead>
                    <tr>
                      <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                      <th class="constructionDialog__col constructionDialog__col--formulaCode" :style="getBaseFormulaCodeCellStyle()">کد فرمول</th>
                      <th class="constructionDialog__col constructionDialog__col--formulaExpr">فرمول</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in constructionImportPreviewRows" :key="`${row.lineNo}-${row.fo_id}`">
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.fo_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--formulaCode" :style="getBaseFormulaCodeCellStyle()">{{ row.param_formula }}</td>
                      <td class="constructionDialog__col constructionDialog__col--formulaExpr">{{ row.formula }}</td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ row.admin_mode === "system" ? "پیش‌فرض" : "اختصاصی ادمین" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(constructionBaseFormulas.length) }}</span>
                <span class="constructionDialog__summaryLabel">کل</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(systemBaseFormulasCount) }}</span>
                <span class="constructionDialog__summaryLabel">پیش‌فرض</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(adminBaseFormulasCount) }}</span>
                <span class="constructionDialog__summaryLabel">اختصاصی</span>
              </div>
            </div>

            <div class="constructionDialog__tableWrap">
              <table class="constructionDialog__table">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                    <th class="constructionDialog__col constructionDialog__col--formulaCode" :style="getBaseFormulaCodeCellStyle()">کد فرمول</th>
                    <th class="constructionDialog__col constructionDialog__col--formulaExpr">فرمول</th>
                    <th class="constructionDialog__col constructionDialog__col--owner">مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">نوع رکورد</th>
                    <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in constructionBaseFormulas" :key="item.id">
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input v-model.number="item.fo_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionBaseFormulaDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--formulaCode" :style="getBaseFormulaCodeCellStyle()">
                      <input
                        v-model="item.param_formula"
                        :class="[
                          'constructionDialog__input',
                          'constructionDialog__input--mono',
                          `is-${getDuplicateInputTone(item, 'param_formula', constructionBaseFormulaDuplicateState)}`
                        ]"
                        :style="getBaseFormulaCodeInputStyle()"
                        type="text"
                        @input="markConstructionBaseFormulaDirty(item)"
                      />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--formulaExpr">
                      <button type="button" class="constructionDialog__formulaBtn" @click="openBaseFormulaBuilder(item, 'edit')">
                        <span class="constructionDialog__formulaBtnText">{{ item.formula }}</span>
                        <span class="constructionDialog__formulaBtnAction">ویرایش فرمول</span>
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--owner">
                      <span class="constructionDialog__pill constructionDialog__pill--mono">{{ item.admin_id || "SYSTEM" }}</span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button type="button" class="constructionDialog__scopeBtn" :class="item.admin_id === null ? 'is-system' : 'is-admin'" @click="toggleConstructionBaseFormulaScope(item)">
                        {{ item.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--actions">
                      <div class="constructionDialog__actionsCell">
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteConstructionBaseFormula(item.id)">×</button>
                        <span v-if="constructionDeletingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال حذف</span>
                        <span v-else-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال ذخیره</span>
                        <span v-else-if="item.__isNew" class="constructionDialog__saving constructionDialog__saving--compact">جدید</span>
                        <span v-else-if="item.__dirty" class="constructionDialog__saving constructionDialog__saving--compact">ذخیره نشده</span>
                        <span
                          class="constructionDialog__duplicateState constructionDialog__duplicateState--compact"
                          :class="`is-${getConstructionBaseFormulaDuplicateMessage(item).tone}`"
                        >
                          {{ getConstructionBaseFormulaDuplicateMessage(item).text }}
                        </span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="constructionDialog__sheetHint">
              فرمول‌ها باید فقط از کد پارامترهای معتبر همان ساختار استفاده کنند. اگر در عبارت فرمول کد ناشناخته‌ای وجود داشته باشد، ذخیره‌سازی از سمت سرور رد می‌شود.
            </div>
          </template>

          <template v-else-if="constructionStep === 'part_formulas'">
            <input
              ref="constructionImportInputEl"
              class="constructionDialog__fileInput"
              type="file"
              accept=".csv"
              @change="onConstructionImportFileChange"
            />
            <div class="constructionDialog__toolbar">
              <div class="constructionDialog__toolbarMain">
                <div class="constructionDialog__sectionTitle">جدول فرمول‌های قطعات</div>
                <div class="constructionDialog__sectionHint">
                  هر قطعه می‌تواند از پارامترها و فرمول‌های پایه استفاده کند. برای هر ردیف، فرمول‌های ابعاد و مختصات جداگانه نگه‌داری می‌شوند.
                </div>
              </div>
              <div class="constructionDialog__toolbarActions">
                <button type="button" class="constructionDialog__textBtn" @click="addConstructionPartFormula">افزودن فرمول قطعه</button>
              </div>
            </div>

            <div v-if="constructionImportPreviewCount && constructionImportPreviewKind === 'part_formulas'" class="constructionDialog__importPreview">
              <div class="constructionDialog__importHead">
                <div>
                  <div class="constructionDialog__sectionTitle">پیش‌نمایش فایل اکسل</div>
                  <div class="constructionDialog__sectionHint">
                    فایل {{ constructionImportFileName }} خوانده شد. قبل از بروزرسانی، جدول واردشده را بررسی و سپس تایید کنید.
                  </div>
                </div>
                <div class="constructionDialog__toolbarActions">
                  <button type="button" class="constructionDialog__textBtn" @click="clearConstructionImportPreview">لغو</button>
                  <button type="button" class="constructionDialog__textBtn is-primary" @click="applyConstructionImportPreview">
                    تایید بروزرسانی
                  </button>
                </div>
              </div>
              <div class="constructionDialog__previewMeta">
                <span>{{ toPersianDigits(constructionImportPreviewCount) }} ردیف</span>
                <span>فایل CSV قابل ویرایش در Excel</span>
              </div>
              <div class="constructionDialog__previewTableWrap">
                <table class="constructionDialog__table constructionDialog__table--preview">
                  <thead>
                    <tr>
                      <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                      <th class="constructionDialog__col constructionDialog__col--id">نوع قطعه</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">داخلی</th>
                      <th class="constructionDialog__col constructionDialog__col--id">زیرنوع</th>
                      <th class="constructionDialog__col constructionDialog__col--code">کد قطعه</th>
                      <th class="constructionDialog__col constructionDialog__col--title">عنوان قطعه</th>
                      <th v-for="field in PART_FORMULA_FIELDS" :key="field.key" class="constructionDialog__col constructionDialog__col--formulaExpr">{{ field.label }}</th>
                      <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in constructionImportPreviewRows" :key="`${row.lineNo}-${row.part_formula_id}`">
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.part_formula_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.part_kind_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ getConstructionPartKindInternalLabel(row.part_kind_id) }}</td>
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.part_sub_kind_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--code">{{ row.part_code }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">{{ row.part_title }}</td>
                      <td v-for="field in PART_FORMULA_FIELDS" :key="field.key" class="constructionDialog__col constructionDialog__col--formulaExpr">{{ row[field.key] }}</td>
                      <td class="constructionDialog__col constructionDialog__col--scope">{{ row.admin_mode === "system" ? "پیش‌فرض" : "اختصاصی ادمین" }}</td>
                    </tr>
                  </tbody>
                </table>
              </div>
            </div>

            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(constructionPartFormulas.length) }}</span>
                <span class="constructionDialog__summaryLabel">کل</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(systemPartFormulasCount) }}</span>
                <span class="constructionDialog__summaryLabel">پیش‌فرض</span>
              </div>
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(adminPartFormulasCount) }}</span>
                <span class="constructionDialog__summaryLabel">اختصاصی</span>
              </div>
            </div>

            <div class="constructionDialog__tableWrap">
              <table class="constructionDialog__table">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                    <th class="constructionDialog__col constructionDialog__col--id">نوع قطعه</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">داخلی</th>
                    <th class="constructionDialog__col constructionDialog__col--id">زیرنوع</th>
                    <th class="constructionDialog__col constructionDialog__col--code">کد قطعه</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان قطعه</th>
                    <th v-for="field in PART_FORMULA_FIELDS" :key="field.key" class="constructionDialog__col constructionDialog__col--formulaExpr">{{ field.label }}</th>
                    <th class="constructionDialog__col constructionDialog__col--owner">مالک</th>
                    <th class="constructionDialog__col constructionDialog__col--scope">نوع رکورد</th>
                    <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in constructionPartFormulas" :key="item.id">
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input v-model.number="item.part_formula_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionPartFormulaDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <select v-model.number="item.part_kind_id" class="constructionDialog__input" @change="markConstructionPartFormulaDirty(item)">
                        <option v-for="option in constructionPartKindOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
                      </select>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button
                        type="button"
                        class="constructionDialog__scopeBtn"
                        :class="getConstructionPartKindInternalLabel(item.part_kind_id) === 'داخلی' ? 'is-admin' : 'is-system'"
                        @click="toggleConstructionPartKindInternalById(item.part_kind_id)"
                      >
                        {{ getConstructionPartKindInternalLabel(item.part_kind_id) }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--id">
                      <input v-model.number="item.part_sub_kind_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionPartFormulaDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--code">
                      <input
                        v-model="item.part_code"
                        :class="[
                          'constructionDialog__input',
                          'constructionDialog__input--mono',
                          `is-${getDuplicateInputTone(item, 'part_code', constructionPartFormulaDuplicateState)}`
                        ]"
                        type="text"
                        @input="markConstructionPartFormulaDirty(item)"
                      />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--title">
                      <input v-model="item.part_title" class="constructionDialog__input" type="text" @input="markConstructionPartFormulaDirty(item)" />
                    </td>
                    <td v-for="field in PART_FORMULA_FIELDS" :key="field.key" class="constructionDialog__col constructionDialog__col--formulaExpr">
                      <button type="button" class="constructionDialog__formulaBtn" @click="openBaseFormulaBuilder(item, 'edit', { entity: 'part_formulas', field: field.key })">
                        <span class="constructionDialog__formulaBtnText">{{ item[field.key] }}</span>
                        <span class="constructionDialog__formulaBtnAction">ویرایش {{ field.label }}</span>
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--owner">
                      <span class="constructionDialog__pill constructionDialog__pill--mono">{{ item.admin_id || "SYSTEM" }}</span>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--scope">
                      <button type="button" class="constructionDialog__scopeBtn" :class="item.admin_id === null ? 'is-system' : 'is-admin'" @click="toggleConstructionPartFormulaScope(item)">
                        {{ item.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
                      </button>
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--actions">
                      <div class="constructionDialog__actionsCell">
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteConstructionPartFormula(item.id)">×</button>
                        <span v-if="constructionDeletingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال حذف</span>
                        <span v-else-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving constructionDialog__saving--compact">در حال ذخیره</span>
                        <span v-else-if="item.__isNew" class="constructionDialog__saving constructionDialog__saving--compact">جدید</span>
                        <span v-else-if="item.__dirty" class="constructionDialog__saving constructionDialog__saving--compact">ذخیره نشده</span>
                        <span
                          class="constructionDialog__duplicateState constructionDialog__duplicateState--compact"
                          :class="`is-${getConstructionPartFormulaDuplicateMessage(item).tone}`"
                        >
                          {{ getConstructionPartFormulaDuplicateMessage(item).text }}
                        </span>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
            <div class="constructionDialog__sheetHint">
              فرمول قطعات می‌توانند از کد پارامترها و همچنین کد فرمول‌های پایه استفاده کنند. هر هشت ستون فرمول هنگام ذخیره از نظر syntax و کدهای ناشناخته اعتبارسنجی می‌شوند.
            </div>
          </template>

          <template v-else>
            <div class="constructionDialog__placeholder">
              <div class="constructionDialog__placeholderTitle">مرحله {{ constructionTables.find((x) => x.id === constructionStep)?.title }}</div>
              <div class="constructionDialog__placeholderMsg">
                این مرحله برای جدول بعدی شیوه ساخت رزرو شده و پس از مشخص کردن فیلدهای دیتابیس به همین wizard متصل می‌شود.
              </div>
            </div>
          </template>
        </section>
      </div>
    </div>
  </div>

  <div v-if="subCategoryDesignEditorOpen" class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeSubCategoryDesignEditor"></div>
    <div class="appDialog__card appDialog__card--subDesign" dir="rtl">
      <div class="formulaBuilder__head">
        <div class="constructionDialog__sectionTitle formulaBuilder__title">ویرایش طرح ساب‌کت</div>
        <button type="button" class="constructionDialog__close formulaBuilder__close" title="بستن" @click="closeSubCategoryDesignEditor">×</button>
      </div>
      <div class="constructionDialog__sectionHint">
        قطعات طرح از فرمول‌های قطعات انتخاب می‌شوند و preview به‌صورت مستقیم از پیش‌فرض‌های ساب‌کت و محاسبات فرمولی بازسازی می‌شود.
      </div>

      <div v-if="subCategoryDesignEditorDraft" class="subCategoryDesignEditor">
        <div class="subCategoryDesignEditor__meta">
          <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--wide">
            <span>ساب‌کت</span>
            <select v-model="subCategoryDesignEditorDraft.sub_category_id" class="constructionDialog__input" @change="onSubCategoryDesignSubCategoryChange">
              <option v-for="item in constructionSubCategoryDesignSubCategoryOptions" :key="item.value" :value="item.value">{{ item.label }}</option>
            </select>
          </label>
          <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--compact">
            <span>شناسه طرح</span>
            <input v-model.number="subCategoryDesignEditorDraft.design_id" class="constructionDialog__input" type="number" min="1" step="1" />
          </label>
          <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--wide">
            <span>عنوان طرح</span>
            <input v-model="subCategoryDesignEditorDraft.design_title" class="constructionDialog__input" type="text" />
          </label>
          <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--compact">
            <span>کد طرح</span>
            <input v-model="subCategoryDesignEditorDraft.code" class="constructionDialog__input constructionDialog__input--mono" type="text" />
          </label>
          <div class="subCategoryDesignEditor__metaActions">
            <button type="button" class="subCategoryDesignEditor__settingsBtn" :class="{ 'is-active': interiorLibraryOpen }" title="قطعات داخلی" @click="openInteriorLibrary">
              <img src="/icons/enternal.png" alt="" class="subCategoryDesignEditor__metaIcon" />
              <span>داخلی</span>
            </button>
            <button type="button" class="subCategoryDesignEditor__settingsBtn" title="پیش‌فرض ادمین" @click="openSubCategoryAdminDefaultsFromDesignEditor">
              <img src="/icons/setting.png" alt="" class="subCategoryDesignEditor__metaIcon" />
              <span>پیش‌فرض ادمین</span>
            </button>
          </div>
        </div>

        <div class="subCategoryDesignEditor__layout">
          <div class="subCategoryDesignEditor__panel subCategoryDesignEditor__panel--parts">
            <div class="subCategoryDesignEditor__panelTitle">قطعات قابل افزودن</div>
            <div class="subCategoryDesignEditor__partList">
              <label v-for="item in constructionSubCategoryDesignPartFormulaOptions" :key="item.id" class="subCategoryDesignEditor__partItem">
                <input :checked="isPartFormulaSelectedInDesign(item.id)" type="checkbox" @change="togglePartFormulaInDesign(item.id)" />
                <span class="subCategoryDesignEditor__partMeta">
                  <span class="subCategoryDesignEditor__partTitle">{{ item.title }}</span>
                  <span class="subCategoryDesignEditor__partCode">{{ item.code }}</span>
                </span>
              </label>
            </div>
          </div>

          <div class="subCategoryDesignEditor__panel subCategoryDesignEditor__panel--preview">
            <div class="subCategoryDesignEditor__panelTitle">پیش‌نمایش طرح</div>
            <div v-if="subCategoryDesignEditorPreview" class="subCategoryDesignEditor__previewBody">
              <div class="subCategoryDesignEditor__viewerWrap">
                <GlbViewerWidget
                  src="/models/1_z1.glb"
                  :walls2d="{ nodes: [], walls: [], selection: { selectedWallId: null, selectedWallIds: [] }, state: {} }"
                  :placeholder-outline-color="normalizeHexColor(subCategoryDesignEditorPreview?.design_outline_color)"
                  :placeholder-boxes="subCategoryDesignEditorPreview.viewer_boxes"
                  :display-unit="currentEditorDisplayUnit"
                  :show-attrs-panel="false"
                  :embedded="true"
                />
                <div v-if="subCategoryDesignPreviewLoading" class="subCategoryDesignEditor__viewerOverlay">
                  <div class="constructionDialog__loading">در حال بازسازی preview طرح...</div>
                </div>
              </div>
            </div>
            <div v-else-if="subCategoryDesignPreviewLoading" class="constructionDialog__loading">در حال بازسازی preview طرح...</div>
            <div v-else-if="subCategoryDesignPreviewError" class="formulaBuilder__error">{{ subCategoryDesignPreviewError }}</div>
          </div>
        </div>
      </div>

      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" :disabled="subCategoryDesignEditorSaving" @click="closeSubCategoryDesignEditor">انصراف</button>
        <button type="button" class="constructionDialog__textBtn is-primary" :disabled="subCategoryDesignEditorSaving" @click="saveSubCategoryDesignEditor">
          <span v-if="subCategoryDesignEditorSaving" class="constructionDialog__spinner"></span>
          <span>{{ subCategoryDesignEditorSaving ? "در حال ذخیره..." : "ذخیره طرح" }}</span>
        </button>
      </div>
    </div>
  </div>

  <div v-if="internalPartGroupEditorOpen" class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeInternalPartGroupEditor"></div>
    <div class="appDialog__card appDialog__card--subDesign" dir="rtl">
      <div class="formulaBuilder__head">
        <div class="constructionDialog__sectionTitle formulaBuilder__title">ویرایش گروه قطعات داخلی</div>
        <button type="button" class="constructionDialog__close formulaBuilder__close" title="بستن" @click="closeInternalPartGroupEditor">×</button>
      </div>
      <div class="constructionDialog__sectionHint">
        در این پنجره از بین قطعات داخلی سمت راست، گروه موردنظر را می‌سازید. همچنین از دکمه گروه پارامترها می‌توانید لیست گروه‌های پارامتر را باز کرده و چند مورد را به این گروه نسبت دهید.
      </div>

      <div v-if="internalPartGroupEditorDraft" class="subCategoryDesignEditor">
        <div class="subCategoryDesignEditor__meta">
          <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--compact">
            <span>شناسه گروه</span>
            <input v-model.number="internalPartGroupEditorDraft.group_id" class="constructionDialog__input" type="number" min="1" step="1" />
          </label>
          <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--wide">
            <span>عنوان گروه</span>
            <input v-model="internalPartGroupEditorDraft.group_title" class="constructionDialog__input" type="text" />
          </label>
          <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--compact">
            <span>کد گروه</span>
            <input v-model="internalPartGroupEditorDraft.code" class="constructionDialog__input constructionDialog__input--mono" type="text" />
          </label>
          <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--wide">
            <span>رنگ پیش‌فرض خطوط</span>
            <div class="constructionDialog__colorEditor">
              <input
                v-model="internalPartGroupEditorDraft.line_color"
                class="constructionDialog__colorInput"
                type="color"
                @input="internalPartGroupEditorDraft.line_color = normalizeHexColor(internalPartGroupEditorDraft.line_color, DEFAULT_INTERIOR_LINE_COLOR)"
              />
              <input
                v-model="internalPartGroupEditorDraft.line_color"
                class="constructionDialog__input constructionDialog__input--mono constructionDialog__colorHex"
                type="text"
                dir="ltr"
                maxlength="7"
                :placeholder="DEFAULT_INTERIOR_LINE_COLOR"
                @change="internalPartGroupEditorDraft.line_color = normalizeHexColor(internalPartGroupEditorDraft.line_color, DEFAULT_INTERIOR_LINE_COLOR)"
              />
            </div>
          </label>
          <div class="subCategoryDesignEditor__metaActions">
            <button type="button" class="subCategoryDesignEditor__settingsBtn" :class="{ 'is-active': internalPartGroupParamGroupsOpen }" title="گروه پارامترها" @click="toggleInternalPartGroupParamGroupsPanel">
              <svg viewBox="0 0 24 24" class="subCategoryDesignEditor__metaIcon subCategoryDesignEditor__metaIcon--glyph" aria-hidden="true">
                <rect x="3" y="4" width="8" height="6" rx="2" fill="currentColor" opacity="0.9" />
                <rect x="13" y="4" width="8" height="6" rx="2" fill="currentColor" opacity="0.7" />
                <rect x="3" y="14" width="8" height="6" rx="2" fill="currentColor" opacity="0.7" />
                <rect x="13" y="14" width="8" height="6" rx="2" fill="currentColor" opacity="0.9" />
              </svg>
              <span>گروه پارامترها</span>
            </button>
          </div>
        </div>

        <div class="subCategoryDesignEditor__layout">
          <div class="subCategoryDesignEditor__panel subCategoryDesignEditor__panel--parts">
            <div class="subCategoryDesignEditor__panelTitle">قطعات داخلی قابل انتخاب</div>
            <div class="subCategoryDesignEditor__partList">
              <label v-for="item in constructionInteriorPartFormulaOptions" :key="item.id" class="subCategoryDesignEditor__partItem">
                <input :checked="isInternalPartFormulaSelectedInGroup(item.id)" type="checkbox" @change="togglePartFormulaInInternalGroup(item.id)" />
                <span class="subCategoryDesignEditor__partMeta">
                  <span class="subCategoryDesignEditor__partTitle">{{ item.title }}</span>
                  <span class="subCategoryDesignEditor__partCode">{{ item.code }}</span>
                </span>
              </label>
            </div>
          </div>

          <div class="subCategoryDesignEditor__panel subCategoryDesignEditor__panel--parts">
            <div class="subCategoryDesignEditor__panelTitle">خلاصه گروه</div>
            <div class="constructionDialog__summary">
              <div class="constructionDialog__summaryItem">
                <span class="constructionDialog__summaryValue">{{ toPersianDigits(internalPartGroupEditorDraft.parts?.length || 0) }}</span>
                <span class="constructionDialog__summaryLabel">قطعه انتخاب‌شده</span>
              </div>
            </div>
            <div class="subCategoryDesignEditor__partList">
              <div v-for="part in internalPartGroupEditorDraft.parts" :key="part.part_formula_id" class="subCategoryDesignEditor__partItem is-static">
                <span class="subCategoryDesignEditor__partMeta">
                  <span class="subCategoryDesignEditor__partTitle">
                    {{ constructionInteriorPartFormulaOptions.find((item) => Number(item.id) === Number(part.part_formula_id))?.title || part.part_formula_id }}
                  </span>
                  <span class="subCategoryDesignEditor__partCode">
                    {{ constructionInteriorPartFormulaOptions.find((item) => Number(item.id) === Number(part.part_formula_id))?.code || "" }}
                  </span>
                </span>
              </div>
              <div v-if="!(internalPartGroupEditorDraft.parts?.length)" class="designMenu__cabinetState">هنوز قطعه داخلی انتخاب نشده است.</div>
            </div>
          </div>
        </div>
      </div>

      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" @click="closeInternalPartGroupEditor">انصراف</button>
        <button type="button" class="constructionDialog__textBtn is-primary" @click="saveInternalPartGroupEditor">ذخیره گروه</button>
      </div>
    </div>
  </div>

  <div v-if="internalPartGroupEditorOpen && internalPartGroupParamGroupsOpen && internalPartGroupEditorDraft" class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="toggleInternalPartGroupParamGroupsPanel"></div>
    <div class="appDialog__card appDialog__card--paramGroups" dir="rtl">
      <div class="formulaBuilder__head">
        <div class="constructionDialog__sectionTitle formulaBuilder__title">انتخاب گروه‌های پارامتر</div>
        <button type="button" class="constructionDialog__close formulaBuilder__close" title="بستن" @click="toggleInternalPartGroupParamGroupsPanel">×</button>
      </div>
      <div class="constructionDialog__sectionHint">
        از این پنجره یک یا چند گروه پارامتر را برای این گروه قطعات داخلی انتخاب کنید.
      </div>
      <div class="constructionDialog__summary">
        <div class="constructionDialog__summaryItem">
          <span class="constructionDialog__summaryValue">{{ toPersianDigits(internalPartGroupEditorDraft.param_groups?.length || 0) }}</span>
          <span class="constructionDialog__summaryLabel">گروه انتخاب‌شده</span>
        </div>
      </div>
      <div class="subCategoryDesignEditor__panel subCategoryDesignEditor__panel--parts subCategoryDesignEditor__modalPanel">
        <div class="subCategoryDesignEditor__panelTitle">گروه‌های پارامتر قابل انتخاب</div>
        <div class="subCategoryDesignEditor__partList">
          <label v-for="item in constructionInternalParamGroupOptions" :key="item.id" class="subCategoryDesignEditor__partItem subCategoryDesignEditor__partItem--paramGroup">
            <span class="subCategoryDesignEditor__partMeta">
              <img v-if="item.iconPath" :src="getParamGroupOptionIconUrl(item.iconPath)" alt="" class="subCategoryDesignEditor__partIcon" />
              <span class="subCategoryDesignEditor__partText">
                <span class="subCategoryDesignEditor__partTitle">{{ item.title }}</span>
                <span class="subCategoryDesignEditor__partCode">{{ item.code }}</span>
              </span>
            </span>
            <input :checked="isParamGroupSelectedInInternalGroup(item.id)" type="checkbox" @change="toggleParamGroupInInternalGroup(item.id)" />
          </label>
          <div v-if="!constructionInternalParamGroupOptions.length" class="designMenu__cabinetState">هنوز گروه پارامتری برای انتخاب ثبت نشده است.</div>
        </div>
      </div>
      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" @click="toggleInternalPartGroupParamGroupsPanel">بستن</button>
      </div>
    </div>
  </div>

  <div v-if="internalPartGroupDefaultsEditorOpen" class="appDialog appDialog--stacked" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeInternalPartGroupDefaultsEditor"></div>
    <div class="appDialog__card appDialog__card--subPreview" dir="rtl">
      <div class="subCategoryPreview__header">
        <div>
          <div class="subCategoryPreview__title">پیش‌فرض‌های گروه داخلی</div>
          <div class="subCategoryPreview__caption">
            {{ activeInternalPartGroupDefaultsRow?.group_title || "گروه داخلی" }}
            <span v-if="activeInternalPartGroupDefaultsRow">
              {{ toPersianDigits(activeInternalPartGroupDefaultsRow.group_id) }}
            </span>
          </div>
        </div>
        <button type="button" class="constructionDialog__textBtn" @click="closeInternalPartGroupDefaultsEditor">بستن</button>
      </div>
      <div class="constructionDialog__sectionHint">
        در این بخش فقط مقدار پیش‌فرض پارامترهای همان گروه قطعات داخلی ثبت می‌شود. عنوان، آیکون و نوع نمایش از پیش‌فرض‌های ساب‌کت/طرح خوانده می‌شود.
      </div>
      <div class="subCategoryPreview__body">
        <div class="subCategoryPreview__tree">
          <div class="subCategoryPreview__panel subCategoryPreview__panel--groups">
            <div class="subCategoryPreview__selectorList">
              <button
                v-for="group in activeInternalPartGroupDefaultsGroups"
                :key="group.id"
                type="button"
                class="subCategoryPreview__groupHead"
                :class="{ 'is-active': String(activeInternalPartGroupDefaultsGroup?.id || '') === String(group.id) }"
                @click="selectInternalPartGroupDefaultsGroup(group.id)"
              >
                <div class="subCategoryPreview__groupMeta">
                  <div class="subCategoryPreview__groupTitle">{{ group.title }}</div>
                  <div class="subCategoryPreview__groupCaption">{{ toPersianDigits(group.items.length) }} پارامتر</div>
                </div>
                <div class="subCategoryPreview__groupBadge" :class="{ 'is-empty': !group.iconUrl }">
                  <img
                    v-if="group.iconUrl"
                    :key="group.iconUrl"
                    :src="group.iconUrl"
                    :alt="group.title"
                    class="subCategoryPreview__groupIcon"
                    @error="handleSubCategoryDefaultIconError"
                  />
                  <span v-else class="subCategoryPreview__groupFallback">{{ toPersianDigits(group.items.length) }}</span>
                </div>
                <span class="subCategoryPreview__groupChevron" aria-hidden="true">‹</span>
              </button>
            </div>
          </div>
          <div class="subCategoryPreview__panel subCategoryPreview__panel--params">
            <div v-if="activeInternalPartGroupDefaultsGroup" class="subCategoryPreview__panelHead">
              <div class="subCategoryPreview__panelTitle">{{ activeInternalPartGroupDefaultsGroup.title }}</div>
              <div class="subCategoryPreview__panelCaption">{{ toPersianDigits(activeInternalPartGroupDefaultsGroup.items.length) }} پارامتر در این گروه</div>
            </div>
            <div v-if="activeInternalPartGroupDefaultsGroup" class="subCategoryPreview__params">
              <article v-for="column in activeInternalPartGroupDefaultsGroup.items" :key="column.key" class="subCategoryPreview__paramCard">
                <template v-if="column.inputMode === 'binary'">
                  <div class="subCategoryPreview__paramMeta">
                    <div class="subCategoryPreview__paramTitle">{{ column.displayTitle }}</div>
                    <div v-if="column.descriptionText" class="subCategoryPreview__paramDescription">{{ column.descriptionText }}</div>
                  </div>
                  <div class="subCategoryPreview__binaryChoices">
                    <button
                      type="button"
                      class="subCategoryPreview__binaryChoice"
                      :class="{ 'is-active': String(internalPartGroupDefaultsValues[column.key] ?? '0') !== '1' }"
                      @click="setInternalPartGroupBinaryDefault(column.key, '0')"
                    >
                      <img :src="column.binaryOffIconUrl" :alt="column.binaryOffLabel" class="subCategoryPreview__binaryIcon" @error="handleSubCategoryDefaultIconError" />
                      <span class="subCategoryPreview__binaryLabel">{{ column.binaryOffLabel }}</span>
                    </button>
                    <button
                      type="button"
                      class="subCategoryPreview__binaryChoice"
                      :class="{ 'is-active': String(internalPartGroupDefaultsValues[column.key] ?? '0') === '1' }"
                      @click="setInternalPartGroupBinaryDefault(column.key, '1')"
                    >
                      <img :src="column.binaryOnIconUrl" :alt="column.binaryOnLabel" class="subCategoryPreview__binaryIcon" @error="handleSubCategoryDefaultIconError" />
                      <span class="subCategoryPreview__binaryLabel">{{ column.binaryOnLabel }}</span>
                    </button>
                  </div>
                </template>
                <template v-else>
                  <div class="subCategoryPreview__valueHead">
                    <div class="subCategoryPreview__valueIconBox">
                      <img :src="column.iconUrl" :alt="column.displayTitle" class="subCategoryPreview__valueIcon" @error="handleSubCategoryDefaultIconError" />
                    </div>
                    <div class="subCategoryPreview__paramMeta">
                      <div class="subCategoryPreview__paramTitle">{{ column.displayTitle }}</div>
                      <div v-if="column.descriptionText" class="subCategoryPreview__paramDescription">{{ column.descriptionText }}</div>
                    </div>
                  </div>
                  <input
                    v-model="internalPartGroupDefaultsValues[column.key]"
                    class="constructionDialog__input subCategoryPreview__valueInput"
                    type="number"
                    inputmode="numeric"
                    min="0"
                    :placeholder="column.displayTitle"
                  />
                  <div class="subCategoryPreview__valueUnit">میلی‌متر</div>
                </template>
              </article>
            </div>
            <div v-else class="designMenu__cabinetState">برای این گروه داخلی هنوز پارامتری قابل نمایش نیست.</div>
          </div>
        </div>
      </div>
      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" :disabled="internalPartGroupDefaultsApplying" @click="closeInternalPartGroupDefaultsEditor">انصراف</button>
        <button type="button" class="constructionDialog__textBtn is-primary" :disabled="internalPartGroupDefaultsApplying" @click="applyInternalPartGroupDefaultsEditor">
          <span v-if="internalPartGroupDefaultsApplying" class="constructionDialog__spinner"></span>
          <span>{{ internalPartGroupDefaultsApplying ? "در حال اعمال..." : "اعمال" }}</span>
        </button>
      </div>
    </div>
  </div>

  <div v-if="internalPartGroupControllerEditorOpen" class="appDialog appDialog--stacked" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeInternalPartGroupControllerEditor"></div>
    <div class="appDialog__card appDialog__card--subPreview" dir="rtl">
      <div class="subCategoryPreview__header">
        <div>
          <div class="subCategoryPreview__title">کنترلر گروه قطعات داخلی</div>
          <div class="subCategoryPreview__caption">
            {{ activeInternalPartGroupControllerRow?.group_title || "گروه داخلی" }}
            <span v-if="activeInternalPartGroupControllerRow">
              {{ toPersianDigits(activeInternalPartGroupControllerRow.group_id) }}
            </span>
          </div>
        </div>
        <button type="button" class="constructionDialog__textBtn" @click="closeInternalPartGroupControllerEditor">بستن</button>
      </div>
      <div class="constructionDialog__sectionHint">
        نوع کنترلر گروه و پارامتر متصل به هر دستک در این بخش مشخص می‌شود. در این فاز فقط کنترلر قطعات عرضی فعال است.
      </div>
      <div class="subCategoryPreview__body">
        <div class="subCategoryPreview__panel subCategoryPreview__panel--params">
          <div class="subCategoryPreview__panelHead">
            <div class="subCategoryPreview__panelTitle">نوع کنترلر</div>
            <div class="subCategoryPreview__panelCaption">منبع پیش‌فرض عدد دستک‌ها از پارامترهای همین گروه داخلی خوانده می‌شود.</div>
          </div>
          <div class="constructionDialog__controllerForm">
            <label class="constructionDialog__field">
              <span class="constructionDialog__fieldLabel">نوع کنترلر گروه</span>
              <select
                :value="internalPartGroupControllerEditorType"
                class="constructionDialog__input"
                @change="updateInternalPartGroupControllerEditorType($event.target.value)"
              >
                <option value="">بدون کنترلر</option>
                <option v-for="option in INTERNAL_GROUP_CONTROLLER_TYPE_OPTIONS" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </label>

            <div v-if="internalPartGroupControllerEditorType" class="constructionDialog__controllerCards">
              <div
                v-for="definition in getInternalPartGroupControllerDefinitions(internalPartGroupControllerEditorType)"
                :key="definition.key"
                class="constructionDialog__controllerCard"
              >
                <div class="constructionDialog__controllerCardMeta">
                  <div class="constructionDialog__controllerCardTitle">{{ definition.label }}</div>
                  <div class="constructionDialog__controllerCardCaption">{{ definition.key }}</div>
                </div>
                <select
                  v-model="internalPartGroupControllerEditorBindings[definition.key].param_code"
                  class="constructionDialog__input"
                  :disabled="!getInternalPartGroupControllerParamOptions(activeInternalPartGroupControllerRow).length"
                >
                  <option :value="null">بدون اتصال</option>
                  <option
                    v-for="option in getInternalPartGroupControllerParamOptions(activeInternalPartGroupControllerRow)"
                    :key="option.value"
                    :value="option.value"
                  >
                    {{ option.label }}
                  </option>
                </select>
              </div>
            </div>

            <div
              v-if="internalPartGroupControllerEditorType && !getInternalPartGroupControllerParamOptions(activeInternalPartGroupControllerRow).length"
              class="designMenu__cabinetState"
            >
              برای این گروه داخلی هنوز پارامتری انتخاب نشده است. ابتدا گروه‌های پارامتری همین گروه داخلی را تنظیم کنید.
            </div>
          </div>
        </div>
      </div>
      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" :disabled="internalPartGroupControllerEditorApplying" @click="closeInternalPartGroupControllerEditor">انصراف</button>
        <button type="button" class="constructionDialog__textBtn is-primary" :disabled="internalPartGroupControllerEditorApplying" @click="applyInternalPartGroupControllerEditor">
          <span v-if="internalPartGroupControllerEditorApplying" class="constructionDialog__spinner"></span>
          <span>{{ internalPartGroupControllerEditorApplying ? "در حال اعمال..." : "اعمال" }}</span>
        </button>
      </div>
    </div>
  </div>

  <div v-if="interiorLibraryOpen" class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeInteriorLibrary"></div>
    <div class="appDialog__card appDialog__card--subDesign" dir="rtl">
      <div class="formulaBuilder__head">
        <div class="constructionDialog__sectionTitle formulaBuilder__title">قطعات داخلی</div>
        <button type="button" class="constructionDialog__close formulaBuilder__close" title="بستن" @click="closeInteriorLibrary">×</button>
      </div>
      <div class="constructionDialog__sectionHint">
        در این مرحله، سمت راست کتابخانه گروه‌های قطعات داخلی، ستون میانی نمونه‌های اضافه‌شده به همین طرح، و سمت چپ نمای روبه‌روی خطی طرح اصلی دیده می‌شود.
      </div>
      <div class="subCategoryDesignEditor__layout subCategoryDesignEditor__layout--interiorLibrary">
        <div class="subCategoryDesignEditor__panel subCategoryDesignEditor__panel--preview subCategoryDesignEditor__panel--interiorPreview">
          <div class="subCategoryDesignEditor__panelHead subCategoryDesignEditor__panelHead--interiorPreview">
            <div class="subCategoryDesignEditor__panelTitle">{{ interiorLibraryPreviewPanelTitle }}</div>
            <div class="subCategoryDesignEditor__previewActions">
              <button
                type="button"
                class="iconbtn iconbtn--sm stageQuickBar__btn subCategoryDesignEditor__previewIconBtn"
                :class="{ 'is-active': interiorLibraryPreviewMode === 'front2d' }"
                title="نمای داخلی دوبعدی"
                @click="setInteriorLibraryPreviewMode('front2d')"
              >
                <img src="/icons/enternal.png" alt="" />
              </button>
              <button
                type="button"
                class="iconbtn iconbtn--sm stageQuickBar__btn subCategoryDesignEditor__previewIconBtn"
                :class="{ 'is-active': interiorLibraryPreviewMode === 'model3d' }"
                title="نمای سه بعدی طرح"
                @click="setInteriorLibraryPreviewMode('model3d')"
              >
                <img src="/icons/3d_viewer.png" alt="" />
              </button>
              <button
                type="button"
                class="iconbtn iconbtn--sm stageQuickBar__btn subCategoryDesignEditor__previewIconBtn"
                :class="{ 'is-active': interiorLibraryControllerTestMode }"
                title="تست کنترلر قطعات داخلی"
                aria-label="تست کنترلر قطعات داخلی"
                @click="openInteriorControllerTest"
              >
                <img src="/icons/double-arrow.png" alt="" />
              </button>
              <button
                type="button"
                class="iconbtn iconbtn--sm stageQuickBar__btn subCategoryDesignEditor__previewIconBtn"
                :class="{ 'is-active': interiorLibraryShowDimensions }"
                title="نمایش اندازه گذاری"
                aria-label="نمایش اندازه گذاری"
                @click="toggleInteriorLibraryDimensionsVisibility"
              >
                <img src="/icons/turn_dim.png" alt="" />
              </button>
              <button
                type="button"
                class="iconbtn iconbtn--sm stageQuickBar__btn subCategoryDesignEditor__previewIconBtn"
                :class="{ 'is-active': interiorLibraryShowGuideAnnotations }"
                title="نمایش خطوط راهنما"
                aria-label="نمایش خطوط راهنما"
                @click="toggleInteriorLibraryGuideAnnotationsVisibility"
              >
                <img src="/icons/turn_offset.png" alt="" />
              </button>
              <button
                type="button"
                class="iconbtn iconbtn--sm stageQuickBar__btn subCategoryDesignEditor__previewIconBtn"
                :class="{ 'is-active': interiorLibraryShowInnerLines }"
                title="نمایش خطوط داخلی"
                aria-label="نمایش خطوط داخلی"
                @click="toggleInteriorLibraryGuideTool"
              >
                <img src="/icons/drawing_wall.png" alt="" />
              </button>
              <button
                type="button"
                class="iconbtn iconbtn--sm stageQuickBar__btn subCategoryDesignEditor__previewIconBtn"
                title="بزرگنمایی نمای دوبعدی"
                @click="zoomInteriorLibraryFrontIn"
              >
                <img src="/icons/zoom-in.png" alt="" />
              </button>
              <button
                type="button"
                class="iconbtn iconbtn--sm stageQuickBar__btn subCategoryDesignEditor__previewIconBtn"
                title="کوچکنمایی نمای دوبعدی"
                @click="zoomInteriorLibraryFrontOut"
              >
                <img src="/icons/zoom-out.png" alt="" />
              </button>
              <div v-if="interiorLibraryPreviewMode === 'model3d'" class="subCategoryDesignEditor__previewOpacity">
                <span class="subCategoryDesignEditor__previewOpacityValue">0</span>
                <input
                  :value="interiorLibraryPreviewOpacity"
                  class="subCategoryDesignEditor__previewOpacitySlider"
                  type="range"
                  min="0"
                  max="100"
                  step="1"
                  @input="setInteriorLibraryPreviewOpacity($event.target.value)"
                />
                <span class="subCategoryDesignEditor__previewOpacityValue">100</span>
              </div>
            </div>
          </div>
          <div class="subCategoryDesignEditor__previewBody subCategoryDesignEditor__previewBody--interior">
            <div
              ref="interiorLibraryViewerWrapEl"
              class="subCategoryDesignEditor__viewerWrap subCategoryDesignEditor__viewerWrap--interior"
              :class="[
                interiorLibraryFrontCursorClass,
                {
                  'is-panning': interiorLibraryFrontPanning && interiorLibraryPreviewMode === 'front2d',
                  'is-front2d-mode': interiorLibraryPreviewMode === 'front2d',
                }
              ]"
              @wheel.prevent="handleInteriorLibraryPreviewWheel"
              @pointermove="onInteriorLibraryViewerPointerMove"
              @pointerleave="onInteriorLibraryViewerPointerLeave"
              @pointerdown="onInteriorLibraryViewerPointerDown"
              @dblclick.prevent="focusInteriorLibraryPreviewCloser"
            >
              <div v-if="interiorLibraryPreviewMode === 'front2d'" class="subCategoryDesignEditor__annotationTools">
                <button
                  type="button"
                  class="iconbtn iconbtn--sm stageQuickBar__btn subCategoryDesignEditor__previewIconBtn subCategoryDesignEditor__annotationToolBtn"
                  :class="{ 'is-active': interiorLibraryAnnotationTool === 'dimension' }"
                  title="رسم اندازه گذاری"
                  @click.stop="toggleInteriorLibraryDimensionTool"
                >
                  <img src="/icons/drawing_dimension.png" alt="" />
                </button>
                <button
                  type="button"
                  class="iconbtn iconbtn--sm stageQuickBar__btn subCategoryDesignEditor__previewIconBtn subCategoryDesignEditor__annotationToolBtn"
                  :class="{ 'is-active': interiorLibraryAnnotationTool === 'guide' }"
                  title="رسم خط راهنما"
                  @click.stop="toggleInteriorLibraryGuideAnnotationTool"
                >
                  <img src="/icons/drawing_hidden_wall.png" alt="" />
                </button>
              </div>
              <GlbViewerWidget
                v-if="interiorLibraryPreviewMode === 'model3d' && activeInteriorLibraryViewerBoxes.length"
                ref="interiorLibraryPreview3dRef"
                src="/models/1_z1.glb"
                :walls2d="{ nodes: [], walls: [], selection: { selectedWallId: null, selectedWallIds: [] }, state: {} }"
                :placeholder-outline-color="activeInteriorLibraryOutlineColor"
                :placeholder-boxes="activeInteriorLibraryViewerBoxes"
                :display-unit="currentEditorDisplayUnit"
                :show-attrs-panel="false"
                :embedded="true"
                :preview-only="true"
                :preview-active="interiorLibraryOpen"
              />
              <svg
                v-else-if="interiorLibraryPreviewSvgLines.outer.length"
                ref="interiorLibraryFrontSvgEl"
                :viewBox="interiorLibraryFrontSvgViewBox"
                class="subCategoryDesignEditor__frontSvg"
                :class="interiorLibraryFrontCursorClass"
                @pointerdown="onInteriorLibraryFrontSvgPointerDown"
                @pointermove="onInteriorLibraryFrontSvgPointerMove"
                @pointerup="onInteriorLibraryFrontSvgPointerUp"
                @pointercancel="onInteriorLibraryFrontSvgPointerCancel"
                @pointerleave="onInteriorLibraryFrontSvgPointerLeave"
              >
                <defs>
                  <pattern id="interior-front-grid" width="40" height="40" patternUnits="userSpaceOnUse">
                    <path d="M 40 0 L 0 0 0 40" fill="none" stroke="rgba(90,60,66,0.08)" stroke-width="1" />
                  </pattern>
                </defs>
                <rect
                  :x="interiorLibraryFrontSvgViewBoxRect.x"
                  :y="interiorLibraryFrontSvgViewBoxRect.y"
                  :width="interiorLibraryFrontSvgViewBoxRect.width"
                  :height="interiorLibraryFrontSvgViewBoxRect.height"
                  fill="url(#interior-front-grid)"
                />
                <circle
                  v-if="interiorLibraryShouldShowSnapMarkers"
                  v-for="(point, index) in interiorLibraryFrontSnapPoints"
                  :key="`interior-snap-${index}`"
                  :cx="point.x"
                  :cy="point.y"
                  class="subCategoryDesignEditor__snapPoint"
                  r="3.6"
                />
                <circle
                  v-if="interiorLibraryShouldShowSnapMarkers && interiorLibraryCurrentSnapPoint"
                  :cx="interiorLibraryCurrentSnapPoint.x"
                  :cy="interiorLibraryCurrentSnapPoint.y"
                  class="subCategoryDesignEditor__snapPoint subCategoryDesignEditor__snapPoint--active"
                  :r="interiorLibraryCurrentSnapPoint.kind === 'edge' ? 4.4 : 5.2"
                />
                <g
                  v-if="interiorLibraryCursorPoint && (interiorLibraryAnnotationTool === 'dimension' || interiorLibraryAnnotationTool === 'guide')"
                  class="subCategoryDesignEditor__drawCursor"
                >
                  <circle
                    :cx="interiorLibraryCursorPoint.x"
                    :cy="interiorLibraryCursorPoint.y"
                    :r="6.5 * interiorLibraryCursorVisualScale"
                    class="subCategoryDesignEditor__drawCursorRing"
                  />
                  <line
                    :x1="interiorLibraryCursorPoint.x - (7 * interiorLibraryCursorVisualScale)"
                    :y1="interiorLibraryCursorPoint.y"
                    :x2="interiorLibraryCursorPoint.x + (7 * interiorLibraryCursorVisualScale)"
                    :y2="interiorLibraryCursorPoint.y"
                    class="subCategoryDesignEditor__drawCursorLine"
                  />
                  <line
                    :x1="interiorLibraryCursorPoint.x"
                    :y1="interiorLibraryCursorPoint.y - (7 * interiorLibraryCursorVisualScale)"
                    :x2="interiorLibraryCursorPoint.x"
                    :y2="interiorLibraryCursorPoint.y + (7 * interiorLibraryCursorVisualScale)"
                    class="subCategoryDesignEditor__drawCursorLine"
                  />
                </g>
                <g
                  v-else-if="interiorLibraryFrontShowPanCursor"
                  class="subCategoryDesignEditor__drawCursor"
                >
                  <circle
                    :cx="interiorLibraryCursorPoint.x"
                    :cy="interiorLibraryCursorPoint.y"
                    :r="6 * interiorLibraryCursorVisualScale"
                    class="subCategoryDesignEditor__floatingCursorCenter"
                  />
                  <line
                    :x1="interiorLibraryCursorPoint.x"
                    :y1="interiorLibraryCursorPoint.y - (20 * interiorLibraryCursorVisualScale)"
                    :x2="interiorLibraryCursorPoint.x"
                    :y2="interiorLibraryCursorPoint.y - (7 * interiorLibraryCursorVisualScale)"
                    class="subCategoryDesignEditor__floatingCursorLine"
                  />
                  <line
                    :x1="interiorLibraryCursorPoint.x"
                    :y1="interiorLibraryCursorPoint.y + (7 * interiorLibraryCursorVisualScale)"
                    :x2="interiorLibraryCursorPoint.x"
                    :y2="interiorLibraryCursorPoint.y + (20 * interiorLibraryCursorVisualScale)"
                    class="subCategoryDesignEditor__floatingCursorLine"
                  />
                  <line
                    :x1="interiorLibraryCursorPoint.x - (20 * interiorLibraryCursorVisualScale)"
                    :y1="interiorLibraryCursorPoint.y"
                    :x2="interiorLibraryCursorPoint.x - (7 * interiorLibraryCursorVisualScale)"
                    :y2="interiorLibraryCursorPoint.y"
                    class="subCategoryDesignEditor__floatingCursorLine"
                  />
                  <line
                    :x1="interiorLibraryCursorPoint.x + (7 * interiorLibraryCursorVisualScale)"
                    :y1="interiorLibraryCursorPoint.y"
                    :x2="interiorLibraryCursorPoint.x + (20 * interiorLibraryCursorVisualScale)"
                    :y2="interiorLibraryCursorPoint.y"
                    class="subCategoryDesignEditor__floatingCursorLine"
                  />
                  <path
                    :d="`M ${interiorLibraryCursorPoint.x} ${interiorLibraryCursorPoint.y - (22 * interiorLibraryCursorVisualScale)} L ${interiorLibraryCursorPoint.x - (4 * interiorLibraryCursorVisualScale)} ${interiorLibraryCursorPoint.y - (15 * interiorLibraryCursorVisualScale)} L ${interiorLibraryCursorPoint.x + (4 * interiorLibraryCursorVisualScale)} ${interiorLibraryCursorPoint.y - (15 * interiorLibraryCursorVisualScale)} Z`"
                    class="subCategoryDesignEditor__floatingCursorArrow"
                  />
                  <path
                    :d="`M ${interiorLibraryCursorPoint.x} ${interiorLibraryCursorPoint.y + (22 * interiorLibraryCursorVisualScale)} L ${interiorLibraryCursorPoint.x - (4 * interiorLibraryCursorVisualScale)} ${interiorLibraryCursorPoint.y + (15 * interiorLibraryCursorVisualScale)} L ${interiorLibraryCursorPoint.x + (4 * interiorLibraryCursorVisualScale)} ${interiorLibraryCursorPoint.y + (15 * interiorLibraryCursorVisualScale)} Z`"
                    class="subCategoryDesignEditor__floatingCursorArrow"
                  />
                  <path
                    :d="`M ${interiorLibraryCursorPoint.x - (22 * interiorLibraryCursorVisualScale)} ${interiorLibraryCursorPoint.y} L ${interiorLibraryCursorPoint.x - (15 * interiorLibraryCursorVisualScale)} ${interiorLibraryCursorPoint.y - (4 * interiorLibraryCursorVisualScale)} L ${interiorLibraryCursorPoint.x - (15 * interiorLibraryCursorVisualScale)} ${interiorLibraryCursorPoint.y + (4 * interiorLibraryCursorVisualScale)} Z`"
                    class="subCategoryDesignEditor__floatingCursorArrow"
                  />
                  <path
                    :d="`M ${interiorLibraryCursorPoint.x + (22 * interiorLibraryCursorVisualScale)} ${interiorLibraryCursorPoint.y} L ${interiorLibraryCursorPoint.x + (15 * interiorLibraryCursorVisualScale)} ${interiorLibraryCursorPoint.y - (4 * interiorLibraryCursorVisualScale)} L ${interiorLibraryCursorPoint.x + (15 * interiorLibraryCursorVisualScale)} ${interiorLibraryCursorPoint.y + (4 * interiorLibraryCursorVisualScale)} Z`"
                    class="subCategoryDesignEditor__floatingCursorArrow"
                  />
                </g>
                <image
                  v-else-if="interiorLibraryCursorPoint && interiorLibraryOverlayCursorIcon"
                  :href="interiorLibraryOverlayCursorIcon"
                  :x="interiorLibraryCursorPoint.x - interiorLibraryOverlayCursorOffset.x"
                  :y="interiorLibraryCursorPoint.y - interiorLibraryOverlayCursorOffset.y"
                  :width="interiorLibraryOverlayCursorOffset.size"
                  :height="interiorLibraryOverlayCursorOffset.size"
                  class="subCategoryDesignEditor__overlayCursorImage"
                  preserveAspectRatio="xMidYMid meet"
                />
                <template v-if="interiorLibraryShowGuideAnnotations">
                  <line
                    v-for="guide in interiorLibraryRenderedAnnotations.guides"
                    :key="guide.id"
                    :x1="guide.screenStart.x"
                    :y1="guide.screenStart.y"
                    :x2="guide.screenEnd.x"
                    :y2="guide.screenEnd.y"
                    :stroke="guide.selected ? interiorLibraryAnnotationColors.selected : interiorLibraryAnnotationColors.guide"
                    :stroke-width="guide.selected ? 2.8 : 1.6"
                    stroke-linecap="round"
                    opacity="0.92"
                  />
                  <line
                    v-if="interiorLibraryRenderedAnnotations.draftGuide"
                    :x1="interiorLibraryRenderedAnnotations.draftGuide.screenStart.x"
                    :y1="interiorLibraryRenderedAnnotations.draftGuide.screenStart.y"
                    :x2="interiorLibraryRenderedAnnotations.draftGuide.screenEnd.x"
                    :y2="interiorLibraryRenderedAnnotations.draftGuide.screenEnd.y"
                    :stroke="interiorLibraryAnnotationColors.guide"
                    stroke-width="1.6"
                    stroke-linecap="round"
                    stroke-dasharray="8 6"
                    opacity="0.75"
                  />
                </template>
                <line
                  v-for="(line, index) in interiorLibraryPreviewSvgLines.outer"
                  :key="`interior-outer-${index}`"
                  :x1="line.x1"
                  :y1="line.y1"
                  :x2="line.x2"
                  :y2="line.y2"
                  :stroke-width="line.sw"
                  stroke="#4f4144"
                  stroke-linecap="round"
                />
                <template v-if="interiorLibraryShowInnerLines">
                  <line
                    v-for="(line, index) in interiorLibraryPreviewSvgLines.inner"
                    :key="`interior-design-inner-${index}`"
                    :x1="line.x1"
                    :y1="line.y1"
                    :x2="line.x2"
                    :y2="line.y2"
                    :stroke-width="line.sw"
                    stroke="#b9c3cd"
                    stroke-linecap="round"
                    stroke-dasharray="6 8"
                    opacity="0.82"
                  />
                </template>
                <g
                  v-for="instance in interiorLibraryPreviewInstances2d"
                  :key="`interior-instance-${instance.id}`"
                  class="subCategoryDesignEditor__instanceLayer"
                  :class="{
                    'is-hovered': String(interiorLibraryHoveredInstanceId || '') === String(instance.id || '') || String(interiorLibraryPickerPreviewInstanceId || '') === String(instance.id || ''),
                    'is-selected': String(interiorLibrarySelectedInstanceId || '') === String(instance.id || '')
                  }"
                >
                  <rect
                    :x="instance.boundsRect.x"
                    :y="instance.boundsRect.y"
                    :width="instance.boundsRect.w"
                    :height="instance.boundsRect.h"
                    class="subCategoryDesignEditor__instanceHitBox"
                  />
                  <line
                    v-for="(line, index) in instance.innerLines"
                    :key="`${instance.id}-inner-${index}`"
                    :x1="line.x1"
                    :y1="line.y1"
                    :x2="line.x2"
                    :y2="line.y2"
                    :stroke-width="String(interiorLibrarySelectedInstanceId || '') === String(instance.id || '') ? 1.8 : (String(interiorLibraryPickerPreviewInstanceId || '') === String(instance.id || '') ? Math.max(1.45, Number(line.sw) || 1.25) : Math.max(1.25, Number(line.sw) || 1.25))"
                    :stroke="instance.lineColor"
                    stroke-linecap="round"
                    stroke-dasharray="6 8"
                    :opacity="String(interiorLibrarySelectedInstanceId || '') === String(instance.id || '') ? 0.98 : (String(interiorLibraryPickerPreviewInstanceId || '') === String(instance.id || '') ? 0.98 : 0.94)"
                  />
                  <line
                    v-for="(line, index) in instance.outerLines"
                    :key="`${instance.id}-outer-${index}`"
                    :x1="line.x1"
                    :y1="line.y1"
                    :x2="line.x2"
                    :y2="line.y2"
                    :stroke="instance.lineColor"
                    :stroke-width="String(interiorLibrarySelectedInstanceId || '') === String(instance.id || '') ? 2.2 : ((String(interiorLibraryHoveredInstanceId || '') === String(instance.id || '') || String(interiorLibraryPickerPreviewInstanceId || '') === String(instance.id || '')) ? 1.4 : 0)"
                    stroke-linecap="round"
                    :opacity="String(interiorLibrarySelectedInstanceId || '') === String(instance.id || '') ? 0.92 : ((String(interiorLibraryHoveredInstanceId || '') === String(instance.id || '') || String(interiorLibraryPickerPreviewInstanceId || '') === String(instance.id || '')) ? 0.88 : 0.78)"
                  />
                </g>
                <template
                  v-for="overlay in interiorLibraryControllerOverlays"
                  :key="`interior-controller-rect-${overlay.instanceId}`"
                >
                  <g
                    v-if="String(interiorLibrarySelectedInstanceId || '') !== String(overlay.instanceId || '')"
                    class="subCategoryDesignEditor__controllerOverlay"
                  >
                    <rect
                      :x="overlay.rect.x"
                      :y="overlay.rect.y"
                      :width="overlay.rect.w"
                      :height="overlay.rect.h"
                      class="subCategoryDesignEditor__controllerRect"
                    />
                  </g>
                </template>
                <g
                  v-if="interiorLibraryControllerState.enabled && interiorLibraryControllerRect"
                  class="subCategoryDesignEditor__controllerOverlay is-selected"
                >
                  <rect
                    :x="interiorLibraryControllerRect.x"
                    :y="interiorLibraryControllerRect.y"
                    :width="interiorLibraryControllerRect.w"
                    :height="interiorLibraryControllerRect.h"
                    class="subCategoryDesignEditor__controllerRect"
                  />
                  <g
                    v-for="controller in interiorLibraryControllerVisuals"
                    :key="`interior-controller-${controller.id}`"
                    class="subCategoryDesignEditor__controllerHandle"
                    :class="{
                      'is-hovered': interiorLibraryHoveredControllerId === controller.id,
                      'is-editing': interiorLibraryControllerEditingId === controller.id,
                      'is-dragging': interiorLibraryControllerPointerState.mode === 'controller' && interiorLibraryControllerPointerState.controllerId === controller.id,
                    }"
                  >
                    <path
                      :d="controller.kind === 'horizontal'
                        ? buildInteriorControllerHorizontalArrowPath(controller.direction, controller.x, controller.y, controller.w, controller.h)
                        : buildInteriorControllerVerticalArrowPath(controller.direction, controller.x, controller.y, controller.w, controller.h)"
                      class="subCategoryDesignEditor__controllerBody"
                    />
                    <circle
                      v-for="(hotspot, hotspotIndex) in getInteriorControllerHotspots(controller)"
                      :key="`${controller.id}-hotspot-${hotspotIndex}`"
                      :cx="hotspot.x"
                      :cy="hotspot.y"
                      :r="hotspot.radius"
                      class="subCategoryDesignEditor__controllerHotspot"
                      @pointerdown="handleInteriorLibraryControllerPointerDown(controller.id, $event)"
                    />
                    <foreignObject
                      :x="controller.x + ((controller.w - controller.inputW) * 0.5)"
                      :y="controller.y + ((controller.h - controller.inputH) * 0.5)"
                      :width="controller.inputW"
                      :height="controller.inputH"
                    >
                      <div class="subCategoryDesignEditor__controllerValueShell" xmlns="http://www.w3.org/1999/xhtml">
                        <input
                          v-if="interiorLibraryControllerEditingId === controller.id"
                          :data-interior-controller-input="controller.id"
                          v-model="interiorLibraryControllerInputDraft"
                          class="subCategoryDesignEditor__controllerValueInput"
                          type="text"
                          dir="ltr"
                          @pointerdown="handleInteriorLibraryControllerValuePointerDown"
                          @keydown.enter.prevent="commitInteriorLibraryControllerEditing"
                          @keydown.esc.prevent="clearInteriorLibraryControllerEditing"
                          @blur="commitInteriorLibraryControllerEditing"
                        />
                        <button
                          v-else
                          type="button"
                          class="subCategoryDesignEditor__controllerValueButton"
                          :class="{ 'is-hovered': interiorLibraryHoveredControllerId === controller.id }"
                          @pointerdown="handleInteriorLibraryControllerValuePointerDown"
                          @click.stop="beginInteriorLibraryControllerEditing(controller.id)"
                        >
                          {{ formatInteriorControllerDisplayValue(interiorLibraryControllerParamValues[controller.id]) }}
                        </button>
                      </div>
                    </foreignObject>
                  </g>
                </g>
                <template v-if="interiorLibraryShowDimensions">
                  <g
                    v-for="dimension in interiorLibraryRenderedAnnotations.dimensions"
                    :key="dimension.id"
                    class="subCategoryDesignEditor__annotationDimension"
                  >
                    <line
                      :x1="dimension.extensionA.x1"
                      :y1="dimension.extensionA.y1"
                      :x2="dimension.extensionA.x2"
                      :y2="dimension.extensionA.y2"
                      :stroke="dimension.selected ? interiorLibraryAnnotationColors.selected : interiorLibraryAnnotationColors.dimension"
                      :stroke-width="dimension.selected ? 2.2 : 1.4"
                      stroke-linecap="round"
                      opacity="0.9"
                    />
                    <line
                      :x1="dimension.extensionB.x1"
                      :y1="dimension.extensionB.y1"
                      :x2="dimension.extensionB.x2"
                      :y2="dimension.extensionB.y2"
                      :stroke="dimension.selected ? interiorLibraryAnnotationColors.selected : interiorLibraryAnnotationColors.dimension"
                      :stroke-width="dimension.selected ? 2.2 : 1.4"
                      stroke-linecap="round"
                      opacity="0.9"
                    />
                    <line
                      :x1="dimension.screenStart.x"
                      :y1="dimension.screenStart.y"
                      :x2="dimension.screenEnd.x"
                      :y2="dimension.screenEnd.y"
                      :stroke="dimension.selected ? interiorLibraryAnnotationColors.selected : interiorLibraryAnnotationColors.dimension"
                      :stroke-width="dimension.selected ? 2.6 : 1.8"
                      stroke-linecap="round"
                    />
                    <line
                      :x1="dimension.tickA.x1"
                      :y1="dimension.tickA.y1"
                      :x2="dimension.tickA.x2"
                      :y2="dimension.tickA.y2"
                      :stroke="dimension.selected ? interiorLibraryAnnotationColors.selected : interiorLibraryAnnotationColors.dimension"
                      :stroke-width="dimension.selected ? 2.4 : 1.6"
                      stroke-linecap="round"
                    />
                    <line
                      :x1="dimension.tickB.x1"
                      :y1="dimension.tickB.y1"
                      :x2="dimension.tickB.x2"
                      :y2="dimension.tickB.y2"
                      :stroke="dimension.selected ? interiorLibraryAnnotationColors.selected : interiorLibraryAnnotationColors.dimension"
                      :stroke-width="dimension.selected ? 2.4 : 1.6"
                      stroke-linecap="round"
                    />
                    <text
                      :x="dimension.textX"
                      :y="dimension.textY"
                      class="subCategoryDesignEditor__annotationText"
                      :fill="dimension.selected ? interiorLibraryAnnotationColors.selected : interiorLibraryAnnotationColors.dimension"
                    >
                      {{ dimension.text }}
                    </text>
                  </g>
                  <g
                    v-if="interiorLibraryRenderedAnnotations.draftDimension"
                    class="subCategoryDesignEditor__annotationDimension subCategoryDesignEditor__annotationDimension--draft"
                    opacity="0.78"
                  >
                    <line
                      :x1="interiorLibraryRenderedAnnotations.draftDimension.extensionA.x1"
                      :y1="interiorLibraryRenderedAnnotations.draftDimension.extensionA.y1"
                      :x2="interiorLibraryRenderedAnnotations.draftDimension.extensionA.x2"
                      :y2="interiorLibraryRenderedAnnotations.draftDimension.extensionA.y2"
                      :stroke="interiorLibraryAnnotationColors.dimension"
                      stroke-width="1.4"
                      stroke-linecap="round"
                    />
                    <line
                      :x1="interiorLibraryRenderedAnnotations.draftDimension.extensionB.x1"
                      :y1="interiorLibraryRenderedAnnotations.draftDimension.extensionB.y1"
                      :x2="interiorLibraryRenderedAnnotations.draftDimension.extensionB.x2"
                      :y2="interiorLibraryRenderedAnnotations.draftDimension.extensionB.y2"
                      :stroke="interiorLibraryAnnotationColors.dimension"
                      stroke-width="1.4"
                      stroke-linecap="round"
                    />
                    <line
                      :x1="interiorLibraryRenderedAnnotations.draftDimension.screenStart.x"
                      :y1="interiorLibraryRenderedAnnotations.draftDimension.screenStart.y"
                      :x2="interiorLibraryRenderedAnnotations.draftDimension.screenEnd.x"
                      :y2="interiorLibraryRenderedAnnotations.draftDimension.screenEnd.y"
                      :stroke="interiorLibraryAnnotationColors.dimension"
                      stroke-width="1.8"
                      stroke-linecap="round"
                      stroke-dasharray="8 6"
                    />
                    <line
                      :x1="interiorLibraryRenderedAnnotations.draftDimension.tickA.x1"
                      :y1="interiorLibraryRenderedAnnotations.draftDimension.tickA.y1"
                      :x2="interiorLibraryRenderedAnnotations.draftDimension.tickA.x2"
                      :y2="interiorLibraryRenderedAnnotations.draftDimension.tickA.y2"
                      :stroke="interiorLibraryAnnotationColors.dimension"
                      stroke-width="1.6"
                      stroke-linecap="round"
                    />
                    <line
                      :x1="interiorLibraryRenderedAnnotations.draftDimension.tickB.x1"
                      :y1="interiorLibraryRenderedAnnotations.draftDimension.tickB.y1"
                      :x2="interiorLibraryRenderedAnnotations.draftDimension.tickB.x2"
                      :y2="interiorLibraryRenderedAnnotations.draftDimension.tickB.y2"
                      :stroke="interiorLibraryAnnotationColors.dimension"
                      stroke-width="1.6"
                      stroke-linecap="round"
                    />
                    <text
                      :x="interiorLibraryRenderedAnnotations.draftDimension.textX"
                      :y="interiorLibraryRenderedAnnotations.draftDimension.textY"
                      class="subCategoryDesignEditor__annotationText"
                      :fill="interiorLibraryAnnotationColors.dimension"
                    >
                      {{ interiorLibraryRenderedAnnotations.draftDimension.text }}
                    </text>
                  </g>
                </template>
              </svg>
              <div
                v-if="interiorLibraryPreviewMode === 'model3d' && interiorLibraryModelCursorStyle"
                class="subCategoryDesignEditor__floatingCursor"
                :class="{ 'is-panning': interiorLibraryModelPanning }"
                :style="interiorLibraryModelCursorStyle"
                aria-hidden="true"
              >
                <svg viewBox="0 0 48 48" class="subCategoryDesignEditor__floatingCursorSvg">
                  <circle cx="24" cy="24" r="6" class="subCategoryDesignEditor__floatingCursorCenter" />
                  <line x1="24" y1="4" x2="24" y2="18" class="subCategoryDesignEditor__floatingCursorLine" />
                  <line x1="24" y1="30" x2="24" y2="44" class="subCategoryDesignEditor__floatingCursorLine" />
                  <line x1="4" y1="24" x2="18" y2="24" class="subCategoryDesignEditor__floatingCursorLine" />
                  <line x1="30" y1="24" x2="44" y2="24" class="subCategoryDesignEditor__floatingCursorLine" />
                  <path d="M24 2 L20 9 H28 Z" class="subCategoryDesignEditor__floatingCursorArrow" />
                  <path d="M24 46 L20 39 H28 Z" class="subCategoryDesignEditor__floatingCursorArrow" />
                  <path d="M2 24 L9 20 V28 Z" class="subCategoryDesignEditor__floatingCursorArrow" />
                  <path d="M46 24 L39 20 V28 Z" class="subCategoryDesignEditor__floatingCursorArrow" />
                </svg>
              </div>
              <div
                v-if="interiorLibraryOverlapPickerState.visible && interiorLibraryOverlapPickerState.items.length"
                class="subCategoryDesignEditor__overlapPicker"
                :style="getInteriorLibraryOverlapPickerStyle()"
                @pointerdown="onInteriorLibraryOverlapPickerPointerDown"
                @mouseleave="onInteriorLibraryOverlapPickerLeave"
              >
                <div class="subCategoryDesignEditor__overlapPickerTitle">آبجکت‌های روی‌هم</div>
                <button
                  v-for="item in interiorLibraryOverlapPickerState.items"
                  :key="`interior-overlap-${item.id}`"
                  type="button"
                  class="subCategoryDesignEditor__overlapPickerItem"
                  :class="{ 'is-active': String(interiorLibrarySelectedInstanceId || '') === String(item.id || '') }"
                  @mouseenter="setInteriorLibraryOverlapPreview(item.id)"
                  @focus="setInteriorLibraryOverlapPreview(item.id)"
                  @click="selectInteriorLibraryOverlapItem(item)"
                >
                  <span class="subCategoryDesignEditor__overlapPickerSwatch" :style="{ '--line-color': item.lineColor || '#7c3f57' }"></span>
                  <span class="subCategoryDesignEditor__overlapPickerText">
                    <span class="subCategoryDesignEditor__overlapPickerPrimary">{{ item.title }}</span>
                    <span v-if="item.instanceCode" class="subCategoryDesignEditor__overlapPickerSecondary">{{ item.instanceCode }}</span>
                  </span>
                </button>
              </div>
              <div v-if="!interiorLibraryPreviewSvgLines.outer.length" class="designMenu__cabinetState">
                {{ interiorLibraryPreviewMode === "model3d"
                  ? "برای این طرح هنوز preview سه بعدی قابل نمایش نیست."
                  : "برای این طرح هنوز preview خطی قابل نمایش نیست." }}
              </div>
              <div
                v-if="interiorLibraryPreviewMode === 'front2d' && interiorLibraryControllerTestMode && interiorLibraryControllerState.message"
                class="subCategoryDesignEditor__controllerHint"
              >
                {{ interiorLibraryControllerState.message }}
              </div>
            </div>
          </div>
        </div>

        <div class="subCategoryDesignEditor__panel subCategoryDesignEditor__panel--parts subCategoryDesignEditor__panel--interiorInstances">
          <div class="subCategoryDesignEditor__panelTitle">نمونه‌های داخلی این طرح</div>
          <div v-if="!activeInteriorLibraryTargetId" class="designMenu__cabinetState">برای افزودن نمونه داخلی، ابتدا یک طرح معتبر را باز یا انتخاب کنید.</div>
          <div v-else-if="!interiorLibraryInstanceCards.length" class="designMenu__cabinetState">هنوز هیچ گروه داخلی به این طرح اضافه نشده است.</div>
          <div v-else class="subCategoryDesignEditor__partList">
            <div
              v-for="item in interiorLibraryInstanceCards"
              :key="item.id"
              class="subCategoryDesignEditor__partItem subCategoryDesignEditor__partItem--interiorCard"
              :class="{ 'is-active': String(interiorLibrarySelectedInstanceId || '') === String(item.id || '') }"
              @click="selectInteriorLibraryInstance(item.id)"
            >
              <div class="subCategoryDesignEditor__interiorGroupHead">
                <span class="subCategoryDesignEditor__partMeta" dir="rtl">
                  <span class="subCategoryDesignEditor__partTitle">{{ item.groupTitle }}</span>
                  <span class="subCategoryDesignEditor__partCode">{{ item.instance_code }}</span>
                </span>
                <div class="subCategoryDesignEditor__interiorGroupActions">
                  <button
                    type="button"
                    class="constructionDialog__iconBtn"
                    title="حذف نمونه"
                    @click="deleteInteriorInstanceFromDesign(item)"
                  >
                    ×
                  </button>
                  <button
                    type="button"
                    class="subCategoryDesignEditor__settingsBtn subCategoryDesignEditor__settingsBtn--mini"
                    title="تنظیمات این نمونه"
                    @click="openInteriorInstanceEditor(item)"
                  >
                    <img src="/icons/setting.png" alt="" class="subCategoryDesignEditor__metaIcon" />
                  </button>
                  <label class="subCategoryDesignEditor__miniColorBtn" :style="{ '--line-color': item.lineColor }" :title="`رنگ خطوط ${item.instance_code}`">
                    <input
                      :value="item.lineColor"
                      class="subCategoryDesignEditor__miniColorInput"
                      type="color"
                      @input="previewInteriorInstanceLineColor(item, $event.target.value)"
                      @change="applyInteriorInstanceLineColor(item, $event.target.value)"
                    />
                  </label>
                  <span class="constructionDialog__pill subCategoryDesignEditor__orderPill">{{ toPersianDigits((Number(item.ui_order) || 0) + 1) }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>

        <div class="subCategoryDesignEditor__panel subCategoryDesignEditor__panel--parts subCategoryDesignEditor__panel--interiorSidebar">
          <div class="subCategoryDesignEditor__panelTitle">گروه‌های قطعات داخلی</div>
          <div v-if="constructionLoading" class="constructionDialog__loading">در حال خواندن گروه‌های داخلی...</div>
          <div v-else-if="!interiorLibraryGroupCards.length" class="designMenu__cabinetState">هنوز گروه قطعات داخلی برای استفاده ثبت نشده است.</div>
          <div v-else class="subCategoryDesignEditor__partList">
            <div v-for="item in interiorLibraryGroupCards" :key="item.id" class="subCategoryDesignEditor__partItem subCategoryDesignEditor__partItem--interiorCard">
              <div class="subCategoryDesignEditor__interiorGroupHead">
                <span class="subCategoryDesignEditor__partMeta" dir="rtl">
                  <span class="subCategoryDesignEditor__partTitle">{{ item.group_title }}</span>
                  <span class="subCategoryDesignEditor__partCode">{{ item.code }}</span>
                </span>
                <div class="subCategoryDesignEditor__interiorGroupActions">
                  <button
                    type="button"
                    class="constructionDialog__textBtn constructionDialog__textBtn--compact"
                    title="افزودن به طرح"
                    :disabled="isAddingInteriorGroup(item)"
                    @click="addInteriorGroupToDesign(item)"
                  >
                    <span v-if="isAddingInteriorGroup(item)" class="constructionDialog__spinner"></span>
                    <span>{{ isAddingInteriorGroup(item) ? "در حال افزودن..." : "افزودن" }}</span>
                  </button>
                  <span class="constructionDialog__pill">{{ toPersianDigits(item.parts?.length || 0) }} قطعه</span>
                  <label class="subCategoryDesignEditor__miniColorBtn subCategoryDesignEditor__miniColorBtn--static" :style="{ '--line-color': item.lineColor }" :title="`رنگ پیش‌فرض خطوط ${item.group_title}`">
                    <span class="subCategoryDesignEditor__miniColorPreview" aria-hidden="true"></span>
                  </label>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>

      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" @click="closeInteriorLibrary">بستن</button>
      </div>
    </div>
  </div>

  <div v-if="interiorInstanceEditorOpen && interiorInstanceEditorDraft" class="appDialog appDialog--stacked" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeInteriorInstanceEditor"></div>
    <div class="appDialog__card appDialog__card--subPreview" dir="rtl">
      <div class="subCategoryPreview__header">
        <div>
          <div class="subCategoryPreview__title">تنظیمات نمونه داخلی</div>
          <div class="subCategoryPreview__caption">
            {{ constructionInternalPartGroupsById.get(String(interiorInstanceEditorDraft.internal_part_group_id))?.group_title || interiorInstanceEditorDraft.instance_code }}
          </div>
        </div>
        <button type="button" class="constructionDialog__textBtn" @click="closeInteriorInstanceEditor">بستن</button>
      </div>
      <div class="subCategoryDesignEditor__meta subCategoryDesignEditor__meta--interiorInstance">
        <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--wide">
          <span>کد نمونه</span>
          <input v-model="interiorInstanceEditorDraft.instance_code" class="constructionDialog__input constructionDialog__input--mono" type="text" />
        </label>
        <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--compact">
          <span>ترتیب</span>
          <input v-model.number="interiorInstanceEditorDraft.ui_order" class="constructionDialog__input" type="number" min="0" step="1" />
        </label>
        <label class="subCategoryDesignEditor__field subCategoryDesignEditor__field--wide">
          <span>رنگ خطوط این نمونه</span>
          <div class="constructionDialog__colorEditor">
            <input
              v-model="interiorInstanceEditorDraft.line_color"
              class="constructionDialog__colorInput"
              type="color"
              @input="interiorInstanceEditorDraft.line_color = normalizeHexColor(interiorInstanceEditorDraft.line_color, DEFAULT_INTERIOR_LINE_COLOR)"
            />
            <input
              v-model="interiorInstanceEditorDraft.line_color"
              class="constructionDialog__input constructionDialog__input--mono constructionDialog__colorHex"
              type="text"
              dir="ltr"
              maxlength="7"
              :placeholder="resolveInteriorInstanceLineColor(interiorInstanceEditorDraft)"
              @change="interiorInstanceEditorDraft.line_color = normalizeHexColor(interiorInstanceEditorDraft.line_color, DEFAULT_INTERIOR_LINE_COLOR)"
            />
          </div>
        </label>
      </div>
      <div class="constructionDialog__sectionHint">
        تغییرات این پنجره فقط روی همین نمونه داخلی اعمال می‌شود و روی پیش‌فرض گروه مادر اثری ندارد.
      </div>
      <div class="subCategoryPreview__body">
        <div class="subCategoryPreview__tree">
          <div class="subCategoryPreview__panel subCategoryPreview__panel--groups">
            <div class="subCategoryPreview__selectorList">
              <button
                v-for="group in activeInteriorInstanceEditorGroups"
                :key="group.id"
                type="button"
                class="subCategoryPreview__groupHead"
                :class="{ 'is-active': String(activeInteriorInstanceEditorGroup?.id || '') === String(group.id) }"
                @click="selectInteriorInstanceEditorGroup(group.id)"
              >
                <div class="subCategoryPreview__groupMeta">
                  <div class="subCategoryPreview__groupTitle">{{ group.title }}</div>
                  <div class="subCategoryPreview__groupCaption">{{ toPersianDigits(group.items.length) }} پارامتر</div>
                </div>
                <div class="subCategoryPreview__groupBadge" :class="{ 'is-empty': !group.iconUrl }">
                  <img
                    v-if="group.iconUrl"
                    :key="group.iconUrl"
                    :src="group.iconUrl"
                    :alt="group.title"
                    class="subCategoryPreview__groupIcon"
                    @error="handleSubCategoryDefaultIconError"
                  />
                  <span v-else class="subCategoryPreview__groupFallback">{{ toPersianDigits(group.items.length) }}</span>
                </div>
                <span class="subCategoryPreview__groupChevron" aria-hidden="true">‹</span>
              </button>
            </div>
          </div>
          <div class="subCategoryPreview__panel subCategoryPreview__panel--params">
            <div v-if="activeInteriorInstanceEditorGroup" class="subCategoryPreview__panelHead">
              <div class="subCategoryPreview__panelTitle">{{ activeInteriorInstanceEditorGroup.title }}</div>
              <div class="subCategoryPreview__panelCaption">{{ toPersianDigits(activeInteriorInstanceEditorGroup.items.length) }} پارامتر در این گروه</div>
            </div>
            <div v-if="activeInteriorInstanceEditorGroup" class="subCategoryPreview__params">
              <article v-for="column in activeInteriorInstanceEditorGroup.items" :key="column.key" class="subCategoryPreview__paramCard">
                <template v-if="column.inputMode === 'binary'">
                  <div class="subCategoryPreview__paramMeta">
                    <div class="subCategoryPreview__paramTitle">{{ column.displayTitle }}</div>
                    <div v-if="column.descriptionText" class="subCategoryPreview__paramDescription">{{ column.descriptionText }}</div>
                  </div>
                  <div class="subCategoryPreview__binaryChoices">
                    <button
                      type="button"
                      class="subCategoryPreview__binaryChoice"
                      :class="{ 'is-active': String(interiorInstanceEditorDraft.param_values?.[column.key] ?? '0') !== '1' }"
                      @click="setInteriorInstanceBinaryValue(column.key, '0')"
                    >
                      <img :src="column.binaryOffIconUrl" :alt="column.binaryOffLabel" class="subCategoryPreview__binaryIcon" @error="handleSubCategoryDefaultIconError" />
                      <span class="subCategoryPreview__binaryLabel">{{ column.binaryOffLabel }}</span>
                    </button>
                    <button
                      type="button"
                      class="subCategoryPreview__binaryChoice"
                      :class="{ 'is-active': String(interiorInstanceEditorDraft.param_values?.[column.key] ?? '0') === '1' }"
                      @click="setInteriorInstanceBinaryValue(column.key, '1')"
                    >
                      <img :src="column.binaryOnIconUrl" :alt="column.binaryOnLabel" class="subCategoryPreview__binaryIcon" @error="handleSubCategoryDefaultIconError" />
                      <span class="subCategoryPreview__binaryLabel">{{ column.binaryOnLabel }}</span>
                    </button>
                  </div>
                </template>
                <template v-else>
                  <div class="subCategoryPreview__valueHead">
                    <div class="subCategoryPreview__valueIconBox">
                      <img :src="column.iconUrl" :alt="column.displayTitle" class="subCategoryPreview__valueIcon" @error="handleSubCategoryDefaultIconError" />
                    </div>
                    <div class="subCategoryPreview__paramMeta">
                      <div class="subCategoryPreview__paramTitle">{{ column.displayTitle }}</div>
                      <div v-if="column.descriptionText" class="subCategoryPreview__paramDescription">{{ column.descriptionText }}</div>
                    </div>
                  </div>
                  <input
                    v-model="interiorInstanceEditorDraft.param_values[column.key]"
                    class="constructionDialog__input subCategoryPreview__valueInput"
                    type="number"
                    inputmode="numeric"
                    min="0"
                    :placeholder="column.displayTitle"
                  />
                  <div class="subCategoryPreview__valueUnit">میلی‌متر</div>
                </template>
              </article>
            </div>
            <div v-else class="designMenu__cabinetState">برای این نمونه هنوز پارامتری قابل نمایش نیست.</div>
          </div>
        </div>
      </div>
      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" :disabled="interiorInstanceEditorApplying" @click="closeInteriorInstanceEditor">انصراف</button>
        <button type="button" class="constructionDialog__textBtn is-primary" :disabled="interiorInstanceEditorApplying" @click="applyInteriorInstanceEditor">
          <span v-if="interiorInstanceEditorApplying" class="constructionDialog__spinner"></span>
          <span>{{ interiorInstanceEditorApplying ? "در حال اعمال..." : "اعمال" }}</span>
        </button>
      </div>
    </div>
  </div>

  <div v-if="baseFormulaBuilderOpen" class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeBaseFormulaBuilder"></div>
    <div class="appDialog__card appDialog__card--builder" dir="rtl">
      <div class="formulaBuilder__head">
        <div class="constructionDialog__sectionTitle formulaBuilder__title">{{ formulaBuilderDialogTitle }}</div>
        <button type="button" class="constructionDialog__close formulaBuilder__close" title="بستن" @click="closeBaseFormulaBuilder">×</button>
      </div>
      <div class="constructionDialog__sectionHint">{{ formulaBuilderHintText }}</div>

      <div v-if="baseFormulaBuilderDraft" class="formulaBuilder">
        <div v-if="baseFormulaBuilderEntity === 'base_formulas'" class="formulaBuilder__meta">
          <label class="formulaBuilder__field">
            <span>شناسه</span>
            <input v-model.number="baseFormulaBuilderDraft.fo_id" class="constructionDialog__input" type="number" min="1" step="1" />
          </label>
          <label class="formulaBuilder__field">
            <span>کد فرمول</span>
            <input v-model="baseFormulaBuilderDraft.param_formula" class="constructionDialog__input constructionDialog__input--mono" type="text" />
          </label>
          <div class="formulaBuilder__field">
            <span>نوع رکورد</span>
            <button type="button" class="constructionDialog__scopeBtn" :class="baseFormulaBuilderDraft.admin_id === null ? 'is-system' : 'is-admin'" @click="baseFormulaBuilderDraft.admin_id = baseFormulaBuilderDraft.admin_id === null ? currentAdminId : null">
              {{ baseFormulaBuilderDraft.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
            </button>
          </div>
        </div>

        <div v-else class="formulaBuilder__meta formulaBuilder__meta--part">
          <label class="formulaBuilder__field">
            <span>شناسه</span>
            <input v-model.number="baseFormulaBuilderDraft.part_formula_id" class="constructionDialog__input" type="number" min="1" step="1" />
          </label>
          <label class="formulaBuilder__field">
            <span>نوع قطعه</span>
            <select v-model.number="baseFormulaBuilderDraft.part_kind_id" class="constructionDialog__input">
              <option v-for="option in constructionPartKindOptions" :key="option.value" :value="option.value">{{ option.label }}</option>
            </select>
          </label>
          <label class="formulaBuilder__field">
            <span>داخلی</span>
            <button
              type="button"
              class="constructionDialog__scopeBtn"
              :class="getConstructionPartKindInternalLabel(baseFormulaBuilderDraft.part_kind_id) === 'داخلی' ? 'is-admin' : 'is-system'"
              @click="toggleConstructionPartKindInternalById(baseFormulaBuilderDraft.part_kind_id)"
            >
              {{ getConstructionPartKindInternalLabel(baseFormulaBuilderDraft.part_kind_id) }}
            </button>
          </label>
          <label class="formulaBuilder__field">
            <span>زیرنوع</span>
            <input v-model.number="baseFormulaBuilderDraft.part_sub_kind_id" class="constructionDialog__input" type="number" min="1" step="1" />
          </label>
          <label class="formulaBuilder__field">
            <span>کد قطعه</span>
            <input v-model="baseFormulaBuilderDraft.part_code" class="constructionDialog__input constructionDialog__input--mono" type="text" />
          </label>
          <label class="formulaBuilder__field">
            <span>عنوان قطعه</span>
            <input v-model="baseFormulaBuilderDraft.part_title" class="constructionDialog__input" type="text" />
          </label>
          <label class="formulaBuilder__field">
            <span>فیلد فرمول</span>
            <select
              v-model="baseFormulaBuilderTargetField"
              class="constructionDialog__input"
              @change="syncBaseFormulaBuilderFromFormulaText({ silent: true })"
            >
              <option v-for="field in formulaBuilderFieldOptions" :key="field.key" :value="field.key">{{ field.label }}</option>
            </select>
          </label>
          <div class="formulaBuilder__field">
            <span>نوع رکورد</span>
            <button type="button" class="constructionDialog__scopeBtn" :class="baseFormulaBuilderDraft.admin_id === null ? 'is-system' : 'is-admin'" @click="baseFormulaBuilderDraft.admin_id = baseFormulaBuilderDraft.admin_id === null ? currentAdminId : null">
              {{ baseFormulaBuilderDraft.admin_id === null ? "پیش‌فرض" : "اختصاصی ادمین" }}
            </button>
          </div>
        </div>

        <div class="formulaBuilder__toolbar">
          <div class="formulaBuilder__operators">
            <button v-for="token in ['(', ')', '+', '-', '*', '/']" :key="token" type="button" class="constructionDialog__miniBtn formulaBuilder__tokenBtn" @click="appendBaseFormulaToken(token === '(' || token === ')' ? 'paren' : 'operator', token)">
              {{ token }}
            </button>
          </div>
          <div class="formulaBuilder__picker">
            <select class="constructionDialog__input" @change="($event) => { if ($event.target.value) { appendBaseFormulaToken('identifier', $event.target.value); $event.target.value = ''; } }">
              <option value="">{{ baseFormulaBuilderEntity === 'part_formulas' ? 'افزودن کد پارامتر یا فرمول پایه' : 'افزودن پارامتر' }}</option>
              <option v-for="item in formulaBuilderAvailableIdentifiers" :key="`${item.kind}-${item.value}`" :value="item.value">{{ item.label }}</option>
            </select>
          </div>
          <div class="formulaBuilder__numberBox">
            <input
              :value="baseFormulaBuilderNumberInput"
              class="constructionDialog__input constructionDialog__input--mono"
              type="text"
              inputmode="decimal"
              placeholder="عدد ثابت، اعشاری یا منفی"
              @input="baseFormulaBuilderNumberInput = normalizeBaseFormulaNumberInput($event.target.value)"
            />
            <button type="button" class="constructionDialog__textBtn" :disabled="!isFormulaNumberToken(baseFormulaBuilderNumberInput)" @click="addBaseFormulaBuilderNumber">افزودن عدد</button>
          </div>
          <div class="formulaBuilder__actions">
            <button type="button" class="constructionDialog__textBtn" :disabled="!baseFormulaBuilderTokens.length" @click="removeLastBaseFormulaToken">حذف آخرین</button>
            <button type="button" class="constructionDialog__textBtn" :disabled="!baseFormulaBuilderTokens.length && !baseFormulaBuilderDraft[baseFormulaBuilderTargetField]" @click="clearBaseFormulaTokens">پاک‌سازی</button>
          </div>
        </div>

        <div v-if="baseFormulaBuilderTokens.length" class="formulaBuilder__tokens">
          <span v-for="(token, index) in baseFormulaBuilderTokens" :key="`${token.value}-${index}`" class="formulaBuilder__token">
            {{ token.value }}
          </span>
        </div>
        <div v-if="baseFormulaBuilderSyncWarning" class="formulaBuilder__warning">{{ baseFormulaBuilderSyncWarning }}</div>
        <div class="formulaBuilder__preview">{{ baseFormulaBuilderDraft[baseFormulaBuilderTargetField] || `${formulaBuilderCurrentFieldLabel} هنوز ساخته نشده است.` }}</div>
        <textarea
          v-model="baseFormulaBuilderDraft[baseFormulaBuilderTargetField]"
          class="constructionDialog__input constructionDialog__input--mono constructionDialog__textarea formulaBuilder__textarea"
          rows="4"
          readonly
        ></textarea>
        <div v-if="baseFormulaBuilderValidationErrors.length" class="formulaBuilder__errors">
          <div v-for="error in baseFormulaBuilderValidationErrors" :key="error" class="formulaBuilder__error">{{ error }}</div>
        </div>
      </div>

      <div class="appDialog__actions">
        <button type="button" class="menuItem" @click="closeBaseFormulaBuilder">انصراف</button>
        <button type="button" class="menuItem" :disabled="isBaseFormulaBuilderApplyDisabled" @click="applyBaseFormulaBuilder">اعمال</button>
      </div>
    </div>
  </div>

  <div v-if="subCategoryDefaultsEditorOpen" class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeSubCategoryDefaultsEditor"></div>
    <div class="appDialog__card appDialog__card--subDefaults" dir="rtl">
      <input
        ref="subCategoryDefaultIconInputEl"
        class="constructionDialog__fileInput"
        type="file"
        accept=".png,.jpg,.jpeg,.webp"
        @change="onSubCategoryDefaultIconFileChange"
      />
      <div class="formulaBuilder__head">
        <div class="constructionDialog__sectionTitle formulaBuilder__title">تنظیمات ساب‌کت</div>
        <button type="button" class="constructionDialog__close formulaBuilder__close" title="بستن" @click="closeSubCategoryDefaultsEditor">×</button>
      </div>
      <div class="constructionDialog__sectionHint">
        {{ activeSubCategoryDefaultsRow?.sub_cat_title || "ساب‌کت" }} -
        {{ activeSubCategoryDefaultsRow ? `${toPersianDigits(activeSubCategoryDefaultsRow.temp_id)} / ${toPersianDigits(activeSubCategoryDefaultsRow.cat_id)} / ${toPersianDigits(activeSubCategoryDefaultsRow.sub_cat_id)}` : "" }}
      </div>
      <div class="constructionDialog__sectionHint">
        در این بخش نام، توضیح، آیکون و نوع هر پارامتر را تعیین می‌کنید. تغییر مقدار پیش‌فرض از پنجره پیش‌فرض سریع انجام می‌شود و همان‌جا روی همین تنظیمات اعمال می‌گردد.
      </div>
      <div class="subCategoryDefaults__summary">
        <span class="constructionDialog__pill">مقداردهی‌شده: {{ toPersianDigits(activeSubCategoryDefaultsCount) }}</span>
        <span class="constructionDialog__pill">کل پارامترها: {{ toPersianDigits(constructionSubCategoryParamColumns.length) }}</span>
      </div>
      <div class="subCategoryDefaults__tree">
        <div class="subCategoryDefaults__panel subCategoryDefaults__panel--groups">
          <div class="subCategoryDefaults__selectorList">
            <button
              v-for="group in constructionSubCategoryParamTree"
              :key="group.id"
              type="button"
              class="subCategoryDefaults__groupHead"
              :class="{ 'is-active': String(activeSubCategoryDefaultsGroup?.id || '') === String(group.id) }"
              @click="selectSubCategoryDefaultsGroup(group.id)"
            >
              <div class="subCategoryDefaults__groupMeta">
                <div class="subCategoryDefaults__groupTitle">{{ group.title }}</div>
                <div class="subCategoryDefaults__groupCaption">
                  {{ toPersianDigits(group.items.length) }} پارامتر
                </div>
              </div>
              <div class="subCategoryDefaults__groupBadge" :class="{ 'is-empty': !group.iconUrl }">
                <img
                  v-if="group.iconUrl"
                  :key="group.iconUrl"
                  :src="group.iconUrl"
                  :alt="group.title"
                  class="subCategoryDefaults__groupIcon"
                  @error="handleSubCategoryDefaultIconError"
                />
                <span v-else class="subCategoryDefaults__groupFallback">{{ toPersianDigits(group.items.length) }}</span>
              </div>
              <span class="subCategoryDefaults__groupChevron" aria-hidden="true">‹</span>
            </button>
          </div>
        </div>
        <div class="subCategoryDefaults__panel subCategoryDefaults__panel--params">
          <div v-if="activeSubCategoryDefaultsGroup" class="subCategoryDefaults__panelHead">
            <div class="subCategoryDefaults__panelTitle">{{ activeSubCategoryDefaultsGroup.title }}</div>
            <div class="subCategoryDefaults__panelCaption">
              {{ toPersianDigits(activeSubCategoryDefaultsGroup.items.length) }} پارامتر در این گروه
            </div>
          </div>
          <div v-if="activeSubCategoryDefaultsGroup" class="subCategoryDefaults__branch">
            <div v-for="column in activeSubCategoryDefaultsGroup.items" :key="column.key" class="subCategoryDefaults__node">
              <div class="subCategoryDefaults__nodeLayout">
                <div class="subCategoryDefaults__nodeBody">
                  <div class="subCategoryDefaults__nodeHead">
                    <div class="subCategoryDefaults__nodeIdentity">
                      <span class="subCategoryDefaults__code">{{ column.key }}</span>
                      <input
                        v-model="subCategoryDefaultsEditorOverridesDraft[column.key].display_title"
                        class="constructionDialog__input subCategoryDefaults__titleInput"
                        type="text"
                        :placeholder="column.label || column.key"
                      />
                    </div>
                    <div class="subCategoryDefaults__nodeMedia">
                      <button
                        type="button"
                        class="subCategoryDefaults__nodeIconBox subCategoryDefaults__iconTrigger"
                        :class="[subCategoryDefaultsEditorOverridesDraft[column.key]?.icon_path ? 'is-filled' : 'is-empty', isUploadingSubCategoryDefaultIcon(column.key, 'icon_path') ? 'is-loading' : '']"
                        :title="getSubCategoryDefaultIconTooltip(column.key, 'icon_path')"
                        :disabled="isUploadingSubCategoryDefaultIcon(column.key, 'icon_path')"
                        @click.prevent="triggerSubCategoryDefaultIconUpload(column.key, 'icon_path')"
                      >
                        <span v-if="isUploadingSubCategoryDefaultIcon(column.key, 'icon_path')" class="constructionDialog__spinner"></span>
                        <img
                          v-else
                          :key="getSubCategoryDefaultPreviewUrl(column.key, subCategoryDefaultsEditorOverridesDraft[column.key]?.icon_path, 'icon_path')"
                          :src="getSubCategoryDefaultPreviewUrl(column.key, subCategoryDefaultsEditorOverridesDraft[column.key]?.icon_path, 'icon_path')"
                          :alt="subCategoryDefaultsEditorOverridesDraft[column.key]?.display_title || column.label || column.key"
                          class="subCategoryDefaults__nodeIcon"
                          @error="handleSubCategoryDefaultIconError"
                        />
                      </button>
                    </div>
                  </div>
                  <textarea
                    v-model="subCategoryDefaultsEditorOverridesDraft[column.key].description_text"
                    class="constructionDialog__input constructionDialog__textarea subCategoryDefaults__textarea"
                    rows="1"
                    placeholder="توضیح این پارامتر را برای همین ساب‌کت بنویسید"
                  ></textarea>
                  <div class="subCategoryDefaults__settingsRow">
                    <div class="subCategoryDefaults__modeWrap">
                      <span class="subCategoryDefaults__valueLabel">نوع</span>
                      <div class="subCategoryDefaults__modeSwitch">
                        <button
                          type="button"
                          class="subCategoryDefaults__modeBtn"
                          :class="{ 'is-active': subCategoryDefaultsEditorOverridesDraft[column.key].input_mode === 'value' }"
                          @click.prevent="setSubCategoryDefaultInputMode(column.key, 'value')"
                        >
                          مقداری
                        </button>
                        <button
                          type="button"
                          class="subCategoryDefaults__modeBtn"
                          :class="{ 'is-active': subCategoryDefaultsEditorOverridesDraft[column.key].input_mode === 'binary' }"
                          @click.prevent="setSubCategoryDefaultInputMode(column.key, 'binary')"
                        >
                          دو گزینه‌ای
                        </button>
                      </div>
                    </div>
                    <div class="subCategoryDefaults__valueWrap">
                      <span class="subCategoryDefaults__valueLabel">مقدار پیش‌فرض</span>
                      <div class="subCategoryDefaults__valueControl">
                        <input
                          v-if="subCategoryDefaultsEditorOverridesDraft[column.key].input_mode !== 'binary'"
                          v-model="subCategoryDefaultsEditorDraft[column.key]"
                          class="constructionDialog__input subCategoryDefaults__input"
                          type="text"
                        />
                        <div v-else class="subCategoryDefaults__binaryToggle">
                          <button
                            type="button"
                            class="subCategoryDefaults__binaryBtn"
                            :class="{ 'is-active': String(subCategoryDefaultsEditorDraft[column.key] ?? '0') !== '1' }"
                            @click.prevent="setSubCategoryBinaryDefault(column.key, 0)"
                          >
                            ۰
                          </button>
                          <button
                            type="button"
                            class="subCategoryDefaults__binaryBtn"
                            :class="{ 'is-active': String(subCategoryDefaultsEditorDraft[column.key] ?? '0') === '1' }"
                            @click.prevent="setSubCategoryBinaryDefault(column.key, 1)"
                          >
                            ۱
                          </button>
                        </div>
                      </div>
                    </div>
                  </div>
                  <div v-if="subCategoryDefaultsEditorOverridesDraft[column.key].input_mode === 'binary'" class="subCategoryDefaults__binarySection">
                    <div class="subCategoryDefaults__binarySectionTitle">گزینه‌های انتخابی کاربر</div>
                    <div class="subCategoryDefaults__binaryLabels">
                      <div class="subCategoryDefaults__binaryOptionCard">
                        <div class="subCategoryDefaults__binaryOptionHead">
                          <span class="subCategoryDefaults__binaryOptionValue">گزینه 0</span>
                          <span class="subCategoryDefaults__binaryOptionCaption">متن و آیکون نمایش برای کاربر</span>
                        </div>
                        <div class="subCategoryDefaults__binaryOptionBody">
                          <button
                            type="button"
                            class="subCategoryDefaults__nodeIconBox subCategoryDefaults__nodeIconBox--binary subCategoryDefaults__iconTrigger"
                            :class="[subCategoryDefaultsEditorOverridesDraft[column.key]?.binary_off_icon_path ? 'is-filled' : 'is-empty', isUploadingSubCategoryDefaultIcon(column.key, 'binary_off_icon_path') ? 'is-loading' : '']"
                            :title="getSubCategoryDefaultIconTooltip(column.key, 'binary_off_icon_path')"
                            :disabled="isUploadingSubCategoryDefaultIcon(column.key, 'binary_off_icon_path')"
                            @click.prevent="triggerSubCategoryDefaultIconUpload(column.key, 'binary_off_icon_path')"
                          >
                            <span v-if="isUploadingSubCategoryDefaultIcon(column.key, 'binary_off_icon_path')" class="constructionDialog__spinner"></span>
                            <img
                              v-else
                              :key="getSubCategoryDefaultPreviewUrl(column.key, subCategoryDefaultsEditorOverridesDraft[column.key]?.binary_off_icon_path, 'binary_off_icon_path')"
                              :src="getSubCategoryDefaultPreviewUrl(column.key, subCategoryDefaultsEditorOverridesDraft[column.key]?.binary_off_icon_path, 'binary_off_icon_path')"
                              :alt="subCategoryDefaultsEditorOverridesDraft[column.key]?.binary_off_label || '0'"
                              class="subCategoryDefaults__nodeIcon subCategoryDefaults__nodeIcon--binary"
                              @error="handleSubCategoryDefaultIconError"
                            />
                          </button>
                          <div class="subCategoryDefaults__binaryTextWrap">
                            <span class="subCategoryDefaults__binaryInputLabel">متن گزینه 0</span>
                            <input
                              v-model="subCategoryDefaultsEditorOverridesDraft[column.key].binary_off_label"
                              class="constructionDialog__input subCategoryDefaults__binaryLabelInput"
                              type="text"
                              placeholder="متن نمایشی گزینه 0"
                            />
                          </div>
                        </div>
                      </div>
                      <div class="subCategoryDefaults__binaryOptionCard">
                        <div class="subCategoryDefaults__binaryOptionHead">
                          <span class="subCategoryDefaults__binaryOptionValue">گزینه 1</span>
                          <span class="subCategoryDefaults__binaryOptionCaption">متن و آیکون نمایش برای کاربر</span>
                        </div>
                        <div class="subCategoryDefaults__binaryOptionBody">
                          <button
                            type="button"
                            class="subCategoryDefaults__nodeIconBox subCategoryDefaults__nodeIconBox--binary subCategoryDefaults__iconTrigger"
                            :class="[subCategoryDefaultsEditorOverridesDraft[column.key]?.binary_on_icon_path ? 'is-filled' : 'is-empty', isUploadingSubCategoryDefaultIcon(column.key, 'binary_on_icon_path') ? 'is-loading' : '']"
                            :title="getSubCategoryDefaultIconTooltip(column.key, 'binary_on_icon_path')"
                            :disabled="isUploadingSubCategoryDefaultIcon(column.key, 'binary_on_icon_path')"
                            @click.prevent="triggerSubCategoryDefaultIconUpload(column.key, 'binary_on_icon_path')"
                          >
                            <span v-if="isUploadingSubCategoryDefaultIcon(column.key, 'binary_on_icon_path')" class="constructionDialog__spinner"></span>
                            <img
                              v-else
                              :key="getSubCategoryDefaultPreviewUrl(column.key, subCategoryDefaultsEditorOverridesDraft[column.key]?.binary_on_icon_path, 'binary_on_icon_path')"
                              :src="getSubCategoryDefaultPreviewUrl(column.key, subCategoryDefaultsEditorOverridesDraft[column.key]?.binary_on_icon_path, 'binary_on_icon_path')"
                              :alt="subCategoryDefaultsEditorOverridesDraft[column.key]?.binary_on_label || '1'"
                              class="subCategoryDefaults__nodeIcon subCategoryDefaults__nodeIcon--binary"
                              @error="handleSubCategoryDefaultIconError"
                            />
                          </button>
                          <div class="subCategoryDefaults__binaryTextWrap">
                            <span class="subCategoryDefaults__binaryInputLabel">متن گزینه 1</span>
                            <input
                              v-model="subCategoryDefaultsEditorOverridesDraft[column.key].binary_on_label"
                              class="constructionDialog__input subCategoryDefaults__binaryLabelInput"
                              type="text"
                              placeholder="متن نمایشی گزینه 1"
                            />
                          </div>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" @click="closeSubCategoryDefaultsEditor">انصراف</button>
        <button type="button" class="constructionDialog__textBtn is-primary" @click="applySubCategoryDefaultsEditor">اعمال</button>
      </div>
    </div>
  </div>

  <div v-if="subCategoryUserPreviewOpen" class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeSubCategoryUserPreview"></div>
    <div class="appDialog__card appDialog__card--subPreview" dir="rtl">
      <div class="subCategoryPreview__header">
        <div>
          <div class="subCategoryPreview__title">پیش‌فرض‌های ساب‌کت</div>
          <div class="subCategoryPreview__caption">
            {{ activeSubCategoryUserPreviewRow?.sub_cat_title || "ساب‌کت" }}
            <span v-if="activeSubCategoryUserPreviewRow">
              {{ `${toPersianDigits(activeSubCategoryUserPreviewRow.temp_id)} / ${toPersianDigits(activeSubCategoryUserPreviewRow.cat_id)} / ${toPersianDigits(activeSubCategoryUserPreviewRow.sub_cat_id)}` }}
            </span>
          </div>
        </div>
        <button type="button" class="constructionDialog__textBtn" @click="closeSubCategoryUserPreview">بستن</button>
      </div>
      <div class="constructionDialog__sectionHint">
        این بخش دسترسی سریع ادمین برای تغییر مقدار پیش‌فرض پارامترها است. هر تغییری که اینجا اعمال شود، مستقیم در تنظیمات همین ساب‌کت نیز دیده می‌شود.
      </div>
      <div class="subCategoryPreview__body">
        <div class="subCategoryPreview__tree">
          <div class="subCategoryPreview__panel subCategoryPreview__panel--groups">
            <div class="subCategoryPreview__selectorList">
              <button
                v-for="group in activeSubCategoryUserPreviewGroups"
                :key="group.id"
                type="button"
                class="subCategoryPreview__groupHead"
                :class="{ 'is-active': String(activeSubCategoryUserPreviewGroup?.id || '') === String(group.id) }"
                @click="selectSubCategoryUserPreviewGroup(group.id)"
              >
                <div class="subCategoryPreview__groupMeta">
                  <div class="subCategoryPreview__groupTitle">{{ group.title }}</div>
                  <div class="subCategoryPreview__groupCaption">{{ toPersianDigits(group.items.length) }} پارامتر</div>
                </div>
                <div class="subCategoryPreview__groupBadge" :class="{ 'is-empty': !group.iconUrl }">
                  <img
                    v-if="group.iconUrl"
                    :key="group.iconUrl"
                    :src="group.iconUrl"
                    :alt="group.title"
                    class="subCategoryPreview__groupIcon"
                    @error="handleSubCategoryDefaultIconError"
                  />
                  <span v-else class="subCategoryPreview__groupFallback">{{ toPersianDigits(group.items.length) }}</span>
                </div>
                <span class="subCategoryPreview__groupChevron" aria-hidden="true">‹</span>
              </button>
            </div>
          </div>
          <div class="subCategoryPreview__panel subCategoryPreview__panel--params">
            <div v-if="activeSubCategoryUserPreviewGroup" class="subCategoryPreview__panelHead">
              <div class="subCategoryPreview__panelTitle">{{ activeSubCategoryUserPreviewGroup.title }}</div>
              <div class="subCategoryPreview__panelCaption">{{ toPersianDigits(activeSubCategoryUserPreviewGroup.items.length) }} پارامتر در این گروه</div>
            </div>
            <div v-if="activeSubCategoryUserPreviewGroup" class="subCategoryPreview__params">
              <article v-for="column in activeSubCategoryUserPreviewGroup.items" :key="column.key" class="subCategoryPreview__paramCard">
              <template v-if="column.inputMode === 'binary'">
                <div class="subCategoryPreview__paramMeta">
                  <div class="subCategoryPreview__paramTitle">{{ column.displayTitle }}</div>
                  <div v-if="column.descriptionText" class="subCategoryPreview__paramDescription">{{ column.descriptionText }}</div>
                </div>
                <div class="subCategoryPreview__binaryChoices">
                  <button
                    type="button"
                    class="subCategoryPreview__binaryChoice"
                    :class="{ 'is-active': String(subCategoryUserPreviewValues[column.key] ?? '0') !== '1' }"
                    @click="setSubCategoryUserPreviewBinaryValue(column.key, '0')"
                  >
                    <img :src="column.binaryOffIconUrl" :alt="column.binaryOffLabel" class="subCategoryPreview__binaryIcon" @error="handleSubCategoryDefaultIconError" />
                    <span class="subCategoryPreview__binaryLabel">{{ column.binaryOffLabel }}</span>
                  </button>
                  <button
                    type="button"
                    class="subCategoryPreview__binaryChoice"
                    :class="{ 'is-active': String(subCategoryUserPreviewValues[column.key] ?? '0') === '1' }"
                    @click="setSubCategoryUserPreviewBinaryValue(column.key, '1')"
                  >
                    <img :src="column.binaryOnIconUrl" :alt="column.binaryOnLabel" class="subCategoryPreview__binaryIcon" @error="handleSubCategoryDefaultIconError" />
                    <span class="subCategoryPreview__binaryLabel">{{ column.binaryOnLabel }}</span>
                  </button>
                </div>
              </template>
              <template v-else>
                <div class="subCategoryPreview__valueHead">
                  <div class="subCategoryPreview__valueIconBox">
                    <img :src="column.iconUrl" :alt="column.displayTitle" class="subCategoryPreview__valueIcon" @error="handleSubCategoryDefaultIconError" />
                  </div>
                  <div class="subCategoryPreview__paramMeta">
                    <div class="subCategoryPreview__paramTitle">{{ column.displayTitle }}</div>
                    <div v-if="column.descriptionText" class="subCategoryPreview__paramDescription">{{ column.descriptionText }}</div>
                  </div>
                </div>
                <input
                  v-model="subCategoryUserPreviewValues[column.key]"
                  class="constructionDialog__input subCategoryPreview__valueInput"
                  type="number"
                  inputmode="numeric"
                  min="0"
                  :placeholder="column.displayTitle"
                />
                <div class="subCategoryPreview__valueUnit">میلی‌متر</div>
              </template>
              </article>
            </div>
          </div>
        </div>
      </div>
      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" @click="closeSubCategoryUserPreview">انصراف</button>
        <button type="button" class="constructionDialog__textBtn is-primary" @click="applySubCategoryUserPreview">اعمال</button>
      </div>
    </div>
  </div>

  <div v-if="orderEntryOpen" class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop"></div>
    <div class="appDialog__card appDialog__card--order" dir="rtl">
      <div class="orderEntry">
        <div class="orderEntry__head">
          <div>
            <div class="orderEntry__title">ورود از مسیر سفارش</div>
            <div class="orderEntry__subtitle">
              {{ isOrderDraftEditMode ? "سفارش فعال را ویرایش و آخرین تغییرات آن را ذخیره کنید." : "قبل از طراحی، یک سفارش بسازید یا یکی از سفارش‌های موجود را انتخاب کنید." }}
            </div>
          </div>
          <button v-if="activeOrder" type="button" class="menuPanel__close" title="بستن" @click="closeOrderEntry()">×</button>
        </div>

        <div class="orderEntry__tabs">
          <button type="button" class="orderEntry__tab" :class="{ 'is-active': orderEntryTab === 'create' }" @click="openOrderCreate('طرح جدید')">سفارش جدید</button>
          <button type="button" class="orderEntry__tab" :class="{ 'is-active': orderEntryTab === 'list' }" @click="orderEntryTab = 'list'">سفارش‌های موجود</button>
        </div>

        <div v-if="orderEntryTab === 'create'" class="orderEntry__body">
          <div class="orderEntry__grid">
            <label class="orderEntry__field">
              <span>نام سفارش</span>
              <input v-model="orderDraft.order_name" class="constructionDialog__input" type="text" placeholder="مثلاً آشپزخانه واحد ۳" />
            </label>
            <label class="orderEntry__field">
              <span>شماره سفارش</span>
              <input :value="orderEntryPreviewNumber" class="constructionDialog__input" type="text" readonly />
            </label>
            <label class="orderEntry__field">
              <span>وضعیت</span>
              <select v-model="orderDraft.status" class="constructionDialog__input">
                <option v-for="status in orderStatusOptions" :key="status.value" :value="status.value">{{ status.label }}</option>
              </select>
            </label>
            <label class="orderEntry__field">
              <span>ثبت‌کننده</span>
              <input :value="currentBootstrapUserName" class="constructionDialog__input" type="text" readonly />
            </label>
            <label class="orderEntry__field">
              <span>ادمین مالک</span>
              <input :value="currentAdminId" class="constructionDialog__input constructionDialog__input--mono" type="text" readonly />
            </label>
            <label class="orderEntry__field">
              <span>تاریخ ثبت</span>
              <input :value="orderEntryDisplayDate" class="constructionDialog__input" type="text" readonly />
            </label>
            <label class="orderEntry__field orderEntry__field--wide">
              <span>توضیح کوتاه</span>
              <textarea v-model="orderDraft.notes" class="constructionDialog__input orderEntry__textarea" rows="3" placeholder="توضیح کوتاه برای این سفارش"></textarea>
            </label>
          </div>
          <div class="orderEntry__actions">
            <button type="button" class="menuItem" :disabled="ordersSaving" @click="isOrderDraftEditMode ? updateOrder() : createOrder()">
              {{ orderEntrySubmitLabel }}
            </button>
          </div>
          <div v-if="isOrderDraftEditMode" class="constructionDialog__tableWrap" style="margin-top: 18px;">
            <div class="constructionDialog__sectionTitle" style="margin-bottom: 8px;">طرح‌های سفارش</div>
            <div v-if="orderDesignCatalogLoading" class="orderEntry__state">در حال خواندن طرح‌های سفارش...</div>
            <table v-else class="constructionDialog__table orderEntry__table">
              <thead>
                <tr>
                  <th class="constructionDialog__col constructionDialog__col--code">کد نمونه</th>
                  <th class="constructionDialog__col constructionDialog__col--code">کد طرح</th>
                  <th class="constructionDialog__col constructionDialog__col--title">عنوان</th>
                  <th class="constructionDialog__col constructionDialog__col--preview">پیش‌نمایش</th>
                  <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                </tr>
              </thead>
              <tbody>
                <tr
                  v-for="item in orderDesignCatalog"
                  :key="item.id"
                  class="orderEntry__designRow"
                  :class="{
                    'is-active': String(activeCabinetDesignId || '') === String(item.id),
                    'is-selected': selectedOrderDesignIds.includes(String(item.id)),
                  }"
                >
                  <td class="constructionDialog__col constructionDialog__col--code">{{ item.instance_code }}</td>
                  <td class="constructionDialog__col constructionDialog__col--code">{{ item.design_code }}</td>
                  <td class="constructionDialog__col constructionDialog__col--title">{{ item.design_title }}</td>
                  <td class="constructionDialog__col constructionDialog__col--preview">
                    <div v-if="item.viewer_boxes?.length" class="constructionDialog__previewThumb">
                      <GlbViewerWidget
                        src="/models/1_z1.glb"
                        :walls2d="{ nodes: [], walls: [], selection: { selectedWallId: null, selectedWallIds: [] }, state: {} }"
                        :placeholder-outline-color="normalizeHexColor(item.design_outline_color)"
                        :placeholder-boxes="item.viewer_boxes"
                        :display-unit="currentEditorDisplayUnit"
                        :show-attrs-panel="false"
                        :embedded="true"
                        :preview-only="true"
                        :preview-active="false"
                      />
                    </div>
                    <span v-else class="constructionDialog__previewEmpty">ندارد</span>
                  </td>
                  <td class="constructionDialog__col constructionDialog__col--actions">
                    <div class="constructionDialog__actionsCell" @click.stop>
                      <button type="button" class="constructionDialog__textBtn" @click="openOrderDesignEditor(item)">ویرایش</button>
                      <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteOrderDesign(item)">×</button>
                    </div>
                  </td>
                </tr>
                <tr v-if="!orderDesignCatalog.length">
                  <td class="constructionDialog__col constructionDialog__col--title" colspan="5">هنوز طرحی برای این سفارش ثبت نشده است. از پنل طراحی، طرح ساب‌کت را داخل صحنه رها کنید.</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>

        <div v-else class="orderEntry__body">
          <div v-if="ordersLoading" class="orderEntry__state">در حال خواندن سفارش‌ها...</div>
          <div v-else-if="ordersCatalog.length === 0" class="orderEntry__state">هنوز سفارشی ثبت نشده است.</div>
          <div v-else class="orderEntry__tableWrap">
            <table class="constructionDialog__table orderEntry__table">
              <thead>
                <tr>
                  <th class="constructionDialog__col constructionDialog__col--title">نام سفارش</th>
                  <th class="constructionDialog__col constructionDialog__col--code">شماره سفارش</th>
                  <th class="constructionDialog__col constructionDialog__col--scope">تاریخ ثبت</th>
                  <th class="constructionDialog__col constructionDialog__col--title">ثبت‌کننده</th>
                  <th class="constructionDialog__col constructionDialog__col--title">ادمین مالک</th>
                  <th class="constructionDialog__col constructionDialog__col--scope">وضعیت</th>
                  <th class="constructionDialog__col constructionDialog__col--actions">عملیات</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in ordersCatalog" :key="item.id">
                  <td class="constructionDialog__col constructionDialog__col--title">{{ item.order_name }}</td>
                  <td class="constructionDialog__col constructionDialog__col--code">{{ item.order_number }}</td>
                  <td class="constructionDialog__col constructionDialog__col--scope">{{ formatOrderDate(item.submitted_at) }}</td>
                  <td class="constructionDialog__col constructionDialog__col--title">{{ item.user_name }}</td>
                  <td class="constructionDialog__col constructionDialog__col--title">{{ item.admin_name }}</td>
                  <td class="constructionDialog__col constructionDialog__col--scope">
                    <span class="constructionDialog__scopeBtn is-admin">{{ orderStatusLabelMap[item.status] || item.status }}</span>
                  </td>
                  <td class="constructionDialog__col constructionDialog__col--actions">
                    <div class="constructionDialog__actionsCell">
                      <button type="button" class="constructionDialog__textBtn" :disabled="isActiveOrderHydrating" @click="selectOrder(item)">
                        {{ isActiveOrderHydrating ? "در حال بارگیری..." : "انتخاب" }}
                      </button>
                      <button type="button" class="constructionDialog__iconBtn" title="آرشیو" @click="archiveOrder(item)">×</button>
                    </div>
                  </td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      </div>
    </div>
  </div>

  <div v-if="isActiveOrderHydrating" class="orderHydrationOverlay" role="status" aria-live="polite" aria-busy="true">
    <div class="orderHydrationOverlay__card">
      <span class="orderHydrationOverlay__spinner" aria-hidden="true"></span>
      <div class="orderHydrationOverlay__title">در حال بارگیری کامل سفارش</div>
      <div class="orderHydrationOverlay__subtitle">
        {{ orderOpeningLabel ? `در حال دریافت ترسیمات و طرح های «${orderOpeningLabel}» از دیتابیس...` : "در حال دریافت ترسیمات و طرح های سفارش از دیتابیس..." }}
      </div>
    </div>
  </div>

  <div v-if="orderDesignEditorOpen" class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeOrderDesignEditor"></div>
    <div class="appDialog__card appDialog__card--order" dir="rtl">
      <div class="formulaBuilder__head">
        <div class="constructionDialog__sectionTitle formulaBuilder__title">ویرایش طرح سفارش</div>
        <button type="button" class="constructionDialog__close formulaBuilder__close" title="بستن" @click="closeOrderDesignEditor">×</button>
      </div>
      <div v-if="orderDesignEditorDraft" class="orderEntry__body">
        <div class="orderEntry__grid">
          <label class="orderEntry__field">
            <span>عنوان</span>
            <input v-model="orderDesignEditorDraft.design_title" class="constructionDialog__input" type="text" />
          </label>
          <label class="orderEntry__field">
            <span>کد نمونه</span>
            <input v-model="orderDesignEditorDraft.instance_code" class="constructionDialog__input constructionDialog__input--mono" type="text" />
          </label>
          <label class="orderEntry__field">
            <span>کد طرح منبع</span>
            <input :value="orderDesignEditorDraft.design_code" class="constructionDialog__input constructionDialog__input--mono" type="text" readonly />
          </label>
        </div>
        <div class="constructionDialog__tableWrap" style="margin-top: 16px;">
          <table class="constructionDialog__table orderEntry__table">
            <thead>
              <tr>
                <th class="constructionDialog__col constructionDialog__col--title">صفت</th>
                <th class="constructionDialog__col constructionDialog__col--title">مقدار</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="entry in getOrderDesignAttrEntries(orderDesignEditorDraft)" :key="entry.key">
                <td class="constructionDialog__col constructionDialog__col--title">{{ entry.meta.label || entry.key }}</td>
                <td class="constructionDialog__col constructionDialog__col--title">
                  <select
                    v-if="entry.meta.input_mode === 'binary'"
                    v-model="orderDesignEditorDraft.order_attr_values[entry.key]"
                    class="constructionDialog__input"
                  >
                    <option value="0">{{ entry.meta.binary_off_label || "0" }}</option>
                    <option value="1">{{ entry.meta.binary_on_label || "1" }}</option>
                  </select>
                  <input
                    v-else
                    v-model="orderDesignEditorDraft.order_attr_values[entry.key]"
                    class="constructionDialog__input"
                    type="text"
                  />
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" @click="closeOrderDesignEditor">انصراف</button>
        <button type="button" class="constructionDialog__textBtn is-primary" @click="saveOrderDesignEditor">ذخیره طرح</button>
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
