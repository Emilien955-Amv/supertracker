import { LIBRARY_COLORS } from "../lib/tracking";

/** Choix d'une couleur parmi la palette : de vrais boutons radio (clavier,
 * lecteurs d'écran), simplement habillés en pastilles. */
export function ColorPicker({
  value,
  onChange,
  name,
}: {
  value: string;
  onChange: (color: string) => void;
  name: string;
}) {
  return (
    <fieldset>
      <legend className="text-sm text-muted">Couleur</legend>
      <div className="mt-1 flex flex-wrap gap-2">
        {LIBRARY_COLORS.map((color, index) => (
          <label key={color} className="cursor-pointer">
            <input
              type="radio"
              name={name}
              value={color}
              checked={value === color}
              onChange={() => onChange(color)}
              className="peer sr-only"
            />
            <span className="sr-only">Couleur {index + 1}</span>
            <span
              aria-hidden="true"
              className="block h-8 w-8 rounded-full border-2 border-transparent peer-checked:border-text peer-focus-visible:outline-2 peer-focus-visible:outline-accent"
              style={{ backgroundColor: color }}
            />
          </label>
        ))}
      </div>
    </fieldset>
  );
}
