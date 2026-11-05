import { useEffect, useState } from "react";

import { apiFetch } from "../lib/api";
import { announceRewards } from "../lib/gamification";
import { STATUSES, STATUS_LABELS } from "../lib/tracking";
import type { ContentState, TrackingStatus } from "../lib/tracking";
import { ProgressBar } from "./ProgressBar";

type Props = {
  /** Adresse de l'API de suivi de ce contenu (voir trackingPath). */
  path: string;
  state: ContentState;
  onChange: (state: ContentState) => void;
  isMovie: boolean;
};

/** Bloc « Mon suivi » de la fiche : statut, progression, note et avis. */
export function TrackingPanel({ path, state, onChange, isMovie }: Props) {
  const tracking = state.tracking;
  // Brouillon de la note et de l'avis, enregistré seulement sur demande.
  const [rating, setRating] = useState(tracking?.rating ?? null);
  const [review, setReview] = useState(tracking?.review ?? "");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{ kind: "ok" | "error"; text: string } | null>(null);

  // Le suivi peut changer ailleurs (ex. épisodes cochés) : on resynchronise.
  useEffect(() => {
    setRating(tracking?.rating ?? null);
    setReview(tracking?.review ?? "");
  }, [tracking?.rating, tracking?.review]);

  const dirty = (tracking?.rating ?? null) !== rating || (tracking?.review ?? "") !== review;

  async function save(status: TrackingStatus, confirmation: string) {
    setBusy(true);
    setMessage(null);
    try {
      const next = await apiFetch<ContentState>(path, {
        method: "PUT",
        body: { status, rating, review: review.trim() || null },
      });
      onChange(next);
      announceRewards(next.rewards);
      setMessage({ kind: "ok", text: confirmation });
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Échec." });
    } finally {
      setBusy(false);
    }
  }

  async function remove() {
    if (!window.confirm("Retirer ce contenu de votre suivi ? Les épisodes cochés seront oubliés.")) {
      return;
    }
    setBusy(true);
    setMessage(null);
    try {
      await apiFetch<void>(path, { method: "DELETE" });
      onChange({ ...state, tracking: null, progress: { ...state.progress, watched: 0, percent: 0 } });
      setMessage({ kind: "ok", text: "Retiré de votre suivi." });
    } catch (error) {
      setMessage({ kind: "error", text: error instanceof Error ? error.message : "Échec." });
    } finally {
      setBusy(false);
    }
  }

  const { watched, total, percent } = state.progress;

  return (
    <section aria-labelledby="mon-suivi" className="mt-6 rounded-xl border border-border bg-surface p-4">
      <h2 id="mon-suivi" className="text-lg font-semibold">
        Mon suivi
      </h2>

      {!isMovie && tracking && (
        <div className="mt-3 space-y-1">
          <ProgressBar percent={percent ?? 0} label="Progression" />
          <p className="text-sm text-muted">
            {total ? `${watched} / ${total} épisodes vus` : `${watched} épisodes vus`}
            {percent !== null && ` · ${percent} %`}
          </p>
        </div>
      )}

      <fieldset className="mt-3" disabled={busy}>
        <legend className="sr-only">Statut</legend>
        <div className="flex flex-wrap gap-2">
          {STATUSES.map((status) => {
            const active = tracking?.status === status;
            return (
              <button
                key={status}
                type="button"
                aria-pressed={active}
                onClick={() =>
                  void save(status, tracking ? "Statut mis à jour." : "Ajouté à votre suivi.")
                }
                className={`rounded-full border px-3 py-1.5 text-sm ${
                  active
                    ? "border-accent bg-accent font-semibold text-white"
                    : "border-border hover:bg-bg"
                }`}
              >
                {isMovie && status === "completed" ? "Vu" : STATUS_LABELS[status]}
              </button>
            );
          })}
        </div>
      </fieldset>

      {tracking && (
        <form
          className="mt-4 space-y-3"
          onSubmit={(event) => {
            event.preventDefault();
            void save(tracking.status, "Note et avis enregistrés.");
          }}
        >
          <label className="block text-sm">
            <span className="text-muted">Ma note</span>
            <select
              value={rating ?? ""}
              onChange={(event) => setRating(event.target.value ? Number(event.target.value) : null)}
              className="mt-1 block rounded-lg border border-border bg-bg px-3 py-2"
            >
              <option value="">Pas de note</option>
              {Array.from({ length: 10 }, (_, i) => 10 - i).map((value) => (
                <option key={value} value={value}>
                  {value} / 10
                </option>
              ))}
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-muted">Mon avis (privé)</span>
            <textarea
              value={review}
              onChange={(event) => setReview(event.target.value)}
              maxLength={5000}
              rows={3}
              placeholder="Ce que vous en avez pensé…"
              className="mt-1 block w-full rounded-lg border border-border bg-bg px-3 py-2"
            />
          </label>
          <div className="flex flex-wrap items-center justify-between gap-3">
            <button
              type="submit"
              disabled={!dirty || busy}
              className="rounded-xl bg-accent px-4 py-2 font-semibold text-white disabled:opacity-40"
            >
              Enregistrer
            </button>
            <button
              type="button"
              onClick={() => void remove()}
              disabled={busy}
              className="text-sm text-muted underline-offset-4 hover:text-error hover:underline"
            >
              Retirer de mon suivi
            </button>
          </div>
        </form>
      )}

      <p
        aria-live="polite"
        className={`mt-2 min-h-5 text-sm ${message?.kind === "error" ? "text-error" : "text-ok"}`}
      >
        {message?.text}
      </p>
    </section>
  );
}
