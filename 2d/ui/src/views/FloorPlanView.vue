<script setup>
import { onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from "vue";
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
} from "../editor/editor_store.js";
import {
  editorSettingsPayloadToState,
  editorSettingsStateToPayload,
  fetchPersistedEditorSettings,
  savePersistedEditorSettings,
} from "../editor/editor_settings.js";
import { CURRENT_ADMIN_ID, CURRENT_BOOTSTRAP_USER_ID } from "../features/part_kinds_catalog.js";
import { createWallApp } from "../../../main.js";

const hostEl = ref(null);
const canvasEl = ref(null);
let settingsSaveTimeout = 0;
let lastSettingsSignature = "";

function editorHasRenderableContent() {
  const snapshot = editorRef.value?.getState?.();
  if (!snapshot) return false;
  const counts = snapshot.counts || {};
  const model2d = snapshot.model2d || {};
  return (
    Number(counts.solidWalls || 0) > 0 ||
    Number(counts.hiddenWalls || 0) > 0 ||
    Number(counts.dimensions || 0) > 0 ||
    Number(model2d.lines || 0) > 0
  );
}

function queueSettingsPersist(state) {
  const payload = editorSettingsStateToPayload(state || {});
  const signature = JSON.stringify(payload);
  if (signature === lastSettingsSignature) return;
  if (settingsSaveTimeout) window.clearTimeout(settingsSaveTimeout);
  settingsSaveTimeout = window.setTimeout(async () => {
    settingsSaveTimeout = 0;
    try {
      await savePersistedEditorSettings(CURRENT_ADMIN_ID, CURRENT_BOOTSTRAP_USER_ID, payload);
      lastSettingsSignature = signature;
    } catch (_) {}
  }, 500);
}

onMounted(() => {
  if (!hostEl.value || !canvasEl.value) return;

  // Ensure a single engine instance per tab (KeepAlive preserves the component).
  if (!editorRef.value) {
    editorRef.value = createWallApp({
      canvas: canvasEl.value,
      container: hostEl.value,
      onModel2dTransformChange: (t) => {
        const x = Number.isFinite(t?.x) ? t.x : 0;
        const y = Number.isFinite(t?.y) ? t.y : 0;
        const rotRad = Number.isFinite(t?.rotRad) ? t.rotRad : 0;
        const mirrorX = Number(t?.mirrorX) === -1 ? -1 : 1;
        model2dTransformRef.value = {
          x,
          y,
          rotRad,
          mirrorX,
          interactive: !!t?.interactive,
          phase: String(t?.phase || (t?.interactive ? "drag" : "commit")),
        };
      },
      onViewportChange: (viewport) => {
        editorViewportRef.value = {
          zoom: Number.isFinite(viewport?.zoom) ? viewport.zoom : 1,
          offsetX: Number.isFinite(viewport?.offsetX) ? viewport.offsetX : 0,
          offsetY: Number.isFinite(viewport?.offsetY) ? viewport.offsetY : 0,
        };
      },
      onPassiveModelSelect: (modelId) => {
        const handler = passiveModelSelectionHandlerRef.value;
        if (typeof handler === "function") handler(modelId);
      },
      onPassiveModelSelectionChange: (modelIds) => {
        passiveModelSelectionStateRef.value = Array.isArray(modelIds) ? modelIds.slice() : [];
      },
      onPassiveModelsTransformChange: (models) => {
        passiveModelTransformStateRef.value = Array.isArray(models) ? models.slice() : [];
      },
      onActiveModelDelete: () => {
        const handler = activeModelDeleteHandlerRef.value;
        if (typeof handler === "function") handler();
      },
      onOrderDesignDeleteRequest: async (payload) => {
        const handler = orderDesignDeleteHandlerRef.value;
        if (typeof handler === "function") return await handler(payload);
        return false;
      },
      onOrderDesignDuplicateRequest: async (payload) => {
        const handler = orderDesignDuplicateHandlerRef.value;
        if (typeof handler === "function") return await handler(payload);
        return null;
      },
      onOrderDesignMirrorRequest: async (payload) => {
        const handler = orderDesignMirrorHandlerRef.value;
        if (typeof handler === "function") return await handler(payload);
        return null;
      },
      captureExternalHistoryState: () => {
        const handler = externalHistoryCaptureHandlerRef.value;
        if (typeof handler === "function") return handler();
        return null;
      },
      restoreExternalHistoryState: async (snap, meta) => {
        const handler = externalHistoryRestoreHandlerRef.value;
        if (typeof handler === "function") return await handler(snap, meta);
        return null;
      },
      onFitViewToAll: () => {
        const handler = fitAllHandlerRef.value;
        if (typeof handler === "function") handler();
      },
      onSettingsChange: (state) => {
        queueSettingsPersist(state);
      },
    });
    editorRef.value.setInputEnabled?.(false);
    fetchPersistedEditorSettings(CURRENT_ADMIN_ID, CURRENT_BOOTSTRAP_USER_ID)
      .then((payload) => {
        const patch = editorSettingsPayloadToState(payload);
        lastSettingsSignature = JSON.stringify(editorSettingsStateToPayload(patch));
        if (!editorHasRenderableContent()) {
          editorRef.value?.setState?.(patch);
        }
      })
      .catch(() => {})
      .finally(() => {
        // Vue shell starts in "no drawing" mode.
        editorRef.value?.setActiveTool?.("select");
        editorRef.value?.setUiCursorMode?.(null);
        editorRef.value?.setInputEnabled?.(true);
      });
  } else {
    editorRef.value.setInputEnabled?.(true);
  }
  editorRef.value.attach();
});

onActivated(() => {
  editorRef.value?.attach();
});

onDeactivated(() => {
  editorRef.value?.detach();
});

onBeforeUnmount(() => {
  if (settingsSaveTimeout) window.clearTimeout(settingsSaveTimeout);
  settingsSaveTimeout = 0;
  editorRef.value?.destroy?.();
  editorRef.value = null;
});
</script>

<template>
  <div ref="hostEl" class="fpHost">
    <canvas ref="canvasEl" class="fpCanvas"></canvas>
  </div>
</template>
