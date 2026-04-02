/**
 * Auth context — email/password + Microsoft OAuth.
 * Auth state is derived from GET /auth/me (succeeds when a valid access
 * cookie is present). Silent refresh is handled by the Axios interceptor
 * in client.ts.
 */
import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

import type { UserResponse } from '../api/auth';
import * as authApi from '../api/auth';

interface AuthContextType {
  user: UserResponse | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  logout: () => Promise<void>;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, displayName: string) => Promise<void>;
  loginWithMicrosoft: () => Promise<void>;
  handleOAuthCallback: (
    provider: 'microsoft',
    code: string,
    state: string,
  ) => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<UserResponse | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  // On mount: check if a valid access cookie is already present
  useEffect(() => {
    authApi
      .getMe()
      .then(({ user: me }) => setUser(me))
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  const logout = useCallback(async () => {
    try {
      await authApi.logout();
    } catch {
      // Best-effort — always clear local state
    }
    setUser(null);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const { user: me } = await authApi.loginWithPassword(email, password);
    setUser(me);
  }, []);

  const register = useCallback(
    async (email: string, password: string, displayName: string) => {
      const { user: me } = await authApi.register(email, password, displayName);
      setUser(me);
    },
    [],
  );

  const loginWithMicrosoft = useCallback(async () => {
    const url = await authApi.getMicrosoftUrl();
    window.location.href = url;
  }, []);

  const handleOAuthCallback = useCallback(
    async (_provider: 'microsoft', code: string, state: string) => {
      const { user: me } = await authApi.microsoftCallback(code, state);
      setUser(me);
    },
    [],
  );

  const value = useMemo<AuthContextType>(
    () => ({
      user,
      isLoading,
      isAuthenticated: user !== null,
      logout,
      login,
      register,
      loginWithMicrosoft,
      handleOAuthCallback,
    }),
    [user, isLoading, logout, login, register, loginWithMicrosoft, handleOAuthCallback],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextType {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
}
