/** Types du suivi et des bibliothèques : miroir des schémas du backend
 * (app/schemas/tracking.py et app/schemas/library.py). */

import type { ContentKind, Source } from "./catalog";
import type { Rewards } from "./gamification";

export type TrackingStatus = "planned" | "watching" | "completed" | "paused" | "dropped";

export const STATUS_LABELS: Record<TrackingStatus, string> = {
  planned: "À voir",
  watching: "En cours",
  completed: "Terminé",
  paused: "En pause",
  dropped: "Abandonné",
};

export const STATUSES = Object.keys(STATUS_LABELS) as TrackingStatus[];

/** Couleur associée à chaque statut (pastilles, barres de progression). */
export const STATUS_COLORS: Record<TrackingStatus, string> = {
  planned: "bg-muted/20 text-muted",
  watching: "bg-accent/20 text-accent",
  completed: "bg-ok/20 text-ok",
  paused: "bg-gold/20 text-gold",
  dropped: "bg-error/20 text-error",
};

export type ContentRead = {
  id: number;
  source: Source;
  kind: ContentKind;
  external_id: string;
  title: string;
  year: number | null;
  poster_url: string | null;
  episodes_count: number | null;
};

export type TrackingRead = {
  status: TrackingStatus;
  rating: number | null;
  review: string | null;
  started_at: string | null;
  completed_at: string | null;
  updated_at: string;
};

export type Progress = { watched: number; total: number | null; percent: number | null };

export type ContentState = {
  content_id: number | null;
  tracking: TrackingRead | null;
  progress: Progress;
  /** Ce que la dernière action a rapporté (absent en simple lecture). */
  rewards?: Rewards | null;
  /** Épisodes que l'action vient de modifier (pour l'annuler). */
  changed_episode_ids?: number[];
};

export type TrackedItem = { content: ContentRead; tracking: TrackingRead; progress: Progress };

export type EpisodeRead = {
  id: number;
  season_number: number;
  number: number;
  title: string | null;
  air_date: string | null;
  runtime_minutes: number | null;
  still_url: string | null;
  watched: boolean;
};

export type ViewMode = "bookcase" | "grid" | "shelf" | "list";
export type Wood = "oak" | "walnut" | "ebony" | "white";
export type ItemSize = "small" | "medium" | "large";
export type SortMode = "manual" | "alpha" | "category" | "recent";

export const VIEW_MODE_LABELS: Record<ViewMode, string> = {
  bookcase: "Meuble",
  grid: "Grille",
  shelf: "Étagère",
  list: "Liste",
};

export const SORT_MODE_LABELS: Record<SortMode, string> = {
  manual: "Mon ordre",
  alpha: "Alphabétique",
  category: "Par catégorie",
  recent: "Derniers ajouts",
};

/** Palette proposée à la création d'une bibliothèque. */
export const LIBRARY_COLORS = [
  "#7c5cff",
  "#3ecf8e",
  "#f5b041",
  "#ff6b6b",
  "#38bdf8",
  "#f472b6",
  "#a3e635",
  "#94a3b8",
];

export type Library = {
  id: number;
  name: string;
  color: string;
  view_mode: ViewMode;
  wood: Wood;
  wall: string;
  item_size: ItemSize;
  sort_mode: SortMode;
  created_at: string;
  items_count: number;
  preview: (string | null)[];
  contains: boolean | null;
};

export type LibraryItem = {
  content: ContentRead;
  shelf_id: number | null;
  position: number;
  added_at: string;
  tracking_status: TrackingStatus | null;
};

/** Une étagère du meuble. */
export type Shelf = { id: number; name: string | null; position: number };

export type LibraryDetail = Library & { shelves: Shelf[]; items: LibraryItem[] };

/** Adresse de l'API de suivi d'un contenu. */
export function trackingPath(item: { source: Source; kind: ContentKind; external_id: string }): string {
  return `/api/tracking/${item.source}/${item.kind}/${item.external_id}`;
}
