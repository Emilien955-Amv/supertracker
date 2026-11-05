import { useEffect, useState } from "react";

/** Réponse de GET /api/health (voir backend/app/api/health.py). */
type Health = {
  status: "ok" | "degraded";
  database: boolean;
  redis: boolean;
  version: string;
};

/** Les trois états possibles d'un chargement : on les affiche tous. */
type State =
  | { kind: "loading" }
  | { kind: "error"; message: string }
  | { kind: "ready"; health: Health };

function StatusDot({ ok }: { ok: boolean }) {
  return (
    <span
      aria-hidden="true"
      className={`inline-block h-2.5 w-2.5 rounded-full ${ok ? "bg-ok" : "bg-error"}`}
    />
  );
}

export default function App() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    // AbortController : annule la requête si le composant disparaît.
    const controller = new AbortController();
    fetch("/api/health", { signal: controller.signal })
      .then(async (response) => {
        // 503 renvoie aussi un JSON exploitable : on l'affiche.
        const health = (await response.json()) as Health;
        setState({ kind: "ready", health });
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          kind: "error",
          message: error instanceof Error ? error.message : "Erreur inconnue",
        });
      });
    return () => controller.abort();
  }, []);

  return (
    <main className="mx-auto flex min-h-dvh max-w-md flex-col gap-6 px-5 py-10">
      <header>
        <p className="text-sm font-medium uppercase tracking-widest text-accent">Étape 0</p>
        <h1 className="mt-1 text-3xl font-bold">SuperTracker</h1>
        <p className="mt-2 text-muted">
          Séries, animes, films, livres et jeux vidéo, réunis au même endroit.
        </p>
      </header>

      <section
        aria-labelledby="etat-titre"
        className="rounded-2xl border border-border bg-surface p-5"
      >
        <h2 id="etat-titre" className="text-lg font-semibold">
          État de l'API
        </h2>

        {/* aria-live : les lecteurs d'écran annoncent le changement d'état. */}
        <div aria-live="polite" className="mt-3">
          {state.kind === "loading" && (
            <p className="animate-pulse text-muted">Vérification en cours…</p>
          )}

          {state.kind === "error" && (
            <p role="alert" className="text-error">
              Impossible de joindre l'API ({state.message}). Vérifiez que « docker compose up »
              est bien lancé.
            </p>
          )}

          {state.kind === "ready" && (
            <ul className="space-y-2">
              <li className="flex items-center gap-2">
                <StatusDot ok={state.health.status === "ok"} />
                {state.health.status === "ok" ? "Opérationnelle" : "Dégradée"} (v
                {state.health.version})
              </li>
              <li className="flex items-center gap-2">
                <StatusDot ok={state.health.database} /> Base de données PostgreSQL
              </li>
              <li className="flex items-center gap-2">
                <StatusDot ok={state.health.redis} /> Cache Redis
              </li>
            </ul>
          )}
        </div>
      </section>

      <a
        href="/api/docs"
        className="rounded-xl bg-accent px-4 py-3 text-center font-semibold text-white hover:opacity-90"
      >
        Ouvrir la documentation de l'API
      </a>
    </main>
  );
}
