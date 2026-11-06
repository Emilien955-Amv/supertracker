/** Échanges de cartes entre amis (miroir de app/api/trades.py). */

import type { BinderContent, CardRead, Mastery } from "./cards";

export type TradeStatus = "pending" | "accepted" | "declined" | "cancelled";

export type Trade = {
  id: number;
  status: TradeStatus;
  /** incoming : on me propose ; outgoing : c'est moi qui propose. */
  direction: "incoming" | "outgoing";
  partner: string;
  message: string | null;
  /** Ce que donne celui qui propose. */
  gives: CardRead[];
  /** Ce qu'il demande en échange. */
  takes: CardRead[];
  created_at: string;
  resolved_at: string | null;
};

export type AcceptResult = { masteries: Mastery[] };

export type PartnerWork = {
  content: BinderContent;
  mine: number;
  theirs: number;
};

export type PartnerCard = { card: CardRead; mine: number; theirs: number };

export const STATUS_LABELS: Record<TradeStatus, string> = {
  pending: "En attente",
  accepted: "Accepté",
  declined: "Refusé",
  cancelled: "Annulé",
};

/** Nombre maximal de cartes de chaque côté d'un échange. */
export const MAX_CARDS_PER_SIDE = 10;
