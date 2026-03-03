export interface LoginRequest {
  username?: string;
  password?: string;
}

export interface LoginResponse {
  token: string;
  force_change_password: boolean;
  user?: {
    id: number;
    username: string;
  };
}

export interface ChangePasswordRequest {
  old_password: string;
  new_password: string;
}
