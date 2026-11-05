import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";

import { BoosterReveal } from "../components/BoosterReveal";
import { CardBack, GameCard } from "../components/GameCard";
import { apiFetch } from "../lib/api";
import { RARITIES, RARITY_COLORS, RARITY_LABELS, THEME_ICONS } from "../lib/cards";
import type {
  BoosterOpened,
  CardRead,
  Collection,
  CollectionCard,
  PackTheme,
  Rarity,
} from "../lib/cards";
import { useApiResource } from "../lib/useApi";

type Filter = "all" | "owned" | "missing";

/** Collection de cartes : boosters par thème, minuteur, fragments, collection. */
export default function CardsPage() {
  const [state, setCollection] = useApiResource<Collection>("/api/cards/me");
  const [opened, setOpened] = useState<BoosterOpened | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState<Filter>("all");
  const [rarity, setRarity] = useState<Rarity | null>(null);

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
  const collection = state.data;

  async function reload() {
    setCollection(await apiFetch<Collection>("/api/cards/me"));
  }

  async function openBooster(theme: PackTheme) {
    setBusy(true);
    setError(null);
    try {
      setOpened(
        await apiFetch<BoosterOpened>("/api/cards/boosters/open", {
          method: "POST",
          body: { theme },
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'ouverture.");
    } finally {
      setBusy(false);
    }
  }

  async function craft(card: CollectionCard) {
    const label = `${card.title} (${RARITY_LABELS[card.rarity]})`;
    if (!window.confirm(`Fabriquer « ${label} » pour ${card.craft_cost} fragments ?`)) return;
    setError(null);
    try {
      await apiFetch<{ card: CardRead; fragments: number }>(`/api/cards/${card.id}/craft`, {
        method: "POST",
      });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de la fabrication.");
    }
  }

  const visible = collection.cards.filter(
    (card) =>
      (filter === "all" || (filter === "owned") === card.owned) &&
      (rarity === null || card.rarity === rarity),
  );
  // Regroupement par contenu, dans l'ordre reçu (alphabétique).
  const groups = new Map<number, { title: string; cards: CollectionCard[] }>();
  for (const card of visible) {
    const group = groups.get(card.content.id) ?? { title: card.content.title, cards: [] };
    group.cards.push(card);
    groups.set(card.content.id, group);
  }
  const ownedTotal = collection.stats.reduce((sum, s) => sum + s.owned, 0);
  const catalogTotal = collection.stats.reduce((sum, s) => sum + s.total, 0);

  return (
    <main className="mx-auto max-w-3xl px-5 pt-8">
      <h1 className="text-2xl font-bold">Mes cartes</h1>
      <p className="mt-1 text-muted">
        {ownedTotal} / {catalogTotal} cartes · {collection.fragments} 💎 fragments
      </p>

      <section
        aria-labelledby="boosters"
        className="mt-5 rounded-2xl border border-accent/40 bg-accent/10 p-5"
      >
        <h2 id="boosters" className="text-center text-lg font-semibold">
          {collection.boosters > 0
            ? `🎁 ${collection.boosters} booster${collection.boosters > 1 ? "s" : ""} à ouvrir`
            : "Aucun booster pour le moment"}
        </h2>
        <FreeBoosterTimer collection={collection} onElapsed={() => void reload()} />

        {collection.boosters > 0 && (
          <>
            <p className="mt-4 text-center text-sm text-muted">Choisissez votre pack :</p>
            <ul className="mt-2 grid grid-cols-2 gap-2">
              {collection.themes.map((theme) => (
                <li key={theme.theme}>
                  <button
                    type="button"
                    onClick={() => void openBooster(theme.theme)}
                    disabled={busy || theme.cards === 0}
                    className="w-full rounded-xl border border-accent/50 bg-surface px-3 py-3 font-semibold hover:bg-accent/20 disabled:opacity-40"
                  >
                    <span aria-hidden="true">{THEME_ICONS[theme.theme]}</span> {theme.label}
                    <span className="block text-xs font-normal text-muted">
                      {theme.cards > 0 ? `${theme.cards} cartes` : "En préparation…"}
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          </>
        )}
        <p className="mt-4 text-center text-xs text-muted">
          5 cartes par booster, dont au moins une Rare · Épique ou mieux garantie d'ici{" "}
          {collection.boosters_until_pity} booster{collection.boosters_until_pity > 1 ? "s" : ""}
          {" · "}Vos contenus suivis sortent 2 fois plus souvent.
        </p>
        {error && (
          <p role="alert" className="mt-3 text-center text-sm text-error">
            {error}
          </p>
        )}
      </section>

      {/* Raretés : progression, probabilité, et filtre au clic. */}
      <section aria-labelledby="raretes" className="mt-6">
        <h2 id="raretes" className="sr-only">
          Raretés
        </h2>
        <ul className="flex flex-wrap gap-2">
          {RARITIES.map((r) => {
            const stat = collection.stats.find((s) => s.rarity === r);
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
                  {RARITY_LABELS[r]} {stat?.owned ?? 0}/{stat?.total ?? 0}
                  <span className="opacity-70"> · {stat?.chance_percent ?? 0} %</span>
                </button>
              </li>
            );
          })}
        </ul>
        <div role="group" aria-label="Afficher" className="mt-3 flex gap-2 text-sm">
          {(
            [
              ["all", "Toutes"],
              ["owned", "Obtenues"],
              ["missing", "À découvrir"],
            ] as [Filter, string][]
          ).map(([value, label]) => (
            <button
              key={value}
              type="button"
              aria-pressed={filter === value}
              onClick={() => setFilter(value)}
              className={`rounded-lg px-3 py-1.5 ${filter === value ? "bg-accent font-semibold text-white" : "border border-border hover:bg-surface"}`}
            >
              {label}
            </button>
          ))}
        </div>
      </section>

      {collection.cards.length === 0 ? (
        <div className="mt-6 rounded-xl border border-border bg-surface p-6 text-center">
          <p className="text-muted">
            Ouvrez un booster pour commencer votre collection ! Les contenus que vous suivez y
            apparaissent aussi.
          </p>
          <Link to="/recherche" className="mt-3 inline-block text-accent hover:underline">
            Suivre un contenu →
          </Link>
        </div>
      ) : (
        <div className="mt-6 space-y-8">
          {[...groups.entries()].map(([contentId, group]) => (
            <section key={contentId} aria-label={group.title}>
              <h2 className="mb-3 font-semibold">
                {group.title}{" "}
                <span className="text-sm font-normal text-muted">
                  {/* Compté sur TOUTES les cartes du contenu, quel que soit le filtre. */}
                  {collection.cards.filter((c) => c.content.id === contentId && c.owned).length}/
                  {collection.cards.filter((c) => c.content.id === contentId).length}
                </span>
              </h2>
              <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5">
                {group.cards.map((card) => (
                  <li key={card.id}>
                    {card.owned ? (
                      <GameCard card={card} />
                    ) : (
                      <MissingCard
                        card={card}
                        fragments={collection.fragments}
                        onCraft={() => void craft(card)}
                      />
                    )}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}

      {opened && (
        <BoosterReveal
          booster={opened}
          onClose={() => {
            setOpened(null);
            void reload();
          }}
          onNext={() => void openBooster(opened.theme)}
        />
      )}
    </main>
  );
}

/** Compte à rebours jusqu'au prochain booster gratuit. */
function FreeBoosterTimer({
  collection,
  onElapsed,
}: {
  collection: Collection;
  onElapsed: () => void;
}) {
  const [seconds, setSeconds] = useState(collection.next_free_booster_in);
  // Référence stable : évite de relancer le minuteur à chaque affichage.
  const elapsed = useRef(onElapsed);
  elapsed.current = onElapsed;

  useEffect(() => {
    setSeconds(collection.next_free_booster_in);
  }, [collection.next_free_booster_in]);

  useEffect(() => {
    if (seconds === null) return;
    if (seconds <= 0) {
      elapsed.current(); // le serveur ajoute le booster dû et relance le minuteur
      return;
    }
    const timer = setTimeout(() => setSeconds(seconds - 1), 1000);
    return () => clearTimeout(timer);
  }, [seconds]);

  if (seconds === null) {
    return (
      <p className="mt-1 text-center text-sm text-muted">
        Réserve pleine ({collection.free_booster_max_stock} boosters gratuits) : ouvrez-en pour
        relancer le minuteur.
      </p>
    );
  }
  const minutes = Math.floor(seconds / 60);
  const rest = String(seconds % 60).padStart(2, "0");
  return (
    <p className="mt-1 text-center text-sm text-muted">
      Prochain booster gratuit dans{" "}
      <span className="font-semibold text-text" aria-live="off">
        {minutes}:{rest}
      </span>{" "}
      · un toutes les {collection.free_booster_minutes} min, et un par épisode vu
    </p>
  );
}

/** Carte pas encore obtenue : dos de carte, rareté visible, fabrication possible. */
function MissingCard({
  card,
  fragments,
  onCraft,
}: {
  card: CollectionCard;
  fragments: number;
  onCraft: () => void;
}) {
  return (
    <div>
      <CardBack rarity={card.rarity} label={`${RARITY_LABELS[card.rarity]} à découvrir`} />
      {card.craft_cost !== null && (
        <button
          type="button"
          onClick={onCraft}
          disabled={fragments < card.craft_cost}
          aria-label={`Fabriquer une carte ${RARITY_LABELS[card.rarity]} de ${card.content.title} pour ${card.craft_cost} fragments`}
          className="mt-1 w-full rounded-lg border border-border py-1 text-xs hover:bg-surface disabled:opacity-40"
        >
          Fabriquer · {card.craft_cost} 💎
        </button>
      )}
    </div>
  );
}
