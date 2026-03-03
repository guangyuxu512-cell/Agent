import request from './index';
import { Agent, OrchestrationConfig } from '../types/agent';

export async function getAgents() {
  return request.get('/agents');
}

export async function addAgent(data: Omit<Agent, 'id' | 'status' | 'updateTime'>) {
  return request.post('/agents', data);
}

export async function updateAgent(id: number | string, data: Partial<Agent>) {
  return request.put(`/agents/${id}`, data);
}

export async function deleteAgent(id: number | string) {
  return request.delete(`/agents/${id}`);
}

export async function getOrchestration() {
  return request.get('/orchestration');
}

export async function saveOrchestration(data: OrchestrationConfig) {
  return request.post('/orchestration', data);
}
