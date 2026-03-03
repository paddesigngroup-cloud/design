import { defineConfig } from "vite";
import vue from "@vitejs/plugin-vue";
import { fileURLToPath } from "node:url";
import path from "node:path";

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue()],
  server: {
    fs: {
      // Allow importing the 2D engine modules from the parent folder (C:\DesignKP\2d\).
      allow: [path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..")],
    },
  },
})
