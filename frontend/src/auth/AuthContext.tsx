/**
 * Contexte d'authentification : rend l'utilisateur connecté accessible à
 * tous les écrans via le hook useAuth().
 */
import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { apiFetch, login as apiLogin, refreshAccessToken, setAccessToken } from "../lib/api";

export type User = {
  id: number;
  email: string;
  username: string;
  avatar_url: string | null;
  bio: string | null;
  is_public: boolean;
  /** Titre gagné en complétant une collection (ex. « Roi des pirates »). */
  title?: string | null;
  created_at: string;
};

/** « loading » : on ne sait pas encore si une session existe (au démarrage). */
export type AuthState =
  | { status: "loading" }
  | { status: "anonymous" }
  | { status: "authenticated"; user: User };

type AuthContextValue = {
  state: AuthState;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  /** Remplace l'utilisateur affiché (ex. après une modification du profil). */
  updateUser: (user: User) => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ status: "loading" });

  const loadUser = useCallback(async () => {
    const user = await apiFetch<User>("/api/users/me");
    setState({ status: "authenticated", user });
  }, []);

  // Au chargement de la page : le cookie de renouvellement permet-il de
  // retrouver la session ? (C'est ce qui évite de se reconnecter à chaque visite.)
  useEffect(() => {
    let cancelled = false;
    refreshAccessToken()
      .then((token) => (token ? loadUser() : setState({ status: "anonymous" })))
      .catch(() => {
        if (!cancelled) setState({ status: "anonymous" });
      });
    return () => {
      cancelled = true;
    };
  }, [loadUser]);

  const login = useCallback(
    async (email: string, password: string) => {
      await apiLogin(email, password);
      await loadUser();
    },
    [loadUser],
  );

  const register = useCallback(
    async (email: string, username: string, password: string) => {
      await apiFetch("/api/auth/register", {
        method: "POST",
        body: { email, username, password },
      });
      await login(email, password);
    },
    [login],
  );

  const logout = useCallback(async () => {
    try {
      await apiFetch("/api/auth/logout", { method: "POST" });
    } finally {
      // Même si le serveur est injoignable, on oublie la session localement.
      setAccessToken(null);
      setState({ status: "anonymous" });
    }
  }, []);

  const updateUser = useCallback((user: User) => setState({ status: "authenticated", user }), []);

  const value = useMemo(
    () => ({ state, login, register, logout, updateUser }),
    [state, login, register, logout, updateUser],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth doit être utilisé dans <AuthProvider>.");
  return context;
}
