import {
  createContext,
  useCallback,
  useEffect,
  useState,
  type ReactNode,
} from 'react';
import { adminApi, getToken, removeToken, saveToken } from '../api/client';

interface AuthContextValue {
  /** null = still loading, true/false = resolved */
  authenticated: boolean | null;
  login: (password: string) => Promise<void>;
  logout: () => Promise<void>;
}

export const AuthContext = createContext<AuthContextValue>({
  authenticated: null,
  login: async () => {},
  logout: async () => {},
});

export function AuthProvider({ children }: { children: ReactNode }) {
  const [authenticated, setAuthenticated] = useState<boolean | null>(null);

  // Verify stored token on first mount
  useEffect(() => {
    if (!getToken()) {
      setAuthenticated(false);
      return;
    }
    adminApi
      .me()
      .then(() => setAuthenticated(true))
      .catch(() => {
        removeToken();
        setAuthenticated(false);
      });
  }, []);

  const login = useCallback(async (password: string) => {
    const { token } = await adminApi.login(password);
    saveToken(token);
    setAuthenticated(true);
  }, []);

  const logout = useCallback(async () => {
    await adminApi.logout().catch(() => {});
    removeToken();
    setAuthenticated(false);
  }, []);

  return (
    <AuthContext.Provider value={{ authenticated, login, logout }}>
      {children}
    </AuthContext.Provider>
  );
}
