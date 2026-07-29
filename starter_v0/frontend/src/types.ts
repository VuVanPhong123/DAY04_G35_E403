export type Role = 'user' | 'assistant';

export interface ChatMessage {
  role: Role;
  content: string;
}

export interface ToolEvent {
  tool?: string;
  name?: string;
  args?: Record<string, unknown>;
  result?: Record<string, unknown>;
}

export interface ChatResponse {
  session_id: string;
  status: 'answered' | 'waiting_for_user' | 'max_tool_rounds';
  answer: string;
  tool_events: ToolEvent[];
  rounds: unknown[];
}

