<script setup>
import { computed, nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";

const props = defineProps({
  scene: {
    type: Object,
    default: () => null,
  },
  cursorClass: {
    type: String,
    default: "is-idle",
  },
});

const emit = defineEmits([
  "pointerdown",
  "pointermove",
  "pointerup",
  "pointercancel",
  "pointerleave",
  "canvas-wheel",
  "contextmenu",
  "dblclick",
]);

const wrapEl = ref(null);
const canvasEl = ref(null);
const viewport = ref({ width: 320, height: 320 });
let resizeObserver = null;
let drawRafId = 0;
let backgroundCanvas = null;
let backgroundCanvasCtx = null;
let backgroundToken = "";

function syncViewport() {
  const el = wrapEl.value;
  if (!el) {
    viewport.value = { width: 320, height: 320 };
    return;
  }
  viewport.value = {
    width: Math.max(320, Math.round(el.clientWidth || 320)),
    height: Math.max(320, Math.round(el.clientHeight || 320)),
  };
}

const sceneViewBox = computed(() => {
  const raw = props.scene?.viewBox || {};
  const baseX = Number(raw.x) || 0;
  const baseY = Number(raw.y) || 0;
  const baseWidth = Math.max(1, Number(raw.width) || 1);
  const baseHeight = Math.max(1, Number(raw.height) || 1);
  const viewportWidth = Math.max(1, Number(viewport.value.width) || 1);
  const viewportHeight = Math.max(1, Number(viewport.value.height) || 1);
  const boxRatio = baseWidth / baseHeight;
  const viewportRatio = viewportWidth / viewportHeight;
  if (!Number.isFinite(boxRatio) || !Number.isFinite(viewportRatio) || boxRatio <= 0 || viewportRatio <= 0) {
    return {
      x: baseX,
      y: baseY,
      width: baseWidth,
      height: baseHeight,
    };
  }
  if (Math.abs(boxRatio - viewportRatio) < 0.0001) {
    return {
      x: baseX,
      y: baseY,
      width: baseWidth,
      height: baseHeight,
    };
  }
  if (boxRatio > viewportRatio) {
    const expandedHeight = Math.max(1, baseWidth / viewportRatio);
    const delta = (expandedHeight - baseHeight) * 0.5;
    return {
      x: baseX,
      y: baseY - delta,
      width: baseWidth,
      height: expandedHeight,
    };
  }
  const expandedWidth = Math.max(1, baseHeight * viewportRatio);
  const delta = (expandedWidth - baseWidth) * 0.5;
  return {
    x: baseX - delta,
    y: baseY,
    width: expandedWidth,
    height: baseHeight,
  };
});

const screenTransform = computed(() => {
  const box = sceneViewBox.value;
  const width = Math.max(1, Number(viewport.value.width) || 1);
  const height = Math.max(1, Number(viewport.value.height) || 1);
  const scale = Math.min(width / box.width, height / box.height);
  const drawWidth = box.width * scale;
  const drawHeight = box.height * scale;
  return {
    scale,
    offsetX: (width - drawWidth) * 0.5,
    offsetY: (height - drawHeight) * 0.5,
  };
});

function worldToScreen(point) {
  const box = sceneViewBox.value;
  const transform = screenTransform.value;
  return {
    x: transform.offsetX + (((Number(point?.x) || 0) - box.x) * transform.scale),
    y: transform.offsetY + (((Number(point?.y) || 0) - box.y) * transform.scale),
  };
}

function screenToWorld(event) {
  const canvas = canvasEl.value;
  if (!canvas || !event) return null;
  const rect = canvas.getBoundingClientRect();
  if (!rect.width || !rect.height) return null;
  const clientX = Number(event.clientX);
  const clientY = Number(event.clientY);
  if (!Number.isFinite(clientX) || !Number.isFinite(clientY)) return null;
  const box = sceneViewBox.value;
  const transform = screenTransform.value;
  const localX = clientX - rect.left - transform.offsetX;
  const localY = clientY - rect.top - transform.offsetY;
  if (localX < 0 || localY < 0) return null;
  const maxX = box.width * transform.scale;
  const maxY = box.height * transform.scale;
  if (localX > maxX || localY > maxY) return null;
  return {
    x: box.x + (localX / transform.scale),
    y: box.y + (localY / transform.scale),
  };
}

function pointInRect(point, rect, padding = 0) {
  if (!rect || !point) return false;
  const px = Number(point.x) || 0;
  const py = Number(point.y) || 0;
  return (
    px >= (Number(rect.x) || 0) - padding &&
    px <= (Number(rect.x) || 0) + (Number(rect.w) || 0) + padding &&
    py >= (Number(rect.y) || 0) - padding &&
    py <= (Number(rect.y) || 0) + (Number(rect.h) || 0) + padding
  );
}

function distancePointToSegment(point, start, end) {
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

function hitTestScene(point) {
  if (!point || !props.scene) return null;
  const controllerOverlays = Array.isArray(props.scene.controllers) ? props.scene.controllers : [];
  for (let i = controllerOverlays.length - 1; i >= 0; i -= 1) {
    const overlay = controllerOverlays[i];
    for (const metric of overlay?.metrics || []) {
      if (pointInRect(point, { x: metric.fieldX, y: metric.fieldY, w: metric.inputW, h: metric.inputH })) {
        return { type: "controller-metric", overlayId: overlay.id, controllerId: metric.id };
      }
    }
    for (const controller of overlay?.visuals || []) {
      if (pointInRect(point, { x: controller.fieldX, y: controller.fieldY, w: controller.inputW, h: controller.inputH })) {
        return { type: "controller-field", overlayId: overlay.id, controllerId: controller.id };
      }
      const handleRect = {
        x: Number(controller.x) || 0,
        y: Number(controller.y) || 0,
        w: Number(controller.w) || 0,
        h: Number(controller.h) || 0,
      };
      if (pointInRect(point, handleRect, 0)) {
        return { type: "controller-handle", overlayId: overlay.id, controllerId: controller.id };
      }
    }
    if (pointInRect(point, overlay?.rect, 0)) {
      return { type: "controller-rect", overlayId: overlay.id };
    }
  }

  const annotations = Array.isArray(props.scene?.annotations?.dimensions) ? props.scene.annotations.dimensions : [];
  for (let i = annotations.length - 1; i >= 0; i -= 1) {
    const item = annotations[i];
    const tolerance = 12;
    const minX = Math.min(Number(item?.screenStart?.x) || 0, Number(item?.screenEnd?.x) || 0) - tolerance;
    const maxX = Math.max(Number(item?.screenStart?.x) || 0, Number(item?.screenEnd?.x) || 0) + tolerance;
    const minY = Math.min(Number(item?.screenStart?.y) || 0, Number(item?.screenEnd?.y) || 0) - tolerance;
    const maxY = Math.max(Number(item?.screenStart?.y) || 0, Number(item?.screenEnd?.y) || 0) + tolerance;
    if (point.x < minX || point.x > maxX || point.y < minY || point.y > maxY) continue;
    const dist = distancePointToSegment(point, item?.screenStart, item?.screenEnd);
    if (dist <= tolerance) {
      return { type: "annotation", annotationId: item.id };
    }
  }

  const entities = Array.isArray(props.scene.entities) ? props.scene.entities : [];
  const cache = props.scene?.hitCache;
  const candidateEntities = [];
  if (cache?.buckets && cache?.bucketSize) {
    const baseCol = Math.floor((Number(point.x) || 0) / cache.bucketSize);
    const baseRow = Math.floor((Number(point.y) || 0) / cache.bucketSize);
    const seen = new Set();
    for (let row = baseRow - 1; row <= baseRow + 1; row += 1) {
      for (let col = baseCol - 1; col <= baseCol + 1; col += 1) {
        for (const item of cache.buckets.get(`${col}:${row}`) || []) {
          const id = String(item?.id || "");
          if (!id || seen.has(id)) continue;
          seen.add(id);
          candidateEntities.push(id);
        }
      }
    }
  }
  const entityMap = new Map(entities.map((entity) => [String(entity?.id || ""), entity]));
  const hitEntities = candidateEntities.length
    ? candidateEntities.map((id) => entityMap.get(id)).filter(Boolean)
    : entities;
  for (let i = hitEntities.length - 1; i >= 0; i -= 1) {
    const entity = hitEntities[i];
    if (pointInRect(point, entity?.boundsRect, 8)) {
      return { type: "entity", entityId: entity.id };
    }
  }
  return null;
}

function emitPointer(name, event) {
  const point = screenToWorld(event);
  emit(name, {
    event,
    point,
    hit: point ? hitTestScene(point) : null,
  });
}

function drawLine(ctx, line, color, width = 1, dashed = false, alpha = 1) {
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = width;
  ctx.lineCap = "round";
  ctx.globalAlpha = alpha;
  if (dashed) ctx.setLineDash([6, 8]);
  ctx.beginPath();
  ctx.moveTo(Number(line?.x1) || 0, Number(line?.y1) || 0);
  ctx.lineTo(Number(line?.x2) || 0, Number(line?.y2) || 0);
  ctx.stroke();
  ctx.restore();
}

function drawWorldLine(ctx, line, color, width = 1, dashed = false, alpha = 1) {
  const start = worldToScreen({ x: line?.x1, y: line?.y1 });
  const end = worldToScreen({ x: line?.x2, y: line?.y2 });
  drawLine(ctx, { x1: start.x, y1: start.y, x2: end.x, y2: end.y }, color, width, dashed, alpha);
}

function drawGrid(ctx) {
  const box = sceneViewBox.value;
  const spacing = 40;
  const startX = Math.floor(box.x / spacing) * spacing;
  const endX = box.x + box.width;
  const startY = Math.floor(box.y / spacing) * spacing;
  const endY = box.y + box.height;
  ctx.save();
  ctx.strokeStyle = "rgba(90,60,66,0.08)";
  ctx.lineWidth = 1;
  for (let x = startX; x <= endX; x += spacing) {
    drawWorldLine(ctx, { x1: x, y1: box.y, x2: x, y2: endY }, "rgba(90,60,66,0.08)", 1, false, 1);
  }
  for (let y = startY; y <= endY; y += spacing) {
    drawWorldLine(ctx, { x1: box.x, y1: y, x2: endX, y2: y }, "rgba(90,60,66,0.08)", 1, false, 1);
  }
  ctx.restore();
}

function drawRectWorld(ctx, rect, options = {}) {
  if (!rect) return;
  const topLeft = worldToScreen({ x: rect.x, y: rect.y });
  const bottomRight = worldToScreen({ x: (Number(rect.x) || 0) + (Number(rect.w) || 0), y: (Number(rect.y) || 0) + (Number(rect.h) || 0) });
  const x = Math.min(topLeft.x, bottomRight.x);
  const y = Math.min(topLeft.y, bottomRight.y);
  const w = Math.abs(bottomRight.x - topLeft.x);
  const h = Math.abs(bottomRight.y - topLeft.y);
  ctx.save();
  if (options.fill) {
    ctx.fillStyle = options.fill;
    ctx.globalAlpha = options.fillAlpha == null ? 1 : options.fillAlpha;
    ctx.fillRect(x, y, w, h);
  }
  if (options.stroke) {
    ctx.strokeStyle = options.stroke;
    ctx.lineWidth = options.lineWidth || 1;
    ctx.globalAlpha = options.strokeAlpha == null ? 1 : options.strokeAlpha;
    if (options.dashed) ctx.setLineDash(options.dashPattern || [6, 6]);
    ctx.strokeRect(x, y, w, h);
  }
  ctx.restore();
}

function drawTextBoxWorld(ctx, rect, text, options = {}) {
  if (!rect) return;
  drawRectWorld(ctx, rect, {
    fill: options.fill || "rgba(255,255,255,0.94)",
    stroke: options.stroke || "rgba(94,50,69,0.24)",
    lineWidth: 1,
  });
  const center = worldToScreen({
    x: (Number(rect.x) || 0) + ((Number(rect.w) || 0) * 0.5),
    y: (Number(rect.y) || 0) + ((Number(rect.h) || 0) * 0.5),
  });
  ctx.save();
  ctx.fillStyle = options.textColor || "#5e3245";
  ctx.font = options.font || "12px Tahoma";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(String(text || ""), center.x, center.y);
  ctx.restore();
}

function drawControllerHandle(ctx, controller, color, isActive) {
  if (!controller || controller.showBody === false) return;
  drawRectWorld(ctx, {
    x: controller.x,
    y: controller.y,
    w: controller.w,
    h: controller.h,
  }, {
    fill: isActive ? "rgba(47,127,211,0.16)" : "rgba(255,255,255,0.92)",
    stroke: color,
    lineWidth: isActive ? 2 : 1.25,
  });
  const center = worldToScreen({
    x: (Number(controller.x) || 0) + ((Number(controller.w) || 0) * 0.5),
    y: (Number(controller.y) || 0) + ((Number(controller.h) || 0) * 0.5),
  });
  ctx.save();
  ctx.strokeStyle = color;
  ctx.lineWidth = 1.6;
  ctx.lineCap = "round";
  if (controller.kind === "horizontal") {
    ctx.beginPath();
    ctx.moveTo(center.x - 8, center.y);
    ctx.lineTo(center.x + 8, center.y);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(center.x - 8, center.y);
    ctx.lineTo(center.x - 3, center.y - 4);
    ctx.moveTo(center.x - 8, center.y);
    ctx.lineTo(center.x - 3, center.y + 4);
    ctx.moveTo(center.x + 8, center.y);
    ctx.lineTo(center.x + 3, center.y - 4);
    ctx.moveTo(center.x + 8, center.y);
    ctx.lineTo(center.x + 3, center.y + 4);
    ctx.stroke();
  } else {
    ctx.beginPath();
    ctx.moveTo(center.x, center.y - 8);
    ctx.lineTo(center.x, center.y + 8);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(center.x, center.y - 8);
    ctx.lineTo(center.x - 4, center.y - 3);
    ctx.moveTo(center.x, center.y - 8);
    ctx.lineTo(center.x + 4, center.y - 3);
    ctx.moveTo(center.x, center.y + 8);
    ctx.lineTo(center.x - 4, center.y + 3);
    ctx.moveTo(center.x, center.y + 8);
    ctx.lineTo(center.x + 4, center.y + 3);
    ctx.stroke();
  }
  ctx.restore();
}

function drawControllerOverlayRect(ctx, overlay) {
  if (!overlay?.rect) return;
  const accent = overlay.lineColor || "#b94f74";
  if (overlay.selected) {
    drawRectWorld(ctx, overlay.rect, {
      fill: "rgba(244, 214, 225, 0.82)",
      stroke: accent,
      lineWidth: 2.2,
      strokeAlpha: 1,
    });
    drawRectWorld(ctx, {
      x: (Number(overlay.rect.x) || 0) + 0.8,
      y: (Number(overlay.rect.y) || 0) + 0.8,
      w: Math.max(0, (Number(overlay.rect.w) || 0) - 1.6),
      h: Math.max(0, (Number(overlay.rect.h) || 0) - 1.6),
    }, {
      stroke: "rgba(255,255,255,0.82)",
      lineWidth: 0.9,
      strokeAlpha: 0.95,
    });
    return;
  }
  drawRectWorld(ctx, overlay.rect, {
    stroke: accent,
    lineWidth: 1.5,
    dashed: !!overlay.showDashed,
    strokeAlpha: 0.96,
  });
}

function ensureBackgroundContext(width, height, dpr) {
  if (!backgroundCanvas) {
    backgroundCanvas = document.createElement("canvas");
    backgroundCanvasCtx = backgroundCanvas.getContext("2d");
  }
  backgroundCanvas.width = Math.round(width * dpr);
  backgroundCanvas.height = Math.round(height * dpr);
  backgroundCanvasCtx?.setTransform(dpr, 0, 0, dpr, 0, 0);
  backgroundCanvasCtx?.clearRect(0, 0, width, height);
  return backgroundCanvasCtx;
}

function drawEntityBase(ctx, entity, state) {
  const safeState = state || {};
  for (const line of entity.innerLines || []) {
    drawWorldLine(ctx, line, entity.lineColor || "#7B858C", safeState.innerStrokeWidth || 1.4, !!line.dashed, safeState.innerOpacity == null ? 1 : safeState.innerOpacity);
  }
  for (const line of entity.outerLines || []) {
    if ((safeState.outerOpacity == null ? 1 : safeState.outerOpacity) <= 0 || (safeState.outerStrokeWidth || 0) <= 0) continue;
    drawWorldLine(ctx, line, entity.lineColor || "#7B858C", safeState.outerStrokeWidth || 1.6, false, safeState.outerOpacity == null ? 1 : safeState.outerOpacity);
  }
}

function drawEntityDynamic(ctx, entity, state) {
  const safeState = state || {};
  if (safeState.selected || safeState.hovered || safeState.preview) {
    drawRectWorld(ctx, entity.boundsRect, {
      stroke: entity.highlightColor || entity.lineColor || "#2f7fd3",
      lineWidth: safeState.selected ? 2.4 : 1.6,
      strokeAlpha: safeState.selected ? 0.94 : 0.78,
    });
  }
  if ((safeState.outerOpacity == null ? 1 : safeState.outerOpacity) > 0 && (safeState.outerStrokeWidth || 0) > 0) {
    for (const line of entity.outerLines || []) {
      drawWorldLine(ctx, line, entity.highlightColor || entity.lineColor || "#7B858C", safeState.outerStrokeWidth || 1.6, false, safeState.outerOpacity == null ? 1 : safeState.outerOpacity);
    }
  }
  if ((safeState.innerOpacity == null ? 1 : safeState.innerOpacity) > 0 && (safeState.innerStrokeWidth || 0) > 0 && (safeState.selected || safeState.hovered || safeState.preview)) {
    for (const line of entity.innerLines || []) {
      drawWorldLine(ctx, line, entity.highlightColor || entity.lineColor || "#7B858C", safeState.innerStrokeWidth || 1.4, !!line.dashed, safeState.innerOpacity == null ? 1 : safeState.innerOpacity);
    }
  }
}

function drawScene() {
  drawRafId = 0;
  const canvas = canvasEl.value;
  if (!canvas) return;
  const ctx = canvas.getContext("2d");
  if (!ctx) return;
  const width = Math.max(1, Number(viewport.value.width) || 1);
  const height = Math.max(1, Number(viewport.value.height) || 1);
  const dpr = Math.max(1, window.devicePixelRatio || 1);
  canvas.width = Math.round(width * dpr);
  canvas.height = Math.round(height * dpr);
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, width, height);
  if (!props.scene) return;
  const renderTokens = props.scene?.renderTokens || {};
  const nextBackgroundToken = [
    String(renderTokens.viewport || ""),
    String(renderTokens.structure || ""),
    String(renderTokens.entities || ""),
  ].join("|");
  if (backgroundToken !== nextBackgroundToken) {
    const bgCtx = ensureBackgroundContext(width, height, dpr);
    if (bgCtx) {
      drawGrid(bgCtx);
      for (const line of props.scene?.structure?.outerLines || []) {
        drawWorldLine(bgCtx, line, line.color || "#4f4144", Number(line.strokeWidth) || 2.2, false, line.opacity == null ? 1 : line.opacity);
      }
      for (const line of props.scene?.structure?.innerLines || []) {
        drawWorldLine(bgCtx, line, line.color || "#b9c3cd", Number(line.strokeWidth) || 1.2, !!line.dashed, line.opacity == null ? 0.82 : line.opacity);
      }
      const entityStates = props.scene?.entityStates || {};
      for (const entity of props.scene.entities || []) {
        drawEntityBase(bgCtx, entity, entityStates[String(entity?.id || "")]);
      }
    }
    backgroundToken = nextBackgroundToken;
  }
  if (backgroundCanvas) {
    ctx.drawImage(backgroundCanvas, 0, 0, width, height);
  }

  for (const point of props.scene?.snap?.points || []) {
    if (!props.scene?.snap?.visible) break;
    const screen = worldToScreen(point);
    ctx.save();
    ctx.fillStyle = "rgba(47,127,211,0.18)";
    ctx.beginPath();
    ctx.arc(screen.x, screen.y, 3.6, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }
  if (props.scene?.snap?.visible && props.scene?.snap?.activePoint) {
    const point = worldToScreen(props.scene.snap.activePoint);
    ctx.save();
    ctx.fillStyle = "rgba(47,127,211,0.96)";
    ctx.beginPath();
    ctx.arc(point.x, point.y, props.scene.snap.activePoint.kind === "edge" ? 4.4 : 5.2, 0, Math.PI * 2);
    ctx.fill();
    ctx.restore();
  }

  const entityStates = props.scene?.entityStates || {};
  for (const entity of props.scene.entities || []) {
    drawEntityDynamic(ctx, entity, entityStates[String(entity?.id || "")]);
  }

  for (const overlay of props.scene.controllers || []) {
    drawControllerOverlayRect(ctx, overlay);
    for (const controller of overlay.visuals || []) {
      const isActive = !!controller.hovered || !!controller.dragging;
      drawControllerHandle(ctx, controller, overlay.lineColor || "#2f7fd3", isActive);
      drawTextBoxWorld(ctx, {
        x: controller.fieldX,
        y: controller.fieldY,
        w: controller.inputW,
        h: controller.inputH,
      }, controller.label, {
        fill: controller.editing ? "rgba(47,127,211,0.14)" : "rgba(255,255,255,0.96)",
        stroke: controller.hovered ? "#2f7fd3" : "rgba(94,50,69,0.24)",
      });
    }
    for (const metric of overlay.metrics || []) {
      drawTextBoxWorld(ctx, {
        x: metric.fieldX,
        y: metric.fieldY,
        w: metric.inputW,
        h: metric.inputH,
      }, metric.label, {
        fill: "rgba(255,255,255,0.96)",
        stroke: "rgba(94,50,69,0.24)",
      });
    }
  }

  if (props.scene?.annotations?.visible) {
    for (const dimension of props.scene?.annotations?.dimensions || []) {
      const color = dimension.selected ? (props.scene?.annotations?.selectedColor || "#2F7FD3") : (props.scene?.annotations?.color || "#E8A559");
      drawWorldLine(ctx, dimension.extensionA, color, dimension.selected ? 2.2 : 1.4, false, 0.9);
      drawWorldLine(ctx, dimension.extensionB, color, dimension.selected ? 2.2 : 1.4, false, 0.9);
      drawWorldLine(ctx, dimension.tickA, color, dimension.selected ? 2.2 : 1.4, false, 1);
      drawWorldLine(ctx, dimension.tickB, color, dimension.selected ? 2.2 : 1.4, false, 1);
      drawWorldLine(ctx, { x1: dimension.screenStart.x, y1: dimension.screenStart.y, x2: dimension.screenEnd.x, y2: dimension.screenEnd.y }, color, dimension.selected ? 2.6 : 1.8, false, 1);
      const textPoint = worldToScreen({ x: dimension.textX, y: dimension.textY });
      ctx.save();
      ctx.fillStyle = color;
      ctx.font = "12px Tahoma";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(dimension.text || ""), textPoint.x, textPoint.y);
      ctx.restore();
    }
    const draft = props.scene?.annotations?.draftDimension;
    if (draft) {
      const color = props.scene?.annotations?.color || "#E8A559";
      drawWorldLine(ctx, draft.extensionA, color, 1.4, false, 0.82);
      drawWorldLine(ctx, draft.extensionB, color, 1.4, false, 0.82);
      drawWorldLine(ctx, draft.tickA, color, 1.6, false, 1);
      drawWorldLine(ctx, draft.tickB, color, 1.6, false, 1);
      drawWorldLine(ctx, { x1: draft.screenStart.x, y1: draft.screenStart.y, x2: draft.screenEnd.x, y2: draft.screenEnd.y }, color, 1.8, true, 1);
      const textPoint = worldToScreen({ x: draft.textX, y: draft.textY });
      ctx.save();
      ctx.fillStyle = color;
      ctx.font = "12px Tahoma";
      ctx.textAlign = "center";
      ctx.textBaseline = "middle";
      ctx.fillText(String(draft.text || ""), textPoint.x, textPoint.y);
      ctx.restore();
    }
  }
}

function scheduleDraw() {
  if (drawRafId) return;
  drawRafId = requestAnimationFrame(drawScene);
}

function setPointerCapture(pointerId) {
  canvasEl.value?.setPointerCapture?.(pointerId);
}

function releasePointerCapture(pointerId) {
  canvasEl.value?.releasePointerCapture?.(pointerId);
}

function getWorldPointFromEvent(event) {
  return screenToWorld(event);
}

defineExpose({
  setPointerCapture,
  releasePointerCapture,
  getWorldPointFromEvent,
});

onMounted(() => {
  syncViewport();
  if (typeof ResizeObserver !== "undefined") {
    resizeObserver = new ResizeObserver(() => {
      syncViewport();
      scheduleDraw();
    });
    if (wrapEl.value) resizeObserver.observe(wrapEl.value);
  }
  nextTick(() => scheduleDraw());
});

onBeforeUnmount(() => {
  if (resizeObserver) resizeObserver.disconnect();
  if (drawRafId) cancelAnimationFrame(drawRafId);
  backgroundCanvas = null;
  backgroundCanvasCtx = null;
  backgroundToken = "";
});

watch(() => props.scene?.renderTokens?.viewport, () => {
  backgroundToken = "";
  scheduleDraw();
}, { immediate: true });
watch(() => props.scene?.renderTokens?.structure, () => {
  backgroundToken = "";
  scheduleDraw();
});
watch(() => props.scene?.renderTokens?.entities, () => {
  backgroundToken = "";
  scheduleDraw();
});
watch(() => props.scene?.renderTokens?.dynamic, () => {
  scheduleDraw();
});
watch(() => props.scene?.renderTokens?.controllers, () => {
  scheduleDraw();
});
watch(() => props.scene?.renderTokens?.annotations, () => {
  scheduleDraw();
});
watch(() => props.scene?.renderTokens?.snap, () => {
  scheduleDraw();
});

watch(viewport, () => {
  backgroundToken = "";
  scheduleDraw();
}, { deep: true });
</script>

<template>
  <div ref="wrapEl" class="frontViewCanvas" :class="cursorClass">
    <canvas
      ref="canvasEl"
      class="frontViewCanvas__canvas"
      @pointerdown="emitPointer('pointerdown', $event)"
      @pointermove="emitPointer('pointermove', $event)"
      @pointerup="emitPointer('pointerup', $event)"
      @pointercancel="emitPointer('pointercancel', $event)"
      @pointerleave="emitPointer('pointerleave', $event)"
      @wheel.prevent.stop="emitPointer('canvas-wheel', $event)"
      @dblclick="emitPointer('dblclick', $event)"
      @contextmenu.prevent.stop="emitPointer('contextmenu', $event)"
    ></canvas>
  </div>
</template>

<style scoped>
.frontViewCanvas {
  position: absolute;
  inset: 0;
  box-sizing: border-box;
  border-radius: 20px;
  overflow: hidden;
  background: #fff;
  box-shadow: 0 1px 1px rgba(70, 24, 42, 0.04);
}

.frontViewCanvas::after {
  content: "";
  position: absolute;
  inset: 0;
  z-index: 2;
  box-sizing: border-box;
  border: 1px solid rgba(211, 151, 172, 0.26);
  border-radius: inherit;
  pointer-events: none;
}

.frontViewCanvas__canvas {
  width: 100%;
  height: 100%;
  box-sizing: border-box;
  display: block;
  background: #fff;
  border-top-left-radius: 10px;
  border-top-right-radius: 10px;
  border-bottom-right-radius: 10px;
  border-bottom-left-radius: 10px;
}
</style>
