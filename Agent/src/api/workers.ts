import request from './index';
import { Worker } from '../types/worker';

export async function getWorkers(status?: string) {
  return request.get<{ list: Worker[]; total: number }>('/workers', {
    params: status ? { status } : {},
  });
}
