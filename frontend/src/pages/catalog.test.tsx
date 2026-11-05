import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { contentPath, formatDate, formatRuntime } from "../lib/catalog";
import { JETON, UTILISATEUR, mockFetch } from "../test/mockFetch";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CONNECTE = {
  "POST /api/auth/refresh": { status: 200, body: JETON },
  "GET /api/users/me": { status: 200, body: UTILISATEUR },
};

const MATRIX = {
  source: "tmdb",
  kind: "movie",
  external_id: "603",
  title: "Matrix",
  original_title: "The Matrix",
  year: 1999,
  poster_url: null,
  overview: "Un pirate informatique découvre la vérité.",
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

describe("Recherche", () => {
  it("lance la recherche après la saisie et affiche les résultats", async () => {
    const fetchMock = mockFetch({
      ...CONNECTE,
      "GET /api/catalog/search?q=matrix": {
        status: 200,
        body: { query: "matrix", results: [MATRIX], unavailable_sources: [] },
      },
    });
    afficher("/recherche");

    fireEvent.change(await screen.findByLabelText(/Rechercher un film/), {
      target: { value: "matrix" },
    });

    const lien = await screen.findByRole("link", { name: /Matrix/ });
    expect(lien.getAttribute("href")).toBe("/contenu/tmdb/movie/603");
    // Une seule requête de recherche malgré la saisie (« debounce »).
    const recherches = fetchMock.mock.calls.filter(([url]) => url.startsWith("/api/catalog/search"));
    expect(recherches).toHaveLength(1);
  });

  it("signale les résultats partiels quand une source ne répond pas", async () => {
    mockFetch({
      ...CONNECTE,
      "GET /api/catalog/search?q=naruto": {
        status: 200,
        body: { query: "naruto", results: [MATRIX], unavailable_sources: ["anilist"] },
      },
    });
    afficher("/recherche?q=naruto");

    expect(await screen.findByText(/AniList ne répond pas/)).toBeTruthy();
  });

  it("indique l'absence de résultat", async () => {
    mockFetch({
      ...CONNECTE,
      "GET /api/catalog/search?q=zzzz": {
        status: 200,
        body: { query: "zzzz", results: [], unavailable_sources: [] },
      },
    });
    afficher("/recherche?q=zzzz");

    expect(await screen.findByText(/Aucun résultat pour « zzzz »/)).toBeTruthy();
  });
});

describe("Fiche contenu", () => {
  it("affiche les informations et les saisons d'une série", async () => {
    mockFetch({
      ...CONNECTE,
      "GET /api/catalog/tmdb/series/1399": {
        status: 200,
        body: {
          ...MATRIX,
          kind: "series",
          external_id: "1399",
          title: "Game of Thrones",
          backdrop_url: null,
          genres: ["Drame"],
          release_date: "2011-04-17",
          end_date: null,
          runtime_minutes: 60,
          status: "Terminée",
          seasons_count: 8,
          episodes_count: 73,
          seasons: [{ number: 1, name: "Saison 1", episode_count: 10, air_date: "2011-04-17", poster_url: null }],
          source_url: "https://www.themoviedb.org/tv/1399",
          watch: {
            region: "FR",
            link: "https://www.themoviedb.org/tv/1399/watch?locale=FR",
            subscription: [{ name: "HBO Max", logo_url: "https://image.tmdb.org/t/p/w92/max.png" }],
            free: [],
            rent: [],
            buy: [{ name: "Apple TV", logo_url: null }],
          },
        },
      },
    });
    afficher("/contenu/tmdb/series/1399");

    expect(await screen.findByRole("heading", { level: 1, name: "Game of Thrones" })).toBeTruthy();
    expect(screen.getByText("17 avril 2011")).toBeTruthy();
    expect(screen.getByText("Terminée")).toBeTruthy();
    expect(screen.getByText("10 épisodes · 2011")).toBeTruthy();
    // Où regarder : logos par catégorie, catégories vides masquées, mention JustWatch.
    expect(screen.getByRole("img", { name: "HBO Max" })).toBeTruthy();
    expect(screen.getByText("Apple TV")).toBeTruthy();
    expect(screen.queryByText("Location")).toBeNull();
    expect(screen.getByRole("link", { name: "JustWatch" })).toBeTruthy();
  });

  it("affiche un message clair si le contenu n'existe pas", async () => {
    mockFetch({
      ...CONNECTE,
      "GET /api/catalog/tmdb/movie/999": { status: 404, body: { detail: "Contenu introuvable." } },
    });
    afficher("/contenu/tmdb/movie/999");

    expect((await screen.findByRole("alert")).textContent).toContain("introuvable");
  });
});

describe("Mise en forme", () => {
  it("formate les durées", () => {
    expect(formatRuntime(136)).toBe("2 h 16 min");
    expect(formatRuntime(120)).toBe("2 h");
    expect(formatRuntime(45)).toBe("45 min");
    expect(formatRuntime(null)).toBeNull();
  });

  it("formate les dates en français", () => {
    expect(formatDate("2026-11-05")).toBe("5 novembre 2026");
    expect(formatDate(null)).toBeNull();
  });

  it("construit l'adresse d'une fiche", () => {
    expect(contentPath({ source: "anilist", kind: "anime", external_id: "21" })).toBe(
      "/contenu/anilist/anime/21",
    );
  });
});
