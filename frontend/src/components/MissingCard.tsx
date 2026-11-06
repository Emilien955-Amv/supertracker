import { RARITY_LABELS } from "../lib/cards";
import type { CollectionCard } from "../lib/cards";
import { CardBack } from "./GameCard";

/** Carte pas encore obtenue : dos de carte, rareté visible, fabrication possible. */
export function MissingCard({
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
