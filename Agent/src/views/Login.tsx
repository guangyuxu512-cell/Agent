import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { login } from '../api/auth';
import { Bot, Lock, User } from 'lucide-react';
import ChangePasswordModal from '../components/ChangePasswordModal';

export default function Login() {
  const navigate = useNavigate();
  const [username, setUsername] = useState('admin');
  const [password, setPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [showChangePassword, setShowChangePassword] = useState(false);
  const [forceChange, setForceChange] = useState(false);

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);

    try {
      const res: any = await login({ username, password });
      if (res.code === 0) {
        localStorage.setItem('token', res.data.token);

        // 检查是否需要强制改密
        if (res.data.force_change_password) {
          setForceChange(true);
          setShowChangePassword(true);
        } else {
          navigate('/');
        }
      } else {
        alert(res.msg || '登录失败');
      }
    } catch (error) {
      console.error('Login failed:', error);
      alert('登录失败，请检查网络或稍后重试');
    } finally {
      setIsLoading(false);
    }
  };

  const handlePasswordChangeSuccess = () => {
    // 改密成功后清除 token，要求重新登录
    localStorage.removeItem('token');
    setShowChangePassword(false);
    setForceChange(false);
    setPassword('');
    alert('密码修改成功，请使用新密码重新登录');
  };

  return (
    <>
      <div className="min-h-screen flex items-center justify-center bg-slate-50">
        <div className="bg-white p-10 rounded-2xl shadow-xl w-96 border border-slate-100">
          <div className="text-center mb-8 flex flex-col items-center">
            <div className="w-16 h-16 bg-blue-100 text-blue-600 rounded-2xl flex items-center justify-center mb-4">
              <Bot size={32} />
            </div>
            <h2 className="text-2xl font-bold text-slate-800">系统登录</h2>
            <p className="text-slate-500 text-sm mt-2">欢迎使用管理控制台</p>
          </div>

          <form onSubmit={handleLogin} className="space-y-5">
            <div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <User size={18} />
                </div>
                <input
                  type="text"
                  required
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                  placeholder="用户名"
                />
              </div>
            </div>

            <div>
              <div className="relative">
                <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none text-slate-400">
                  <Lock size={18} />
                </div>
                <input
                  type="password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="w-full pl-10 pr-4 py-3 border border-slate-200 rounded-xl focus:ring-2 focus:ring-blue-500 outline-none transition-all"
                  placeholder="密码"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={isLoading}
              className="w-full bg-blue-600 text-white py-3 rounded-xl font-medium hover:bg-blue-700 transition-colors disabled:opacity-70 flex justify-center items-center"
            >
              {isLoading ? '登录中...' : '登录'}
            </button>
          </form>
        </div>
      </div>

      <ChangePasswordModal
        isOpen={showChangePassword}
        onClose={() => setShowChangePassword(false)}
        onSuccess={handlePasswordChangeSuccess}
        forceChange={forceChange}
      />
    </>
  );
}
