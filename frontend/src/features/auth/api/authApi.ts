import { API_ENDPOINTS } from '@/shared/constant/endpoints';

interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
}

interface UserResponse {
  id: string;
  email: string;
}

async function handleResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error((body as { detail?: string }).detail ?? `HTTP ${res.status}`);
  }
  return res.json() as Promise<T>;
}

export const authApi = {
  login: async (email: string, password: string): Promise<TokenResponse> => {
    const res = await fetch(API_ENDPOINTS.AUTH.LOGIN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    return handleResponse<TokenResponse>(res);
  },

  register: async (email: string, password: string, redirectTo?: string): Promise<TokenResponse> => {
    const res = await fetch(API_ENDPOINTS.AUTH.REGISTER, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password, redirect_to: redirectTo }),
    });
    return handleResponse<TokenResponse>(res);
  },

  loginWithGoogle: async (idToken: string, nonce: string): Promise<TokenResponse> => {
    const res = await fetch(API_ENDPOINTS.AUTH.GOOGLE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ id_token: idToken, nonce }),
    });
    return handleResponse<TokenResponse>(res);
  },

  logout: async (token: string): Promise<void> => {
    await fetch(API_ENDPOINTS.AUTH.LOGOUT, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` },
    });
  },

  me: async (token: string): Promise<UserResponse> => {
    const res = await fetch(API_ENDPOINTS.AUTH.ME, {
      headers: { Authorization: `Bearer ${token}` },
    });
    return handleResponse<UserResponse>(res);
  },

  refresh: async (refreshToken: string): Promise<TokenResponse> => {
    const res = await fetch(API_ENDPOINTS.AUTH.REFRESH, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ refresh_token: refreshToken }),
    });
    return handleResponse<TokenResponse>(res);
  },
};
