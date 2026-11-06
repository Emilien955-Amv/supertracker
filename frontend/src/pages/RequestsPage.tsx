import { Link } from "react-router";

import { Poster } from "../components/Poster";
import { ProgressBar } from "../components/ProgressBar";
import { apiFetch } from "../lib/api";
import { KIND_LABELS, contentPath } from "../lib/catalog";
import type { WorkRequest } from "../lib/requests";
import { useApiResource } from "../lib/useApi";

/** Sondages : les œuvres que les joueurs veulent en cartes, les plus votées d'abord. */
export default function RequestsPage() {
  const [state, setRequests] = useApiResource<WorkRequest[]>("/api/requests");

  async function toggle(request: WorkRequest) {
    if (request.voted) {
      await apiFetch<void>(`/api/requests/${request.id}/vote`, { method: "DELETE" });
    } else {
      await apiFetch<WorkRequest>("/api/requests", {
        method: "POST",
        body: { source: request.source, kind: request.kind, external_id: request.external_id },
      });
    }
    setRequests(await apiFetch<WorkRequest[]>("/api/requests"));
  }

  const requests = state.status === "success" ? state.data : [];
  const open = requests.filter((r) => r.status === "open");
  const added = requests.filter((r) => r.status === "added");

  return (
    <main className="mx-auto max-w-3xl px-5 pt-6">
      <Link to="/cartes" className="text-sm text-muted hover:text-text">
        ← Mes cartes
      </Link>
      <h1 className="mt-3 text-2xl font-bold">🗳️ Demandes de cartes</h1>
      <p className="mt-1 text-muted">
        Une série, un film ou un anime n'a pas encore ses cartes ? Demandez-les depuis sa fiche
        (bouton « Demander ses cartes »), puis votez ici. Au seuil de votes, ses cartes sont créées.
      </p>
      <Link to="/recherche" className="mt-2 inline-block text-sm text-accent hover:underline">
        Chercher une œuvre à demander →
      </Link>

      {state.status === "error" && (
        <p role="alert" className="mt-4 text-error">
          {state.error.message}
        </p>
      )}

      <section aria-labelledby="ouvertes" className="mt-6">
        <h2 id="ouvertes" className="font-semibold">
          En attente de votes ({open.length})
        </h2>
        {open.length === 0 ? (
          <p className="mt-2 text-sm text-muted">Aucune demande pour l'instant.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {open.map((request) => (
              <li key={request.id} className="flex items-center gap-3 rounded-xl border border-border bg-surface p-3">
                <Link to={contentPath(request)} className="w-12 shrink-0">
                  <Poster url={request.poster_url} title={request.title} className="rounded-md text-[8px]" />
                </Link>
                <div className="min-w-0 flex-1">
                  <Link to={contentPath(request)} className="block truncate font-medium hover:underline">
                    {request.title}
                  </Link>
                  <p className="text-xs text-muted">
                    {KIND_LABELS[request.kind]}
                    {request.year && ` · ${request.year}`} · {request.votes} / {request.votes_needed} votes
                  </p>
                  <div className="mt-1">
                    <ProgressBar
                      percent={Math.min(100, Math.round((100 * request.votes) / request.votes_needed))}
                      label={`Votes pour ${request.title}`}
                    />
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => void toggle(request)}
                  aria-pressed={request.voted}
                  aria-label={`${request.voted ? "Retirer mon vote" : "Voter"} : ${request.title}`}
                  className={`shrink-0 rounded-lg px-3 py-1.5 text-sm ${
                    request.voted ? "border border-accent text-accent" : "bg-accent font-semibold text-white"
                  }`}
                >
                  {request.voted ? "✔ Voté" : "Voter"}
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {added.length > 0 && (
        <section aria-labelledby="ajoutees" className="mt-6">
          <h2 id="ajoutees" className="font-semibold">
            ✅ Ajoutées grâce à vos votes
          </h2>
          <ul className="mt-2 grid grid-cols-3 gap-3 sm:grid-cols-5">
            {added.map((request) => (
              <li key={request.id}>
                <Link to={contentPath(request)} className="block">
                  <Poster url={request.poster_url} title={request.title} />
                  <p className="mt-1 truncate text-xs">{request.title}</p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
    </main>
  );
}
