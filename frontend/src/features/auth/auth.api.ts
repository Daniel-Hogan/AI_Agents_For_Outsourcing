import { apiJson } from "../../lib/api";
import type { AuthResponse, LoginRequest, RegisterRequest, SessionUser } from "./auth.types";

export async function login(data: LoginRequest) {
  return apiJson<AuthResponse>("/auth/login", {
    method: "POST",
    body: JSON.stringify(data),
  }, { retryOn401: false });
}

export async function register(data: RegisterRequest) {
  return apiJson<AuthResponse>("/auth/register", {
    method: "POST",
    body: JSON.stringify(data),
  }, { retryOn401: false });
}

export async function fetchCurrentUser() {
  return apiJson<SessionUser>("/auth/me");
}

export async function logout() {
  return apiJson<{ ok: boolean }>("/auth/logout", { method: "POST" }, { retryOn401: false });
}
