import { useState } from "react";
import { Link } from "react-router";

import { KIND_LABELS } from "../lib/catalog";
import type { ContentKind } from "../lib/catalog";
import type { BinderEntry } from "../lib/cards";
import { useApi } from "../lib/useApi";
import { Poster } from "./Poster";
import { ProgressBar } from "./ProgressBar";

type KindFilter = ContentKind | "all";
type Sort = "alpha" | "complete" | "owned";

const KIND_TABS: { value: KindFilter; label: string }[] = [
  { value: "all", label: "Tout" },
  { value: "anime", label: "Animes" },
  { value: "movie", label: "Films" },
  { value: "series", label: "Séries" },
];

const SORTS: Record<Sort, string> = {
  alpha: "De A à Z",
  complete: "Les plus complètes",
  owned: "Le plus de cartes",
};

/** Normalise un texte pour la recherche : « Pokémon » trouve « pokemon ». */
function normalize(text: string): string {
  return text
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase();
}

/** Le filtre « Films » inclut les sagas (Harry Potter, Star Wars…). */
function matchesKind(kind: ContentKind, filter: KindFilter): boolean {
  if (filter === "all") return true;
  return filter === "movie" ? kind === "movie" || kind === "saga" : kind === filter;
}

/** Classeur : une pochette par œuvre, filtrable par catégorie et par nom. */
export function Binder() {
  const state = useApi<BinderEntry[]>("/api/cards/binder");
  const [kind, setKind] = useState<KindFilter>("all");
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<Sort>("alpha");

  if (state.status === "idle" || state.status === "loading") {
    return <p className="mt-6 text-muted">Chargement du classeur…</p>;
  }
  if (state.status === "error") {
    return (
      <p role="alert" className="mt-6 text-error">
        {state.error.message}
      </p>
    );
  }

  const entries = state.data;
  const needle = normalize(search.trim());
  const visible = entries
    .filter((e) => matchesKind(e.content.kind, kind))
    .filter((e) => !needle || normalize(e.content.title).includes(needle))
    .sort((a, b) => {
      if (sort === "complete") return b.owned / b.total - a.owned / a.total;
      if (sort === "owned") return b.owned - a.owned;
      return 0; // déjà triées de A à Z par le serveur
    });
  const count = (k: KindFilter) => entries.filter((e) => matchesKind(e.content.kind, k)).length;

  return (
    <section aria-labelledby="classeur" className="mt-8">
      <h2 id="classeur" className="text-lg font-semibold">
        📒 Mon classeur
      </h2>
      {entries.length === 0 ? (
        <p className="mt-3 rounded-xl border border-border bg-surface p-6 text-center text-muted">
          Ouvrez un booster pour commencer votre collection de personnages !
        </p>
      ) : (
        <>
          <div role="group" aria-label="Catégorie" className="mt-3 flex flex-wrap gap-2">
            {KIND_TABS.map((tab) => (
              <button
                key={tab.value}
                type="button"
                aria-pressed={kind === tab.value}
                onClick={() => setKind(tab.value)}
                className={`rounded-full px-3 py-1.5 text-sm ${kind === tab.value ? "bg-accent font-semibold text-white" : "border border-border hover:bg-surface"}`}
              >
                {tab.label} <span className="opacity-70">{count(tab.value)}</span>
              </button>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <label className="min-w-0 flex-1 basis-full sm:basis-0">
              <span className="sr-only">Rechercher une œuvre</span>
              <input
                type="search"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Rechercher une série, un film…"
                className="block w-full rounded-xl border border-border bg-surface px-3 py-2"
              />
            </label>
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted">Tri</span>
              <select
                value={sort}
                onChange={(e) => setSort(e.target.value as Sort)}
                className="rounded-lg border border-border bg-bg px-2 py-2"
              >
                {(Object.keys(SORTS) as Sort[]).map((value) => (
                  <option key={value} value={value}>
                    {SORTS[value]}
                  </option>
                ))}
              </select>
            </label>
          </div>

          <p className="mt-3 text-sm text-muted" aria-live="polite">
            {visible.length} œuvre{visible.length > 1 ? "s" : ""}
          </p>
          <ul className="mt-2 grid grid-cols-3 gap-3 sm:grid-cols-5">
            {visible.map(({ content, owned, total, mastered }) => (
              <li key={content.id}>
                <Link
                  to={`/cartes/oeuvre/${content.id}`}
                  className="block rounded-xl border border-border bg-surface p-1.5 hover:border-accent/60"
                >
                  <Poster url={content.poster_url} title={content.title} className="rounded-lg text-[9px]" />
                  <p className="mt-1 truncate text-xs font-semibold">
                    {mastered && (
                      <span title="Collection complète" aria-label="Collection complète">
                        🏆{" "}
                      </span>
                    )}
                    {content.title}
                  </p>
                  <p className="text-[10px] text-muted">
                    {KIND_LABELS[content.kind]} · {owned}/{total}
                  </p>
                  <ProgressBar
                    percent={Math.round((100 * owned) / total)}
                    label={`Collection ${content.title}`}
                  />
                </Link>
              </li>
            ))}
          </ul>
        </>
      )}
    </section>
  );
}
