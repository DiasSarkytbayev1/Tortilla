import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { api, ApiError, unwrap } from "@/api/client";
import type { UserOut } from "@/api/schemas";

type AuthState =
  | { status: "loading" }
  | { status: "anon" }
  | { status: "authed"; user: UserOut };

type AuthContextValue = {
  state: AuthState;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  useEffect(() => {
    void refresh();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function refresh() {
    const res = await api.GET("/api/auth/me");
    if (res.response.status === 401) {
      setState({ status: "anon" });
      return;
    }
    try {
      const user = unwrap(res);
      setState({ status: "authed", user });
    } catch {
      setState({ status: "anon" });
    }
  }

  async function login(username: string, password: string) {
    const res = await api.POST("/api/auth/login", { body: { username, password } });
    if (res.response.status === 401) {
      throw new ApiError(401, "Invalid username or password");
    }
    const user = unwrap(res);
    setState({ status: "authed", user });
  }

  async function logout() {
    await api.POST("/api/auth/logout");
    setState({ status: "anon" });
  }

  return <AuthContext.Provider value={{ state, login, logout }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
