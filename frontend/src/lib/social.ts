/** Types du social (miroir de app/schemas/social.py). */

import type { BadgeBrief } from "./gamification";
import type { Rarity } from "./cards";

export type Relation = "self" | "friends" | "outgoing" | "incoming" | "none";

export type PublicUser = { username: string; avatar_url: string | null; relation: Relation };

export type ProfileStats = {
  level: number;
  xp: number;
  episodes: number;
  movies: number;
  series_completed: number;
  cards: number;
  top_cards: { rarity: Rarity; count: number }[];
  badges: BadgeBrief[];
  masteries?: { work_title: string; poster_url: string | null; title: string }[];
};

export type UserProfile = {
  username: string;
  avatar_url: string | null;
  relation: Relation;
  visible: boolean;
  is_public: boolean;
  bio: string | null;
  title?: string | null;
  member_since: string | null;
  stats: ProfileStats | null;
};

export type Friends = { friends: PublicUser[]; incoming: PublicUser[]; outgoing: PublicUser[] };

/** Texte du bouton d'ami selon la relation actuelle. */
export const RELATION_ACTIONS: Record<Relation, string | null> = {
  self: null,
  friends: "Retirer des amis",
  outgoing: "Annuler la demande",
  incoming: "Accepter la demande",
  none: "Ajouter en ami",
};
