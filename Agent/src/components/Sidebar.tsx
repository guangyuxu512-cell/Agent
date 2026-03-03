import { NavLink } from 'react-router-dom';
import { Bot, FileText, Table, Settings } from 'lucide-react';

const navItems = [
  { name: 'Agent智能体', path: '/agent', icon: Bot },
  { name: '影刀运行日志', path: '/logs', icon: FileText },
  { name: '飞书表管理', path: '/feishu', icon: Table },
  { name: '基础配置', path: '/config', icon: Settings },
];

export default function Sidebar() {
  return (
    <div className="w-64 bg-gray-900 text-gray-300 flex flex-col h-full border-r border-gray-800">
      <div className="h-16 flex items-center px-6 border-b border-gray-800">
        <h1 className="text-lg font-semibold text-white tracking-wide">管理控制台</h1>
      </div>
      <nav className="flex-1 px-4 py-6 space-y-2 overflow-y-auto">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) =>
                `flex items-center px-3 py-2.5 rounded-lg transition-colors duration-200 ${
                  isActive
                    ? 'bg-indigo-600 text-white'
                    : 'hover:bg-gray-800 hover:text-white'
                }`
              }
            >
              <Icon className="w-5 h-5 mr-3 flex-shrink-0" />
              <span className="text-sm font-medium">{item.name}</span>
            </NavLink>
          );
        })}
      </nav>
      <div className="p-4 border-t border-gray-800 text-xs text-gray-500 text-center">
        v1.0.0
      </div>
    </div>
  );
}
