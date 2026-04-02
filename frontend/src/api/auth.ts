/**
 * Auth API client — email/password + Microsoft OAuth.
 * The backend sets HttpOnly cookies directly — no tokens are stored in JS.
 */
import apiClient from './client';

export interface UserResponse {
  id: string;
  email: string;
  display_name: string;
  avatar_url: string | null;
  role: string;
  auth_provider: string;
  is_active: boolean;
  created_at: string;
}

export interface AuthStatusResponse {
  user: UserResponse;
}

export async function logout(): Promise<void> {
  await apiClient.post('/auth/logout');
}

export async function getMe(): Promise<AuthStatusResponse> {
  const { data } = await apiClient.get<AuthStatusResponse>('/auth/me');
  return data;
}

export async function loginWithPassword(
  email: string,
  password: string,
): Promise<AuthStatusResponse> {
  const { data } = await apiClient.post<AuthStatusResponse>('/auth/login', {
    email,
    password,
  });
  return data;
}

export async function register(
  email: string,
  password: string,
  display_name: string,
): Promise<AuthStatusResponse> {
  const { data } = await apiClient.post<AuthStatusResponse>('/auth/register', {
    email,
    password,
    display_name,
  });
  return data;
}

export async function getMicrosoftUrl(): Promise<string> {
  const { data } = await apiClient.get<{ url: string; state: string }>(
    '/auth/microsoft/url',
  );
  return data.url;
}

export async function microsoftCallback(
  code: string,
  state: string,
): Promise<AuthStatusResponse> {
  const { data } = await apiClient.post<AuthStatusResponse>(
    '/auth/microsoft/callback',
    { code, state },
  );
  return data;
}
