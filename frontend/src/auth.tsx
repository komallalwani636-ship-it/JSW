import {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { TOKEN_KEY } from "./api/client";
import type { JwtPayload } from "./api/types";

interface AuthContextValue {
  token: string | null;
  username: string | null;
  role: "planner" | "viewer" | null;
  isPlanner: boolean;
  isAuthenticated: boolean;
  setToken: (token: string | null) => void;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function decodeJwt(token: string): JwtPayload | null {
  try {
    const payload = token.split(".")[1];
    const json = atob(payload.replace(/-/g, "+").replace(/_/g, "/"));
    return JSON.parse(json) as JwtPayload;
  } catch {
    return null;
  }
}

function isTokenValid(token: string): boolean {
  const payload = decodeJwt(token);
  if (!payload?.exp) return false;
  return payload.exp * 1000 > Date.now();
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [token, setTokenState] = useState<string | null>(() => {
    const stored = localStorage.getItem(TOKEN_KEY);
    return stored && isTokenValid(stored) ? stored : null;
  });

  const setToken = useCallback((value: string | null) => {
    if (value) {
      localStorage.setItem(TOKEN_KEY, value);
    } else {
      localStorage.removeItem(TOKEN_KEY);
    }
    setTokenState(value);
  }, []);

  const logout = useCallback(() => setToken(null), [setToken]);

  const payload = token ? decodeJwt(token) : null;

  const value = useMemo<AuthContextValue>(
    () => ({
      token,
      username: payload?.sub ?? null,
      role: payload?.role ?? null,
      isPlanner: payload?.role === "planner",
      isAuthenticated: Boolean(token && payload),
      setToken,
      logout,
    }),
    [token, payload, setToken, logout],
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}

export function isAuthenticated(): boolean {
  const token = localStorage.getItem(TOKEN_KEY);
  return Boolean(token && isTokenValid(token));
}
