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
  orderDesign: {
    type: Object,
    default: null,
  },
  selectedOrderDesignIds: {
    type: Array,
    default: () => [],
  },
  orderParamGroups: {
    type: Array,
    default: () => [],
  },
  placeholderBoxes: {
    type: Array,
    default: () => [],
  },
  placeholderOutlineColor: {
    type: String,
    default: "#7A4A2B",
  },
  placeholderInstances: {
    type: Array,
    default: () => [],
  },
  showAttrsPanel: {
    type: Boolean,
    default: true,
  },
  embedded: {
    type: Boolean,
    default: false,
  },
  previewOnly: {
    type: Boolean,
    default: false,
  },
  previewActive: {
    type: Boolean,
    default: false,
  },
  displayUnit: {
    type: String,
    default: "cm",
  },
});

const emit = defineEmits(["mouseenter", "mouseleave", "model2d", "update:wallStyleDraft", "update:selectedWallCoords", "update:orderDesignAttr", "openInteriorLibraryForDesign"]);

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
let placeholderBoxesRoot = null;

let axesHelper = null;
let lastMiddleClickMs = 0;
const PREVIEW_VIEW_DIR = new THREE.Vector3(1, 0.78, 1.18);

const DEFAULT_WALL_HEIGHT_M = 2.8;
const DEFAULT_MITER_LIMIT = 10;
const PLACEHOLDER_BOX_SPECS_MM = [
  // یونیت کابینت چپ
  { width: 800, depth: 550, height: 16, cx: 400, cy: 325, cz: 146 },
  { width: 16, depth: 550, height: 704, cx: 8, cy: 325, cz: 506 },
  { width: 16, depth: 550, height: 704, cx: 792, cy: 325, cz: 506 },
  { width: 782, depth: 3, height: 711, cx: 400, cy: 582.5, cz: 502.5 },
  { width: 768, depth: 80, height: 16, cx: 400, cy: 90, cz: 850 },
  { width: 768, depth: 80, height: 16, cx: 400, cy: 541, cz: 850 },
  { width: 768, depth: 16, height: 80, cx: 400, cy: 592, cz: 818 },
  { width: 768, depth: 16, height: 80, cx: 400, cy: 592, cz: 194 },
  { width: 768, depth: 531, height: 16, cx: 400, cy: 315.5, cz: 498 },
  { width: 398, depth: 16, height: 718, cx: 200, cy: 42, cz: 498 },
  { width: 398, depth: 16, height: 718, cx: 600, cy: 42, cz: 498 },
  // یونیت کابینت راست
  { width: 800, depth: 550, height: 16, cx: 1200, cy: 325, cz: 146 },
  { width: 16, depth: 550, height: 704, cx: 808, cy: 325, cz: 506 },
  { width: 16, depth: 550, height: 704, cx: 1592, cy: 325, cz: 506 },
  { width: 782, depth: 3, height: 711, cx: 1200, cy: 582.5, cz: 502.5 },
  { width: 768, depth: 80, height: 16, cx: 1200, cy: 90, cz: 850 },
  { width: 768, depth: 80, height: 16, cx: 1200, cy: 541, cz: 850 },
  { width: 768, depth: 16, height: 80, cx: 1200, cy: 592, cz: 818 },
  { width: 768, depth: 16, height: 80, cx: 1200, cy: 592, cz: 194 },
  { width: 768, depth: 531, height: 16, cx: 1200, cy: 315.5, cz: 498 },
  { width: 398, depth: 16, height: 718, cx: 1000, cy: 42, cz: 498 },
  { width: 398, depth: 16, height: 718, cx: 1400, cy: 42, cz: 498 },
  // صفحه کابینت
  { width: 1600, depth: 600, height: 32, cx: 800, cy: 300, cz: 874 },
  // پاخور
  { width: 1600, depth: 16, height: 138, cx: 800, cy: 58, cz: 69 },
];
const attrsSnapshot = computed(() => props.walls2d?.metrics || props.walls2d || {});
const selectedEntityType = computed(
  () => attrsSnapshot.value?.entityType || props.selectedWallStyle?.entityType || "wall"
);
const displayUnit = computed(() => {
  const unit = String(props.displayUnit || "").trim().toLowerCase();
  return unit === "mm" || unit === "inch" ? unit : "cm";
});
const displayUnitLabel = computed(() => {
  if (displayUnit.value === "mm") return "میلی‌متر";
  if (displayUnit.value === "inch") return "اینچ";
  return "سانتی‌متر";
});
const isBeamLikeEntity = computed(() => selectedEntityType.value === "beam" || selectedEntityType.value === "column");
const showLengthField = computed(() => selectedEntityType.value !== "hidden");
const showThicknessField = computed(() => selectedEntityType.value === "wall" || isBeamLikeEntity.value);
const showHeightField = computed(() => selectedEntityType.value === "wall" || isBeamLikeEntity.value);
const showFloorDistanceField = computed(() => selectedEntityType.value === "beam");
const lengthFieldLabel = computed(() => selectedEntityType.value === "column" ? "عرض" : "طول");
const thicknessFieldLabel = computed(() => selectedEntityType.value === "column" ? "عمق" : "ضخامت");
const colorFieldLabel = computed(() => {
  if (selectedEntityType.value === "column") return "رنگ سه بعدی ستون";
  if (selectedEntityType.value === "beam") return "رنگ سه بعدی تیر";
  return "رنگ سه بعدی دیوار";
});
const showColorField = computed(() => selectedEntityType.value === "wall" || selectedEntityType.value === "beam" || selectedEntityType.value === "column");
const activeOrderDesign = computed(() => props.orderDesign || null);
const orderDesignInputDrafts = ref({});
const brokenOrderDesignIcons = ref({});
const liveOrderParamGroupsById = computed(() =>
  new Map(
    (Array.isArray(props.orderParamGroups) ? props.orderParamGroups : []).map((group) => [
      String(group?.param_group_id ?? ""),
      group || {},
    ])
  )
);
const orderDesignAttrGroups = computed(() => {
  const item = activeOrderDesign.value;
  if (!item?.order_attr_meta) return [];
  const meta = item.order_attr_meta || {};
  const values = item.order_attr_values || {};
  const groupsMap = new Map();
  for (const [key, rawMeta] of Object.entries(meta)) {
    const entryMeta = rawMeta || {};
    const liveGroup = liveOrderParamGroupsById.value.get(String(entryMeta.group_id ?? ""));
    const shouldShowGroup = liveGroup
      ? liveGroup.show_in_order_attrs !== false
      : entryMeta.group_show_in_order_attrs !== false;
    if (!shouldShowGroup) continue;
    const groupKey = String((entryMeta.group_id ?? entryMeta.group_title) || "سایر صفات").trim() || "سایر صفات";
    const groupTitle = String(
      liveGroup?.org_param_group_title || liveGroup?.title || entryMeta.group_title || "سایر صفات"
    ).trim() || "سایر صفات";
    const groupIconPath = String(
      liveGroup?.param_group_icon_path || entryMeta.group_icon_path || ""
    ).trim();
    const groupOrder = Number.isFinite(Number(liveGroup?.ui_order))
      ? Number(liveGroup.ui_order)
      : (Number(entryMeta.group_ui_order) || 0);
    if (!groupsMap.has(groupKey)) {
      groupsMap.set(groupKey, {
        key: groupKey,
        title: groupTitle,
        order: groupOrder,
        iconPath: groupIconPath,
        items: [],
      });
    }
    groupsMap.get(groupKey).items.push({
      key,
      label: String(entryMeta.label || key).trim() || key,
      iconPath: String(entryMeta.icon_path || entryMeta.group_icon_path || "").trim() || "",
      inputMode: entryMeta.input_mode === "binary" ? "binary" : "value",
      binaryOffLabel: String(entryMeta.binary_off_label || "0").trim() || "0",
      binaryOnLabel: String(entryMeta.binary_on_label || "1").trim() || "1",
      binaryOffIconPath: String(entryMeta.binary_off_icon_path || entryMeta.icon_path || entryMeta.group_icon_path || "").trim() || "",
      binaryOnIconPath: String(entryMeta.binary_on_icon_path || entryMeta.icon_path || entryMeta.group_icon_path || "").trim() || "",
      value: Object.prototype.hasOwnProperty.call(orderDesignInputDrafts.value, key)
        ? orderDesignInputDrafts.value[key]
        : values[key] ?? "",
      displayValue: Object.prototype.hasOwnProperty.call(orderDesignInputDrafts.value, key)
        ? orderDesignInputDrafts.value[key]
        : formatOrderDesignDisplayValue(values[key] ?? "", entryMeta.input_mode === "binary" ? "binary" : "value"),
      unitLabel: getOrderDesignValueUnit(entryMeta.input_mode === "binary" ? "binary" : "value"),
      sortOrder: Number(entryMeta.param_ui_order) || 0,
      paramId: Number(entryMeta.param_id) || 0,
    });
  }
  return Array.from(groupsMap.values())
    .map((group) => ({
      ...group,
      items: group.items.sort((a, b) => {
        const orderDelta = a.sortOrder - b.sortOrder;
        if (orderDelta !== 0) return orderDelta;
        const idDelta = a.paramId - b.paramId;
        if (idDelta !== 0) return idDelta;
        return a.label.localeCompare(b.label, "fa");
      }),
    }))
    .sort((a, b) => a.order - b.order || a.title.localeCompare(b.title, "fa"));
});
const orderDesignAttrIconBase = computed(() => {
  const adminId = String(activeOrderDesign.value?.admin_id || "").trim();
  return adminId ? `/api/admin-storage/${encodeURIComponent(adminId)}/icons/` : "";
});
function resolveOrderDesignMetaIcon(path) {
  const fileName = String(path || "").trim();
  const base = orderDesignAttrIconBase.value;
  if (!fileName) return "";
  if (/^(https?:)?\/\//i.test(fileName) || fileName.startsWith("/")) return fileName;
  if (!base) return "";
  const cacheKey = `${base}::${fileName}`;
  if (brokenOrderDesignIcons.value[cacheKey]) return "";
  return `${base}${encodeURIComponent(fileName)}`;
}
function markOrderDesignIconBroken(path) {
  const fileName = String(path || "").trim();
  const base = orderDesignAttrIconBase.value;
  if (!fileName || !base) return;
  const cacheKey = `${base}::${fileName}`;
  brokenOrderDesignIcons.value = {
    ...brokenOrderDesignIcons.value,
    [cacheKey]: true,
  };
}
const hasOrderDesignAttrs = computed(() => !!activeOrderDesign.value && orderDesignAttrGroups.value.length > 0);
const activeOrderDesignIdentity = computed(() => {
  const item = activeOrderDesign.value;
  if (!item) return null;
  const title = String(item.design_title || item.instance_code || "").trim();
  const code = String(item.design_code || "").trim();
  const name = String(item.instance_code || "").trim();
  if (!title && !code && !name) return null;
  return { title, code, name };
});
const showOrderDesignTools = computed(() =>
  showOrderDesignAttrPanel.value
  && selectedOrderDesignCount.value <= 1
  && !!activeOrderDesign.value
);

function normalizeGroupSearchText(group) {
  return `${String(group?.title || "")} ${String(group?.key || "")}`.trim().toLowerCase();
}

function findOrderDesignGroupKey(tokens = []) {
  const normalizedTokens = (Array.isArray(tokens) ? tokens : [])
    .map((token) => String(token || "").trim().toLowerCase())
    .filter(Boolean);
  if (!normalizedTokens.length) return "";
  const match = orderDesignAttrGroups.value.find((group) => {
    const haystack = normalizeGroupSearchText(group);
    return normalizedTokens.some((token) => haystack.includes(token));
  });
  return String(match?.key || "");
}

function openDoorAttrsForActiveDesign() {
  const doorKey = findOrderDesignGroupKey(["door", "درب"]);
  if (doorKey) {
    openOrderDesignGroupKey.value = doorKey;
    return;
  }
  openOrderDesignGroupKey.value = String(orderDesignAttrGroups.value?.[0]?.key || "");
}

function focusActiveDesign3d() {
  fitCameraToSelectionOrAll();
}

function openInteriorLibraryForActiveDesign() {
  const designId = String(activeOrderDesign.value?.id || "").trim();
  if (!designId) return;
  emit("openInteriorLibraryForDesign", designId);
}
const mmToCm = (v) => Math.round((Number(v || 0) * 0.1) * 10) / 10;
const cmToMm = (v) => Number(v) * 10;
function cmToDisplay(v) {
  const numeric = Number(v || 0);
  if (displayUnit.value === "mm") return Math.round(numeric * 10 * 10) / 10;
  if (displayUnit.value === "inch") return Math.round((numeric / 2.54) * 100) / 100;
  return numeric;
}
function displayToCm(v) {
  const numeric = Number(v);
  if (!Number.isFinite(numeric)) return numeric;
  if (displayUnit.value === "mm") return numeric / 10;
  if (displayUnit.value === "inch") return numeric * 2.54;
  return numeric;
}
function mmToDisplay(v) {
  const numeric = Number(v || 0);
  if (displayUnit.value === "mm") return numeric;
  if (displayUnit.value === "inch") return Math.round((numeric / 25.4) * 100) / 100;
  return Math.round((numeric / 10) * 10) / 10;
}
function displayToMm(v) {
  const numeric = Number(v);
  if (!Number.isFinite(numeric)) return numeric;
  if (displayUnit.value === "mm") return numeric;
  if (displayUnit.value === "inch") return numeric * 25.4;
  return numeric * 10;
}
function formatOrderDesignDisplayValue(value, inputMode) {
  if (inputMode === "binary") return value;
  const text = value == null ? "" : String(value).trim();
  if (!text) return "";
  const numeric = Number(text);
  if (!Number.isFinite(numeric)) return text;
  return String(mmToDisplay(numeric));
}
function getOrderDesignValueUnit(inputMode) {
  return inputMode === "binary" ? "" : displayUnitLabel.value;
}
function normalizeIds(ids) {
  return Array.isArray(ids)
    ? ids.map((id) => String(id || "").trim()).filter(Boolean)
    : [];
}
function getBoxBoundsMm(boxes) {
  const normalized = Array.isArray(boxes) ? boxes : [];
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  for (const raw of normalized) {
    const width = Math.max(1, Number(raw?.width) || 0);
    const depth = Math.max(1, Number(raw?.depth) || 0);
    const cx = Number(raw?.cx) || 0;
    const cy = Number(raw?.cy) || 0;
    const halfW = width * 0.5;
    const halfD = depth * 0.5;
    minX = Math.min(minX, cx - halfW);
    maxX = Math.max(maxX, cx + halfW);
    minY = Math.min(minY, cy - halfD);
    maxY = Math.max(maxY, cy + halfD);
  }
  if (!Number.isFinite(minX) || !Number.isFinite(minY) || !Number.isFinite(maxX) || !Number.isFinite(maxY)) return null;
  return { minX, minY, maxX, maxY };
}
function mapLocalPointToWorld(point, transform = null) {
  const tx = Number.isFinite(Number(transform?.x)) ? Number(transform.x) : 0;
  const ty = Number.isFinite(Number(transform?.y)) ? Number(transform.y) : 0;
  const rotRad = Number.isFinite(Number(transform?.rotRad)) ? Number(transform.rotRad) : 0;
  const cos = Math.cos(rotRad);
  const sin = Math.sin(rotRad);
  return {
    x: (Number(point?.x) * cos - Number(point?.y) * sin) + tx,
    y: (Number(point?.x) * sin + Number(point?.y) * cos) + ty,
  };
}
const hasModelOutlineSelection = computed(() => !!attrsSnapshot.value?.selection?.selectedModelOutline);
const selectedOrderDesignIds = computed(() => normalizeIds(props.selectedOrderDesignIds));
const selectedOrderDesignCount = computed(() =>
  selectedOrderDesignIds.value.length > 0
    ? selectedOrderDesignIds.value.length
    : (hasModelOutlineSelection.value && activeOrderDesign.value?.id ? 1 : 0)
);
const hasOrderDesignSelection = computed(() => selectedOrderDesignCount.value > 0 || hasModelOutlineSelection.value);
const openOrderDesignGroupKey = ref("");

watch(
  () => String(activeOrderDesign.value?.id || ""),
  () => {
    orderDesignInputDrafts.value = {};
    brokenOrderDesignIcons.value = {};
    openOrderDesignGroupKey.value = String(orderDesignAttrGroups.value?.[0]?.key || "");
  }
);

watch(
  orderDesignAttrGroups,
  (groups) => {
    const firstKey = String(groups?.[0]?.key || "");
    const hasCurrent = groups.some((group) => String(group.key) === String(openOrderDesignGroupKey.value));
    if (!hasCurrent) {
      openOrderDesignGroupKey.value = firstKey;
    }
  },
  { immediate: true }
);

const selectionSummary = computed(() => {
  const selection = attrsSnapshot.value?.selection || {};
  const collectIds = (singleValue, manyValues) => {
    const next = normalizeIds(manyValues);
    const single = String(singleValue || "").trim();
    if (single && !next.includes(single)) next.unshift(single);
    return next;
  };
  const rawWallIds = collectIds(selection.selectedWallId, selection.selectedWallIds);
  const beamIds = collectIds(selection.selectedBeamId, selection.selectedBeamIds);
  const beamSet = new Set(beamIds);
  const wallIds = rawWallIds.filter((id) => !beamSet.has(id));
  const hiddenIds = collectIds(selection.selectedHiddenId, selection.selectedHiddenIds);
  const passiveDesignIds = collectIds(selection.selectedPassiveModelId, selection.selectedPassiveModelIds);
  const designIds = selectedOrderDesignIds.value.length
    ? selectedOrderDesignIds.value
    : (hasModelOutlineSelection.value && activeOrderDesign.value?.id ? [String(activeOrderDesign.value.id)] : passiveDesignIds);
  const categoryCount = [
    wallIds.length > 0,
    beamIds.length > 0,
    hiddenIds.length > 0,
    designIds.length > 0,
  ].filter(Boolean).length;
  return {
    wallIds,
    beamIds,
    hiddenIds,
    passiveDesignIds,
    designIds,
    totalCount: wallIds.length + beamIds.length + hiddenIds.length + designIds.length,
    categoryCount,
    hasMixedSelection: categoryCount > 1,
  };
});
const selectedEntityCount = computed(() => selectionSummary.value.totalCount);
const isGroupEditMode = computed(() => selectedEntityCount.value > 1);
const hasMixedSelection = computed(() => selectionSummary.value.hasMixedSelection);
const hasNonDesignSelection = computed(() =>
  selectionSummary.value.wallIds.length > 0
  || selectionSummary.value.beamIds.length > 0
  || selectionSummary.value.hiddenIds.length > 0
);
const selectedObjectTitle = computed(() => {
  if (hasMixedSelection.value) return `انتخاب ترکیبی (${selectedEntityCount.value} مورد)`;
  if (hasOrderDesignSelection.value && selectedOrderDesignCount.value > 1) return `${selectedOrderDesignCount.value} طرح سفارش`;
  const raw = props.selectedWallStyle?.name || props.selectedWallStyle?.id || wallMetrics.value?.id || "";
  return String(raw).trim();
});
const showOrderDesignAttrPanel = computed(() =>
  !!activeOrderDesignIdentity.value
  && hasOrderDesignSelection.value
  && !hasMixedSelection.value
  && !hasNonDesignSelection.value
);
const showObjectStyleEditor = computed(() => !!wallMetrics.value && !hasOrderDesignSelection.value && !hasMixedSelection.value);
const wallMoveDeltaCm = ref({ x: 0, y: 0 });
const coordInputDrafts = ref({});
const showPlaceholderEdges = ref(true);
const placeholderOpacity = ref(100);

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

function buildCornerMetrics(a, b) {
  if (!a || !b) return null;

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
}

const singleSelectedOrderDesignInstance = computed(() => {
  if (hasMixedSelection.value || selectedOrderDesignCount.value !== 1) return null;
  const designId = String(selectedOrderDesignIds.value[0] || activeOrderDesign.value?.id || "").trim();
  if (!designId) return null;
  const instances = Array.isArray(props.placeholderInstances) ? props.placeholderInstances : [];
  const passive = instances.find((instance) => String(instance?.orderDesignId || "").trim() === designId);
  if (passive) return passive;
  if (hasModelOutlineSelection.value && String(activeOrderDesign.value?.id || "").trim() === designId) {
    return {
      orderDesignId: designId,
      boxes: Array.isArray(props.placeholderBoxes) ? props.placeholderBoxes : [],
      transform: props.model2dTransform,
      active: true,
    };
  }
  return null;
});

const orderDesignMetrics = computed(() => {
  const instance = singleSelectedOrderDesignInstance.value;
  const bounds = getBoxBoundsMm(instance?.boxes);
  if (!bounds) return null;
  const worldCorners = [
    mapLocalPointToWorld({ x: bounds.minX, y: bounds.minY }, instance?.transform),
    mapLocalPointToWorld({ x: bounds.maxX, y: bounds.minY }, instance?.transform),
    mapLocalPointToWorld({ x: bounds.maxX, y: bounds.maxY }, instance?.transform),
    mapLocalPointToWorld({ x: bounds.minX, y: bounds.maxY }, instance?.transform),
  ];
  const xs = worldCorners.map((point) => Number(point.x) || 0);
  const ys = worldCorners.map((point) => Number(point.y) || 0);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return {
    id: String(instance?.orderDesignId || activeOrderDesign.value?.id || "").trim() || "design",
    bottomLeft: { x: mmToCm(minX), y: mmToCm(minY) },
    topRight: { x: mmToCm(maxX), y: mmToCm(maxY) },
    center: { x: mmToCm((minX + maxX) * 0.5), y: mmToCm((minY + maxY) * 0.5) },
    bottomLeftKey: "a",
    topRightKey: "b",
    kind: "design",
  };
});

const wallCoordPoints = computed(() => {
  if (orderDesignMetrics.value) return orderDesignMetrics.value;
  if (!wallMetrics.value) return null;
  return {
    ...buildCornerMetrics(wallMetrics.value.a, wallMetrics.value.b),
    kind: "wall",
  };
});
const hasAnyAttrSelection = computed(() => selectedEntityCount.value > 0 || !!wallMetrics.value);
const showCoordsEditor = computed(() => selectedEntityCount.value > 0);

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
  emit("update:wallStyleDraft", patch);
}

function patchSelectedWallCoords(patch) {
  emit("update:selectedWallCoords", patch);
}

function patchOrderDesignAttr(key, value) {
  emit("update:orderDesignAttr", { key, value });
}

function setOrderDesignDraftValue(key, value) {
  orderDesignInputDrafts.value = {
    ...orderDesignInputDrafts.value,
    [key]: value,
  };
}

function commitOrderDesignDraftValue(key, entry = null) {
  if (!Object.prototype.hasOwnProperty.call(orderDesignInputDrafts.value, key)) return;
  const rawValue = orderDesignInputDrafts.value[key] ?? "";
  if (entry?.inputMode === "binary") {
    patchOrderDesignAttr(key, rawValue);
    return;
  }
  const numeric = Number(rawValue);
  if (!String(rawValue).trim() || !Number.isFinite(numeric)) {
    patchOrderDesignAttr(key, rawValue);
    return;
  }
  patchOrderDesignAttr(key, String(displayToMm(numeric)));
}

function toggleOrderDesignGroup(groupKey) {
  const key = String(groupKey || "");
  if (!key) return;
  openOrderDesignGroupKey.value = openOrderDesignGroupKey.value === key ? "" : key;
}

function patchCenterCoord(axis, value) {
  const num = Number(value);
  if (!Number.isFinite(num)) return;

  const curCenter = wallCoordPoints.value?.center;
  if (!curCenter) return;

  const dx = (axis === "x") ? (num - curCenter.x) : 0;
  const dy = (axis === "y") ? (num - curCenter.y) : 0;
  if (dx === 0 && dy === 0) return;

  if (wallCoordPoints.value?.kind === "design") {
    patchSelectedWallCoords({
      axCm: wallCoordPoints.value.bottomLeft.x + dx,
      ayCm: wallCoordPoints.value.bottomLeft.y + dy,
      bxCm: wallCoordPoints.value.topRight.x + dx,
      byCm: wallCoordPoints.value.topRight.y + dy,
    });
    return;
  }

  if (!wallMetrics.value) return;
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
    [axis]: Number.isFinite(num) ? displayToCm(num) : 0,
  };
}

function moveWallByAxis(axis) {
  if (axis !== "x" && axis !== "y") return;
  const delta = Number(wallMoveDeltaCm.value?.[axis]);
  if (!Number.isFinite(delta) || delta === 0) return;

  if (isGroupEditMode.value || wallCoordPoints.value?.kind === "design") {
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
  if (fallback == null || fallback === "") return "";
  return String(cmToDisplay(fallback));
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
  patchCenterCoord(axis, displayToCm(num));
}

function commitPointCoordInput(pointKey, axis, key) {
  const text = coordInputDrafts.value[key];
  const num = parseNumericInput(text);
  clearCoordFieldDraft(key);
  if (!Number.isFinite(num)) return;
  patchByPointKey(pointKey, axis, displayToCm(num));
}

watch(
  [() => wallMetrics.value?.id, () => orderDesignMetrics.value?.id, () => selectedEntityCount.value, () => isGroupEditMode.value],
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

function clearPlaceholderBoxes() {
  if (!scene || !placeholderBoxesRoot) return;
  placeholderBoxesRoot.traverse((n) => {
    if (n.geometry) n.geometry.dispose?.();
    if (n.material) {
      const mats = Array.isArray(n.material) ? n.material : [n.material];
      for (const m of mats) m.dispose?.();
    }
  });
  scene.remove(placeholderBoxesRoot);
  placeholderBoxesRoot = null;
}

function normalizePlaceholderColor(value, fallback = "#7A4A2B") {
  const raw = String(value || "").trim();
  const normalized = raw.startsWith("#") ? raw : `#${raw}`;
  return /^#[0-9A-Fa-f]{6}$/.test(normalized) ? normalized.toUpperCase() : fallback;
}

function buildPlaceholderPalette(outlineColor) {
  const fill = new THREE.Color(normalizePlaceholderColor(outlineColor)).lerp(new THREE.Color("#FFFFFF"), 0.76);
  const edge = new THREE.Color("#000000");
  return { edge, fill };
}

function cloneColor(color, fallback = "#FFFFFF") {
  if (color?.isColor) return color.clone();
  return new THREE.Color(color || fallback);
}

function applyPlaceholderInstanceVisualState(instanceRoot, state = "default") {
  if (!instanceRoot) return;
  const DRAG_EDGE = "#4B5563";

  const solidOpacityFactor =
    state === "selected" ? 1
      : state === "ready" ? 1
      : state === "drag-preview" ? 0.94
      : 1;
  const edgeOpacity =
    state === "selected" ? 1
      : state === "ready" ? 0.95
      : state === "drag-preview" ? 0.96
      : 0.95;
  const emissiveIntensity =
    state === "selected" ? 0.62
      : state === "ready" ? 0
      : state === "drag-preview" ? 0.08
      : 0;

  instanceRoot.traverse((obj) => {
    if (obj?.userData?.isPlaceholderSolid) {
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      for (const mat of mats) {
        if (!mat) continue;
        const baseColor = cloneColor(obj.userData?.basePlaceholderColor, mat.color);
        mat.color.copy(baseColor);
        if (mat.emissive?.isColor) {
          mat.emissive.set(state === "selected" ? "#FFF6E6" : "#000000");
          mat.emissiveIntensity = emissiveIntensity;
        }
        mat.roughness =
          state === "selected" ? 0.48
            : state === "ready" ? 0.82
            : state === "drag-preview" ? 0.78
            : 0.82;
        mat.metalness = state === "selected" ? 0.1 : 0.04;
        const baseOpacity = Number.isFinite(Number(obj.userData?.basePlaceholderOpacity))
          ? Number(obj.userData.basePlaceholderOpacity)
          : 1;
        const nextOpacity = Math.max(0.08, Math.min(1, baseOpacity * solidOpacityFactor));
        mat.transparent = nextOpacity < 0.999;
        mat.opacity = nextOpacity;
        mat.needsUpdate = true;
      }
      return;
    }

    if (obj?.userData?.isPlaceholderEdge) {
      const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
      for (const mat of mats) {
        if (!mat) continue;
        const baseEdgeColor = cloneColor(obj.userData?.basePlaceholderEdgeColor, mat.color);
        const nextEdgeColor = baseEdgeColor.clone();
        if (state === "drag-preview") nextEdgeColor.copy(new THREE.Color(DRAG_EDGE));
        mat.color.copy(nextEdgeColor);
        mat.opacity = edgeOpacity;
        mat.needsUpdate = true;
      }
    }
  });
}

function rebuildPlaceholderBoxes() {
  if (!scene) return;
  clearPlaceholderBoxes();

  const root = new THREE.Group();
  root.name = "placeholder-boxes";
  const instances = Array.isArray(props.placeholderInstances) && props.placeholderInstances.length
    ? props.placeholderInstances
    : [{
        orderDesignId: "active",
        boxes: Array.isArray(props.placeholderBoxes) ? props.placeholderBoxes : (props.embedded ? PLACEHOLDER_BOX_SPECS_MM : []),
        transform: props.model2dTransform,
        active: true,
      }];

  for (const instance of instances) {
    const specs = Array.isArray(instance?.boxes) ? instance.boxes : [];
    if (!specs.length) continue;
    const palette = buildPlaceholderPalette(
      instance?.outlineColor || props.orderDesign?.design_outline_color || props.placeholderOutlineColor
    );
    const tx = Number.isFinite(Number(instance?.transform?.x)) ? Number(instance.transform.x) : 0;
    const ty = Number.isFinite(Number(instance?.transform?.y)) ? Number(instance.transform.y) : 0;
    const rotRad = Number.isFinite(Number(instance?.transform?.rotRad)) ? Number(instance.transform.rotRad) : 0;

    const instanceRoot = new THREE.Group();
    instanceRoot.name = `placeholder-instance-${String(instance?.orderDesignId || "item")}`;
    instanceRoot.userData.orderDesignId = String(instance?.orderDesignId || "item").trim() || "item";
    instanceRoot.userData.isActivePlaceholderInstance = !!instance?.active;
    instanceRoot.userData.isDragPreviewInstance = !!instance?.dragPreview;
    instanceRoot.position.set(tx * 0.001, 0, -ty * 0.001);
    instanceRoot.rotation.y = rotRad;

    for (const spec of specs) {
      const widthM = Math.max(0.001, Number(spec.width) * 0.001);
      const depthM = Math.max(0.001, Number(spec.depth) * 0.001);
      const heightM = Math.max(0.001, Number(spec.height) * 0.001);
      const cxM = Number(spec.cx) * 0.001;
      const cyM = Number(spec.cy) * 0.001;
      const czM = Number(spec.cz) * 0.001;

      const geometry = new THREE.BoxGeometry(widthM, heightM, depthM);
      const material = new THREE.MeshStandardMaterial({
        color: palette.fill.clone(),
        roughness: 0.82,
        metalness: 0.04,
        transparent: true,
        opacity: 1,
      });
      const mesh = new THREE.Mesh(geometry, material);
      mesh.userData.isPlaceholderSolid = true;
      mesh.userData.basePlaceholderColor = palette.fill.clone();
      mesh.userData.basePlaceholderOpacity = 1;
      const edges = new THREE.EdgesGeometry(geometry);
      const edgeLines = new THREE.LineSegments(
        edges,
        new THREE.LineBasicMaterial({
          color: palette.edge.clone(),
          transparent: true,
          opacity: 0.95,
          depthTest: true,
          depthWrite: false,
        })
      );
      edgeLines.userData.isPlaceholderEdge = true;
      edgeLines.userData.basePlaceholderEdgeColor = palette.edge.clone();

      mesh.position.set(cxM, czM, -cyM);
      edgeLines.position.copy(mesh.position);
      instanceRoot.add(mesh);
      instanceRoot.add(edgeLines);
    }

    root.add(instanceRoot);
  }

  if (!root.children.length) return;
  placeholderBoxesRoot = root;
  scene.add(root);
  if (!(Array.isArray(props.placeholderInstances) && props.placeholderInstances.length)) {
    applyModel2dTransformTo3d(props.model2dTransform);
    try {
      const lines = projectModelTo2DLines(root);
      emit("model2d", {
        lines,
        opts: { color: "#8a98a3", lineWidthPx: 1, dash: [4, 7], alpha: 0.5 },
      });
    } catch (_) {
      // no-op
    }
  }

  syncPlaceholderEdgeVisibility();
  syncPlaceholderOpacity();
  syncSelectionHighlight();
}

function syncPlaceholderEdgeVisibility() {
  if (!placeholderBoxesRoot) return;
  placeholderBoxesRoot.traverse((obj) => {
    if (obj?.userData?.isPlaceholderEdge) obj.visible = !!showPlaceholderEdges.value;
  });
}

function togglePlaceholderEdges() {
  showPlaceholderEdges.value = !showPlaceholderEdges.value;
  syncPlaceholderEdgeVisibility();
}

function syncPlaceholderOpacity() {
  if (!placeholderBoxesRoot) return;
  const nextOpacity = Math.max(0, Math.min(1, Number(placeholderOpacity.value) / 100));
  placeholderBoxesRoot.traverse((obj) => {
    if (!obj?.userData?.isPlaceholderSolid) return;
    const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
    for (const mat of mats) {
      if (!mat) continue;
      obj.userData.basePlaceholderOpacity = nextOpacity;
      mat.transparent = nextOpacity < 1;
      mat.opacity = nextOpacity;
      mat.needsUpdate = true;
    }
  });
  syncSelectionHighlight();
}

function syncSelectionHighlight() {
  if (!placeholderBoxesRoot) return;
  if (props.embedded) {
    for (const child of placeholderBoxesRoot.children) {
      applyPlaceholderInstanceVisualState(child, "default");
    }
    return;
  }
  const selection = props.walls2d?.selection || {};
  const selectedIds = new Set(
    (Array.isArray(props.selectedOrderDesignIds) ? props.selectedOrderDesignIds : [])
      .map((id) => String(id || "").trim())
      .filter(Boolean)
  );
  const hasActiveModelSelection = !!selection.selectedModelOutline;

  for (const child of placeholderBoxesRoot.children) {
    const orderDesignId = String(child?.userData?.orderDesignId || "").trim();
    const isActive = !!child?.userData?.isActivePlaceholderInstance;
    const isDragPreview = !!child?.userData?.isDragPreviewInstance;
    const isSelected = (!!orderDesignId && selectedIds.has(orderDesignId)) || (hasActiveModelSelection && isActive);
    const state = isDragPreview ? "drag-preview" : (isSelected ? "selected" : (isActive ? "ready" : "default"));
    applyPlaceholderInstanceVisualState(child, state);
  }
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
      mesh.userData.wallId = String(w?.id || "").trim() || null;
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

function has2dDrawingContent() {
  const normalized = normalizeLinearMembers(props.walls2d);
  const nodes = Array.isArray(normalized?.nodes) ? normalized.nodes : [];
  const walls = Array.isArray(normalized?.walls) ? normalized.walls : [];
  return nodes.length > 0 && walls.length > 0;
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

  camera.position.copy(center).addScaledVector(dir, distance * (props.previewOnly ? 1.72 : 1.5));
  controls.target.copy(center);
  camera.near = Math.max(distance / 500, 0.01);
  camera.far = Math.max(distance * 50, 100);
  camera.updateProjectionMatrix();
  controls.update();

  if (axesHelper) {
    const maxDim = Math.max(size.x, size.y, size.z) || 1;
    const a = THREE.MathUtils.clamp(maxDim * 0.18, 0.16, 2.4);
    axesHelper.scale.setScalar(a);
  }
}

function fitCameraToAll(viewDir = null) {
  const bounds = computeRenderableSceneBounds();
  if (!bounds) {
    centerCameraOnOrigin(viewDir);
    return;
  }
  fitCameraToBounds(bounds, viewDir);
}

function centerCameraOnOrigin(viewDir = null) {
  const halfSpanM = 3;
  const bounds = new THREE.Box3(
    new THREE.Vector3(-halfSpanM, 0, -halfSpanM),
    new THREE.Vector3(halfSpanM, 0.01, halfSpanM)
  );
  fitCameraToBounds(bounds, viewDir);
}

function computeSelectionBounds() {
  if (!scene) return null;

  const bounds = new THREE.Box3();
  let hasSelection = false;
  const selection = props.walls2d?.selection || {};
  const selectedWallIds = new Set();
  const addWallId = (id) => {
    const key = String(id || "").trim();
    if (key) selectedWallIds.add(key);
  };

  addWallId(selection.selectedWallId);
  if (Array.isArray(selection.selectedWallIds)) {
    for (const id of selection.selectedWallIds) addWallId(id);
  }
  addWallId(selection.selectedBeamId);
  if (Array.isArray(selection.selectedBeamIds)) {
    for (const id of selection.selectedBeamIds) addWallId(id);
  }

  if (wallsRoot && selectedWallIds.size > 0) {
    wallsRoot.traverse((obj) => {
      if (!obj?.isMesh) return;
      const wallId = String(obj.userData?.wallId || "").trim();
      if (!wallId || !selectedWallIds.has(wallId)) return;
      bounds.expandByObject(obj);
      hasSelection = true;
    });
  }

  const selectedOrderDesignIds = new Set(
    (Array.isArray(props.selectedOrderDesignIds) ? props.selectedOrderDesignIds : [])
      .map((id) => String(id || "").trim())
      .filter(Boolean)
  );
  const hasActiveModelSelection = !!selection.selectedModelOutline;

  if (placeholderBoxesRoot) {
    const hasInstances = Array.isArray(props.placeholderInstances) && props.placeholderInstances.length > 0;
    if (hasInstances) {
      for (const child of placeholderBoxesRoot.children) {
        const orderDesignId = String(child?.userData?.orderDesignId || "").trim();
        const isActive = !!child?.userData?.isActivePlaceholderInstance;
        if (!selectedOrderDesignIds.has(orderDesignId) && !(hasActiveModelSelection && isActive)) continue;
        bounds.expandByObject(child);
        hasSelection = true;
      }
    } else if (hasActiveModelSelection) {
      bounds.expandByObject(placeholderBoxesRoot);
      hasSelection = true;
    }
  }

  return hasSelection && !bounds.isEmpty() ? bounds : null;
}

function fitCameraToSelectionOrAll(viewDir = null) {
  fitCameraToBounds(computeSelectionBounds() || computeRenderableSceneBounds(), viewDir);
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
  if (props.embedded) {
    fitCameraToAll();
  }
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
  if (!has2dDrawingContent()) {
    centerCameraOnOrigin();
    return;
  }
  fitCameraToAll();
}

function onCanvasMouseDown(event) {
  if (event.button !== 1) return;
  const now = performance.now();
  if (now - lastMiddleClickMs <= 300) {
    lastMiddleClickMs = 0;
    event.preventDefault();
    if (!has2dDrawingContent()) {
      centerCameraOnOrigin();
      return;
    }
    fitCameraToAll();
    return;
  }
  lastMiddleClickMs = now;
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
  const xMm = Number.isFinite(transform?.x) ? transform.x : 0;
  const yMm = Number.isFinite(transform?.y) ? transform.y : 0;
  const rotRad = Number.isFinite(transform?.rotRad) ? transform.rotRad : 0;
  const mPerMm = 0.001;

  if (modelRoot && modelBasePosition) {
    modelRoot.position.set(
      modelBasePosition.x + xMm * mPerMm,
      modelBasePosition.y,
      modelBasePosition.z - yMm * mPerMm
    );
    modelRoot.rotation.y = modelBaseRotationY + rotRad;
  }

  if (placeholderBoxesRoot) {
    if (Array.isArray(props.placeholderInstances) && props.placeholderInstances.length) {
      placeholderBoxesRoot.position.set(0, 0, 0);
      placeholderBoxesRoot.rotation.y = 0;
    } else {
      placeholderBoxesRoot.position.set(xMm * mPerMm, 0, -yMm * mPerMm);
      placeholderBoxesRoot.rotation.y = rotRad;
    }
  }
}

watch(
  () => props.placeholderBoxes,
  () => {
    rebuildPlaceholderBoxes();
  },
  { immediate: true, deep: true }
);

watch(
  () => props.placeholderInstances,
  () => {
    rebuildPlaceholderBoxes();
  },
  { immediate: true, deep: true }
);

watch(
  () => props.model2dTransform,
  (t) => {
    applyModel2dTransformTo3d(t);
  },
  { immediate: true }
);

watch(
  () => [
    props.walls2d?.selection?.selectedModelOutline,
    ...(Array.isArray(props.selectedOrderDesignIds) ? props.selectedOrderDesignIds : []),
    ...(Array.isArray(props.placeholderInstances)
      ? props.placeholderInstances.map((item) => `${String(item?.orderDesignId || "").trim()}:${item?.active ? 1 : 0}`)
      : []),
  ],
  () => {
    syncSelectionHighlight();
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
  if (props.previewOnly && axesHelper) axesHelper.visible = false;

  camera = new THREE.PerspectiveCamera(45, 1, 0.01, 1000);
  camera.position.set(2.2, 1.6, 2.2);

  controls = new OrbitControls(camera, canvas);
  controls.enableDamping = true;
  controls.dampingFactor = 0.08;
  controls.rotateSpeed = 0.7;
  controls.zoomSpeed = 0.9;
  controls.panSpeed = 0.7;
  controls.screenSpacePanning = true;
  if (props.previewOnly) {
    controls.autoRotate = !!props.previewActive;
    controls.autoRotateSpeed = 2.2;
    controls.enablePan = false;
    controls.enableZoom = false;
  }

  const hemi = new THREE.HemisphereLight(0xffffff, 0x334155, 1.0);
  scene.add(hemi);
  const dir = new THREE.DirectionalLight(0xffffff, 0.9);
  dir.position.set(3, 6, 4);
  scene.add(dir);

  rebuildWalls3d(props.walls2d);
  rebuildPlaceholderBoxes();

  // GLB model loading is temporarily disabled.
  // This keeps the 3D widget active for generated walls while removing
  // the imported model from both the 3D scene and its 2D projected overlay.
  // try {
  //   const gltf = await loadGlb(props.src);
  //   const root = gltf.scene || gltf.scenes?.[0];
  //   if (root) {
  //     modelRoot = root;
  //     modelBasePosition = root.position.clone();
  //     modelBaseRotationY = root.rotation.y || 0;
  //     scene.add(root);
  //     applyModel2dTransformTo3d(props.model2dTransform);
  //
  //     try {
  //       const lines = projectModelTo2DLines(root);
  //       emit("model2d", {
  //         lines,
  //         opts: { color: "#8a98a3", lineWidthPx: 1, dash: [4, 7], alpha: 0.5 },
  //       });
  //     } catch (_) {}
  //
  //     fitCameraToAll();
  //   }
  // } catch (_) {
  //   // ignore
  // }
  fitCameraToAll(props.previewOnly ? PREVIEW_VIEW_DIR : null);

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

  canvas.addEventListener("mousedown", onCanvasMouseDown);
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
  canvasEl.value?.removeEventListener?.("mousedown", onCanvasMouseDown);
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
  clearPlaceholderBoxes();

  try {
    axesHelper?.removeFromParent?.();
  } catch (_) {
    // no-op
  }
  axesHelper = null;
});

watch(
  () => props.previewActive,
  (active) => {
    if (!controls || !props.previewOnly) return;
    controls.autoRotate = !!active;
    if (!active) fitCameraToAll(PREVIEW_VIEW_DIR);
  },
  { immediate: true }
);

defineExpose({
  fitCameraToAll,
  fitCameraToSelectionOrAll,
});

</script>

<template>
  <div ref="widgetEl" class="glbWidget" :class="{ 'is-max': isMax, 'is-embedded': embedded }" @mouseenter="$emit('mouseenter')" @mouseleave="$emit('mouseleave')">
    <div v-if="!previewOnly" class="glbWidget__head" dir="rtl">
      <div class="glbWidget__headBtns">
        <button type="button" class="glbWidget__btn" title="کوچک" @click="goSmall">–</button>
        <button type="button" class="glbWidget__btn" title="بزرگ" @click="goMax">□</button>
      </div>
    </div>
    <div ref="hostEl" class="glbWidget__host">
      <canvas ref="canvasEl" class="glbWidget__canvas"></canvas>
      <template v-if="!previewOnly">
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

        <div class="glbWidget__edgeToggle" @mouseenter.stop @mouseleave.stop>
          <button
            type="button"
            class="glbWidget__viewBtn"
            :class="{ 'is-active': showPlaceholderEdges }"
            :title="showPlaceholderEdges ? 'مخفی کردن لبه ها' : 'نمایش لبه ها'"
            @click="togglePlaceholderEdges"
          >
            <span class="glbWidget__edgeIcon">{{ showPlaceholderEdges ? "⬚" : "□" }}</span>
          </button>
        </div>

        <div class="glbWidget__opacity" @mouseenter.stop @mouseleave.stop>
          <span class="glbWidget__opacityValue">0</span>
          <input
            v-model="placeholderOpacity"
            class="glbWidget__opacitySlider"
            type="range"
            min="0"
            max="100"
            step="1"
            @input="syncPlaceholderOpacity"
          />
          <span class="glbWidget__opacityValue">100</span>
        </div>
      </template>
    </div>
  </div>

  <div v-if="showAttrsPanel" class="glbWallAttrs glbWallAttrs--panel" dir="rtl" @mouseenter="$emit('mouseenter')" @mouseleave="$emit('mouseleave')">
    <div class="glbWallAttrs__sticky">
      <div class="glbWallAttrs__head">
        <div class="menuPanel__title glbWallAttrs__title">صفات</div>
        <div class="glbWallAttrs__titleUnit">({{ displayUnitLabel }})</div>
        <div v-if="isGroupEditMode || selectedOrderDesignCount > 1" class="glbWallAttrs__groupLabel">ویرایش گروهی</div>
      </div>
      <div v-if="showOrderDesignTools" class="glbWallAttrs__tools">
        <button type="button" class="glbWallAttrs__toolBtn" title="درب" @click="openDoorAttrsForActiveDesign">
          <img src="/icons/door_styles.png" alt="" class="glbWallAttrs__toolIcon" />
        </button>
        <button type="button" class="glbWallAttrs__toolBtn" title="سه بعدی" @click="focusActiveDesign3d">
          <img src="/icons/3d_viewer.png" alt="" class="glbWallAttrs__toolIcon" />
        </button>
        <button type="button" class="glbWallAttrs__toolBtn" title="داخلی" @click="openInteriorLibraryForActiveDesign">
          <img src="/icons/enternal.png" alt="" class="glbWallAttrs__toolIcon" />
        </button>
      </div>
      <div class="glbWallAttrs__sep"></div>
    </div>

    <template v-if="showOrderDesignAttrPanel">
      <div class="glbWallAttrs__objectTitle glbWallAttrs__objectTitle--design">
        <div v-if="selectedOrderDesignCount > 1" class="glbWallAttrs__objectTitleMain">
          {{ `${selectedOrderDesignCount} طرح سفارش` }}
        </div>
        <div v-else class="glbWallAttrs__designIdentity">
          <div v-if="activeOrderDesignIdentity?.title" class="glbWallAttrs__identityRow">
            <span class="glbWallAttrs__identityLabel">عنوان طرح</span>
            <span class="glbWallAttrs__identityValue">{{ activeOrderDesignIdentity.title }}</span>
          </div>
          <div v-if="activeOrderDesignIdentity?.name" class="glbWallAttrs__identityRow">
            <span class="glbWallAttrs__identityLabel">نام طرح</span>
            <span class="glbWallAttrs__identityValue glbWallAttrs__identityValue--mono">{{ activeOrderDesignIdentity.name }}</span>
          </div>
          <div v-if="activeOrderDesignIdentity?.code" class="glbWallAttrs__identityRow">
            <span class="glbWallAttrs__identityLabel">کد طرح</span>
            <span class="glbWallAttrs__identityValue glbWallAttrs__identityValue--mono">{{ activeOrderDesignIdentity.code }}</span>
          </div>
        </div>
      </div>
      <div v-for="group in orderDesignAttrGroups" :key="group.key" class="glbWallAttrs__attrGroup">
        <button type="button" class="glbWallAttrs__groupToggle" @click="toggleOrderDesignGroup(group.key)">
          <span class="glbWallAttrs__groupTitleRow">
            <img
              v-if="resolveOrderDesignMetaIcon(group.iconPath)"
              :src="resolveOrderDesignMetaIcon(group.iconPath)"
              alt=""
              class="glbWallAttrs__metaIcon glbWallAttrs__metaIcon--group"
              @error="markOrderDesignIconBroken(group.iconPath)"
            />
            <span>{{ group.title }}</span>
          </span>
          <span class="glbWallAttrs__groupCaret">{{ openOrderDesignGroupKey === group.key ? "−" : "+" }}</span>
        </button>
        <div v-if="openOrderDesignGroupKey === group.key" class="glbWallAttrs__editor glbWallAttrs__editor--attrs">
          <label v-for="entry in group.items" :key="entry.key" class="glbWallAttrs__editRow glbWallAttrs__editRow--meta">
            <span class="glbWallAttrs__fieldTitle">{{ entry.label }}</span>
            <div v-if="entry.inputMode === 'binary'" class="glbWallAttrs__fieldBody">
              <div class="glbWallAttrs__binaryRow">
                <button
                  type="button"
                  class="glbWallAttrs__binaryBtn"
                  :class="{ 'is-active': String(entry.value ?? '') === '0' }"
                  @click="patchOrderDesignAttr(entry.key, '0')"
                >
                  <img
                    v-if="resolveOrderDesignMetaIcon(entry.binaryOffIconPath)"
                    :src="resolveOrderDesignMetaIcon(entry.binaryOffIconPath)"
                    alt=""
                    class="glbWallAttrs__metaIcon glbWallAttrs__metaIcon--binary"
                    @error="markOrderDesignIconBroken(entry.binaryOffIconPath)"
                  />
                  <span>{{ entry.binaryOffLabel }}</span>
                </button>
                <button
                  type="button"
                  class="glbWallAttrs__binaryBtn"
                  :class="{ 'is-active': String(entry.value ?? '') === '1' }"
                  @click="patchOrderDesignAttr(entry.key, '1')"
                >
                  <img
                    v-if="resolveOrderDesignMetaIcon(entry.binaryOnIconPath)"
                    :src="resolveOrderDesignMetaIcon(entry.binaryOnIconPath)"
                    alt=""
                    class="glbWallAttrs__metaIcon glbWallAttrs__metaIcon--binary"
                    @error="markOrderDesignIconBroken(entry.binaryOnIconPath)"
                  />
                  <span>{{ entry.binaryOnLabel }}</span>
                </button>
              </div>
            </div>
            <div v-else class="glbWallAttrs__fieldBody">
              <input
                class="glbWallAttrs__input"
                type="text"
                inputmode="decimal"
                :value="entry.displayValue"
                @input="setOrderDesignDraftValue(entry.key, $event.target.value)"
                @blur="commitOrderDesignDraftValue(entry.key, entry)"
                @keydown.enter.prevent="commitOrderDesignDraftValue(entry.key, entry)"
              />
              <span v-if="entry.unitLabel" class="glbWallAttrs__unit">{{ entry.unitLabel }}</span>
              <img
                v-if="resolveOrderDesignMetaIcon(entry.iconPath || group.iconPath)"
                :src="resolveOrderDesignMetaIcon(entry.iconPath || group.iconPath)"
                alt=""
                class="glbWallAttrs__metaIcon"
                @error="markOrderDesignIconBroken(entry.iconPath || group.iconPath)"
              />
            </div>
          </label>
        </div>
        <div class="glbWallAttrs__sep"></div>
      </div>
      <div v-if="!hasOrderDesignAttrs" class="menuPanel__hint glbWallAttrs__hint--soft">برای این طرح هنوز صفتی تعریف نشده است.</div>
    </template>

    <template v-if="showObjectStyleEditor">
      <div v-if="selectedObjectTitle" class="glbWallAttrs__objectTitle">{{ selectedObjectTitle }}</div>
      <div class="glbWallAttrs__editor glbWallAttrs__editor--attrs">
        <label v-if="showLengthField" class="glbWallAttrs__editRow">
          <span class="glbWallAttrs__fieldTitle">{{ lengthFieldLabel }}</span>
          <div class="glbWallAttrs__fieldBody">
            <input
              class="glbWallAttrs__input"
              type="number"
              min="1"
              step="0.1"
              :value="isGroupEditMode ? '' : cmToDisplay(wallMetrics.lengthCm)"
              :disabled="isGroupEditMode"
              @input="patchWallStyleDraft({ lengthCm: displayToCm($event.target.value) })"
            />
            <span class="glbWallAttrs__unit">{{ displayUnitLabel }}</span>
          </div>
        </label>
        <label v-if="showThicknessField" class="glbWallAttrs__editRow">
          <span class="glbWallAttrs__fieldTitle">{{ thicknessFieldLabel }}</span>
          <div class="glbWallAttrs__fieldBody">
            <input
              class="glbWallAttrs__input"
              type="number"
              min="0.1"
              step="0.5"
              :value="cmToDisplay(wallStyleDraft.thicknessCm)"
              @input="patchWallStyleDraft({ thicknessCm: displayToCm($event.target.value) })"
            />
            <span class="glbWallAttrs__unit">{{ displayUnitLabel }}</span>
          </div>
        </label>
        <label v-if="showHeightField" class="glbWallAttrs__editRow">
          <span class="glbWallAttrs__fieldTitle">ارتفاع</span>
          <div class="glbWallAttrs__fieldBody">
            <input
              class="glbWallAttrs__input"
              type="number"
              min="1"
              step="1"
              :value="cmToDisplay(wallStyleDraft.heightCm)"
              @input="patchWallStyleDraft({ heightCm: displayToCm($event.target.value) })"
            />
            <span class="glbWallAttrs__unit">{{ displayUnitLabel }}</span>
          </div>
        </label>
        <label v-if="showFloorDistanceField" class="glbWallAttrs__editRow">
          <span class="glbWallAttrs__fieldTitle">ارتفاع از کف</span>
          <div class="glbWallAttrs__fieldBody">
            <input
              class="glbWallAttrs__input"
              type="number"
              min="0"
              step="0.1"
              :value="cmToDisplay(wallStyleDraft.floorOffsetCm)"
              @input="patchWallStyleDraft({ floorOffsetCm: displayToCm($event.target.value) })"
            />
            <span class="glbWallAttrs__unit">{{ displayUnitLabel }}</span>
          </div>
        </label>
        <label v-if="showColorField" class="glbWallAttrs__editRow">
          <span class="glbWallAttrs__fieldTitle">{{ colorFieldLabel }}</span>
          <div class="glbWallAttrs__fieldBody">
            <input
              class="glbWallAttrs__color"
              type="color"
              :value="wallStyleDraft.color"
              @input="patchWallStyleDraft({ color: $event.target.value })"
            />
          </div>
        </label>
      </div>

      <div class="glbWallAttrs__sep"></div>
    </template>

    <div v-else-if="!showOrderDesignAttrPanel && selectedObjectTitle && hasAnyAttrSelection" class="glbWallAttrs__objectTitle">{{ selectedObjectTitle }}</div>

    <template v-if="showCoordsEditor">
      <div class="menuPanel__title glbWallAttrs__title glbWallAttrs__title--secondary">مختصات</div>
      <div class="glbWallAttrs__editor">
        <div class="glbWallAttrs__pointTitle">جابجایی محوری</div>
        <div class="glbWallAttrs__editRow glbWallAttrs__axisSingleRow">
          <div class="glbWallAttrs__axisInputWrap">
            <input
              class="glbWallAttrs__input glbWallAttrs__moveInput glbWallAttrs__moveInput--axis"
              type="text"
              inputmode="decimal"
              :disabled="selectedEntityCount === 0"
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
              :disabled="selectedEntityCount === 0"
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

    <div v-else-if="!hasAnyAttrSelection" class="menuPanel__hint glbWallAttrs__hint--soft">ترسیم یا طرح سفارش خود را انتخاب نمایید</div>
    <div v-else class="menuPanel__hint glbWallAttrs__hint--soft">برای مورد انتخاب‌شده صفتی نمایش داده نشد.</div>
  </div>
</template>
