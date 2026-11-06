import { useParams } from "react-router";

import { Avatar } from "../components/Avatar";
import { FriendButton } from "../components/FriendButton";
import { MasterCard } from "../components/MasterCard";
import { RARITY_COLORS, RARITY_LABELS } from "../lib/cards";
import { formatDate } from "../lib/catalog";
import { TIER_STYLES } from "../lib/gamification";
import type { UserProfile } from "../lib/social";
import { useApiResource } from "../lib/useApi";

/** Profil d'un autre utilisateur : détail visible par ses amis (ou tous s'il est public). */
export default function UserProfilePage() {
  const { username = "" } = useParams();
  const [state, setProfile] = useApiResource<UserProfile>(
    `/api/users/${encodeURIComponent(username)}/profile`,
  );

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
  const stats = profile.stats;

  return (
    <main className="mx-auto max-w-3xl space-y-6 px-5 pt-8">
      <header className="flex items-center gap-4">
        <Avatar username={profile.username} size="h-16 w-16 text-2xl" />
        <div className="min-w-0 flex-1">
          <h1 className="truncate text-2xl font-bold">{profile.username}</h1>
          {profile.title && <p className="text-sm font-semibold text-gold">🏆 {profile.title}</p>}
          {stats && <p className="text-sm text-muted">Niveau {stats.level} · {stats.xp} XP</p>}
          {profile.member_since && (
            <p className="text-xs text-muted">Membre depuis le {formatDate(profile.member_since.slice(0, 10))}</p>
          )}
        </div>
        <FriendButton
          username={profile.username}
          relation={profile.relation}
          onChange={(relation) => setProfile({ ...profile, relation })}
        />
      </header>

      {!profile.visible ? (
        <p className="rounded-xl border border-border bg-surface p-6 text-center text-muted">
          🔒 Ce profil est privé. Devenez amis pour voir sa collection et sa progression.
        </p>
      ) : (
        <>
          {profile.bio && <p className="whitespace-pre-line rounded-xl bg-surface p-4">{profile.bio}</p>}
          {stats && (
            <>
              <dl className="grid grid-cols-2 gap-3 sm:grid-cols-4">
                {[
                  ["Épisodes vus", stats.episodes],
                  ["Films vus", stats.movies],
                  ["Séries terminées", stats.series_completed],
                  ["Cartes", stats.cards],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-xl border border-border bg-surface p-3">
                    <dt className="text-xs text-muted">{label}</dt>
                    <dd className="text-xl font-bold">{value}</dd>
                  </div>
                ))}
              </dl>
              <ul className="flex flex-wrap gap-2" aria-label="Cartes les plus rares">
                {stats.top_cards.map(({ rarity, count }) => (
                  <li
                    key={rarity}
                    className="rounded-full border px-3 py-1 text-sm"
                    style={{ borderColor: RARITY_COLORS[rarity], color: RARITY_COLORS[rarity] }}
                  >
                    {RARITY_LABELS[rarity]} : {count}
                  </li>
                ))}
              </ul>
              {(stats.masteries ?? []).length > 0 && (
                <section aria-labelledby="maitrises">
                  <h2 id="maitrises" className="font-semibold">
                    Collections complètes ({stats.masteries!.length})
                  </h2>
                  <ul className="mt-2 grid grid-cols-3 gap-3 sm:grid-cols-5">
                    {stats.masteries!.map((m) => (
                      <li key={m.work_title}>
                        <MasterCard
                          mastery={{ ...m, content_id: 0, completed_at: null, rewards: null }}
                        />
                      </li>
                    ))}
                  </ul>
                </section>
              )}
              <section aria-labelledby="succes-ami">
                <h2 id="succes-ami" className="font-semibold">
                  Succès ({stats.badges.length})
                </h2>
                {stats.badges.length === 0 ? (
                  <p className="mt-2 text-sm text-muted">Pas encore de succès.</p>
                ) : (
                  <ul className="mt-2 flex flex-wrap gap-2">
                    {stats.badges.map((badge) => (
                      <li
                        key={badge.code}
                        className={`rounded-xl border px-3 py-2 text-sm ${TIER_STYLES[badge.tier]}`}
                      >
                        <span aria-hidden="true">{badge.icon}</span> {badge.name}
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            </>
          )}
        </>
      )}
    </main>
  );
}
