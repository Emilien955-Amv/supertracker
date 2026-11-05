import { Link, useSearchParams } from "react-router";

import { Attribution } from "../components/Attribution";
import { Poster } from "../components/Poster";
import { KIND_LABELS, SOURCE_LABELS, contentPath } from "../lib/catalog";
import type { SearchResponse } from "../lib/catalog";
import { useApi, useDebouncedValue } from "../lib/useApi";

const MIN_LENGTH = 2;

export default function SearchPage() {
  // La recherche est gardée dans l'adresse (?q=…) : le bouton « retour » du
  // navigateur retrouve les résultats, et on peut partager le lien.
  const [params, setParams] = useSearchParams();
  const query = params.get("q") ?? "";
  const debounced = useDebouncedValue(query.trim(), 400);

  const path =
    debounced.length >= MIN_LENGTH
      ? `/api/catalog/search?q=${encodeURIComponent(debounced)}`
      : null;
  const state = useApi<SearchResponse>(path);

  return (
    <main className="mx-auto max-w-3xl px-5 pt-8">
      <h1 className="text-2xl font-bold">Recherche</h1>

      <form role="search" onSubmit={(e) => e.preventDefault()} className="mt-4">
        <label htmlFor="recherche" className="sr-only">
          Rechercher un film, une série ou un anime
        </label>
        <input
          id="recherche"
          type="search"
          autoFocus
          autoComplete="off"
          placeholder="Film, série, anime…"
          value={query}
          onChange={(e) => setParams(e.target.value ? { q: e.target.value } : {}, { replace: true })}
          className="w-full rounded-xl border border-border bg-surface px-4 py-3 text-lg placeholder:text-muted/60 focus:border-accent focus:outline-none"
        />
      </form>

      <section aria-live="polite" aria-busy={state.status === "loading"} className="mt-6">
        {state.status === "idle" && (
          <p className="text-muted">
            {query.trim().length > 0 && query.trim().length < MIN_LENGTH
              ? `Tapez au moins ${MIN_LENGTH} caractères.`
              : "Cherchez parmi des centaines de milliers de films, séries et animes."}
          </p>
        )}

        {state.status === "loading" && <ResultsSkeleton />}

        {state.status === "error" && (
          <p role="alert" className="rounded-xl border border-error/40 bg-error/10 p-3 text-error">
            {state.error.message}
          </p>
        )}

        {state.status === "success" && (
          <>
            {state.data.unavailable_sources.length > 0 && (
              <p className="mb-4 rounded-xl border border-gold/40 bg-gold/10 p-3 text-sm text-gold">
                Résultats partiels :{" "}
                {state.data.unavailable_sources.map((s) => SOURCE_LABELS[s]).join(", ")} ne répond
                pas pour le moment.
              </p>
            )}
            {state.data.results.length === 0 ? (
              <p className="text-muted">Aucun résultat pour « {state.data.query} ».</p>
            ) : (
              <>
                <p className="sr-only">{state.data.results.length} résultats</p>
                <ul className="grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 md:grid-cols-5">
                  {state.data.results.map((item) => (
                    <li key={`${item.source}-${item.kind}-${item.external_id}`}>
                      <Link to={contentPath(item)} className="group block rounded-xl">
                        <div className="relative">
                          <Poster url={item.poster_url} title={item.title} className="group-hover:opacity-80" />
                          <span className="absolute left-1.5 top-1.5 rounded-md bg-bg/85 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide">
                            {KIND_LABELS[item.kind]}
                          </span>
                        </div>
                        <p className="mt-2 line-clamp-2 text-sm font-medium leading-tight">{item.title}</p>
                        {item.year && <p className="text-xs text-muted">{item.year}</p>}
                      </Link>
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}
      </section>

      <Attribution />
    </main>
  );
}

/** Silhouettes grises pendant le chargement : la page ne « saute » pas. */
function ResultsSkeleton() {
  return (
    <ul aria-hidden="true" className="grid grid-cols-3 gap-x-3 gap-y-5 sm:grid-cols-4 md:grid-cols-5">
      {Array.from({ length: 9 }, (_, i) => (
        <li key={i} className="animate-pulse motion-reduce:animate-none">
          <div className="aspect-[2/3] rounded-xl bg-border" />
          <div className="mt-2 h-3 w-4/5 rounded bg-border" />
        </li>
      ))}
    </ul>
  );
}
