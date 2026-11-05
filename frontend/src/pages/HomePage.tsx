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
          <p className="mt-2 text-muted">Votre compte est prêt. La suite arrive bientôt !</p>
        </div>
        <button
          type="button"
          onClick={() => void logout()}
          className="shrink-0 rounded-xl border border-border px-3 py-2 text-sm hover:bg-surface"
        >
          Se déconnecter
        </button>
      </header>

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
