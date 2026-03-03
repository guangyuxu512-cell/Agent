import { useState, useRef, useEffect, useCallback } from 'react';
import {
  Send, Mic, Paperclip, Image as ImageIcon, Trash2, RefreshCw,
  Bot, User, Plus, MessageSquare, Clock,
} from 'lucide-react';
import ReactMarkdown from 'react-markdown';
import * as chatStore from '../stores/chatStore';
import { fetchConversations, fetchMessages, deleteConversation, Conversation } from '../api/conversations';

// 动画延迟样式
const BOUNCE_DELAY_1 = { animationDelay: '0ms' };
const BOUNCE_DELAY_2 = { animationDelay: '150ms' };
const BOUNCE_DELAY_3 = { animationDelay: '300ms' };

// ========== 对话列表侧边栏组件 ==========
function ConversationSidebar({
  conversations,
  activeId,
  onSelect,
  onNewChat,
  onDelete,
}: {
  conversations: Conversation[];
  activeId: string | null;
  onSelect: (conv: Conversation) => void;
  onNewChat: () => void;
  onDelete: (id: string) => void;
}) {
  return (
    <div className="w-64 border-r border-slate-200 bg-slate-50 flex flex-col h-full">
      {/* 新对话按钮 */}
      <div className="p-3 border-b border-slate-200">
        <button
          onClick={onNewChat}
          className="w-full flex items-center justify-center gap-2 px-3 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors text-sm font-medium"
        >
          <Plus size={16} />
          新对话
        </button>
      </div>

      {/* 对话列表 */}
      <div className="flex-1 overflow-y-auto">
        {conversations.length === 0 ? (
          <div className="p-4 text-center text-slate-400 text-sm">暂无对话</div>
        ) : (
          conversations.map(conv => (
            <div
              key={conv.id}
              onClick={() => onSelect(conv)}
              className={`group flex items-start gap-2 p-3 cursor-pointer border-b border-slate-100 hover:bg-white transition-colors ${
                activeId === conv.id ? 'bg-white border-l-2 border-l-blue-600' : ''
              }`}
            >
              <MessageSquare size={16} className="text-slate-400 mt-0.5 shrink-0" />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-1">
                  <span className="text-sm font-medium text-slate-700 truncate">
                    {conv.title}
                  </span>
                  {conv.source === 'feishu' && (
                    <span className="shrink-0 text-[10px] px-1 py-0.5 bg-blue-100 text-blue-600 rounded">
                      飞书
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-1 mt-0.5">
                  <Clock size={10} className="text-slate-300" />
                  <span className="text-[11px] text-slate-400 truncate">
                    {conv.updated_at}
                  </span>
                </div>
              </div>
              {/* 删除按钮 */}
              <button
                onClick={e => { e.stopPropagation(); onDelete(conv.id); }}
                className="opacity-0 group-hover:opacity-100 p-1 text-slate-300 hover:text-red-500 transition-all"
                title="删除对话"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

// ========== 主组件 ==========
export default function AgentChat() {
  // ========== State ==========
  const [messages, setMessages] = useState(chatStore.getMessages);
  const [isTyping, setIsTyping] = useState(chatStore.isSending);
  const [input, setInput] = useState('');
  const [currentAgentId, setCurrentAgentId] = useState<string>('');
  const [conversations, setConversations] = useState<Conversation[]>([]);
  const [activeConvId, setActiveConvId] = useState<string | null>(chatStore.getConversationId());
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // ========== SSE 防闪烁 Refs ==========
  const streamingRef = useRef<HTMLDivElement>(null);
  const streamingTextRef = useRef('');
  const prevMsgCountRef = useRef(0);
  const wasSendingRef = useRef(false);

  // ========== 加载智能体 ID（优先使用编排入口 Agent） ==========
  useEffect(() => {
    const token = localStorage.getItem('token');
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    const base = import.meta.env.VITE_API_BASE_URL || '/api';

    Promise.all([
      fetch(`${base}/orchestration`, { headers }).then(r => r.json()).catch(() => null),
      fetch(`${base}/agents`, { headers }).then(r => r.json()).catch(() => null),
    ]).then(([orchRes, agentsRes]) => {
      // 优先使用编排配置的入口 Agent
      const entryAgent = orchRes?.code === 0 && orchRes?.data?.entryAgent;
      if (entryAgent) {
        setCurrentAgentId(entryAgent);
        return;
      }
      // 回退：取 Agent 列表第一个
      if (agentsRes?.code === 0 && agentsRes?.data?.list?.length > 0) {
        setCurrentAgentId(agentsRes.data.list[0].id);
      }
    });
  }, []);

  // ========== ⭐ 轮询对话列表（5 秒） ==========
  const loadConversations = useCallback(async () => {
    try {
      const data = await fetchConversations();
      setConversations(data.list);
    } catch (e) {
      console.error('加载对话列表失败:', e);
    }
  }, []);

  useEffect(() => {
    if (!currentAgentId) return;
    loadConversations();
    const timer = setInterval(loadConversations, 5000);
    return () => clearInterval(timer);
  }, [currentAgentId, loadConversations]);

  // ========== chatStore 订阅（SSE 防闪烁） ==========
  useEffect(() => {
    const initMsgs = chatStore.getMessages();
    prevMsgCountRef.current = initMsgs.length;
    wasSendingRef.current = chatStore.isSending();

    const unsub = chatStore.subscribe(() => {
      const nowSending = chatStore.isSending();
      const msgs = chatStore.getMessages();

      // ⭐ 同步 activeConvId
      setActiveConvId(chatStore.getConversationId());

      if (nowSending) {
        if (msgs.length !== prevMsgCountRef.current) {
          prevMsgCountRef.current = msgs.length;
          setMessages([...msgs]);
        }
        const lastMsg = msgs[msgs.length - 1];
        if (lastMsg && lastMsg.role === 'assistant') {
          streamingTextRef.current = lastMsg.content || '';
          if (streamingRef.current) {
            streamingRef.current.textContent = streamingTextRef.current;
          }
        }
        if (!wasSendingRef.current) {
          setIsTyping(true);
        }
      } else {
        prevMsgCountRef.current = msgs.length;
        streamingTextRef.current = '';
        setMessages([...msgs]);
        setIsTyping(false);
        // ⭐ SSE 完成后立即刷新对话列表
        loadConversations();
      }

      wasSendingRef.current = nowSending;
    });

    setMessages(chatStore.getMessages());
    setIsTyping(chatStore.isSending());
    return unsub;
  }, [loadConversations]);

  // 流式 ref 同步
  useEffect(() => {
    if (isTyping && streamingRef.current && streamingTextRef.current) {
      streamingRef.current.textContent = streamingTextRef.current;
    }
  });

  // 自动滚动
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };
  useEffect(() => { scrollToBottom(); }, [messages, isTyping]);
  useEffect(() => {
    if (!isTyping) return;
    const timer = setInterval(scrollToBottom, 200);
    return () => clearInterval(timer);
  }, [isTyping]);

  // ========== Handlers ==========
  const handleSend = () => {
    if (!input.trim() || !currentAgentId || chatStore.isSending()) return;
    chatStore.send(currentAgentId, input);
    setInput('');
  };

  // ⭐ 点击对话列表加载历史
  const handleSelectConversation = async (conv: Conversation) => {
    if (chatStore.isSending()) return;
    try {
      const serverMsgs = await fetchMessages(conv.id);
      chatStore.setConversationId(conv.id);
      chatStore.loadServerMessages(serverMsgs);
      setActiveConvId(conv.id);
    } catch (e) {
      console.error('加载消息失败:', e);
    }
  };

  // ⭐ 新对话
  const handleNewChat = () => {
    if (chatStore.isSending()) return;
    chatStore.startNewChat();
    setActiveConvId(null);
  };

  // ⭐ 删除对话
  const handleDeleteConversation = async (id: string) => {
    try {
      await deleteConversation(id);
      if (activeConvId === id) {
        chatStore.startNewChat();
        setActiveConvId(null);
      }
      loadConversations();
    } catch (e) {
      console.error('删除对话失败:', e);
    }
  };

  const handleClearMessages = () => chatStore.clearMessages();
  const handleClearContext = () => chatStore.clearContext();

  // ========== Render ==========
  return (
    <div className="flex h-[calc(100vh-8rem)] bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
      {/* ⭐ 左侧对话列表 */}
      <ConversationSidebar
        conversations={conversations}
        activeId={activeConvId}
        onSelect={handleSelectConversation}
        onNewChat={handleNewChat}
        onDelete={handleDeleteConversation}
      />

      {/* 右侧聊天区域 */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Header */}
        <div className="flex justify-between items-center p-4 border-b border-slate-100 bg-slate-50">
          <div className="flex items-center gap-2 text-slate-800 font-bold">
            <Bot className="text-blue-600" />
            Agent 聊天
            {activeConvId && (
              <span className="text-xs font-normal text-slate-400 ml-2">
                {conversations.find(c => c.id === activeConvId)?.title}
              </span>
            )}
          </div>
          <div className="flex gap-2">
            <button onClick={handleClearContext} className="flex items-center gap-1 px-3 py-1.5 text-sm text-slate-600 hover:bg-slate-200 rounded-lg transition-colors">
              <RefreshCw size={14} /> 清除上下文
            </button>
            <button onClick={handleClearMessages} className="flex items-center gap-1 px-3 py-1.5 text-sm text-red-600 hover:bg-red-50 rounded-lg transition-colors">
              <Trash2 size={14} /> 清空消息
            </button>
          </div>
        </div>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto p-4 space-y-6 bg-slate-50/50">
          {messages.map((msg, index) => {
            if (msg.type === 'divider') {
              return (
                <div key={msg.id} className="flex items-center justify-center my-6">
                  <div className="border-b border-slate-200 flex-1" />
                  <span className="px-4 text-xs text-slate-400">{msg.content}</span>
                  <div className="border-b border-slate-200 flex-1" />
                </div>
              );
            }

            const isLastAssistant = msg.role === 'assistant' && index === messages.length - 1;
            const isCurrentlyStreaming = isLastAssistant && isTyping;

            return (
              <div key={msg.id} className={`flex gap-4 ${msg.role === 'user' ? 'flex-row-reverse' : ''}`}>
                <div className={`w-8 h-8 rounded-full flex items-center justify-center shrink-0 ${msg.role === 'user' ? 'bg-blue-600 text-white' : 'bg-slate-200 text-slate-600'}`}>
                  {msg.role === 'user' ? <User size={16} /> : <Bot size={16} />}
                </div>
                <div className={`max-w-[70%] rounded-2xl p-4 ${msg.role === 'user'
                  ? 'bg-blue-600 text-white rounded-tr-none'
                  : 'bg-white border border-slate-200 text-slate-800 rounded-tl-none shadow-sm'
                }`}>
                  {isCurrentlyStreaming ? (
                    <div ref={streamingRef} className="whitespace-pre-wrap break-words leading-relaxed" />
                  ) : msg.role === 'assistant' ? (
                    <ReactMarkdown
                      components={{
                        p: ({ children }) => <p className="mb-2 last:mb-0 leading-relaxed">{children}</p>,
                        ul: ({ children }) => <ul className="list-disc ml-4 mb-2 space-y-1">{children}</ul>,
                        ol: ({ children }) => <ol className="list-decimal ml-4 mb-2 space-y-1">{children}</ol>,
                        li: ({ children }) => <li className="leading-relaxed">{children}</li>,
                        code: ({ className, children, ...props }) => {
                          if (className) return <code className={className} {...props}>{children}</code>;
                          return <code className="bg-slate-100 text-pink-600 px-1.5 py-0.5 rounded text-sm" {...props}>{children}</code>;
                        },
                        pre: ({ children }) => <pre className="bg-slate-900 text-slate-100 p-3 rounded-lg overflow-x-auto text-sm my-2">{children}</pre>,
                        h1: ({ children }) => <h1 className="text-lg font-bold mb-2 mt-3">{children}</h1>,
                        h2: ({ children }) => <h2 className="text-base font-bold mb-2 mt-3">{children}</h2>,
                        h3: ({ children }) => <h3 className="text-sm font-bold mb-1 mt-2">{children}</h3>,
                        blockquote: ({ children }) => <blockquote className="border-l-4 border-slate-300 pl-3 italic text-slate-600 mb-2">{children}</blockquote>,
                        a: ({ href, children }) => <a href={href} className="text-blue-600 underline hover:text-blue-800" target="_blank" rel="noopener noreferrer">{children}</a>,
                        strong: ({ children }) => <strong className="font-semibold">{children}</strong>,
                        hr: () => <hr className="my-3 border-slate-200" />,
                        table: ({ children }) => <div className="overflow-x-auto my-2"><table className="min-w-full border-collapse border border-slate-200 text-sm">{children}</table></div>,
                        th: ({ children }) => <th className="border border-slate-200 bg-slate-50 px-3 py-1.5 text-left font-semibold">{children}</th>,
                        td: ({ children }) => <td className="border border-slate-200 px-3 py-1.5">{children}</td>,
                      }}
                    >
                      {msg.content}
                    </ReactMarkdown>
                  ) : (
                    <span className="whitespace-pre-wrap">{msg.content}</span>
                  )}
                </div>
              </div>
            );
          })}

          {isTyping && messages[messages.length - 1]?.role !== 'assistant' && (
            <div className="flex gap-4">
              <div className="w-8 h-8 rounded-full flex items-center justify-center shrink-0 bg-slate-200 text-slate-600">
                <Bot size={16} />
              </div>
              <div className="bg-white border border-slate-200 rounded-2xl rounded-tl-none p-4 shadow-sm flex gap-1 items-center">
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={BOUNCE_DELAY_1} />
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={BOUNCE_DELAY_2} />
                <div className="w-2 h-2 bg-slate-400 rounded-full animate-bounce" style={BOUNCE_DELAY_3} />
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>

        {/* Input Area */}
        <div className="p-4 bg-white border-t border-slate-100">
          <div className="flex items-end gap-2 bg-slate-50 border border-slate-200 rounded-xl p-2 focus-within:border-blue-500 focus-within:ring-1 focus-within:ring-blue-500 transition-colors">
            <div className="flex gap-1 pb-1 pl-1">
              <button className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-lg transition-colors" title="语音输入">
                <Mic size={20} />
              </button>
              <button className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-lg transition-colors" title="上传图片">
                <ImageIcon size={20} />
              </button>
              <button className="p-2 text-slate-400 hover:text-slate-600 hover:bg-slate-200 rounded-lg transition-colors" title="上传文件">
                <Paperclip size={20} />
              </button>
            </div>
            <textarea
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              placeholder="输入消息，Enter 发送，Shift+Enter 换行..."
              className="flex-1 max-h-32 min-h-[44px] bg-transparent border-none focus:ring-0 resize-none py-2.5 px-2 outline-none"
              rows={1}
            />
            <button
              onClick={handleSend}
              disabled={!input.trim() || isTyping}
              className="p-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors mb-0.5 mr-0.5"
            >
              <Send size={18} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}