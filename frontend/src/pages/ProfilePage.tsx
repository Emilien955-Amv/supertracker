import { useAuth } from "../auth/AuthContext";
import { ProgressBar } from "../components/ProgressBar";
import { TIER_LABELS, TIER_STYLES, levelPercent } from "../lib/gamification";
import type { BadgeRead, Profile } from "../lib/gamification";
import { useApi } from "../lib/useApi";

/** Profil de joueur : niveau, série de jours, plafond du jour, succès. */
export default function ProfilePage() {
  const { state: auth } = useAuth();
  const state = useApi<Profile>("/api/gamification/me");

  if (state.status === "idle" || state.status === "loading") {
    return <main className="mx-auto max-w-3xl px-5 pt-8 text-muted">Chargement…</main>;
  }
  if (state.status === "error") {
    return (
      <main className="mx-auto max-w-3xl px-5 pt-8">
        <p role="alert" className="text-error">
          {state.error.message}
        </p>
      </main>
    );
  }

  const profile = state.data;
  const earned = profile.badges.filter((b) => b.earned_at);

  return (
    <main className="mx-auto max-w-3xl space-y-6 px-5 pt-8">
      <header>
        <h1 className="text-2xl font-bold">
          {auth.status === "authenticated" ? auth.user.username : "Mon profil"}
        </h1>
        <p className="text-muted">Vos points, votre régularité et vos succès.</p>
      </header>

      <section aria-labelledby="niveau" className="rounded-2xl border border-accent/40 bg-accent/10 p-5">
        <div className="flex items-end justify-between">
          <h2 id="niveau" className="text-3xl font-bold">
            Niveau {profile.level}
          </h2>
          <p className="text-sm text-muted">{profile.xp} XP au total</p>
        </div>
        <div className="mt-3">
          <ProgressBar percent={levelPercent(profile)} label={`Progression vers le niveau ${profile.level + 1}`} />
        </div>
        <p className="mt-1 text-xs text-muted">
          Encore {profile.next_level_xp - profile.xp} XP pour le niveau {profile.level + 1}
        </p>
      </section>

      <div className="grid grid-cols-2 gap-3">
        <section aria-labelledby="serie" className="rounded-xl border border-border bg-surface p-4">
          <h2 id="serie" className="text-sm text-muted">
            Série en cours
          </h2>
          <p className="mt-1 text-2xl font-bold">
            <span aria-hidden="true">🔥</span> {profile.streak_days} {profile.streak_days > 1 ? "jours" : "jour"}
          </p>
          <p className="text-xs text-muted">
            {profile.streak_bonus_percent > 0
              ? `+${profile.streak_bonus_percent} % d'XP par épisode`
              : "Revenez demain pour un bonus"}
          </p>
        </section>
        <section aria-labelledby="aujourdhui" className="rounded-xl border border-border bg-surface p-4">
          <h2 id="aujourdhui" className="text-sm text-muted">
            Aujourd'hui
          </h2>
          <p className="mt-1 text-2xl font-bold">
            {profile.today_watch_xp}
            <span className="text-sm font-normal text-muted"> / {profile.daily_cap} XP</span>
          </p>
          <ProgressBar
            percent={Math.round((100 * profile.today_watch_xp) / profile.daily_cap)}
            label="XP de visionnage gagnés aujourd'hui"
          />
        </section>
      </div>

      <section aria-labelledby="succes">
        <h2 id="succes" className="text-lg font-semibold">
          Succès <span className="text-sm font-normal text-muted">({earned.length} / {profile.badges.length})</span>
        </h2>
        <ul className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-3">
          {profile.badges.map((badge) => (
            <li key={badge.code}>
              <BadgeCard badge={badge} />
            </li>
          ))}
        </ul>
      </section>

      {profile.recent.length > 0 && (
        <section aria-labelledby="gains">
          <h2 id="gains" className="text-lg font-semibold">
            Derniers gains
          </h2>
          <ul className="mt-3 divide-y divide-border rounded-xl border border-border bg-surface">
            {profile.recent.map((event, i) => (
              <li key={i} className="flex justify-between p-3 text-sm">
                <span>{event.label}</span>
                <span className="font-semibold text-accent">+{event.amount} XP</span>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}

function BadgeCard({ badge }: { badge: BadgeRead }) {
  const unlocked = badge.earned_at !== null;
  return (
    <div
      className={`h-full rounded-xl border p-3 ${unlocked ? TIER_STYLES[badge.tier] : "border-border bg-surface opacity-60"}`}
    >
      <p className={`text-3xl ${unlocked ? "" : "grayscale"}`} aria-hidden="true">
        {badge.icon}
      </p>
      <p className="mt-1 font-semibold">{badge.name}</p>
      <p className="text-xs text-muted">{badge.description}</p>
      <p className="mt-1 text-xs text-muted">
        {TIER_LABELS[badge.tier]} · {unlocked ? "Débloqué" : `${badge.progress} / ${badge.threshold}`}
      </p>
      {!unlocked && badge.threshold > 1 && (
        <div className="mt-1">
          <ProgressBar
            percent={Math.round((100 * badge.progress) / badge.threshold)}
            label={`Progression du succès ${badge.name}`}
          />
        </div>
      )}
    </div>
  );
}
