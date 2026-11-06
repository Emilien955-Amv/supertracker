import type { Mastery } from "../lib/cards";

/** Carte « Maître » : dorée et animée, unique à chaque œuvre complétée. */
export function MasterCard({ mastery, className = "" }: { mastery: Mastery; className?: string }) {
  return (
    <figure
      className={`card-divine relative aspect-[5/7] overflow-hidden rounded-xl border-[3px] border-gold bg-border ${className}`}
      style={{ boxShadow: "0 0 26px 6px rgb(245 176 65 / 0.55)" }}
    >
      {mastery.poster_url && (
        <img src={mastery.poster_url} alt="" loading="lazy" className="h-full w-full object-cover" />
      )}
      <span className="absolute left-1/2 top-2 -translate-x-1/2 rounded-full bg-gradient-to-b from-[#fde68a] to-[#b45309] px-3 py-0.5 text-[10px] font-black uppercase tracking-widest text-[#3a2405] shadow">
        🏆 Maître
      </span>
      <figcaption className="absolute inset-x-0 bottom-0 bg-gradient-to-t from-[#3a2405] via-[#3a2405]/85 to-transparent p-2 pt-8 text-center">
        <p className="truncate text-sm font-black text-gold">{mastery.work_title}</p>
        <p className="truncate text-[11px] text-[#fde68a]">« {mastery.title} »</p>
      </figcaption>
    </figure>
  );
}
