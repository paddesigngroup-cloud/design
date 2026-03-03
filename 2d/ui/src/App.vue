<script setup>
import { computed, onBeforeUnmount, onMounted, ref } from "vue";
import { useRoute, useRouter } from "vue-router";
import { editorRef, model2dTransformRef } from "./editor/editor_store.js";
import GlbViewerWidget from "./components/GlbViewerWidget.vue";

const activeTool = ref("select");
const snapOn = ref(true);
const showDimensions = ref(true);
const showOffsetWalls = ref(true);
const stepDrawMode = ref("line"); // "line" | "degree"
const snapModes = ref({
  corner: true,
  mid: true,
  center: true,
  edge: true,
});
const quickMenuOpen = ref(null); // "snaps" | "steps" | null
const activeMenu = ref(null); // menuId | null
const openMenuPanel = ref(null); // menuId | null
const drawUiLock = ref(false); // while drawing, keep submenus closed until Esc
const designMenuTool = ref(null); // "wall" | "hidden" | "dimension" | "beam" | "column" | null

const topbarEl = ref(null);
const mainEl = ref(null);
const stageEl = ref(null);
const homeBtnEl = ref(null);
const menuPanelEl = ref(null);
const mainMenuBtnEl = ref(null);
const designBtnEl = ref(null);
const catalogBtnEl = ref(null);

const route = useRoute();
const router = useRouter();
const isSettings = computed(() => route.path === "/settings");
const isHome = computed(() => route.path === "/");

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
  { id: "hidden", icon: "/icons/drawing_hidden_wall.png", title: "هیدن وال", mapsToTool: "hidden" },
  { id: "dimension", icon: "/icons/drawing_dimension.png", title: "دایمنشن", mapsToTool: "dimension" },
  { id: "beam", icon: "/icons/beam.png", title: "تیر", mapsToTool: null },
  { id: "column", icon: "/icons/column.png", title: "ستون", mapsToTool: null },
];

const wallPresets = [
  { id: "rect", title: "مستطیل", kind: "rect" },
  { id: "l1", title: "L", kind: "l1" },
  { id: "l2", title: "L2", kind: "l2" },
  { id: "u1", title: "U", kind: "u1" },
  { id: "u2", title: "U2", kind: "u2" },
  { id: "c1", title: "C", kind: "c1" },
  { id: "c2", title: "C2", kind: "c2" },
  { id: "diag1", title: "مورب", kind: "diag1" },
  { id: "diag2", title: "مورب2", kind: "diag2" },
  { id: "oct1", title: "۸ضلعی", kind: "oct1" },
  { id: "oct2", title: "۸ضلعی2", kind: "oct2" },
  { id: "mix1", title: "ترکیبی", kind: "mix1" },
];
const snapMenuItems = [
  { id: "corner", title: "گوشه ها", icon: "/icons/corner_point.png" },
  { id: "mid", title: "وسط ضلع", icon: "/icons/midpoint.png" },
  { id: "center", title: "آکس وسط", icon: "/icons/ax_point.png" },
  { id: "edge", title: "لبه", icon: "/icons/edge_snap.png" },
];

function applyEditorPatch(patch) {
  editorRef.value?.setState?.(patch);
}

function syncQuickStateFromEditor() {
  const s = editorRef.value?.getState?.()?.state;
  if (!s) return;
  snapOn.value = !!s.snapOn;
  showDimensions.value = s.showDimensions !== false;
  showOffsetWalls.value = !!s.offsetWallEnabled;
  stepDrawMode.value = (s.stepDrawMode === "degree") ? "degree" : "line";
  snapModes.value = {
    corner: s.snapCornerEnabled !== false,
    mid: s.snapMidEnabled !== false,
    center: s.snapCenterEnabled !== false,
    edge: s.snapEdgeEnabled !== false,
  };
}

function toggleQuickMenu(menuId) {
  quickMenuOpen.value = quickMenuOpen.value === menuId ? null : menuId;
}

function closeQuickMenus() {
  quickMenuOpen.value = null;
}

function toggleDimensions() {
  const next = !showDimensions.value;
  showDimensions.value = next;
  applyEditorPatch({ showDimensions: next });
}

function toggleOffsets() {
  const next = !showOffsetWalls.value;
  showOffsetWalls.value = next;
  applyEditorPatch({ offsetWallEnabled: next });
}

function toggleSnapMaster() {
  const next = !snapOn.value;
  snapOn.value = next;
  editorRef.value?.setSnapOn?.(next);
  if (next) {
    applyEditorPatch({ snapOn: true });
  }
}

function toggleSnapMode(id) {
  const next = !snapModes.value[id];
  snapModes.value = { ...snapModes.value, [id]: next };
  const patch = {};
  if (id === "corner") patch.snapCornerEnabled = next;
  else if (id === "mid") patch.snapMidEnabled = next;
  else if (id === "center") patch.snapCenterEnabled = next;
  else if (id === "edge") patch.snapEdgeEnabled = next;
  applyEditorPatch(patch);
}

function setStepMode(mode) {
  const m = mode === "degree" ? "degree" : "line";
  stepDrawMode.value = m;
  applyEditorPatch({ stepDrawMode: m });
  closeQuickMenus();
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

function doNewDesign() {
  if (!editorRef.value) return;
  if (!isEditorEmpty()) {
    const ok = window.confirm("طرح فعلی ذخیره نشده است. بدون ذخیره پاک شود؟");
    if (!ok) return;
  }
  editorRef.value.clearAll?.();
  editorRef.value.goOrigin?.();
}

function doSaveProject() {
  if (!editorRef.value) return;
  const state = getEditorState();
  if (!state) return;
  const name = (window.prompt("نام طرح را وارد کنید:", "طرح جدید") || "").trim();
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
function doDeleteProject(p) {
  projects.value = projects.value.filter((x) => x.id !== p.id);
  saveProjects();
}

async function doExportJsonToClipboard() {
  const s = getEditorState();
  if (!s) return;
  const txt = JSON.stringify(s);
  try {
    await navigator.clipboard.writeText(txt);
    window.alert("خروجی JSON در کلیپ‌بورد کپی شد.");
  } catch (_) {
    window.prompt("کپی نشد. متن زیر را کپی کنید:", txt);
  }
}

function doPrint() {
  window.print();
}

function doMessages() {
  window.alert("پیام‌ها: به زودی.");
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
  window.alert("سفارش خدمات برش: به زودی.");
}
function doBuyFromTopbar() {
  window.alert("سفارش پیش ساخته: به زودی.");
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

  const isDrawingTool = tool === "wall" || tool === "hidden" || tool === "dimension";
  if (route.path !== "/" && isDrawingTool) {
    await router.push("/");
  }

  if (tool === "wall") editorRef.value?.setActiveTool?.("wall");
  else if (tool === "hidden") editorRef.value?.setActiveTool?.("hidden");
  else if (tool === "dimension") editorRef.value?.setActiveTool?.("dim");
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
  router.push("/settings");
}

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

function toggleMenu(menuId, e) {
  // While drawing, keep submenus closed (AutoCAD-like).
  if (drawUiLock.value) return;
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
  if (!topbarEl.value || !stageEl.value || !homeBtnEl.value) return;
  const stageRect = stageEl.value.getBoundingClientRect();
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
    if (drawUiLock.value) return;
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
                  @click="setDesignMenuTool(it.id)"
                >
                  <img :src="it.icon" alt="" />
                </button>
                <!-- keep 2x3 grid: add one empty cell -->
                <div class="designToolBtn designToolBtn--empty" aria-hidden="true"></div>
              </div>

              <div class="designMenu__sep" role="separator"></div>

              <div class="designMenu__presetsHead">مدل های آماده دیوار</div>
              <div class="designMenu__presets" aria-label="Wall Presets">
                <button
                  v-for="p in wallPresets"
                  :key="p.id"
                  type="button"
                  class="presetTile"
                  :title="p.title"
                >
                  <svg class="presetTile__svg" viewBox="0 0 44 44" aria-hidden="true">
                    <g fill="none" stroke="rgba(52,20,31,.72)" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                      <path v-if="p.kind==='rect'" d="M10 10H34V34H10Z" />
                      <path v-else-if="p.kind==='l1'" d="M12 10V34H34" />
                      <path v-else-if="p.kind==='l2'" d="M10 12H28V34" />
                      <path v-else-if="p.kind==='u1'" d="M12 10V34H34V10" />
                      <path v-else-if="p.kind==='u2'" d="M10 14V34H34V14" />
                      <path v-else-if="p.kind==='c1'" d="M34 12H16V32H34" />
                      <path v-else-if="p.kind==='c2'" d="M30 10H14V34H30" />
                      <path v-else-if="p.kind==='diag1'" d="M10 30L30 10H34V34H10Z" />
                      <path v-else-if="p.kind==='diag2'" d="M10 10H34V28L28 34H10Z" />
                      <path v-else-if="p.kind==='oct1'" d="M16 10H28L34 16V28L28 34H16L10 28V16Z" />
                      <path v-else-if="p.kind==='oct2'" d="M18 10H26L34 18V26L26 34H18L10 26V18Z" />
                      <path v-else d="M10 12H30V22H22V34H10Z" />
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
        <div class="stage__card">
          <div v-if="isHome" class="stageQuickBar" @mouseenter="disable2dInput" @mouseleave="enable2dInput">
            <button class="iconbtn iconbtn--sm stageQuickBar__btn" title="تنظیمات" @click="goSettings">
              <img src="/icons/setting.png" alt="" />
            </button>

            <button
              class="iconbtn iconbtn--sm stageQuickBar__btn"
              :class="{ 'is-active': showDimensions }"
              title="نمایش دایمنشن"
              @click="toggleDimensions"
            >
              <img src="/icons/turn_dim.png" alt="" />
            </button>

            <button
              class="iconbtn iconbtn--sm stageQuickBar__btn"
              :class="{ 'is-active': showOffsetWalls }"
              title="نمایش آفست دیوار"
              @click="toggleOffsets"
            >
              <img src="/icons/turn_offset.png" alt="" />
            </button>

            <div class="stageQuickBar__ddWrap">
              <button
                class="iconbtn iconbtn--sm stageQuickBar__btn"
                :class="{ 'is-active': quickMenuOpen === 'snaps' }"
                title="اسنپ ها"
                @click="toggleQuickMenu('snaps')"
              >
                <img src="/icons/turn_snaps.png" alt="" />
              </button>
              <div v-if="quickMenuOpen === 'snaps'" class="stageQuickDrop">
                <div class="stageQuickDrop__head">
                  <span>Snap</span>
                  <button type="button" class="stageQuickDrop__headBtn" @click="toggleSnapMaster">
                    {{ snapOn ? "خاموش" : "روشن" }}
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
                :class="{ 'is-active': quickMenuOpen === 'steps' }"
                title="رسم مرحله ای"
                @click="toggleQuickMenu('steps')"
              >
                <img src="/icons/turn_steps.png" alt="" />
              </button>
              <div v-if="quickMenuOpen === 'steps'" class="stageQuickDrop stageQuickDrop--steps">
                <button
                  type="button"
                  class="stepModeBtn"
                  :class="{ 'is-active': stepDrawMode === 'line' }"
                  @click="setStepMode('line')"
                >
                  <img src="/icons/step_line.png" alt="" />
                  <span>رسم خط</span>
                </button>
                <button
                  type="button"
                  class="stepModeBtn"
                  :class="{ 'is-active': stepDrawMode === 'degree' }"
                  @click="setStepMode('degree')"
                >
                  <img src="/icons/step_degree.png" alt="" />
                  <span>رسم زاویه ای</span>
                </button>
              </div>
            </div>
          </div>

          <RouterView v-slot="{ Component }">
            <KeepAlive>
              <component :is="Component" />
            </KeepAlive>
          </RouterView>

          <GlbViewerWidget
            src="/models/1_z1.glb"
            :model2d-transform="model2dTransformRef"
            @model2d="onGlbModel2d"
            @mouseenter="disable2dInput"
            @mouseleave="enable2dInput"
          />

          <div class="stageBottom" aria-label="Stage Bottom Bar" @mouseenter="disable2dInput" @mouseleave="enable2dInput">
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
</template>
