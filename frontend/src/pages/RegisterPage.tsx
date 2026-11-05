import { useState } from "react";
import type { FormEvent } from "react";
import { Link, useNavigate } from "react-router";

import { useAuth } from "../auth/AuthContext";
import { AuthLayout } from "../components/AuthLayout";
import { FormField } from "../components/FormField";
import { ApiError } from "../lib/api";

// Mêmes règles que le backend (backend/app/schemas/auth.py). Le serveur
// revérifie TOUJOURS : ces contrôles servent seulement au confort de l'utilisateur.
const USERNAME_PATTERN = /^[A-Za-z0-9_]{3,30}$/;
const PASSWORD_MIN_LENGTH = 10;

type Errors = Partial<Record<"email" | "username" | "password", string>>;

export function validateRegistration(email: string, username: string, password: string): Errors {
  const errors: Errors = {};
  if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) errors.email = "Adresse e-mail invalide.";
  if (!USERNAME_PATTERN.test(username)) {
    errors.username = "De 3 à 30 caractères : lettres sans accent, chiffres ou « _ ».";
  }
  if (password.length < PASSWORD_MIN_LENGTH) {
    errors.password = `Au moins ${PASSWORD_MIN_LENGTH} caractères.`;
  }
  return errors;
}

export default function RegisterPage() {
  const { register } = useAuth();
  const navigate = useNavigate();

  const [email, setEmail] = useState("");
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [errors, setErrors] = useState<Errors>({});
  const [serverError, setServerError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setServerError(null);
    const found = validateRegistration(email.trim(), username.trim(), password);
    setErrors(found);
    if (Object.keys(found).length > 0) return;

    setSubmitting(true);
    try {
      await register(email.trim(), username.trim(), password);
      navigate("/", { replace: true });
    } catch (err) {
      setServerError(err instanceof ApiError ? err.message : "Impossible de joindre le serveur.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <AuthLayout title="Créer un compte" subtitle="Tous vos suivis réunis au même endroit.">
      <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
        {serverError && (
          <p role="alert" className="rounded-xl border border-error/40 bg-error/10 p-3 text-error">
            {serverError}
          </p>
        )}
        <FormField
          id="email"
          label="E-mail"
          type="email"
          autoComplete="email"
          required
          value={email}
          error={errors.email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <FormField
          id="username"
          label="Pseudo"
          autoComplete="username"
          required
          value={username}
          error={errors.username}
          hint="Visible par les autres utilisateurs si votre profil est public."
          onChange={(e) => setUsername(e.target.value)}
        />
        <div className="flex flex-col gap-2">
          <FormField
            id="password"
            label="Mot de passe"
            type={showPassword ? "text" : "password"}
            autoComplete="new-password"
            required
            value={password}
            error={errors.password}
            hint={`Au moins ${PASSWORD_MIN_LENGTH} caractères. Une phrase facile à retenir est idéale.`}
            onChange={(e) => setPassword(e.target.value)}
          />
          <label className="flex items-center gap-2 text-sm text-muted">
            <input
              type="checkbox"
              checked={showPassword}
              onChange={(e) => setShowPassword(e.target.checked)}
              className="h-4 w-4 accent-accent"
            />
            Afficher le mot de passe
          </label>
        </div>
        <button
          type="submit"
          disabled={submitting}
          className="rounded-xl bg-accent px-4 py-3 font-semibold text-white hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {submitting ? "Création du compte…" : "Créer mon compte"}
        </button>
      </form>
      <p className="mt-6 text-center text-sm text-muted">
        Déjà inscrit ?{" "}
        <Link to="/connexion" className="font-semibold text-accent underline-offset-4 hover:underline">
          Se connecter
        </Link>
      </p>
    </AuthLayout>
  );
}
