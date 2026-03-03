import { sendMessageSSE } from '../api/chat';

// ========== Types ==========
interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  type?: 'text' | 'image' | 'file' | 'divider';
}

// ========== 模块级状态（组件卸载后依然存活） ==========
let pendingAiMsgId: string | null = null;
let abortFn: (() => void) | null = null;
let conversationId: string | null = null;
let timeoutId: ReturnType<typeof setTimeout> | null = null;
let listeners: Array<() => void> = [];

const DEFAULT_MSG: Message = {
  id: '1',
  role: 'assistant',
  content: '你好！我是你的专属 Agent，有什么可以帮你的吗？',
  type: 'text',
};

// ========== localStorage 读写 ==========
export function getMessages(): Message[] {
  const saved = localStorage.getItem('chat_messages');
  if (saved) {
    try {
      const parsed: Message[] = JSON.parse(saved);
      // 过滤掉因中断残留的空 AI 消息（但保留正在流式追加的那条）
      const cleaned = parsed.filter(
        msg => !(msg.role === 'assistant' && msg.content === '' && msg.id !== pendingAiMsgId)
      );
      return cleaned.length > 0 ? cleaned : [DEFAULT_MSG];
    } catch {
      // ignore
    }
  }
  return [DEFAULT_MSG];
}

function saveMessages(msgs: Message[]) {
  localStorage.setItem('chat_messages', JSON.stringify(msgs));
  notify();
}

// ========== 订阅 / 通知 ==========
export function subscribe(cb: () => void) {
  listeners.push(cb);
  return () => {
    listeners = listeners.filter(l => l !== cb);
  };
}

function notify() {
  listeners.forEach(cb => cb());
}

// ========== 公开 API ==========

/** 是否正在等待 AI 回复 */
export function isSending(): boolean {
  return pendingAiMsgId !== null;
}

/** 获取当前 conversationId */
export function getConversationId(): string | null {
  return conversationId;
}

/** 发送消息（启动 SSE，模块级管理，组件卸载不中断） */
export function send(agentId: string, message: string) {
  if (!message.trim() || !agentId || pendingAiMsgId) return;

  const msgs = getMessages();
  const userMsg: Message = {
    id: Date.now().toString(),
    role: 'user',
    content: message,
    type: 'text',
  };
  const aiMsgId = (Date.now() + 1).toString();
  const aiMsg: Message = {
    id: aiMsgId,
    role: 'assistant',
    content: '',
    type: 'text',
  };

  pendingAiMsgId = aiMsgId;
  saveMessages([...msgs, userMsg, aiMsg]);

  // 120 秒兜底超时
  timeoutId = setTimeout(() => {
    pendingAiMsgId = null;
    timeoutId = null;
    abortFn = null;
    notify();
  }, 120000);

  const abort = sendMessageSSE(
    {
      agent_id: agentId,
      message,
      conversation_id: conversationId || undefined,
    },
    // onToken
    (token) => {
      if (!pendingAiMsgId) return;
      const current = getMessages();
      const updated = current.map(m =>
        m.id === aiMsgId ? { ...m, content: m.content + token } : m
      );
      saveMessages(updated);
    },
    // onDone
    () => {
      if (timeoutId) clearTimeout(timeoutId);
      pendingAiMsgId = null;
      timeoutId = null;
      abortFn = null;
      notify();
    },
    // onError
    (error) => {
      if (timeoutId) clearTimeout(timeoutId);
      if (pendingAiMsgId) {
        const current = getMessages();
        const updated = current.map(m =>
          m.id === aiMsgId ? { ...m, content: `❌ ${error}` } : m
        );
        saveMessages(updated);
      }
      pendingAiMsgId = null;
      timeoutId = null;
      abortFn = null;
      notify();
    },
    // onConversationId
    (id) => {
      conversationId = id;
    }
  );

  abortFn = abort;
}

/** 清空所有消息（同时 abort 进行中的 SSE） */
export function clearMessages() {
  abortFn?.();
  if (timeoutId) clearTimeout(timeoutId);
  abortFn = null;
  pendingAiMsgId = null;
  timeoutId = null;
  conversationId = null;
  saveMessages([{
    id: Date.now().toString(),
    role: 'assistant',
    content: '你好！我是你的专属 Agent，有什么可以帮你的吗？',
    type: 'text',
  }]);
}

/** 清除上下文（不清消息，只重置 conversationId） */
export function clearContext() {
  conversationId = null;
  const msgs = getMessages();
  saveMessages([
    ...msgs,
    {
      id: Date.now().toString(),
      role: 'system' as const,
      content: '— 上下文已清除 —',
      type: 'divider' as const,
    },
  ]);
}

/** 手动中止 SSE（外部调用） */
export function abortRequest() {
  abortFn?.();
  abortFn = null;
}

// ========== ⭐ Step 5.5 新增：服务端对话加载 ==========

/** ⭐ 获取当前 conversationId（AgentChat.tsx 初始化时用） */

/** 设置当前 conversationId（从对话列表点击时用） */
export function setConversationId(id: string | null) {
  conversationId = id;
}

/** 从服务端消息列表加载到本地（替换 localStorage 中的消息） */
export function loadServerMessages(serverMessages: Array<{
  id: string;
  role: 'user' | 'assistant';
  content: string;
}>) {
  if (serverMessages.length === 0) {
    saveMessages([DEFAULT_MSG]);
    return;
  }
  const msgs: Message[] = serverMessages.map(m => ({
    id: m.id,
    role: m.role,
    content: m.content,
    type: 'text' as const,
  }));
  saveMessages(msgs);
}

/** 开始新对话（清除 conversationId + 重置消息） */
export function startNewChat() {
  abortFn?.();
  if (timeoutId) clearTimeout(timeoutId);
  abortFn = null;
  pendingAiMsgId = null;
  timeoutId = null;
  conversationId = null;
  saveMessages([{
    id: Date.now().toString(),
    role: 'assistant',
    content: '你好！我是你的专属 Agent，有什么可以帮你的吗？',
    type: 'text',
  }]);
}
