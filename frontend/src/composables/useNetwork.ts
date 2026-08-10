/**
 * 网络状态监听 Composable。
 *
 * 监听在线/离线状态变化，自动提示用户。
 */

import { ref, onMounted, onUnmounted, readonly } from "vue";

export function useNetwork() {
  const isOnline = ref(navigator.onLine);
  const showOfflineBanner = ref(false);

  function handleOnline() {
    isOnline.value = true;
    showOfflineBanner.value = false;
  }

  function handleOffline() {
    isOnline.value = false;
    showOfflineBanner.value = true;
  }

  onMounted(() => {
    window.addEventListener("online", handleOnline);
    window.addEventListener("offline", handleOffline);
  });

  onUnmounted(() => {
    window.removeEventListener("online", handleOnline);
    window.removeEventListener("offline", handleOffline);
  });

  function dismissBanner() {
    showOfflineBanner.value = false;
  }

  return {
    isOnline: readonly(isOnline),
    showOfflineBanner: readonly(showOfflineBanner),
    dismissBanner,
  };
}
