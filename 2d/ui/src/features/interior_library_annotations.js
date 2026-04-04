let annotationSeed = 1;

function nextAnnotationId(prefix) {
  const safePrefix = String(prefix || "annotation").trim() || "annotation";
  annotationSeed += 1;
  return `${safePrefix}-${annotationSeed}`;
}

export function createEmptyInteriorLibraryAnnotations() {
  return {
    dimensions: [],
    guides: [],
  };
}

export function clampAxisAnnotation(startPoint, currentPoint) {
  const start = {
    x: Number(startPoint?.x) || 0,
    y: Number(startPoint?.y) || 0,
  };
  const raw = {
    x: Number(currentPoint?.x) || 0,
    y: Number(currentPoint?.y) || 0,
  };
  const dx = raw.x - start.x;
  const dy = raw.y - start.y;
  const axis = Math.abs(dx) >= Math.abs(dy) ? "horizontal" : "vertical";
  return {
    axis,
    start,
    end: axis === "horizontal"
      ? { x: raw.x, y: start.y }
      : { x: start.x, y: raw.y },
  };
}

export function isInteriorAnnotationMeaningful(annotation) {
  const start = annotation?.start;
  const end = annotation?.end;
  if (!start || !end) return false;
  const dx = Number(end.x) - Number(start.x);
  const dy = Number(end.y) - Number(start.y);
  return Math.hypot(dx, dy) >= 1;
}

export function buildInteriorAnnotationRecord(type, startPoint, currentPoint) {
  const normalizedType = type === "guide" ? "guide" : "dimension";
  const clamped = clampAxisAnnotation(startPoint, currentPoint);
  const record = {
    id: nextAnnotationId(normalizedType),
    type: normalizedType,
    axis: clamped.axis,
    start: clamped.start,
    end: clamped.end,
  };
  if (normalizedType === "dimension") {
    record.value = clamped.axis === "horizontal"
      ? Math.abs(Number(clamped.end.x) - Number(clamped.start.x))
      : Math.abs(Number(clamped.end.y) - Number(clamped.start.y));
  }
  return record;
}

export function formatInteriorDimensionValue(valueMm, unit = "cm") {
  const numeric = Math.max(0, Number(valueMm) || 0);
  const normalizedUnit = String(unit || "cm").trim().toLowerCase();
  if (normalizedUnit === "mm") {
    return `${Math.round(numeric)} mm`;
  }
  if (normalizedUnit === "inch") {
    return `${(numeric / 25.4).toFixed(2)} in`;
  }
  return `${(numeric / 10).toFixed(1)} cm`;
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
  const lengthSq = dx * dx + dy * dy;
  if (lengthSq <= 0.0001) return Math.hypot(px - ax, py - ay);
  const t = Math.max(0, Math.min(1, ((px - ax) * dx + (py - ay) * dy) / lengthSq));
  const cx = ax + dx * t;
  const cy = ay + dy * t;
  return Math.hypot(px - cx, py - cy);
}

export function hitTestInteriorAnnotationList(items, point, tolerance = 10) {
  const targetPoint = {
    x: Number(point?.x) || 0,
    y: Number(point?.y) || 0,
  };
  for (let index = (Array.isArray(items) ? items.length : 0) - 1; index >= 0; index -= 1) {
    const item = items[index];
    const hitDistance = distancePointToSegment(targetPoint, item?.screenStart, item?.screenEnd);
    if (hitDistance <= tolerance) {
      return item;
    }
  }
  return null;
}

export function removeSelectedInteriorAnnotation(annotations, selectedAnnotation) {
  const selectedType = String(selectedAnnotation?.type || "").trim();
  const selectedId = String(selectedAnnotation?.id || "").trim();
  if (!selectedType || !selectedId) return annotations;
  return {
    dimensions: (annotations?.dimensions || []).filter((item) => !(selectedType === "dimension" && String(item?.id || "") === selectedId)),
    guides: (annotations?.guides || []).filter((item) => !(selectedType === "guide" && String(item?.id || "") === selectedId)),
  };
}

export function collectInteriorSnapPoints(lines) {
  const seen = new Set();
  const points = [];
  for (const line of Array.isArray(lines) ? lines : []) {
    const endpoints = [
      { x: Number(line?.x1) || 0, y: Number(line?.y1) || 0 },
      { x: Number(line?.x2) || 0, y: Number(line?.y2) || 0 },
    ];
    for (const point of endpoints) {
      const key = `${point.x.toFixed(2)}:${point.y.toFixed(2)}`;
      if (seen.has(key)) continue;
      seen.add(key);
      points.push(point);
    }
  }
  return points;
}

export function snapInteriorPointToGeometry(point, lines, tolerance = 10) {
  const targetPoint = {
    x: Number(point?.x) || 0,
    y: Number(point?.y) || 0,
  };
  const safeTolerance = Math.max(1, Number(tolerance) || 0);
  let best = null;
  for (const line of Array.isArray(lines) ? lines : []) {
    const start = { x: Number(line?.x1) || 0, y: Number(line?.y1) || 0 };
    const end = { x: Number(line?.x2) || 0, y: Number(line?.y2) || 0 };
    const endpoints = [start, end];
    for (const endpoint of endpoints) {
      const distance = Math.hypot(targetPoint.x - endpoint.x, targetPoint.y - endpoint.y);
      if (distance > safeTolerance) continue;
      if (!best || distance < best.distance || (best.kind !== "corner" && distance <= best.distance + 0.01)) {
        best = { kind: "corner", point: endpoint, distance };
      }
    }
    const dx = end.x - start.x;
    const dy = end.y - start.y;
    const lengthSq = dx * dx + dy * dy;
    if (lengthSq <= 0.0001) continue;
    const t = Math.max(0, Math.min(1, ((targetPoint.x - start.x) * dx + (targetPoint.y - start.y) * dy) / lengthSq));
    const projected = {
      x: start.x + dx * t,
      y: start.y + dy * t,
    };
    const distance = Math.hypot(targetPoint.x - projected.x, targetPoint.y - projected.y);
    if (distance > safeTolerance) continue;
    if (!best || distance < best.distance) {
      best = { kind: "edge", point: projected, distance };
    }
  }
  return best;
}
