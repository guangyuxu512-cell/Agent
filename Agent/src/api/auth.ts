import request from './index';
import { LoginRequest, ChangePasswordRequest } from '../types/auth';

export async function login(data: LoginRequest) {
  return request.post('/auth/login', data);
}

export async function changePassword(data: ChangePasswordRequest) {
  return request.post('/auth/change-password', data);
}
