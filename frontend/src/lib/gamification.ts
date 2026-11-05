/** Types de la gamification (miroir de app/schemas/gamification.py) et
 * diffusion des récompenses vers la notification affichée à l'écran. */

export type Tier = "bronze" | "silver" | "gold";

export const TIER_LABELS: Record<Tier, string> = { bronze: "Bronze", silver: "Argent", gold: "Or" };

export const TIER_STYLES: Record<Tier, string> = {
  bronze: "border-[#cd7f32]/60 bg-[#cd7f32]/10",
  silver: "border-[#c0c7d1]/60 bg-[#c0c7d1]/10",
  gold: "border-gold/70 bg-gold/10",
};

export type BadgeBrief = { code: string; name: string; icon: string; tier: Tier };

export type Rewards = {
  xp: number;
  lines: { label: string; amount: number }[];
  badges: BadgeBrief[];
  level_up: number | null;
  streak_days: number;
  /** Boosters de cartes gagnés. */
  boosters: number;
};

export type BadgeRead = BadgeBrief & {
  description: string;
  threshold: number;
  progress: number;
  earned_at: string | null;
};

export type Profile = {
  xp: number;
  level: number;
  level_start_xp: number;
  next_level_xp: number;
  streak_days: number;
  streak_bonus_percent: number;
  today_watch_xp: number;
  daily_cap: number;
  badges: BadgeRead[];
  recent: { label: string; amount: number; created_at: string }[];
};

/** Pourcentage d'avancement dans le niveau actuel. */
export function levelPercent(profile: Pick<Profile, "xp" | "level_start_xp" | "next_level_xp">): number {
  const span = profile.next_level_xp - profile.level_start_xp;
  return span > 0 ? Math.round((100 * (profile.xp - profile.level_start_xp)) / span) : 0;
}

// Diffusion des récompenses : n'importe quel composant les annonce, et la
// notification (RewardToaster) les affiche, sans dépendance entre les deux.
const EVENT = "supertracker:rewards";

export function announceRewards(rewards: Rewards | null | undefined): void {
  if (rewards) window.dispatchEvent(new CustomEvent<Rewards>(EVENT, { detail: rewards }));
}

export function onRewards(listener: (rewards: Rewards) => void): () => void {
  const handler = (event: Event) => listener((event as CustomEvent<Rewards>).detail);
  window.addEventListener(EVENT, handler);
  return () => window.removeEventListener(EVENT, handler);
}
