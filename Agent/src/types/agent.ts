export interface Agent {
  id: string;
  name: string;
  role: string;
  prompt: string;
  llmProvider: string;
  llmModel: string;
  llmApiUrl: string;
  llmApiKey: string;
  temperature: number;
  tools: string[];
  maxIterations: number;
  timeout: number;
  requireApproval: boolean;
  status: 'running' | 'stopped';
  updateTime: string;
}

export interface OrchestrationConfig {
  mode: string;
  entryAgent: string;
  routingRules: string;
  parallelGroups: string;
  globalState: { key: string; desc: string }[];
}
