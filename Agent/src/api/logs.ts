import request from './index';

export async function getLogs() {
  return request.get('/logs');
}
