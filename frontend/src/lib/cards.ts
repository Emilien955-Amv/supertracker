/** Types des cartes (miroir de app/schemas/cards.py) et apparence des raretés. */

import type { ContentKind, Source } from "./catalog";
import type { Rewards } from "./gamification";

export type Rarity = "common" | "uncommon" | "rare" | "epic" | "legendary" | "mythic" | "divine";

export const RARITIES: Rarity[] = ["common", "uncommon", "rare", "epic", "legendary", "mythic", "divine"];

export const RARITY_LABELS: Record<Rarity, string> = {
  common: "Commune",
  uncommon: "Peu commune",
  rare: "Rare",
  epic: "Épique",
  legendary: "Légendaire",
  mythic: "Mythique",
  divine: "Divine",
};

/** Couleur de chaque rareté : cadre, texte et lueur. */
export const RARITY_COLORS: Record<Rarity, string> = {
  common: "#9aa1b2",
  uncommon: "#3ecf8e",
  rare: "#38bdf8",
  epic: "#a855f7",
  legendary: "#f5b041",
  mythic: "#ef4444",
  divine: "#fff3c4",
};

export type CardRead = {
  id: number;
  rarity: Rarity;
  kind: "character";
  title: string;
  subtitle: string | null;
  image_url: string;
  content: { id: number; source: Source; kind: ContentKind; external_id: string; title: string };
};

export type CollectionCard = CardRead & {
  owned: boolean;
  /** Exemplaires possédés (2 et plus : doublons à échanger ou recycler). */
  copies?: number;
  craft_cost: number | null;
};

export type GenreTheme = "anime" | "movie" | "series" | "mixed";
export type PlatformTheme =
  | "netflix"
  | "disney"
  | "prime"
  | "apple"
  | "max"
  | "canal"
  | "paramount"
  | "crunchyroll"
  | "adn";
export type PackTheme = GenreTheme | PlatformTheme;

export const GENRE_THEMES: GenreTheme[] = ["anime", "movie", "series", "mixed"];

/** Icône de chaque pack par genre. */
export const THEME_ICONS: Record<GenreTheme, string> = {
  anime: "🍥",
  movie: "🎬",
  series: "📺",
  mixed: "🎲",
};

/** Couleur de chaque plateforme (bordure du bouton de pack). */
export const PLATFORM_COLORS: Record<PlatformTheme, string> = {
  netflix: "#e50914",
  disney: "#113ccf",
  prime: "#00a8e1",
  apple: "#a2aaad",
  max: "#002be7",
  canal: "#ffffff",
  paramount: "#0064ff",
  crunchyroll: "#f47521",
  adn: "#0096ff",
};

/** La dernière carte a droit à une révélation spéciale à partir de Légendaire. */
export function isEpicReveal(rarity: Rarity): boolean {
  return RARITIES.indexOf(rarity) >= RARITIES.indexOf("legendary");
}

export type Collection = {
  boosters: number;
  fragments: number;
  boosters_until_pity: number;
  /** Secondes avant le prochain booster gratuit (null : réserve pleine). */
  next_free_booster_in: number | null;
  free_booster_minutes: number;
  free_booster_max_stock: number;
  themes: { theme: PackTheme; label: string; cards: number }[];
  stats: { rarity: Rarity; owned: number; total: number; chance_percent: number }[];
  /** Exemplaires en trop, et les fragments qu'ils rapporteraient. */
  duplicates?: number;
  duplicates_value?: number;
};

/** Résultat d'un recyclage de doublons. */
export type RecycleResult = { recycled: number; gained: number; fragments: number };

/** Œuvre telle que présentée dans le classeur. */
export type BinderContent = CardRead["content"] & { poster_url: string | null; year: number | null };

/** Une pochette du classeur : une œuvre et sa progression. */
export type BinderEntry = { content: BinderContent; owned: number; total: number; mastered: boolean };

/** Collection complète : carte « Maître » et titre de profil débloqué. */
export type Mastery = {
  content_id: number;
  work_title: string;
  poster_url: string | null;
  title: string;
  completed_at: string | null;
  rewards: Rewards | null;
};

/** Toutes les cartes d'une œuvre. */
export type BinderPage = {
  content: BinderContent;
  fragments: number;
  cards: CollectionCard[];
  mastery: Mastery | null;
};

/** Liste des cartes qu'on peut obtenir dans un pack (une page). */
export type PackContents = {
  theme: PackTheme;
  label: string;
  total: number;
  matching: number;
  rarities: { rarity: Rarity; count: number }[];
  cards: CollectionCard[];
};

export type BoosterOpened = {
  theme: PackTheme;
  boosters_opened: number;
  cards: { card: CardRead; is_new: boolean; fragments: number }[];
  fragments: number;
  boosters_left: number;
  /** Collections complétées grâce à ce booster. */
  masteries?: Mastery[];
};

/** Les raretés à partir de « Rare » brillent à la révélation. */
export function isShiny(rarity: Rarity): boolean {
  return RARITIES.indexOf(rarity) >= RARITIES.indexOf("rare");
}
