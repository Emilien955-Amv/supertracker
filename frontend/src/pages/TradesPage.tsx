import { useState } from "react";
import { Link } from "react-router";

import { GameCard } from "../components/GameCard";
import { apiFetch } from "../lib/api";
import type { Friends } from "../lib/social";
import { STATUS_LABELS } from "../lib/trades";
import type { AcceptResult, Trade } from "../lib/trades";
import { announceRewards } from "../lib/gamification";
import { useApi, useApiResource } from "../lib/useApi";

/** Mes échanges : reçus, envoyés, historique ; et lancer un nouvel échange. */
export default function TradesPage() {
  const [state, setTrades] = useApiResource<Trade[]>("/api/trades");
  const friends = useApi<Friends>("/api/friends");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState<number | null>(null);

  async function act(trade: Trade, action: "accept" | "decline" | "cancel") {
    setBusy(trade.id);
    setError(null);
    setMessage(null);
    try {
      if (action === "accept") {
        const result = await apiFetch<AcceptResult>(
          `/api/trades/${trade.id}/accept`,
          { method: "POST" },
        );
        for (const mastery of result.masteries)
          announceRewards(mastery.rewards);
        setMessage("Échange réussi ! Les cartes sont dans votre classeur.");
      } else {
        await apiFetch(`/api/trades/${trade.id}/${action}`, { method: "POST" });
      }
      setTrades(await apiFetch<Trade[]>("/api/trades"));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec.");
      setTrades(await apiFetch<Trade[]>("/api/trades"));
    } finally {
      setBusy(null);
    }
  }

  const trades = state.status === "success" ? state.data : [];
  const incoming = trades.filter(
    (t) => t.status === "pending" && t.direction === "incoming",
  );
  const outgoing = trades.filter(
    (t) => t.status === "pending" && t.direction === "outgoing",
  );
  const history = trades.filter((t) => t.status !== "pending");

  return (
    <main className="mx-auto max-w-3xl space-y-6 px-5 pt-6">
      <Link to="/cartes" className="text-sm text-muted hover:text-text">
        ← Mes cartes
      </Link>
      <h1 className="text-2xl font-bold">🔁 Échanges</h1>
      <p className="text-sm text-muted">
        Échangez vos cartes avec vos amis pour compléter vos collections. Rien
        ne bouge tant que l'échange n'est pas accepté.
      </p>

      <section
        aria-labelledby="nouvel-echange"
        className="rounded-2xl border border-accent/40 bg-accent/10 p-4"
      >
        <h2 id="nouvel-echange" className="font-semibold">
          Proposer un échange
        </h2>
        {friends.status === "success" && friends.data.friends.length > 0 ? (
          <ul className="mt-3 flex flex-wrap gap-2">
            {friends.data.friends.map((friend) => (
              <li key={friend.username}>
                <Link
                  to={`/echanges/nouveau/${friend.username}`}
                  className="inline-block rounded-full border border-accent/60 px-3 py-1.5 text-sm hover:bg-accent/20"
                >
                  avec {friend.username}
                </Link>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm text-muted">
            Les échanges se font entre amis.{" "}
            <Link to="/amis" className="text-accent hover:underline">
              Ajouter des amis →
            </Link>
          </p>
        )}
      </section>

      {message && (
        <p
          className="rounded-xl bg-ok/15 p-3 text-sm text-ok"
          aria-live="polite"
        >
          {message}
        </p>
      )}
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}
      {state.status === "loading" && <p className="text-muted">Chargement…</p>}
      {state.status === "error" && (
        <p role="alert" className="text-error">
          {state.error.message}
        </p>
      )}

      <TradeList title="Reçus" trades={incoming} empty="Aucun échange reçu.">
        {(trade) => (
          <div className="flex gap-2">
            <button
              type="button"
              disabled={busy === trade.id}
              onClick={() => void act(trade, "accept")}
              className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
            >
              Accepter
            </button>
            <button
              type="button"
              disabled={busy === trade.id}
              onClick={() => void act(trade, "decline")}
              className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-surface disabled:opacity-50"
            >
              Refuser
            </button>
          </div>
        )}
      </TradeList>

      <TradeList
        title="Envoyés"
        trades={outgoing}
        empty="Aucun échange en attente."
      >
        {(trade) => (
          <button
            type="button"
            disabled={busy === trade.id}
            onClick={() => void act(trade, "cancel")}
            className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-surface disabled:opacity-50"
          >
            Annuler
          </button>
        )}
      </TradeList>

      {history.length > 0 && (
        <TradeList title="Historique" trades={history} empty="" />
      )}
    </main>
  );
}

function TradeList({
  title,
  trades,
  empty,
  children,
}: {
  title: string;
  trades: Trade[];
  empty: string;
  children?: (trade: Trade) => React.ReactNode;
}) {
  return (
    <section aria-label={title}>
      <h2 className="text-lg font-semibold">
        {title}{" "}
        {trades.length > 0 && (
          <span className="text-muted">({trades.length})</span>
        )}
      </h2>
      {trades.length === 0 ? (
        <p className="mt-2 text-sm text-muted">{empty}</p>
      ) : (
        <ul className="mt-3 space-y-3">
          {trades.map((trade) => (
            <li
              key={trade.id}
              className="rounded-xl border border-border bg-surface p-4"
            >
              <TradeSummary trade={trade} />
              <div className="mt-3 flex items-center justify-between gap-2">
                <span className="text-xs text-muted">
                  {STATUS_LABELS[trade.status]}
                </span>
                {children?.(trade)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

/** « Vous donnez / vous recevez », vu depuis le joueur connecté. */
function TradeSummary({ trade }: { trade: Trade }) {
  const incoming = trade.direction === "incoming";
  const iGive = incoming ? trade.takes : trade.gives;
  const iGet = incoming ? trade.gives : trade.takes;
  return (
    <div>
      <p className="text-sm">
        {incoming ? (
          <>
            <strong>{trade.partner}</strong> vous propose :
          </>
        ) : (
          <>
            Proposé à <strong>{trade.partner}</strong> :
          </>
        )}
      </p>
      {trade.message && (
        <p className="mt-1 text-sm italic text-muted">« {trade.message} »</p>
      )}
      <div className="mt-2 grid gap-3 sm:grid-cols-2">
        <CardRow label="Vous donnez" cards={iGive} />
        <CardRow label="Vous recevez" cards={iGet} />
      </div>
    </div>
  );
}

function CardRow({ label, cards }: { label: string; cards: Trade["gives"] }) {
  return (
    <div>
      <p className="text-xs font-semibold uppercase tracking-wide text-muted">
        {label}
      </p>
      {cards.length === 0 ? (
        <p className="mt-1 text-sm text-muted">Rien (cadeau)</p>
      ) : (
        <ul className="mt-1 grid grid-cols-4 gap-1.5">
          {cards.map((card) => (
            <li key={card.id} title={`${card.title} · ${card.content.title}`}>
              <GameCard card={card} />
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
