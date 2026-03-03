export interface ConfigData {
  llm: {
    provider: string;
    modelName: string;
    apiUrl: string;
    apiKey: string;
  };
  agent: { systemPrompt: string };
  email: {
    smtpServer: string;
    smtpPort: string;
    sender: string;
    smtpPassword: string;
  };
  shadowbot: {
    targetEmail: string;
    subjectTemplate: string;
    contentTemplate: string;
  };
  feishu: { appId: string; appSecret: string; feishuEventAgentId?: string };
  n8n: {
    apiUrl: string;
    apiKey: string;
    workflows: { id: string; name: string; url: string; workflowId: string }[];
  };
  ragflow: { apiUrl: string; apiKey: string; kbId: string };
  wecom: {
    callbackToken: string;
    callbackSecret: string;
    corpId: string;
    appId: string;
    appSecret: string;
  };
}
