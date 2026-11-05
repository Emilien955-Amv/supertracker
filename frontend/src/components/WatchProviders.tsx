import type { WatchAvailability, WatchProvider } from "../lib/catalog";

const GROUPS: { key: keyof Pick<WatchAvailability, "subscription" | "free" | "rent" | "buy">; label: string }[] = [
  { key: "subscription", label: "Avec abonnement" },
  { key: "free", label: "Gratuit" },
  { key: "rent", label: "Location" },
  { key: "buy", label: "Achat" },
];

// Au-delà, la liste devient illisible sur mobile : on résume « +3 ».
const MAX_LOGOS = 6;

function ProviderLogos({ providers, fallback }: { providers: WatchProvider[]; fallback: string | null }) {
  const shown = providers.slice(0, MAX_LOGOS);
  const hidden = providers.slice(MAX_LOGOS);
  return (
    <ul className="mt-2 flex flex-wrap items-center gap-2">
      {shown.map((provider) => {
        const logo = provider.logo_url ? (
          <img
            src={provider.logo_url}
            alt={provider.name}
            loading="lazy"
            className="h-11 w-11 rounded-xl bg-border object-cover"
          />
        ) : (
          <span className="inline-block rounded-xl border border-border px-3 py-2 text-sm">
            {provider.name}
          </span>
        );
        // Lien direct vers la plateforme si on la connaît, sinon vers la page
        // récapitulative des offres (qui mène au bon titre en un clic).
        const href = provider.url ?? fallback;
        return (
          <li key={provider.name}>
            {href ? (
              <a
                href={href}
                target="_blank"
                rel="noreferrer"
                title={`Regarder sur ${provider.name}`}
                aria-label={`Regarder sur ${provider.name} (nouvel onglet)`}
                className="block rounded-xl transition-transform hover:scale-105 motion-reduce:transition-none"
              >
                {logo}
              </a>
            ) : (
              logo
            )}
          </li>
        );
      })}
      {hidden.length > 0 && (
        <li title={hidden.map((p) => p.name).join(", ")} className="text-sm text-muted">
          +{hidden.length}
          <span className="sr-only"> : {hidden.map((p) => p.name).join(", ")}</span>
        </li>
      )}
    </ul>
  );
}

/** Rubrique « Où regarder », avec la mention JustWatch exigée par TMDB. */
export function WatchProviders({ watch }: { watch: WatchAvailability }) {
  const groups = GROUPS.filter((group) => watch[group.key].length > 0);

  return (
    <section aria-labelledby="ou-regarder" className="mt-8">
      <h2 id="ou-regarder" className="text-lg font-semibold">
        Où regarder en France
      </h2>

      {groups.length === 0 ? (
        <p className="mt-2 text-muted">Pas disponible en streaming en France pour le moment.</p>
      ) : (
        <div className="mt-3 space-y-4 rounded-xl border border-border bg-surface p-4">
          {groups.map((group) => (
            <div key={group.key}>
              <h3 className="text-sm text-muted">{group.label}</h3>
              <ProviderLogos providers={watch[group.key]} fallback={watch.link} />
            </div>
          ))}
          {watch.link && (
            <a
              href={watch.link}
              target="_blank"
              rel="noreferrer"
              className="inline-block text-sm text-accent underline-offset-4 hover:underline"
            >
              Voir toutes les offres ↗
            </a>
          )}
        </div>
      )}
      <p className="mt-2 text-xs text-muted">
        Données de disponibilité fournies par{" "}
        <a href="https://www.justwatch.com/fr" target="_blank" rel="noreferrer" className="underline">
          JustWatch
        </a>
        .
      </p>
    </section>
  );
}
