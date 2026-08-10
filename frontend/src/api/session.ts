import { apiClient } from "./client";
import type { SessionInfo, MessageItem, PaginatedResponse } from "@/types";

export const sessionApi = {
  create() {
    return apiClient.post<SessionInfo>("/session/create", {});
  },
  get(sessionId: string) {
    return apiClient.get<SessionInfo>(`/session/${sessionId}`);
  },
  getMessages(sessionId: string, page = 1, pageSize = 50) {
    return apiClient.get<PaginatedResponse<MessageItem>>(
      `/session/${sessionId}/messages?page=${page}&page_size=${pageSize}`
    );
  },
  list(page = 1, pageSize = 50) {
    return apiClient.get<PaginatedResponse<SessionInfo>>(
      `/sessions?page=${page}&page_size=${pageSize}`
    );
  },
};
