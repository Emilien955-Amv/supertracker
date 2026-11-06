import { useState } from "react";
import { Link, useParams } from "react-router";

import { useAuth } from "../auth/AuthContext";
import type { User } from "../auth/AuthContext";
import { GameCard } from "../components/GameCard";
import { MasterCard } from "../components/MasterCard";
import { MissingCard } from "../components/MissingCard";
import { Poster } from "../components/Poster";
import { ProgressBar } from "../components/ProgressBar";
import { ApiError, apiFetch } from "../lib/api";
import { KIND_LABELS, contentPath } from "../lib/catalog";
import { RARITIES, RARITY_COLORS, RARITY_LABELS } from "../lib/cards";
import type { BinderPage as BinderPageData, CardRead, CollectionCard, Mastery, Rarity } from "../lib/cards";
import { announceRewards } from "../lib/gamification";
import { useApiResource } from "../lib/useApi";

/** Une page du classeur : toutes les cartes d'une œuvre. */
export default function BinderPage() {
  const { id } = useParams();
  const path = `/api/cards/binder/${id}`;
  const [state, setPage] = useApiResource<BinderPageData>(path);
  const [rarity, setRarity] = useState<Rarity | null>(null);
  const [onlyMissing, setOnlyMissing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [titleMessage, setTitleMessage] = useState<string | null>(null);
  const { updateUser } = useAuth();

  if (state.status === "idle" || state.status === "loading") {
    return <main className="mx-auto max-w-3xl px-5 pt-8 text-muted">Chargement…</main>;
  }
  if (state.status === "error") {
    const notFound = state.error instanceof ApiError && [404, 422].includes(state.error.status);
    return (
      <main className="mx-auto max-w-3xl px-5 pt-8">
        <p role="alert" className="text-error">
          {notFound ? "Cette œuvre est introuvable." : state.error.message}
        </p>
        <Link to="/cartes" className="mt-4 inline-block text-accent hover:underline">
          ← Mes cartes
        </Link>
      </main>
    );
  }

  const page = state.data;
  const owned = page.cards.filter((c) => c.owned).length;
  const visible = page.cards.filter(
    (c) => (rarity === null || c.rarity === rarity) && (!onlyMissing || !c.owned),
  );

  async function craft(card: CollectionCard) {
    const label = `${card.title} (${RARITY_LABELS[card.rarity]})`;
    if (!window.confirm(`Fabriquer « ${label} » pour ${card.craft_cost} fragments ?`)) return;
    setError(null);
    try {
      const result = await apiFetch<{ card: CardRead; fragments: number; masteries: Mastery[] }>(
        `/api/cards/${card.id}/craft`,
        { method: "POST" },
      );
      for (const mastery of result.masteries) announceRewards(mastery.rewards);
      setPage(await apiFetch<BinderPageData>(path));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de la fabrication.");
    }
  }

  async function showTitle(contentId: number) {
    setTitleMessage(null);
    try {
      updateUser(await apiFetch<User>("/api/users/me", { method: "PATCH", body: { title_content_id: contentId } }));
      setTitleMessage("Titre affiché sur votre profil.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec.");
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-5 pt-6">
      <Link to="/cartes" className="text-sm text-muted hover:text-text">
        ← Mon classeur
      </Link>
      <header className="mt-3 flex gap-4">
        <div className="w-20 shrink-0">
          <Poster url={page.content.poster_url} title={page.content.title} />
        </div>
        <div className="min-w-0 flex-1">
          <h1 className="text-2xl font-bold leading-tight">{page.content.title}</h1>
          <p className="text-sm text-muted">
            {KIND_LABELS[page.content.kind]}
            {page.content.year && ` · ${page.content.year}`}
          </p>
          <p className="mt-2 text-sm">
            {owned} / {page.cards.length} cartes · {page.fragments} 💎
          </p>
          <div className="mt-1">
            <ProgressBar
              percent={page.cards.length ? Math.round((100 * owned) / page.cards.length) : 0}
              label="Progression de la collection"
            />
          </div>
          <Link to={contentPath(page.content)} className="mt-2 inline-block text-xs text-accent hover:underline">
            Voir la fiche →
          </Link>
        </div>
      </header>

      {page.mastery ? (
        <section aria-label="Collection complète" className="mt-5 flex items-center gap-4 rounded-2xl border border-gold/60 bg-gold/10 p-4">
          <div className="w-24 shrink-0">
            <MasterCard mastery={page.mastery} />
          </div>
          <div className="min-w-0">
            <p className="font-black text-gold">🏆 Collection complète !</p>
            <p className="mt-1 text-sm">Titre débloqué : « {page.mastery.title} »</p>
            <button
              type="button"
              onClick={() => void showTitle(page.mastery!.content_id)}
              className="mt-2 rounded-lg bg-gold px-3 py-1.5 text-sm font-semibold text-[#3a2405]"
            >
              Afficher ce titre sur mon profil
            </button>
            {titleMessage && <p className="mt-1 text-xs text-ok" aria-live="polite">{titleMessage}</p>}
          </div>
        </section>
      ) : (
        <p className="mt-4 text-xs text-muted">
          🏆 Complétez cette collection pour gagner la carte « Maître », un titre de profil, 500 XP et 5 boosters.
        </p>
      )}

      <ul className="mt-5 flex flex-wrap gap-2" aria-label="Filtrer par rareté">
        {RARITIES.map((r) => (
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
              {RARITY_LABELS[r]}
            </button>
          </li>
        ))}
      </ul>
      <label className="mt-3 flex items-center gap-2 text-sm">
        <input
          type="checkbox"
          checked={onlyMissing}
          onChange={(e) => setOnlyMissing(e.target.checked)}
          className="h-5 w-5 accent-accent"
        />
        Seulement les cartes manquantes
      </label>

      {error && (
        <p role="alert" className="mt-3 text-sm text-error">
          {error}
        </p>
      )}

      <ul className="mt-4 grid grid-cols-3 gap-3 sm:grid-cols-5">
        {visible.map((card) => (
          <li key={card.id}>
            {card.owned ? (
              <GameCard card={card} />
            ) : (
              <MissingCard card={card} fragments={page.fragments} onCraft={() => void craft(card)} />
            )}
          </li>
        ))}
      </ul>
      {visible.length === 0 && <p className="mt-4 text-center text-muted">Aucune carte ici.</p>}
    </main>
  );
}
