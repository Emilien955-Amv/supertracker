import { useState } from "react";

import { apiFetch } from "../lib/api";
import { formatDate } from "../lib/catalog";
import { announceRewards } from "../lib/gamification";
import type { SeasonSummary } from "../lib/catalog";
import type { ContentState, EpisodeRead } from "../lib/tracking";
import { Poster } from "./Poster";

// Au-delà, on affiche les épisodes par paquets (One Piece en compte plus de 1 100).
const PAGE_SIZE = 100;

type Props = {
  path: string;
  seasons: SeasonSummary[];
  onStateChange: (state: ContentState) => void;
};

/** Liste des saisons ; chacune se déplie pour cocher ses épisodes. */
export function SeasonsTracker({ path, seasons, onStateChange }: Props) {
  return (
    <section aria-labelledby="saisons" className="mt-8">
      <h2 id="saisons" className="text-lg font-semibold">
        Saisons et épisodes
      </h2>
      <ul className="mt-3 divide-y divide-border rounded-xl border border-border bg-surface">
        {seasons.map((season) => (
          <li key={season.number}>
            <Season path={path} season={season} onStateChange={onStateChange} />
          </li>
        ))}
      </ul>
    </section>
  );
}

type Load =
  | { status: "idle" | "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; episodes: EpisodeRead[] };

function Season({
  path,
  season,
  onStateChange,
}: {
  path: string;
  season: SeasonSummary;
  onStateChange: (state: ContentState) => void;
}) {
  const [load, setLoad] = useState<Load>({ status: "idle" });
  const [visible, setVisible] = useState(PAGE_SIZE);
  const [error, setError] = useState<string | null>(null);

  async function open() {
    // Les épisodes ne sont chargés qu'à la première ouverture de la saison.
    if (load.status !== "idle" && load.status !== "error") return;
    setLoad({ status: "loading" });
    try {
      const episodes = await apiFetch<EpisodeRead[]>(`${path}/seasons/${season.number}`);
      setLoad({ status: "ready", episodes });
    } catch (err) {
      setLoad({ status: "error", message: err instanceof Error ? err.message : "Échec." });
    }
  }

  async function mark(ids: number[], watched: boolean) {
    if (load.status !== "ready" || ids.length === 0) return;
    const previous = load.episodes;
    // Mise à jour « optimiste » : la case se coche tout de suite, et on
    // revient en arrière si le serveur refuse.
    const changed = new Set(ids);
    setLoad({
      status: "ready",
      episodes: previous.map((e) => (changed.has(e.id) ? { ...e, watched } : e)),
    });
    setError(null);
    try {
      const state = await apiFetch<ContentState>(`${path}/episodes`, {
        method: "POST",
        body: { episode_ids: ids, watched },
      });
      onStateChange(state);
      announceRewards(state.rewards);
    } catch (err) {
      setLoad({ status: "ready", episodes: previous });
      setError(err instanceof Error ? err.message : "Échec de l'enregistrement.");
    }
  }

  const episodes = load.status === "ready" ? load.episodes : [];
  const watchedCount = episodes.filter((e) => e.watched).length;
  const allWatched = episodes.length > 0 && watchedCount === episodes.length;
  const today = new Date().toISOString().slice(0, 10);

  return (
    <details
      onToggle={(event) => {
        if (event.currentTarget.open) void open();
      }}
    >
      <summary className="flex cursor-pointer items-center gap-3 p-3 hover:bg-bg/50">
        <div className="w-12 shrink-0">
          <Poster url={season.poster_url} title={season.name} className="rounded-md text-[8px]" />
        </div>
        <div className="min-w-0 flex-1">
          <p className="font-medium">{season.name}</p>
          <p className="text-sm text-muted">
            {[
              season.episode_count !== null && `${season.episode_count} épisodes`,
              season.air_date && new Date(season.air_date).getFullYear(),
              load.status === "ready" && `${watchedCount} vus`,
            ]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        <span aria-hidden="true" className="text-muted">
          ▾
        </span>
      </summary>

      <div className="border-t border-border px-3 pb-3">
        {load.status === "loading" && (
          <p className="py-3 text-sm text-muted" aria-live="polite">
            Chargement des épisodes…
          </p>
        )}
        {load.status === "error" && (
          <p role="alert" className="py-3 text-sm text-error">
            {load.message}
          </p>
        )}
        {load.status === "ready" && episodes.length === 0 && (
          <p className="py-3 text-sm text-muted">Aucun épisode connu pour le moment.</p>
        )}
        {load.status === "ready" && episodes.length > 0 && (
          <>
            <div className="flex justify-end py-2">
              <button
                type="button"
                onClick={() => void mark(episodes.map((e) => e.id), !allWatched)}
                className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-bg"
              >
                {allWatched ? "Tout décocher" : "Tout marquer comme vu"}
              </button>
            </div>
            {error && (
              <p role="alert" className="pb-2 text-sm text-error">
                {error}
              </p>
            )}
            <ul className="space-y-1">
              {episodes.slice(0, visible).map((episode, index) => {
                const upcoming = episode.air_date !== null && episode.air_date > today;
                const before = episodes.slice(0, index + 1).filter((e) => !e.watched);
                return (
                  <li key={episode.id} className="flex items-center gap-3 rounded-lg px-1 py-1.5">
                    <input
                      id={`episode-${episode.id}`}
                      type="checkbox"
                      checked={episode.watched}
                      onChange={(event) => void mark([episode.id], event.target.checked)}
                      className="h-5 w-5 shrink-0 accent-accent"
                    />
                    <label htmlFor={`episode-${episode.id}`} className="min-w-0 flex-1 cursor-pointer">
                      <span className={episode.watched ? "text-muted line-through" : ""}>
                        <span className="font-medium">É{episode.number}</span>
                        {episode.title && ` · ${episode.title}`}
                      </span>
                      <span className="block text-xs text-muted">
                        {upcoming ? `À venir · ${formatDate(episode.air_date)}` : formatDate(episode.air_date)}
                      </span>
                    </label>
                    {/* « Vu jusqu'ici » : rattrape plusieurs épisodes d'un coup. */}
                    {!episode.watched && before.length > 1 && (
                      <button
                        type="button"
                        onClick={() => void mark(before.map((e) => e.id), true)}
                        aria-label={`Marquer comme vus tous les épisodes jusqu'au ${episode.number}`}
                        className="shrink-0 rounded-md px-2 py-1 text-xs text-accent hover:bg-accent/10"
                      >
                        Vu jusqu'ici
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
            {episodes.length > visible && (
              <button
                type="button"
                onClick={() => setVisible((v) => v + PAGE_SIZE)}
                className="mt-2 w-full rounded-lg border border-border py-2 text-sm hover:bg-bg"
              >
                Afficher les épisodes suivants ({episodes.length - visible} restants)
              </button>
            )}
          </>
        )}
      </div>
    </details>
  );
}
