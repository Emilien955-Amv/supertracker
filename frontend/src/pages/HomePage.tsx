import { Link } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { HealthCard } from "../components/HealthCard";

/** Accueil provisoire : il accueillera « prochains épisodes » et « sorties de
 * la semaine » dans les étapes suivantes. */
export default function HomePage() {
  const { state, logout } = useAuth();
  if (state.status !== "authenticated") return null; // garanti par RequireAuth

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-6 px-5 py-10">
      <header className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-medium uppercase tracking-widest text-accent">SuperTracker</p>
          <h1 className="mt-1 text-3xl font-bold">Bonjour {state.user.username} 👋</h1>
          <p className="mt-2 text-muted">Que regardons-nous aujourd'hui ?</p>
        </div>
        <button
          type="button"
          onClick={() => void logout()}
          className="shrink-0 rounded-xl border border-border px-3 py-2 text-sm hover:bg-surface"
        >
          Se déconnecter
        </button>
      </header>

      <Link
        to="/recherche"
        className="flex items-center justify-between rounded-2xl border border-accent/40 bg-accent/10 p-5 hover:bg-accent/20"
      >
        <span>
          <span className="block text-lg font-semibold">Trouver un contenu</span>
          <span className="text-sm text-muted">Films, séries et animes</span>
        </span>
        <span aria-hidden="true" className="text-2xl text-accent">
          →
        </span>
      </Link>

      <HealthCard />

      <a
        href="/api/docs"
        className="rounded-xl bg-accent px-4 py-3 text-center font-semibold text-white hover:opacity-90"
      >
        Ouvrir la documentation de l'API
      </a>
    </main>
  );
}
