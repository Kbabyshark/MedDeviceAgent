/** 对齐后端 Pydantic Schema */

export interface APIResponse<T = unknown> {
  code: number;
  message: string;
  data: T | null;
}

export interface PaginatedData<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
}

export interface PaginatedResponse<T> extends APIResponse<PaginatedData<T>> {}

// ---- Chat ----
export interface ChatRequest {
  session_id: string;
  message: string;
  device_type?: string;
}

export interface ChatResponse {
  answer: string;
  trace_id: string;
  citations: Citation[];
}

export interface Citation {
  source: string;
  device_type: string;
  version: string;
  score: number;
  snippet: string;
}

export interface StreamEvent {
  event: "start" | "node" | "token" | "tool_call" | "tool_result"
    | "human_confirm_required" | "error" | "heartbeat" | "end";
  data: Record<string, unknown>;
}

// ---- Session ----
export interface SessionInfo {
  session_id: string;
  title: string | null;
  summary: string | null;
  status: string;
  created_at: string | null;
}

export interface MessageItem {
  role: "user" | "assistant" | "tool" | "system";
  content: string;
  created_at: string | null;
}

// ---- Ticket ----
export interface TicketInfo {
  ticket_id: string;
  device_sn: string;
  fault_desc: string;
  status: string;
  priority: string;
  created_at?: string | null;
}

export interface TicketConfirmRequest {
  ticket_id: string;
  confirm: boolean;
}

// ---- Knowledge ----
export interface KnowledgeDocument {
  document_id: string;
  name: string;
  device_type: string;
  doc_type: string;
  version: string;
  status: string;
  chunk_count: number;
  created_at: string;
}

export interface DocumentStatus {
  document_id: string;
  name: string;
  version: string;
  status: string;
  chunks_total: number;
  chunks_embedded: number;
  chunks_pending: number;
  chunks_failed: number;
}

export interface KnowledgeSearchResult {
  content: string;
  metadata: Record<string, string>;
  score: number;
}

// ---- Trace ----
export interface TraceInfo {
  trace_id: string;
  session_id: string;
  user_id: string;
  query: string;
  start_time: string;
  end_time: string | null;
  total_latency: number;
  status: string;
  node_count: number;
  llm_call_count: number;
  total_tokens: number;
  nodes: TraceNode[];
  llm_calls: LLMCallRecord[];
}

export interface TraceNode {
  trace_id: string;
  node_name: string;
  index: number;
  input: unknown;
  output: unknown;
  latency: number;
  error: string | null;
}

export interface LLMCallRecord {
  trace_id: string;
  task_type: string;
  model_name: string;
  prompt_tokens: number;
  completion_tokens: number;
  total_tokens: number;
  latency: number;
}

export interface ReplayStep {
  step: number;
  node: string;
  input_summary: string;
  output_summary: string;
  latency_ms: number;
  error: string | null;
}

export interface CostSummary {
  period_days: number;
  total_calls: number;
  total_prompt_tokens: number;
  total_completion_tokens: number;
  total_tokens: number;
  estimated_cost_cny: number;
  daily_breakdown: DailyCost[];
}

export interface DailyCost {
  date: string;
  prompt_tokens: number;
  completion_tokens: number;
  calls: number;
}

// ---- System ----
export interface SystemStatus {
  status: string;
  app: string;
  version: string;
  env: string;
  performance: Record<string, PathPerf>;
  alerts_triggered: AlertItem[];
  alert_rules: AlertRule[];
}

export interface PathPerf {
  count: number;
  avg_ms: number;
  p50_ms: number;
  p95_ms: number;
  p99_ms: number;
  max_ms: number;
  min_ms: number;
  slow_count: number;
}

export interface AlertItem {
  name: string;
  level: string;
  description: string;
  current_value: number;
  threshold: number;
}

export interface AlertRule {
  name: string;
  level: string;
  threshold: number;
}

// ---- Auth ----
export interface LoginRequest {
  username: string;
  password: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: number;
  role: string;
  username: string;
}

export interface RegisterRequest {
  username: string;
  password: string;
  phone?: string;
  email?: string;
}

export interface UserInfo {
  user_id: number;
  username: string;
  role: string;
  phone: string | null;
  email: string | null;
  status: number;  // 1=正常 0=禁用
  created_at: string | null;
}
