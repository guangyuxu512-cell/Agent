export interface FeishuTable {
  id: string;           // UUID 字符串（不是 number）
  name: string;
  appToken: string;
  tableId: string;
  description: string;
  createdAt?: string;
  updatedAt?: string;
}