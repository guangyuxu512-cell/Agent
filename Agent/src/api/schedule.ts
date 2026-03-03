import request from './index';
import { Schedule } from '../types/schedule';

export async function getSchedules() {
  return request.get('/schedules');
}

export async function addSchedule(data: Omit<Schedule, 'id' | 'lastRunTime' | 'lastRunStatus' | 'lastRunDuration'>) {
  return request.post('/schedules', data);
}

export async function updateSchedule(id: string, data: Partial<Schedule>) {
  return request.put(`/schedules/${id}`, data);
}

export async function deleteSchedule(id: string) {
  return request.delete(`/schedules/${id}`);
}
