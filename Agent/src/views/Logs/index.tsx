export default function LogsView() {
  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-2xl font-semibold text-gray-900">影刀运行日志</h2>
        <p className="mt-1 text-sm text-gray-500">查看影刀RPA的执行记录和状态。</p>
      </div>
      <div className="bg-white rounded-xl shadow-sm border border-gray-200 p-6">
        <p className="text-gray-500 text-sm">暂无日志</p>
      </div>
    </div>
  );
}
