export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  first_name: string;
  last_name: string;
  email: string;
  password: string;
}

export interface AuthResponse {
  access_token: string;
}

export interface SessionUser {
  id: number;
  first_name: string;
  last_name: string;
  email: string;
  phone: string | null;
  avatar_color: string;
}
