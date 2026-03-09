export type WorkerStatus = 'online' | 'offline' | 'busy';

export interface Worker {
  id: number;
  machine_id: string;
  hostname: string;
  ip: string;
  queue_name: string;
  status: WorkerStatus;
  last_heartbeat: string | null;
  tags: string[];
}
