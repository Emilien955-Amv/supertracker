import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { JETON, UTILISATEUR, mockFetch } from "../test/mockFetch";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

const CONNECTE = {
  "POST /api/auth/refresh": { status: 200, body: JETON },
  "GET /api/users/me": { status: 200, body: UTILISATEUR },
};

const FICHE_SERIE = {
  source: "tmdb",
  kind: "series",
  external_id: "1399",
  title: "Game of Thrones",
  original_title: null,
  year: 2011,
  poster_url: null,
  overview: null,
  backdrop_url: null,
  genres: [],
  release_date: null,
  end_date: null,
  runtime_minutes: null,
  status: null,
  seasons_count: 1,
  episodes_count: 2,
  seasons: [{ number: 1, name: "Saison 1", episode_count: 2, air_date: null, poster_url: null }],
  source_url: "https://www.themoviedb.org/tv/1399",
  watch: null,
};

const SUIVI = "/api/tracking/tmdb/series/1399";
const PAS_SUIVI = { content_id: null, tracking: null, progress: { watched: 0, total: null, percent: 0 } };
const TRACKING = {
  status: "watching",
  rating: null,
  review: null,
  started_at: "2026-11-05T20:00:00Z",
  completed_at: null,
  updated_at: "2026-11-05T20:00:00Z",
};

function afficher(adresse: string) {
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={[adresse]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

/** Corps JSON envoyé lors de l'appel « MÉTHODE chemin ». */
function corpsEnvoye(fetchMock: ReturnType<typeof mockFetch>, methode: string, chemin: string): unknown {
  const appel = fetchMock.mock.calls.find(
    ([url, init]) => url === chemin && (init?.method ?? "GET") === methode,
  );
  return appel?.[1]?.body ? JSON.parse(appel[1].body as string) : undefined;
}

describe("Suivi depuis la fiche", () => {
  it("ajoute le contenu au suivi en choisissant un statut", async () => {
    const fetchMock = mockFetch({
      ...CONNECTE,
      "GET /api/catalog/tmdb/series/1399": { status: 200, body: FICHE_SERIE },
      [`GET ${SUIVI}`]: { status: 200, body: PAS_SUIVI },
      [`PUT ${SUIVI}`]: {
        status: 200,
        body: { content_id: 7, tracking: { ...TRACKING, status: "planned" }, progress: { watched: 0, total: 2, percent: 0 } },
      },
    });
    afficher("/contenu/tmdb/series/1399");

    fireEvent.click(await screen.findByRole("button", { name: "À voir" }));

    expect(await screen.findByText("Ajouté à votre suivi.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "À voir" }).getAttribute("aria-pressed")).toBe("true");
    expect(corpsEnvoye(fetchMock, "PUT", SUIVI)).toEqual({ status: "planned", rating: null, review: null });
    // Une fois suivi : note et avis deviennent disponibles.
    expect(screen.getByLabelText("Ma note")).toBeTruthy();
  });

  it("coche un épisode et met à jour la progression", async () => {
    const fetchMock = mockFetch({
      ...CONNECTE,
      "GET /api/catalog/tmdb/series/1399": { status: 200, body: FICHE_SERIE },
      [`GET ${SUIVI}`]: { status: 200, body: PAS_SUIVI },
      [`GET ${SUIVI}/seasons/1`]: {
        status: 200,
        body: [1, 2].map((n) => ({
          id: 100 + n,
          season_number: 1,
          number: n,
          title: `Épisode ${n}`,
          air_date: "2011-04-17",
          runtime_minutes: 60,
          still_url: null,
          watched: false,
        })),
      },
      [`POST ${SUIVI}/episodes`]: {
        status: 200,
        body: { content_id: 7, tracking: TRACKING, progress: { watched: 1, total: 2, percent: 50 } },
      },
    });
    afficher("/contenu/tmdb/series/1399");

    // Ouverture de la saison (élément <details>).
    const saison = (await screen.findByText("Saison 1", { selector: "p" })).closest("details")!;
    saison.open = true;
    fireEvent(saison, new Event("toggle"));

    fireEvent.click(await within(saison).findByLabelText(/Épisode 1/));

    expect(await screen.findByText(/1 \/ 2 épisodes vus · 50 %/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "En cours" }).getAttribute("aria-pressed")).toBe("true");
    expect(corpsEnvoye(fetchMock, "POST", `${SUIVI}/episodes`)).toEqual({ episode_ids: [101], watched: true });
  });
});

describe("Vu jusqu'ici et annulation", () => {
  it("coche jusqu'à un épisode puis annule", async () => {
    const episodes = [1, 2].map((n) => ({
      id: 100 + n,
      season_number: 1,
      number: n,
      title: `Épisode ${n}`,
      air_date: "2011-04-17",
      runtime_minutes: 60,
      still_url: null,
      watched: false,
    }));
    const fetchMock = mockFetch({
      ...CONNECTE,
      "GET /api/catalog/tmdb/series/1399": { status: 200, body: FICHE_SERIE },
      [`GET ${SUIVI}`]: { status: 200, body: PAS_SUIVI },
      [`GET ${SUIVI}/seasons/1`]: { status: 200, body: episodes },
      [`POST ${SUIVI}/watched-until`]: {
        status: 200,
        body: {
          content_id: 7,
          tracking: TRACKING,
          progress: { watched: 2, total: 2, percent: 100 },
          changed_episode_ids: [101, 102],
        },
      },
      [`POST ${SUIVI}/episodes`]: {
        status: 200,
        body: { content_id: 7, tracking: TRACKING, progress: { watched: 0, total: 2, percent: 0 } },
      },
    });
    afficher("/contenu/tmdb/series/1399");

    const saison = (await screen.findByText("Saison 1", { selector: "p" })).closest("details")!;
    saison.open = true;
    fireEvent(saison, new Event("toggle"));
    // Pas de « Vu jusqu'ici » sur le tout premier épisode : rien avant lui.
    const boutons = await within(saison).findAllByRole("button", { name: /jusqu'à la saison 1/ });
    expect(boutons).toHaveLength(1);
    fireEvent.click(boutons[0]);

    expect(corpsEnvoye(fetchMock, "POST", `${SUIVI}/watched-until`)).toEqual({
      season_number: 1,
      episode_number: 2,
      watched: true,
    });
    expect(await screen.findByText(/2 épisodes marqués comme vus/)).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Annuler" }));
    await waitFor(() =>
      expect(corpsEnvoye(fetchMock, "POST", `${SUIVI}/episodes`)).toEqual({
        episode_ids: [101, 102],
        watched: false,
      }),
    );
  });
});

describe("Mon suivi", () => {
  it("liste les contenus suivis avec leur progression", async () => {
    mockFetch({
      ...CONNECTE,
      "GET /api/tracking?status=watching": {
        status: 200,
        body: [
          {
            content: {
              id: 7,
              source: "tmdb",
              kind: "series",
              external_id: "1399",
              title: "Game of Thrones",
              year: 2011,
              poster_url: null,
              episodes_count: 73,
            },
            tracking: { ...TRACKING, rating: 9 },
            progress: { watched: 10, total: 73, percent: 14 },
          },
        ],
      },
    });
    afficher("/suivi?statut=watching");

    const lien = await screen.findByRole("link", { name: /Game of Thrones/ });
    expect(lien.getAttribute("href")).toBe("/contenu/tmdb/series/1399");
    expect(within(lien).getByText("10/73")).toBeTruthy();
    expect(within(lien).getByText(/★ 9\/10/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "En cours" }).getAttribute("aria-current")).toBe("page");
  });
});

describe("Bibliothèques", () => {
  const BIBLIO = {
    id: 3,
    name: "Coups de cœur",
    color: "#7c5cff",
    view_mode: "list",
    sort_mode: "manual",
    created_at: "2026-11-05T20:00:00Z",
    items_count: 2,
    preview: [null, null],
    contains: null,
  };
  const element = (id: number, title: string) => ({
    content: { id, source: "tmdb", kind: "movie", external_id: String(id), title, year: 1999, poster_url: null, episodes_count: null },
    position: 0,
    added_at: "2026-11-05T20:00:00Z",
    tracking_status: id === 1 ? "completed" : null,
  });

  it("crée une bibliothèque", async () => {
    const fetchMock = mockFetch({
      ...CONNECTE,
      "GET /api/libraries": { status: 200, body: [] },
      "POST /api/libraries": { status: 201, body: { ...BIBLIO, items_count: 0, preview: [] } },
    });
    afficher("/bibliotheques");

    fireEvent.change(await screen.findByLabelText("Nouvelle bibliothèque"), {
      target: { value: "Coups de cœur" },
    });
    fireEvent.click(screen.getByRole("button", { name: "Créer" }));

    expect(await screen.findByRole("link", { name: /Coups de cœur/ })).toBeTruthy();
    expect(corpsEnvoye(fetchMock, "POST", "/api/libraries")).toEqual({ name: "Coups de cœur", color: "#7c5cff" });
  });

  it("affiche le contenu et enregistre un nouvel ordre", async () => {
    const fetchMock = mockFetch({
      ...CONNECTE,
      "GET /api/libraries/3": {
        status: 200,
        body: { ...BIBLIO, items: [element(1, "Matrix"), element(2, "Alien")] },
      },
      "PUT /api/libraries/3/order": { status: 204 },
    });
    afficher("/bibliotheques/3");

    // Affichage « liste » avec le statut de suivi.
    expect(await screen.findByRole("heading", { name: "Coups de cœur" })).toBeTruthy();
    expect(screen.getByText("Vu")).toBeTruthy();

    fireEvent.click(screen.getByRole("button", { name: "Organiser" }));
    fireEvent.click(screen.getByRole("button", { name: "Descendre Matrix" }));

    await waitFor(() =>
      expect(corpsEnvoye(fetchMock, "PUT", "/api/libraries/3/order")).toEqual({ content_ids: [2, 1] }),
    );
    const lignes = screen.getAllByRole("listitem").map((li) => li.textContent);
    expect(lignes.findIndex((t) => t?.includes("Alien"))).toBeLessThan(
      lignes.findIndex((t) => t?.includes("Matrix")),
    );
  });

  it("signale une bibliothèque introuvable", async () => {
    mockFetch({ ...CONNECTE, "GET /api/libraries/99": { status: 404, body: { detail: "Bibliothèque introuvable." } } });
    afficher("/bibliotheques/99");

    expect((await screen.findByRole("alert")).textContent).toContain("introuvable");
  });
});
