export interface Log {
  id: number;
  taskName: string;
  executeTime: string;
  status: 'success' | 'failed';
  duration: string;
}
