<script setup>
import { computed, reactive, ref, watchEffect } from "vue";
import { useRouter } from "vue-router";
import { editorRef } from "../editor/editor_store.js";

const hasEditor = computed(() => !!editorRef.value);
const router = useRouter();
const baseState = ref(null);
const isHydrating = ref(true);

const model = reactive({
  unit: "cm",
  wallThicknessMm: 120,
  wallHeightMm: 3000,
  hiddenWallThicknessMm: 1,

  dimOffsetMm: 150,
  dimFontPx: 15,
  dimLineWidthPx: 2,

  meterDivisions: 10,
  majorEvery: 10,

  fontFamily: "Tahoma",
  wallNameFontPx: 15,
  angleFontPx: 12,

  snapOn: true,
  showDimensions: true,
  stepDrawEnabled: true,
  stepLineCm: 5,
  stepAngleDeg: 10,
  snapCornerEnabled: true,
  snapMidEnabled: true,
  snapCenterEnabled: true,
  snapEdgeEnabled: true,
  wallMagnetEnabled: true,

  // Colors
  bgColor: "#FFFFFF",
  minorColor: "#E6E6E6",
  majorColor: "#A3A3A3",
  axisXColor: "#9CC9B4",
  axisYColor: "#BCC8EB",

  wallFillColor: "#A6A6A6",
  wallEdgeColor: "#000000",
  wallTextColor: "#FFFFFF",
  wallHeightColor: "#4B5563",

  dimColor: "#E8A559",
  hiddenWallColor: "#D8D4D4",

  offsetWallEnabled: true,
  offsetWallDistanceMm: 600,
});

function positiveOrFallback(value, fallback, min = 0.0001) {
  const parsed = Number(value);
  return Number.isFinite(parsed) && parsed > min ? parsed : fallback;
}

watchEffect(() => {
  // Hydrate once from editor state; do not overwrite local unsaved edits.
  const st = editorRef.value?.getState?.()?.state;
  if (!st) return;
  if (!isHydrating.value) return;

  const nextBase = {};
  for (const k of Object.keys(model)) {
    if (k in st) model[k] = st[k];
    nextBase[k] = (k in st) ? st[k] : model[k];
  }
  baseState.value = nextBase;
  isHydrating.value = false;
});

function applyPatch(patch) {
  if (!patch || typeof patch !== "object") return;
  // Local draft only; nothing is applied to engine until Save is clicked.
  Object.assign(model, patch);
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
  if (!editorRef.value) {
    await dialogs.alert("ابتدا وارد صفحه پلان شوید تا موتور 2D فعال شود.", { title: "تنظیمات" });
    return;
  }

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

  if (Object.keys(patch).length > 0) {
    editorRef.value?.setState?.(patch);
    baseState.value = { ...base, ...patch };
  }
  router.push("/");
}
</script>

<template>
  <div style="padding: 14px;" class="settin_panel">
    <div style="display:flex; align-items:center; justify-content:space-between; gap:10px; margin: 0 0 12px;">
      <h3 style="margin: 0;">تنظیمات</h3>
      <button class="iconbtn iconbtn--sm" type="button" title="ذخیره تنظیمات" @click="handleSaveSettings">
        <img src="/icons/save.png" alt="" />
      </button>
    </div>
    <div v-if="!hasEditor" style="color:#6b7280; font-size:13px; line-height:1.7; margin-bottom: 12px;">
      برای اعمال تنظیمات، اول صفحه «پلان» را باز کنید تا موتور 2D فعال شود.
    </div>

    <div class="panel">
      <div class="panel__title">واحدها و دیوار</div>
      <div class="row">
        <label class="label">واحد نمایش</label>
        <select
          class="input"
          :value="model.unit"
          @change="model.unit = $event.target.value; applyPatch({ unit: model.unit })"
        >
          <option value="mm">میلی‌متر</option>
          <option value="cm">سانتی‌متر</option>
        </select>
      </div>
      <div class="row">
        <label class="label">ضخامت دیوار (سانتی‌متر)</label>
        <input
          class="input ltr"
          type="number"
          min="1"
          step="0.5"
          :value="(model.wallThicknessMm || 120) / 10"
          @change="applyPatch({ wallThicknessMm: Math.max(1, (+$event.target.value || 12) * 10) })"
        />
      </div>
      <div class="row">
        <label class="label">ارتفاع دیوار (سانتی‌متر)</label>
        <input
          class="input ltr"
          type="number"
          min="1"
          step="1"
          :value="(model.wallHeightMm || 3000) / 10"
          @change="applyPatch({ wallHeightMm: Math.max(1, (+$event.target.value || 300) * 10) })"
        />
      </div>
      <div class="row">
        <label class="label">ضخامت پیش‌فرض خط راهنما (سانتی‌متر)</label>
        <input
          class="input ltr"
          type="number"
          min="0.1"
          step="0.1"
          :value="(model.hiddenWallThicknessMm || 1) / 10"
          @change="applyPatch({ hiddenWallThicknessMm: Math.max(0.1, (+$event.target.value || 0.1) * 10) })"
        />
      </div>
    </div>

    <div class="panel">
      <div class="panel__title">دایمنشن</div>
      <div class="row">
        <label class="label">فاصله دایمنشن از دیوار (میلی‌متر)</label>
        <input
          class="input ltr"
          type="number"
          min="0"
          step="10"
          :value="model.dimOffsetMm"
          @change="applyPatch({ dimOffsetMm: +$event.target.value || 0 })"
        />
      </div>
      <div class="row">
        <label class="label">فونت دایمنشن (px)</label>
        <input
          class="input ltr"
          type="number"
          min="8"
          step="1"
          :value="model.dimFontPx"
          @change="applyPatch({ dimFontPx: +$event.target.value || model.dimFontPx })"
        />
      </div>
      <div class="row">
        <label class="label">ضخامت خط دایمنشن (px)</label>
        <input
          class="input ltr"
          type="number"
          min="1"
          step="0.5"
          :value="model.dimLineWidthPx"
          @change="applyPatch({ dimLineWidthPx: +$event.target.value || model.dimLineWidthPx })"
        />
      </div>
    </div>

    <div class="panel">
      <div class="panel__title">گرید</div>
      <div class="row">
        <label class="label">تقسیمات هر متر</label>
        <input
          class="input ltr"
          type="number"
          min="2"
          step="1"
          :value="model.meterDivisions"
          @change="applyPatch({ meterDivisions: +$event.target.value || 10 })"
        />
      </div>
      <div class="row">
        <label class="label">هر چند خانه یک خط درشت</label>
        <input
          class="input ltr"
          type="number"
          min="2"
          step="1"
          :value="model.majorEvery"
          @change="applyPatch({ majorEvery: +$event.target.value || 10 })"
        />
      </div>
    </div>

    <div class="panel">
      <div class="panel__title">نمایش و اسنپ</div>
      <div class="row">
        <label class="label">نمایش دایمنشن ها</label>
        <label style="display:flex; gap:10px; align-items:center;">
          <input
            type="checkbox"
            :checked="!!model.showDimensions"
            @change="applyPatch({ showDimensions: !!$event.target.checked })"
          />
          <span style="font-size:13px; color:#111827;">فعال</span>
        </label>
      </div>
      <div class="row">
        <label class="label">رسم گام به گام</label>
        <label style="display:flex; gap:10px; align-items:center;">
          <input
            type="checkbox"
            :checked="!!model.stepDrawEnabled"
            @change="applyPatch({ stepDrawEnabled: !!$event.target.checked })"
          />
          <span style="font-size:13px; color:#111827;">فعال</span>
        </label>
      </div>
      <div style="margin: 4px 0 10px; padding: 10px; border: 1px solid #e5e7eb; border-radius: 8px;">
        <div style="font-size: 12px; color: #374151; margin-bottom: 8px;">رسم گام به گام</div>
        <div class="row" style="margin-bottom: 8px;">
          <label class="label">گام خط (سانتی‌متر)</label>
          <input
            class="input ltr"
            type="number"
            min="0.1"
            step="0.5"
            :value="model.stepLineCm"
            @change="applyPatch({ stepLineCm: positiveOrFallback($event.target.value, model.stepLineCm) })"
          />
        </div>
        <div class="row" style="margin-bottom: 0;">
          <label class="label">گام زاویه (درجه)</label>
          <input
            class="input ltr"
            type="number"
            min="0.1"
            step="1"
            :value="model.stepAngleDeg"
            @change="applyPatch({ stepAngleDeg: positiveOrFallback($event.target.value, model.stepAngleDeg) })"
          />
        </div>
      </div>
      <div class="row">
        <label class="label">اسنپ</label>
        <label style="display:flex; gap:10px; align-items:center;">
          <input
            type="checkbox"
            :checked="!!model.snapOn"
            @change="applyPatch({ snapOn: !!$event.target.checked })"
          />
          <span style="font-size:13px; color:#111827;">روشن</span>
        </label>
      </div>
      <div class="row">
        <label class="label">اسنپ گوشه</label>
        <label style="display:flex; gap:10px; align-items:center;">
          <input
            type="checkbox"
            :checked="!!model.snapCornerEnabled"
            @change="applyPatch({ snapCornerEnabled: !!$event.target.checked })"
          />
          <span style="font-size:13px; color:#111827;">فعال</span>
        </label>
      </div>
      <div class="row">
        <label class="label">اسنپ وسط ضلع</label>
        <label style="display:flex; gap:10px; align-items:center;">
          <input
            type="checkbox"
            :checked="!!model.snapMidEnabled"
            @change="applyPatch({ snapMidEnabled: !!$event.target.checked })"
          />
          <span style="font-size:13px; color:#111827;">فعال</span>
        </label>
      </div>
      <div class="row">
        <label class="label">اسنپ آکس وسط</label>
        <label style="display:flex; gap:10px; align-items:center;">
          <input
            type="checkbox"
            :checked="!!model.snapCenterEnabled"
            @change="applyPatch({ snapCenterEnabled: !!$event.target.checked })"
          />
          <span style="font-size:13px; color:#111827;">فعال</span>
        </label>
      </div>
      <div class="row">
        <label class="label">اسنپ لبه</label>
        <label style="display:flex; gap:10px; align-items:center;">
          <input
            type="checkbox"
            :checked="!!model.snapEdgeEnabled"
            @change="applyPatch({ snapEdgeEnabled: !!$event.target.checked })"
          />
          <span style="font-size:13px; color:#111827;">فعال</span>
        </label>
      </div>
      <div class="row">
        <label class="label">اسنپ مغناطیسی دیوار</label>
        <label style="display:flex; gap:10px; align-items:center;">
          <input
            type="checkbox"
            :checked="!!model.wallMagnetEnabled"
            @change="applyPatch({ wallMagnetEnabled: !!$event.target.checked })"
          />
          <span style="font-size:13px; color:#111827;">فعال</span>
        </label>
      </div>
      <div class="row">
        <label class="label">Offset Wall</label>
        <label style="display:flex; gap:10px; align-items:center;">
          <input
            type="checkbox"
            :checked="!!model.offsetWallEnabled"
            @change="applyPatch({ offsetWallEnabled: !!$event.target.checked })"
          />
          <span style="font-size:13px; color:#111827;">فعال</span>
        </label>
      </div>
      <div class="row">
        <label class="label">فاصله Offset (میلی‌متر)</label>
        <input
          class="input ltr"
          type="number"
          min="0"
          step="10"
          :value="model.offsetWallDistanceMm"
          @change="applyPatch({ offsetWallDistanceMm: +$event.target.value || model.offsetWallDistanceMm })"
        />
      </div>
    </div>

    <div class="panel">
      <div class="panel__title">فونت‌ها</div>
      <div class="row">
        <label class="label">Font Family</label>
        <input
          class="input ltr"
          type="text"
          :value="model.fontFamily"
          @change="applyPatch({ fontFamily: $event.target.value || 'Tahoma' })"
        />
      </div>
      <div class="row">
        <label class="label">فونت نام دیوار (px)</label>
        <input
          class="input ltr"
          type="number"
          min="8"
          step="1"
          :value="model.wallNameFontPx"
          @change="applyPatch({ wallNameFontPx: +$event.target.value || model.wallNameFontPx })"
        />
      </div>
      <div class="row">
        <label class="label">فونت زاویه (px)</label>
        <input
          class="input ltr"
          type="number"
          min="8"
          step="1"
          :value="model.angleFontPx"
          @change="applyPatch({ angleFontPx: +$event.target.value || model.angleFontPx })"
        />
      </div>
    </div>

    <div class="panel">
      <div class="panel__title">رنگ‌ها</div>
      <div class="row">
        <label class="label">Background</label>
        <input type="color" :value="model.bgColor" @input="applyPatch({ bgColor: $event.target.value })" />
      </div>
      <div class="row">
        <label class="label">Grid Minor / Major</label>
        <div style="display:flex; gap:10px; align-items:center;">
          <input type="color" :value="model.minorColor" @input="applyPatch({ minorColor: $event.target.value })" />
          <input type="color" :value="model.majorColor" @input="applyPatch({ majorColor: $event.target.value })" />
        </div>
      </div>
      <div class="row">
        <label class="label">Axis X / Y</label>
        <div style="display:flex; gap:10px; align-items:center;">
          <input type="color" :value="model.axisXColor" @input="applyPatch({ axisXColor: $event.target.value })" />
          <input type="color" :value="model.axisYColor" @input="applyPatch({ axisYColor: $event.target.value })" />
        </div>
      </div>
      <div class="row">
        <label class="label">Wall (Fill / Edge / Text)</label>
        <div style="display:flex; gap:10px; align-items:center;">
          <input type="color" :value="model.wallFillColor" @input="applyPatch({ wallFillColor: $event.target.value })" />
          <input type="color" :value="model.wallEdgeColor" @input="applyPatch({ wallEdgeColor: $event.target.value })" />
          <input type="color" :value="model.wallTextColor" @input="applyPatch({ wallTextColor: $event.target.value })" />
        </div>
      </div>
      <div class="row">
        <label class="label">Wall Height (Temp)</label>
        <div style="display:flex; gap:10px; align-items:center;">
          <input type="color" :value="model.wallHeightColor" @input="applyPatch({ wallHeightColor: $event.target.value })" />
        </div>
      </div>
      <div class="row">
        <label class="label">Dimension / خط راهنما</label>
        <div style="display:flex; gap:10px; align-items:center;">
          <input type="color" :value="model.dimColor" @input="applyPatch({ dimColor: $event.target.value })" />
          <input type="color" :value="model.hiddenWallColor" @input="applyPatch({ hiddenWallColor: $event.target.value })" />
        </div>
      </div>
    </div>
  </div>
</template>
