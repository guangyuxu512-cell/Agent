import { useState } from 'react';
import { X, Lock, AlertCircle } from 'lucide-react';
import { changePassword } from '../api/auth';

interface ChangePasswordModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  forceChange?: boolean;
}

export default function ChangePasswordModal({ isOpen, onClose, onSuccess, forceChange = false }: ChangePasswordModalProps) {
  const [oldPassword, setOldPassword] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');

  if (!isOpen) return null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (newPassword !== confirmPassword) {
      setError('两次输入的新密码不一致');
      return;
    }

    if (newPassword.length < 12) {
      setError('新密码长度必须至少 12 位');
      return;
    }

    setIsLoading(true);

    try {
      const res: any = await changePassword({
        old_password: oldPassword,
        new_password: newPassword
      });

      if (res.code === 0) {
        alert('密码修改成功，请重新登录');
        onSuccess();
      } else {
        setError(res.msg || '修改失败');
      }
    } catch (err) {
      console.error('Change password failed:', err);
      setError('修改失败，请检查网络或稍后重试');
    } finally {
      setIsLoading(false);
    }
  };

  const handleClose = () => {
    if (forceChange) {
      alert('必须修改密码后才能继续使用系统');
      return;
    }
    onClose();
  };

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md p-6 relative">
        {!forceChange && (
          <button
            onClick={handleClose}
            className="absolute top-4 right-4 text-gray-400 hover:text-gray-600"
          >
            <X size={20} />
          </button>
        )}

        <div className="flex items-center gap-3 mb-6">
          <div className="w-12 h-12 bg-blue-100 text-blue-600 rounded-xl flex items-center justify-center">
            <Lock size={24} />
          </div>
          <div>
            <h2 className="text-xl font-bold text-gray-800">修改密码</h2>
            {forceChange && (
              <p className="text-sm text-red-600 flex items-center gap-1 mt-1">
                <AlertCircle size={14} />
                检测到弱口令，必须修改密码
              </p>
            )}
          </div>
        </div>

        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-red-700 text-sm">
            {error}
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              旧密码
            </label>
            <input
              type="password"
              required
              value={oldPassword}
              onChange={(e) => setOldPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="请输入旧密码"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              新密码
            </label>
            <input
              type="password"
              required
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="至少12位，包含大小写/数字/符号至少两类"
            />
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              确认新密码
            </label>
            <input
              type="password"
              required
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 outline-none"
              placeholder="再次输入新密码"
            />
          </div>

          <div className="flex gap-3 pt-2">
            {!forceChange && (
              <button
                type="button"
                onClick={handleClose}
                className="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-50 transition-colors"
              >
                取消
              </button>
            )}
            <button
              type="submit"
              disabled={isLoading}
              className="flex-1 px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50"
            >
              {isLoading ? '修改中...' : '确认修改'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
