<script setup>
import { onActivated, onBeforeUnmount, onDeactivated, onMounted, ref } from "vue";
import { editorRef, model2dTransformRef } from "../editor/editor_store.js";
import { createWallApp } from "../../../main.js";

const hostEl = ref(null);
const canvasEl = ref(null);

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
        model2dTransformRef.value = { x, y, rotRad };
      },
    });
    // Vue shell starts in "no drawing" mode.
    editorRef.value.setActiveTool?.("select");
    editorRef.value.setUiCursorMode?.(null);
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
  editorRef.value?.destroy?.();
  editorRef.value = null;
});
</script>

<template>
  <div ref="hostEl" class="fpHost">
    <canvas ref="canvasEl" class="fpCanvas"></canvas>
  </div>
</template>
