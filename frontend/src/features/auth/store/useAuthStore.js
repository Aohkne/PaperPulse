import { create } from 'zustand';
import { persist } from 'zustand/middleware';
import { authApi } from '@/features/auth/api/authApi';
import { API_ENDPOINTS } from '@/shared/constant/endpoints';

async function fetchProfile(token) {
  try {
    const res = await fetch(API_ENDPOINTS.AUTH.ME, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!res.ok) return { id: null, role: 'user' };
    const data = await res.json();
    return { id: data.id ?? null, role: data.role ?? 'user' };
  } catch {
    return { id: null, role: 'user' };
  }
}

export const useAuthStore = create(
  persist(
    (set, get) => ({
      user: null,
      token: null,
      refreshToken: null,
      isAuthenticated: false,

      login: async (email, password) => {
        const data = await authApi.login(email, password);
        const { id, role } = await fetchProfile(data.access_token);
        set({
          token: data.access_token,
          refreshToken: data.refresh_token,
          user: { id, email, name: email.split('@')[0], role },
          isAuthenticated: true,
        });
      },

      signup: async (email, password, name) => {
        const data = await authApi.register(email, password);
        const { id, role } = await fetchProfile(data.access_token);
        set({
          token: data.access_token,
          refreshToken: data.refresh_token,
          user: { id, email, name: name || email.split('@')[0], role },
          isAuthenticated: true,
        });
      },

      logout: async () => {
        const { token } = get();
        if (token) {
          try {
            await authApi.logout(token);
          } catch {
            // clear state regardless of server response
          }
        }
        set({ user: null, token: null, refreshToken: null, isAuthenticated: false });
      },

      // Exchange the refresh_token for a new access_token — called by API
      // clients on a 401 "Token expired" response. Throws (and logs the user
      // out) if the refresh token itself is no longer valid, so the caller's
      // ProtectedRoute redirects to /login instead of looping on 401s.
      refreshAccessToken: async () => {
        const { refreshToken } = get();
        if (!refreshToken) {
          set({ user: null, token: null, refreshToken: null, isAuthenticated: false });
          throw new Error('No refresh token available — please log in again.');
        }
        try {
          const data = await authApi.refresh(refreshToken);
          set({ token: data.access_token, refreshToken: data.refresh_token });
          return data.access_token;
        } catch (err) {
          set({ user: null, token: null, refreshToken: null, isAuthenticated: false });
          throw err;
        }
      },
    }),
    {
      name: 'auth-storage',
      partialize: (state) => ({
        token: state.token,
        refreshToken: state.refreshToken,
        user: state.user,
        isAuthenticated: state.isAuthenticated,
      }),
    }
  )
);
