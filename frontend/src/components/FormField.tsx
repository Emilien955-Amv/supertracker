import type { InputHTMLAttributes } from "react";

type Props = Omit<InputHTMLAttributes<HTMLInputElement>, "id"> & {
  id: string;
  label: string;
  /** Message d'erreur affiché sous le champ (et lu par les lecteurs d'écran). */
  error?: string;
  /** Aide affichée sous le champ quand il n'y a pas d'erreur. */
  hint?: string;
};

/** Champ de formulaire accessible : étiquette, aide et erreur reliées au champ. */
export function FormField({ id, label, error, hint, ...inputProps }: Props) {
  const messageId = `${id}-message`;
  const message = error ?? hint;

  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={message ? messageId : undefined}
        className={`rounded-xl border bg-bg px-4 py-3 text-text placeholder:text-muted/60 focus:border-accent focus:outline-none ${
          error ? "border-error" : "border-border"
        }`}
        {...inputProps}
      />
      {message && (
        <p id={messageId} className={`text-sm ${error ? "text-error" : "text-muted"}`}>
          {message}
        </p>
      )}
    </div>
  );
}
