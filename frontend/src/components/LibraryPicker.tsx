import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router";

import { apiFetch } from "../lib/api";
import type { ContentKind, Source } from "../lib/catalog";
import { LIBRARY_COLORS } from "../lib/tracking";
import type { ContentRead, Library } from "../lib/tracking";
import { useApiResource } from "../lib/useApi";

type Props = {
  content: { source: Source; kind: ContentKind; external_id: string };
  /** Identifiant interne du contenu (null tant qu'il n'est pas enregistré). */
  contentId: number | null;
  onContentId: (id: number) => void;
};

/** « Ajouter à une bibliothèque » : une case à cocher par bibliothèque. */
export function LibraryPicker({ content, contentId, onContentId }: Props) {
  const [open, setOpen] = useState(false);
  const query = new URLSearchParams(content).toString();
  // Chargée seulement à l'ouverture du panneau.
  const [state, setLibraries] = useApiResource<Library[]>(open ? `/api/libraries?${query}` : null);
  const [error, setError] = useState<string | null>(null);
  const [newName, setNewName] = useState("");

  const libraries = state.status === "success" ? state.data : [];

  function patch(id: number, changes: Partial<Library>) {
    setLibraries(libraries.map((l) => (l.id === id ? { ...l, ...changes } : l)));
  }

  async function toggle(library: Library) {
    setError(null);
    try {
      if (library.contains) {
        if (contentId === null) return;
        await apiFetch<void>(`/api/libraries/${library.id}/items/${contentId}`, { method: "DELETE" });
        patch(library.id, { contains: false, items_count: library.items_count - 1 });
      } else {
        const added = await apiFetch<ContentRead>(`/api/libraries/${library.id}/items`, {
          method: "POST",
          body: content,
        });
        onContentId(added.id);
        patch(library.id, { contains: true, items_count: library.items_count + 1 });
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec.");
    }
  }

  async function createAndAdd(event: FormEvent) {
    event.preventDefault();
    const name = newName.trim();
    if (!name) return;
    setError(null);
    try {
      const color = LIBRARY_COLORS[libraries.length % LIBRARY_COLORS.length];
      const library = await apiFetch<Library>("/api/libraries", {
        method: "POST",
        body: { name, color },
      });
      const added = await apiFetch<ContentRead>(`/api/libraries/${library.id}/items`, {
        method: "POST",
        body: content,
      });
      onContentId(added.id);
      setLibraries([...libraries, { ...library, contains: true, items_count: 1 }]);
      setNewName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec.");
    }
  }

  const inCount = libraries.filter((l) => l.contains).length;

  return (
    <section className="mt-4">
      <button
        type="button"
        aria-expanded={open}
        aria-controls="choix-bibliotheques"
        onClick={() => setOpen(!open)}
        className="w-full rounded-xl border border-border px-4 py-3 text-left font-medium hover:bg-surface"
      >
        📚 Ajouter à une bibliothèque
        {state.status === "success" && inCount > 0 && (
          <span className="text-sm text-muted"> · dans {inCount}</span>
        )}
      </button>

      {open && (
        <div id="choix-bibliotheques" className="mt-2 rounded-xl border border-border bg-surface p-4">
          {state.status === "loading" && <p className="text-sm text-muted">Chargement…</p>}
          {state.status === "error" && (
            <p role="alert" className="text-sm text-error">
              {state.error.message}
            </p>
          )}
          {state.status === "success" && (
            <>
              {libraries.length === 0 ? (
                <p className="text-sm text-muted">Vous n'avez pas encore de bibliothèque.</p>
              ) : (
                <ul className="space-y-1">
                  {libraries.map((library) => (
                    <li key={library.id}>
                      <label className="flex cursor-pointer items-center gap-3 rounded-lg px-1 py-1.5 hover:bg-bg">
                        <input
                          type="checkbox"
                          checked={library.contains === true}
                          onChange={() => void toggle(library)}
                          className="h-5 w-5 accent-accent"
                        />
                        <span
                          aria-hidden="true"
                          className="h-3 w-3 rounded-full"
                          style={{ backgroundColor: library.color }}
                        />
                        <span className="flex-1">{library.name}</span>
                        <span className="text-xs text-muted">{library.items_count}</span>
                      </label>
                    </li>
                  ))}
                </ul>
              )}
              <form onSubmit={(e) => void createAndAdd(e)} className="mt-3 flex gap-2">
                <label className="sr-only" htmlFor="nouvelle-bibliotheque">
                  Nom de la nouvelle bibliothèque
                </label>
                <input
                  id="nouvelle-bibliotheque"
                  value={newName}
                  onChange={(e) => setNewName(e.target.value)}
                  maxLength={50}
                  placeholder="Nouvelle bibliothèque…"
                  className="min-w-0 flex-1 rounded-lg border border-border bg-bg px-3 py-2 text-sm"
                />
                <button
                  type="submit"
                  disabled={!newName.trim()}
                  className="rounded-lg bg-accent px-3 py-2 text-sm font-semibold text-white disabled:opacity-40"
                >
                  Créer
                </button>
              </form>
            </>
          )}
          {error && (
            <p role="alert" className="mt-2 text-sm text-error">
              {error}
            </p>
          )}
          <Link to="/bibliotheques" className="mt-3 inline-block text-sm text-accent hover:underline">
            Gérer mes bibliothèques →
          </Link>
        </div>
      )}
    </section>
  );
}
