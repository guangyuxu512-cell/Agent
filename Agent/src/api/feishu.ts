import request from './index';
import { FeishuTable } from '../types/feishu';

// 获取所有飞书表格配置
export async function getTables() {
  return request.get('/feishu/tables');
}

// 新增飞书表格
export async function addTable(data: Omit<FeishuTable, 'id' | 'createdAt' | 'updatedAt'>) {
  return request.post('/feishu/tables', data);
}

// 更新飞书表格
export async function updateTable(id: string, data: Omit<FeishuTable, 'id' | 'createdAt' | 'updatedAt'>) {
  return request.put(`/feishu/tables/${id}`, data);
}

// 删除飞书表格
export async function deleteTable(id: string) {
  return request.delete(`/feishu/tables/${id}`);
}
