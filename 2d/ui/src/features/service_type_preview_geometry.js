export function normalizeServiceTypePreviewSceneInput(source) {
  const part = source?.part || {};
  const cutter = source?.cutter || {};
  const normalizedPart = {
    width: Math.max(1, Number(part.width) || 0),
    length: Math.max(1, Number(part.length) || 0),
    thickness: Math.max(1, Number(part.thickness) || 0),
  };
  const normalizedProfilePoints = Array.isArray(cutter.profilePoints)
    ? cutter.profilePoints
      .map((point) => ({
        x: Number(point?.x) || 0,
        y: Number(point?.y) || 0,
      }))
      .filter((point, index, list) =>
        Number.isFinite(point.x)
        && Number.isFinite(point.y)
        && (index === 0 || point.x !== list[index - 1].x || point.y !== list[index - 1].y)
      )
    : [];
  const workingDiameter = Math.max(0, Number(cutter.workingDiameter) || 0);
  const workingWidth = Math.max(0, Number(cutter.workingWidth) || 0);
  const workingHeight = Math.max(0, Number(cutter.workingHeight) || 0);
  const workingDepth = Math.max(0, Number(cutter.workingDepth) || 0);
  const workingDepthMode = normalizeWorkingDepthMode(cutter.workingDepthMode);
  const workingDepthEndOffset = Math.max(0, Number(cutter.workingDepthEndOffset) || 0);
  const effectiveWorkingDepth = resolveEffectiveWorkingDepth(
    normalizedPart,
    normalizeServiceLocation(cutter.serviceLocation),
    workingDepth,
    workingDepthMode,
    workingDepthEndOffset,
  );
  const profileBounds = getProfileBounds(cutter.shape, normalizedProfilePoints, workingDiameter, workingWidth, workingHeight);
  return {
    part: normalizedPart,
    cutter: {
      hasVisibleSubtraction: !!cutter.hasVisibleSubtraction && (workingDiameter > 0 || workingWidth > 0 || workingHeight > 0),
      serviceLocation: normalizeServiceLocation(cutter.serviceLocation),
      shape: normalizeSubtractionShape(cutter.shape),
      workingDiameter,
      workingWidth,
      workingHeight,
      workingDepth,
      workingDepthMode,
      workingDepthEndOffset,
      effectiveWorkingDepth,
      axisAligned: Math.max(0, Number(cutter.axisAligned) || 0),
      axisOpposite: Math.max(0, Number(cutter.axisOpposite) || 0),
      profilePoints: normalizedProfilePoints,
      profileBounds,
      projectedWidth: profileBounds.width,
      projectedHeight: profileBounds.height,
    },
  };
}

export function buildServiceTypeProjectionViews(sceneInput, frames) {
  const scene = normalizeServiceTypePreviewSceneInput(sceneInput);
  const topRect = frames?.topRect || null;
  const bottomRect = frames?.bottomRect || null;
  const sideRect = frames?.sideRect || null;
  return {
    top: buildTopBottomProjection(scene, topRect),
    bottom: buildTopBottomProjection(scene, bottomRect),
    side: buildSideProjection(scene, sideRect),
    scene,
  };
}

function normalizeServiceLocation(value) {
  const text = String(value || "").trim().toLowerCase();
  if (text === "back" || text === "thickness") return text;
  return "front";
}

function normalizeSubtractionShape(value) {
  const text = String(value || "").trim().toLowerCase();
  if (text === "triangle" || text === "rectangle") return text;
  return "circle";
}

function normalizeWorkingDepthMode(value) {
  return String(value || "").trim().toLowerCase() === "to_end" ? "to_end" : "fixed";
}

function resolveEffectiveWorkingDepth(part, serviceLocation, workingDepth, workingDepthMode, endOffset) {
  if (workingDepthMode !== "to_end") return workingDepth;
  const pathExtent = serviceLocation === "thickness"
    ? Math.max(0, Number(part?.length) || 0)
    : Math.max(0, Number(part?.thickness) || 0);
  return Math.max(0, pathExtent - Math.max(0, Number(endOffset) || 0));
}

function getProfileBounds(shape, profilePoints, workingDiameter, workingWidth, workingHeight) {
  if (shape === "circle") {
    const diameter = Math.max(0, Number(workingDiameter) || 0);
    return {
      minX: -diameter / 2,
      maxX: diameter / 2,
      minY: -diameter / 2,
      maxY: diameter / 2,
      width: diameter,
      height: diameter,
    };
  }
  const points = Array.isArray(profilePoints) ? profilePoints : [];
  if (!points.length) {
    const fallbackWidth = Math.max(0, Number(workingWidth) || Number(workingDiameter) || 0);
    const fallbackHeight = Math.max(0, Number(workingHeight) || Number(workingDiameter) || 0);
    return {
      minX: -fallbackWidth / 2,
      maxX: fallbackWidth / 2,
      minY: -fallbackHeight / 2,
      maxY: fallbackHeight / 2,
      width: fallbackWidth,
      height: fallbackHeight,
    };
  }
  const xs = points.map((point) => point.x);
  const ys = points.map((point) => point.y);
  const minX = Math.min(...xs);
  const maxX = Math.max(...xs);
  const minY = Math.min(...ys);
  const maxY = Math.max(...ys);
  return {
    minX,
    maxX,
    minY,
    maxY,
    width: Math.max(0, maxX - minX),
    height: Math.max(0, maxY - minY),
  };
}

function buildTopBottomProjection(scene, rect) {
  if (!rect) return { primaryShape: null, traceShape: null };
  const { part, cutter } = scene;
  if (!cutter.hasVisibleSubtraction || cutter.effectiveWorkingDepth <= 0) {
    return { primaryShape: null, traceShape: null };
  }
  if (cutter.serviceLocation === "thickness") {
    const xCenter = (-part.width / 2) + cutter.axisAligned;
    const xMin = xCenter + cutter.profileBounds.minX;
    const xMax = xCenter + cutter.profileBounds.maxX;
    const zStart = -part.length / 2;
    const zEnd = Math.min(part.length / 2, zStart + cutter.effectiveWorkingDepth);
    return {
      primaryShape: buildProjectedRect(
        rect,
        part.width,
        part.length,
        xMin,
        xMax,
        zStart,
        zEnd
      ),
      traceShape: null,
    };
  }
  const center = {
    x: (-part.width / 2) + cutter.axisAligned,
    z: (-part.length / 2) + cutter.axisOpposite,
  };
  return {
      primaryShape: cutter.shape === "circle"
        ? buildProjectedCircle(rect, part.width, part.length, center.x, center.z, cutter.workingDiameter / 2)
        : buildProjectedPolygon(
        rect,
        part.width,
        part.length,
        cutter.profilePoints.map((point) => ({
          x: center.x + point.x,
          z: center.z + point.y,
        }))
      ),
    traceShape: null,
  };
}

function buildSideProjection(scene, rect) {
  if (!rect) return { primaryShape: null, traceShape: null };
  const { part, cutter } = scene;
  if (!cutter.hasVisibleSubtraction || cutter.effectiveWorkingDepth <= 0) {
    return { primaryShape: null, traceShape: null };
  }
  if (cutter.serviceLocation === "thickness") {
    const center = {
      x: (-part.width / 2) + cutter.axisAligned,
      y: (-part.thickness / 2) + cutter.axisOpposite,
    };
    return {
      primaryShape: cutter.shape === "circle"
        ? buildProjectedCircle(rect, part.width, part.thickness, center.x, center.y, cutter.workingDiameter / 2)
        : buildProjectedPolygon(
        rect,
        part.width,
        part.thickness,
        cutter.profilePoints.map((point) => ({
          x: center.x + point.x,
          y: center.y + point.y,
        }))
      ),
      traceShape: null,
    };
  }
  const xCenter = (-part.width / 2) + cutter.axisAligned;
  const xMin = xCenter + cutter.profileBounds.minX;
  const xMax = xCenter + cutter.profileBounds.maxX;
  const visibleDepth = Math.min(part.thickness, cutter.effectiveWorkingDepth);
  const yMin = cutter.serviceLocation === "back"
    ? -part.thickness / 2
    : (part.thickness / 2) - visibleDepth;
  const yMax = cutter.serviceLocation === "back"
    ? (-part.thickness / 2) + visibleDepth
    : part.thickness / 2;
  return {
    primaryShape: buildProjectedRect(
      rect,
      part.width,
      part.thickness,
      xMin,
      xMax,
      yMin,
      yMax
    ),
    traceShape: null,
  };
}

function mapXToRect(rect, totalWidth, xValue) {
  if (!rect || totalWidth <= 0) return 0;
  return rect.x + (((xValue + (totalWidth / 2)) / totalWidth) * rect.width);
}

function mapYToRect(rect, totalHeight, yValue) {
  if (!rect || totalHeight <= 0) return 0;
  return rect.y + rect.height - (((yValue + (totalHeight / 2)) / totalHeight) * rect.height);
}

function buildProjectedCircle(rect, totalWidth, totalHeight, centerX, centerY, radius) {
  if (!rect || radius <= 0) return null;
  const scaleX = rect.width / Math.max(1, totalWidth);
  const scaleY = rect.height / Math.max(1, totalHeight);
  return {
    type: "circle",
    cx: mapXToRect(rect, totalWidth, centerX),
    cy: mapYToRect(rect, totalHeight, centerY),
    r: Math.max(2, radius * Math.min(scaleX, scaleY)),
  };
}

function buildProjectedRect(rect, totalWidth, totalHeight, minX, maxX, minY, maxY) {
  if (!rect) return null;
  const x1 = mapXToRect(rect, totalWidth, minX);
  const x2 = mapXToRect(rect, totalWidth, maxX);
  const y1 = mapYToRect(rect, totalHeight, minY);
  const y2 = mapYToRect(rect, totalHeight, maxY);
  return {
    type: "rect",
    x: Math.min(x1, x2),
    y: Math.min(y1, y2),
    width: Math.max(2, Math.abs(x2 - x1)),
    height: Math.max(2, Math.abs(y2 - y1)),
    rx: 2,
  };
}

function buildProjectedPolygon(rect, totalWidth, totalHeight, points) {
  const source = Array.isArray(points) ? points : [];
  if (!rect || source.length < 3) return null;
  return {
    type: "polygon",
    points: source
      .map((point) => {
        const x = mapXToRect(rect, totalWidth, Number(point?.x) || 0);
        const y = mapYToRect(rect, totalHeight, Number(point?.z ?? point?.y) || 0);
        return `${x.toFixed(2)},${y.toFixed(2)}`;
      })
      .join(" "),
  };
}
