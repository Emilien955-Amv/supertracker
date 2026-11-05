import { useEffect, useState } from "react";
import { Link } from "react-router";

import { onRewards } from "../lib/gamification";
import type { Rewards } from "../lib/gamification";

const DURATION_MS = 4500;

type Toast = Rewards & { id: number };

/** Notifications « +25 XP », succès et niveau, en haut de l'écran.
 * aria-live : les lecteurs d'écran annoncent le gain sans déplacer le focus. */
export function RewardToaster() {
  const [toasts, setToasts] = useState<Toast[]>([]);

  useEffect(
    () =>
      onRewards((rewards) => {
        const id = Date.now() + Math.random();
        setToasts((list) => [...list.slice(-2), { ...rewards, id }]);
        setTimeout(() => setToasts((list) => list.filter((t) => t.id !== id)), DURATION_MS);
      }),
    [],
  );

  return (
    <div
      aria-live="polite"
      className="pointer-events-none fixed inset-x-0 top-3 z-50 flex flex-col items-center gap-2 px-4"
    >
      {toasts.map((toast) => (
        <div
          key={toast.id}
          role="status"
          className="pointer-events-auto w-full max-w-sm rounded-2xl border border-accent/50 bg-surface/95 p-3 shadow-2xl backdrop-blur"
        >
          {toast.level_up && (
            <p className="text-center font-bold text-gold">🎉 Niveau {toast.level_up} atteint !</p>
          )}
          {toast.xp > 0 && (
            <p className="flex items-baseline justify-between gap-3">
              <span className="text-lg font-bold text-accent">+{toast.xp} XP</span>
              {toast.streak_days > 1 && (
                <span className="text-xs text-muted">🔥 {toast.streak_days} jours d'affilée</span>
              )}
            </p>
          )}
          <ul className="mt-1 space-y-0.5 text-sm text-muted">
            {toast.lines.map((line) => (
              <li key={line.label} className="flex justify-between">
                <span>{line.label}</span>
                <span>+{line.amount}</span>
              </li>
            ))}
          </ul>
          {toast.boosters > 0 && (
            <Link to="/cartes" className="mt-2 block rounded-lg bg-accent/15 px-2 py-1 text-sm hover:bg-accent/25">
              🎁 {toast.boosters} booster{toast.boosters > 1 ? "s" : ""} de cartes gagné
              {toast.boosters > 1 ? "s" : ""} ! <span className="text-accent">Ouvrir →</span>
            </Link>
          )}
          {toast.badges.map((badge) => (
            <p key={badge.code} className="mt-2 rounded-lg bg-gold/10 px-2 py-1 text-sm">
              <span aria-hidden="true">{badge.icon}</span> Succès débloqué : <strong>{badge.name}</strong>
            </p>
          ))}
        </div>
      ))}
    </div>
  );
}
