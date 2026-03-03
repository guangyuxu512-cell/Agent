export interface Schedule {
  id: string;
  name: string;
  agentId: string;
  triggerType: 'cron' | 'interval' | 'once';
  cronExpression?: string;
  intervalValue?: number;
  intervalUnit?: 'minutes' | 'hours' | 'days';
  executeTime?: string;
  inputMessage: string;
  enabled: boolean;
  lastRunTime?: string;
  lastRunStatus?: 'success' | 'failed' | 'running';
  lastRunDuration?: string;
}
