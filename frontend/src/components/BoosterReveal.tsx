import { useEffect, useRef, useState } from "react";

import { RARITY_COLORS, RARITY_LABELS, isShiny } from "../lib/cards";
import type { BoosterOpened } from "../lib/cards";
import { CardBack, GameCard } from "./GameCard";

type Props = {
  booster: BoosterOpened;
  onClose: () => void;
  /** Ouvrir le booster suivant (proposé s'il en reste). */
  onNext: () => void;
};

/** Ouverture d'un booster : 5 cartes face cachée, à retourner une à une. */
export function BoosterReveal({ booster, onClose, onNext }: Props) {
  const [revealed, setRevealed] = useState<boolean[]>(() => booster.cards.map(() => false));
  const title = useRef<HTMLHeadingElement>(null);
  const allRevealed = revealed.every(Boolean);

  useEffect(() => {
    title.current?.focus(); // le lecteur d'écran annonce la fenêtre
    const onKey = (event: KeyboardEvent) => event.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  const reveal = (index: number) =>
    setRevealed((list) => list.map((value, i) => (i === index ? true : value)));

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="booster-titre"
      className="fixed inset-0 z-40 overflow-y-auto bg-bg/95 px-4 py-8 backdrop-blur"
    >
      <div className="mx-auto max-w-3xl">
        <h2 id="booster-titre" ref={title} tabIndex={-1} className="text-center text-2xl font-bold outline-none">
          🎁 Votre booster
        </h2>
        <p className="mt-1 text-center text-sm text-muted">
          {allRevealed ? "Toutes vos cartes sont révélées !" : "Touchez une carte pour la retourner."}
        </p>

        <ul className="mt-6 grid grid-cols-3 gap-3 sm:grid-cols-5">
          {booster.cards.map(({ card, is_new, fragments }, index) => (
            <li key={index}>
              <button
                type="button"
                onClick={() => reveal(index)}
                disabled={revealed[index]}
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
                    <CardBack />
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
          ))}
        </ul>

        <div className="mt-8 flex flex-wrap justify-center gap-3">
          {!allRevealed && (
            <button
              type="button"
              onClick={() => setRevealed(booster.cards.map(() => true))}
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
    </div>
  );
}
