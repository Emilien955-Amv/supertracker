import { RARITY_COLORS, RARITY_LABELS } from "../lib/cards";
import type { CardRead, Rarity } from "../lib/cards";

const EFFECTS: Partial<Record<Rarity, string>> = { mythic: "card-mythic", divine: "card-divine" };

/** Face avant d'une carte : image, nom, rareté et cadre coloré. */
export function GameCard({ card }: { card: CardRead }) {
  const color = RARITY_COLORS[card.rarity];
  return (
    <figure
      className={`relative aspect-[5/7] overflow-hidden rounded-xl border-[3px] bg-border ${EFFECTS[card.rarity] ?? ""}`}
      style={{ borderColor: color }}
    >
      <img
        src={card.image_url}
        alt=""
        loading="lazy"
        className={`h-full w-full ${card.kind === "backdrop" || card.kind === "still" ? "object-cover object-center" : "object-cover object-top"}`}
      />
      <span
        className="absolute left-1.5 top-1.5 rounded-full bg-bg/80 px-2 py-0.5 text-[10px] font-bold uppercase tracking-wide"
        style={{ color }}
      >
        {RARITY_LABELS[card.rarity]}
      </span>
      <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-bg via-bg/85 to-transparent p-2 pt-6">
        <p className="truncate text-sm font-bold leading-tight">{card.title}</p>
        {card.subtitle && <p className="truncate text-[11px] text-muted">{card.subtitle}</p>}
        <p className="truncate text-[10px] text-muted/80">{card.content.title}</p>
      </figcaption>
    </figure>
  );
}

/** Dos de carte : sert aux cartes pas encore révélées ou pas encore obtenues. */
export function CardBack({ rarity, label }: { rarity?: Rarity; label?: string }) {
  const color = rarity ? RARITY_COLORS[rarity] : "#7c5cff";
  return (
    <div
      className="flex aspect-[5/7] flex-col items-center justify-center rounded-xl border-[3px] bg-[radial-gradient(circle_at_50%_35%,#2a2147,#0b0d12)] p-2 text-center"
      style={{ borderColor: `${color}99` }}
    >
      <span aria-hidden="true" className="text-3xl">
        ✦
      </span>
      {label && <span className="mt-2 text-[11px] leading-tight text-muted">{label}</span>}
    </div>
  );
}
