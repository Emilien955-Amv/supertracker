import { useCallback, useEffect, useState } from "react";

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
  /** Change quand les épisodes ont été modifiés ailleurs (ex. statut « Terminé »). */
  refreshKey?: number;
};

/** Dernière action, pour pouvoir l'annuler (erreur de clic). */
type Undo = { ids: number[]; watched: boolean };
const UNDO_MS = 10_000;

/** Liste des saisons ; chacune se déplie pour cocher ses épisodes. */
export function SeasonsTracker({ path, seasons, onStateChange, refreshKey = 0 }: Props) {
  // Incrémenté après une action sur plusieurs saisons : les saisons ouvertes
  // se rechargent pour afficher les bonnes cases.
  const [version, setVersion] = useState(0);
  const [undo, setUndo] = useState<Undo | null>(null);
  const [undoError, setUndoError] = useState<string | null>(null);
  const firstSeason = Math.min(...seasons.map((s) => s.number).filter((n) => n > 0));

  useEffect(() => {
    if (refreshKey > 0) setVersion((v) => v + 1);
  }, [refreshKey]);

  useEffect(() => {
    if (!undo) return;
    const timer = setTimeout(() => setUndo(null), UNDO_MS);
    return () => clearTimeout(timer);
  }, [undo]);

  const changed = useCallback(
    (state: ContentState, watched: boolean, reloadAll: boolean) => {
      onStateChange(state);
      announceRewards(state.rewards);
      const ids = state.changed_episode_ids ?? [];
      setUndo(ids.length ? { ids, watched } : null);
      if (reloadAll) setVersion((v) => v + 1);
    },
    [onStateChange],
  );

  async function cancel() {
    if (!undo) return;
    setUndoError(null);
    try {
      const state = await apiFetch<ContentState>(`${path}/episodes`, {
        method: "POST",
        body: { episode_ids: undo.ids, watched: !undo.watched },
      });
      onStateChange(state);
      setUndo(null);
      setVersion((v) => v + 1);
    } catch (err) {
      setUndoError(err instanceof Error ? err.message : "Échec de l'annulation.");
    }
  }

  return (
    <section aria-labelledby="saisons" className="mt-8">
      <h2 id="saisons" className="text-lg font-semibold">
        Saisons et épisodes
      </h2>
      {undo && (
        <div
          role="status"
          className="sticky top-2 z-10 mt-3 flex items-center justify-between gap-3 rounded-xl border border-accent/50 bg-surface p-3 text-sm shadow-lg"
        >
          <span>
            {undo.ids.length} épisode{undo.ids.length > 1 ? "s" : ""} marqué
            {undo.ids.length > 1 ? "s" : ""} comme {undo.watched ? "vu" : "pas vu"}
            {undo.ids.length > 1 ? "s" : ""}.
          </span>
          <button
            type="button"
            onClick={() => void cancel()}
            className="shrink-0 rounded-lg bg-accent px-3 py-1.5 font-semibold text-white"
          >
            Annuler
          </button>
        </div>
      )}
      {undoError && (
        <p role="alert" className="mt-2 text-sm text-error">
          {undoError}
        </p>
      )}
      <ul className="mt-3 divide-y divide-border rounded-xl border border-border bg-surface">
        {seasons.map((season) => (
          <li key={season.number}>
            <Season
              path={path}
              season={season}
              isFirst={season.number === firstSeason}
              version={version}
              onChanged={changed}
            />
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
  isFirst,
  version,
  onChanged,
}: {
  path: string;
  season: SeasonSummary;
  /** Première saison (hors épisodes spéciaux) : pas de « vu jusqu'ici » au 1er épisode. */
  isFirst: boolean;
  version: number;
  onChanged: (state: ContentState, watched: boolean, reloadAll: boolean) => void;
}) {
  const [load, setLoad] = useState<Load>({ status: "idle" });
  const [visible, setVisible] = useState(PAGE_SIZE);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const loaded = load.status === "ready";

  // Action sur plusieurs saisons ailleurs : on recharge si déjà ouverte.
  useEffect(() => {
    if (version === 0 || !loaded) return;
    apiFetch<EpisodeRead[]>(`${path}/seasons/${season.number}`)
      .then((episodes) => setLoad({ status: "ready", episodes }))
      .catch(() => undefined); // l'affichage actuel reste valable
    // eslint-disable-next-line react-hooks/exhaustive-deps -- seulement quand version change
  }, [version]);

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
      onChanged(state, watched, false);
    } catch (err) {
      setLoad({ status: "ready", episodes: previous });
      setError(err instanceof Error ? err.message : "Échec de l'enregistrement.");
    }
  }

  /** « Vu jusqu'ici » (saisons précédentes comprises) ou « pas vu à partir d'ici ». */
  async function until(episode: EpisodeRead, watched: boolean) {
    setBusy(true);
    setError(null);
    try {
      const state = await apiFetch<ContentState>(`${path}/watched-until`, {
        method: "POST",
        body: { season_number: season.number, episode_number: episode.number, watched },
      });
      onChanged(state, watched, true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'enregistrement.");
    } finally {
      setBusy(false);
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
                // Saison spéciale (0) : pas de « jusqu'ici », l'ordre n'a pas de sens.
                const special = season.number === 0;
                const canWatchUntil = !special && !episode.watched && !(isFirst && index === 0);
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
                    {/* « Vu jusqu'ici » : rattrape tout, saisons précédentes comprises. */}
                    {canWatchUntil && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void until(episode, true)}
                        aria-label={`Marquer comme vus tous les épisodes jusqu'à la saison ${season.number}, épisode ${episode.number}`}
                        className="shrink-0 rounded-md px-2 py-1 text-xs text-accent hover:bg-accent/10 disabled:opacity-40"
                      >
                        Vu jusqu'ici
                      </button>
                    )}
                    {/* Erreur de clic : décoche cet épisode et tous les suivants. */}
                    {!special && episode.watched && (
                      <button
                        type="button"
                        disabled={busy}
                        onClick={() => void until(episode, false)}
                        aria-label={`Marquer comme pas vus tous les épisodes à partir de la saison ${season.number}, épisode ${episode.number}`}
                        className="shrink-0 rounded-md px-2 py-1 text-xs text-muted hover:bg-bg hover:text-error disabled:opacity-40"
                      >
                        Pas vu à partir d'ici
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
