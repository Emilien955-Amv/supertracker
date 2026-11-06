import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { GameCard } from "../components/GameCard";
import { apiFetch } from "../lib/api";
import { RARITY_LABELS } from "../lib/cards";
import type { CardRead } from "../lib/cards";
import { MAX_CARDS_PER_SIDE } from "../lib/trades";
import type { PartnerCard, PartnerWork } from "../lib/trades";
import { useApi } from "../lib/useApi";

/** Préparer un échange avec un ami : choisir une œuvre, puis les cartes à
 * donner (les miennes) et à recevoir (les siennes). */
export default function TradeComposePage() {
  const { username = "" } = useParams();
  const navigate = useNavigate();
  const works = useApi<PartnerWork[]>(
    `/api/trades/partner/${encodeURIComponent(username)}/works`,
  );
  const [workId, setWorkId] = useState<number | null>(null);
  const cards = useApi<PartnerCard[]>(
    workId === null
      ? null
      : `/api/trades/partner/${encodeURIComponent(username)}/works/${workId}`,
  );
  // Cartes choisies (gardées même en changeant d'œuvre).
  const [give, setGive] = useState<Map<number, CardRead>>(new Map());
  const [take, setTake] = useState<Map<number, CardRead>>(new Map());
  const [message, setMessage] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);

  function toggle(side: "give" | "take", card: CardRead) {
    const [current, set] = side === "give" ? [give, setGive] : [take, setTake];
    const next = new Map(current);
    if (next.has(card.id)) next.delete(card.id);
    else if (next.size < MAX_CARDS_PER_SIDE) next.set(card.id, card);
    set(next);
  }

  async function send() {
    setSending(true);
    setError(null);
    try {
      await apiFetch("/api/trades", {
        method: "POST",
        body: {
          username,
          give: [...give.keys()],
          take: [...take.keys()],
          message: message || null,
        },
      });
      navigate("/echanges");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'envoi.");
      setSending(false);
    }
  }

  if (works.status === "error") {
    return (
      <main className="mx-auto max-w-3xl px-5 pt-8">
        <p role="alert" className="text-error">
          {works.error.message}
        </p>
        <Link
          to="/echanges"
          className="mt-4 inline-block text-accent hover:underline"
        >
          ← Échanges
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-3xl space-y-5 px-5 pb-40 pt-6">
      <Link to="/echanges" className="text-sm text-muted hover:text-text">
        ← Échanges
      </Link>
      <h1 className="text-2xl font-bold">Échange avec {username}</h1>

      <label className="block">
        <span className="text-sm font-semibold">Œuvre</span>
        <select
          value={workId ?? ""}
          onChange={(e) =>
            setWorkId(e.target.value ? Number(e.target.value) : null)
          }
          className="mt-1 block w-full rounded-xl border border-border bg-surface px-3 py-2.5"
        >
          <option value="">— Choisir une œuvre —</option>
          {works.status === "success" &&
            works.data.map((w) => (
              <option key={w.content.id} value={w.content.id}>
                {w.content.title} (vous : {w.mine} · {username} : {w.theirs})
              </option>
            ))}
        </select>
      </label>
      {works.status === "success" && works.data.length === 0 && (
        <p className="text-sm text-muted">
          Aucun de vous deux n'a encore de cartes.
        </p>
      )}

      {cards.status === "success" && (
        <>
          <p className="text-xs text-muted">
            Touchez une de vos cartes pour la donner, ou une carte de {username}{" "}
            pour la demander.
          </p>
          <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5">
            {cards.data
              .filter((c) => c.mine > 0 || c.theirs > 0)
              .map(({ card, mine, theirs }) => (
                <li key={card.id}>
                  <GameCard card={card} />
                  <p className="mt-1 text-center text-[11px] text-muted">
                    Vous ×{mine} · {username} ×{theirs}
                  </p>
                  <div className="mt-1 flex flex-col gap-1">
                    {mine > 0 && (
                      <button
                        type="button"
                        aria-pressed={give.has(card.id)}
                        aria-label={`Donner ${card.title} (${RARITY_LABELS[card.rarity]})`}
                        onClick={() => toggle("give", card)}
                        className={`rounded-md border px-2 py-1 text-xs ${give.has(card.id) ? "border-accent bg-accent text-white" : "border-border hover:bg-surface"}`}
                      >
                        {give.has(card.id)
                          ? "✓ Donnée"
                          : mine > 1
                            ? "Donner (doublon)"
                            : "Donner"}
                      </button>
                    )}
                    {theirs > 0 && (
                      <button
                        type="button"
                        aria-pressed={take.has(card.id)}
                        aria-label={`Demander ${card.title} (${RARITY_LABELS[card.rarity]})`}
                        onClick={() => toggle("take", card)}
                        className={`rounded-md border px-2 py-1 text-xs ${take.has(card.id) ? "border-ok bg-ok text-[#0b0d12]" : "border-border hover:bg-surface"}`}
                      >
                        {take.has(card.id)
                          ? "✓ Demandée"
                          : mine === 0
                            ? "Demander ★"
                            : "Demander"}
                      </button>
                    )}
                  </div>
                </li>
              ))}
          </ul>
        </>
      )}
      {cards.status === "loading" && <p className="text-muted">Chargement…</p>}

      {/* Récapitulatif fixé en bas, au-dessus de la barre de navigation. */}
      <section
        aria-label="Récapitulatif de l'échange"
        className="fixed inset-x-0 bottom-16 border-t border-border bg-surface/95 px-5 py-3 backdrop-blur"
      >
        <div className="mx-auto max-w-3xl space-y-2">
          <p className="text-sm">
            Vous donnez <strong>{give.size}</strong> carte
            {give.size > 1 ? "s" : ""} · vous recevez{" "}
            <strong>{take.size}</strong> carte{take.size > 1 ? "s" : ""}
            <span className="text-muted">
              {" "}
              (max {MAX_CARDS_PER_SIDE} de chaque côté)
            </span>
          </p>
          {(give.size > 0 || take.size > 0) && (
            <p className="truncate text-xs text-muted">
              {[...give.values()].map((c) => `−${c.title}`).join(", ")}
              {give.size > 0 && take.size > 0 && " · "}
              {[...take.values()].map((c) => `+${c.title}`).join(", ")}
            </p>
          )}
          <div className="flex gap-2">
            <input
              value={message}
              onChange={(e) => setMessage(e.target.value.slice(0, 200))}
              placeholder="Petit message (facultatif)"
              aria-label="Message"
              className="min-w-0 flex-1 rounded-lg border border-border bg-bg px-3 py-2 text-sm"
            />
            <button
              type="button"
              disabled={sending || (give.size === 0 && take.size === 0)}
              onClick={() => void send()}
              className="rounded-lg bg-accent px-4 py-2 text-sm font-semibold text-white disabled:opacity-40"
            >
              Proposer
            </button>
          </div>
          {error && (
            <p role="alert" className="text-sm text-error">
              {error}
            </p>
          )}
        </div>
      </section>
    </main>
  );
}
