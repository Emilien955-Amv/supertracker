import { useEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";

import { RARITY_COLORS, RARITY_LABELS, isEpicReveal, isShiny } from "../lib/cards";
import type { BoosterOpened, Rarity } from "../lib/cards";
import { CardBack, GameCard } from "./GameCard";

// Durées de la révélation spéciale (dernière carte Légendaire ou mieux).
const SUSPENSE_MS = 1800; // la carte tremble et s'illumine…
const BANNER_MS = 2600; // … puis « LÉGENDAIRE ! » s'affiche

type Props = {
  booster: BoosterOpened;
  onClose: () => void;
  /** Ouvrir le booster suivant (proposé s'il en reste). */
  onNext: () => void;
};

/** Ouverture d'un booster : 5 cartes face cachée, à retourner une à une.
 * Si la dernière est Légendaire, Mythique ou Divine : révélation spéciale. */
export function BoosterReveal({ booster, onClose, onNext }: Props) {
  const [revealed, setRevealed] = useState<boolean[]>(() => booster.cards.map(() => false));
  const [suspense, setSuspense] = useState(false);
  const [banner, setBanner] = useState<Rarity | null>(null);
  const title = useRef<HTMLHeadingElement>(null);
  const timers = useRef<number[]>([]);
  const last = booster.cards.length - 1;
  const lastRarity = booster.cards[last]?.card.rarity;
  const special = lastRarity !== undefined && isEpicReveal(lastRarity);
  const allRevealed = revealed.every(Boolean);

  useEffect(() => {
    title.current?.focus(); // le lecteur d'écran annonce la fenêtre
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    const pending = timers.current;
    return () => {
      window.removeEventListener("keydown", onKey);
      pending.forEach((id) => window.clearTimeout(id));
    };
  }, [onClose]);

  const flip = (indexes: number[]) =>
    setRevealed((list) => list.map((value, i) => value || indexes.includes(i)));

  function reveal(index: number) {
    if (revealed[index] || suspense) return;
    if (index !== last || !special || !lastRarity) {
      flip([index]);
      return;
    }
    // Révélation spéciale : suspense, retournement, puis bannière.
    setSuspense(true);
    timers.current.push(
      window.setTimeout(() => {
        setSuspense(false);
        flip([index]);
        setBanner(lastRarity);
        timers.current.push(window.setTimeout(() => setBanner(null), BANNER_MS));
      }, SUSPENSE_MS),
    );
  }

  function revealAll() {
    flip(booster.cards.map((_, i) => i).filter((i) => i !== last || !special));
    if (special) reveal(last);
  }

  const glow = (rarity: Rarity) => ({ "--glow": RARITY_COLORS[rarity] }) as CSSProperties;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="booster-titre"
      className="fixed inset-0 z-40 overflow-y-auto bg-bg/95 px-4 py-8 backdrop-blur"
    >
      {/* Halo pulsant derrière tout l'écran pendant le suspense. */}
      {suspense && lastRarity && (
        <div aria-hidden="true" className="reveal-backdrop pointer-events-none fixed inset-0" style={glow(lastRarity)} />
      )}

      <div className="relative mx-auto max-w-3xl">
        <h2 id="booster-titre" ref={title} tabIndex={-1} className="text-center text-2xl font-bold outline-none">
          🎁 Votre booster
        </h2>
        <p className="mt-1 text-center text-sm text-muted" aria-live="polite">
          {suspense
            ? "✨ Quelque chose de rare arrive…"
            : allRevealed
              ? "Toutes vos cartes sont révélées !"
              : "Touchez une carte pour la retourner."}
        </p>

        <ul className="mt-6 grid grid-cols-3 gap-3 sm:grid-cols-5">
          {booster.cards.map(({ card, is_new, fragments }, index) => {
            const shaking = suspense && index === last;
            return (
              <li key={index}>
                <button
                  type="button"
                  onClick={() => reveal(index)}
                  disabled={revealed[index] || suspense}
                  aria-label={
                    revealed[index]
                      ? `${card.title}, ${RARITY_LABELS[card.rarity]}${is_new ? ", nouvelle" : ""}`
                      : `Retourner la carte ${index + 1}`
                  }
                  className="block w-full perspective-distant"
                >
                  {/* Retournement en 3D : deux faces dos à dos, on pivote de 180°. */}
                  <div
                    className={`relative transition-transform duration-700 transform-3d motion-reduce:transition-none ${revealed[index] ? "rotate-y-180" : ""}`}
                  >
                    <div className="backface-hidden">
                      <CardBack
                        className={shaking ? "card-suspense" : ""}
                        style={shaking ? { ...glow(card.rarity), borderColor: RARITY_COLORS[card.rarity] } : undefined}
                      />
                    </div>
                    <div
                      className="absolute inset-0 rotate-y-180 backface-hidden"
                      style={
                        revealed[index] && isShiny(card.rarity)
                          ? { filter: `drop-shadow(0 0 12px ${RARITY_COLORS[card.rarity]})` }
                          : undefined
                      }
                    >
                      <GameCard card={card} />
                    </div>
                  </div>
                </button>
                {revealed[index] && (
                  <p className="mt-1 text-center text-xs" aria-hidden="true">
                    {is_new ? (
                      <span className="font-semibold text-ok">Nouvelle !</span>
                    ) : (
                      <span className="text-muted">Doublon · +{fragments} 💎</span>
                    )}
                  </p>
                )}
              </li>
            );
          })}
        </ul>

        <div className="mt-8 flex flex-wrap justify-center gap-3">
          {!allRevealed && !suspense && (
            <button
              type="button"
              onClick={revealAll}
              className="rounded-xl border border-border px-4 py-2 hover:bg-surface"
            >
              Tout retourner
            </button>
          )}
          {allRevealed && booster.boosters_left > 0 && (
            <button
              type="button"
              onClick={onNext}
              className="rounded-xl bg-accent px-4 py-2 font-semibold text-white"
            >
              Ouvrir le suivant ({booster.boosters_left})
            </button>
          )}
          <button
            type="button"
            onClick={onClose}
            className="rounded-xl border border-border px-4 py-2 hover:bg-surface"
          >
            Fermer
          </button>
        </div>
        <p className="mt-4 text-center text-sm text-muted">Fragments : {booster.fragments} 💎</p>
      </div>

      {/* Bannière « LÉGENDAIRE ! » par-dessus tout. */}
      {banner && (
        <div className="pointer-events-none fixed inset-0 z-50 flex items-center justify-center" role="status">
          <p
            className="reveal-banner text-center text-5xl font-black uppercase tracking-widest sm:text-6xl"
            style={{ ...glow(banner), color: RARITY_COLORS[banner] }}
          >
            {RARITY_LABELS[banner]} !
          </p>
        </div>
      )}
    </div>
  );
}
