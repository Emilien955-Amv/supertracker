import { useState } from "react";
import { Link } from "react-router";

import { useAuth } from "../auth/AuthContext";
import type { User } from "../auth/AuthContext";
import { apiFetch } from "../lib/api";
import type { Mastery } from "../lib/cards";
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

      {auth.status === "authenticated" && <SocialSettings />}

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


/** Présentation, visibilité du profil et accès aux amis. */
function SocialSettings() {
  const { state, updateUser } = useAuth();
  const user = state.status === "authenticated" ? state.user : null;
  const [bio, setBio] = useState(user?.bio ?? "");
  const [message, setMessage] = useState<{ ok: boolean; text: string } | null>(null);
  if (!user) return null;

  async function save(changes: { bio?: string; is_public?: boolean }, confirmation: string) {
    setMessage(null);
    try {
      updateUser(await apiFetch<User>("/api/users/me", { method: "PATCH", body: changes }));
      setMessage({ ok: true, text: confirmation });
    } catch (err) {
      setMessage({ ok: false, text: err instanceof Error ? err.message : "Échec." });
    }
  }

  return (
    <section aria-labelledby="social" className="rounded-xl border border-border bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <h2 id="social" className="font-semibold">
          Mon profil social
        </h2>
        <Link to="/amis" className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white">
          👥 Mes amis
        </Link>
      </div>
      <label className="mt-3 block text-sm">
        <span className="text-muted">Ma présentation</span>
        <textarea
          value={bio}
          onChange={(e) => setBio(e.target.value)}
          onBlur={() => bio !== (user.bio ?? "") && void save({ bio }, "Présentation enregistrée.")}
          maxLength={300}
          rows={2}
          placeholder="Ex. Fan d'animes et de séries policières…"
          className="mt-1 block w-full rounded-lg border border-border bg-bg px-3 py-2"
        />
      </label>
      <label className="mt-3 flex items-start gap-3 text-sm">
        <input
          type="checkbox"
          checked={user.is_public}
          onChange={(e) =>
            void save(
              { is_public: e.target.checked },
              e.target.checked ? "Votre profil est maintenant public." : "Votre profil est maintenant privé.",
            )
          }
          className="mt-0.5 h-5 w-5 accent-accent"
        />
        <span>
          Profil public
          <span className="block text-xs text-muted">
            {user.is_public
              ? "Tout le monde peut voir votre niveau, vos succès et votre collection."
              : "Seuls vos amis voient votre niveau, vos succès et votre collection."}
          </span>
        </span>
      </label>
      <TitlePicker />
      <div className="mt-3 flex items-center justify-between gap-3">
        <Link to={`/u/${encodeURIComponent(user.username)}`} className="text-sm text-accent hover:underline">
          Voir mon profil comme les autres →
        </Link>
        <p aria-live="polite" className={`text-sm ${message?.ok ? "text-ok" : "text-error"}`}>
          {message?.text}
        </p>
      </div>
    </section>
  );
}


/** Titre affiché sous le pseudo, parmi ceux des collections complétées. */
function TitlePicker() {
  const { state, updateUser } = useAuth();
  const masteries = useApi<Mastery[]>("/api/cards/masteries");
  if (state.status !== "authenticated" || masteries.status !== "success") return null;
  const user = state.user;
  const list = masteries.data;
  const current = list.find((m) => m.title === user.title)?.content_id ?? "";

  return (
    <label className="mt-3 block text-sm">
      <span className="text-muted">Mon titre</span>
      {list.length === 0 ? (
        <span className="mt-1 block text-xs text-muted">
          Complétez la collection de cartes d'une œuvre pour gagner un titre (ex. « Roi des pirates »).
        </span>
      ) : (
        <select
          value={current}
          onChange={(e) =>
            void apiFetch<User>("/api/users/me", {
              method: "PATCH",
              body: { title_content_id: e.target.value ? Number(e.target.value) : null },
            }).then(updateUser)
          }
          className="mt-1 block w-full rounded-lg border border-border bg-bg px-3 py-2"
        >
          <option value="">Aucun titre</option>
          {list.map((m) => (
            <option key={m.content_id} value={m.content_id}>
              {m.title} ({m.work_title})
            </option>
          ))}
        </select>
      )}
    </label>
  );
}
