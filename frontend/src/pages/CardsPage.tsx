import { useEffect, useRef, useState } from "react";
import type { ReactNode } from "react";
import { Link } from "react-router";

import { Binder } from "../components/Binder";
import { BoosterReveal } from "../components/BoosterReveal";
import { apiFetch } from "../lib/api";
import {
  GENRE_THEMES,
  PLATFORM_COLORS,
  RARITIES,
  RARITY_COLORS,
  RARITY_LABELS,
  THEME_ICONS,
} from "../lib/cards";
import type { BoosterOpened, Collection, GenreTheme, PackTheme, PlatformTheme } from "../lib/cards";
import { useApiResource } from "../lib/useApi";

/** Page des cartes : boosters (par genre ou plateforme), progression, classeur. */
export default function CardsPage() {
  const [state, setCollection] = useApiResource<Collection>("/api/cards/me");
  const [opened, setOpened] = useState<BoosterOpened | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [byTen, setByTen] = useState(false); // ouvrir 10 boosters d'un coup
  // Change après une ouverture : le classeur se recharge.
  const [binderKey, setBinderKey] = useState(0);

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
          body: { theme, count: byTen ? 10 : 1 },
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec de l'ouverture.");
    } finally {
      setBusy(false);
    }
  }

  const ownedTotal = collection.stats.reduce((sum, s) => sum + s.owned, 0);
  const catalogTotal = collection.stats.reduce((sum, s) => sum + s.total, 0);
  const genres = collection.themes.filter((t) => GENRE_THEMES.includes(t.theme as GenreTheme));
  const platforms = collection.themes.filter((t) => !GENRE_THEMES.includes(t.theme as GenreTheme));

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
            {collection.boosters > 1 && (
              <label className="mt-4 flex items-center justify-center gap-2 text-sm">
                <input
                  type="checkbox"
                  checked={byTen}
                  onChange={(e) => setByTen(e.target.checked)}
                  className="h-5 w-5 accent-accent"
                />
                Ouvrir par 10 (50 cartes d'un coup)
              </label>
            )}
            <p className="mt-4 text-center text-sm text-muted">Choisissez votre pack :</p>
            <h3 className="mt-3 text-xs font-semibold uppercase tracking-wide text-muted">Par genre</h3>
            <ul className="mt-2 grid grid-cols-2 gap-2">
              {genres.map((theme) => (
                <li key={theme.theme}>
                  <PackButton theme={theme} busy={busy} onOpen={() => void openBooster(theme.theme)}>
                    <span aria-hidden="true">{THEME_ICONS[theme.theme as GenreTheme]}</span> {theme.label}
                  </PackButton>
                </li>
              ))}
            </ul>
            <h3 className="mt-4 text-xs font-semibold uppercase tracking-wide text-muted">
              Par plateforme
            </h3>
            <ul className="mt-2 grid grid-cols-2 gap-2 sm:grid-cols-3">
              {platforms.map((theme) => (
                <li key={theme.theme}>
                  <PackButton
                    theme={theme}
                    busy={busy}
                    onOpen={() => void openBooster(theme.theme)}
                    color={PLATFORM_COLORS[theme.theme as PlatformTheme]}
                  >
                    {theme.label}
                  </PackButton>
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

      {/* Progression par rareté et probabilité de chacune. */}
      <section aria-labelledby="raretes" className="mt-6">
        <h2 id="raretes" className="sr-only">
          Progression par rareté
        </h2>
        <ul className="flex flex-wrap gap-2">
          {RARITIES.map((r) => {
            const stat = collection.stats.find((s) => s.rarity === r);
            return (
              <li
                key={r}
                className="rounded-full border px-3 py-1 text-xs"
                style={{ borderColor: RARITY_COLORS[r], color: RARITY_COLORS[r] }}
              >
                {RARITY_LABELS[r]} {stat?.owned ?? 0}/{stat?.total ?? 0}
                <span className="opacity-70"> · {stat?.chance_percent ?? 0} %</span>
              </li>
            );
          })}
        </ul>
      </section>

      <Link
        to="/cartes/demandes"
        className="mt-6 flex items-center justify-between rounded-xl border border-border bg-surface p-4 hover:border-accent/60"
      >
        <span>
          <span className="block font-semibold">🗳️ Demandes de cartes</span>
          <span className="text-sm text-muted">Votez pour les séries, films et animes à ajouter</span>
        </span>
        <span aria-hidden="true" className="text-accent">
          →
        </span>
      </Link>

      <Binder key={binderKey} />

      {opened && (
        <BoosterReveal
          booster={opened}
          onClose={() => {
            setOpened(null);
            setBinderKey((k) => k + 1);
            void reload();
          }}
          onNext={() => void openBooster(opened.theme)}
        />
      )}
    </main>
  );
}

/** Bouton d'un pack : nom, nombre de cartes, lien vers la liste des cartes. */
function PackButton({
  theme,
  busy,
  onOpen,
  color,
  children,
}: {
  theme: Collection["themes"][number];
  busy: boolean;
  onOpen: () => void;
  color?: string;
  children: ReactNode;
}) {
  return (
    <div>
      <button
        type="button"
        onClick={onOpen}
        disabled={busy || theme.cards === 0}
        aria-label={`Ouvrir un pack ${theme.label}`}
        className="w-full rounded-xl border border-accent/50 bg-surface px-3 py-3 font-semibold hover:bg-accent/20 disabled:opacity-40"
        style={color ? { borderLeft: `6px solid ${color}` } : undefined}
      >
        {children}
        <span className="block text-xs font-normal text-muted">
          {theme.cards > 0 ? `${theme.cards} cartes` : "En préparation…"}
        </span>
      </button>
      {theme.cards > 0 && (
        <Link
          to={`/cartes/pack/${theme.theme}`}
          className="mt-1 block text-center text-xs text-accent hover:underline"
        >
          Voir les cartes
          <span className="sr-only"> du pack {theme.label}</span>
        </Link>
      )}
    </div>
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
      · un toutes les {collection.free_booster_minutes} min, et un par film, série ou anime
      terminé
    </p>
  );
}
