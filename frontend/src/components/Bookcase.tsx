import { useEffect, useState } from "react";
import type { CSSProperties } from "react";
import { Link } from "react-router";
import {
  DndContext,
  DragOverlay,
  KeyboardSensor,
  PointerSensor,
  TouchSensor,
  closestCenter,
  useDroppable,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import type { DragEndEvent, DragOverEvent, DragStartEvent, UniqueIdentifier } from "@dnd-kit/core";
import {
  SortableContext,
  arrayMove,
  horizontalListSortingStrategy,
  sortableKeyboardCoordinates,
  useSortable,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";

import { apiFetch } from "../lib/api";
import { contentPath } from "../lib/catalog";
import type { ItemSize, LibraryDetail, LibraryItem, Shelf, Wood } from "../lib/tracking";
import { Poster } from "./Poster";

/** Apparence de chaque essence de bois (dégradés CSS, sans image à charger). */
export const WOODS: Record<Wood, { label: string; board: string; frame: string; grain: string }> = {
  oak: {
    label: "Chêne",
    board: "linear-gradient(180deg, #e0bb85, #b88a52 55%, #8f6538)",
    frame: "#a8794a",
    grain: "rgba(80, 50, 20, 0.18)",
  },
  walnut: {
    label: "Noyer",
    board: "linear-gradient(180deg, #91633f, #6b4428 55%, #4a2e1b)",
    frame: "#5a3a24",
    grain: "rgba(30, 15, 5, 0.25)",
  },
  ebony: {
    label: "Ébène",
    board: "linear-gradient(180deg, #463b34, #241d19 55%, #120e0c)",
    frame: "#1d1714",
    grain: "rgba(255, 255, 255, 0.05)",
  },
  white: {
    label: "Blanc laqué",
    board: "linear-gradient(180deg, #ffffff, #ece7df 55%, #d3ccc0)",
    frame: "#e6e0d6",
    grain: "rgba(0, 0, 0, 0.05)",
  },
};

/** Largeur des objets selon la taille choisie (en pixels). */
const SIZES: Record<ItemSize, number> = { small: 56, medium: 80, large: 112 };

const key = (shelfId: number) => `etagere-${shelfId}`;

type Columns = Record<string, number[]>;

/** Répartit les objets sur les étagères (ceux sans étagère vont sur la première). */
function buildColumns(library: LibraryDetail): Columns {
  const columns: Columns = Object.fromEntries(library.shelves.map((s) => [key(s.id), [] as number[]]));
  const first = library.shelves[0];
  const sorted = [...library.items].sort((a, b) => a.position - b.position);
  for (const item of sorted) {
    const shelf = item.shelf_id !== null && columns[key(item.shelf_id)] ? item.shelf_id : first?.id;
    if (shelf !== undefined) columns[key(shelf)].push(item.content.id);
  }
  return columns;
}

type Props = {
  library: LibraryDetail;
  /** Mode « Ranger » : glisser-déposer et gestion des étagères. */
  arranging: boolean;
  onChange: (library: LibraryDetail) => void;
  onError: (message: string | null) => void;
};

/** La bibliothèque comme un vrai meuble : étagères en bois, objets debout. */
export function Bookcase({ library, arranging, onChange, onError }: Props) {
  const path = `/api/libraries/${library.id}`;
  const [columns, setColumns] = useState<Columns>(() => buildColumns(library));
  const [activeId, setActiveId] = useState<UniqueIdentifier | null>(null);
  const items = new Map(library.items.map((item) => [item.content.id, item]));
  const wood = WOODS[library.wood];
  const width = SIZES[library.item_size];

  // La bibliothèque a changé (ajout, rechargement) : on reconstruit les rangées.
  useEffect(() => {
    if (activeId === null) setColumns(buildColumns(library));
    // eslint-disable-next-line react-hooks/exhaustive-deps -- pas pendant un glisser
  }, [library]);

  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 6 } }),
    // Au doigt : un appui un peu prolongé, pour ne pas gêner le défilement.
    useSensor(TouchSensor, { activationConstraint: { delay: 180, tolerance: 6 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  );

  function containerOf(id: UniqueIdentifier): string | undefined {
    if (typeof id === "string" && id in columns) return id;
    return Object.keys(columns).find((k) => columns[k].includes(id as number));
  }

  /** Enregistre le rangement (affichage immédiat, puis envoi au serveur). */
  async function save(next: Columns, shelves: Shelf[] = library.shelves) {
    const position = new Map<number, [number, number]>();
    for (const shelf of shelves) {
      next[key(shelf.id)].forEach((contentId, index) => position.set(contentId, [shelf.id, index]));
    }
    const previous = library;
    onChange({
      ...library,
      shelves: shelves.map((s, index) => ({ ...s, position: index })),
      items: library.items.map((item) => {
        const [shelfId, index] = position.get(item.content.id) ?? [item.shelf_id, item.position];
        return { ...item, shelf_id: shelfId, position: index };
      }),
    });
    onError(null);
    try {
      await apiFetch(`${path}/layout`, {
        method: "PUT",
        body: {
          shelves: shelves.map((s) => ({ id: s.id, content_ids: next[key(s.id)] })),
        },
      });
    } catch (err) {
      onChange(previous);
      onError(err instanceof Error ? err.message : "Échec de l'enregistrement du rangement.");
    }
  }

  function onDragStart({ active }: DragStartEvent) {
    setActiveId(active.id);
  }

  // Passage d'une étagère à une autre pendant le glisser.
  function onDragOver({ active, over }: DragOverEvent) {
    if (!over) return;
    const from = containerOf(active.id);
    const to = containerOf(over.id);
    if (!from || !to || from === to) return;
    setColumns((cols) => {
      const target = cols[to];
      const index = typeof over.id === "number" ? target.indexOf(over.id) : target.length;
      return {
        ...cols,
        [from]: cols[from].filter((id) => id !== active.id),
        [to]: [...target.slice(0, index < 0 ? target.length : index), active.id as number, ...target.slice(index < 0 ? target.length : index)],
      };
    });
  }

  function onDragEnd({ active, over }: DragEndEvent) {
    setActiveId(null);
    const container = containerOf(active.id);
    if (!over || !container) {
      setColumns(buildColumns(library));
      return;
    }
    const list = columns[container];
    const oldIndex = list.indexOf(active.id as number);
    const newIndex = typeof over.id === "number" ? list.indexOf(over.id) : list.length - 1;
    const next = {
      ...columns,
      [container]: newIndex >= 0 && oldIndex !== newIndex ? arrayMove(list, oldIndex, newIndex) : list,
    };
    setColumns(next);
    void save(next);
  }

  async function addShelf() {
    onError(null);
    try {
      await apiFetch(`${path}/shelves`, { method: "POST", body: {} });
      onChange(await apiFetch<LibraryDetail>(path));
    } catch (err) {
      onError(err instanceof Error ? err.message : "Échec.");
    }
  }

  async function renameShelf(shelf: Shelf, name: string) {
    if ((shelf.name ?? "") === name.trim()) return;
    onError(null);
    try {
      await apiFetch(`${path}/shelves/${shelf.id}`, { method: "PATCH", body: { name: name.trim() || null } });
      onChange({
        ...library,
        shelves: library.shelves.map((s) => (s.id === shelf.id ? { ...s, name: name.trim() || null } : s)),
      });
    } catch (err) {
      onError(err instanceof Error ? err.message : "Échec.");
    }
  }

  async function deleteShelf(shelf: Shelf) {
    const count = columns[key(shelf.id)].length;
    const message = count
      ? `Supprimer cette étagère ? Ses ${count} objet${count > 1 ? "s" : ""} iront sur l'étagère voisine.`
      : "Supprimer cette étagère vide ?";
    if (!window.confirm(message)) return;
    onError(null);
    try {
      await apiFetch(`${path}/shelves/${shelf.id}`, { method: "DELETE" });
      onChange(await apiFetch<LibraryDetail>(path));
    } catch (err) {
      onError(err instanceof Error ? err.message : "Échec.");
    }
  }

  function moveShelf(index: number, offset: -1 | 1) {
    const target = index + offset;
    if (target < 0 || target >= library.shelves.length) return;
    void save(columns, arrayMove(library.shelves, index, target));
  }

  const active = typeof activeId === "number" ? items.get(activeId) : undefined;

  return (
    // Le mur : la couleur choisie, avec un léger motif.
    <div
      className="rounded-2xl p-3 sm:p-5"
      style={{
        backgroundColor: library.wall,
        backgroundImage:
          "radial-gradient(circle at 20% 10%, rgba(255,255,255,0.08), transparent 45%), radial-gradient(circle at 80% 90%, rgba(0,0,0,0.25), transparent 50%)",
      }}
    >
      {/* Le meuble : cadre en bois, fond plus sombre. */}
      <div
        className="rounded-t-lg p-2 shadow-[0_18px_30px_-12px_rgba(0,0,0,0.7)] sm:p-3"
        style={{ backgroundColor: wood.frame }}
      >
        <DndContext
          sensors={sensors}
          collisionDetection={closestCenter}
          onDragStart={onDragStart}
          onDragOver={onDragOver}
          onDragEnd={onDragEnd}
          onDragCancel={() => {
            setActiveId(null);
            setColumns(buildColumns(library));
          }}
          accessibility={{
            screenReaderInstructions: {
              draggable:
                "Pour déplacer cet objet, appuyez sur Espace, utilisez les flèches, puis Espace pour le poser. Échap pour annuler.",
            },
          }}
        >
          <div className="space-y-2 sm:space-y-3">
            {library.shelves.map((shelf, index) => (
              <ShelfRow
                key={shelf.id}
                shelf={shelf}
                ids={columns[key(shelf.id)] ?? []}
                items={items}
                width={width}
                wood={wood}
                arranging={arranging}
                isFirst={index === 0}
                isLast={index === library.shelves.length - 1}
                onRename={(name) => void renameShelf(shelf, name)}
                onDelete={() => void deleteShelf(shelf)}
                onMove={(offset) => moveShelf(index, offset)}
              />
            ))}
          </div>
          <DragOverlay>
            {active ? (
              <div style={{ width }} className="rotate-3 scale-105 drop-shadow-2xl">
                <Poster url={active.content.poster_url} title={active.content.title} className="rounded-sm" />
              </div>
            ) : null}
          </DragOverlay>
        </DndContext>
      </div>
      {/* Socle du meuble. */}
      <div className="mx-1 h-3 rounded-b-md" style={{ background: wood.board }} aria-hidden="true" />

      {arranging && (
        <button
          type="button"
          onClick={() => void addShelf()}
          className="mt-4 w-full rounded-xl border-2 border-dashed border-white/40 py-3 text-sm font-semibold text-white/90 hover:bg-white/10"
        >
          + Ajouter une étagère
        </button>
      )}
    </div>
  );
}

function ShelfRow({
  shelf,
  ids,
  items,
  width,
  wood,
  arranging,
  isFirst,
  isLast,
  onRename,
  onDelete,
  onMove,
}: {
  shelf: Shelf;
  ids: number[];
  items: Map<number, LibraryItem>;
  width: number;
  wood: (typeof WOODS)[Wood];
  arranging: boolean;
  isFirst: boolean;
  isLast: boolean;
  onRename: (name: string) => void;
  onDelete: () => void;
  onMove: (offset: -1 | 1) => void;
}) {
  const { setNodeRef, isOver } = useDroppable({ id: key(shelf.id) });
  const [name, setName] = useState(shelf.name ?? "");
  useEffect(() => setName(shelf.name ?? ""), [shelf.name]);
  const label = shelf.name || `Étagère ${shelf.position + 1}`;
  const small = "rounded-md bg-black/40 px-2 py-1 text-xs text-white hover:bg-black/60 disabled:opacity-30";

  return (
    <section aria-label={label}>
      {(arranging || shelf.name) && (
        <div className="mb-1 flex items-center gap-2">
          {arranging ? (
            <>
              <label className="min-w-0 flex-1">
                <span className="sr-only">Nom de l'étagère {shelf.position + 1}</span>
                <input
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  onBlur={() => onRename(name)}
                  maxLength={50}
                  placeholder={`Étagère ${shelf.position + 1} (sans nom)`}
                  className="w-full rounded-md bg-black/40 px-2 py-1 text-xs text-white placeholder:text-white/50"
                />
              </label>
              <button type="button" onClick={() => onMove(-1)} disabled={isFirst} aria-label={`Monter ${label}`} className={small}>
                ↑
              </button>
              <button type="button" onClick={() => onMove(1)} disabled={isLast} aria-label={`Descendre ${label}`} className={small}>
                ↓
              </button>
              <button type="button" onClick={onDelete} aria-label={`Supprimer ${label}`} className={small}>
                🗑
              </button>
            </>
          ) : (
            // Petite plaque gravée.
            <span className="mx-auto rounded-sm bg-gradient-to-b from-[#e8d9a8] to-[#b39b5a] px-3 py-0.5 text-[11px] font-semibold text-[#3a2c10] shadow">
              {shelf.name}
            </span>
          )}
        </div>
      )}

      {/* Fond de l'étagère (assombri) et objets posés dessus. */}
      <div
        ref={setNodeRef}
        className={`overflow-x-auto rounded-sm bg-black/35 px-2 pt-3 transition-colors ${isOver ? "bg-white/15" : ""}`}
        style={{ minHeight: width * 1.5 + 14 }}
      >
        <SortableContext items={ids} strategy={horizontalListSortingStrategy}>
          <ul className="flex min-w-max items-end gap-1.5">
            {ids.map((id) => {
              const item = items.get(id);
              return item ? <ShelfItem key={id} item={item} width={width} arranging={arranging} /> : null;
            })}
            {ids.length === 0 && (
              <li className="self-center px-2 pb-3 text-xs text-white/50">
                {arranging ? "Glissez une œuvre ici" : "Étagère vide"}
              </li>
            )}
          </ul>
        </SortableContext>
      </div>
      {/* La planche, avec le veinage du bois. */}
      <div
        aria-hidden="true"
        className="h-3 rounded-sm shadow-[0_6px_8px_-3px_rgba(0,0,0,0.6)]"
        style={{
          background: `repeating-linear-gradient(90deg, transparent 0 22px, ${wood.grain} 22px 23px), ${wood.board}`,
        }}
      />
    </section>
  );
}

function ShelfItem({ item, width, arranging }: { item: LibraryItem; width: number; arranging: boolean }) {
  const { attributes, listeners, setNodeRef, transform, transition, isDragging } = useSortable({
    id: item.content.id,
    disabled: !arranging,
  });
  const style: CSSProperties = {
    width,
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.3 : 1,
  };
  const cover = (
    <Poster url={item.content.poster_url} title={item.content.title} className="rounded-sm text-[8px]" />
  );

  return (
    <li ref={setNodeRef} style={style} className="shrink-0">
      {arranging ? (
        <button
          type="button"
          {...attributes}
          {...listeners}
          aria-label={`Déplacer ${item.content.title}`}
          className="block w-full cursor-grab touch-none shadow-[2px_4px_6px_rgba(0,0,0,0.5)] active:cursor-grabbing"
        >
          {cover}
        </button>
      ) : (
        <Link
          to={contentPath(item.content)}
          title={item.content.title}
          className="block shadow-[2px_4px_6px_rgba(0,0,0,0.5)] transition-transform hover:-translate-y-1 motion-reduce:transition-none"
        >
          {cover}
          <span className="sr-only">{item.content.title}</span>
        </Link>
      )}
    </li>
  );
}
