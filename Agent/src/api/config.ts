import request from './index';

export async function getConfig() {
  return request.get('/config');
}

export async function saveConfig(data: any) {
  return request.post('/config', data);
}
