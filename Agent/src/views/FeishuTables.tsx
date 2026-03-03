import { useState, useEffect } from 'react';
import { getTables, addTable, updateTable, deleteTable } from '../api/feishu';
import { Edit, Trash2, Plus, X, CheckCircle2 } from 'lucide-react';

import { FeishuTable } from '../types/feishu';

export default function FeishuTables() {
  const [tables, setTables] = useState<FeishuTable[]>([]);
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [formData, setFormData] = useState({ name: '', appToken: '', tableId: '', description: '' });
  
  // 防抖与加载状态
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [isDeleting, setIsDeleting] = useState(false);
  const [saveSuccess, setSaveSuccess] = useState(false);

  const fetchTables = async () => {
    const res = await getTables();
    if (res.code === 0) {
      setTables([...res.data]); // clone to trigger re-render if using mock array
    }
  };

  useEffect(() => {
    fetchTables();
  }, []);

  const openModal = (table?: FeishuTable) => {
    if (table) {
      setEditingId(table.id);
      setFormData({ name: table.name, appToken: table.appToken, tableId: table.tableId, description: table.description });
    } else {
      setEditingId(null);
      setFormData({ name: '', appToken: '', tableId: '', description: '' });
    }
    setIsModalOpen(true);
  };

  const closeModal = () => {
    setIsModalOpen(false);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      let res;
      if (editingId) {
        res = await updateTable(editingId, formData);
      } else {
        res = await addTable(formData);
      }

      // ★ 检查返回码
      if (res.code !== 0) {
        alert(res.msg || '操作失败');
        return;           // 不关弹窗，让用户改名
      }

      closeModal();
      await fetchTables();
      setSaveSuccess(true);
      setTimeout(() => setSaveSuccess(false), 3000);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDeleteClick = (id: string) => {
    setDeleteConfirmId(id);
  };

  const executeDelete = async () => {
    if (!deleteConfirmId || isDeleting) return;
    setIsDeleting(true);
    try {
      await deleteTable(deleteConfirmId);
      await fetchTables();
      setDeleteConfirmId(null);
    } finally {
      setIsDeleting(false);
    }
  };

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div className="flex items-center gap-4">
          <h2 className="text-2xl font-bold text-slate-800">飞书表管理</h2>
          {saveSuccess && (
            <span className="text-green-600 text-sm bg-green-50 px-3 py-1 rounded border border-green-200 flex items-center gap-1 animate-fade-in">
              <CheckCircle2 size={14} /> 操作成功
            </span>
          )}
        </div>
        <button 
          onClick={() => openModal()}
          className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors flex items-center gap-2"
        >
          <Plus size={18} />
          添加新表格
        </button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {tables.map(table => (
          <div key={table.id} className="bg-white p-6 rounded-xl shadow-sm border border-slate-200 hover:shadow-md transition-shadow">
            <div className="flex justify-between items-start mb-4">
              <h3 className="text-lg font-bold text-slate-800">{table.name}</h3>
              <div className="flex gap-2 text-slate-400">
                <button onClick={() => openModal(table)} className="hover:text-blue-600 transition-colors" title="编辑">
                  <Edit size={18} />
                </button>
                <button onClick={() => handleDeleteClick(table.id)} className="hover:text-red-600 transition-colors" title="删除">
                  <Trash2 size={18} />
                </button>
              </div>
            </div>
            <div className="space-y-2 text-sm text-slate-600">
              <p><span className="font-medium text-slate-500">App Token:</span> {table.appToken}</p>
              <p><span className="font-medium text-slate-500">Table ID:</span> {table.tableId}</p>
              <p className="text-slate-500 mt-4 line-clamp-2">{table.description || '暂无描述'}</p>
            </div>
          </div>
        ))}
        {tables.length === 0 && (
          <div className="col-span-full bg-white p-10 rounded-xl shadow-sm border border-slate-200 text-slate-500 text-center">
            暂无表格配置，请点击右上角添加。
          </div>
        )}
      </div>

      {/* Modal */}
      {isModalOpen && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-md overflow-hidden">
            <div className="flex justify-between items-center p-6 border-b border-slate-100">
              <h3 className="text-xl font-bold text-slate-800">{editingId ? '编辑表格' : '添加新表格'}</h3>
              <button onClick={closeModal} className="text-slate-400 hover:text-slate-600">
                <X size={24} />
              </button>
            </div>
            <form onSubmit={handleSubmit} className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">表格名称</label>
                <input 
                  required
                  type="text" 
                  value={formData.name}
                  onChange={e => setFormData({...formData, name: e.target.value})}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  placeholder="例如：客户线索表"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">App Token</label>
                <input 
                  required
                  type="text" 
                  value={formData.appToken}
                  onChange={e => setFormData({...formData, appToken: e.target.value})}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  placeholder="飞书多维表格的 App Token"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Table ID</label>
                <input 
                  required
                  type="text" 
                  value={formData.tableId}
                  onChange={e => setFormData({...formData, tableId: e.target.value})}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  placeholder="数据表的 Table ID"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">描述</label>
                <textarea 
                  value={formData.description}
                  onChange={e => setFormData({...formData, description: e.target.value})}
                  className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none h-24"
                  placeholder="选填，表格用途描述"
                />
              </div>
              <div className="pt-4 flex justify-end gap-3">
                <button 
                  type="button" 
                  onClick={closeModal}
                  className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg font-medium transition-colors"
                >
                  取消
                </button>
                <button 
                  type="submit"
                  disabled={isSubmitting}
                  className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  {isSubmitting ? '提交中...' : '确定'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirmId && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-xl w-full max-w-sm overflow-hidden p-6">
            <h3 className="text-xl font-bold text-slate-800 mb-2">确认删除</h3>
            <p className="text-slate-600 mb-6">确定要删除这个表格配置吗？此操作不可恢复。</p>
            <div className="flex justify-end gap-3">
              <button 
                onClick={() => setDeleteConfirmId(null)}
                disabled={isDeleting}
                className="px-4 py-2 text-slate-600 hover:bg-slate-100 rounded-lg font-medium transition-colors disabled:opacity-50"
              >
                取消
              </button>
              <button 
                onClick={executeDelete}
                disabled={isDeleting}
                className="bg-red-600 hover:bg-red-700 text-white px-4 py-2 rounded-lg font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {isDeleting ? '删除中...' : '确认删除'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
