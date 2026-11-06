import { useEffect, useState } from "react";
import { Link, useParams } from "react-router";

import { GameCard } from "../components/GameCard";
import { apiFetch } from "../lib/api";
import { RARITIES, RARITY_COLORS, RARITY_LABELS } from "../lib/cards";
import type { CollectionCard, PackContents, Rarity } from "../lib/cards";
import { useDebouncedValue } from "../lib/useApi";

const PAGE_SIZE = 60;

/** Toutes les cartes qu'on peut obtenir dans un pack, de la plus rare à la
 * plus commune. Les cartes pas encore obtenues sont grisées. */
export default function PackPage() {
  const { theme = "mixed" } = useParams();
  const [rarity, setRarity] = useState<Rarity | null>(null);
  const [search, setSearch] = useState("");
  const query = useDebouncedValue(search.trim(), 300);
  const [pack, setPack] = useState<PackContents | null>(null);
  const [cards, setCards] = useState<CollectionCard[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  function url(offset: number) {
    const params = new URLSearchParams({ offset: String(offset), limit: String(PAGE_SIZE) });
    if (rarity) params.set("rarity", rarity);
    if (query) params.set("q", query);
    return `/api/cards/packs/${encodeURIComponent(theme)}?${params}`;
  }

  // Nouveau filtre : on recharge depuis le début.
  useEffect(() => {
    const controller = new AbortController();
    setLoading(true);
    setError(null);
    apiFetch<PackContents>(url(0), { signal: controller.signal })
      .then((data) => {
        setPack(data);
        setCards(data.cards);
      })
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setError(err instanceof Error ? err.message : "Échec.");
      })
      .finally(() => {
        if (!controller.signal.aborted) setLoading(false);
      });
    return () => controller.abort();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- url() dépend de ces valeurs
  }, [theme, rarity, query]);

  async function more() {
    setLoading(true);
    try {
      const data = await apiFetch<PackContents>(url(cards.length));
      setCards((list) => [...list, ...data.cards]);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec.");
    } finally {
      setLoading(false);
    }
  }

  const owned = cards.filter((c) => c.owned).length;

  return (
    <main className="mx-auto max-w-3xl px-5 pt-6">
      <Link to="/cartes" className="text-sm text-muted hover:text-text">
        ← Mes cartes
      </Link>
      <h1 className="mt-3 text-2xl font-bold">Pack {pack?.label ?? ""}</h1>
      {pack && (
        <p className="mt-1 text-muted">
          {pack.total} cartes à obtenir dans ce pack · grisées : pas encore obtenues
        </p>
      )}

      <label className="mt-4 block text-sm">
        <span className="sr-only">Rechercher un personnage ou une œuvre</span>
        <input
          type="search"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          maxLength={100}
          placeholder="Rechercher un personnage ou une œuvre…"
          className="block w-full rounded-xl border border-border bg-surface px-4 py-2.5"
        />
      </label>

      <ul className="mt-3 flex flex-wrap gap-2" aria-label="Filtrer par rareté">
        {RARITIES.map((r) => {
          const count = pack?.rarities.find((x) => x.rarity === r)?.count ?? 0;
          return (
            <li key={r}>
              <button
                type="button"
                aria-pressed={rarity === r}
                onClick={() => setRarity(rarity === r ? null : r)}
                className="rounded-full border px-3 py-1 text-xs"
                style={{
                  borderColor: RARITY_COLORS[r],
                  color: rarity === r ? "#0b0d12" : RARITY_COLORS[r],
                  backgroundColor: rarity === r ? RARITY_COLORS[r] : "transparent",
                }}
              >
                {RARITY_LABELS[r]} · {count}
              </button>
            </li>
          );
        })}
      </ul>

      {error && (
        <p role="alert" className="mt-4 text-error">
          {error}
        </p>
      )}

      <div className="mt-5" aria-live="polite" aria-busy={loading}>
        {pack && (
          <p className="mb-3 text-sm text-muted">
            {pack.matching} carte{pack.matching > 1 ? "s" : ""}
            {cards.length > 0 && ` · ${owned} obtenue${owned > 1 ? "s" : ""} parmi celles affichées`}
          </p>
        )}
        {!loading && pack && cards.length === 0 && (
          <p className="text-center text-muted">Aucune carte ne correspond.</p>
        )}
        <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5">
          {cards.map((card) => (
            <li key={card.id}>
              <div
                className={card.owned ? "" : "opacity-50 grayscale"}
                title={card.owned ? undefined : "Pas encore obtenue"}
              >
                <GameCard card={card} />
              </div>
              <p className="mt-1 text-center text-[11px] text-muted">
                {card.owned ? "✔ Obtenue" : "Pas encore obtenue"}
              </p>
            </li>
          ))}
        </ul>
        {pack && cards.length < pack.matching && (
          <button
            type="button"
            onClick={() => void more()}
            disabled={loading}
            className="mt-4 w-full rounded-xl border border-border py-2.5 hover:bg-surface disabled:opacity-50"
          >
            {loading ? "Chargement…" : `Afficher plus (${pack.matching - cards.length} restantes)`}
          </button>
        )}
      </div>
    </main>
  );
}
