import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { Attribution } from "../components/Attribution";
import { LibraryPicker } from "../components/LibraryPicker";
import { Poster } from "../components/Poster";
import { SeasonsTracker } from "../components/SeasonsTracker";
import { TrackingPanel } from "../components/TrackingPanel";
import { WatchProviders } from "../components/WatchProviders";
import { ApiError } from "../lib/api";
import { KIND_LABELS, SOURCE_LABELS, contentPath, formatDate, formatRuntime } from "../lib/catalog";
import type { ContentDetail, ContentKind, Source } from "../lib/catalog";
import { trackingPath } from "../lib/tracking";
import type { ContentState } from "../lib/tracking";
import { useApi, useApiResource } from "../lib/useApi";

export default function ContentPage() {
  const { source, kind, id } = useParams();
  const navigate = useNavigate();
  const state = useApi<ContentDetail>(`/api/catalog/${source}/${kind}/${id}`);
  // Identité du contenu telle que l'API l'attend (sans le reste de la fiche).
  const ref = { source: source as Source, kind: kind as ContentKind, external_id: id ?? "" };
  const apiPath = trackingPath(ref);
  // Où en est l'utilisateur : chargé en parallèle de la fiche.
  const [tracking, setTracking] = useApiResource<ContentState>(apiPath);
  // Incrémenté quand le statut coche des épisodes (« Terminé ») : les saisons
  // affichées se mettent à jour.
  const [episodesVersion, setEpisodesVersion] = useState(0);

  const back = (
    <button
      type="button"
      onClick={() => navigate(-1)}
      className="rounded-xl bg-bg/80 px-3 py-2 text-sm backdrop-blur hover:bg-surface"
    >
      ← Retour
    </button>
  );

  if (state.status === "idle" || state.status === "loading") {
    return (
      <main className="mx-auto max-w-3xl px-5 pt-6" aria-busy="true">
        {back}
        <div className="mt-6 flex animate-pulse gap-4 motion-reduce:animate-none">
          <div className="aspect-[2/3] w-32 rounded-xl bg-border" />
          <div className="flex-1 space-y-3">
            <div className="h-6 w-3/4 rounded bg-border" />
            <div className="h-4 w-1/2 rounded bg-border" />
          </div>
        </div>
        <p className="sr-only">Chargement de la fiche…</p>
      </main>
    );
  }

  if (state.status === "error") {
    const notFound = state.error instanceof ApiError && [404, 422].includes(state.error.status);
    return (
      <main className="mx-auto max-w-3xl px-5 pt-6">
        {back}
        <p role="alert" className="mt-6 rounded-xl border border-error/40 bg-error/10 p-4 text-error">
          {notFound ? "Ce contenu est introuvable." : state.error.message}
        </p>
      </main>
    );
  }

  const content = state.data;
  const facts = [
    { label: "Sortie", value: formatDate(content.release_date) },
    { label: "Fin", value: formatDate(content.end_date) },
    { label: "Statut", value: content.status },
    { label: content.kind === "movie" ? "Durée" : "Durée d'un épisode", value: formatRuntime(content.runtime_minutes) },
    { label: "Saisons", value: content.seasons_count?.toString() ?? null },
    { label: "Épisodes", value: content.episodes_count?.toString() ?? null },
  ].filter((fact) => fact.value);

  return (
    <main className="mx-auto max-w-3xl">
      {/* Bandeau : image de fond assombrie vers le bas pour garder le texte lisible. */}
      <div className="relative h-48 overflow-hidden sm:h-64">
        {content.backdrop_url && (
          <img src={content.backdrop_url} alt="" className="h-full w-full object-cover" />
        )}
        <div className="absolute inset-0 bg-gradient-to-b from-bg/30 to-bg" />
        <div className="absolute left-5 top-5">{back}</div>
      </div>

      <div className="relative -mt-24 px-5">
        <div className="flex items-end gap-4">
          <div className="w-28 shrink-0 shadow-xl sm:w-36">
            <Poster url={content.poster_url} title={content.title} />
          </div>
          <div className="pb-1">
            <p className="text-xs font-semibold uppercase tracking-widest text-accent">
              {KIND_LABELS[content.kind]}
              {content.year && ` · ${content.year}`}
            </p>
            <h1 className="mt-1 text-2xl font-bold leading-tight sm:text-3xl">{content.title}</h1>
            {content.original_title && (
              <p className="mt-1 text-sm text-muted" lang="und">
                {content.original_title}
              </p>
            )}
          </div>
        </div>

        {content.kind === "saga" && content.parts && content.parts.length > 0 && (
          <section aria-labelledby="films-saga" className="mt-6">
            <h2 id="films-saga" className="text-lg font-semibold">
              Les {content.parts.length} films de la saga
            </h2>
            <ul className="mt-3 grid grid-cols-3 gap-3 sm:grid-cols-5">
              {content.parts.map((part) => (
                <li key={part.external_id}>
                  <Link to={contentPath(part)} className="block">
                    <Poster url={part.poster_url} title={part.title} />
                    <p className="mt-1 line-clamp-2 text-xs">{part.title}</p>
                    {part.year && <p className="text-[11px] text-muted">{part.year}</p>}
                  </Link>
                </li>
              ))}
            </ul>
            <p className="mt-2 text-xs text-muted">
              Suivez chaque film depuis sa propre fiche. Les cartes, elles, regroupent toute la saga.
            </p>
          </section>
        )}

        {tracking.status === "success" && content.kind !== "saga" && (
          <>
            <TrackingPanel
              path={apiPath}
              state={tracking.data}
              onChange={(next) => {
                setTracking(next);
                if (next.changed_episode_ids?.length) setEpisodesVersion((v) => v + 1);
              }}
              isMovie={content.kind === "movie"}
            />
            <LibraryPicker
              content={ref}
              contentId={tracking.data.content_id}
              onContentId={(contentId) => setTracking({ ...tracking.data, content_id: contentId })}
            />
          </>
        )}

        {content.genres.length > 0 && (
          <ul aria-label="Genres" className="mt-5 flex flex-wrap gap-2">
            {content.genres.map((genre) => (
              <li key={genre} className="rounded-full border border-border px-3 py-1 text-xs">
                {genre}
              </li>
            ))}
          </ul>
        )}

        <section aria-labelledby="synopsis" className="mt-6">
          <h2 id="synopsis" className="text-lg font-semibold">
            Synopsis
          </h2>
          <p className="mt-2 whitespace-pre-line leading-relaxed text-text/90">
            {content.overview ?? "Aucun synopsis disponible pour le moment."}
          </p>
        </section>

        {facts.length > 0 && (
          <dl className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
            {facts.map((fact) => (
              <div key={fact.label} className="rounded-xl border border-border bg-surface p-3">
                <dt className="text-xs text-muted">{fact.label}</dt>
                <dd className="mt-0.5 font-medium">{fact.value}</dd>
              </div>
            ))}
          </dl>
        )}

        {/* Absent pour les sources qui ne fournissent pas l'information (AniList). */}
        {content.watch && <WatchProviders watch={content.watch} />}

        {content.seasons.length > 0 && (
          <SeasonsTracker
            path={apiPath}
            seasons={content.seasons}
            onStateChange={setTracking}
            refreshKey={episodesVersion}
          />
        )}

        <a
          href={content.source_url}
          target="_blank"
          rel="noreferrer"
          className="mt-8 inline-block text-sm text-accent underline-offset-4 hover:underline"
        >
          Voir sur {SOURCE_LABELS[content.source]} ↗
        </a>

        <Attribution />
      </div>
    </main>
  );
}
