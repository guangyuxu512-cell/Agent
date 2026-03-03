import { ChatRequest } from '../types/chat';

const API_BASE = import.meta.env.VITE_API_BASE_URL || '/api';

/**
 * SSE 流式发送消息
 * 返回一个 abort 函数，调用后可取消请求（用于组件卸载时清理）
 */
export function sendMessageSSE(
  data: ChatRequest,
  onToken: (token: string) => void,
  onDone: (fullContent: string) => void,
  onError: (error: string) => void,
  onConversationId?: (id: string) => void,
): () => void {
  const token = localStorage.getItem('token');
  let hasDone = false;
  const controller = new AbortController();

  fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: JSON.stringify(data),
    signal: controller.signal,
  })
    .then(async (response) => {
      if (!response.ok) {
        onError(`请求失败: ${response.status}`);
        return;
      }

      const reader = response.body?.getReader();
      if (!reader) {
        onError('无法读取响应流');
        return;
      }

      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          try {
            const json = JSON.parse(line.slice(6));
            switch (json.type) {
              case 'token':
                onToken(json.content);
                break;
              case 'done':
                hasDone = true;
                onDone(json.content);
                break;
              case 'error':
                hasDone = true;
                onError(json.content);
                break;
              case 'conversation_id':
                onConversationId?.(json.content);
                break;
            }
          } catch (e) {
            // 忽略解析失败的行
          }
        }
      }
    })
    .catch((err) => {
      if (err.name === 'AbortError') return; // 组件卸载导致的取消，不报错
      hasDone = true;
      onError(`网络错误: ${err.message}`);
    })
    .finally(() => {
      if (!hasDone) {
        onDone('');
      }
    });

  return () => controller.abort();
}