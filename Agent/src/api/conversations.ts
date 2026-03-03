// src/api/conversations.ts
// 对话列表 + 消息加载 API — 使用统一 axios 实例

import request from './index';

export interface Conversation {
  id: string;
  agent_id: string;
  agent_name: string;
  title: string;
  source: 'web' | 'feishu';
  message_count: number;
  created_at: string;
  updated_at: string;
}

export interface ServerMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  agent_name: string;
  created_at: string;
}

/** 获取对话列表 */
export async function fetchConversations(
  agentId?: string,
  page = 1,
  pageSize = 50,
): Promise<{ list: Conversation[]; total: number }> {
  const params: Record<string, string> = {
    page: String(page),
    page_size: String(pageSize),
  };
  if (agentId) params.agent_id = agentId;

  const data: any = await request.get('/conversations', { params });
  if (data.code !== 0) throw new Error(data.msg);
  return data.data;
}

/** 获取对话的消息列表 */
export async function fetchMessages(conversationId: string): Promise<ServerMessage[]> {
  const data: any = await request.get(`/conversations/${conversationId}/messages`);
  if (data.code !== 0) throw new Error(data.msg);
  return data.data;
}

/** 删除对话 */
export async function deleteConversation(conversationId: string): Promise<void> {
  const data: any = await request.delete(`/conversations/${conversationId}`);
  if (data.code !== 0) throw new Error(data.msg);
}
