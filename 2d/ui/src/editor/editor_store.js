import { shallowRef } from "vue";

// Holds the singleton instance of the embedded 2D editor engine.
export const editorRef = shallowRef(null);

// Latest 2D transform of the projected 3D model (millimeters in 2D world).
export const model2dTransformRef = shallowRef({ x: 0, y: 0, rotRad: 0 });

