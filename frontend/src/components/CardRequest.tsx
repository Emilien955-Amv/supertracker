import { useState } from "react";
import { Link } from "react-router";

import { apiFetch } from "../lib/api";
import type { ContentKind, Source } from "../lib/catalog";
import type { CatalogStatus, WorkRequest } from "../lib/requests";
import { useApiResource } from "../lib/useApi";

type Props = { content: { source: Source; kind: ContentKind; external_id: string } };

/** Encart « Cartes » de la fiche : l'œuvre a-t-elle ses cartes ? Sinon, la demander. */
export function CardRequest({ content }: Props) {
  const path = `/api/requests/status/${content.source}/${content.kind}/${content.external_id}`;
  const [state, setStatus] = useApiResource<CatalogStatus>(path);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (state.status !== "success") return null;
  const { in_catalog, request } = state.data;

  async function vote() {
    setBusy(true);
    setError(null);
    try {
      const updated = await apiFetch<WorkRequest>("/api/requests", { method: "POST", body: content });
      setStatus({ in_catalog: updated.status === "added", request: updated });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec.");
    } finally {
      setBusy(false);
    }
  }

  async function unvote(current: WorkRequest) {
    setBusy(true);
    try {
      await apiFetch<void>(`/api/requests/${current.id}/vote`, { method: "DELETE" });
      setStatus(await apiFetch<CatalogStatus>(path));
    } finally {
      setBusy(false);
    }
  }

  return (
    <section aria-labelledby="cartes-oeuvre" className="mt-4 rounded-xl border border-border bg-surface p-4">
      <h2 id="cartes-oeuvre" className="font-semibold">
        🃏 Cartes à collectionner
      </h2>
      {in_catalog ? (
        <p className="mt-1 text-sm text-muted">
          Cette œuvre a ses cartes de personnages.{" "}
          <Link to="/cartes" className="text-accent hover:underline">
            Ouvrir un booster →
          </Link>
        </p>
      ) : (
        <>
          <p className="mt-1 text-sm text-muted">
            {request
              ? `Demande en cours : ${request.votes} / ${request.votes_needed} votes pour ajouter ses cartes.`
              : "Pas encore de cartes pour cette œuvre. Demandez-les : à "}
            {!request && "3 votes, elles sont créées."}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            {request?.voted ? (
              <button
                type="button"
                onClick={() => void unvote(request)}
                disabled={busy}
                className="rounded-lg border border-border px-3 py-1.5 text-sm hover:bg-bg disabled:opacity-50"
              >
                ✔ Vous avez voté · Retirer mon vote
              </button>
            ) : (
              <button
                type="button"
                onClick={() => void vote()}
                disabled={busy}
                className="rounded-lg bg-accent px-3 py-1.5 text-sm font-semibold text-white disabled:opacity-50"
              >
                {request ? "Voter pour ses cartes" : "Demander ses cartes"}
              </button>
            )}
            <Link to="/cartes/demandes" className="text-sm text-accent hover:underline">
              Toutes les demandes
            </Link>
          </div>
        </>
      )}
      {error && (
        <p role="alert" className="mt-2 text-sm text-error">
          {error}
        </p>
      )}
    </section>
  );
}
