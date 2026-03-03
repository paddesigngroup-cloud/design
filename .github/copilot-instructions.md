# Copilot Instructions for DesignKP 2D

This is a lightweight browser demo of a 2D viewport with grid, camera, and
simple wall-drawing tools. The code runs entirely in the browser using ES6
modules; there is no build system or dependencies beyond a local web server.

## Project Overview
- **Entry point:** `2d/index.html` loads `main.js` as a module. All logic is in
  `2d/main.js` and the `src/engine` subdirectory.
- **Engine modules:**
  - `wall_graph_v2.js` implements a node/edge graph of walls. Walls connect
    `Node` objects and track thickness/name; helper methods create or snap
    nodes, manage duplicates, and query connectivity.
  - `wall_rules_v2.js` contains pure‑math utilities and the gamma/miter
    computation used by wall joints. It exports `computeGammaForJoint`, the
    only consumer is `main.js`'s debug view and later tooling.
  - `tools/SolidWallTool.js` defines the interactive wall‑drawing tool used by
    the app. It handles pointer events, 45° snapping (toggle with right‑click),
    ESC to cancel chaining, and sequential naming (`Wall A`, `Wall B`, …).

- **Rendering & state:** `main.js` handles canvas setup, device pixel ratio,
  grid drawing, camera transforms (`worldToScreen` / `screenToWorld`), input
  handling and UI controls. The global `state` object contains colors, units
  (world units are always **mm**), camera zoom/offset, and settings saved in
  `localStorage` under the key `wall_v1_settings_rtl_v2`.
- **Camera:** origin starts centered; zoom controlled by mouse wheel; pan with
  middle mouse drag. Coordinates flipped in Y because world Y+ is up. UI labels
  display mm or cm based on `state.unit`.


## Getting started / Developer workflow
1. **Serve the files.** Because `main.js` is a module, open the demo with a
   local web server; opening `file://` will fail due to CORS/modules.
   - `cd C:\DesignKP\2d && python -m http.server 5173` then browse
     `http://localhost:5173`
   - or use VS Code _Live Server_ extension on `index.html`.
2. **Edit and refresh.** No build step; edits to JS/HTML are immediately
   visible on reload.
3. **Debugging:** open DevTools, set breakpoints in `main.js` or engine
   modules. The names are not minified.
4. **Persistence:** settings (colors, grid density, etc.) persist via
   `localStorage`; the graph itself is not saved yet.

There are no automated tests or CI configured. If you add files, keep using
ES module syntax (`import`/`export`).


## Conventions & Patterns
- **World units = millimeters.** All geometry in engine modules uses mm. UI
  displays either mm or cm; conversion helpers are in `main.js`.
- **Snap tolerance default 30 mm.** Both the graph (`getOrCreateNode`) and the
  `SolidWallTool` use this value to merge close points.
- **Tool chaining:** `SolidWallTool` keeps a `pendingStartNodeId`; after the
  first click a subsequent click creates a wall and continues from the end
  node. Press ESC to break the chain. Names increment even across chains.
- **45° snap:** computed by rounding the angle to the nearest multiple of
  π/4; toggled with a right‑click on the canvas.
- **State object:** a flat object with default values in `main.js`. When adding
  new settings, update `loadSettings`/`saveSettings` accordingly.
- **No framework.** Plain DOM, canvas APIs, and small helper functions.
- **Separate concerns.** Engine modules avoid any rendering/UI code and can be
  reused independently in tests or another frontend.


## Key Files / Areas to Know
- `2d/index.html` – minimal HTML, inlined styles, loads `main.js`.
- `2d/main.js` – the heart of the app; camera, drawing loop, event handlers,
  and UI control wiring.
- `2d/src/engine/wall_graph_v2.js` – graph data model; use this when adding
  persistence or undo/redo features.
- `2d/src/engine/wall_rules_v2.js` – geometry rule engine; look here to
  implement joint trimming or new wall rules.
- `2d/src/engine/tools/SolidWallTool.js` – interactive drawing logic; add
  similar tools here (e.g. arc tool) following the same `onPointerX` +
  `getStatus` pattern.


## When Editing
- Keep transformations consistent (`worldToScreen`/`screenToWorld`) to avoid
  mismatched coordinates. The `view` object passed to tools exposes those
  methods.
- The canvas is resized on window `resize` and the DPR is applied to the
  context transform; don't forget to call `resize()` if you add new canvases.
- Avoid hard‑coding pixel values for UI elements – most visual constants are
  in `state` and saved/loaded.
- The engine and tools are written in ES modules; adding new files should use
  the same `export class ...` pattern and named imports in `main.js`.


## Questions & Feedback
If any part of these instructions is unclear or missing important context,
let me know and I can expand or correct sections. Feel free to point out any
project‑specific quirks you'd like documented.