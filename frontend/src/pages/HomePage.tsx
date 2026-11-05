import { Link } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { HealthCard } from "../components/HealthCard";
import { Poster } from "../components/Poster";
import { ProgressBar } from "../components/ProgressBar";
import { contentPath } from "../lib/catalog";
import { levelPercent } from "../lib/gamification";
import type { Profile } from "../lib/gamification";
import type { TrackedItem } from "../lib/tracking";
import { useApi } from "../lib/useApi";

/** Raccourci vers le profil : niveau et série de jours. */
function LevelCard() {
  const state = useApi<Profile>("/api/gamification/me");
  if (state.status !== "success") return null;
  const profile = state.data;
  return (
    <Link
      to="/profil"
      className="block rounded-2xl border border-border bg-surface p-4 hover:border-accent/60"
    >
      <div className="flex items-baseline justify-between">
        <span className="font-semibold">Niveau {profile.level}</span>
        <span className="text-sm text-muted">
          <span aria-hidden="true">🔥</span> {profile.streak_days} j · {profile.xp} XP
        </span>
      </div>
      <div className="mt-2">
        <ProgressBar percent={levelPercent(profile)} label={`Progression vers le niveau ${profile.level + 1}`} />
      </div>
    </Link>
  );
}

/** « Continuer à regarder » : les contenus en cours, du plus récent au plus ancien. */
function ContinueWatching() {
  const state = useApi<TrackedItem[]>("/api/tracking?status=watching");
  // Rien à afficher (ou erreur) : la section disparaît simplement.
  if (state.status !== "success" || state.data.length === 0) return null;
  return (
    <section aria-labelledby="continuer">
      <div className="flex items-baseline justify-between">
        <h2 id="continuer" className="text-lg font-semibold">
          Continuer à regarder
        </h2>
        <Link to="/suivi?statut=watching" className="text-sm text-accent hover:underline">
          Tout voir
        </Link>
      </div>
      <ul className="-mx-5 mt-3 flex gap-3 overflow-x-auto px-5 pb-2">
        {state.data.slice(0, 10).map(({ content, progress }) => (
          <li key={content.id} className="w-28 shrink-0">
            <Link to={contentPath(content)} className="block">
              <Poster url={content.poster_url} title={content.title} />
              <p className="mt-1 truncate text-sm">{content.title}</p>
              <ProgressBar percent={progress.percent ?? 0} label={`Progression de ${content.title}`} />
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
}

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

      <LevelCard />

      <ContinueWatching />

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
