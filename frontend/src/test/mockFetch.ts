import { vi } from "vitest";

type FakeResponse = { status: number; body?: unknown };

/**
 * Remplace fetch par une fausse API : chaque clé « MÉTHODE /chemin » renvoie
 * la réponse indiquée. Une route non prévue renvoie 404 (et fait échouer le
 * test de façon visible plutôt que silencieuse).
 */
export function mockFetch(routes: Record<string, FakeResponse>) {
  const fetchMock = vi.fn(async (url: string, init?: RequestInit) => {
    const key = `${init?.method ?? "GET"} ${url}`;
    const { status, body } = routes[key] ?? { status: 404, body: { detail: `Route non simulée : ${key}` } };
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => body,
    } as Response;
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const UTILISATEUR = {
  id: 1,
  email: "emilien@exemple.fr",
  username: "emilien",
  avatar_url: null,
  is_public: false,
  created_at: "2026-11-05T20:00:00Z",
};

export const JETON = { access_token: "jeton-de-test", token_type: "bearer", expires_in: 900 };
