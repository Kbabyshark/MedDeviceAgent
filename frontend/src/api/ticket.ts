import { apiClient } from "./client";
import type { TicketInfo, TicketConfirmRequest } from "@/types";

export const ticketApi = {
  createDraft(deviceSn: string, faultDesc: string, priority = "medium") {
    return apiClient.post<TicketInfo>("/ticket/draft", {
      device_sn: deviceSn,
      fault_desc: faultDesc,
      priority,
    });
  },
  confirm(req: TicketConfirmRequest) {
    return apiClient.post<TicketInfo>("/ticket/confirm", req);
  },
  get(ticketId: string) {
    return apiClient.get<TicketInfo>(`/ticket/${ticketId}`);
  },
};
