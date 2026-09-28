import { apiClient } from "./client";
import type { TokenResponse } from "./types";

export async function login(username: string, password: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/api/auth/login", {
    username,
    password,
  });
  return data;
}

export async function refreshToken(): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/api/auth/refresh");
  return data;
}

export async function msLogin(idToken: string): Promise<TokenResponse> {
  const { data } = await apiClient.post<TokenResponse>("/api/auth/ms-login", {
    id_token: idToken,
  });
  return data;
}

