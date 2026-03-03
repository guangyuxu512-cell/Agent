# app/常量.py
# 集中管理可调参数，避免散落在各文件中的魔法数字

# ==================== LLM 默认值 ====================
DEFAULT_MODEL = "GPT-4o"
DEFAULT_TEMPERATURE = 0.7
MEMORY_EXTRACTION_TEMPERATURE = 0.3
MEMORY_EXTRACTION_MAX_TOKENS = 500

# ==================== 超时（秒） ====================
PYTHON_TOOL_EXEC_TIMEOUT = 10          # 沙箱 Python 工具执行超时
LLM_HTTP_TIMEOUT = 30                  # 记忆提取 LLM 调用超时
RAGFLOW_TIMEOUT = 15                   # RAGFlow 知识检索超时
FEISHU_AGENT_TIMEOUT = 120             # 飞书智能体调用最大等待
SCHEDULER_MISFIRE_GRACE = 60           # APScheduler 错过触发容忍

# ==================== 飞书长连接 ====================
FEISHU_SESSION_TIMEOUT = 1800          # 会话超时（30 分钟）
FEISHU_DEDUP_LIMIT = 5000             # 消息去重集合上限
FEISHU_MSG_EXPIRE = 120                # 消息过期阈值（秒）
FEISHU_MSG_MAX_LEN = 4000             # 飞书消息长度限制
FEISHU_MAX_RETRY = 3                   # 智能体调用最大重试次数

# ==================== 截断长度 ====================
TOOL_RESULT_MAX_LEN = 500              # 工具调用结果截断
HTTP_TOOL_RESULT_MAX_LEN = 2000        # HTTP 工具响应截断
SCHEDULER_RESULT_MAX_LEN = 5000        # 调度器任务结果截断
SCHEDULER_ERROR_MAX_LEN = 2000         # 调度器错误信息截断
CONVERSATION_TEXT_MAX_LEN = 6000       # 记忆提取对话文本截断

# ==================== 查询限制 ====================
LOG_HISTORY_LIMIT = 500                # 日志历史查询上限
LOG_DEFAULT_PAGE_SIZE = 200            # 日志默认分页大小
LOG_RETENTION_DAYS = 30                # 日志保留天数
MEMORY_DEFAULT_LIMIT = 10             # 记忆查询默认条数
MEMORY_SUMMARY_LIMIT = 5              # 最近摘要查询条数
RAGFLOW_DEFAULT_TOP_K = 3             # 知识检索默认 top_k
CONV_TITLE_MAX_LEN = 20               # 对话标题截断长度
