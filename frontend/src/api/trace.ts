import { apiClient } from "./client";
import type { TraceInfo, ReplayStep, CostSummary } from "@/types";

export const traceApi = {
  get(traceId: string) {
    return apiClient.get<TraceInfo>(`/trace/${traceId}`);
  },
  getNodes(traceId: string) {
    return apiClient.get(`/trace/${traceId}/nodes`);
  },
  getReplay(traceId: string) {
    return apiClient.get<{ steps: ReplayStep[]; query: string; total_latency_ms: number }>(
      `/trace/${traceId}/replay`
    );
  },
  list(params: { user_id?: string; session_id?: string; status?: string; page?: number; page_size?: number }) {
    const qs = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v) qs.set(k, String(v)); });
    return apiClient.get(`/traces?${qs.toString()}`);
  },
  getCost(days = 30) {
    return apiClient.get<CostSummary>(`/admin/cost?days=${days}`);
  },
};
