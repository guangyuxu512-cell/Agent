import React, { useState, useEffect } from 'react';
import { getAgents, addAgent, updateAgent, deleteAgent, getOrchestration, saveOrchestration } from '../api/agents';
import { getTools } from '../api/tools';
import { getSchedules, addSchedule, updateSchedule, deleteSchedule } from '../api/schedule';
import { Plus, X, Edit, Trash2, Bot, Settings2, Play, Square, Network, CheckCircle2, Clock, ChevronDown, ChevronUp } from 'lucide-react';
import { Tool } from '../types/tool';

import { Agent as AgentType, OrchestrationConfig } from '../types/agent';
import { Schedule } from '../types/schedule';

export default function Agent() {
  const [activeTab, setActiveTab] = useState<'agents' | 'orchestration' | 'schedules'>('agents');
  const [agents, setAgents] = useState<AgentType[]>([]);
  const [orchestration, setOrchestration] = useState<OrchestrationConfig | null>(null);
  const [availableTools, setAvailableTools] = useState<Tool[]>([]);
  const [schedules, setSchedules] = useState<Schedule[]>([]);
  
  // 状态提示
  const [isSavingOrch, setIsSavingOrch] = useState(false);
  const [orchSuccess, setOrchSuccess] = useState(false);
  const [saveAgentSuccess, setSaveAgentSuccess] = useState(false);
  
  // Agent Modal 状态
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);

  // Schedule Modal 状态
  const [isScheduleModalOpen, setIsScheduleModalOpen] = useState(false);
  const [editingScheduleId, setEditingScheduleId] = useState<string | null>(null);
  const [expandedScheduleId, setExpandedScheduleId] = useState<string | null>(null);
  const [scheduleFormData, setScheduleFormData] = useState<Omit<Schedule, 'id' | 'lastRunTime' | 'lastRunStatus' | 'lastRunDuration'>>({
    name: '',
    agentId: '',
    triggerType: 'cron',
    cronExpression: '0 8 * * *',
    intervalValue: 1,
    intervalUnit: 'hours',
    executeTime: '',
    inputMessage: '',
    enabled: true
  });
  
  // Agent 表单状态
  const [formData, setFormData] = useState({
    name: '',
    role: '',
    prompt: '',
    llmProvider: 'OpenAI',
    llmModel: 'GPT-4o',
    llmApiUrl: '',
    llmApiKey: '',
    temperature: 0.7,
    tools: [] as string[],
    maxIterations: 10,
    timeout: 60,
    requireApproval: false
  });

  useEffect(() => {
    fetchData();
  }, []);



  const fetchData = async () => {
    // Agent 列表（真实 API）
    try {
      const agentsRes = await getAgents();
      if (agentsRes.code === 0) setAgents(agentsRes.data?.list || []);
    } catch (e) {
      console.error('获取Agent列表失败:', e);
    }

    // 编排配置（API 暂未实现，会走 catch）
    try {
      const orchRes = await getOrchestration();
      if (orchRes.code === 0) {
        setOrchestration(orchRes.data);
      } else {
        setOrchestration({ mode: 'Supervisor', entryAgent: '', routingRules: '', parallelGroups: '', globalState: [] });
      }
    } catch (e) {
      setOrchestration({ mode: 'Supervisor', entryAgent: '', routingRules: '', parallelGroups: '', globalState: [] });
    }

    // 工具列表（API 暂未实现，忽略错误）
    try {
      const toolsRes = await getTools();
      if (toolsRes.code === 0) {
        const list = toolsRes.data?.list || [];
        setAvailableTools(list.map((item: any) => ({
          id: String(item.id),
          name: item.name || '',
          enabled: item.status === 'active',   // ← 关键：映射 status → enabled
        })));
      }
    } catch (e) { /* 忽略 */ }

    // 定时任务（API 暂未实现，忽略错误）
    try {
      const schedulesRes = await getSchedules();
      if (schedulesRes.code === 0) setSchedules(schedulesRes.data?.list || []);
    } catch (e) { /* Step 后续再实现 */ }
  };
  const openModal = (agent?: AgentType) => {
    if (agent) {
      setEditingId(agent.id);
      setFormData({
        name: agent.name || '',
        role: agent.role || '',
        prompt: agent.prompt || '',
        llmProvider: agent.llmProvider || 'OpenAI',
        llmModel: agent.llmModel || 'GPT-4o',
        llmApiUrl: agent.llmApiUrl || '',
        llmApiKey: agent.llmApiKey || '',
        temperature: agent.temperature ?? 0.7,
        tools: agent.tools || [],
        maxIterations: agent.maxIterations ?? 10,
        timeout: agent.timeout ?? 60,
        requireApproval: agent.requireApproval ?? false
      });
    } else {
      setEditingId(null);
      setFormData({
        name: '', role: '', prompt: '', 
        llmProvider: 'OpenAI', llmModel: 'GPT-4o', llmApiUrl: '', llmApiKey: '',
        temperature: 0.7, tools: [], maxIterations: 10, timeout: 60, requireApproval: false
      });
    }
    setIsModalOpen(true);
  };

  const handleToolToggle = (tool: string) => {
    setFormData(prev => ({
      ...prev,
      tools: prev.tools.includes(tool) 
        ? prev.tools.filter(t => t !== tool)
        : [...prev.tools, tool]
    }));
  };



  const handleSaveAgent = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      let res;
      if (editingId) {
        res = await updateAgent(String(editingId), formData);
      } else {
        res = await addAgent(formData);
      }
      if (res.code === 0) {
        await fetchData();
        setIsModalOpen(false);
        setSaveAgentSuccess(true);
        setTimeout(() => setSaveAgentSuccess(false), 3000);
      } else {
        alert(res.msg || '保存失败');
      }
    } catch (err) {
      console.error('保存Agent失败:', err);
      alert('保存失败，请检查网络连接');
    }
  };

  const handleSaveOrchestration = async () => {
    setIsSavingOrch(true);
    setOrchSuccess(false);
    try {
      const res = await saveOrchestration(orchestration);
      if (res.code === 0) {
        setOrchSuccess(true);
        setTimeout(() => setOrchSuccess(false), 3000);
      }
    } finally {
      setIsSavingOrch(false);
    }
  };



  const handleDeleteAgent = async (id: string) => {
    if (window.confirm('确定删除该智能体吗？')) {
      try {
        const res = await deleteAgent(String(id));
        if (res.code === 0) {
          await fetchData();
        } else {
          alert(res.msg || '删除失败');
        }
      } catch (err) {
        console.error('删除Agent失败:', err);
        alert('删除失败，请检查网络连接');
      }
    }
  };

  const openScheduleModal = (schedule?: Schedule) => {
    if (schedule) {
      setEditingScheduleId(schedule.id);
      setScheduleFormData({
        name: schedule.name,
        agentId: schedule.agentId,
        triggerType: schedule.triggerType,
        cronExpression: schedule.cronExpression || '0 8 * * *',
        intervalValue: schedule.intervalValue || 1,
        intervalUnit: schedule.intervalUnit || 'hours',
        executeTime: schedule.executeTime || '',
        inputMessage: schedule.inputMessage,
        enabled: schedule.enabled
      });
    } else {
      setEditingScheduleId(null);
      setScheduleFormData({
        name: '',
        agentId: agents.length > 0 ? agents[0].id : '',
        triggerType: 'cron',
        cronExpression: '0 8 * * *',
        intervalValue: 1,
        intervalUnit: 'hours',
        executeTime: '',
        inputMessage: '',
        enabled: true
      });
    }
    setIsScheduleModalOpen(true);
  };

  const handleSaveSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (editingScheduleId) {
      await updateSchedule(editingScheduleId, scheduleFormData);
    } else {
      await addSchedule(scheduleFormData);
    }
    setIsScheduleModalOpen(false);
    fetchData();
  };

  const handleDeleteSchedule = async (id: string) => {
    if (window.confirm('确定要删除该定时任务吗？')) {
      await deleteSchedule(id);
      fetchData();
    }
  };

  const handleToggleSchedule = async (id: string, enabled: boolean) => {
    await updateSchedule(id, { enabled });
    fetchData();
  };

  return (
    <div className="space-y-6 pb-12">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-bold text-slate-800">智能体管理</h2>
          {saveAgentSuccess && (
            <span className="text-green-600 text-sm bg-green-50 px-3 py-1 rounded border border-green-200 flex items-center gap-1 animate-fade-in">
              <CheckCircle2 size={14} /> 保存成功
            </span>
          )}
        </div>
        {activeTab === 'agents' && (
          <button 
            onClick={() => openModal()}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
          >
            <Plus size={18} />
            新建智能体
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex gap-4 border-b border-slate-200">
        <button 
          onClick={() => setActiveTab('agents')}
          className={`pb-3 px-2 font-medium text-sm transition-colors relative ${activeTab === 'agents' ? 'text-blue-600' : 'text-slate-500 hover:text-slate-800'}`}
        >
          <div className="flex items-center gap-2"><Bot size={16} /> 智能体列表</div>
          {activeTab === 'agents' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-t-full" />}
        </button>
        <button 
          onClick={() => setActiveTab('orchestration')}
          className={`pb-3 px-2 font-medium text-sm transition-colors relative ${activeTab === 'orchestration' ? 'text-blue-600' : 'text-slate-500 hover:text-slate-800'}`}
        >
          <div className="flex items-center gap-2"><Network size={16} /> 编排层配置</div>
          {activeTab === 'orchestration' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-t-full" />}
        </button>
        <button 
          onClick={() => setActiveTab('schedules')}
          className={`pb-3 px-2 font-medium text-sm transition-colors relative ${activeTab === 'schedules' ? 'text-blue-600' : 'text-slate-500 hover:text-slate-800'}`}
        >
          <div className="flex items-center gap-2"><Clock size={16} /> 定时任务</div>
          {activeTab === 'schedules' && <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600 rounded-t-full" />}
        </button>
      </div>
      
      {/* 智能体列表 Tab */}
      {activeTab === 'agents' && (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-6">
          {agents.map(agent => (
            <div key={agent.id} className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden hover:shadow-md transition-all flex flex-col">
              <div className="p-5 border-b border-slate-100 flex justify-between items-start bg-slate-50/50">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-lg bg-blue-100 text-blue-600 flex items-center justify-center shrink-0">
                    <Bot size={20} />
                  </div>
                  <div>
                    <h3 className="font-bold text-slate-800">{agent.name}</h3>
                    <p className="text-xs text-slate-500 mt-0.5">{agent.llmModel}</p>
                  </div>
                </div>
                <span className="px-2 py-1 rounded text-xs font-medium flex items-center gap-1 bg-green-100 text-green-700">
								  <CheckCircle2 size={12} />
								  就绪
								</span>
              </div>
              <div className="p-5 flex-1 space-y-4">
                <div>
                  <div className="text-xs font-medium text-slate-400 mb-1">角色描述</div>
                  <div className="text-sm text-slate-700 line-clamp-2">{agent.role || '暂无描述'}</div>
                </div>
                <div className="flex gap-4">
                  <div>
                    <div className="text-xs font-medium text-slate-400 mb-1">工具数</div>
                    <div className="text-sm text-slate-700 font-medium">{agent.tools?.length || 0}</div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-400 mb-1">温度</div>
                    <div className="text-sm text-slate-700 font-medium">{agent.temperature}</div>
                  </div>
                  <div>
                    <div className="text-xs font-medium text-slate-400 mb-1">人工审批</div>
                    <div className="text-sm text-slate-700 font-medium">{agent.requireApproval ? '是' : '否'}</div>
                  </div>
                </div>
              </div>
              <div className="p-3 border-t border-slate-100 bg-slate-50 flex justify-end gap-2">
                <button onClick={() => openModal(agent)} className="p-2 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors" title="配置">
                  <Settings2 size={18} />
                </button>
                <button onClick={() => handleDeleteAgent(agent.id)} className="p-2 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors" title="删除">
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
          ))}
          {agents.length === 0 && (
            <div className="col-span-full py-20 text-center text-slate-400 bg-white rounded-xl border border-slate-200 border-dashed">
              暂无智能体，请点击右上角新建
            </div>
          )}
        </div>
      )}

      {/* 编排层配置 Tab */}
      {activeTab === 'orchestration' && orchestration && (
        <div className="bg-white rounded-xl shadow-sm border border-slate-200 p-8 max-w-3xl">
          <div className="space-y-6">
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">编排模式</label>
              <div className="flex gap-4">
                {['Supervisor', 'Network', 'Hierarchical'].map(mode => (
                  <label key={mode} className="flex items-center gap-2 cursor-pointer">
                    <input type="radio" name="mode" value={mode} checked={orchestration.mode === mode} onChange={() => setOrchestration({...orchestration, mode})} className="text-blue-600 focus:ring-blue-500" />
                    <span className="text-sm text-slate-700">{mode}</span>
                  </label>
                ))}
              </div>
              <p className="text-xs text-slate-400 mt-1">Supervisor(主管调度) / Network(平等协作) / Hierarchical(层级)</p>
            </div>
            
            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">入口 Agent</label>
              <select 
                value={orchestration.entryAgent} 
                onChange={e => setOrchestration({...orchestration, entryAgent: e.target.value})}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none disabled:bg-slate-100 disabled:text-slate-400"
                disabled={agents.length === 0}
              >
                {agents.length === 0 ? (
                  <option value="">请先创建智能体</option>
                ) : (
                  agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)
                )}
              </select>
              <p className="text-xs text-slate-400 mt-1">第一个接收输入的 Agent</p>
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">路由规则</label>
              <textarea 
                value={orchestration.routingRules}
                onChange={e => setOrchestration({...orchestration, routingRules: e.target.value})}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none h-24 resize-none disabled:bg-slate-100 disabled:text-slate-400"
                placeholder={agents.length === 0 ? "请先创建智能体" : "定义 Agent 之间的流转条件..."}
                disabled={agents.length === 0}
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">并行组</label>
              <input 
                type="text" 
                value={orchestration.parallelGroups}
                onChange={e => setOrchestration({...orchestration, parallelGroups: e.target.value})}
                className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                placeholder="哪些 Agent 可以同时运行"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-slate-700 mb-2">全局状态字段 (State)</label>
              <div className="space-y-2">
                {orchestration.globalState.map((state: {key: string, desc: string}, idx: number) => (
                  <div key={idx} className="flex gap-2">
                    <input type="text" value={state.key} readOnly className="w-1/3 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded text-sm" />
                    <input type="text" value={state.desc} readOnly className="flex-1 px-3 py-1.5 bg-slate-50 border border-slate-200 rounded text-sm" />
                  </div>
                ))}
              </div>
              <p className="text-xs text-slate-400 mt-2">定义工作流中共享的数据结构</p>
            </div>

            <div className="pt-4 border-t border-slate-100 flex items-center gap-4">
              <button 
                onClick={handleSaveOrchestration}
                disabled={isSavingOrch}
                className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                {isSavingOrch ? '保存中...' : '保存编排配置'}
              </button>
              {orchSuccess && (
                <span className="text-green-600 text-sm flex items-center gap-1 animate-fade-in">
                  <CheckCircle2 size={16} /> 配置已保存
                </span>
              )}
            </div>
          </div>
        </div>
      )}

      {/* 定时任务 Tab */}
      {activeTab === 'schedules' && (
        <div className="space-y-6">
          <div className="flex justify-between items-center">
            <h2 className="text-xl font-bold text-slate-800">定时任务列表</h2>
            <button 
              onClick={() => openScheduleModal()}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2 text-sm"
            >
              <Plus size={16} />
              新建任务
            </button>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200 text-sm text-slate-500">
                  <th className="p-4 font-medium">任务名称</th>
                  <th className="p-4 font-medium">关联 Agent</th>
                  <th className="p-4 font-medium">触发方式</th>
                  <th className="p-4 font-medium">状态</th>
                  <th className="p-4 font-medium">上次执行时间</th>
                  <th className="p-4 font-medium text-right">操作</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {schedules.map(schedule => (
                  <React.Fragment key={schedule.id}>
                    <tr className="hover:bg-slate-50/50 transition-colors group">
                      <td className="p-4">
                        <div className="font-medium text-slate-800">{schedule.name}</div>
                        <div className="text-xs text-slate-500 mt-1 truncate max-w-[200px]">{schedule.inputMessage}</div>
                      </td>
                      <td className="p-4">
                        <span className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-blue-50 text-blue-700 text-xs font-medium border border-blue-100">
                          <Bot size={12} />
                          {agents.find(a => a.id === schedule.agentId)?.name || '未知 Agent'}
                        </span>
                      </td>
                      <td className="p-4">
                        <div className="text-sm text-slate-700">
                          {schedule.triggerType === 'cron' && `Cron: ${schedule.cronExpression}`}
                          {schedule.triggerType === 'interval' && `每 ${schedule.intervalValue} ${schedule.intervalUnit === 'minutes' ? '分钟' : schedule.intervalUnit === 'hours' ? '小时' : '天'}`}
                          {schedule.triggerType === 'once' && `一次性: ${schedule.executeTime}`}
                        </div>
                      </td>
                      <td className="p-4">
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input 
                            type="checkbox" 
                            className="sr-only peer" 
                            checked={schedule.enabled}
                            onChange={(e) => handleToggleSchedule(schedule.id, e.target.checked)}
                          />
                          <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                        </label>
                      </td>
                      <td className="p-4">
                        <div className="text-sm text-slate-600">{schedule.lastRunTime || '-'}</div>
                        {schedule.lastRunStatus && (
                          <div className={`text-xs mt-1 ${schedule.lastRunStatus === 'success' ? 'text-green-600' : 'text-red-600'}`}>
                            {schedule.lastRunStatus === 'success' ? '成功' : '失败'} {schedule.lastRunDuration && `(${schedule.lastRunDuration})`}
                          </div>
                        )}
                      </td>
                      <td className="p-4 text-right">
                        <div className="flex items-center justify-end gap-2">
                          <button 
                            onClick={() => setExpandedScheduleId(expandedScheduleId === schedule.id ? null : schedule.id)}
                            className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors" 
                            title="查看记录"
                          >
                            {expandedScheduleId === schedule.id ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                          </button>
                          <button 
                            onClick={() => openScheduleModal(schedule)} 
                            className="p-1.5 text-slate-400 hover:text-blue-600 hover:bg-blue-50 rounded transition-colors" 
                            title="编辑"
                          >
                            <Edit size={16} />
                          </button>
                          <button 
                            onClick={() => handleDeleteSchedule(schedule.id)} 
                            className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded transition-colors" 
                            title="删除"
                          >
                            <Trash2 size={16} />
                          </button>
                        </div>
                      </td>
                    </tr>
                    {expandedScheduleId === schedule.id && (
                      <tr>
                        <td colSpan={6} className="p-0 bg-slate-50 border-b border-slate-200">
                          <div className="p-4 text-sm text-slate-600">
                            <h4 className="font-medium text-slate-800 mb-2">最近执行记录</h4>
                            {schedule.lastRunTime ? (
                              <div className="flex items-center gap-4">
                                <span>时间: {schedule.lastRunTime}</span>
                                <span>状态: <span className={schedule.lastRunStatus === 'success' ? 'text-green-600' : 'text-red-600'}>{schedule.lastRunStatus === 'success' ? '成功' : '失败'}</span></span>
                                <span>耗时: {schedule.lastRunDuration || '-'}</span>
                              </div>
                            ) : (
                              <div className="text-slate-400">暂无执行记录</div>
                            )}
                          </div>
                        </td>
                      </tr>
                    )}
                  </React.Fragment>
                ))}
                {schedules.length === 0 && (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-slate-400">
                      暂无定时任务
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Agent 配置 Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] flex flex-col">
            <div className="flex justify-between items-center p-6 border-b border-slate-100 shrink-0">
              <h3 className="text-xl font-bold text-slate-800 flex items-center gap-2">
                <Bot className="text-blue-600" />
                {editingId ? '编辑智能体' : '新建智能体'}
              </h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X size={24} />
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto flex-1">
              <form id="agent-form" onSubmit={handleSaveAgent} className="space-y-5">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-5">
                  <div className="col-span-full md:col-span-1">
                    <label className="block text-sm font-medium text-slate-700 mb-1">Agent 名称</label>
                    <input required type="text" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="唯一标识" />
                  </div>
                  <div className="col-span-full md:col-span-1">
                    <label className="block text-sm font-medium text-slate-700 mb-1">角色描述</label>
                    <input required type="text" value={formData.role} onChange={e => setFormData({...formData, role: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="简要说明职责" />
                  </div>

                  <div className="col-span-full">
                    <div className="bg-slate-50 p-4 rounded-lg border border-slate-200 space-y-4">
                      <h4 className="font-medium text-slate-700 text-sm">大模型配置</h4>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">提供商</label>
                          <select value={formData.llmProvider} onChange={e => setFormData({...formData, llmProvider: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm">
                            <option value="OpenAI">OpenAI</option>
                            <option value="Anthropic">Anthropic</option>
                            <option value="Google">Google</option>
                          </select>
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">模型名称</label>
                          <input type="text" value={formData.llmModel} onChange={e => setFormData({...formData, llmModel: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="如 GPT-4o" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">接口地址</label>
                          <input type="text" value={formData.llmApiUrl} onChange={e => setFormData({...formData, llmApiUrl: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="https://api.openai.com/v1" />
                        </div>
                        <div>
                          <label className="block text-xs font-medium text-slate-600 mb-1">API 密钥</label>
                          <input type="password" value={formData.llmApiKey} onChange={e => setFormData({...formData, llmApiKey: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none text-sm" placeholder="sk-..." />
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="col-span-full">
                    <label className="block text-sm font-medium text-slate-700 mb-1">System Prompt</label>
                    <textarea required value={formData.prompt} onChange={e => setFormData({...formData, prompt: e.target.value})} className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none h-32 resize-y font-mono text-sm" placeholder="核心指令，支持变量模板..." />
                  </div>

                  <div className="col-span-full md:col-span-1">
                    <label className="block text-sm font-medium text-slate-700 mb-1">
                      Temperature: <span className="text-blue-600 font-bold">{formData.temperature}</span>
                    </label>
                    <input type="range" min="0" max="2" step="0.1" value={formData.temperature} onChange={e => setFormData({...formData, temperature: parseFloat(e.target.value)})} className="w-full mt-2" />
                    <div className="flex justify-between text-xs text-slate-400 mt-1">
                      <span>确定性</span>
                      <span>创造性</span>
                    </div>
                  </div>

                  <div className="col-span-full md:col-span-1">
                    <label className="block text-sm font-medium text-slate-700 mb-2">工具列表</label>
                    <div className="flex flex-wrap gap-2">
                      {availableTools.filter(t => t.enabled).map(tool => (
                        <label key={tool.id} className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full border text-sm cursor-pointer transition-colors ${formData.tools.includes(tool.name) ? 'bg-blue-50 border-blue-200 text-blue-700' : 'bg-white border-slate-200 text-slate-600 hover:bg-slate-50'}`}>
                          <input type="checkbox" className="hidden" checked={formData.tools.includes(tool.name)} onChange={() => handleToolToggle(tool.name)} />
                          {tool.name}
                        </label>
                      ))}
                      {availableTools.filter(t => t.enabled).length === 0 && (
                        <span className="text-sm text-slate-400">暂无可用工具，请先在工具管理中添加</span>
                      )}
                    </div>
                  </div>

                  <div className="col-span-full md:col-span-1">
                    <label className="block text-sm font-medium text-slate-700 mb-1">最大迭代次数</label>
                    <input type="number" min="1" value={formData.maxIterations} onChange={e => setFormData({...formData, maxIterations: parseInt(e.target.value)})} className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="防止无限循环" />
                  </div>

                  <div className="col-span-full md:col-span-1">
                    <label className="block text-sm font-medium text-slate-700 mb-1">超时时间 (秒)</label>
                    <input type="number" min="1" value={formData.timeout} onChange={e => setFormData({...formData, timeout: parseInt(e.target.value)})} className="w-full px-3 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" placeholder="单次执行上限" />
                  </div>

                  <div className="col-span-full flex items-center gap-3 pt-2">
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input type="checkbox" className="sr-only peer" checked={formData.requireApproval} onChange={e => setFormData({...formData, requireApproval: e.target.checked})} />
                      <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                      <span className="ml-3 text-sm font-medium text-slate-700">需要人工审批 (执行前暂停确认)</span>
                    </label>
                  </div>
                </div>
              </form>
            </div>
            
            <div className="p-6 border-t border-slate-100 shrink-0 flex justify-end gap-3 bg-slate-50 rounded-b-xl">
              <button onClick={() => setIsModalOpen(false)} className="px-6 py-2 text-slate-600 hover:bg-slate-200 rounded-lg font-medium transition-colors">
                取消
              </button>
              <button type="submit" form="agent-form" className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2 rounded-lg font-medium transition-colors">
                保存配置
              </button>
            </div>
          </div>
        </div>
      )}
      {/* Schedule Modal */}
      {isScheduleModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-2xl max-h-[90vh] overflow-y-auto">
            <div className="flex justify-between items-center p-6 border-b border-slate-100 sticky top-0 bg-white z-10">
              <h2 className="text-xl font-bold text-slate-800">
                {editingScheduleId ? '编辑定时任务' : '新建定时任务'}
              </h2>
              <button onClick={() => setIsScheduleModalOpen(false)} className="text-slate-400 hover:text-slate-600 p-1">
                <X size={24} />
              </button>
            </div>
            
            <form onSubmit={handleSaveSchedule} className="p-6 space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="col-span-full">
                  <label className="block text-sm font-medium text-slate-700 mb-2">任务名称 *</label>
                  <input 
                    type="text" 
                    required
                    value={scheduleFormData.name}
                    onChange={e => setScheduleFormData({...scheduleFormData, name: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    placeholder="例如: 每日早报生成"
                  />
                </div>
                
                <div className="col-span-full">
                  <label className="block text-sm font-medium text-slate-700 mb-2">关联智能体 *</label>
                  <select 
                    value={scheduleFormData.agentId}
                    onChange={e => setScheduleFormData({...scheduleFormData, agentId: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    required
                  >
                    {agents.length === 0 && <option value="">请先创建智能体</option>}
                    {agents.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}
                  </select>
                </div>

                <div className="col-span-full">
                  <label className="block text-sm font-medium text-slate-700 mb-2">触发方式 *</label>
                  <div className="flex gap-4">
                    {['cron', 'interval', 'once'].map(type => (
                      <label key={type} className="flex items-center gap-2 cursor-pointer">
                        <input 
                          type="radio" 
                          name="triggerType" 
                          value={type} 
                          checked={scheduleFormData.triggerType === type} 
                          onChange={() => setScheduleFormData({...scheduleFormData, triggerType: type as any})} 
                          className="text-blue-600 focus:ring-blue-500" 
                        />
                        <span className="text-sm text-slate-700">
                          {type === 'cron' ? 'Cron 表达式' : type === 'interval' ? '固定间隔' : '一次性'}
                        </span>
                      </label>
                    ))}
                  </div>
                </div>

                {scheduleFormData.triggerType === 'cron' && (
                  <div className="col-span-full">
                    <label className="block text-sm font-medium text-slate-700 mb-2">Cron 表达式 *</label>
                    <input 
                      type="text" 
                      required
                      value={scheduleFormData.cronExpression}
                      onChange={e => setScheduleFormData({...scheduleFormData, cronExpression: e.target.value})}
                      className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none font-mono text-sm"
                      placeholder="0 8 * * *"
                    />
                    <p className="text-xs text-slate-400 mt-1">格式: 分 时 日 月 周 (例如: 0 8 * * * 表示每天早上8点)</p>
                  </div>
                )}

                {scheduleFormData.triggerType === 'interval' && (
                  <div className="col-span-full flex gap-4">
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-slate-700 mb-2">间隔数值 *</label>
                      <input 
                        type="number" 
                        min="1"
                        required
                        value={scheduleFormData.intervalValue}
                        onChange={e => setScheduleFormData({...scheduleFormData, intervalValue: Number(e.target.value)})}
                        className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm font-medium text-slate-700 mb-2">时间单位 *</label>
                      <select 
                        value={scheduleFormData.intervalUnit}
                        onChange={e => setScheduleFormData({...scheduleFormData, intervalUnit: e.target.value as any})}
                        className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                      >
                        <option value="minutes">分钟</option>
                        <option value="hours">小时</option>
                        <option value="days">天</option>
                      </select>
                    </div>
                  </div>
                )}

                {scheduleFormData.triggerType === 'once' && (
                  <div className="col-span-full">
                    <label className="block text-sm font-medium text-slate-700 mb-2">执行时间 *</label>
                    <input 
                      type="datetime-local" 
                      required
                      value={scheduleFormData.executeTime}
                      onChange={e => setScheduleFormData({...scheduleFormData, executeTime: e.target.value})}
                      className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
                    />
                  </div>
                )}

                <div className="col-span-full">
                  <label className="block text-sm font-medium text-slate-700 mb-2">输入消息 *</label>
                  <textarea 
                    required
                    value={scheduleFormData.inputMessage}
                    onChange={e => setScheduleFormData({...scheduleFormData, inputMessage: e.target.value})}
                    className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none h-24 resize-none"
                    placeholder="作为 Agent 启动时的初始输入消息..."
                  />
                </div>
                
                <div className="col-span-full flex items-center gap-2">
                  <input 
                    type="checkbox" 
                    id="scheduleEnabled"
                    checked={scheduleFormData.enabled}
                    onChange={e => setScheduleFormData({...scheduleFormData, enabled: e.target.checked})}
                    className="w-4 h-4 text-blue-600 rounded border-slate-300 focus:ring-blue-500"
                  />
                  <label htmlFor="scheduleEnabled" className="text-sm font-medium text-slate-700">启用该任务</label>
                </div>
              </div>

              <div className="pt-6 border-t border-slate-100 flex justify-end gap-3">
                <button type="button" onClick={() => setIsScheduleModalOpen(false)} className="px-6 py-2 border border-slate-300 text-slate-700 rounded-lg hover:bg-slate-50 font-medium transition-colors">
                  取消
                </button>
                <button type="submit" className="px-6 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 font-medium transition-colors" disabled={agents.length === 0}>
                  保存
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}