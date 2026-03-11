import request from './index';
import { Worker } from '../types/worker';

function assertSuccess<T>(response: any, fallback: string): T {
  if (response.code !== 0) {
    throw new Error(response.msg || fallback);
  }
  return response.data as T;
}

export async function getWorkers(status?: string): Promise<{ list: Worker[]; total: number }> {
  const response = await request.get<{ list: Worker[]; total: number }>('/workers', {
    params: status ? { status } : {},
  });
  return assertSuccess<{ list: Worker[]; total: number }>(response, '获取 Worker 列表失败');
}

export async function deleteWorker(machineId: string): Promise<void> {
  const response = await request.delete(`/workers/${machineId}`);
  assertSuccess(response, '删除 Worker 失败');
}
