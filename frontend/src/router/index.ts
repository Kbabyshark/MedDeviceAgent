import { createRouter, createWebHistory } from "vue-router";
import { useAuthStore } from "@/stores/auth";

const router = createRouter({
  history: createWebHistory(),
  routes: [
    {
      path: "/login",
      name: "login",
      component: () => import("@/pages/Login.vue"),
      meta: { guest: true },
    },
    {
      path: "/register",
      name: "register",
      component: () => import("@/pages/Register.vue"),
      meta: { guest: true },
    },
    {
      path: "/",
      redirect: (to: any) => {
        const auth = useAuthStore();
        if (auth.role === "support") return "/support";
        return "/chat";
      },
    },
    {
      path: "/chat",
      name: "chat",
      component: () => import("@/pages/chat/ChatPage.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/my/devices",
      name: "my-devices",
      component: () => import("@/pages/MyDevices.vue"),
      meta: { requiresAuth: true },
    },
    {
      path: "/support",
      name: "support",
      component: () => import("@/pages/SupportPage.vue"),
      meta: { requiresAuth: true, requiresSupport: true },
    },
    {
      path: "/support/mine",
      name: "support-mine",
      component: () => import("@/pages/SupportPage.vue"),
      meta: { requiresAuth: true, requiresSupport: true },
    },
    {
      path: "/support/chat",
      name: "support-chat",
      component: () => import("@/pages/support/SupportChat.vue"),
      meta: { requiresAuth: true, requiresSupport: true },
    },
    {
      path: "/admin",
      name: "admin",
      component: () => import("@/pages/admin/AdminLayout.vue"),
      meta: { requiresAuth: true, requiresAdmin: true },
      children: [
        { path: "", redirect: "/admin/knowledge" },
        { path: "knowledge", name: "admin-knowledge", component: () => import("@/pages/admin/KnowledgePage.vue") },
        { path: "search", name: "admin-search", component: () => import("@/pages/admin/SearchTest.vue") },
        { path: "trace", name: "admin-trace", component: () => import("@/pages/admin/TracePage.vue") },
        { path: "trace/:traceId", name: "admin-trace-replay", component: () => import("@/pages/admin/TraceReplay.vue") },
        { path: "cost", name: "admin-cost", component: () => import("@/pages/admin/CostDashboard.vue") },
        { path: "fault-codes", name: "admin-fault-codes", component: () => import("@/pages/admin/FaultCodePage.vue") },
        { path: "users", name: "admin-users", component: () => import("@/pages/admin/UserPage.vue") },
        { path: "warranties", name: "admin-warranties", component: () => import("@/pages/admin/WarrantyPage.vue") },
        { path: "devices", name: "admin-devices", component: () => import("@/pages/admin/DevicePage.vue") },
        { path: "status", name: "admin-status", component: () => import("@/pages/admin/StatusPage.vue") },
      ],
    },
    {
      path: "/:pathMatch(.*)*",
      name: "not-found",
      component: () => import("@/pages/NotFound.vue"),
    },
  ],
});

// ---- 导航守卫 ----
router.beforeEach((to, _from, next) => {
  const auth = useAuthStore();

  // 需要登录
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return next({ name: "login", query: { redirect: to.fullPath } });
  }

  // 需要管理员（support 可访问设备/故障码/保修查询）
  const supportAllowed = ["admin-devices", "admin-fault-codes", "admin-warranties"];
  if (to.meta.requiresAdmin && !auth.isAdmin && !(auth.role === "support" && supportAllowed.includes(String(to.name)))) {
    return next({ name: "chat" });
  }

  // 需要客服权限（support 或 admin）
  if (to.meta.requiresSupport && auth.role !== "support" && auth.role !== "admin") {
    return next({ name: "chat" });
  }

  // support 角色默认进客服工作台，但允许通过工单进入具体会话
  if (to.name === "chat" && auth.role === "support" && !to.query.session) {
    return next({ name: "support" });
  }

  // 已登录访问登录页 → 跳转聊天
  if (to.meta.guest && auth.isLoggedIn) {
    return next({ name: "chat" });
  }

  next();
});

export default router;
