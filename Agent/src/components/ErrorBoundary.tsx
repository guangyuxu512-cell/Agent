import { useRouteError } from 'react-router-dom';

export default function ErrorBoundary() {
  const error: any = useRouteError();
  console.error(error);
  return (
    <div className="p-8 text-center flex flex-col items-center justify-center h-screen bg-slate-50">
      <h1 className="text-2xl font-bold text-red-600 mb-4">Oops! 发生错误了</h1>
      <p className="text-slate-600">{error?.statusText || error?.message || '未知错误'}</p>
      <button 
        onClick={() => window.location.href = '/'}
        className="mt-6 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors"
      >
        返回首页
      </button>
    </div>
  );
}
