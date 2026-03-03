export interface ChatRequest {
  agent_id: string;
  message: string;
  conversation_id?: string;
}

export interface ChatResponse {
  id: string;
  role: 'assistant';
  content: string;
  type: 'text';
}
