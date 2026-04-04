<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import { formatInteriorDimensionValue } from "../features/interior_library_annotations.js";

const props = defineProps({
  displayUnit: { type: String, default: "cm" },
});

const emit = defineEmits(["close"]);

const DEFAULT_VIEWPORT = { width: 920, height: 620 };
const FRAME_PADDING_MM = 240;
const CONTROLLER_MIN_WIDTH_MM = 240;
const CONTROLLER_MIN_HEIGHT_MM = 180;
const ZOOM_MIN = 0.65;
const ZOOM_MAX = 3.2;

function createDefaultControllerBindings() {
  return {
    left: { bindingType: null, bindingKey: null, formulaKey: null },
    top: { bindingType: null, bindingKey: null, formulaKey: null },
    right: { bindingType: null, bindingKey: null, formulaKey: null },
    bottomOffset: { bindingType: null, bindingKey: null, formulaKey: null },
  };
}

function createDefaultGeometryState() {
  const frameRect = { x: 240, y: 140, w: 2200, h: 1600 };
  const innerHeight = 360;
  const bottomOffset = 90;
  return {
    frameRect,
    innerRect: {
      x: frameRect.x,
      y: frameRect.y + frameRect.h - bottomOffset - innerHeight,
      w: frameRect.w,
      h: innerHeight,
    },
    selected: false,
    hoveredController: "",
    editingController: "",
    controllerBindings: createDefaultControllerBindings(),
  };
}

const wrapEl = ref(null);
const svgEl = ref(null);
const viewport = ref({ ...DEFAULT_VIEWPORT });
const zoom = ref(1);
const pan = ref({ x: 0, y: 0 });
const geometryState = ref(createDefaultGeometryState());
const pointerState = ref({
  mode: "idle",
  pointerId: null,
  controllerId: "",
  startPoint: null,
  startRect: null,
  startPan: null,
  pointerToAnchor: null,
});
const hoveredRect = ref(false);
const cursorPoint = ref(null);
const inputDraft = ref("");

let viewportObserver = null;
let lastControllerPointerDown = { id: "", at: 0 };

const normalizedDisplayUnit = computed(() => {
  const unit = String(props.displayUnit || "cm").trim().toLowerCase();
  return unit === "mm" || unit === "inch" ? unit : "cm";
});

const unitLabel = computed(() => (
  normalizedDisplayUnit.value === "mm" ? "mm" : (normalizedDisplayUnit.value === "inch" ? "inch" : "cm")
));

const baseBounds = computed(() => {
  const frame = geometryState.value.frameRect;
  return {
    x: frame.x - FRAME_PADDING_MM,
    y: frame.y - FRAME_PADDING_MM,
    w: frame.w + FRAME_PADDING_MM * 2,
    h: frame.h + FRAME_PADDING_MM * 2,
  };
});

const viewBoxRect = computed(() => {
  const bounds = baseBounds.value;
  const nextZoom = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Number(zoom.value) || 1));
  const width = bounds.w / nextZoom;
  const height = bounds.h / nextZoom;
  return {
    x: bounds.x + ((bounds.w - width) * 0.5) + (Number(pan.value?.x) || 0),
    y: bounds.y + ((bounds.h - height) * 0.5) + (Number(pan.value?.y) || 0),
    width,
    height,
  };
});

const viewBox = computed(() => {
  const rect = viewBoxRect.value;
  return `${rect.x} ${rect.y} ${rect.width} ${rect.height}`;
});

const visualScale = computed(() => 1 / Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Number(zoom.value) || 1)));
const innerRect = computed(() => ({ ...(geometryState.value.innerRect || {}) }));
const frameRect = computed(() => ({ ...(geometryState.value.frameRect || {}) }));

const controllerValues = computed(() => {
  const frame = frameRect.value;
  const inner = innerRect.value;
  return {
    left: Math.max(0, inner.x - frame.x),
    top: Math.max(0, inner.h),
    right: Math.max(0, (frame.x + frame.w) - (inner.x + inner.w)),
    bottomOffset: Math.max(0, (frame.y + frame.h) - (inner.y + inner.h)),
  };
});

function toPersianDigits(value) {
  return String(value ?? "").replace(/\d/g, (digit) => "۰۱۲۳۴۵۶۷۸۹"[Number(digit)]);
}

function normalizeNumericText(value) {
  return String(value ?? "")
    .trim()
    .replace(/[۰-۹]/g, (digit) => String("۰۱۲۳۴۵۶۷۸۹".indexOf(digit)))
    .replace(/[٫،]/g, ".");
}

function formatControllerRawValue(valueMm) {
  const numeric = Math.max(0, Number(valueMm) || 0);
  if (normalizedDisplayUnit.value === "mm") return String(Math.round(numeric));
  if (normalizedDisplayUnit.value === "inch") return (numeric / 25.4).toFixed(2);
  return (numeric / 10).toFixed(1);
}

function formatControllerDisplayValue(valueMm) {
  return `${formatControllerRawValue(valueMm)} ${unitLabel.value}`;
}

function parseControllerInputToMm(value) {
  const numeric = Number.parseFloat(normalizeNumericText(value));
  if (!Number.isFinite(numeric)) return null;
  if (normalizedDisplayUnit.value === "mm") return numeric;
  if (normalizedDisplayUnit.value === "inch") return numeric * 25.4;
  return numeric * 10;
}

function getBottom(rect) {
  return (Number(rect?.y) || 0) + (Number(rect?.h) || 0);
}

function getRight(rect) {
  return (Number(rect?.x) || 0) + (Number(rect?.w) || 0);
}

function sanitizeInnerRect(rect) {
  const frame = frameRect.value;
  const frameRight = frame.x + frame.w;
  const frameBottom = frame.y + frame.h;
  let left = Number(rect?.x) || frame.x;
  let width = Number(rect?.w) || frame.w;
  let top = Number(rect?.y) || frame.y;
  let height = Number(rect?.h) || CONTROLLER_MIN_HEIGHT_MM;
  width = Math.max(CONTROLLER_MIN_WIDTH_MM, Math.min(width, frame.w));
  height = Math.max(CONTROLLER_MIN_HEIGHT_MM, Math.min(height, frame.h));
  left = Math.max(frame.x, Math.min(left, frameRight - width));
  top = Math.max(frame.y, Math.min(top, frameBottom - height));
  if (left + width > frameRight) width = Math.max(CONTROLLER_MIN_WIDTH_MM, frameRight - left);
  if (top + height > frameBottom) height = Math.max(CONTROLLER_MIN_HEIGHT_MM, frameBottom - top);
  return { x: left, y: top, w: width, h: height };
}

function updateInnerRect(nextRect) {
  geometryState.value = { ...geometryState.value, innerRect: sanitizeInnerRect(nextRect) };
}

function setHoveredController(controllerId) {
  geometryState.value = { ...geometryState.value, hoveredController: String(controllerId || "").trim() };
}

function setEditingController(controllerId) {
  geometryState.value = { ...geometryState.value, editingController: String(controllerId || "").trim() };
}

function clearEditingController() {
  if (!geometryState.value.editingController) return;
  geometryState.value = { ...geometryState.value, editingController: "" };
}

const controllerVisuals = computed(() => {
  if (!geometryState.value.selected) return [];
  const inner = innerRect.value;
  const scale = visualScale.value;
  const horizontal = { w: 810 * scale, h: 252 * scale, inputW: 180 * scale, inputH: 51 * scale };
  const vertical = { w: 252 * scale, h: 810 * scale, inputW: 180 * scale, inputH: 51 * scale };
  return [
    {
      id: "left",
      kind: "horizontal",
      direction: "left",
      anchor: { x: inner.x, y: inner.y + (inner.h * 0.5) },
      x: inner.x - (horizontal.w * 0.5),
      y: inner.y + (inner.h * 0.5) - (horizontal.h * 0.5),
      ...horizontal,
    },
    {
      id: "top",
      kind: "vertical",
      direction: "up",
      anchor: { x: inner.x + (inner.w * 0.5), y: inner.y },
      x: inner.x + (inner.w * 0.5) - (vertical.w * 0.5),
      y: inner.y - (vertical.h * 0.5),
      ...vertical,
    },
    {
      id: "right",
      kind: "horizontal",
      direction: "right",
      anchor: { x: inner.x + inner.w, y: inner.y + (inner.h * 0.5) },
      x: inner.x + inner.w - (horizontal.w * 0.5),
      y: inner.y + (inner.h * 0.5) - (horizontal.h * 0.5),
      ...horizontal,
    },
    {
      id: "bottomOffset",
      kind: "vertical",
      direction: "up",
      anchor: { x: inner.x + (inner.w * 0.5), y: inner.y + inner.h },
      x: inner.x + (inner.w * 0.5) - (vertical.w * 0.5),
      y: inner.y + inner.h - (vertical.h * 0.5),
      ...vertical,
    },
  ];
});

function buildHorizontalArrowPath(direction, x, y, width, height) {
  const pad = height * 0.22;
  const head = height * 0.55;
  const startX = direction === "left" ? x + width - pad : x + pad;
  const endX = direction === "left" ? x + pad : x + width - pad;
  const centerY = y + height * 0.5;
  const topY = centerY - height * 0.22;
  const bottomY = centerY + height * 0.22;
  const headTop = centerY - head * 0.5;
  const headBottom = centerY + head * 0.5;
  if (direction === "left") {
    return `M ${startX} ${topY} L ${x + head} ${topY} L ${x + head} ${headTop} L ${x + pad} ${centerY} L ${x + head} ${headBottom} L ${x + head} ${bottomY} L ${startX} ${bottomY} Z`;
  }
  return `M ${startX} ${topY} L ${endX - head} ${topY} L ${endX - head} ${headTop} L ${endX} ${centerY} L ${endX - head} ${headBottom} L ${endX - head} ${bottomY} L ${startX} ${bottomY} Z`;
}

function buildVerticalArrowPath(direction, x, y, width, height) {
  const pad = width * 0.22;
  const head = width * 0.7;
  const centerX = x + width * 0.5;
  const startY = direction === "up" ? y + height - pad : y + pad;
  const endY = direction === "up" ? y + pad : y + height - pad;
  const leftX = centerX - width * 0.22;
  const rightX = centerX + width * 0.22;
  const headLeft = centerX - head * 0.5;
  const headRight = centerX + head * 0.5;
  if (direction === "up") {
    return `M ${leftX} ${startY} L ${leftX} ${y + head} L ${headLeft} ${y + head} L ${centerX} ${endY} L ${headRight} ${y + head} L ${rightX} ${y + head} L ${rightX} ${startY} Z`;
  }
  return `M ${leftX} ${startY} L ${leftX} ${endY - head} L ${headLeft} ${endY - head} L ${centerX} ${endY} L ${headRight} ${endY - head} L ${rightX} ${endY - head} L ${rightX} ${startY} Z`;
}

function pointInRect(point, rect, pad = 0) {
  const x = Number(point?.x) || 0;
  const y = Number(point?.y) || 0;
  return (
    x >= (Number(rect?.x) || 0) - pad &&
    x <= (Number(rect?.x) || 0) + (Number(rect?.w) || 0) + pad &&
    y >= (Number(rect?.y) || 0) - pad &&
    y <= (Number(rect?.y) || 0) + (Number(rect?.h) || 0) + pad
  );
}

function hitTestInnerRect(point) {
  return pointInRect(point, innerRect.value, 0);
}

function hitTestController(point) {
  for (let index = controllerVisuals.value.length - 1; index >= 0; index -= 1) {
    const item = controllerVisuals.value[index];
    if (pointInRect(point, item, 10 * visualScale.value)) return item;
  }
  return null;
}

function syncViewport() {
  const el = wrapEl.value;
  if (!el) {
    viewport.value = { ...DEFAULT_VIEWPORT };
    return;
  }
  viewport.value = {
    width: Math.max(420, Math.round(el.clientWidth)),
    height: Math.max(340, Math.round(el.clientHeight)),
  };
}

function getSvgPoint(event) {
  const svg = svgEl.value;
  if (!svg || !event) return null;
  const rect = svg.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const clientX = Number(event.clientX);
  const clientY = Number(event.clientY);
  if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) return null;
  const vb = viewBoxRect.value;
  return {
    x: vb.x + ((clientX - rect.left) / rect.width) * vb.width,
    y: vb.y + ((clientY - rect.top) / rect.height) * vb.height,
  };
}

function resetView() {
  zoom.value = 1;
  pan.value = { x: 0, y: 0 };
}

function resetState() {
  geometryState.value = createDefaultGeometryState();
  pointerState.value = {
    mode: "idle",
    pointerId: null,
    controllerId: "",
    startPoint: null,
    startRect: null,
    startPan: null,
    pointerToAnchor: null,
  };
  hoveredRect.value = false;
  cursorPoint.value = null;
  inputDraft.value = "";
  resetView();
}

function zoomBy(direction) {
  const amount = direction > 0 ? 1.15 : (1 / 1.15);
  zoom.value = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, Number((zoom.value * amount).toFixed(4)) || 1));
}

function applyControllerDrag(controllerId, currentPoint) {
  const startRect = pointerState.value.startRect;
  const frame = frameRect.value;
  if (!startRect || !currentPoint) return;
  const nextRect = { ...startRect };
  const pointerToAnchor = pointerState.value.pointerToAnchor || { x: 0, y: 0 };
  if (controllerId === "left") {
    const right = getRight(startRect);
    const anchorX = (Number(currentPoint.x) || frame.x) - (Number(pointerToAnchor.x) || 0);
    nextRect.x = Math.max(frame.x, Math.min(anchorX, right - CONTROLLER_MIN_WIDTH_MM));
    nextRect.w = right - nextRect.x;
  } else if (controllerId === "right") {
    const anchorX = (Number(currentPoint.x) || getRight(startRect)) - (Number(pointerToAnchor.x) || 0);
    const nextRight = Math.min(frame.x + frame.w, Math.max(anchorX, startRect.x + CONTROLLER_MIN_WIDTH_MM));
    nextRect.w = nextRight - startRect.x;
  } else if (controllerId === "top") {
    const bottom = getBottom(startRect);
    const anchorY = (Number(currentPoint.y) || frame.y) - (Number(pointerToAnchor.y) || 0);
    nextRect.y = Math.max(frame.y, Math.min(anchorY, bottom - CONTROLLER_MIN_HEIGHT_MM));
    nextRect.h = bottom - nextRect.y;
  } else if (controllerId === "bottomOffset") {
    const anchorY = (Number(currentPoint.y) || frame.y) - (Number(pointerToAnchor.y) || 0);
    const startAnchorY = (Number(pointerState.value.startPoint?.y) || frame.y) - (Number(pointerToAnchor.y) || 0);
    const rawY = (Number(startRect.y) || frame.y) + (anchorY - startAnchorY);
    nextRect.y = Math.max(frame.y, Math.min(rawY, (frame.y + frame.h) - startRect.h));
    nextRect.h = startRect.h;
  }
  updateInnerRect(nextRect);
}

function applyControllerInput(controllerId, nextValueMm) {
  if (!Number.isFinite(nextValueMm)) return false;
  const frame = frameRect.value;
  const startRect = innerRect.value;
  const nextRect = { ...startRect };
  const safeValue = Math.max(0, Number(nextValueMm) || 0);
  if (controllerId === "left") {
    const inset = Math.min(Math.max(0, safeValue), Math.max(0, frame.w - controllerValues.value.right - CONTROLLER_MIN_WIDTH_MM));
    nextRect.x = frame.x + inset;
    nextRect.w = (frame.x + frame.w) - controllerValues.value.right - nextRect.x;
  } else if (controllerId === "right") {
    const inset = Math.min(Math.max(0, safeValue), Math.max(0, frame.w - controllerValues.value.left - CONTROLLER_MIN_WIDTH_MM));
    nextRect.w = frame.w - controllerValues.value.left - inset;
  } else if (controllerId === "top") {
    const height = Math.min(Math.max(CONTROLLER_MIN_HEIGHT_MM, safeValue), frame.h - controllerValues.value.bottomOffset);
    nextRect.h = height;
    nextRect.y = (frame.y + frame.h) - controllerValues.value.bottomOffset - height;
  } else if (controllerId === "bottomOffset") {
    const bottomOffset = Math.min(Math.max(0, safeValue), frame.h - startRect.h);
    nextRect.y = (frame.y + frame.h) - bottomOffset - startRect.h;
  } else {
    return false;
  }
  updateInnerRect(nextRect);
  return true;
}

function beginEditing(controllerId) {
  if (!controllerId) return;
  setEditingController(controllerId);
  inputDraft.value = formatControllerRawValue(controllerValues.value[controllerId]);
  nextTick(() => {
    const inputEl = wrapEl.value?.querySelector?.(`[data-controller-input="${controllerId}"]`);
    inputEl?.focus?.();
    inputEl?.select?.();
  });
}

function cancelEditing() {
  inputDraft.value = "";
  clearEditingController();
}

function commitEditing() {
  const controllerId = geometryState.value.editingController;
  if (!controllerId) return;
  const nextValueMm = parseControllerInputToMm(inputDraft.value);
  if (nextValueMm == null) {
    cancelEditing();
    return;
  }
  applyControllerInput(controllerId, nextValueMm);
  cancelEditing();
}

function beginControllerDrag(controllerId, event) {
  const point = getSvgPoint(event);
  const controller = controllerVisuals.value.find((item) => item.id === controllerId);
  if (!point || !controllerId || !controller?.anchor) return;
  geometryState.value = { ...geometryState.value, selected: true, hoveredController: controllerId };
  pointerState.value = {
    mode: "controller",
    pointerId: event.pointerId,
    controllerId,
    startPoint: point,
    startRect: { ...innerRect.value },
    startPan: null,
    pointerToAnchor: {
      x: (Number(point.x) || 0) - (Number(controller.anchor.x) || 0),
      y: (Number(point.y) || 0) - (Number(controller.anchor.y) || 0),
    },
  };
  svgEl.value?.setPointerCapture?.(event.pointerId);
}

function handleControllerPointerDown(controllerId, event) {
  if (Number(event?.button) === 1) {
    beginPan(event);
    return;
  }

  if (Number(event?.button) !== 0) return;

  const now = Date.now();
  const isDoublePress =
    String(lastControllerPointerDown.id || "") === String(controllerId || "") &&
    now - Number(lastControllerPointerDown.at || 0) <= 320;

  lastControllerPointerDown = { id: controllerId, at: now };

  if (isDoublePress) {
    event?.stopPropagation?.();
    event?.preventDefault?.();
    beginEditing(controllerId);
    endPointerSession();
    return;
  }

  beginControllerDrag(controllerId, event);
}

function handleValueFieldPointerDown(event) {
  if (Number(event?.button) === 1) {
    beginPan(event);
    return;
  }
  event?.stopPropagation?.();
}

function beginPan(event) {
  const point = getSvgPoint(event);
  if (!point) return;
  pointerState.value = {
    mode: "pan",
    pointerId: event.pointerId,
    controllerId: "",
    startPoint: point,
    startRect: null,
    startPan: { ...(pan.value || { x: 0, y: 0 }) },
    pointerToAnchor: null,
  };
  svgEl.value?.setPointerCapture?.(event.pointerId);
}

function endPointerSession() {
  pointerState.value = {
    mode: "idle",
    pointerId: null,
    controllerId: "",
    startPoint: null,
    startRect: null,
    startPan: null,
    pointerToAnchor: null,
  };
}

function handleWheel(event) {
  event.preventDefault();
  zoomBy(event.deltaY < 0 ? 1 : -1);
}

function handleSvgPointerDown(event) {
  if (Number(event.button) === 1) {
    beginPan(event);
    event.preventDefault();
    return;
  }
  if (Number(event.button) !== 0 || geometryState.value.editingController) return;
  const point = getSvgPoint(event);
  if (!point) return;
  const controllerHit = hitTestController(point);
  if (controllerHit) {
    beginControllerDrag(controllerHit.id, event);
    event.preventDefault();
    return;
  }
  const rectHit = hitTestInnerRect(point);
  hoveredRect.value = rectHit;
  geometryState.value = { ...geometryState.value, selected: rectHit, hoveredController: "" };
}

function handleSvgPointerMove(event) {
  const point = getSvgPoint(event);
  cursorPoint.value = point;
  if (!point) return;
  if (pointerState.value.mode === "controller") {
    applyControllerDrag(pointerState.value.controllerId, point);
    return;
  }
  if (pointerState.value.mode === "pan" && pointerState.value.startPoint && pointerState.value.startPan) {
    pan.value = {
      x: (Number(pointerState.value.startPan.x) || 0) - (point.x - pointerState.value.startPoint.x),
      y: (Number(pointerState.value.startPan.y) || 0) - (point.y - pointerState.value.startPoint.y),
    };
    return;
  }
  const controllerHit = hitTestController(point);
  hoveredRect.value = !controllerHit && hitTestInnerRect(point);
  setHoveredController(controllerHit?.id || "");
}

function handleSvgPointerUp(event) {
  if (pointerState.value.pointerId != null) {
    svgEl.value?.releasePointerCapture?.(pointerState.value.pointerId);
  }
  if (pointerState.value.mode === "controller") {
    setHoveredController(pointerState.value.controllerId);
  }
  if (pointerState.value.mode === "pan") {
    cursorPoint.value = getSvgPoint(event);
  }
  endPointerSession();
}

function handleSvgPointerLeave() {
  if (pointerState.value.mode !== "idle") return;
  cursorPoint.value = null;
  hoveredRect.value = false;
  setHoveredController("");
}

const cursorModeClass = computed(() => {
  if (pointerState.value.mode === "pan") return "is-panning";
  if (pointerState.value.mode === "controller") {
    return pointerState.value.controllerId === "left" || pointerState.value.controllerId === "right"
      ? "is-drag-horizontal"
      : "is-drag-vertical";
  }
  if (geometryState.value.hoveredController === "left" || geometryState.value.hoveredController === "right") return "is-resize-horizontal";
  if (geometryState.value.hoveredController === "top" || geometryState.value.hoveredController === "bottomOffset") return "is-resize-vertical";
  if (hoveredRect.value) return "is-clickable";
  return "is-idle";
});

function closeModal() {
  emit("close");
}

function handleWindowKeydown(event) {
  if (event.key !== "Escape") return;
  if (geometryState.value.editingController) {
    event.preventDefault();
    cancelEditing();
    return;
  }
  closeModal();
}

const footerSummary = computed(() => ([
  { id: "left", label: "فاصله چپ", value: formatInteriorDimensionValue(controllerValues.value.left, normalizedDisplayUnit.value) },
  { id: "top", label: "ارتفاع مستطیل", value: formatInteriorDimensionValue(controllerValues.value.top, normalizedDisplayUnit.value) },
  { id: "right", label: "فاصله راست", value: formatInteriorDimensionValue(controllerValues.value.right, normalizedDisplayUnit.value) },
  { id: "bottomOffset", label: "فاصله تا کف طرح", value: formatInteriorDimensionValue(controllerValues.value.bottomOffset, normalizedDisplayUnit.value) },
]));

onMounted(() => {
  syncViewport();
  if (typeof ResizeObserver !== "undefined") {
    viewportObserver = new ResizeObserver(() => syncViewport());
    if (wrapEl.value) viewportObserver.observe(wrapEl.value);
  }
  window.addEventListener("keydown", handleWindowKeydown);
});

onBeforeUnmount(() => {
  if (viewportObserver) viewportObserver.disconnect();
  window.removeEventListener("keydown", handleWindowKeydown);
});

watch(() => props.displayUnit, () => {
  if (!geometryState.value.editingController) return;
  inputDraft.value = formatControllerRawValue(controllerValues.value[geometryState.value.editingController]);
});
</script>

<template>
  <div class="appDialog" role="dialog" aria-modal="true">
    <div class="appDialog__backdrop" @click="closeModal"></div>
    <div class="appDialog__card appDialog__card--subDesign controllerTestModal" dir="rtl">
      <div class="formulaBuilder__head">
        <div class="constructionDialog__sectionTitle formulaBuilder__title">تست کنترلر قطعات داخلی</div>
        <button type="button" class="constructionDialog__close formulaBuilder__close" title="بستن" @click="closeModal">×</button>
      </div>
      <div class="controllerTestModal__hint">
        این صفحه برای تست محلی ۴ کنترلر قطعه داخلی است. انتخاب مستطیل، drag دستک‌ها، ورودی عددی و رفتار zoom/pan فقط در همین دمو اعمال می‌شود.
        <span class="controllerTestModal__hintStrong">برای ویرایش عدد، روی متن داخل دستک کلیک یا روی خود دستک دابل‌کلیک کنید.</span>
      </div>
      <div class="controllerTestModal__toolbar">
        <button type="button" class="iconbtn iconbtn--sm stageQuickBar__btn" title="بزرگنمایی" @click="zoomBy(1)">
          <img src="/icons/zoom-in.png" alt="" />
        </button>
        <button type="button" class="iconbtn iconbtn--sm stageQuickBar__btn" title="کوچکنمایی" @click="zoomBy(-1)">
          <img src="/icons/zoom-out.png" alt="" />
        </button>
        <button type="button" class="controllerTestModal__resetBtn" @click="resetView">بازنشانی نما</button>
        <button type="button" class="controllerTestModal__resetBtn" @click="resetState">بازنشانی تست</button>
        <div class="controllerTestModal__unitPill">واحد فعال: {{ unitLabel }}</div>
      </div>
      <div ref="wrapEl" class="controllerTestModal__viewerWrap" :class="cursorModeClass">
        <svg
          ref="svgEl"
          class="controllerTestModal__svg"
          :viewBox="viewBox"
          @wheel.prevent="handleWheel"
          @pointerdown="handleSvgPointerDown"
          @pointermove="handleSvgPointerMove"
          @pointerup="handleSvgPointerUp"
          @pointercancel="handleSvgPointerUp"
          @pointerleave="handleSvgPointerLeave"
        >
          <defs>
            <pattern id="controller-test-grid" width="100" height="100" patternUnits="userSpaceOnUse">
              <path d="M 100 0 L 0 0 0 100" fill="none" stroke="rgba(79, 65, 68, 0.08)" stroke-width="1" />
            </pattern>
          </defs>
          <rect :x="baseBounds.x" :y="baseBounds.y" :width="baseBounds.w" :height="baseBounds.h" fill="url(#controller-test-grid)" />
          <rect :x="frameRect.x" :y="frameRect.y" :width="frameRect.w" :height="frameRect.h" class="controllerTestModal__frame" />
          <rect
            :x="innerRect.x"
            :y="innerRect.y"
            :width="innerRect.w"
            :height="innerRect.h"
            class="controllerTestModal__innerRect"
            :class="{ 'is-selected': geometryState.selected, 'is-hovered': hoveredRect }"
          />
          <g v-if="geometryState.selected" class="controllerTestModal__controllers">
            <g
              v-for="controller in controllerVisuals"
              :key="controller.id"
              class="controllerTestModal__controller"
              :class="{
                'is-hovered': geometryState.hoveredController === controller.id,
                'is-editing': geometryState.editingController === controller.id,
                'is-dragging': pointerState.controllerId === controller.id && pointerState.mode === 'controller',
              }"
            >
              <image
                :href="'/icons/double-arrow.png'"
                :x="controller.kind === 'vertical' ? controller.x + ((controller.w - controller.h) * 0.5) : controller.x"
                :y="controller.kind === 'vertical' ? controller.y + ((controller.h - controller.w) * 0.5) : controller.y"
                :width="controller.kind === 'vertical' ? controller.h : controller.w"
                :height="controller.kind === 'vertical' ? controller.w : controller.h"
                class="controllerTestModal__controllerBody"
                preserveAspectRatio="xMidYMid meet"
                :transform="controller.kind === 'vertical' ? `rotate(-90 ${controller.x + (controller.w * 0.5)} ${controller.y + (controller.h * 0.5)})` : null"
                @pointerdown.stop.prevent="handleControllerPointerDown(controller.id, $event)"
                @pointerenter="setHoveredController(controller.id)"
                @pointerleave="setHoveredController('')"
              />
              <foreignObject
                :x="controller.kind === 'horizontal' ? controller.x + (315 * visualScale) : controller.x + (36 * visualScale)"
                :y="controller.kind === 'horizontal' ? controller.y + ((controller.h - controller.inputH) * 0.5) : controller.y + (379 * visualScale)"
                :width="180 * visualScale"
                :height="51 * visualScale"
              >
                <div class="controllerTestModal__valueShell" xmlns="http://www.w3.org/1999/xhtml">
                  <input
                    v-if="geometryState.editingController === controller.id"
                    :data-controller-input="controller.id"
                    v-model="inputDraft"
                    class="controllerTestModal__valueInput is-editing"
                    type="text"
                    @pointerdown="handleValueFieldPointerDown($event)"
                    @keydown.enter.prevent.stop="commitEditing"
                    @keydown.esc.prevent.stop="cancelEditing"
                    @blur="commitEditing"
                  />
                  <button
                    v-else
                    type="button"
                    class="controllerTestModal__valueButton controllerTestModal__valueButton--field"
                    :class="{ 'is-hovered': geometryState.hoveredController === controller.id }"
                    @pointerenter="setHoveredController(controller.id)"
                    @pointerleave="setHoveredController('')"
                    @pointerdown="handleValueFieldPointerDown($event)"
                    @click.stop="beginEditing(controller.id)"
                  >
                    {{ formatControllerDisplayValue(controllerValues[controller.id]) }}
                  </button>
                </div>
              </foreignObject>
            </g>
          </g>
        </svg>
      </div>
      <div class="controllerTestModal__footer">
        <div v-for="item in footerSummary" :key="item.id" class="controllerTestModal__stat">
          <div class="controllerTestModal__statLabel">{{ item.label }}</div>
          <div class="controllerTestModal__statValue">{{ item.value }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.controllerTestModal {
  width: min(1180px, calc(100vw - 48px));
  max-width: 1180px;
}

.controllerTestModal__hint {
  margin-bottom: 14px;
  color: #7a5d67;
  font-size: 13px;
  line-height: 1.8;
}

.controllerTestModal__hintStrong {
  color: #4b1e2f;
  font-weight: 800;
}

.controllerTestModal__toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 14px;
  flex-wrap: wrap;
}

.controllerTestModal__resetBtn,
.controllerTestModal__unitPill {
  border-radius: 999px;
  border: 1px solid rgba(118, 45, 71, 0.14);
  background: rgba(255, 255, 255, 0.92);
  color: #5e3245;
  font-size: 12px;
  font-weight: 700;
  line-height: 1;
}

.controllerTestModal__resetBtn {
  padding: 9px 14px;
  cursor: pointer;
}

.controllerTestModal__unitPill {
  padding: 10px 14px;
  margin-inline-start: auto;
}

.controllerTestModal__viewerWrap {
  position: relative;
  min-height: 620px;
  border-radius: 22px;
  overflow: hidden;
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.98), rgba(250, 245, 244, 0.95)),
    radial-gradient(circle at top left, rgba(118, 45, 71, 0.05), transparent 42%);
  box-shadow: inset 0 0 0 1px rgba(118, 45, 71, 0.08);
}

.controllerTestModal__viewerWrap.is-idle { cursor: default; }
.controllerTestModal__viewerWrap.is-clickable { cursor: pointer; }
.controllerTestModal__viewerWrap.is-resize-horizontal { cursor: ew-resize; }
.controllerTestModal__viewerWrap.is-resize-vertical { cursor: ns-resize; }
.controllerTestModal__viewerWrap.is-drag-horizontal,
.controllerTestModal__viewerWrap.is-drag-vertical { cursor: grabbing; }
.controllerTestModal__viewerWrap.is-panning { cursor: grab; }

.controllerTestModal__svg {
  width: 100%;
  height: 100%;
  min-height: 620px;
  display: block;
  touch-action: none;
}

.controllerTestModal__frame {
  fill: rgba(255, 255, 255, 0.82);
  stroke: #8b0d23;
  stroke-width: 12;
}

.controllerTestModal__innerRect {
  fill: rgba(29, 183, 109, 0.04);
  stroke: #1fb457;
  stroke-width: 10;
  transition: stroke-width 0.16s ease, stroke 0.16s ease, fill 0.16s ease;
}

.controllerTestModal__innerRect.is-hovered,
.controllerTestModal__innerRect.is-selected {
  fill: rgba(46, 145, 255, 0.08);
  stroke: #1d8ef0;
}

.controllerTestModal__innerRect.is-selected { stroke-width: 12; }

.controllerTestModal__controllerBody {
  opacity: 0.98;
  transition: opacity 0.14s ease, filter 0.14s ease, transform 0.14s ease;
}

.controllerTestModal__controller.is-hovered .controllerTestModal__controllerBody,
.controllerTestModal__controller.is-dragging .controllerTestModal__controllerBody,
.controllerTestModal__controller.is-editing .controllerTestModal__controllerBody {
  filter: drop-shadow(0 0 0 rgba(0, 0, 0, 0)) drop-shadow(0 10px 18px rgba(29, 142, 240, 0.24)) saturate(1.08) brightness(1.04);
}

.controllerTestModal__valueShell {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  height: 100%;
}

.controllerTestModal__valueButton,
.controllerTestModal__valueInput {
  width: 100%;
  min-width: 0;
  height: 100%;
  border: 1px solid rgba(122, 122, 122, 0.55);
  border-radius: 28px;
  background: rgba(255, 255, 255, 0.98);
  color: #2b6fda;
  font-size: 24px;
  font-weight: 700;
  text-align: center;
  padding: 0 18px;
  box-sizing: border-box;
  box-shadow: 0 2px 0 rgba(255, 255, 255, 0.35), 0 6px 14px rgba(0, 0, 0, 0.08);
  letter-spacing: 0;
  direction: ltr;
  opacity: 0.9;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: clip;
  line-height: 1;
}

.controllerTestModal__valueButton {
  cursor: text;
  line-height: 1.1;
  display: flex;
  align-items: center;
  justify-content: center;
}

.controllerTestModal__valueButton--field {
  transition: background-color 0.14s ease, border-color 0.14s ease, box-shadow 0.14s ease, transform 0.14s ease;
}

.controllerTestModal__valueButton--field:hover,
.controllerTestModal__valueButton--field.is-hovered,
.controllerTestModal__valueButton--field:focus-visible {
  background: #ffffff;
  border-color: rgba(80, 114, 170, 0.9);
  box-shadow: 0 0 0 4px rgba(58, 124, 240, 0.14), 0 8px 18px rgba(0, 0, 0, 0.1);
  outline: none;
}

.controllerTestModal__controller.is-hovered .controllerTestModal__valueButton--field,
.controllerTestModal__controller.is-dragging .controllerTestModal__valueButton--field,
.controllerTestModal__controller.is-editing .controllerTestModal__valueButton--field {
  opacity: 1;
  transform: translateY(-1px);
}

.controllerTestModal__valueInput.is-editing {
  border-color: rgba(80, 114, 170, 0.95);
  background: #ffffff;
  padding-inline: 18px;
}

.controllerTestModal__valueInput:focus {
  outline: none;
  box-shadow: 0 0 0 4px rgba(58, 124, 240, 0.16), 0 8px 18px rgba(0, 0, 0, 0.1);
}

.controllerTestModal__footer {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.controllerTestModal__stat {
  border-radius: 16px;
  border: 1px solid rgba(118, 45, 71, 0.1);
  background: rgba(255, 255, 255, 0.9);
  padding: 12px 14px;
}

.controllerTestModal__statLabel {
  color: #7a5d67;
  font-size: 12px;
  font-weight: 700;
}

.controllerTestModal__statValue {
  margin-top: 6px;
  color: #4b1e2f;
  font-size: 13px;
  font-weight: 800;
}

@media (max-width: 980px) {
  .controllerTestModal {
    width: min(100vw - 20px, 1180px);
  }

  .controllerTestModal__viewerWrap,
  .controllerTestModal__svg {
    min-height: 480px;
  }

  .controllerTestModal__footer {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
