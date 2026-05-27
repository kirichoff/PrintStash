export interface LoginRequest {
  username: string;
  password: string;
}

export interface TokenResponse {
  access_token: string;
  token_type: string;
}

export interface UserRead {
  id: number;
  username: string;
  email: string | null;
  is_superuser: boolean;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}
