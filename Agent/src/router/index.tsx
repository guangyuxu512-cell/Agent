import { createBrowserRouter, redirect } from 'react-router-dom';
import Layout from '../components/Layout';
import ErrorBoundary from '../components/ErrorBoundary';
import Login from '../views/Login';
import Agent from '../views/Agent';
import AgentChat from '../views/AgentChat';
import ShadowbotLogs from '../views/ShadowbotLogs';
import FeishuTables from '../views/FeishuTables';
import BasicConfig from '../views/BasicConfig';
import Tools from '../views/Tools';

// 鉴权路由守卫：未登录（无 token）重定向到 /login
const authLoader = () => {
  const token = localStorage.getItem('token');
  if (!token) {
    return redirect('/login');
  }
  return null;
};

export const router = createBrowserRouter([
  {
    path: '/login',
    element: <Login />,
  },
  {
    path: '/',
    element: <Layout />,
    loader: authLoader,
    errorElement: <ErrorBoundary />,
    children: [
      { index: true, element: <AgentChat /> },
      { path: 'agent', element: <Agent /> },
      { path: 'tools', element: <Tools /> },
      { path: 'logs', element: <ShadowbotLogs /> },
      { path: 'feishu', element: <FeishuTables /> },
      { path: 'config', element: <BasicConfig /> },
    ],
  },
]);
