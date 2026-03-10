import request from './index';

export interface Machine {
  id: number;
  machine_id: string;
  machine_name: string;
  status: 'idle' | 'running' | 'error' | 'offline';
  last_heartbeat: string | null;
  created_at: string;
  updated_at: string;
}

export interface MachineApp {
  id: number;
  machine_id: string;
  app_name: string;
  description: string;
  enabled: boolean;
  created_at: string;
}

interface 创建机器请求 {
  machine_id: string;
  machine_name: string;
}

interface 更新机器请求 {
  machine_name: string;
}

interface 创建应用绑定请求 {
  machine_id: string;
  app_name: string;
  description: string;
}

interface 更新应用绑定请求 {
  description?: string;
  enabled?: boolean;
}

function 断言成功<T>(响应: any, 默认错误: string): T {
  if (响应.code !== 0) {
    throw new Error(响应.msg || 默认错误);
  }
  return 响应.data as T;
}

export async function getMachines(): Promise<Machine[]> {
  const 响应 = await request.get<Machine[]>('/machines');
  return 断言成功<Machine[]>(响应, '获取机器列表失败');
}

export async function createMachine(请求体: 创建机器请求): Promise<Machine> {
  const 响应 = await request.post<Machine>('/machines', 请求体);
  return 断言成功<Machine>(响应, '添加机器失败');
}

export async function updateMachine(machineId: string, 请求体: 更新机器请求): Promise<Machine> {
  const 响应 = await request.put<Machine>(`/machines/${machineId}`, 请求体);
  return 断言成功<Machine>(响应, '编辑机器失败');
}

export async function deleteMachine(machineId: string): Promise<void> {
  const 响应 = await request.delete(`/machines/${machineId}`);
  断言成功(响应, '删除机器失败');
}

export async function getMachineApps(machineId?: string): Promise<MachineApp[]> {
  const 响应 = await request.get<MachineApp[]>('/machine-apps', {
    params: machineId ? { machine_id: machineId } : {},
  });
  return 断言成功<MachineApp[]>(响应, '获取应用绑定列表失败');
}

export async function createMachineApp(请求体: 创建应用绑定请求): Promise<MachineApp> {
  const 响应 = await request.post<MachineApp>('/machine-apps', 请求体);
  return 断言成功<MachineApp>(响应, '添加应用绑定失败');
}

export async function updateMachineApp(bindingId: number, 请求体: 更新应用绑定请求): Promise<MachineApp> {
  const 响应 = await request.put<MachineApp>(`/machine-apps/${bindingId}`, 请求体);
  return 断言成功<MachineApp>(响应, '更新应用绑定失败');
}

export async function deleteMachineApp(bindingId: number): Promise<void> {
  const 响应 = await request.delete(`/machine-apps/${bindingId}`);
  断言成功(响应, '删除应用绑定失败');
}
