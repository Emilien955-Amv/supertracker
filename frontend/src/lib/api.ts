/**
 * Client HTTP de l'application : toutes les requêtes vers l'API passent par ici.
 *
 * - Le jeton d'accès est gardé EN MÉMOIRE (une simple variable), jamais dans
 *   localStorage : un script malveillant injecté dans la page (XSS) ne
 *   pourrait pas le lire et l'emporter.
 * - Le jeton de renouvellement vit dans un cookie « httpOnly » que le
 *   navigateur envoie tout seul à /api/auth/refresh : JavaScript n'y a pas accès.
 * - Si l'API répond 401 (jeton expiré), on renouvelle le jeton une fois et on
 *   rejoue la requête, de façon transparente pour l'utilisateur.
 */

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

type TokenResponse = { access_token: string; token_type: "bearer"; expires_in: number };

let accessToken: string | null = null;
// Renouvellement en cours, partagé : si plusieurs requêtes échouent en même
// temps, une seule demande de renouvellement part. Sans cela, le serveur
// verrait le même jeton utilisé deux fois et révoquerait la session.
let refreshInFlight: Promise<string | null> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

async function toApiError(response: Response): Promise<ApiError> {
  let message = "Une erreur inattendue est survenue. Réessayez dans un instant.";
  if (response.status === 422) message = "Certaines informations sont invalides.";
  if (response.status === 429) message = "Trop de tentatives. Réessayez dans quelques minutes.";
  try {
    const data: unknown = await response.json();
    if (data && typeof data === "object" && "detail" in data && typeof data.detail === "string") {
      message = data.detail;
    }
  } catch {
    // Réponse sans JSON : on garde le message générique.
  }
  return new ApiError(response.status, message);
}

export function refreshAccessToken(): Promise<string | null> {
  refreshInFlight ??= fetch("/api/auth/refresh", { method: "POST", credentials: "same-origin" })
    .then(async (response) => {
      if (!response.ok) return null;
      return ((await response.json()) as TokenResponse).access_token;
    })
    .catch(() => null)
    .then((token) => {
      accessToken = token;
      return token;
    })
    .finally(() => {
      refreshInFlight = null;
    });
  return refreshInFlight;
}

type RequestOptions = {
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  body?: unknown;
  /** Permet d'annuler la requête (ex. l'utilisateur a quitté la page). */
  signal?: AbortSignal;
};

export async function apiFetch<T>(
  path: string,
  { method = "GET", body, signal }: RequestOptions = {},
  retryOnUnauthorized = true,
): Promise<T> {
  const headers: Record<string, string> = {};
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (accessToken) headers.Authorization = `Bearer ${accessToken}`;

  const response = await fetch(path, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
    credentials: "same-origin",
    signal,
  });

  if (response.status === 401 && retryOnUnauthorized && accessToken) {
    if (await refreshAccessToken()) return apiFetch<T>(path, { method, body, signal }, false);
  }
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}

export async function login(email: string, password: string): Promise<void> {
  const data = await apiFetch<TokenResponse>("/api/auth/login", {
    method: "POST",
    body: { email, password },
  });
  accessToken = data.access_token;
}
