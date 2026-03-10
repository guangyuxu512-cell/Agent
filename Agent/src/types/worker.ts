export type WorkerStatus = 'idle' | 'running' | 'offline' | 'error';

export interface Worker {
  id: number;
  machine_id: string;
  machine_name: string;
  queue_name: string;
  status: WorkerStatus;
  last_heartbeat: string | null;
  created_at?: string;
  updated_at?: string;
}
