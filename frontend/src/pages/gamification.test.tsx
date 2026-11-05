import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { levelPercent } from "../lib/gamification";
import { JETON, UTILISATEUR, mockFetch } from "../test/mockFetch";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CONNECTE = {
  "POST /api/auth/refresh": { status: 200, body: JETON },
  "GET /api/users/me": { status: 200, body: UTILISATEUR },
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

const BADGE = { code: "premier_pas", name: "Premier pas", icon: "👣", tier: "bronze" };

describe("Gamification", () => {
  it("affiche les gains après avoir marqué un film comme vu", async () => {
    mockFetch({
      ...CONNECTE,
      "GET /api/catalog/tmdb/movie/603": {
        status: 200,
        body: {
          source: "tmdb",
          kind: "movie",
          external_id: "603",
          title: "Matrix",
          original_title: null,
          year: 1999,
          poster_url: null,
          overview: null,
          backdrop_url: null,
          genres: [],
          release_date: null,
          end_date: null,
          runtime_minutes: 136,
          status: null,
          seasons_count: null,
          episodes_count: null,
          seasons: [],
          source_url: "https://www.themoviedb.org/movie/603",
          watch: null,
        },
      },
      "GET /api/tracking/tmdb/movie/603": {
        status: 200,
        body: { content_id: null, tracking: null, progress: { watched: 0, total: null, percent: 0 } },
      },
      "PUT /api/tracking/tmdb/movie/603": {
        status: 200,
        body: {
          content_id: 7,
          tracking: {
            status: "completed",
            rating: null,
            review: null,
            started_at: null,
            completed_at: null,
            updated_at: "2026-11-06T10:00:00Z",
          },
          progress: { watched: 1, total: 1, percent: 100 },
          rewards: {
            xp: 70,
            lines: [
              { label: "Film vu", amount: 50 },
              { label: "Succès débloqué", amount: 20 },
            ],
            badges: [BADGE],
            level_up: null,
            streak_days: 3,
          },
        },
      },
    });
    afficher("/contenu/tmdb/movie/603");

    fireEvent.click(await screen.findByRole("button", { name: "Vu" }));

    expect(await screen.findByText("+70 XP")).toBeTruthy();
    expect(screen.getByText("Film vu")).toBeTruthy();
    expect(screen.getByText(/3 jours d'affilée/)).toBeTruthy();
    expect(screen.getByText("Premier pas")).toBeTruthy();
  });

  it("affiche le niveau, la série de jours et les succès", async () => {
    mockFetch({
      ...CONNECTE,
      "GET /api/gamification/me": {
        status: 200,
        body: {
          xp: 150,
          level: 2,
          level_start_xp: 100,
          next_level_xp: 283,
          streak_days: 4,
          streak_bonus_percent: 15,
          today_watch_xp: 30,
          daily_cap: 300,
          badges: [
            { ...BADGE, description: "Regarder un premier épisode.", threshold: 1, progress: 1, earned_at: "2026-11-06T10:00:00Z" },
            {
              code: "binge_100",
              name: "Binge-watcheur",
              icon: "🍿",
              tier: "silver",
              description: "Regarder 100 épisodes.",
              threshold: 100,
              progress: 12,
              earned_at: null,
            },
          ],
          recent: [{ label: "Épisodes vus", amount: 10, created_at: "2026-11-06T10:00:00Z" }],
        },
      },
    });
    afficher("/profil");

    expect(await screen.findByRole("heading", { name: "Niveau 2" })).toBeTruthy();
    expect(screen.getByText("Encore 133 XP pour le niveau 3")).toBeTruthy();
    expect(screen.getByText("+15 % d'XP par épisode")).toBeTruthy();
    expect(screen.getByText(/1 \/ 2/)).toBeTruthy();
    expect(screen.getByText("Argent · 12 / 100")).toBeTruthy();
  });

  it("calcule l'avancement dans le niveau", () => {
    expect(levelPercent({ xp: 150, level_start_xp: 100, next_level_xp: 283 })).toBe(27);
    expect(levelPercent({ xp: 0, level_start_xp: 0, next_level_xp: 100 })).toBe(0);
  });
});
