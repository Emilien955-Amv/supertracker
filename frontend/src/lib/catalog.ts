/** Types du catalogue : miroir des modèles du backend (app/providers/base.py). */

export type Source = "tmdb" | "anilist";
export type ContentKind = "movie" | "series" | "anime";

export type SearchResult = {
  source: Source;
  kind: ContentKind;
  external_id: string;
  title: string;
  original_title: string | null;
  year: number | null;
  poster_url: string | null;
  overview: string | null;
};

export type SearchResponse = {
  query: string;
  results: SearchResult[];
  unavailable_sources: Source[];
};

export type SeasonSummary = {
  number: number;
  name: string;
  episode_count: number | null;
  air_date: string | null;
  poster_url: string | null;
};

export type WatchProvider = { name: string; logo_url: string | null };

/** Où regarder (données JustWatch transmises par TMDB). */
export type WatchAvailability = {
  region: string;
  link: string | null;
  subscription: WatchProvider[];
  free: WatchProvider[];
  rent: WatchProvider[];
  buy: WatchProvider[];
};

export type ContentDetail = SearchResult & {
  backdrop_url: string | null;
  genres: string[];
  release_date: string | null;
  end_date: string | null;
  runtime_minutes: number | null;
  status: string | null;
  seasons_count: number | null;
  episodes_count: number | null;
  seasons: SeasonSummary[];
  source_url: string;
  watch: WatchAvailability | null;
};

export const KIND_LABELS: Record<ContentKind, string> = {
  movie: "Film",
  series: "Série",
  anime: "Anime",
};

export const SOURCE_LABELS: Record<Source, string> = {
  tmdb: "TMDB",
  anilist: "AniList",
};

/** Adresse de la fiche d'un contenu dans l'application. */
export function contentPath(item: Pick<SearchResult, "source" | "kind" | "external_id">): string {
  return `/contenu/${item.source}/${item.kind}/${item.external_id}`;
}

/** « 2026-11-05 » → « 5 novembre 2026 ». */
export function formatDate(value: string | null): string | null {
  if (!value) return null;
  return new Date(`${value}T00:00:00`).toLocaleDateString("fr-FR", {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
}

/** 136 → « 2 h 16 min ». */
export function formatRuntime(minutes: number | null): string | null {
  if (!minutes) return null;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  if (hours === 0) return `${rest} min`;
  return rest === 0 ? `${hours} h` : `${hours} h ${String(rest).padStart(2, "0")} min`;
}
