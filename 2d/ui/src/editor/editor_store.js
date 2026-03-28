import { shallowRef } from "vue";

// Holds the singleton instance of the embedded 2D editor engine.
export const editorRef = shallowRef(null);

// Latest 2D transform of the projected 3D model (millimeters in 2D world).
export const model2dTransformRef = shallowRef({ x: 0, y: 0, rotRad: 0 });

// Latest 2D viewport state used by stage overlays that must track pan/zoom live.
export const editorViewportRef = shallowRef({ zoom: 1, offsetX: 0, offsetY: 0 });

// Handler used by the 2D engine when a passive saved design is clicked in canvas space.
export const passiveModelSelectionHandlerRef = shallowRef(null);

// Latest passive saved-design selection reported by the 2D engine.
export const passiveModelSelectionStateRef = shallowRef([]);

// Latest passive saved-design transforms reported by the 2D engine.
export const passiveModelTransformStateRef = shallowRef([]);

// Handler used by the 2D engine when the active saved design is deleted from canvas space.
export const activeModelDeleteHandlerRef = shallowRef(null);

