import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate, useParams } from "react-router";

import { ColorPicker } from "../components/ColorPicker";
import { Poster } from "../components/Poster";
import { ApiError, apiFetch } from "../lib/api";
import { KIND_LABELS, contentPath } from "../lib/catalog";
import type { ContentKind } from "../lib/catalog";
import { SORT_MODE_LABELS, STATUS_COLORS, STATUS_LABELS, VIEW_MODE_LABELS } from "../lib/tracking";
import type { LibraryDetail, LibraryItem, SortMode, ViewMode } from "../lib/tracking";
import { useApiResource } from "../lib/useApi";

/** Une bibliothèque : affichage au choix, tri, réorganisation et réglages. */
export default function LibraryPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const path = `/api/libraries/${id}`;
  const [state, setLibrary] = useApiResource<LibraryDetail>(path);
  const [organizing, setOrganizing] = useState(false);
  const [editing, setEditing] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (state.status === "idle" || state.status === "loading") {
    return <main className="mx-auto max-w-3xl px-5 pt-8 text-muted">Chargement…</main>;
  }
  if (state.status === "error") {
    const notFound = state.error instanceof ApiError && [404, 422].includes(state.error.status);
    return (
      <main className="mx-auto max-w-3xl px-5 pt-8">
        <p role="alert" className="rounded-xl border border-error/40 bg-error/10 p-4 text-error">
          {notFound ? "Cette bibliothèque est introuvable." : state.error.message}
        </p>
        <Link to="/bibliotheques" className="mt-4 inline-block text-accent hover:underline">
          ← Mes bibliothèques
        </Link>
      </main>
    );
  }

  const library = state.data;

  /** Exécute une modification ; en cas d'échec, restaure l'état précédent. */
  async function run(action: () => Promise<void>) {
    const previous = library;
    setError(null);
    try {
      await action();
    } catch (err) {
      setLibrary(previous);
      setError(err instanceof Error ? err.message : "Échec.");
    }
  }

  const reload = async () => setLibrary(await apiFetch<LibraryDetail>(path));

  function changeSettings(changes: { view_mode?: ViewMode; sort_mode?: SortMode }) {
    setLibrary({ ...library, ...changes }); // affichage immédiat
    void run(async () => {
      await apiFetch(path, { method: "PATCH", body: changes });
      if (changes.sort_mode) await reload(); // le serveur renvoie le nouvel ordre
    });
  }

  function move(index: number, offset: -1 | 1) {
    const items = [...library.items];
    const target = index + offset;
    if (target < 0 || target >= items.length) return;
    [items[index], items[target]] = [items[target], items[index]];
    setLibrary({ ...library, items, sort_mode: "manual" });
    void run(() =>
      apiFetch(`${path}/order`, {
        method: "PUT",
        body: { content_ids: items.map((item) => item.content.id) },
      }),
    );
  }

  function remove(item: LibraryItem) {
    const items = library.items.filter((i) => i.content.id !== item.content.id);
    setLibrary({ ...library, items, items_count: items.length });
    void run(() => apiFetch(`${path}/items/${item.content.id}`, { method: "DELETE" }));
  }

  async function destroy() {
    if (!window.confirm(`Supprimer la bibliothèque « ${library.name} » ? Son contenu reste dans votre suivi.`)) {
      return;
    }
    await run(async () => {
      await apiFetch(path, { method: "DELETE" });
      navigate("/bibliotheques", { replace: true });
    });
  }

  return (
    <main className="mx-auto max-w-3xl px-5 pt-6">
      <Link to="/bibliotheques" className="text-sm text-muted hover:text-text">
        ← Mes bibliothèques
      </Link>

      <header className="mt-3 flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-3">
          <span aria-hidden="true" className="h-4 w-4 shrink-0 rounded-full" style={{ backgroundColor: library.color }} />
          <div className="min-w-0">
            <h1 className="truncate text-2xl font-bold">{library.name}</h1>
            <p className="text-sm text-muted">
              {library.items.length} {library.items.length > 1 ? "éléments" : "élément"}
            </p>
          </div>
        </div>
        <button
          type="button"
          aria-expanded={editing}
          onClick={() => setEditing(!editing)}
          className="shrink-0 rounded-xl border border-border px-3 py-2 text-sm hover:bg-surface"
        >
          Réglages
        </button>
      </header>

      {editing && (
        <SettingsForm
          library={library}
          onSaved={(changes) => {
            setLibrary({ ...library, ...changes });
            setEditing(false);
          }}
          onDelete={() => void destroy()}
        />
      )}

      {/* Barre d'outils : affichage, tri, organisation. */}
      <div className="mt-5 flex flex-wrap items-center gap-3">
        <div role="group" aria-label="Affichage" className="flex rounded-xl border border-border p-0.5">
          {(Object.keys(VIEW_MODE_LABELS) as ViewMode[]).map((mode) => (
            <button
              key={mode}
              type="button"
              aria-pressed={library.view_mode === mode}
              onClick={() => changeSettings({ view_mode: mode })}
              className={`rounded-lg px-3 py-1.5 text-sm ${
                library.view_mode === mode ? "bg-accent font-semibold text-white" : "hover:bg-surface"
              }`}
            >
              {VIEW_MODE_LABELS[mode]}
            </button>
          ))}
        </div>
        <label className="flex items-center gap-2 text-sm">
          <span className="text-muted">Tri</span>
          <select
            value={library.sort_mode}
            onChange={(e) => changeSettings({ sort_mode: e.target.value as SortMode })}
            className="rounded-lg border border-border bg-bg px-2 py-1.5"
          >
            {(Object.keys(SORT_MODE_LABELS) as SortMode[]).map((mode) => (
              <option key={mode} value={mode}>
                {SORT_MODE_LABELS[mode]}
              </option>
            ))}
          </select>
        </label>
        {library.items.length > 0 && (
          <button
            type="button"
            aria-pressed={organizing}
            onClick={() => setOrganizing(!organizing)}
            className={`rounded-xl border px-3 py-1.5 text-sm ${
              organizing ? "border-accent text-accent" : "border-border hover:bg-surface"
            }`}
          >
            {organizing ? "Terminer" : "Organiser"}
          </button>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-error">
          {error}
        </p>
      )}

      <div className="mt-5">
        {library.items.length === 0 ? (
          <div className="rounded-xl border border-border bg-surface p-6 text-center">
            <p className="text-muted">Cette bibliothèque est vide.</p>
            <p className="mt-1 text-sm text-muted">
              Ouvrez la fiche d'un contenu puis « Ajouter à une bibliothèque ».
            </p>
            <Link to="/recherche" className="mt-3 inline-block text-accent hover:underline">
              Rechercher un contenu →
            </Link>
          </div>
        ) : organizing ? (
          <OrganizeList items={library.items} onMove={move} onRemove={remove} />
        ) : library.view_mode === "grid" ? (
          <GridView items={library.items} />
        ) : library.view_mode === "shelf" ? (
          <ShelfView items={library.items} byCategory={library.sort_mode === "category"} />
        ) : (
          <ListView items={library.items} />
        )}
      </div>
    </main>
  );
}

function SettingsForm({
  library,
  onSaved,
  onDelete,
}: {
  library: LibraryDetail;
  onSaved: (changes: { name: string; color: string }) => void;
  onDelete: () => void;
}) {
  const [name, setName] = useState(library.name);
  const [color, setColor] = useState(library.color);
  const [error, setError] = useState<string | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    try {
      const saved = await apiFetch<{ name: string; color: string }>(`/api/libraries/${library.id}`, {
        method: "PATCH",
        body: { name: name.trim(), color },
      });
      onSaved({ name: saved.name, color: saved.color });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Échec.");
    }
  }

  return (
    <form onSubmit={(e) => void submit(e)} className="mt-4 space-y-3 rounded-xl border border-border bg-surface p-4">
      <label className="block text-sm">
        <span className="text-muted">Nom</span>
        <input
          value={name}
          onChange={(e) => setName(e.target.value)}
          maxLength={50}
          required
          className="mt-1 block w-full rounded-lg border border-border bg-bg px-3 py-2"
        />
      </label>
      <ColorPicker name="couleur-reglages" value={color} onChange={setColor} />
      {error && (
        <p role="alert" className="text-sm text-error">
          {error}
        </p>
      )}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <button
          type="submit"
          disabled={!name.trim()}
          className="rounded-xl bg-accent px-4 py-2 font-semibold text-white disabled:opacity-40"
        >
          Enregistrer
        </button>
        <button type="button" onClick={onDelete} className="text-sm text-error hover:underline">
          Supprimer la bibliothèque
        </button>
      </div>
    </form>
  );
}

function StatusBadge({ item }: { item: LibraryItem }) {
  const status = item.tracking_status;
  if (!status) return null;
  const label = item.content.kind === "movie" && status === "completed" ? "Vu" : STATUS_LABELS[status];
  return <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_COLORS[status]}`}>{label}</span>;
}

function GridView({ items }: { items: LibraryItem[] }) {
  return (
    <ul className="grid grid-cols-3 gap-3 sm:grid-cols-5">
      {items.map((item) => (
        <li key={item.content.id}>
          <Link to={contentPath(item.content)} className="group block">
            <Poster url={item.content.poster_url} title={item.content.title} className="group-hover:opacity-80" />
            <p className="mt-1 truncate text-sm">{item.content.title}</p>
          </Link>
        </li>
      ))}
    </ul>
  );
}

const KIND_ORDER: ContentKind[] = ["movie", "series", "anime"];

/** Étagère : les affiches défilent horizontalement sur une planche. Triée
 * par catégorie, une étagère par catégorie (films, séries, animes). */
function ShelfView({ items, byCategory }: { items: LibraryItem[]; byCategory: boolean }) {
  const shelves = byCategory
    ? KIND_ORDER.map((kind) => ({
        label: `${KIND_LABELS[kind]}s`,
        items: items.filter((item) => item.content.kind === kind),
      })).filter((shelf) => shelf.items.length > 0)
    : [{ label: null, items }];

  return (
    <div className="space-y-6">
      {shelves.map((shelf) => (
        <section key={shelf.label ?? "tout"} aria-label={shelf.label ?? "Étagère"}>
          {shelf.label && <h2 className="mb-2 font-semibold">{shelf.label}</h2>}
          <ul className="flex gap-3 overflow-x-auto border-b-8 border-[#5b4636] px-2 pb-1 shadow-[0_6px_10px_-4px_rgba(0,0,0,0.6)]">
            {shelf.items.map((item) => (
              <li key={item.content.id} className="w-24 shrink-0 sm:w-28">
                <Link to={contentPath(item.content)} title={item.content.title} className="block">
                  <Poster url={item.content.poster_url} title={item.content.title} className="rounded-md shadow-lg" />
                  <span className="sr-only">{item.content.title}</span>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function ListView({ items }: { items: LibraryItem[] }) {
  return (
    <ul className="divide-y divide-border rounded-xl border border-border bg-surface">
      {items.map((item) => (
        <li key={item.content.id}>
          <Link to={contentPath(item.content)} className="flex items-center gap-3 p-3 hover:bg-bg/50">
            <div className="w-10 shrink-0">
              <Poster url={item.content.poster_url} title={item.content.title} className="rounded-md text-[6px]" />
            </div>
            <div className="min-w-0 flex-1">
              <p className="truncate font-medium">{item.content.title}</p>
              <p className="text-xs text-muted">
                {KIND_LABELS[item.content.kind]}
                {item.content.year && ` · ${item.content.year}`}
              </p>
            </div>
            <StatusBadge item={item} />
          </Link>
        </li>
      ))}
    </ul>
  );
}

/** Mode « Organiser » : boutons Monter / Descendre / Retirer, utilisables au
 * clavier et au doigt (plus fiable que le glisser-déposer sur mobile). */
function OrganizeList({
  items,
  onMove,
  onRemove,
}: {
  items: LibraryItem[];
  onMove: (index: number, offset: -1 | 1) => void;
  onRemove: (item: LibraryItem) => void;
}) {
  const button = "rounded-lg border border-border px-2.5 py-1.5 text-sm hover:bg-bg disabled:opacity-30";
  return (
    <ol className="divide-y divide-border rounded-xl border border-border bg-surface">
      {items.map((item, index) => (
        <li key={item.content.id} className="flex items-center gap-3 p-3">
          <span className="w-6 text-right text-sm text-muted">{index + 1}</span>
          <p className="min-w-0 flex-1 truncate">{item.content.title}</p>
          <button
            type="button"
            disabled={index === 0}
            onClick={() => onMove(index, -1)}
            aria-label={`Monter ${item.content.title}`}
            className={button}
          >
            ↑
          </button>
          <button
            type="button"
            disabled={index === items.length - 1}
            onClick={() => onMove(index, 1)}
            aria-label={`Descendre ${item.content.title}`}
            className={button}
          >
            ↓
          </button>
          <button
            type="button"
            onClick={() => onRemove(item)}
            aria-label={`Retirer ${item.content.title} de la bibliothèque`}
            className={`${button} text-error`}
          >
            ✕
          </button>
        </li>
      ))}
    </ol>
  );
}
