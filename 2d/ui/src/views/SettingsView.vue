<script setup>
import { computed, onBeforeUnmount, onMounted, reactive, ref } from "vue";
import { useRouter } from "vue-router";
import { editorRef } from "../editor/editor_store.js";
import {
  EDITOR_SETTINGS_DEFAULTS,
  editorSettingsStateToPayload,
  editorSettingsPayloadToState,
  fetchPersistedEditorSettings,
  savePersistedEditorSettings,
  settingsViewStateFromEditorState,
} from "../editor/editor_settings.js";
import { CURRENT_ADMIN_ID, CURRENT_BOOTSTRAP_USER_ID } from "../features/part_kinds_catalog.js";

const hasEditor = computed(() => !!editorRef.value);
const router = useRouter();
const defaultViewState = settingsViewStateFromEditorState(EDITOR_SETTINGS_DEFAULTS);
const baseState = ref({ ...defaultViewState });
const baseEditorState = ref({ ...EDITOR_SETTINGS_DEFAULTS });
const model = reactive({ ...defaultViewState });
const settingsSections = [
  {
    id: "units",
    title: "واحدها",
    description: "تنظیمات پایه دیوار، تیر و ستون",
    fields: [
      {
        key: "unit",
        kind: "select",
        label: "واحد نمایش",
        description: "واحدی که در فرم‌ها نمایش داده می‌شود",
        options: [
          { value: "mm", label: "میلی‌متر" },
          { value: "inch", label: "اینچ" },
          { value: "cm", label: "سانتی‌متر" },
        ],
      },
      { key: "wallThicknessMm", kind: "cm-mm", label: "ضخامت دیوار", description: "مقدار پیش‌فرض ضخامت دیوار", min: 1, step: 0.5, fallback: 120 },
      { key: "wallHeightMm", kind: "cm-mm", label: "ارتفاع دیوار", description: "ارتفاع پیش‌فرض دیوار", min: 1, step: 1, fallback: 3000 },
      { key: "hiddenWallThicknessMm", kind: "cm-mm", label: "ضخامت خط راهنما", description: "ضخامت پیش‌فرض خط راهنما", min: 0.1, step: 0.1, fallback: 1 },
      { key: "beamThicknessMm", kind: "cm-mm", label: "ضخامت تیر", description: "ضخامت پیش‌فرض تیر", min: 1, step: 0.5, fallback: 400 },
      { key: "beamHeightMm", kind: "cm-mm", label: "ارتفاع تیر", description: "ارتفاع پیش‌فرض تیر", min: 1, step: 0.5, fallback: 200 },
      { key: "beamFloorOffsetMm", kind: "cm-mm", label: "فاصله تیر از کف", description: "فاصله پیش‌فرض تیر از کف", min: 0, step: 1, fallback: 2600 },
      { key: "columnWidthMm", kind: "cm-mm", label: "عرض ستون", description: "عرض پیش‌فرض ستون", min: 1, step: 0.5, fallback: 500 },
      { key: "columnDepthMm", kind: "cm-mm", label: "عمق ستون", description: "عمق پیش‌فرض ستون", min: 1, step: 0.5, fallback: 400 },
      { key: "columnHeightMm", kind: "cm-mm", label: "ارتفاع ستون", description: "ارتفاع پیش‌فرض ستون", min: 1, step: 1, fallback: 2800 },
    ],
  },
  {
    id: "dimension",
    title: "اندازه‌گذاری",
    description: "فاصله و نمایش خطوط اندازه‌گذاری",
    fields: [
      { key: "dimOffsetMm", kind: "number", label: "فاصله اندازه‌گذاری از دیوار", description: "فاصله خطوط اندازه‌گذاری از دیوار", min: 0, step: 10, unit: "میلی‌متر" },
      { key: "dimFontPx", kind: "number", label: "فونت اندازه‌گذاری", description: "اندازه فونت اندازه‌گذاری", min: 8, step: 1, unit: "px" },
      { key: "dimLineWidthPx", kind: "number", label: "ضخامت خط دایمنشن", description: "ضخامت خطوط اندازه‌گذاری", min: 1, step: 0.5, unit: "px" },
    ],
  },
  {
    id: "grid",
    title: "شبکه",
    description: "تقسیم‌بندی و خطوط راهنمای شبکه",
    fields: [
      { key: "meterDivisions", kind: "number", label: "تقسیمات هر متر", description: "تعداد تقسیمات هر متر", min: 2, step: 1 },
      { key: "majorEvery", kind: "number", label: "خط درشت هر چند خانه", description: "فاصله تکرار خطوط درشت", min: 2, step: 1 },
    ],
  },
  {
    id: "snap",
    title: "نمایش و جذب",
    description: "کنترل نمایش، جذب و رسم گام به گام",
    fields: [
      { key: "showDimensions", kind: "toggle", label: "نمایش اندازه‌گذاری", description: "نمایش یا مخفی کردن اندازه‌گذاری" },
      { key: "stepDrawEnabled", kind: "toggle", label: "رسم گام به گام", description: "فعال بودن رسم پله‌ای" },
      { key: "stepLineCm", kind: "number", label: "گام خط", description: "فاصله رسم پله‌ای خط", min: 0.1, step: 0.5, unit: "سانتی‌متر" },
      { key: "stepAngleDeg", kind: "number", label: "گام زاویه", description: "فاصله رسم پله‌ای زاویه", min: 0.1, step: 1, unit: "درجه" },
      { key: "snapOn", kind: "toggle", label: "جذب کلی", description: "روشن یا خاموش بودن جذب" },
      { key: "snapCornerEnabled", kind: "toggle", label: "جذب گوشه", description: "جذب روی گوشه‌ها" },
      { key: "snapMidEnabled", kind: "toggle", label: "جذب وسط ضلع", description: "جذب روی نقاط میانی" },
      { key: "snapCenterEnabled", kind: "toggle", label: "جذب آکس وسط", description: "جذب روی محور مرکز" },
      { key: "snapEdgeEnabled", kind: "toggle", label: "جذب لبه", description: "جذب روی لبه‌ها" },
      { key: "wallMagnetEnabled", kind: "toggle", label: "جذب مغناطیسی دیوار", description: "جذب مغناطیسی روی دیوار" },
      { key: "offsetWallEnabled", kind: "toggle", label: "دیوار موازی", description: "فعالسازی دیوار موازی" },
      { key: "offsetWallDistanceMm", kind: "number", label: "فاصله دیوار موازی", description: "فاصله دیوار موازی", min: 0, step: 10, unit: "میلی‌متر" },
    ],
  },
  {
    id: "fonts",
    title: "نوشتار",
    description: "تنظیمات نوشتار و متن",
    fields: [
      { key: "fontFamily", kind: "text", label: "خانواده فونت", description: "فونت اصلی محیط طراحی", placeholder: "مثلاً Tahoma" },
      { key: "wallNameFontPx", kind: "number", label: "فونت نام دیوار", description: "اندازه فونت نام دیوار", min: 8, step: 1, unit: "px" },
      { key: "angleFontPx", kind: "number", label: "فونت زاویه", description: "اندازه فونت زاویه", min: 8, step: 1, unit: "px" },
    ],
  },
  {
    id: "colors",
    title: "رنگ‌ها",
    description: "پالت نمایش صفحه و اجزای ترسیم",
    fields: [
      { key: "bgColor", kind: "color", label: "پس‌زمینه", description: "رنگ پس‌زمینه محیط" },
      { key: "gridColors", kind: "color-group", label: "شبکه", description: "رنگ خطوط ریز و درشت", colors: [
        { key: "minorColor", label: "ریز" },
        { key: "majorColor", label: "درشت" },
      ] },
      { key: "axisColors", kind: "color-group", label: "محورها", description: "رنگ محورهای X / Y / Z", colors: [
        { key: "axisXColor", label: "محور X" },
        { key: "axisYColor", label: "محور Y" },
        { key: "axisZColor", label: "محور Z" },
      ] },
      { key: "wallColors", kind: "color-group", label: "دیوار", description: "رنگ‌های نمایش دیوار", colors: [
        { key: "wallFillColor", label: "داخلی دوبعدی" },
        { key: "wallFillOpacityPercent", label: "شفافیت داخلی", kind: "number", min: 0, max: 100, unit: "%" },
        { key: "wallTextColor", label: "متن" },
        { key: "wallEdgeColor", label: "خط بیرونی" },
        { key: "wall3dColor", label: "سه‌بعدی" },
      ] },
      { key: "beamColors", kind: "color-group", label: "تیر", description: "رنگ‌های نمایش تیر", colors: [
        { key: "beamFillColor", label: "داخلی دوبعدی" },
        { key: "beamFillOpacityPercent", label: "شفافیت داخلی", kind: "number", min: 0, max: 100, unit: "%" },
        { key: "beamTextColor", label: "متن" },
        { key: "beamEdgeColor", label: "خط بیرونی" },
        { key: "beam3dColor", label: "سه‌بعدی" },
      ] },
      { key: "columnColors", kind: "color-group", label: "ستون", description: "رنگ‌های نمایش ستون", colors: [
        { key: "columnFillColor", label: "داخلی دوبعدی" },
        { key: "columnFillOpacityPercent", label: "شفافیت داخلی", kind: "number", min: 0, max: 100, unit: "%" },
        { key: "columnTextColor", label: "متن" },
        { key: "columnEdgeColor", label: "خط بیرونی" },
        { key: "column3dColor", label: "سه‌بعدی" },
      ] },
      { key: "guideColors", kind: "color-group", label: "اندازه‌گذاری و راهنما", description: "رنگ خطوط اندازه‌گذاری و راهنما", colors: [
        { key: "dimColor", label: "اندازه‌گذاری" },
        { key: "hiddenWallColor", label: "راهنما" },
      ] },
    ],
  },
];
const activeSectionId = ref(settingsSections[0]?.id || "");
const activeSettingsSection = computed(() =>
  settingsSections.find((section) => section.id === activeSectionId.value) || settingsSections[0]
);

function positiveOrFallback(value, fallback, min = 0.0001) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > min ? parsed : fallback;
}

function normalizeDisplayUnit(unit) {
  const normalized = String(unit || "").trim().toLowerCase();
  return normalized === "mm" || normalized === "inch" ? normalized : "cm";
}

function mmToDisplayValue(value, unit) {
  const numeric = Number(value ?? 0);
  const normalizedUnit = normalizeDisplayUnit(unit);
  if (normalizedUnit === "mm") return numeric;
  if (normalizedUnit === "inch") return Math.round((numeric / 25.4) * 100) / 100;
  return numeric / 10;
}

function displayValueToMm(value, unit) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return numeric;
  const normalizedUnit = normalizeDisplayUnit(unit);
  if (normalizedUnit === "mm") return numeric;
  if (normalizedUnit === "inch") return numeric * 25.4;
  return numeric * 10;
}

function cmToDisplayValue(value, unit) {
  const numeric = Number(value ?? 0);
  const normalizedUnit = normalizeDisplayUnit(unit);
  if (normalizedUnit === "mm") return numeric * 10;
  if (normalizedUnit === "inch") return Math.round((numeric / 2.54) * 100) / 100;
  return numeric;
}

function displayValueToCm(value, unit) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) return numeric;
  const normalizedUnit = normalizeDisplayUnit(unit);
  if (normalizedUnit === "mm") return numeric / 10;
  if (normalizedUnit === "inch") return numeric * 2.54;
  return numeric;
}

function getDisplayLengthUnitLabel(unit) {
  const normalizedUnit = normalizeDisplayUnit(unit);
  if (normalizedUnit === "mm") return "میلی‌متر";
  if (normalizedUnit === "inch") return "اینچ";
  return "سانتی‌متر";
}

function hydrateModelFromFlatState(flatState) {
  const nextModel = settingsViewStateFromEditorState(flatState);
  for (const k of Object.keys(model)) model[k] = nextModel[k];
  baseState.value = { ...nextModel };
  baseEditorState.value = { ...flatState };
}

onMounted(async () => {
  try {
    const payload = await fetchPersistedEditorSettings(CURRENT_ADMIN_ID, CURRENT_BOOTSTRAP_USER_ID);
    hydrateModelFromFlatState(editorSettingsPayloadToState(payload));
  } catch (_) {
    hydrateModelFromFlatState(EDITOR_SETTINGS_DEFAULTS);
  }
});

function applyPatch(patch) {
  if (!patch || typeof patch !== "object") return;
  // Local draft only; nothing is applied to engine until Save is clicked.
  Object.assign(model, patch);
}

function selectSection(sectionId) {
  activeSectionId.value = String(sectionId || settingsSections[0]?.id || "");
}

function getFieldValue(field) {
  if (!field) return "";
  if (field.kind === "cm-mm") {
    return mmToDisplayValue(model[field.key] ?? field.fallback ?? 0, model.unit);
  }
  if (field.key === "dimOffsetMm" || field.key === "offsetWallDistanceMm") {
    return mmToDisplayValue(model[field.key] ?? 0, model.unit);
  }
  if (field.key === "stepLineCm") {
    return cmToDisplayValue(model[field.key] ?? 0, model.unit);
  }
  return model[field.key];
}

function getFieldMin(field) {
  if (!field) return undefined;
  if (field.kind === "cm-mm") {
    return mmToDisplayValue(field.min ?? 0, model.unit);
  }
  if (field.key === "dimOffsetMm" || field.key === "offsetWallDistanceMm") {
    return mmToDisplayValue(field.min ?? 0, model.unit);
  }
  if (field.key === "stepLineCm") {
    return cmToDisplayValue(field.min ?? 0, model.unit);
  }
  return field.min;
}

function getFieldStep(field) {
  if (!field) return undefined;
  if (field.kind === "cm-mm") {
    return mmToDisplayValue(field.step ?? 1, model.unit);
  }
  if (field.key === "dimOffsetMm" || field.key === "offsetWallDistanceMm") {
    return mmToDisplayValue(field.step ?? 1, model.unit);
  }
  if (field.key === "stepLineCm") {
    return cmToDisplayValue(field.step ?? 1, model.unit);
  }
  return field.step;
}

function getFieldUnitLabel(field) {
  if (!field) return "";
  if (field.kind === "cm-mm") return getDisplayLengthUnitLabel(model.unit);
  if (field.key === "dimOffsetMm" || field.key === "offsetWallDistanceMm") {
    return getDisplayLengthUnitLabel(model.unit);
  }
  if (field.key === "stepLineCm") {
    return getDisplayLengthUnitLabel(model.unit);
  }
  return field.unit || "";
}

function normalizePercentValue(value, fallback = 0) {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return fallback;
  return Math.max(0, Math.min(100, parsed));
}

function updateFieldValue(field, rawValue) {
  if (!field) return;
  if (field.kind === "select") {
    applyPatch({ [field.key]: rawValue });
    return;
  }
  if (field.kind === "text") {
    applyPatch({ [field.key]: rawValue || field.placeholder || "" });
    return;
  }
  if (field.kind === "toggle") {
    applyPatch({ [field.key]: !!rawValue });
    return;
  }
  if (field.kind === "color") {
    applyPatch({ [field.key]: rawValue });
    return;
  }
  if (field.max === 100 && field.min === 0 && field.unit === "%") {
    applyPatch({ [field.key]: normalizePercentValue(rawValue, model[field.key] ?? 0) });
    return;
  }
  if (field.kind === "cm-mm") {
    const min = field.min ?? 0;
    const fallback = field.fallback ?? 0;
    const nextValue = Math.max(min, +rawValue || fallback);
    applyPatch({ [field.key]: displayValueToMm(nextValue, model.unit) });
    return;
  }
  if (field.key === "stepLineCm" || field.key === "stepAngleDeg") {
    if (field.key === "stepLineCm") {
      const nextValue = positiveOrFallback(rawValue, getFieldValue(field), 0);
      applyPatch({ [field.key]: displayValueToCm(nextValue, model.unit) });
      return;
    }
    applyPatch({ [field.key]: positiveOrFallback(rawValue, model[field.key]) });
    return;
  }
  if (field.key === "dimOffsetMm" || field.key === "offsetWallDistanceMm") {
    const nextValue = Math.max(field.min ?? 0, +rawValue || 0);
    applyPatch({ [field.key]: displayValueToMm(nextValue, model.unit) });
    return;
  }
  applyPatch({ [field.key]: +rawValue || model[field.key] || 0 });
}

function getDialogApi() {
  return window.__designkpDialogs || {
    alert: async (msg) => { window.alert(msg); return true; },
    confirm: async (msg) => window.confirm(msg),
  };
}

async function handleSaveSettings() {
  const dialogs = getDialogApi();
  const ok = await dialogs.confirm("آیا از تغییرات اطمینان دارید؟", { title: "ذخیره تنظیمات" });
  if (!ok) return;

  const base = baseState.value || {};
  const patch = {};
  for (const k of Object.keys(model)) {
    if (model[k] !== base[k]) patch[k] = model[k];
  }

  if ("stepLineCm" in patch) {
    patch.stepLineCm = positiveOrFallback(patch.stepLineCm, base.stepLineCm ?? 5);
    model.stepLineCm = patch.stepLineCm;
  }
  if ("stepAngleDeg" in patch) {
    patch.stepAngleDeg = positiveOrFallback(patch.stepAngleDeg, base.stepAngleDeg ?? 10);
    model.stepAngleDeg = patch.stepAngleDeg;
  }
  if ("hiddenWallThicknessMm" in patch) {
    patch.hiddenWallThicknessMm = positiveOrFallback(patch.hiddenWallThicknessMm, base.hiddenWallThicknessMm ?? 1, 0);
    model.hiddenWallThicknessMm = patch.hiddenWallThicknessMm;
  }
  if ("beamThicknessMm" in patch) {
    patch.beamThicknessMm = positiveOrFallback(patch.beamThicknessMm, base.beamThicknessMm ?? 400);
    model.beamThicknessMm = patch.beamThicknessMm;
  }
  if ("beamHeightMm" in patch) {
    patch.beamHeightMm = positiveOrFallback(patch.beamHeightMm, base.beamHeightMm ?? 200);
    model.beamHeightMm = patch.beamHeightMm;
  }
  if ("columnWidthMm" in patch) {
    patch.columnWidthMm = positiveOrFallback(patch.columnWidthMm, base.columnWidthMm ?? 500);
    model.columnWidthMm = patch.columnWidthMm;
  }
  if ("columnDepthMm" in patch) {
    patch.columnDepthMm = positiveOrFallback(patch.columnDepthMm, base.columnDepthMm ?? 400);
    model.columnDepthMm = patch.columnDepthMm;
  }
  if ("columnHeightMm" in patch) {
    patch.columnHeightMm = positiveOrFallback(patch.columnHeightMm, base.columnHeightMm ?? 2800);
    model.columnHeightMm = patch.columnHeightMm;
  }
  if ("beamFloorOffsetMm" in patch) {
    patch.beamFloorOffsetMm = positiveOrFallback(patch.beamFloorOffsetMm, base.beamFloorOffsetMm ?? 2600, 0);
    model.beamFloorOffsetMm = patch.beamFloorOffsetMm;
  }

  const nextEditorState = { ...baseEditorState.value, ...patch };

  try {
    await savePersistedEditorSettings(
      CURRENT_ADMIN_ID,
      CURRENT_BOOTSTRAP_USER_ID,
      editorSettingsStateToPayload(nextEditorState)
    );
  } catch (_) {
    await dialogs.alert("ذخیره تنظیمات در دیتابیس انجام نشد.", { title: "خطا" });
    return;
  }

  if (Object.keys(patch).length > 0) {
    editorRef.value?.setState?.(patch);
    baseState.value = { ...base, ...patch };
    baseEditorState.value = nextEditorState;
  }
  router.push("/");
}

function onGlobalSaveShortcut() {
  handleSaveSettings();
}

onMounted(() => {
  window.addEventListener("designkp:save-settings", onGlobalSaveShortcut);
});

onBeforeUnmount(() => {
  window.removeEventListener("designkp:save-settings", onGlobalSaveShortcut);
});
</script>

<template>
  <div class="settin_panel settingsPage" dir="rtl">
    <header class="settingsPage__header">
      <div class="settingsPage__titleWrap">
        <h2 class="settingsPage__title">تنظیمات</h2>
        <p class="settingsPage__caption">
          دسته‌بندی‌ها مثل پیش‌فرض‌های ساب‌کت در ستون راست قرار گرفته‌اند و هر بخش تنظیمات در پنل سمت چپ نمایش داده می‌شود.
        </p>
      </div>
      <button class="settingsPage__saveBtn" type="button" title="ذخیره تنظیمات" @click="handleSaveSettings">
        <img src="/icons/save.png" alt="" />
        <span>ذخیره</span>
      </button>
    </header>

    <div v-if="!hasEditor" class="settingsPage__hint">
      برای اعمال تنظیمات، اول صفحه «پلان» را باز کنید تا موتور 2D فعال شود.
    </div>

    <div class="settingsLayout">
      <section class="settingsPanel">
        <div v-if="activeSettingsSection" class="settingsPanel__head">
          <div class="settingsPanel__title">{{ activeSettingsSection.title }}</div>
          <div class="settingsPanel__caption">
            {{ activeSettingsSection.description }}
            <span>{{ activeSettingsSection.fields.length }} آیتم</span>
          </div>
        </div>

        <div v-if="activeSettingsSection" class="settingsGrid">
          <article
            v-for="field in activeSettingsSection.fields"
            :key="field.key"
            class="settingsCard"
            :class="{
              'settingsCard--toggle': field.kind === 'toggle',
              'settingsCard--colors': field.kind === 'color-group',
            }"
          >
            <div class="settingsCard__head">
              <h3 class="settingsCard__title">{{ field.label }}</h3>
              <p v-if="field.description" class="settingsCard__desc">{{ field.description }}</p>
            </div>

            <div v-if="field.kind === 'select'" class="settingsCard__body">
              <select class="settingsField settingsField--select" :value="getFieldValue(field)" @change="updateFieldValue(field, $event.target.value)">
                <option v-for="option in field.options" :key="option.value" :value="option.value">{{ option.label }}</option>
              </select>
            </div>

            <div v-else-if="field.kind === 'toggle'" class="settingsCard__body">
              <div class="settingsToggle">
                <button
                  type="button"
                  class="settingsToggle__btn"
                  :class="{ 'is-active': !model[field.key] }"
                  @click="updateFieldValue(field, false)"
                >
                  غیرفعال
                </button>
                <button
                  type="button"
                  class="settingsToggle__btn"
                  :class="{ 'is-active': !!model[field.key] }"
                  @click="updateFieldValue(field, true)"
                >
                  فعال
                </button>
              </div>
            </div>

            <div v-else-if="field.kind === 'color'" class="settingsCard__body">
              <label class="settingsColor">
                <input class="settingsColor__input" type="color" :value="model[field.key]" @input="updateFieldValue(field, $event.target.value)" />
                <span class="settingsColor__value">{{ model[field.key] }}</span>
              </label>
            </div>

            <div v-else-if="field.kind === 'color-group'" class="settingsCard__body">
              <div class="settingsColorGrid">
                <label v-for="colorItem in field.colors" :key="colorItem.key" class="settingsColor settingsColor--small">
                  <span class="settingsColor__label">{{ colorItem.label }}</span>
                  <template v-if="colorItem.kind === 'number'">
                    <input
                      class="settingsField"
                      type="number"
                      inputmode="decimal"
                      :min="colorItem.min"
                      :max="colorItem.max"
                      step="1"
                      :value="model[colorItem.key]"
                      @change="applyPatch({ [colorItem.key]: normalizePercentValue($event.target.value, model[colorItem.key] ?? 0) })"
                    />
                    <span class="settingsColor__value">{{ model[colorItem.key] }}{{ colorItem.unit }}</span>
                  </template>
                  <template v-else>
                    <input class="settingsColor__input" type="color" :value="model[colorItem.key]" @input="applyPatch({ [colorItem.key]: $event.target.value })" />
                    <span class="settingsColor__value">{{ model[colorItem.key] }}</span>
                  </template>
                </label>
              </div>
            </div>

            <div v-else class="settingsCard__body">
              <input
                class="settingsField"
                :class="{ 'settingsField--text': field.kind === 'text' }"
                :type="field.kind === 'text' ? 'text' : 'number'"
                :inputmode="field.kind === 'text' ? undefined : 'decimal'"
                :min="getFieldMin(field)"
                :step="getFieldStep(field)"
                :value="getFieldValue(field)"
                :placeholder="field.placeholder || field.label"
                @change="updateFieldValue(field, $event.target.value)"
              />
              <div v-if="getFieldUnitLabel(field)" class="settingsCard__unit">{{ getFieldUnitLabel(field) }}</div>
            </div>
          </article>
        </div>
      </section>

      <aside class="settingsSidebar">
        <div class="settingsSidebar__head">
          <div class="settingsSidebar__title">دسته‌بندی تنظیمات</div>
          <div class="settingsSidebar__caption">{{ settingsSections.length }} گروه</div>
        </div>
        <div class="settingsSidebar__list">
          <button
            v-for="section in settingsSections"
            :key="section.id"
            type="button"
            class="settingsSidebar__tab"
            :class="{ 'is-active': activeSettingsSection?.id === section.id }"
            @click="selectSection(section.id)"
          >
            <span class="settingsSidebar__tabTitle">{{ section.title }}</span>
            <span class="settingsSidebar__tabMeta">{{ section.fields.length }} آیتم</span>
          </button>
        </div>
      </aside>
    </div>
  </div>
</template>
