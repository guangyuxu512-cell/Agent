import request from './index';
import { Tool } from '../types/tool';

export async function getTools() {
  return request.get('/tools');
}

export async function addTool(data: Omit<Tool, 'id'>) {
  return request.post('/tools', data);
}

export async function updateTool(id: string, data: Partial<Tool>) {
  return request.put(`/tools/${id}`, data);
}

export async function deleteTool(id: string) {
  return request.delete(`/tools/${id}`);
}
