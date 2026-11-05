/**
 * « Gardes » de navigation : elles décident si une page peut s'afficher.
 */
import type { ReactNode } from "react";
import { Navigate, useLocation } from "react-router";

import { Spinner } from "../components/Spinner";
import { useAuth } from "./AuthContext";

/** Page réservée aux utilisateurs connectés ; sinon, direction la connexion. */
export function RequireAuth({ children }: { children: ReactNode }) {
  const { state } = useAuth();
  const location = useLocation();

  if (state.status === "loading") return <Spinner label="Chargement de votre session…" />;
  if (state.status === "anonymous") {
    // On mémorise la page demandée pour y revenir après la connexion.
    return <Navigate to="/connexion" replace state={{ from: location.pathname }} />;
  }
  return children;
}

/** Page réservée aux visiteurs (connexion, inscription) ; sinon, accueil. */
export function GuestOnly({ children }: { children: ReactNode }) {
  const { state } = useAuth();

  if (state.status === "loading") return <Spinner label="Chargement…" />;
  if (state.status === "authenticated") return <Navigate to="/" replace />;
  return children;
}
