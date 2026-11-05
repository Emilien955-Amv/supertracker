import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router";

import { ColorPicker } from "../components/ColorPicker";
import { apiFetch } from "../lib/api";
import { LIBRARY_COLORS } from "../lib/tracking";
import type { Library } from "../lib/tracking";
import { useApiResource } from "../lib/useApi";

/** « Mes bibliothèques » : liste et création. */
export default function LibrariesPage() {
  const [state, setLibraries] = useApiResource<Library[]>("/api/libraries");
  const [name, setName] = useState("");
  const [color, setColor] = useState(LIBRARY_COLORS[0]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (state.status !== "success" || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      const library = await apiFetch<Library>("/api/libraries", {
        method: "POST",
        body: { name: name.trim(), color },
      });
      setLibraries([...state.data, library]);
      setName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-3xl px-5 pt-8">
      <h1 className="text-2xl font-bold">Mes bibliothèques</h1>
      <p className="mt-1 text-muted">Rangez vos films, séries et animes comme vous l'entendez.</p>

      <form
        onSubmit={(e) => void create(e)}
        className="mt-6 space-y-3 rounded-xl border border-border bg-surface p-4"
      >
        <label className="block text-sm">
          <span className="text-muted">Nouvelle bibliothèque</span>
          <input
            value={name}
            onChange={(e) => setName(e.target.value)}
            maxLength={50}
            placeholder="Ex. Coups de cœur, Animes d'enfance…"
            className="mt-1 block w-full rounded-lg border border-border bg-bg px-3 py-2"
          />
        </label>
        <ColorPicker name="couleur-creation" value={color} onChange={setColor} />
        <button
          type="submit"
          disabled={busy || !name.trim()}
          className="rounded-xl bg-accent px-4 py-2 font-semibold text-white disabled:opacity-40"
        >
          Créer
        </button>
        {error && (
          <p role="alert" className="text-sm text-error">
            {error}
          </p>
        )}
      </form>

      <div className="mt-6">
        {state.status === "loading" && <p className="text-muted">Chargement…</p>}
        {state.status === "error" && (
          <p role="alert" className="text-error">
            {state.error.message}
          </p>
        )}
        {state.status === "success" && state.data.length === 0 && (
          <p className="text-center text-muted">Aucune bibliothèque pour l'instant.</p>
        )}
        {state.status === "success" && state.data.length > 0 && (
          <ul className="grid grid-cols-2 gap-4 sm:grid-cols-3">
            {state.data.map((library) => (
              <li key={library.id}>
                <LibraryCard library={library} />
              </li>
            ))}
          </ul>
        )}
      </div>
    </main>
  );
}

function LibraryCard({ library }: { library: Library }) {
  // Aperçu : les 4 premières affiches en mosaïque 2 × 2.
  const cells = Array.from({ length: 4 }, (_, i) => library.preview[i]);
  return (
    <Link
      to={`/bibliotheques/${library.id}`}
      className="block overflow-hidden rounded-xl border border-border bg-surface hover:border-accent/60"
      style={{ borderTopColor: library.color, borderTopWidth: 4 }}
    >
      <div className="grid grid-cols-2 gap-0.5 bg-border">
        {cells.map((url, i) =>
          url ? (
            <img key={i} src={url} alt="" loading="lazy" className="aspect-[2/3] w-full object-cover" />
          ) : (
            <div
              key={i}
              className="aspect-[2/3] w-full"
              style={{ backgroundColor: `${library.color}22` }}
            />
          ),
        )}
      </div>
      <div className="p-3">
        <p className="truncate font-semibold">{library.name}</p>
        <p className="text-xs text-muted">
          {library.items_count} {library.items_count > 1 ? "éléments" : "élément"}
        </p>
      </div>
    </Link>
  );
}
