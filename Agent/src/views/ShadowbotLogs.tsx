  import { useState, useEffect, useRef } from 'react';
  import { Activity, CheckCircle2, AlertCircle, Monitor, Clock, Terminal, Search, X, Server, Package } from 'lucide-react';

  // 定义日志数据结构
  interface LogEntry {
    seq?: number;
    time: string;
    task_id: string;
    machine: string;
    level: string;
    msg: any;
  }

  interface TaskState {
    taskId: string;
    machine: string;
    level: string;
    latestTime: string;
    latestMsg: any;
    logs: LogEntry[];
  }

  // 机器管理数据结构
  interface Machine {
    id: number;
    machine_id: string;
    machine_name: string;
    status: 'idle' | 'running' | 'error' | 'offline';
    last_heartbeat: string | null;
    created_at: string;
    updated_at: string;
  }

  // 应用绑定数据结构
  interface MachineApp {
    id: number;
    machine_id: string;
    app_name: string;
    description: string;
    enabled: boolean;
    created_at: string;
  }

  type TabType = 'logs' | 'machines' | 'apps';

  export default function ShadowbotLogs() {
    // Tab 切换状态
    const [activeTab, setActiveTab] = useState<TabType>('logs');

    // 运行日志相关状态
    const [tasks, setTasks] = useState<Record<string, TaskState>>(() => {
      const saved = localStorage.getItem('shadowbot_logs');
      if (saved) {
        try {
          return JSON.parse(saved);
        } catch (e) {
          console.error('Failed to parse shadowbot_logs', e);
        }
      }
      return {};
    });
    const [searchInput, setSearchInput] = useState('');
    const [dismissedIds, setDismissedIds] = useState<Set<string>>(() => {
      const saved = localStorage.getItem('shadowbot_dismissed');
      if (saved) {
        try {
          return new Set(JSON.parse(saved));
        } catch (e) {
          console.error('Failed to parse shadowbot_dismissed', e);
        }
      }
      return new Set();
    });

    const tasksRef = useRef<Record<string, TaskState>>(tasks);
    const dismissedIdsRef = useRef(dismissedIds);
    const lastSeqRef = useRef((() => {
      const saved = localStorage.getItem('shadowbot_last_seq');
      return saved ? parseInt(saved, 10) : 0;
    })());

    // 机器管理相关状态
    const [machines, setMachines] = useState<Machine[]>([]);
    const [showAddMachineModal, setShowAddMachineModal] = useState(false);
    const [showEditMachineModal, setShowEditMachineModal] = useState(false);
    const [showDeleteMachineConfirm, setShowDeleteMachineConfirm] = useState(false);
    const [currentMachine, setCurrentMachine] = useState<Machine | null>(null);
    const [machineForm, setMachineForm] = useState({ machine_id: '', machine_name: '' });

    // 应用绑定相关状态
    const [machineApps, setMachineApps] = useState<MachineApp[]>([]);
    const [filterMachineId, setFilterMachineId] = useState<string>('');
    const [showAddAppModal, setShowAddAppModal] = useState(false);
    const [showDeleteAppConfirm, setShowDeleteAppConfirm] = useState(false);
    const [currentApp, setCurrentApp] = useState<MachineApp | null>(null);
    const [appForm, setAppForm] = useState({ machine_id: '', app_name: '', description: '' });

    // 处理接收到的新日志
    const handleNewLog = (log: LogEntry, isRealtime: boolean) => {
      if (log.seq && log.seq > lastSeqRef.current) {
        lastSeqRef.current = log.seq;
        localStorage.setItem('shadowbot_last_seq', String(log.seq));
      }

      const taskId = log.task_id;

      // 如果是实时数据且该 taskId 在 dismissedIds 里，则从 dismissedIds 中移除它
      if (isRealtime && dismissedIdsRef.current.has(taskId)) {
        setDismissedIds(prev => {
          const newSet = new Set(prev);
          newSet.delete(taskId);
          return newSet;
        });
      }

      // 如果是历史数据且该 taskId 在 dismissedIds 里，直接 return
      if (!isRealtime && dismissedIdsRef.current.has(taskId)) {
        return;
      }

      setTasks(prev => {
        // 如果是历史数据且 tasks 里不存在该 taskId，直接 return
        if (!isRealtime && !prev[taskId]) {
          return prev;
        }

        const existingTask = prev[taskId] || {
          taskId,
          machine: '',
          level: '',
          latestTime: '',
          latestMsg: '',
          logs: []
        };

        // seq 去重：防止 SSE + 轮询重复
        if (log.seq && existingTask.logs.some(l => l.seq === log.seq)) {
          return prev;
        }

        const updatedLogs = [log, ...existingTask.logs].slice(0, 50);

        // ★ 直接用最新收到的数据更新头部（去掉 isNewer 守卫）
        const updatedTask: TaskState = {
          ...existingTask,
          machine: log.machine || existingTask.machine || '未知设备',
          level: log.level || '',
          latestTime: log.time,
          latestMsg: log.msg,
          logs: updatedLogs
        };

        let newTasks = { ...prev, [taskId]: updatedTask };

        const taskEntries = Object.entries(newTasks);
        if (taskEntries.length > 20) {
          taskEntries.sort((a, b) => new Date(b[1].latestTime).getTime() - new Date(a[1].latestTime).getTime());
          newTasks = Object.fromEntries(taskEntries.slice(0, 20));
        }

        tasksRef.current = newTasks;
        localStorage.setItem('shadowbot_logs', JSON.stringify(newTasks));
        return newTasks;
      });
    };

    const handleSearch = () => {
      const taskId = searchInput.trim();
      if (!taskId) return;

      // 用户主动搜索意味着想看，从 dismissedIds 中移除
      setDismissedIds(prev => {
        const newSet = new Set(prev);
        newSet.delete(taskId);
        return newSet;
      });

      setTasks(prev => {
        if (prev[taskId]) return prev;

        const now = new Date();
        const timeStr = `${now.getFullYear()}-${String(now.getMonth() + 1).padStart(2, '0')}-${String(now.getDate()).padStart(2, '0')} ${String(now.getHours()).padStart(2, '0')}:${String(now.getMinutes()).padStart(2, '0')}:${String(now.getSeconds()).padStart(2, '0')}`;

        let newTasks = {
          ...prev,
          [taskId]: {
            taskId,
            machine: '等待连接...',
            level: '连接中',
            latestTime: timeStr,
            latestMsg: '等待接收日志...',
            logs: []
          }
        };

        const taskEntries = Object.entries(newTasks);
        if (taskEntries.length > 20) {
          taskEntries.sort((a, b) => new Date(b[1].latestTime).getTime() - new Date(a[1].latestTime).getTime());
          newTasks = Object.fromEntries(taskEntries.slice(0, 20));
        }

        tasksRef.current = newTasks;
        localStorage.setItem('shadowbot_logs', JSON.stringify(newTasks));
        return newTasks;
      });

      setSearchInput('');
    };

    const handleDeleteTask = (taskId: string) => {
      setDismissedIds(prev => {
        const newSet = new Set(prev);
        newSet.add(taskId);
        return newSet;
      });

      setTasks(prev => {
        const newTasks = { ...prev };
        delete newTasks[taskId];
        tasksRef.current = newTasks;
        localStorage.setItem('shadowbot_logs', JSON.stringify(newTasks));
        return newTasks;
      });
    };

    // 同步 dismissedIds 到 localStorage
    useEffect(() => {
      dismissedIdsRef.current = dismissedIds;
      localStorage.setItem('shadowbot_dismissed', JSON.stringify([...dismissedIds]));
    }, [dismissedIds]);

    // ==================== 机器管理相关函数 ====================

    // 获取机器列表
    const fetchMachines = async () => {
      try {
        const token = localStorage.getItem('token');
        const res = await fetch('/api/machines', {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const json = await res.json();
        if (json.code === 0 && json.data) {
          setMachines(json.data);
        }
      } catch (e) {
        console.error('获取机器列表失败:', e);
      }
    };

    // 添加机器
    const handleAddMachine = async () => {
      if (!machineForm.machine_id.trim() || !machineForm.machine_name.trim()) {
        alert('请填写完整信息');
        return;
      }

      try {
        const token = localStorage.getItem('token');
        const res = await fetch('/api/machines', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            machine_id: machineForm.machine_id.trim(),
            machine_name: machineForm.machine_name.trim()
          })
        });
        const json = await res.json();

        if (json.code === 0) {
          setShowAddMachineModal(false);
          setMachineForm({ machine_id: '', machine_name: '' });
          fetchMachines();
        } else {
          alert(json.msg || '添加失败');
        }
      } catch (e) {
        console.error('添加机器失败:', e);
        alert('添加失败');
      }
    };

    // 编辑机器
    const handleEditMachine = async () => {
      if (!currentMachine || !machineForm.machine_name.trim()) {
        alert('请填写机器名称');
        return;
      }

      try {
        const token = localStorage.getItem('token');
        const res = await fetch(`/api/machines/${currentMachine.machine_id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            machine_name: machineForm.machine_name.trim()
          })
        });
        const json = await res.json();

        if (json.code === 0) {
          setShowEditMachineModal(false);
          setCurrentMachine(null);
          setMachineForm({ machine_id: '', machine_name: '' });
          fetchMachines();
        } else {
          alert(json.msg || '编辑失败');
        }
      } catch (e) {
        console.error('编辑机器失败:', e);
        alert('编辑失败');
      }
    };

    // 删除机器
    const handleDeleteMachine = async () => {
      if (!currentMachine) return;

      try {
        const token = localStorage.getItem('token');
        const res = await fetch(`/api/machines/${currentMachine.machine_id}`, {
          method: 'DELETE',
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const json = await res.json();

        if (json.code === 0) {
          setShowDeleteMachineConfirm(false);
          setCurrentMachine(null);
          fetchMachines();
        } else {
          alert(json.msg || '删除失败');
        }
      } catch (e) {
        console.error('删除机器失败:', e);
        alert('删除失败');
      }
    };

    // 格式化相对时间
    const formatRelativeTime = (dateStr: string | null) => {
      if (!dateStr) return '从未';

      const now = new Date();
      const date = new Date(dateStr);
      const diffMs = now.getTime() - date.getTime();
      const diffSec = Math.floor(diffMs / 1000);

      if (diffSec < 60) return `${diffSec}秒前`;
      if (diffSec < 3600) return `${Math.floor(diffSec / 60)}分钟前`;
      if (diffSec < 86400) return `${Math.floor(diffSec / 3600)}小时前`;
      return `${Math.floor(diffSec / 86400)}天前`;
    };

    // 渲染状态圆点
    const renderStatusDot = (status: string) => {
      const colors = {
        idle: 'bg-green-500',
        running: 'bg-red-500',
        error: 'bg-yellow-500',
        offline: 'bg-gray-500'
      };
      const labels = {
        idle: '空闲',
        running: '执行中',
        error: '异常',
        offline: '离线'
      };
      return (
        <span className="flex items-center gap-2">
          <span className={`w-2.5 h-2.5 rounded-full ${colors[status as keyof typeof colors] || 'bg-gray-500'}`}></span>
          <span>{labels[status as keyof typeof labels] || status}</span>
        </span>
      );
    };

    // 机器管理 Tab 的轮询
    useEffect(() => {
      if (activeTab === 'machines') {
        fetchMachines();
        const interval = setInterval(fetchMachines, 15000); // 每15秒刷新
        return () => clearInterval(interval);
      }
    }, [activeTab]);

    // ==================== 应用绑定相关函数 ====================

    // 获取应用绑定列表
    const fetchMachineApps = async (machineId?: string) => {
      try {
        const token = localStorage.getItem('token');
        const url = machineId ? `/api/machine-apps?machine_id=${encodeURIComponent(machineId)}` : '/api/machine-apps';
        const res = await fetch(url, {
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const json = await res.json();
        if (json.code === 0 && json.data) {
          setMachineApps(json.data);
        }
      } catch (e) {
        console.error('获取应用绑定列表失败:', e);
      }
    };

    // 添加应用绑定
    const handleAddApp = async () => {
      if (!appForm.machine_id || !appForm.app_name.trim()) {
        alert('请填写完整信息');
        return;
      }

      try {
        const token = localStorage.getItem('token');
        const res = await fetch('/api/machine-apps', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            machine_id: appForm.machine_id,
            app_name: appForm.app_name.trim(),
            description: appForm.description.trim()
          })
        });
        const json = await res.json();

        if (json.code === 0) {
          setShowAddAppModal(false);
          setAppForm({ machine_id: '', app_name: '', description: '' });
          fetchMachineApps(filterMachineId);
        } else {
          alert(json.msg || '添加失败');
        }
      } catch (e) {
        console.error('添加应用绑定失败:', e);
        alert('添加失败');
      }
    };

    // 切换启用状态
    const handleToggleAppEnabled = async (app: MachineApp) => {
      try {
        const token = localStorage.getItem('token');
        const res = await fetch(`/api/machine-apps/${app.id}`, {
          method: 'PUT',
          headers: {
            'Content-Type': 'application/json',
            ...(token ? { 'Authorization': `Bearer ${token}` } : {})
          },
          body: JSON.stringify({
            enabled: !app.enabled
          })
        });
        const json = await res.json();

        if (json.code === 0) {
          fetchMachineApps(filterMachineId);
        } else {
          alert(json.msg || '更新失败');
        }
      } catch (e) {
        console.error('更新应用绑定失败:', e);
        alert('更新失败');
      }
    };

    // 删除应用绑定
    const handleDeleteApp = async () => {
      if (!currentApp) return;

      try {
        const token = localStorage.getItem('token');
        const res = await fetch(`/api/machine-apps/${currentApp.id}`, {
          method: 'DELETE',
          headers: token ? { 'Authorization': `Bearer ${token}` } : {}
        });
        const json = await res.json();

        if (json.code === 0) {
          setShowDeleteAppConfirm(false);
          setCurrentApp(null);
          fetchMachineApps(filterMachineId);
        } else {
          alert(json.msg || '删除失败');
        }
      } catch (e) {
        console.error('删除应用绑定失败:', e);
        alert('删除失败');
      }
    };

    // 应用绑定 Tab 的数据加载
    useEffect(() => {
      if (activeTab === 'apps') {
        fetchMachines(); // 获取机器列表用于下拉框
        fetchMachineApps(filterMachineId);
      }
    }, [activeTab, filterMachineId]);

    useEffect(() => {
      let cleanup: () => void;

      // 先获取短期 SSE 令牌，再建立 EventSource
      const token = localStorage.getItem('token');
      let eventSource: EventSource | null = null;

      (async () => {
        let sseToken = '';
        if (token) {
          try {
            const res = await fetch('/api/logs/sse-token', {
              headers: { 'Authorization': `Bearer ${token}` }
            });
            const json = await res.json();
            if (json.code === 0 && json.data?.token) {
              sseToken = json.data.token;
            }
          } catch (e) {
            console.error('获取 SSE token 失败:', e);
          }
        }

        if (!sseToken) {
          return;
        }

        eventSource = new EventSource(`/api/logs/stream?token=${encodeURIComponent(sseToken)}`);

        eventSource.onopen = () => {
          // SSE 连接已建立
        };

        eventSource.onmessage = (event) => {
          try {
            const data: LogEntry = JSON.parse(event.data);
            handleNewLog(data, true);
          } catch (error) {
            console.error('[SSE-DEBUG] 解析 SSE 数据失败:', error);
          }
        };

        eventSource.onerror = () => {
          // SSE 连接错误，已回退到轮询模式
        };
      })();

      // 兜底轮询（带 auth token，修复 401）
      const pollInterval = setInterval(async () => {
        try {
          const token = localStorage.getItem('token');
          const res = await fetch(`/api/logs/history?since_seq=${lastSeqRef.current}`, {
            headers: token ? { 'Authorization': `Bearer ${token}` } : {}
          });
          const json = await res.json();
          if (json.code === 0 && json.data?.logs?.length) {
            for (const entry of json.data.logs) {
              handleNewLog(entry, false);
            }
          }
        } catch (e) {}
      }, 3000);

      cleanup = () => {
        if (eventSource) eventSource.close();
        clearInterval(pollInterval);
      };

      return cleanup;
    }, []);

    const renderStatusBadge = (level: string) => {
      const safeLevel = level || '';
      if (safeLevel.includes('完成') || safeLevel.includes('成功')) {
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-green-100 text-green-700 text-xs font-medium border border-green-200">
            <CheckCircle2 size={14} />
            {safeLevel}
          </span>
        );
      }
      if (safeLevel.includes('异常') || safeLevel.includes('错误') || safeLevel.includes('失败')) {
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-red-100 text-red-700 text-xs font-medium border border-red-200">
            <AlertCircle size={14} />
            {safeLevel}
          </span>
        );
      }
      if (safeLevel === '连接中') {
        return (
          <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-slate-100 text-slate-600 text-xs font-medium border border-slate-200">
            <Activity size={14} />
            {safeLevel}
          </span>
        );
      }
      return (
        <span className="flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-100 text-blue-700 text-xs font-medium border border-blue-200">
          <Activity size={14} className="animate-pulse" />
          {safeLevel}
        </span>
      );
    };

    const taskList = Object.values(tasks);

    return (
      <div className="space-y-6">
        {/* Tab 切换导航 */}
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-1 flex gap-1">
          <button
            onClick={() => setActiveTab('logs')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-all ${
              activeTab === 'logs'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Activity size={18} />
            运行日志
          </button>
          <button
            onClick={() => setActiveTab('machines')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-all ${
              activeTab === 'machines'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Server size={18} />
            机器管理
          </button>
          <button
            onClick={() => setActiveTab('apps')}
            className={`flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg font-medium transition-all ${
              activeTab === 'apps'
                ? 'bg-blue-600 text-white shadow-sm'
                : 'text-slate-600 hover:bg-slate-50'
            }`}
          >
            <Package size={18} />
            应用绑定
          </button>
        </div>

        {/* Tab 1: 运行日志 */}
        {activeTab === 'logs' && (
          <>
            <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
          <div>
            <h2 className="text-2xl font-bold text-slate-800 flex items-center gap-2">
              RPA运行日志
              <span className="flex h-3 w-3 relative ml-2">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-400 opacity-75"></span>
                <span className="relative inline-flex rounded-full h-3 w-3 bg-green-500"></span>
              </span>
            </h2>
            <p className="text-sm text-slate-500 mt-1">输入 Task ID 订阅实时推流，完成后可手动关闭面板</p>
          </div>
          
          <div className="flex items-center gap-3 w-full md:w-auto">
            <div className="relative flex-1 md:w-64">
              <input 
                type="text" 
                value={searchInput}
                onChange={(e) => setSearchInput(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                placeholder="输入任务 ID (例如: 拼多多售后)"
                className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none transition-all"
              />
              <Search className="absolute left-3 top-2.5 text-slate-400" size={18} />
            </div>
            <button 
              onClick={handleSearch}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors whitespace-nowrap"
            >
              查询推流
            </button>
          </div>
        </div>
        
        {taskList.length === 0 ? (
          <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-20 flex flex-col items-center justify-center text-slate-400">
            <Activity size={48} className="mb-4 opacity-20 animate-pulse" />
            <p>等待接收日志推流...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
            {taskList.map(task => (
              <div key={task.taskId} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden flex flex-col h-[380px] transition-all hover:shadow-md relative group">
                <button 
                  onClick={() => handleDeleteTask(task.taskId)}
                  className="absolute top-3 right-3 p-1.5 bg-white/80 hover:bg-red-100 text-slate-400 hover:text-red-600 rounded-md opacity-0 group-hover:opacity-100 transition-all z-10"
                  title="关闭面板"
                >
                  <X size={16} />
                </button>

                <div className="p-4 border-b border-slate-100 bg-slate-50/50 flex justify-between items-start pr-12">
                  <div>
                    <h3 className="text-lg font-bold text-slate-800 mb-1 line-clamp-1" title={task.taskId}>{task.taskId}</h3>
                    <div className="flex items-center gap-3 text-xs text-slate-500">
                      <span className="flex items-center gap-1"><Monitor size={12} /> {task.machine}</span>
                      <span className="flex items-center gap-1"><Clock size={12} /> {task.logs[0]?.time || task.latestTime}</span>
                    </div>
                  </div>
                  {renderStatusBadge(task.logs[0]?.level || task.level || '')}
                </div>
                
                <div className="p-4 bg-blue-50/30 border-b border-blue-100/50">
                  <div className="text-xs font-medium text-blue-800 mb-1 flex items-center gap-1">
                    <Terminal size={12} /> 最新状态
                  </div>
                  <div className="text-sm text-slate-700 font-mono break-all line-clamp-2">
                    {(() => { const m = task.logs[0]?.msg ?? task.latestMsg; return typeof m === 'object' ? JSON.stringify(m) : String(m); })()}
                  </div>
                </div>

                <div className="flex-1 overflow-y-auto p-4 bg-slate-900 text-slate-300 font-mono text-xs space-y-2">
                  {task.logs.length === 0 ? (
                    <div className="text-slate-600 text-center mt-10">等待日志数据...</div>
                  ) : (
                    task.logs.map((log, idx) => (
                      <div key={idx} className="flex gap-3 border-b border-slate-800 pb-2 last:border-0">
                        <span className="text-slate-500 shrink-0">[{log.time}]</span>
                        <div className="flex-1 break-all">
                          <span className={
                            (log.level || '').includes('异常') || (log.level || '').includes('错误') ? 'text-red-400' :
                            (log.level || '').includes('完成') ? 'text-green-400' : 'text-blue-300'
                          }>
                            [{log.level || '未知'}]
                          </span>
                          {' '}
                          <span className="text-slate-300">
                            {typeof log.msg === 'object' ? JSON.stringify(log.msg) : String(log.msg)}
                          </span>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </div>
            ))}
          </div>
        )}
          </>
        )}

        {/* Tab 2: 机器管理 */}
        {activeTab === 'machines' && (
          <>
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-slate-800">机器管理</h2>
                <p className="text-sm text-slate-500 mt-1">管理影刀机器设备，监控运行状态</p>
              </div>
              <button
                onClick={() => {
                  setMachineForm({ machine_id: '', machine_name: '' });
                  setShowAddMachineModal(true);
                }}
                className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
              >
                <span className="text-xl">+</span>
                添加机器
              </button>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">机器码</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">机器名称</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">状态</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">最后心跳</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {machines.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-slate-400">
                        <Server size={48} className="mx-auto mb-4 opacity-20" />
                        <p>暂无机器数据</p>
                      </td>
                    </tr>
                  ) : (
                    machines.map(machine => (
                      <tr key={machine.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-slate-900">{machine.machine_id}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-900">{machine.machine_name}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                          {renderStatusDot(machine.status)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-slate-600">
                          {formatRelativeTime(machine.last_heartbeat)}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium space-x-3">
                          <button
                            onClick={() => {
                              setCurrentMachine(machine);
                              setMachineForm({ machine_id: machine.machine_id, machine_name: machine.machine_name });
                              setShowEditMachineModal(true);
                            }}
                            className="text-blue-600 hover:text-blue-800 transition-colors"
                          >
                            编辑
                          </button>
                          <button
                            onClick={() => {
                              setCurrentMachine(machine);
                              setShowDeleteMachineConfirm(true);
                            }}
                            className="text-red-600 hover:text-red-800 transition-colors"
                          >
                            删除
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* 添加机器弹窗 */}
            {showAddMachineModal && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowAddMachineModal(false)}>
                <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
                  <h3 className="text-xl font-bold text-slate-800 mb-4">添加机器</h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">机器码</label>
                      <input
                        type="text"
                        value={machineForm.machine_id}
                        onChange={(e) => setMachineForm({ ...machineForm, machine_id: e.target.value })}
                        placeholder="例如: machine_01"
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">机器名称</label>
                      <input
                        type="text"
                        value={machineForm.machine_name}
                        onChange={(e) => setMachineForm({ ...machineForm, machine_name: e.target.value })}
                        placeholder="例如: 办公室电脑"
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      />
                    </div>
                  </div>
                  <div className="flex gap-3 mt-6">
                    <button
                      onClick={() => setShowAddMachineModal(false)}
                      className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      取消
                    </button>
                    <button
                      onClick={handleAddMachine}
                      className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      确定
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 编辑机器弹窗 */}
            {showEditMachineModal && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowEditMachineModal(false)}>
                <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
                  <h3 className="text-xl font-bold text-slate-800 mb-4">编辑机器</h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">机器码</label>
                      <input
                        type="text"
                        value={machineForm.machine_id}
                        disabled
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg bg-slate-100 text-slate-500 cursor-not-allowed"
                      />
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">机器名称</label>
                      <input
                        type="text"
                        value={machineForm.machine_name}
                        onChange={(e) => setMachineForm({ ...machineForm, machine_name: e.target.value })}
                        placeholder="例如: 办公室电脑"
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      />
                    </div>
                  </div>
                  <div className="flex gap-3 mt-6">
                    <button
                      onClick={() => setShowEditMachineModal(false)}
                      className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      取消
                    </button>
                    <button
                      onClick={handleEditMachine}
                      className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      保存
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 删除确认弹窗 */}
            {showDeleteMachineConfirm && currentMachine && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowDeleteMachineConfirm(false)}>
                <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
                  <h3 className="text-xl font-bold text-slate-800 mb-4">确认删除</h3>
                  <p className="text-slate-600 mb-6">
                    确定要删除机器 <span className="font-semibold text-slate-900">{currentMachine.machine_name}</span> 吗？
                    <br />
                    <span className="text-sm text-red-600">此操作将同时删除该机器的所有应用绑定。</span>
                  </p>
                  <div className="flex gap-3">
                    <button
                      onClick={() => setShowDeleteMachineConfirm(false)}
                      className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      取消
                    </button>
                    <button
                      onClick={handleDeleteMachine}
                      className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                    >
                      确定删除
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}

        {/* Tab 3: 应用绑定 */}
        {activeTab === 'apps' && (
          <>
            <div className="flex justify-between items-center">
              <div>
                <h2 className="text-2xl font-bold text-slate-800">应用绑定</h2>
                <p className="text-sm text-slate-500 mt-1">管理机器与影刀应用的绑定关系</p>
              </div>
              <div className="flex items-center gap-3">
                <select
                  value={filterMachineId}
                  onChange={(e) => setFilterMachineId(e.target.value)}
                  className="px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                >
                  <option value="">全部机器</option>
                  {machines.map(m => (
                    <option key={m.machine_id} value={m.machine_id}>
                      {m.machine_name} ({m.machine_id})
                    </option>
                  ))}
                </select>
                <button
                  onClick={() => {
                    setAppForm({ machine_id: '', app_name: '', description: '' });
                    setShowAddAppModal(true);
                  }}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
                >
                  <span className="text-xl">+</span>
                  添加绑定
                </button>
              </div>
            </div>

            <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
              <table className="w-full">
                <thead className="bg-slate-50 border-b border-slate-200">
                  <tr>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">机器码</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">应用名</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">描述</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">启用</th>
                    <th className="px-6 py-3 text-left text-xs font-medium text-slate-500 uppercase tracking-wider">操作</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {machineApps.length === 0 ? (
                    <tr>
                      <td colSpan={5} className="px-6 py-12 text-center text-slate-400">
                        <Package size={48} className="mx-auto mb-4 opacity-20" />
                        <p>暂无应用绑定数据</p>
                      </td>
                    </tr>
                  ) : (
                    machineApps.map(app => (
                      <tr key={app.id} className="hover:bg-slate-50 transition-colors">
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-mono text-slate-900">{app.machine_id}</td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-slate-900">{app.app_name}</td>
                        <td className="px-6 py-4 text-sm text-slate-600 max-w-xs truncate">{app.description || '-'}</td>
                        <td className="px-6 py-4 whitespace-nowrap">
                          <button
                            onClick={() => handleToggleAppEnabled(app)}
                            className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                              app.enabled ? 'bg-blue-600' : 'bg-slate-300'
                            }`}
                          >
                            <span
                              className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                app.enabled ? 'translate-x-6' : 'translate-x-1'
                              }`}
                            />
                          </button>
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium">
                          <button
                            onClick={() => {
                              setCurrentApp(app);
                              setShowDeleteAppConfirm(true);
                            }}
                            className="text-red-600 hover:text-red-800 transition-colors"
                          >
                            删除
                          </button>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            {/* 添加应用绑定弹窗 */}
            {showAddAppModal && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowAddAppModal(false)}>
                <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
                  <h3 className="text-xl font-bold text-slate-800 mb-4">添加应用绑定</h3>
                  <div className="space-y-4">
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">选择机器</label>
                      <select
                        value={appForm.machine_id}
                        onChange={(e) => setAppForm({ ...appForm, machine_id: e.target.value })}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      >
                        <option value="">请选择机器</option>
                        {machines.map(m => (
                          <option key={m.machine_id} value={m.machine_id}>
                            {m.machine_name} ({m.machine_id})
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">应用名</label>
                      <input
                        type="text"
                        value={appForm.app_name}
                        onChange={(e) => setAppForm({ ...appForm, app_name: e.target.value })}
                        placeholder="例如: 拼多多售后"
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                      />
                      <p className="text-xs text-slate-500 mt-1">应用名同时也是下发任务时的 task_id</p>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-slate-700 mb-1">描述（可选）</label>
                      <textarea
                        value={appForm.description}
                        onChange={(e) => setAppForm({ ...appForm, description: e.target.value })}
                        placeholder="应用描述或备注"
                        rows={3}
                        className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none"
                      />
                    </div>
                  </div>
                  <div className="flex gap-3 mt-6">
                    <button
                      onClick={() => setShowAddAppModal(false)}
                      className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      取消
                    </button>
                    <button
                      onClick={handleAddApp}
                      className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
                    >
                      确定
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* 删除应用绑定确认弹窗 */}
            {showDeleteAppConfirm && currentApp && (
              <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50" onClick={() => setShowDeleteAppConfirm(false)}>
                <div className="bg-white rounded-xl shadow-xl p-6 w-full max-w-md" onClick={(e) => e.stopPropagation()}>
                  <h3 className="text-xl font-bold text-slate-800 mb-4">确认删除</h3>
                  <p className="text-slate-600 mb-6">
                    确定要删除应用绑定 <span className="font-semibold text-slate-900">{currentApp.app_name}</span> 吗？
                  </p>
                  <div className="flex gap-3">
                    <button
                      onClick={() => setShowDeleteAppConfirm(false)}
                      className="flex-1 px-4 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 transition-colors"
                    >
                      取消
                    </button>
                    <button
                      onClick={handleDeleteApp}
                      className="flex-1 px-4 py-2 bg-red-600 text-white rounded-lg hover:bg-red-700 transition-colors"
                    >
                      确定删除
                    </button>
                  </div>
                </div>
              </div>
            )}
          </>
        )}
      </div>
    );
  }