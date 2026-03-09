import { useEffect, useMemo, useState } from 'react';
import { Cpu, RefreshCw, Server } from 'lucide-react';
import { getWorkers } from '../api/workers';
import { Worker, WorkerStatus } from '../types/worker';

const statusOptions: Array<{ value: '' | WorkerStatus; label: string }> = [
  { value: '', label: '全部状态' },
  { value: 'online', label: '在线' },
  { value: 'busy', label: '忙碌' },
  { value: 'offline', label: '离线' },
];

const statusStyles: Record<WorkerStatus, string> = {
  online: 'bg-emerald-100 text-emerald-700',
  busy: 'bg-amber-100 text-amber-700',
  offline: 'bg-slate-200 text-slate-700',
};

const statusText: Record<WorkerStatus, string> = {
  online: '在线',
  busy: '忙碌',
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

  const fetchWorkers = async () => {
    setLoading(true);
    setError('');
    try {
      const res = await getWorkers(status || undefined);
      if (res.code !== 0) {
        setError(res.msg || '获取机器列表失败');
        return;
      }
      setWorkers(res.data?.list || []);
    } catch (err: any) {
      setError(err?.message || '获取机器列表失败');
    } finally {
      setLoading(false);
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
      { total: 0, online: 0, busy: 0, offline: 0 }
    );
  }, [workers]);

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-2xl font-semibold text-slate-900">机器管理</h2>
          <p className="mt-1 text-sm text-slate-500">展示 Worker 列表、在线状态和最近一次心跳。</p>
        </div>
        <button
          onClick={fetchWorkers}
          className="inline-flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm text-slate-700 shadow-sm hover:bg-slate-50"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          刷新
        </button>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-sm text-slate-500">机器总数</div>
          <div className="mt-2 text-2xl font-semibold text-slate-900">{summary.total}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-sm text-slate-500">在线</div>
          <div className="mt-2 text-2xl font-semibold text-emerald-600">{summary.online}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
          <div className="text-sm text-slate-500">忙碌</div>
          <div className="mt-2 text-2xl font-semibold text-amber-600">{summary.busy}</div>
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
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {workers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-10 text-center text-slate-400">
                    {loading ? '正在加载机器列表…' : '暂无机器数据'}
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
                    <td className="px-4 py-3 text-slate-700">{worker.hostname || '-'}</td>
                    <td className="px-4 py-3 text-slate-700">{worker.ip || '-'}</td>
                    <td className="px-4 py-3 text-slate-700">{worker.queue_name}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-full px-2.5 py-1 text-xs font-medium ${statusStyles[worker.status]}`}>
                        {statusText[worker.status]}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-700">{formatTime(worker.last_heartbeat)}</td>
                    <td className="px-4 py-3 text-slate-700">
                      {worker.tags?.length ? worker.tags.join('、') : '-'}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
