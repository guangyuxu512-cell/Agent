import { useState, useEffect } from 'react';
import ChangePasswordModal from '../components/ChangePasswordModal';
import { getConfig, saveConfig } from '../api/config';
import { getAgents } from '../api/agents';
import { Plus, Trash2, Save, CheckCircle2 } from 'lucide-react';

import { ConfigData } from '../types/config';
import { Agent } from '../types/agent';

// 辅助组件：配置区块
const ConfigSection = ({ title, children }: { title: string, children: React.ReactNode }) => (
  <div className="border border-slate-200 rounded-lg p-6 relative mt-4 bg-white">
    <div className="absolute -top-3 left-4 bg-white px-2 text-blue-500 font-bold text-sm">
      {title}
    </div>
    <div className="space-y-4">
      {children}
    </div>
  </div>
);

// 辅助组件：表单行
const FormRow = ({ label, children }: { label: string, children: React.ReactNode }) => (
  <div className="flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4">
    <label className="sm:w-32 text-sm text-slate-600 shrink-0">{label}</label>
    <div className="flex-1">
      {children}
    </div>
  </div>
);

export default function BasicConfig() {
  const defaultConfig: ConfigData = {
    llm: { provider: '', modelName: '', apiUrl: '', apiKey: '' },
    agent: { systemPrompt: '' },
    email: { smtpServer: '', smtpPort: '', sender: '', smtpPassword: '' },
    shadowbot: { targetEmail: '', subjectTemplate: '影刀触发-{app_name}', contentTemplate: '请执行应用：{app_name}' },
    feishu: { appId: '', appSecret: '' },
    n8n: { apiUrl: '', apiKey: '', workflows: [] },
    ragflow: { apiUrl: '', apiKey: '', kbId: '' },
    wecom: { callbackToken: '', callbackSecret: '', corpId: '', appId: '', appSecret: '' }
  };

  const [formData, setFormData] = useState<ConfigData>(defaultConfig);
  const [agents, setAgents] = useState<Agent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);

  useEffect(() => {
      setIsLoading(true);
      Promise.all([
        getConfig().catch(() => null),    // config 失败不影响 agents
        getAgents().catch(() => null)     // agents 失败不影响 config
      ])
      .then(([configRes, agentsRes]) => {
        if (configRes && configRes.code === 0 && configRes.data) {
          const data = configRes.data;
          if (data.n8n && !Array.isArray(data.n8n.workflows)) {
            data.n8n.workflows = [];
          }
          setFormData({ ...defaultConfig, ...data });
        }
        if (agentsRes && agentsRes.code === 0 && agentsRes.data) {
          setAgents(agentsRes.data.list || []);
        }
      })
      .finally(() => {
        setIsLoading(false);
      });
    }, []);

  const handleInputChange = (section: keyof ConfigData, field: string, value: any) => {
    setFormData((prev: ConfigData) => {
      return {
        ...prev,
        [section]: {
          ...prev[section],
          [field]: value
        }
      };
    });
  };

  // N8N 工作流相关操作
  const handleN8nWorkflowChange = (index: number, field: string, value: string) => {
    setFormData((prev: ConfigData) => {
      const newWorkflows = [...prev.n8n.workflows];
      newWorkflows[index] = { ...newWorkflows[index], [field]: value };
      return {
        ...prev,
        n8n: { ...prev.n8n, workflows: newWorkflows }
      };
    });
  };

  const addN8nWorkflow = () => {
    setFormData((prev: ConfigData) => {
      return {
        ...prev,
        n8n: {
          ...prev.n8n,
          workflows: [...prev.n8n.workflows, { id: Date.now().toString(), name: '', url: '', workflowId: '' }]
        }
      };
    });
  };

  const removeN8nWorkflow = (index: number) => {
    setFormData((prev: ConfigData) => {
      const newWorkflows = [...prev.n8n.workflows];
      newWorkflows.splice(index, 1);
      return {
        ...prev,
        n8n: { ...prev.n8n, workflows: newWorkflows }
      };
    });
  };

  const handleSave = async () => {
    setIsSaving(true);
    setSaveSuccess(false);
    try {
      const res = await saveConfig(formData);
      if (res.code === 0) {
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      }
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return <div className="p-8 text-slate-500">加载配置中...</div>;
  }

  return (
    <div className="max-w-4xl space-y-6 pb-12">
      <div className="flex justify-between items-center">
        <h2 className="text-2xl font-bold text-slate-800">系统配置</h2>
        <button
          onClick={() => setShowChangePassword(true)}
          className="px-4 py-2 bg-slate-600 text-white rounded-lg hover:bg-slate-700 transition-colors text-sm"
        >
          修改密码
        </button>
      </div>

      <div className="space-y-8">
        {/* 邮件配置 */}
        <ConfigSection title="邮件配置">
          <FormRow label="SMTP 服务器"><input type="text" value={formData.email.smtpServer} onChange={(e) => handleInputChange('email', 'smtpServer', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="SMTP 端口"><input type="text" value={formData.email.smtpPort} onChange={(e) => handleInputChange('email', 'smtpPort', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="发件人"><input type="text" value={formData.email.sender} onChange={(e) => handleInputChange('email', 'sender', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="SMTP 密码"><input type="password" value={formData.email.smtpPassword} onChange={(e) => handleInputChange('email', 'smtpPassword', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
        </ConfigSection>

        {/* 影刀触发 */}
        <ConfigSection title="影刀触发">
          <FormRow label="影刀目标邮箱"><input type="text" value={formData.shadowbot.targetEmail} onChange={(e) => handleInputChange('shadowbot', 'targetEmail', e.target.value)} placeholder="影刀监听的邮箱地址" className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="邮件主题模板"><input type="text" value={formData.shadowbot.subjectTemplate} onChange={(e) => handleInputChange('shadowbot', 'subjectTemplate', e.target.value)} placeholder="影刀触发-{app_name}" className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="邮件内容模板"><input type="text" value={formData.shadowbot.contentTemplate} onChange={(e) => handleInputChange('shadowbot', 'contentTemplate', e.target.value)} placeholder="请执行应用：{app_name}" className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
        </ConfigSection>

        {/* 飞书 */}
        <ConfigSection title="飞书">
          <FormRow label="应用 ID"><input type="text" value={formData.feishu.appId} onChange={(e) => handleInputChange('feishu', 'appId', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="应用密钥"><input type="password" value={formData.feishu.appSecret} onChange={(e) => handleInputChange('feishu', 'appSecret', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="事件订阅绑定智能体">
            <select 
              value={formData.feishu.feishuEventAgentId || ''} 
              onChange={(e) => handleInputChange('feishu', 'feishuEventAgentId', e.target.value)} 
              className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none bg-white"
            >
              <option value="">请选择接收飞书事件的智能体</option>
              {agents.map(agent => (
                <option key={agent.id} value={agent.id}>{agent.name}</option>
              ))}
            </select>
          </FormRow>
        </ConfigSection>

        {/* N8N */}
        <ConfigSection title="N8N">
          <FormRow label="接口地址"><input type="text" value={formData.n8n.apiUrl} onChange={(e) => handleInputChange('n8n', 'apiUrl', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="API 密钥"><input type="password" value={formData.n8n.apiKey} onChange={(e) => handleInputChange('n8n', 'apiKey', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          
          {/* 动态工作流列表 */}
          <div className="pt-4 border-t border-slate-100 mt-4">
            <div className="flex justify-between items-center mb-3">
              <label className="text-sm font-medium text-slate-700">工作流列表</label>
              <button 
                onClick={addN8nWorkflow}
                className="text-blue-500 hover:text-blue-700 text-sm flex items-center gap-1"
              >
                <Plus size={16} /> 添加工作流
              </button>
            </div>
            
            <div className="space-y-3">
              {formData.n8n.workflows.map((wf: {id: string, name: string, url: string, workflowId: string}, index: number) => (
                <div key={wf.id} className="flex flex-col sm:flex-row gap-2 items-start sm:items-center bg-slate-50 p-3 rounded border border-slate-200">
                  <input 
                    type="text" 
                    placeholder="工作流名称 (如: 飞书图生图)" 
                    value={wf.name} 
                    onChange={(e) => handleN8nWorkflowChange(index, 'name', e.target.value)}
                    className="w-full sm:w-1/4 px-3 py-1.5 text-sm border border-slate-300 rounded focus:border-blue-500 outline-none"
                  />
                  <input 
                    type="text" 
                    placeholder="Webhook URL" 
                    value={wf.url} 
                    onChange={(e) => handleN8nWorkflowChange(index, 'url', e.target.value)}
                    className="w-full sm:flex-1 px-3 py-1.5 text-sm border border-slate-300 rounded focus:border-blue-500 outline-none"
                  />
                  <input 
                    type="text" 
                    placeholder="工作流 ID (可选)" 
                    value={wf.workflowId} 
                    onChange={(e) => handleN8nWorkflowChange(index, 'workflowId', e.target.value)}
                    className="w-full sm:w-1/5 px-3 py-1.5 text-sm border border-slate-300 rounded focus:border-blue-500 outline-none"
                  />
                  <button 
                    onClick={() => removeN8nWorkflow(index)}
                    className="text-red-400 hover:text-red-600 p-1.5 shrink-0"
                    title="删除"
                  >
                    <Trash2 size={18} />
                  </button>
                </div>
              ))}
              {formData.n8n.workflows.length === 0 && (
                <div className="text-center text-slate-400 text-sm py-4 bg-slate-50 rounded border border-slate-200 border-dashed">
                  暂无工作流，请点击右上角添加
                </div>
              )}
            </div>
          </div>
        </ConfigSection>

        {/* RAGFlow 知识库 */}
        <ConfigSection title="RAGFlow 知识库">
          <FormRow label="接口地址"><input type="text" value={formData.ragflow.apiUrl} onChange={(e) => handleInputChange('ragflow', 'apiUrl', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="API 密钥"><input type="password" value={formData.ragflow.apiKey} onChange={(e) => handleInputChange('ragflow', 'apiKey', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="知识库 ID"><input type="text" value={formData.ragflow.kbId} onChange={(e) => handleInputChange('ragflow', 'kbId', e.target.value)} placeholder="从 RAGFlow 管理界面获取" className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
        </ConfigSection>

        {/* 企业微信 */}
        <ConfigSection title="企业微信">
          <FormRow label="回调 Token"><input type="text" value={formData.wecom.callbackToken} onChange={(e) => handleInputChange('wecom', 'callbackToken', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="回调密钥"><input type="password" value={formData.wecom.callbackSecret} onChange={(e) => handleInputChange('wecom', 'callbackSecret', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="企业 ID"><input type="text" value={formData.wecom.corpId} onChange={(e) => handleInputChange('wecom', 'corpId', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="应用 ID"><input type="text" value={formData.wecom.appId} onChange={(e) => handleInputChange('wecom', 'appId', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
          <FormRow label="应用密钥"><input type="password" value={formData.wecom.appSecret} onChange={(e) => handleInputChange('wecom', 'appSecret', e.target.value)} className="w-full px-3 py-2 border border-slate-300 rounded focus:border-blue-500 outline-none" /></FormRow>
        </ConfigSection>

        <div className="flex items-center gap-4">
          <button 
            onClick={handleSave}
            disabled={isSaving}
            className="bg-blue-500 hover:bg-blue-600 text-white px-8 py-2.5 rounded font-medium transition-colors disabled:opacity-50 flex items-center gap-2"
          >
            <Save size={18} />
            {isSaving ? '保存中...' : '保存配置'}
          </button>
          {saveSuccess && (
            <div className="text-green-600 flex items-center gap-1.5 text-sm font-medium animate-fade-in">
              <CheckCircle2 size={16} />
              配置保存成功
            </div>
          )}
        </div>
      </div>

      <ChangePasswordModal
        isOpen={showChangePassword}
        onClose={() => setShowChangePassword(false)}
        onSuccess={() => {
          setShowChangePassword(false);
          alert('密码修改成功');
        }}
      />
    </div>
  );
}
