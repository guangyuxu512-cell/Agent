import { useState, useEffect } from 'react';
import { getTools, addTool, updateTool, deleteTool } from '../api/tools';
import { Tool } from '../types/tool';
import { Plus, Edit, Trash2, X, Search } from 'lucide-react';
import request from '../api/index';

/* ========== 后端 ↔ 前端 字段映射工具 ========== */

// 后端 tool_type → 前端 type
const mapToolTypeFromBackend = (toolType: string): Tool['type'] => {
  const map: Record<string, Tool['type']> = {
    http_api: 'api',
    python_code: 'script',
    builtin: 'builtin',
  };
  return map[toolType] || 'builtin';
};

// 前端 type → 后端 tool_type
const mapToolTypeToBackend = (type: string): string => {
  const map: Record<string, string> = {
    api: 'http_api',
    script: 'python_code',
    builtin: 'builtin',
  };
  return map[type] || type;
};

// 后端整条数据 → 前端 Tool 对象
const mapToolFromBackend = (item: any): Tool => ({
  id: String(item.id),
  name: item.name || '',
  type: mapToolTypeFromBackend(item.tool_type),
  path: typeof item.config === 'object'
    ? (item.config?.url || item.config?.path || JSON.stringify(item.config))
    : String(item.config || ''),
  description: item.description || '',
  parameters: typeof item.parameters === 'object'
    ? JSON.stringify(item.parameters, null, 2)
    : String(item.parameters || ''),
  enabled: item.status === 'active',
});

// 工具类型图标
const getToolIcon = (type: Tool['type']) => {
  const icons = {
    builtin: '💬',
    api: '🔗',
    script: '📜',
  };
  // 特殊处理：发送邮件用📧
  return icons[type] || '🔧';
};

export default function Tools() {
  const [activeTab, setActiveTab] = useState<'market' | 'register'>('market');
  const [tools, setTools] = useState<Tool[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState<Omit<Tool, 'id'>>({
    name: '',
    type: 'api',
    path: '',
    description: '',
    parameters: '',
    enabled: true
  });
  const [isSaving, setIsSaving] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  // 技能市场筛选
  const [filterType, setFilterType] = useState<'all' | Tool['type']>('all');
  const [searchQuery, setSearchQuery] = useState('');

  /* ========== 拉取列表（含字段映射） ========== */
  const fetchTools = async () => {
    const res = await getTools();
    if (res.code === 0) {
      const list: any[] = res.data.list || res.data || [];
      setTools(list.map(mapToolFromBackend));
    }
  };

  useEffect(() => {
    fetchTools();
  }, []);

  /* ========== 打开弹窗 ========== */
  const openModal = (tool?: Tool) => {
    setSaveError(null);
    if (tool) {
      setEditingId(tool.id);
      setFormData({
        name: tool.name,
        type: tool.type,
        path: tool.path,
        description: tool.description,
        parameters: tool.parameters,
        enabled: tool.enabled
      });
    } else {
      setEditingId(null);
      setFormData({
        name: '',
        type: 'api',
        path: '',
        description: '',
        parameters: '',
        enabled: true
      });
    }
    setIsModalOpen(true);
  };

  /* ========== 提交（含格式转换） ========== */
  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSaving) return;
    setIsSaving(true);
    setSaveError(null);
    try {
      let parsedParams = {};
      try {
        parsedParams = formData.parameters ? JSON.parse(formData.parameters) : {};
      } catch {
        setSaveError('参数 JSON 格式不正确');
        setIsSaving(false);
        return;
      }

      const payload = {
        name: formData.name,
        description: formData.description,
        tool_type: mapToolTypeToBackend(formData.type),
        parameters: parsedParams,
        config: { url: formData.path },
        status: formData.enabled ? 'active' : 'inactive',
      };

      let res;
      if (editingId) {
        res = await request.put(`/tools/${editingId}`, payload);
      } else {
        res = await request.post('/tools', payload);
      }

      if (res.code === 0) {
        setIsModalOpen(false);
        await fetchTools();
        setSaveSuccess(true);
        setTimeout(() => setSaveSuccess(false), 3000);
      } else {
        setSaveError(res.msg || '保存失败');
      }
    } catch (err: any) {
      setSaveError(err.message || '网络错误');
    } finally {
      setIsSaving(false);
    }
  };

  /* ========== 删除 ========== */
  const handleDelete = async (id: string) => {
    if (window.confirm('确定要删除这个工具吗？')) {
      await request.delete(`/tools/${id}`);
      fetchTools();
    }
  };

  /* ========== 切换启用状态 ========== */
  const toggleEnabled = async (tool: Tool) => {
    await request.put(`/tools/${tool.id}`, {
      status: !tool.enabled ? 'active' : 'inactive',
    });
    fetchTools();
  };

  /* ========== 技能市场：筛选和排序 ========== */
  const filteredTools = tools
    .filter(tool => {
      // 类型筛选
      if (filterType !== 'all' && tool.type !== filterType) return false;
      // 搜索筛选
      if (searchQuery && !tool.name.toLowerCase().includes(searchQuery.toLowerCase()) &&
          !tool.description.toLowerCase().includes(searchQuery.toLowerCase())) return false;
      return true;
    })
    .sort((a, b) => {
      // builtin 工具置顶
      if (a.type === 'builtin' && b.type !== 'builtin') return -1;
      if (a.type !== 'builtin' && b.type === 'builtin') return 1;
      return 0;
    });

  /* ========== 技能市场卡片 ========== */
  const renderMarketCard = (tool: Tool) => {
    const isBuiltin = tool.type === 'builtin';
    const icon = tool.name.includes('邮件') ? '📧' : getToolIcon(tool.type);

    return (
      <div
        key={tool.id}
        className="bg-white rounded-lg border border-slate-200 p-5 hover:shadow-md transition-shadow relative"
      >
        {/* 系统内置标签 */}
        {isBuiltin && (
          <div className="absolute top-3 right-3">
            <span className="px-2 py-1 text-xs font-medium bg-blue-100 text-blue-700 rounded">
              系统内置
            </span>
          </div>
        )}

        {/* 图标和标题 */}
        <div className="flex items-start gap-3 mb-3">
          <div className="text-3xl">{icon}</div>
          <div className="flex-1 min-w-0">
            <h3 className="font-semibold text-slate-800 text-lg truncate">{tool.name}</h3>
            <span className={`inline-block mt-1 px-2 py-0.5 text-xs font-medium rounded ${
              tool.type === 'builtin' ? 'bg-blue-50 text-blue-600' :
              tool.type === 'api' ? 'bg-green-50 text-green-600' :
              'bg-purple-50 text-purple-600'
            }`}>
              {tool.type === 'builtin' ? '内置' : tool.type === 'api' ? 'API' : '脚本'}
            </span>
          </div>
        </div>

        {/* 描述 */}
        <p className="text-slate-600 text-sm mb-4 line-clamp-2 min-h-[40px]">
          {tool.description}
        </p>

        {/* 底部操作栏 */}
        <div className="flex items-center justify-between pt-3 border-t border-slate-100">
          {/* 启用开关 */}
          <label className="relative inline-flex items-center cursor-pointer">
            <input
              type="checkbox"
              className="sr-only peer"
              checked={tool.enabled}
              onChange={() => toggleEnabled(tool)}
            />
            <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
            <span className="ml-2 text-sm text-slate-600">
              {tool.enabled ? '已启用' : '已禁用'}
            </span>
          </label>

          {/* 操作按钮 */}
          {!isBuiltin && (
            <div className="flex gap-2">
              <button
                onClick={() => {
                  setActiveTab('register');
                  openModal(tool);
                }}
                className="text-slate-400 hover:text-blue-600 transition-colors"
                title="编辑"
              >
                <Edit size={18} />
              </button>
              <button
                onClick={() => handleDelete(tool.id)}
                className="text-slate-400 hover:text-red-600 transition-colors"
                title="删除"
              >
                <Trash2 size={18} />
              </button>
            </div>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="space-y-6">
      {/* 顶部标题和成功提示 */}
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-bold text-slate-800">工具管理</h2>
          {saveSuccess && (
            <span className="text-green-600 text-sm bg-green-50 px-3 py-1 rounded border border-green-200 animate-fade-in">
              操作成功
            </span>
          )}
        </div>
      </div>

      {/* Tab 切换 */}
      <div className="border-b border-slate-200">
        <div className="flex gap-8">
          <button
            onClick={() => setActiveTab('market')}
            className={`pb-3 px-1 font-medium transition-colors relative ${
              activeTab === 'market'
                ? 'text-blue-600'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            技能市场
            {activeTab === 'market' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600"></div>
            )}
          </button>
          <button
            onClick={() => setActiveTab('register')}
            className={`pb-3 px-1 font-medium transition-colors relative ${
              activeTab === 'register'
                ? 'text-blue-600'
                : 'text-slate-500 hover:text-slate-700'
            }`}
          >
            工具注册
            {activeTab === 'register' && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-blue-600"></div>
            )}
          </button>
        </div>
      </div>

      {/* 技能市场 Tab */}
      {activeTab === 'market' && (
        <div className="space-y-4">
          {/* 筛选和搜索栏 */}
          <div className="flex flex-col sm:flex-row gap-4 items-start sm:items-center justify-between">
            {/* 分类筛选 */}
            <div className="flex gap-2 flex-wrap">
              <button
                onClick={() => setFilterType('all')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  filterType === 'all'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                全部
              </button>
              <button
                onClick={() => setFilterType('builtin')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  filterType === 'builtin'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                内置
              </button>
              <button
                onClick={() => setFilterType('api')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  filterType === 'api'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                API
              </button>
              <button
                onClick={() => setFilterType('script')}
                className={`px-4 py-2 rounded-lg font-medium transition-colors ${
                  filterType === 'script'
                    ? 'bg-blue-600 text-white'
                    : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                }`}
              >
                脚本
              </button>
            </div>

            {/* 搜索框 */}
            <div className="relative w-full sm:w-64">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" size={18} />
              <input
                type="text"
                placeholder="搜索工具..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="w-full pl-10 pr-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              />
            </div>
          </div>

          {/* 卡片网格 */}
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {filteredTools.map(renderMarketCard)}
          </div>

          {filteredTools.length === 0 && (
            <div className="text-center py-12 text-slate-400">
              暂无匹配的工具
            </div>
          )}
        </div>
      )}

      {/* 工具注册 Tab */}
      {activeTab === 'register' && (
        <div className="space-y-4">
          <div className="flex justify-end">
            <button
              onClick={() => openModal()}
              className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
            >
              <Plus size={18} />
              新建工具
            </button>
          </div>

          <div className="bg-white rounded-xl shadow-sm border border-slate-200 overflow-hidden">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="bg-slate-50 border-b border-slate-200">
                  <th className="p-4 font-medium text-slate-600">名称</th>
                  <th className="p-4 font-medium text-slate-600">类型</th>
                  <th className="p-4 font-medium text-slate-600">路径</th>
                  <th className="p-4 font-medium text-slate-600">描述</th>
                  <th className="p-4 font-medium text-slate-600">状态</th>
                  <th className="p-4 font-medium text-slate-600">操作</th>
                </tr>
              </thead>
              <tbody>
                {tools.map(tool => (
                  <tr key={tool.id} className="border-b border-slate-100 hover:bg-slate-50 transition-colors">
                    <td className="p-4 text-slate-800 font-medium">{tool.name}</td>
                    <td className="p-4">
                      <span className="px-2 py-1 rounded text-xs font-medium bg-slate-100 text-slate-600 uppercase">
                        {tool.type}
                      </span>
                    </td>
                    <td className="p-4 text-slate-600 text-sm font-mono truncate max-w-[200px]" title={tool.path}>{tool.path}</td>
                    <td className="p-4 text-slate-600 text-sm truncate max-w-[200px]" title={tool.description}>{tool.description}</td>
                    <td className="p-4">
                      <label className="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" className="sr-only peer" checked={tool.enabled} onChange={() => toggleEnabled(tool)} />
                        <div className="w-9 h-5 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-4 after:w-4 after:transition-all peer-checked:bg-blue-600"></div>
                      </label>
                    </td>
                    <td className="p-4 flex gap-2">
                      <button onClick={() => openModal(tool)} className="text-slate-400 hover:text-blue-600 transition-colors" title="编辑">
                        <Edit size={18} />
                      </button>
                      <button onClick={() => handleDelete(tool.id)} className="text-slate-400 hover:text-red-600 transition-colors" title="删除">
                        <Trash2 size={18} />
                      </button>
                    </td>
                  </tr>
                ))}
                {tools.length === 0 && (
                  <tr>
                    <td colSpan={6} className="p-8 text-center text-slate-400">暂无工具，请点击右上角新建</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden flex flex-col max-h-[90vh]">
            <div className="flex justify-between items-center p-6 border-b border-slate-100 shrink-0">
              <h3 className="text-xl font-bold text-slate-800">{editingId ? '编辑工具' : '新建工具'}</h3>
              <button onClick={() => setIsModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X size={24} />
              </button>
            </div>
            <div className="p-6 overflow-y-auto flex-1">
              <form id="tool-form" onSubmit={handleSubmit} className="space-y-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">名称</label>
                  <input required type="text" value={formData.name} onChange={e => setFormData({...formData, name: e.target.value})} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">执行类型</label>
                  <select value={formData.type} onChange={e => setFormData({...formData, type: e.target.value as any})} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none">
                    <option value="api">API 接口</option>
                    <option value="script">本地脚本</option>
                    <option value="builtin">内置工具</option>
                  </select>
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">路径 / URL</label>
                  <input required type="text" value={formData.path} onChange={e => setFormData({...formData, path: e.target.value})} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">描述</label>
                  <textarea required value={formData.description} onChange={e => setFormData({...formData, description: e.target.value})} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none h-20 resize-none" />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">参数 (JSON格式)</label>
                  <textarea value={formData.parameters} onChange={e => setFormData({...formData, parameters: e.target.value})} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none h-24 resize-none font-mono text-sm" placeholder='{"key": "type"}' />
                </div>
                <div className="flex items-center gap-3 pt-2">
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" className="sr-only peer" checked={formData.enabled} onChange={e => setFormData({...formData, enabled: e.target.checked})} />
                    <div className="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
                    <span className="ml-3 text-sm font-medium text-slate-700">启用该工具</span>
                  </label>
                </div>
              </form>
            </div>
            <div className="p-6 border-t border-slate-100 shrink-0 flex flex-col gap-3 bg-slate-50">
              {saveError && (
                <div className="text-red-500 text-sm bg-red-50 p-3 rounded-lg border border-red-100">
                  {saveError}
                </div>
              )}
              <div className="flex justify-end gap-3">
                <button onClick={() => setIsModalOpen(false)} className="px-4 py-2 text-slate-600 hover:bg-slate-200 rounded-lg font-medium transition-colors">
                  取消
                </button>
                <button type="submit" form="tool-form" disabled={isSaving} className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50">
                  {isSaving ? '保存中...' : '确定'}
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
