/** Indicateur de chargement accessible (annoncé par les lecteurs d'écran). */
export function Spinner({ label }: { label: string }) {
  return (
    <div role="status" className="flex min-h-dvh flex-col items-center justify-center gap-3">
      <span
        aria-hidden="true"
        className="h-8 w-8 animate-spin rounded-full border-4 border-border border-t-accent motion-reduce:animate-none"
      />
      <span className="text-muted">{label}</span>
    </div>
  );
}
