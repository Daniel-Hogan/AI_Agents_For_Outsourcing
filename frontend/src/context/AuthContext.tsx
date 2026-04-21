import { createContext, useContext, useEffect, useState } from "react";

import { fetchCurrentUser, logout as logoutRequest } from "../features/auth/auth.api";
import { clearStoredToken, getStoredToken, refreshAccessToken, storeToken } from "../lib/api";
import type { SessionUser } from "../features/auth/auth.types";

interface AuthContextType {
  token: string | null;
  user: SessionUser | null;
  isLoading: boolean;
  setToken: (token: string | null) => void;
  refreshSession: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [token, setTokenState] = useState<string | null>(getStoredToken());
  const [user, setUser] = useState<SessionUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  function setToken(newToken: string | null) {
    if (newToken) {
      storeToken(newToken);
    } else {
      clearStoredToken();
      setUser(null);
    }
    setTokenState(newToken);
  }

  async function refreshSession() {
    const existingToken = getStoredToken();

    if (!existingToken) {
      await refreshAccessToken();
    }

    const nextToken = getStoredToken();
    if (!nextToken) {
      setTokenState(null);
      setUser(null);
      return;
    }

    try {
      const currentUser = await fetchCurrentUser();
      setTokenState(getStoredToken());
      setUser(currentUser);
    } catch {
      clearStoredToken();
      setTokenState(null);
      setUser(null);
    }
  }

  async function logout() {
    try {
      await logoutRequest();
    } catch {
      // Always clear local session state even if the request fails.
    }
    clearStoredToken();
    setTokenState(null);
    setUser(null);
  }

  useEffect(() => {
    let isMounted = true;

    async function bootstrapSession() {
      try {
        await refreshSession();
      } finally {
        if (isMounted) {
          setIsLoading(false);
        }
      }
    }

    bootstrapSession();

    return () => {
      isMounted = false;
    };
  }, []);

  return (
    <AuthContext.Provider value={{ token, user, isLoading, setToken, refreshSession, logout }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider");
  return context;
}
