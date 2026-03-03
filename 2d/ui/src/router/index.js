import { createRouter, createWebHistory } from "vue-router";

import FloorPlanView from "../views/FloorPlanView.vue";
import SettingsView from "../views/SettingsView.vue";

export const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: "/", name: "floorplan", component: FloorPlanView },
    { path: "/settings", name: "settings", component: SettingsView },
  ],
});

