import axios from 'axios';

interface ApiResponse<T = any> {
  code: number;
  data: T;
  msg: string;
}

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || '/api',
  timeout: 10000
});

// 请求拦截器：自动从 localStorage 读取 token，加到 Header
request.interceptors.request.use(config => {
    const token = localStorage.getItem('token');
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
});

// 响应拦截器：401 状态码自动跳转登录页，统一返回数据格式
request.interceptors.response.use(
    res => res.data,
    err => {
        if (err.response?.status === 401) {
            localStorage.removeItem('token');
            window.location.href = '/login';
        }
        return Promise.reject(err);
    }
);

// 封装请求方法，返回类型为 ApiResponse 而非 AxiosResponse
const api = {
  get<T = any>(url: string, config?: any): Promise<ApiResponse<T>> {
    return request.get(url, config) as any;
  },
  post<T = any>(url: string, data?: any, config?: any): Promise<ApiResponse<T>> {
    return request.post(url, data, config) as any;
  },
  put<T = any>(url: string, data?: any, config?: any): Promise<ApiResponse<T>> {
    return request.put(url, data, config) as any;
  },
  delete<T = any>(url: string, config?: any): Promise<ApiResponse<T>> {
    return request.delete(url, config) as any;
  },
};

export default api;
export type { ApiResponse };
