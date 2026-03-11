import { useEffect, useMemo, useState } from 'react';
import { Cpu, RefreshCw, Server } from 'lucide-react';
import { deleteWorker, getWorkers } from '../api/workers';
import { Worker, WorkerStatus } from '../types/worker';

const statusOptions: Array<{ value: '' | WorkerStatus; label: string }> = [
  { value: '', label: '全部状态' },
  { value: 'idle', label: '空闲' },
  { value: 'running', label: '运行中' },
  { value: 'error', label: '异常' },
  { value: 'offline', label: '离线' },
];

const statusStyles: Record<WorkerStatus, string> = {
  idle: 'bg-emerald-100 text-emerald-700',
  running: 'bg-amber-100 text-amber-700',
  error: 'bg-rose-100 text-rose-700',
  offline: 'bg-slate-200 text-slate-700',
};

const statusText: Record<WorkerStatus, string> = {
  idle: '空闲',
  running: '运行中',
  error: '异常',
  offline: '离线',
};

function formatTime(value: string | null) {
  if (!value) return '暂无心跳';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString();
}

export default function Workers() {
  const [workers, setWorkers] = useState<Worker[]>([]);
  const [status, setStatus] = useState<'' | WorkerStatus>('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);
  const [currentWorker, setCurrentWorker] = useState<Worker | null>(null);
  const [deleting, setDeleting] = useState(false);

  const getErrorMessage = (err: unknown, fallback: string) => {
    if (err instanceof Error && err.message) {
      return err.message;
    }
    return fallback;
  };

  const fetchWorkers = async () => {
    setLoading(true);
    setError('');
    try {
      const data = await getWorkers(status || undefined);
      setWorkers(data.list || []);
    } catch (err) {
      setError(getErrorMessage(err, '获取 Worker 列表失败'));
    } finally {
      setLoading(false);
    }
  };

  const handleDeleteWorker = async () => {
    if (!currentWorker) return;

    setDeleting(true);
    setError('');
    try {
      await deleteWorker(currentWorker.machine_id);
      setShowDeleteConfirm(false);
      setCurrentWorker(null);
      await fetchWorkers();
    } catch (err) {
      setError(getErrorMessage(err, '删除 Worker 失败'));
    } finally {
      setDeleting(false);
    }
  };

  useEffect(() => {
    fetchWorkers();
    const timer = setInterval(fetchWorkers, 10000);
    return () => clearInterval(timer);
  }, [status]);

  const summary = useMemo(() => {
    return workers.reduce(
      (acc, item) => {
        acc.total += 1;
        acc[item.status] += 1;
        return acc;
      },
      { total: 0, idle: 0, running: 0, error: 0, offline: 0 }
    );
  }, [workers]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">工人列表</h2>
          <p className="mt-1 text-sm text-slate-500">展示外部 Worker 脚本注册的机器、队列和最近一次心跳。</p>
        </div>
        <button
          onClick={fetchWorkers}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm hover:bg-slate-50"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-5">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-sm text-slate-500">机器总数</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">{summary.total}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-sm text-slate-500">空闲</div>
          <div className="mt-2 text-2xl font-semibold text-emerald-600">{summary.idle}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-sm text-slate-500">运行中</div>
          <div className="mt-2 text-2xl font-semibold text-amber-600">{summary.running}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-sm text-slate-500">异常</div>
          <div className="mt-2 text-2xl font-semibold text-rose-600">{summary.error}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-sm text-slate-500">离线</div>
          <div className="mt-2 text-2xl font-semibold text-slate-600">{summary.offline}</div>
        </div>
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
        <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-2 text-slate-900">
            <Server size={18} />
            <span className="font-medium">Worker 列表</span>
          </div>
          <div className="flex items-center gap-3">
            <label className="text-sm text-slate-500">状态筛选</label>
            <select
              value={status}
              onChange={(e) => setStatus(e.target.value as '' | WorkerStatus)}
              className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700"
            >
              {statusOptions.map((item) => (
                <option key={item.value || 'all'} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {error ? (
          <div className="mt-4 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-600">
            {error}
          </div>
        ) : null}

        <div className="mt-4 overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead>
              <tr className="text-left text-slate-500">
                <th className="px-4 py-3 font-medium">机器</th>
                <th className="px-4 py-3 font-medium">主机名</th>
                <th className="px-4 py-3 font-medium">IP</th>
                <th className="px-4 py-3 font-medium">队列</th>
                <th className="px-4 py-3 font-medium">状态</th>
                <th className="px-4 py-3 font-medium">最后心跳</th>
                <th className="px-4 py-3 font-medium">标签</th>
                <th className="px-4 py-3 font-medium">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {workers.length === 0 ? (
                <tr>
                  <td colSpan={8} className="px-4 py-10 text-center text-slate-400">
                    {loading ? '正在加载 Worker 列表…' : '暂无 Worker 数据'}
                  </td>
                </tr>
              ) : (
                workers.map((worker) => (
                  <tr key={worker.machine_id} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-medium text-slate-900">
                      <div className="flex items-center gap-2">
                        <Cpu size={16} className="text-slate-400" />
                        {worker.machine_id}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{worker.hostname || worker.machine_name || '-'}</td>
                    <td className="px-4 py-3 text-slate-700">{worker.ip || '-'}</td>
                    <td className="px-4 py-3 text-slate-700">{worker.queue_name || `worker.${worker.machine_id}`}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${statusStyles[worker.status]}`}>
                        {statusText[worker.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{formatTime(worker.last_heartbeat)}</td>
                    <td className="px-4 py-3 text-slate-700">-</td>
                    <td className="px-4 py-3 text-sm font-medium">
                      <button
                        onClick={() => {
                          setCurrentWorker(worker);
                          setShowDeleteConfirm(true);
                        }}
                        className="text-red-600 transition-colors hover:text-red-800"
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
      </div>

      {showDeleteConfirm && currentWorker ? (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowDeleteConfirm(false)}>
          <div className="w-full max-w-md rounded-xl bg-white p-6 shadow-xl" onClick={(e) => e.stopPropagation()}>
            <h3 className="mb-4 text-xl font-bold text-slate-800">确认删除</h3>
            <p className="mb-6 text-slate-600">
              确定要删除 Worker <span className="font-semibold text-slate-900">{currentWorker.machine_name || currentWorker.machine_id}</span> 吗？
              <br />
              <span className="text-sm text-red-600">此操作不可撤销。</span>
            </p>
            <div className="flex gap-3">
              <button
                onClick={() => setShowDeleteConfirm(false)}
                disabled={deleting}
                className="flex-1 rounded-lg border border-slate-300 px-4 py-2 text-slate-700 transition-colors hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-60"
              >
                取消
              </button>
              <button
                onClick={handleDeleteWorker}
                disabled={deleting}
                className="flex-1 rounded-lg bg-red-600 px-4 py-2 text-white transition-colors hover:bg-red-700 disabled:cursor-not-allowed disabled:opacity-60"
              >
                {deleting ? '删除中...' : '确定删除'}
              </button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
