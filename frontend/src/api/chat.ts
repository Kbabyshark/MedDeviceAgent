import { apiClient } from "./client";
import type { ChatRequest, ChatResponse } from "@/types";

export const chatApi = {
  send(req: ChatRequest) {
    return apiClient.post<ChatResponse>("/chat", req);
  },
  stream(body: ChatRequest) {
    return apiClient.stream("/chat/stream", body);
  },
};
