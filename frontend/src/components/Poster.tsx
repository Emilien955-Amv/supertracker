import { useState } from "react";

/** Affiche d'un contenu, chargée seulement quand elle devient visible
 * (loading="lazy"), avec une vignette de remplacement si l'image manque. */
export function Poster({
  url,
  title,
  className = "",
}: {
  url: string | null;
  title: string;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);

  if (!url || failed) {
    return (
      <div
        aria-hidden="true"
        className={`flex aspect-[2/3] items-center justify-center rounded-xl bg-border p-2 text-center text-xs text-muted ${className}`}
      >
        {title}
      </div>
    );
  }
  return (
    <img
      src={url}
      alt=""
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
      className={`aspect-[2/3] w-full rounded-xl bg-border object-cover ${className}`}
    />
  );
}
