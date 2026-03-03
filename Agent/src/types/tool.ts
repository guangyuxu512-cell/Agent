export interface Tool {
  id: string;
  name: string;
  type: 'api' | 'script' | 'builtin';
  path: string;
  description: string;
  parameters: string;
  enabled: boolean;
}
