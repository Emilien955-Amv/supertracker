import { Link, useSearchParams } from "react-router";

import { Poster } from "../components/Poster";
import { ProgressBar } from "../components/ProgressBar";
import { KIND_LABELS, contentPath } from "../lib/catalog";
import { STATUSES, STATUS_COLORS, STATUS_LABELS } from "../lib/tracking";
import type { TrackedItem, TrackingStatus } from "../lib/tracking";
import { useApi } from "../lib/useApi";

/** « Mon suivi » : tous les contenus suivis, filtrables par statut. */
export default function TrackingListPage() {
  const [params] = useSearchParams();
  const raw = params.get("statut");
  const filter = STATUSES.includes(raw as TrackingStatus) ? (raw as TrackingStatus) : null;
  const state = useApi<TrackedItem[]>(filter ? `/api/tracking?status=${filter}` : "/api/tracking");

  const tabs: { value: TrackingStatus | null; label: string }[] = [
    { value: null, label: "Tous" },
    ...STATUSES.map((value) => ({ value, label: STATUS_LABELS[value] })),
  ];

  return (
    <main className="mx-auto max-w-3xl px-5 pt-8">
      <h1 className="text-2xl font-bold">Mon suivi</h1>

      {/* Filtres dans l'adresse (?statut=watching) : partageables et gardés au retour arrière. */}
      <nav aria-label="Filtrer par statut" className="-mx-5 mt-4 overflow-x-auto px-5">
        <ul className="flex gap-2">
          {tabs.map((tab) => (
            <li key={tab.label} className="shrink-0">
              <Link
                to={tab.value ? `/suivi?statut=${tab.value}` : "/suivi"}
                aria-current={tab.value === filter ? "page" : undefined}
                className={`block rounded-full border px-3 py-1.5 text-sm ${
                  tab.value === filter
                    ? "border-accent bg-accent font-semibold text-white"
                    : "border-border hover:bg-surface"
                }`}
              >
                {tab.label}
              </Link>
            </li>
          ))}
        </ul>
      </nav>

      <div className="mt-6" aria-live="polite" aria-busy={state.status === "loading"}>
        {state.status === "loading" && <p className="text-muted">Chargement…</p>}
        {state.status === "error" && (
          <p role="alert" className="rounded-xl border border-error/40 bg-error/10 p-4 text-error">
            {state.error.message}
          </p>
        )}
        {state.status === "success" && state.data.length === 0 && (
          <div className="rounded-xl border border-border bg-surface p-6 text-center">
            <p className="text-muted">Rien ici pour le moment.</p>
            <Link to="/recherche" className="mt-3 inline-block text-accent hover:underline">
              Trouver un contenu à suivre →
            </Link>
          </div>
        )}
        {state.status === "success" && state.data.length > 0 && (
          <ul className="space-y-3">
            {state.data.map((item) => (
              <li key={item.content.id}>
                <TrackedRow item={item} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}

function TrackedRow({ item }: { item: TrackedItem }) {
  const { content, tracking, progress } = item;
  const isMovie = content.kind === "movie";
  return (
    <Link
      to={contentPath(content)}
      className="flex gap-3 rounded-xl border border-border bg-surface p-3 hover:border-accent/60"
    >
      <div className="w-14 shrink-0">
        <Poster url={content.poster_url} title={content.title} className="rounded-lg text-[8px]" />
      </div>
      <div className="min-w-0 flex-1">
        <p className="truncate font-semibold">{content.title}</p>
        <p className="text-xs text-muted">
          {KIND_LABELS[content.kind]}
          {content.year && ` · ${content.year}`}
          {tracking.rating && ` · ★ ${tracking.rating}/10`}
        </p>
        <span
          className={`mt-1.5 inline-block rounded-full px-2 py-0.5 text-xs ${STATUS_COLORS[tracking.status]}`}
        >
          {isMovie && tracking.status === "completed" ? "Vu" : STATUS_LABELS[tracking.status]}
        </span>
        {!isMovie && (
          <div className="mt-2 flex items-center gap-2">
            <ProgressBar percent={progress.percent ?? 0} label={`Progression de ${content.title}`} />
            <span className="shrink-0 text-xs text-muted">
              {progress.total ? `${progress.watched}/${progress.total}` : `${progress.watched} vus`}
            </span>
          </div>
        )}
      </div>
    </Link>
  );
}
