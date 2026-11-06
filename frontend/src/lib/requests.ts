/** Sondages : demandes de cartes (miroir de app/api/requests.py). */

import type { ContentKind, Source } from "./catalog";

export type WorkRequest = {
  id: number;
  source: Source;
  kind: ContentKind;
  external_id: string;
  title: string;
  poster_url: string | null;
  year: number | null;
  status: "open" | "added";
  votes: number;
  votes_needed: number;
  voted: boolean;
};

export type CatalogStatus = { in_catalog: boolean; request: WorkRequest | null };
