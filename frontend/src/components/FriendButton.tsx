import { useState } from "react";

import { apiFetch } from "../lib/api";
import { RELATION_ACTIONS } from "../lib/social";
import type { PublicUser, Relation } from "../lib/social";

/** Bouton d'ami : ajouter, accepter, annuler ou retirer selon la relation. */
export function FriendButton({
  username,
  relation,
  onChange,
}: {
  username: string;
  relation: Relation;
  onChange: (relation: Relation) => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const label = RELATION_ACTIONS[relation];
  if (!label) return null;

  // Ajouter / accepter = POST ; annuler / retirer = DELETE.
  const adds = relation === "none" || relation === "incoming";

  async function click() {
    if (relation === "friends" && !window.confirm(`Retirer ${username} de vos amis ?`)) return;
    setBusy(true);
    setError(null);
    try {
      const path = `/api/friends/${encodeURIComponent(username)}`;
      if (adds) {
        const updated = await apiFetch<PublicUser>(path, { method: "POST" });
        onChange(updated.relation);
      } else {
        await apiFetch<void>(path, { method: "DELETE" });
        onChange("none");
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <span className="inline-flex flex-col items-end">
      <button
        type="button"
        onClick={() => void click()}
        disabled={busy}
        aria-label={`${label} : ${username}`}
        className={`rounded-lg px-3 py-1.5 text-sm disabled:opacity-50 ${
          adds ? "bg-accent font-semibold text-white" : "border border-border hover:bg-surface"
        }`}
      >
        {label}
      </button>
      {error && (
        <span role="alert" className="mt-1 text-xs text-error">
          {error}
        </span>
      )}
    </span>
  );
}
