const ICON_SIZE = 44;
const ICON_PAD = 4;

const RAW_WALL_PRESETS = [
  {
    id: "tmp_01",
    title: "نمونه ۱",
    data: {
      nodes: [
        { id: "n2", x: -1508.3739380132456, y: 2280.559204591612 },
        { id: "n3", x: -1508.3739380132454, y: -1819.440795408388 },
        { id: "n4", x: 2591.6260619867544, y: 2280.559204591612 },
      ],
      walls: [
        { a: "n2", b: "n3", thickness: 200 },
        { a: "n2", b: "n4", thickness: 200 },
      ],
    },
  },
  {
    id: "tmp_02",
    title: "نمونه ۲",
    data: {
      nodes: [
        { id: "n7", x: -1494.3546141317452, y: -1035.583321674961 },
        { id: "n8", x: 2605.645385868255, y: -1035.583321674961 },
        { id: "n9", x: -1494, y: 3164 },
        { id: "n10", x: 2606, y: 3164 },
      ],
      walls: [
        { a: "n7", b: "n8", thickness: 200 },
        { a: "n7", b: "n9", thickness: 200 },
        { a: "n9", b: "n10", thickness: 200 },
      ],
    },
  },
  {
    id: "tmp_03",
    title: "نمونه ۳",
    data: {
      nodes: [
        { id: "n7", x: -1494.3546141317452, y: -1035.583321674961 },
        { id: "n8", x: 2605.645385868255, y: -1035.583321674961 },
        { id: "n9", x: -1494.0084081350772, y: 3064.4251080960134 },
      ],
      walls: [
        { a: "n7", b: "n8", thickness: 200 },
        { a: "n7", b: "n9", thickness: 200 },
      ],
    },
  },
    {
    id: "tmp_04",
    title: "نمونه ۴",
    data: {
      nodes: [
        { id: "n5", x: 4994.646326513425, y: -1896.9727549609881 },
        { id: "n6", x: 4994.646326513425, y: 2203.027245039012 },
        { id: "n7", x: 894.6463265134253, y: -1896.9727549609886 },
      ],
      walls: [
        { a: "n5", b: "n6", thickness: 200, name: "Wall A" },
        { a: "n5", b: "n7", thickness: 200, name: "Wall B" },
      ],
    },
  },
    {
    id: "tmp_05",
    title: "نمونه ۵",
    data: {
      nodes: [
        { id: "n12", x: 7373.21083996267, y: -1758.1592926800354 },
        { id: "n13", x: 3273.2108399626704, y: -1758.1592926800358 },
        { id: "n14", x: 7373, y: 2442 },
        { id: "n15", x: 3273, y: 2442 },
      ],
      walls: [
        { a: "n12", b: "n13", thickness: 200, name: "Wall A" },
        { a: "n12", b: "n14", thickness: 200, name: "Wall B" },
        { a: "n14", b: "n15", thickness: 200, name: "Wall C" },
      ],
    },
  },

    {
    id: "tmp_06",
    title: "نمونه ۶",
    data: {
      nodes: [
        { id: "n19", x: 11601.162084545267, y: 3215.070986006269 },
        { id: "n20", x: 7501.162084545267, y: 3215.0709860062693 },
        { id: "n21", x: 11601.162084545267, y: -884.9290139937311 },
      ],
      walls: [
        { a: "n19", b: "n20", thickness: 200, name: "Wall A" },
        { a: "n19", b: "n21", thickness: 200, name: "Wall B" },
      ],
    },
  },
  {
    id: "tmp_07",
    title: "نمونه ۷",
    data: {
      nodes: [
        { id: "n8", x: -1045.4556571797316, y: 2535.369668619035 },
        { id: "n9", x: -1045.4556571797314, y: -1564.630331380965 },
        { id: "n10", x: 3155, y: 2535 },
        { id: "n12", x: 3155, y: -1565 },
      ],
      walls: [
        { a: "n8", b: "n9", thickness: 200, name: "Wall A" },
        { a: "n8", b: "n10", thickness: 200, name: "Wall B" },
        { a: "n10", b: "n12", thickness: 200, name: "Wall C" },
      ],
    },
  },
  {
    id: "tmp_08",
    title: "نمونه ۸",
    data: {
      nodes: [
        { id: "n13", x: -1360.6343331912915, y: -142.82339479365126 },
        { id: "n14", x: -1360.6343331912913, y: 3957.1766052063485 },
        { id: "n15", x: 2839, y: -143 },
        { id: "n16", x: 2839, y: 3957 },
      ],
      walls: [
        { a: "n13", b: "n14", thickness: 200, name: "Wall A" },
        { a: "n13", b: "n15", thickness: 200, name: "Wall B" },
        { a: "n15", b: "n16", thickness: 200, name: "Wall C" },
      ],
    },
  },
    {
    id: "tmp_09",
    title: "نمونه ۹",
    data: {
      nodes: [
        { id: "n1", x: -3632.9313701314463, y: -1590.7764445150397 },
        { id: "n2", x: 508.03894086968137, y: -1590.9096894501954 },
        { id: "n3", x: -3633, y: 3609 },
        { id: "n4", x: 1981.7172420961265, y: -117.23138822375051 },
        { id: "n12", x: 1965, y: 3607.9999999999995 },
      ],
      walls: [
        { a: "n1", b: "n2", thickness: 200, name: "Wall A" },
        { a: "n1", b: "n3", thickness: 200, name: "Wall B" },
        { a: "n2", b: "n4", thickness: 200, name: "Wall C" },
        { a: "n4", b: "n12", thickness: 200, name: "Wall D" },
        { a: "n3", b: "n12", thickness: 200, name: "Wall E" },
      ],
    },
  },

        {
    id: "tmp_10",
    title: "نمونه ۱۰",
    data: {
      nodes: [
        { id: "n1", x: 1981.6486122275728, y: -1590.7764445150397 },
        { id: "n2", x: -2159.321698773555, y: -1590.9096894501954 },
        { id: "n3", x: 1981.7172420961265, y: 3609 },
        { id: "n4", x: -3633.0, y: -117.23138822375051 },
        { id: "n12", x: -3616.2827579038735, y: 3607.9999999999995 },
      ],
      walls: [
        { a: "n1", b: "n2", thickness: 200, name: "Wall A" },
        { a: "n1", b: "n3", thickness: 200, name: "Wall B" },
        { a: "n2", b: "n4", thickness: 200, name: "Wall C" },
        { a: "n4", b: "n12", thickness: 200, name: "Wall D" },
        { a: "n3", b: "n12", thickness: 200, name: "Wall E" },
      ],
    },
  },

  {
    id: "tmp_11",
    title: "نمونه ۱۱",
    data: {
      nodes: [
        { id: "n1", x: -3632.931370131446, y: 3608.866755064844 },
        { id: "n2", x: 508.038940869681, y: 3609 },
        { id: "n3", x: -3633, y: -1590.909689450195 },
        { id: "n4", x: 1981.717242096126, y: 2135.321698773555 },
        { id: "n12", x: 1965, y: -1589.909689450195 },
      ],
      walls: [
        { a: "n1", b: "n2", thickness: 200, name: "Wall A" },
        { a: "n1", b: "n3", thickness: 200, name: "Wall B" },
        { a: "n2", b: "n4", thickness: 200, name: "Wall C" },
        { a: "n4", b: "n12", thickness: 200, name: "Wall D" },
        { a: "n3", b: "n12", thickness: 200, name: "Wall E" },
      ],
    },
  },

  {
    id: "tmp_12",
    title: "نمونه ۱۲",
    data: {
      nodes: [
        { id: "n1", x: 1981.648612227573, y: 3608.866755064844 },
        { id: "n2", x: -2159.321698773555, y: 3609 },
        { id: "n3", x: 1981.717242096126, y: -1590.909689450195 },
        { id: "n4", x: -3633, y: 2135.321698773555 },
        { id: "n12", x: -3616.282757903874, y: -1589.909689450195 },
      ],
      walls: [
        { a: "n1", b: "n2", thickness: 200, name: "Wall A" },
        { a: "n1", b: "n3", thickness: 200, name: "Wall B" },
        { a: "n2", b: "n4", thickness: 200, name: "Wall C" },
        { a: "n4", b: "n12", thickness: 200, name: "Wall D" },
        { a: "n3", b: "n12", thickness: 200, name: "Wall E" },
      ],
    },
  },

];

function toLinesFromGraph(graph) {
  const byId = new Map((Array.isArray(graph?.nodes) ? graph.nodes : []).map((n) => [n.id, n]));
  const walls = Array.isArray(graph?.walls) ? graph.walls : [];
  return walls
    .map((w, idx) => {
      const a = byId.get(w.a);
      const b = byId.get(w.b);
      if (!a || !b) return null;
      const fallbackName = `Wall ${String.fromCharCode(65 + (idx % 26))}`;
      return {
        ax: Number(a.x),
        ay: Number(a.y),
        bx: Number(b.x),
        by: Number(b.y),
        thickness: Number(w.thickness) || 200,
        name: (typeof w.name === "string" && w.name) ? w.name : fallbackName,
      };
    })
    .filter(Boolean);
}

function centeredLines(lines) {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const l of lines) {
    minX = Math.min(minX, l.ax, l.bx);
    maxX = Math.max(maxX, l.ax, l.bx);
    minY = Math.min(minY, l.ay, l.by);
    maxY = Math.max(maxY, l.ay, l.by);
  }
  if (!isFinite(minX) || !isFinite(minY) || !isFinite(maxX) || !isFinite(maxY)) return [];
  const cx = (minX + maxX) * 0.5;
  const cy = (minY + maxY) * 0.5;
  return lines.map((l) => ({ ...l, ax: l.ax - cx, ay: l.ay - cy, bx: l.bx - cx, by: l.by - cy }));
}

function getBounds(lines) {
  let minX = Infinity;
  let maxX = -Infinity;
  let minY = Infinity;
  let maxY = -Infinity;
  for (const l of lines) {
    minX = Math.min(minX, l.ax, l.bx);
    maxX = Math.max(maxX, l.ax, l.bx);
    minY = Math.min(minY, l.ay, l.by);
    maxY = Math.max(maxY, l.ay, l.by);
  }
  return { minX, maxX, minY, maxY };
}

const PRESET_STORE = RAW_WALL_PRESETS.map((p) => {
  const lines = centeredLines(toLinesFromGraph(p.data));
  return { id: p.id, title: p.title, lines };
});

const _wallReadyPresets = PRESET_STORE.map((p) => ({ id: p.id, title: p.title, kind: p.id }));

function sampleNo(title) {
  const m = String(title || "").match(/(\d+)/);
  return m ? Number(m[1]) : NaN;
}

const byNo = new Map(_wallReadyPresets.map((p) => [sampleNo(p.title), p]));

// Requested grid order from design review (left->right, top->bottom):
// 1,7,6 / 3,5,4 / 9,2,10 / 11,8,12
const orderNo = [1, 7, 6, 3, 5, 4, 9, 2, 10, 11, 8, 12];
const ordered = orderNo.map((n) => byNo.get(n)).filter(Boolean);

export const WALL_READY_PRESETS =
  ordered.length === _wallReadyPresets.length ? ordered : _wallReadyPresets;

export function buildPresetLines(kind) {
  const p = PRESET_STORE.find((x) => x.id === kind) || PRESET_STORE[0];
  return (p?.lines || []).map((l) => ({
    ax: l.ax,
    ay: l.ay,
    bx: l.bx,
    by: l.by,
    thickness: l.thickness,
    name: l.name,
  }));
}

export function getPresetIconWalls(kind) {
  const p = PRESET_STORE.find((x) => x.id === kind) || PRESET_STORE[0];
  const lines = p?.lines || [];
  if (lines.length === 0) return [];

  const { minX, maxX, minY, maxY } = getBounds(lines);
  const spanX = Math.max(1, maxX - minX);
  const spanY = Math.max(1, maxY - minY);
  const scale = Math.min((ICON_SIZE - ICON_PAD * 2) / spanX, (ICON_SIZE - ICON_PAD * 2) / spanY);

  return lines.map((l) => ({
    x1: ICON_SIZE * 0.5 + l.ax * scale,
    y1: ICON_SIZE * 0.5 - l.ay * scale,
    x2: ICON_SIZE * 0.5 + l.bx * scale,
    y2: ICON_SIZE * 0.5 - l.by * scale,
    sw: Math.max(2, l.thickness * scale),
  }));
}
