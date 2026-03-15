<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { useRoute, useRouter } from "vue-router";
import { editorRef, model2dTransformRef } from "./editor/editor_store.js";
import GlbViewerWidget from "./components/GlbViewerWidget.vue";
import { useDialogService } from "./dialog_service.js";
import { WALL_READY_PRESETS, buildPresetLines, getPresetIconWalls } from "./features/wall_preset_drag.js";
import { CURRENT_ADMIN_ID, PART_KINDS_CATALOG } from "./features/part_kinds_catalog.js";

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
  { id: "beam", icon: "/icons/beam.png", title: "تیر", mapsToTool: "wall" },
  { id: "column", icon: "/icons/column.png", title: "ستون", mapsToTool: null },
];

const wallPresets = WALL_READY_PRESETS;
const presetDrag = ref({ active: false, type: null, preset: null, clientX: 0, clientY: 0, startX: 0, startY: 0, enteredStage: false });
const PRESET_PREVIEW_MIN_DRAG_PX = 12;
const snapMenuItems = [
  { id: "corner", title: "گوشه", icon: "/icons/corner_point.png" },
  { id: "mid", title: "وسط ضلع", icon: "/icons/midpoint.png" },
  { id: "center", title: "مرکز", icon: "/icons/ax_point.png" },
  { id: "edge", title: "لبه", icon: "/icons/edge_snap.png" },
  { id: "wallMagnet", title: "جذب دیوار", icon: "/icons/magnet.png" },
  { id: "ortho", title: "راستا (راست کلیک)", icon: "/icons/ortho_line.png" },
];
const currentAdminId = ref(CURRENT_ADMIN_ID);
const constructionWizardOpen = ref(false);
const constructionStep = ref("part_kinds");
const editablePartKinds = ref(PART_KINDS_CATALOG.map((item) => ({ ...item })));
const editableParamGroups = ref([]);
const constructionLoading = ref(false);
const constructionSavingIds = ref([]);
const constructionDeletingIds = ref([]);
const constructionDeletedPartKindIds = ref([]);
const constructionDeletedParamGroupIds = ref([]);
const constructionImportInputEl = ref(null);
const constructionImportPreviewRows = ref([]);
const constructionImportFileName = ref("");
const constructionTables = [
  { id: "part_kinds", title: "انواع قطعات", status: "active" },
  { id: "param_groups", title: "گروه پارامترها", status: "active" },
  { id: "part_sizes", title: "ابعاد پایه", status: "planned" },
  { id: "joinery_rules", title: "قواعد اتصال", status: "planned" },
  { id: "hardware_sets", title: "ست یراق", status: "planned" },
];
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
const systemPartKindsCount = computed(() => constructionPartKinds.value.filter((item) => item.admin_id === null).length);
const adminPartKindsCount = computed(() => constructionPartKinds.value.filter((item) => item.admin_id === currentAdminId.value).length);
const constructionHasPendingChanges = computed(
  () =>
    constructionDeletedPartKindIds.value.length > 0 ||
    constructionDeletedParamGroupIds.value.length > 0 ||
    editablePartKinds.value.some((item) => !!item.__isNew || !!item.__dirty) ||
    editableParamGroups.value.some((item) => !!item.__isNew || !!item.__dirty)
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

function openConstructionWizard() {
  constructionWizardOpen.value = true;
  constructionStep.value = "part_kinds";
  activeMenu.value = "construction";
  openMenuPanel.value = null;
  openMode.value = "menu";
  loadConstructionPartKinds();
  loadConstructionParamGroups();
  constructionDeletedPartKindIds.value = [];
  constructionDeletedParamGroupIds.value = [];
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
  }
  constructionWizardOpen.value = false;
  if (activeMenu.value === "construction") activeMenu.value = null;
}

function normalizePartKindPayload(item) {
  return {
    admin_id: item.admin_id,
    part_kind_id: Number(item.part_kind_id),
    part_kind_code: String(item.part_kind_code || "").trim(),
    org_part_kind_title: String(item.org_part_kind_title || "").trim(),
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.part_kind_id),
    is_system: !!item.is_system,
  };
}

function toPersianDigits(value) {
  return String(value ?? "").replace(/\d/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
}

function buildPartKindDraft(item, overrides = {}) {
  return {
    ...item,
    ...overrides,
  };
}

function withConstructionDraftState(item) {
  return buildPartKindDraft(item, { __isNew: false, __dirty: false });
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

function normalizeParamGroupPayload(item) {
  return {
    admin_id: item.admin_id,
    param_group_id: Number(item.param_group_id),
    param_group_code: String(item.param_group_code || "").trim(),
    org_param_group_title: String(item.org_param_group_title || "").trim(),
    param_group_icon_path: String(item.param_group_icon_path || "").trim() || null,
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
  return ["part_kind_id", "part_kind_code", "org_part_kind_title", "admin_mode"];
}

function getConstructionCsvRows(items = constructionPartKinds.value) {
  return items.map((item) => [
    Number(item.part_kind_id) || "",
    String(item.part_kind_code || "").trim(),
    String(item.org_part_kind_title || "").trim(),
    item.admin_id === null ? "system" : "admin",
  ]);
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
  if (constructionImportInputEl.value) constructionImportInputEl.value.value = "";
}

function downloadConstructionExcelTemplate() {
  const csv = buildCsvText(getConstructionCsvHeaders(), getConstructionCsvRows());
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8;" });
  const link = document.createElement("a");
  link.href = URL.createObjectURL(blob);
  link.download = "part_kinds_excel_template.csv";
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(link.href);
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
    const previewRows = rows.slice(1).map((row, index) => {
      const partKindId = Number(row[0]);
      const partKindCode = String(row[1] || "").trim();
      const orgPartKindTitle = String(row[2] || "").trim();
      const adminMode = String(row[3] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
      return {
        lineNo: index + 2,
        part_kind_id: partKindId,
        part_kind_code: partKindCode,
        org_part_kind_title: orgPartKindTitle,
        admin_mode: adminMode,
      };
    });
    if (!previewRows.length) throw new Error("empty-file");
    const invalidRow = previewRows.find(
      (row) =>
        !Number.isInteger(row.part_kind_id) ||
        row.part_kind_id < 1 ||
        !row.part_kind_code ||
        !row.org_part_kind_title
    );
    if (invalidRow) {
      throw new Error(`invalid-row-${invalidRow.lineNo}`);
    }
    constructionImportPreviewRows.value = previewRows;
    constructionImportFileName.value = file.name;
  } catch (error) {
    clearConstructionImportPreview();
    showAlert("خواندن فایل اکسل انجام نشد. فقط فایل CSV خروجی همین جدول را آپلود کنید.", { title: "آپلود فایل" });
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

async function loadConstructionPartKinds() {
  constructionLoading.value = true;
  try {
    const url = `/api/part-kinds?admin_id=${encodeURIComponent(currentAdminId.value)}`;
    const res = await fetch(url);
    if (!res.ok) throw new Error("load-failed");
    editablePartKinds.value = (await res.json()).map(withConstructionDraftState);
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
    editableParamGroups.value = (await res.json()).map(withConstructionDraftState);
    constructionDeletedParamGroupIds.value = [];
  } catch (_) {
    showAlert("خواندن جدول گروه پارامترها از دیتابیس انجام نشد.", { title: "خطا" });
  }
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
      code: `param_group_${nextId}`,
      title: `گروه پارامتر ${toPersianDigits(nextId)}`,
      sort_order: nextId,
      is_system: false,
      __isNew: true,
      __dirty: false,
    },
  ];
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

async function saveConstructionParamGroups() {
  if (!(constructionDeletedParamGroupIds.value.length > 0 || editableParamGroups.value.some((item) => !!item.__isNew || !!item.__dirty))) {
    showAlert("تغییری برای ذخیره وجود ندارد.", { title: "ذخیره تغییرات" });
    return;
  }
  if (!validateConstructionParamGroups()) return;
  const ok = await showConfirm("تغییرات جدول گروه پارامترها در دیتابیس ذخیره شود؟", {
    title: "ذخیره تغییرات",
    confirmText: "ذخیره",
    cancelText: "انصراف",
  });
  if (!ok) return;
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
    showAlert("تغییرات جدول گروه پارامترها با موفقیت ذخیره شد.", { title: "ذخیره تغییرات" });
  } catch (_) {
    showAlert("ذخیره تغییرات جدول گروه پارامترها در دیتابیس انجام نشد.", { title: "خطا" });
    await loadConstructionParamGroups();
  } finally {
    constructionSavingIds.value = [];
  }
}

async function applyConstructionImportPreview() {
  if (!constructionImportPreviewRows.value.length) return;
  const ok = await showConfirm("پیش‌نمایش فایل اکسل روی جدول انواع قطعات اعمال شود؟", {
    title: "تایید بروزرسانی",
    confirmText: "اعمال",
    cancelText: "انصراف",
  });
  if (!ok) return;
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
  const selectedWall = selectedWallId ? walls.find((w) => w.id === selectedWallId) : null;
  const selectedHidden = selectedHiddenId ? hiddenWalls.find((w) => w.id === selectedHiddenId) : null;
  const selectedBeam = selectedBeamId ? beams.find((w) => w.id === selectedBeamId) : null;
  const selectedWallCount = selectedWallIds.length > 0 ? selectedWallIds.length : (selectedWallId ? 1 : 0);
  const selectedHiddenCount = selectedHiddenIds.length > 0 ? selectedHiddenIds.length : (selectedHiddenId ? 1 : 0);
  const selectedBeamCount = selectedBeamIds.length > 0 ? selectedBeamIds.length : (selectedBeamId ? 1 : 0);
  const hasWallSelection = !!(selectedWall || selectedWallIds.length > 0);
  const hasHiddenSelection = !!(selectedHidden || selectedHiddenIds.length > 0);
  const hasBeamSelection = !!(selectedBeam || selectedBeamIds.length > 0);
  const selectedSolidEntityType = selectedWall ? getSolidEntityType(selectedWall) : "wall";
  const metricsEntityType = hasBeamSelection ? "beam" : hasWallSelection ? selectedSolidEntityType : hasHiddenSelection ? "hidden" : "wall";
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
        selectedWallIds: metricsEntityType === "hidden" ? selectedHiddenIds : metricsEntityType === "beam" ? selectedBeamIds : selectedWallIds,
      },
      entityType: metricsEntityType,
    },
    state: {
      wallHeightMm: Number.isFinite(s?.wallHeightMm) ? s.wallHeightMm : 2800,
      wallFillColor: (typeof s?.wallFillColor === "string" && s.wallFillColor) ? s.wallFillColor : "#A6A6A6",
      wall3dColor: (typeof s?.wall3dColor === "string" && s.wall3dColor) ? s.wall3dColor : "#C7CCD1",
      beam3dColor: (typeof s?.beam3dColor === "string" && s.beam3dColor) ? s.beam3dColor : "#C7CCD1",
      columnFillColor: (typeof s?.columnFillColor === "string" && s.columnFillColor) ? s.columnFillColor : "#A6A6A6",
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
    const defaultWallColor = (typeof s?.wall3dColor === "string" && s.wall3dColor) ? s.wall3dColor : "#C7CCD1";
    const defaultBeamColor = (typeof s?.beam3dColor === "string" && s.beam3dColor) ? s.beam3dColor : "#C7CCD1";
    const defaultColumnColor = (typeof s?.column3dColor === "string" && s.column3dColor) ? s.column3dColor : "#C7CCD1";
    const defaultColumnWidthCm = (Number.isFinite(Number(s?.columnWidthMm)) ? Number(s.columnWidthMm) : 500) / 10;
    const defaultColumnDepthCm = (Number.isFinite(Number(s?.columnDepthMm)) ? Number(s.columnDepthMm) : 400) / 10;
    const defaultColumnHeightCm = (Number.isFinite(Number(s?.columnHeightMm)) ? Number(s.columnHeightMm) : 2800) / 10;

    const selectedObj = (metricsEntityType === "hidden") ? selectedHidden : selectedWall;
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
          thicknessCm: (Number(selectedObj.thickness) || (fallbackThicknessCm * 10)) / 10,
          heightCm: (Number(selectedObj.heightMm) || (fallbackHeightCm * 10)) / 10,
          lengthCm: fallbackLengthCm,
          floorOffsetCm: (Number(selectedObj.floorOffsetMm) || (fallbackFloorOffsetCm * 10)) / 10,
          color: (typeof selectedObj.color3d === "string" && selectedObj.color3d) ? selectedObj.color3d : fallbackColor,
        }
      : {
          thicknessCm: designMenuTool.value === "column" ? defaultColumnDepthCm : defaultThicknessCm,
          heightCm: designMenuTool.value === "column" ? defaultColumnHeightCm : defaultHeightCm,
          lengthCm: designMenuTool.value === "column" ? defaultColumnWidthCm : null,
          floorOffsetCm: 0,
          color: designMenuTool.value === "column" ? defaultColumnColor : defaultWallColor,
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
      heightCm: (Number(selectedEntity.heightMm)
        || (metricsEntityType === "column" ? Number(s?.columnHeightMm) : Number(s?.wallHeightMm))
        || 3000) / 10,
      floorOffsetCm: (Number(selectedEntity.floorOffsetMm) || 0) / 10,
      lengthCm: lenMm / 10,
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
  const fallbackThickness = entityType === "column" ? 40 : 12;
  const fallbackHeight = entityType === "column" ? 280 : 300;
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
  if (entityType === "column" || Number.isFinite(lengthRaw)) {
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
    || (designMenuTool.value === "column" ? "column" : null)
    || (designMenuTool.value === "beam" ? "beam" : null)
    || "wall";
  const isBeamEntity = /^Beam\s+/i.test(String(selectedWallStyle.value?.name || "").trim());

  // Only update global wall defaults when no wall is selected.
  if (entityType !== "hidden" && !selectedWallStyle.value?.id) {
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

function buildDebugJsonPayload() {
  const full = editorRef.value?.getState?.();
  if (!full) return null;
  const solid = buildSolidDebugBuckets(full);
  const hidden = buildHiddenDebugBucket(full);
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
    uiState: {
      activeTool: activeTool.value,
      designMenuTool: designMenuTool.value,
      wallStyleDraft: wallStyleDraft.value,
      selectedWallStyle: selectedWallStyle.value,
      walls3dSnapshot: walls3dSnapshot.value,
    },
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

  const mode =
    (id === "wall") ? "wall" :
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
  if (constructionWizardOpen.value) {
    closeConstructionWizard();
    scheduleSubRailPosition();
    return;
  }
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

function getEditorStateSnapshot() {
  return editorRef.value?.getState?.()?.state || {};
}

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
  }
}

function startWallPresetDrag(ev, preset) {
  if (!preset || !ev?.isPrimary) return;
  presetDrag.value = {
    active: true,
    type: "wallPreset",
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

function startColumnDrag(ev) {
  if (!ev?.isPrimary) return;
  designMenuTool.value = "column";
  setDraftFromDesignTool("column");
  presetDrag.value = {
    active: true,
    type: "column",
    preset: null,
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

function onPresetPointerUp(ev) {
  const stageRect = stageEl.value?.getBoundingClientRect();
  const inStage = !!stageRect && ev.clientX >= stageRect.left && ev.clientX <= stageRect.right
    && ev.clientY >= stageRect.top && ev.clientY <= stageRect.bottom;
  const dragDx = ev.clientX - (presetDrag.value.startX || ev.clientX);
  const dragDy = ev.clientY - (presetDrag.value.startY || ev.clientY);
  const movedEnough = Math.hypot(dragDx, dragDy) >= PRESET_PREVIEW_MIN_DRAG_PX;

  if (inStage && movedEnough && presetDrag.value.enteredStage) {
    if (presetDrag.value.type === "column") {
      editorRef.value?.placeColumnAtClient?.(ev.clientX, ev.clientY);
    } else if (presetDrag.value.preset) {
      const lines = buildPresetLines(presetDrag.value.preset.kind);
      editorRef.value?.placeWallPresetAtClient?.(lines, ev.clientX, ev.clientY);
    }
  }
  presetDrag.value = { active: false, type: null, preset: null, clientX: 0, clientY: 0, startX: 0, startY: 0, enteredStage: false };
  window.removeEventListener("pointermove", onPresetPointerMove);
  enable2dInput();
}

const presetPreview = computed(() => {
  const drag = presetDrag.value;
  if (!drag.active) return null;
  if (drag.type !== "column" && !drag.preset) return null;

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
    : (walls3dSnapshot.value?.state?.wallFillColor || "#A6A6A6");
  const previewIdBase = drag.type === "column" ? "column-preview" : drag.preset.id;

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
      label: drag.type === "column" ? `C${idx + 1}` : (l.name || `Wall ${idx + 1}`),
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
        <!--
        <button class="iconbtn" title="کپی JSON دیباگ" @click="doCopyWallsJson">
          <img src="/icons/copy.png" alt="" />
        </button>
        -->
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
                  @pointerdown.prevent="it.id === 'column' ? startColumnDrag($event) : null"
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
            @click="constructionStep === 'part_kinds' ? saveConstructionPartKinds() : constructionStep === 'param_groups' ? saveConstructionParamGroups() : null"
          >
            <img src="/icons/construction-save.svg" alt="ذخیره" />
          </button>
          <button
            type="button"
            class="constructionDialog__headIconBtn"
            title="دانلود اکسل"
            :disabled="constructionStep !== 'part_kinds'"
            @click="downloadConstructionExcelTemplate"
          >
            <img src="/icons/construction-download.svg" alt="دانلود" />
          </button>
          <button
            type="button"
            class="constructionDialog__headIconBtn"
            title="آپلود اکسل"
            :disabled="constructionStep !== 'part_kinds'"
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
          <template v-if="constructionStep === 'part_kinds'">
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

            <div v-if="constructionImportPreviewCount" class="constructionDialog__importPreview">
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
                      <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in constructionImportPreviewRows" :key="`${row.lineNo}-${row.part_kind_id}`">
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.part_kind_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--code">{{ row.part_kind_code }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">{{ row.org_part_kind_title }}</td>
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
            </div>

            <div class="constructionDialog__tableWrap">
              <table class="constructionDialog__table">
                <thead>
                  <tr>
                    <th class="constructionDialog__col constructionDialog__col--id">شناسه</th>
                    <th class="constructionDialog__col constructionDialog__col--code">کد</th>
                    <th class="constructionDialog__col constructionDialog__col--title">عنوان</th>
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
                        class="constructionDialog__input constructionDialog__input--mono"
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
                        <span v-if="constructionDeletingIds.includes(String(item.id))" class="constructionDialog__saving">در حال حذف</span>
                        <span v-else-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving">در حال ذخیره</span>
                        <span v-else-if="item.__isNew" class="constructionDialog__saving">جدید</span>
                        <span v-else-if="item.__dirty" class="constructionDialog__saving">ذخیره نشده</span>
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="removeConstructionPartKind(item.id)">×</button>
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
                      <input v-model="item.param_group_code" class="constructionDialog__input constructionDialog__input--mono" type="text" @input="markConstructionParamGroupDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--title">
                      <input v-model="item.org_param_group_title" class="constructionDialog__input" type="text" @input="markConstructionParamGroupDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--uiOrder">
                      <input v-model.number="item.ui_order" class="constructionDialog__input" type="number" min="0" step="1" @input="markConstructionParamGroupDirty(item)" />
                    </td>
                    <td class="constructionDialog__col constructionDialog__col--icon">
                      <input v-model="item.param_group_icon_path" class="constructionDialog__input constructionDialog__input--mono" type="text" placeholder="/icons/..." @input="markConstructionParamGroupDirty(item)" />
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
                        <span v-if="constructionDeletingIds.includes(String(item.id))" class="constructionDialog__saving">در حال حذف</span>
                        <span v-else-if="constructionSavingIds.includes(String(item.id))" class="constructionDialog__saving">در حال ذخیره</span>
                        <span v-else-if="item.__isNew" class="constructionDialog__saving">جدید</span>
                        <span v-else-if="item.__dirty" class="constructionDialog__saving">ذخیره نشده</span>
                        <button type="button" class="constructionDialog__iconBtn" title="حذف" @click="deleteConstructionParamGroup(item.id)">×</button>
                      </div>
                    </td>
                  </tr>
                </tbody>
              </table>
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
