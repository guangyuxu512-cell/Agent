import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import { Bot, MessageSquare, FileText, Table, Settings, LogOut, Wrench, Server } from 'lucide-react';

const navItems = [
  { path: '/', name: 'Agent聊天', icon: MessageSquare },
  { path: '/agent', name: 'Agent智能体', icon: Bot },
  { path: '/tools', name: '工具管理', icon: Wrench },
  { path: '/workers', name: '机器管理', icon: Server },
  { path: '/logs', name: '自动化日志', icon: FileText },
  { path: '/feishu', name: '飞书表管理', icon: Table },
  { path: '/config', name: '基础配置', icon: Settings },
];

export default function Layout() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('token');
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-slate-50 font-sans">
      {/* 左侧导航栏 */}
      <aside className="w-64 bg-slate-900 text-white flex flex-col shadow-xl z-10">
        <div className="h-16 flex items-center px-6 border-b border-slate-800">
          <h1 className="text-xl font-bold tracking-wider">自动化控制台</h1>
        </div>
        <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
          {navItems.map((item) => {
            const Icon = item.icon;
            return (
              <NavLink
                key={item.path}
                to={item.path}
                className={({ isActive }) =>
                  `flex items-center gap-3 px-4 py-3 rounded-lg transition-all duration-200 ${
                    isActive
                      ? 'bg-blue-600 text-white shadow-md'
                      : 'text-slate-400 hover:bg-slate-800 hover:text-white'
                  }`
                }
              >
                <Icon size={20} />
                <span className="font-medium">{item.name}</span>
              </NavLink>
            );
          })}
        </nav>
        <div className="p-4 border-t border-slate-800">
          <button 
            onClick={handleLogout}
            className="flex items-center gap-3 px-4 py-3 w-full rounded-lg text-slate-400 hover:bg-slate-800 hover:text-white transition-all duration-200"
          >
            <LogOut size={20} />
            <span className="font-medium">退出登录</span>
          </button>
        </div>
      </aside>

      {/* 右侧内容区 */}
      <main className="flex-1 flex flex-col overflow-hidden">
        {/* 顶部 Header */}
        <header className="h-16 bg-white shadow-sm flex items-center justify-between px-8 z-0 border-b border-slate-200">
          <div className="text-slate-800 font-medium">欢迎回来，管理员</div>
        </header>
        
        {/* 路由出口 */}
        <div className="flex-1 overflow-auto p-8">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
