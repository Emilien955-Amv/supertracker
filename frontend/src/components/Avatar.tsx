/** Pastille avec l'initiale du pseudo (les photos de profil viendront plus tard). */
export function Avatar({ username, size = "h-9 w-9 text-sm" }: { username: string; size?: string }) {
  return (
    <span
      aria-hidden="true"
      className={`flex shrink-0 items-center justify-center rounded-full bg-accent/25 font-bold text-accent ${size}`}
    >
      {username.slice(0, 1).toUpperCase()}
    </span>
  );
}
