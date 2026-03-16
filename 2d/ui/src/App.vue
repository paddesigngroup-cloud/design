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
const editableTemplates = ref([]);
const editableCategories = ref([]);
const editablePartKinds = ref(PART_KINDS_CATALOG.map((item) => ({ ...item })));
const editableParamGroups = ref([]);
const editableParams = ref([]);
const editableSubCategories = ref([]);
const editableBaseFormulas = ref([]);
const editablePartFormulas = ref([]);
const subCategoryDefaultsEditorOpen = ref(false);
const subCategoryDefaultsEditorRowId = ref(null);
const subCategoryDefaultsEditorDraft = ref({});
const subCategoryDefaultsActiveGroupId = ref("");
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
const constructionDeletedBaseFormulaIds = ref([]);
const constructionDeletedPartFormulaIds = ref([]);
const constructionImportInputEl = ref(null);
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
const systemPartKindsCount = computed(() => constructionPartKinds.value.filter((item) => item.admin_id === null).length);
const adminPartKindsCount = computed(() => constructionPartKinds.value.filter((item) => item.admin_id === currentAdminId.value).length);
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
    sort_order: Number.isFinite(Number(item.sort_order)) ? Number(item.sort_order) : Number(item.cat_id),
    is_system: !!item.is_system,
  };
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
  };
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

function normalizeIconFileName(value) {
  const text = String(value ?? "").trim();
  if (!text) return "";
  return text.split("?")[0].split("/").pop() || "";
}

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

function isUploadingParamGroupIcon(item) {
  return String(constructionUploadingIconRowId.value || "") === String(item?.id || "");
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
        editableParamGroups.value
          .map((item) => normalizeIconFileName(item?.param_group_icon_path))
          .filter((value) => isStagedParamGroupIcon(value))
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
    param_group_icon_path: normalizeIconFileName(item.param_group_icon_path) || null,
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

function toggleConstructionSubCategoryScope(item) {
  item.admin_id = item.admin_id === null ? currentAdminId.value : null;
  item.is_system = item.admin_id === null;
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
  for (const column of constructionSubCategoryParamColumns.value) {
    if (!(column.key in item.param_defaults)) {
      item.param_defaults[column.key] = "";
    }
  }
  return item;
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
  subCategoryDefaultsEditorRowId.value = item.id;
  subCategoryDefaultsEditorDraft.value = Object.fromEntries(
    constructionSubCategoryParamColumns.value.map((column) => [
      column.key,
      String(item.param_defaults?.[column.key] ?? ""),
    ])
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
  const changed = constructionSubCategoryParamColumns.value.some(
    (column) => String(original[column.key] ?? "").trim() !== String(subCategoryDefaultsEditorDraft.value?.[column.key] ?? "").trim()
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
  subCategoryDefaultsActiveGroupId.value = "";
}

function applySubCategoryDefaultsEditor() {
  const row = activeSubCategoryDefaultsRow.value;
  if (!row) return;
  ensureSubCategoryParamDefaults(row);
  for (const column of constructionSubCategoryParamColumns.value) {
    row.param_defaults[column.key] = String(subCategoryDefaultsEditorDraft.value?.[column.key] ?? "").trim();
  }
  markConstructionSubCategoryDirty(row);
  subCategoryDefaultsEditorOpen.value = false;
  subCategoryDefaultsEditorRowId.value = null;
  subCategoryDefaultsEditorDraft.value = {};
  subCategoryDefaultsActiveGroupId.value = "";
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
    return ["temp_id", "cat_id", "cat_title", "admin_mode"];
  }
  if (constructionStep.value === "sub_categories") {
    return ["temp_id", "cat_id", "sub_cat_id", "sub_cat_title", ...constructionSubCategoryParamColumns.value.map((item) => item.key), "admin_mode"];
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
    return ["param_group_id", "param_group_code", "org_param_group_title", "param_group_icon_path", "ui_order", "admin_mode"];
  }
  return ["part_kind_id", "part_kind_code", "org_part_kind_title", "admin_mode"];
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
      ...constructionSubCategoryParamColumns.value.map((column) => String(item.param_defaults?.[column.key] ?? "").trim()),
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
        item.admin_id === null ? "system" : "admin",
      ]);
  }
  const rows = items || constructionPartKinds.value;
  return rows.map((item) => [
    Number(item.part_kind_id) || "",
    String(item.part_kind_code || "").trim(),
    String(item.org_part_kind_title || "").trim(),
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
        const adminMode = String(row[3] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
        return {
          lineNo: index + 2,
          temp_id: tempId,
          cat_id: catId,
          cat_title: catTitle,
          admin_mode: adminMode,
        };
      });
    } else if (constructionStep.value === "sub_categories") {
      const adminModeIndex = 4 + constructionSubCategoryParamColumns.value.length;
      previewRows = rows.slice(1).map((row, index) => {
        const paramDefaults = {};
        constructionSubCategoryParamColumns.value.forEach((column, paramIndex) => {
          paramDefaults[column.key] = String(row[4 + paramIndex] || "").trim();
        });
        return {
          lineNo: index + 2,
          temp_id: Number(row[0]),
          cat_id: Number(row[1]),
          sub_cat_id: Number(row[2]),
          sub_cat_title: String(row[3] || "").trim(),
          param_defaults: paramDefaults,
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
        const adminMode = String(row[5] || "admin").trim().toLowerCase() === "system" ? "system" : "admin";
        return {
          lineNo: index + 2,
          param_group_id: paramGroupId,
          param_group_code: paramGroupCode,
          org_param_group_title: orgTitle,
          param_group_icon_path: normalizeIconFileName(iconPath),
          ui_order: uiOrder,
          admin_mode: adminMode,
        };
      });
    } else {
      previewRows = rows.slice(1).map((row, index) => {
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
            !Number.isFinite(row.ui_order)
        )
      : previewRows.find(
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
    };
    if (!existing) {
      return ensureSubCategoryParamDefaults(buildPartKindDraft(nextPayload, {
        id: `draft-sub-category-${Date.now()}-${index}`,
        __isNew: true,
        __dirty: false,
      }));
    }
    const existingDefaults = existing.param_defaults || {};
    const changed =
      existing.admin_id !== nextPayload.admin_id ||
      Number(existing.temp_id) !== nextPayload.temp_id ||
      Number(existing.cat_id) !== nextPayload.cat_id ||
      Number(existing.sub_cat_id) !== nextPayload.sub_cat_id ||
      String(existing.sub_cat_title || "").trim() !== nextPayload.sub_cat_title ||
      Number(existing.sort_order) !== nextPayload.sort_order ||
      !!existing.is_system !== nextPayload.is_system ||
      constructionSubCategoryParamColumns.value.some((column) => String(existingDefaults[column.key] ?? "").trim() !== String(nextPayload.param_defaults[column.key] ?? "").trim());
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
    editableCategories.value = (await res.json()).map(withConstructionDraftState);
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
    editableParamGroups.value = (await res.json()).map((item) =>
      withConstructionDraftState({
        ...item,
        param_group_icon_path: normalizeIconFileName(item.param_group_icon_path),
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
    editableParams.value = (await res.json()).map(withConstructionDraftState);
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
      param_defaults: {},
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

function addConstructionParam() {
  const nextId = editableParams.value.reduce((max, item) => Math.max(max, Number(item.param_id) || 0), 0) + 1;
  editableParams.value = [
    ...editableParams.value,
    {
      id: `draft-param-row-${Date.now()}-${nextId}`,
      admin_id: currentAdminId.value,
      param_id: nextId,
      part_kind_id: 1,
      param_code: `param_${nextId}`,
      param_title_en: `param_${nextId}`,
      param_title_fa: `پارامتر ${toPersianDigits(nextId)}`,
      param_group_id: 1,
      ui_order: 1,
      code: `param_${nextId}`,
      title: `پارامتر ${toPersianDigits(nextId)}`,
      sort_order: nextId,
      is_system: false,
      __isNew: true,
      __dirty: false,
    },
  ];
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
    showAlert(options.successMessage || "تغییرات جدول دسته‌بندی‌ها با موفقیت ذخیره شد.", {
      title: options.successTitle || "ذخیره تغییرات",
    });
  } catch (_) {
    showAlert("ذخیره تغییرات جدول دسته‌بندی‌ها در دیتابیس انجام نشد.", { title: "خطا" });
    await loadConstructionCategories();
    await loadConstructionSubCategories();
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
      if (!res.ok) throw new Error("delete-failed");
    }
    for (const item of editableSubCategories.value.filter((row) => row.__isNew)) {
      const res = await fetch("/api/sub-categories", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeSubCategoryPayload(item)),
      });
      if (!res.ok) throw new Error("create-failed");
    }
    for (const item of editableSubCategories.value.filter((row) => !row.__isNew && row.__dirty)) {
      const res = await fetch(`/api/sub-categories/${encodeURIComponent(String(item.id))}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(normalizeSubCategoryPayload(item)),
      });
      if (!res.ok) throw new Error("save-failed");
    }
    await loadConstructionSubCategories();
    showAlert(options.successMessage || "تغییرات جدول ساب‌کت‌ها با موفقیت ذخیره شد.", {
      title: options.successTitle || "ذخیره تغییرات",
    });
  } catch (_) {
    showAlert("ذخیره تغییرات جدول ساب‌کت‌ها در دیتابیس انجام نشد.", { title: "خطا" });
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
                      <th class="constructionDialog__col constructionDialog__col--scope">نوع مالک</th>
                    </tr>
                  </thead>
                  <tbody>
                    <tr v-for="row in constructionImportPreviewRows" :key="`${row.lineNo}-${row.cat_id}`">
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.temp_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--id">{{ row.cat_id }}</td>
                      <td class="constructionDialog__col constructionDialog__col--title">{{ row.cat_title }}</td>
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
                  <tr v-for="item in constructionParams" :key="item.id">
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
                      <button type="button" class="constructionDialog__defaultsBtn" @click="openSubCategoryDefaultsEditor(item)">
                        <span class="constructionDialog__defaultsBtnValue">{{ getSubCategoryDefaultsSummary(item).text }}</span>
                        <span class="constructionDialog__defaultsBtnLabel">ویرایش پیش‌فرض‌ها</span>
                      </button>
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
                      <input v-model.number="item.part_kind_id" class="constructionDialog__input" type="number" min="1" step="1" @input="markConstructionPartFormulaDirty(item)" />
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
            <input v-model.number="baseFormulaBuilderDraft.part_kind_id" class="constructionDialog__input" type="number" min="1" step="1" />
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
      <div class="formulaBuilder__head">
        <div class="constructionDialog__sectionTitle formulaBuilder__title">پیش‌فرض‌های ساب‌کت</div>
        <button type="button" class="constructionDialog__close formulaBuilder__close" title="بستن" @click="closeSubCategoryDefaultsEditor">×</button>
      </div>
      <div class="constructionDialog__sectionHint">
        {{ activeSubCategoryDefaultsRow?.sub_cat_title || "ساب‌کت" }} -
        {{ activeSubCategoryDefaultsRow ? `${toPersianDigits(activeSubCategoryDefaultsRow.temp_id)} / ${toPersianDigits(activeSubCategoryDefaultsRow.cat_id)} / ${toPersianDigits(activeSubCategoryDefaultsRow.sub_cat_id)}` : "" }}
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
                <img v-if="group.iconUrl" :src="group.iconUrl" :alt="group.title" class="subCategoryDefaults__groupIcon" />
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
            <label v-for="column in activeSubCategoryDefaultsGroup.items" :key="column.key" class="subCategoryDefaults__node">
              <div class="subCategoryDefaults__nodeHead">
                <span class="subCategoryDefaults__label">{{ column.label || column.key }}</span>
                <span class="subCategoryDefaults__code">{{ column.key }}</span>
              </div>
              <input
                v-model="subCategoryDefaultsEditorDraft[column.key]"
                class="constructionDialog__input constructionDialog__input--mono subCategoryDefaults__input"
                type="text"
              />
            </label>
          </div>
        </div>
      </div>
      <div class="appDialog__actions">
        <button type="button" class="constructionDialog__textBtn" @click="closeSubCategoryDefaultsEditor">انصراف</button>
        <button type="button" class="constructionDialog__textBtn is-primary" @click="applySubCategoryDefaultsEditor">اعمال</button>
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
