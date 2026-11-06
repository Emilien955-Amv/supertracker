import { act, cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../App";
import { AuthProvider } from "../auth/AuthContext";
import { JETON, UTILISATEUR, mockFetch } from "../test/mockFetch";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CONNECTE = {
  "POST /api/auth/refresh": { status: 200, body: JETON },
  "GET /api/users/me": { status: 200, body: UTILISATEUR },
};

const CONTENU = { id: 7, source: "tmdb", kind: "movie", external_id: "603", title: "Matrix" };

function carte(id: number, rarity: string, title: string, extra: Record<string, unknown> = {}) {
  return {
    id,
    rarity,
    kind: "character",
    title,
    subtitle: "Second rôle",
    image_url: `https://img/${id}.jpg`,
    content: CONTENU,
    owned: false,
    craft_cost: 25,
    ...extra,
  };
}

const COLLECTION = {
  boosters: 1,
  fragments: 30,
  boosters_until_pity: 20,
  next_free_booster_in: 125,
  free_booster_minutes: 5,
  free_booster_max_stock: 12,
  themes: [
    { theme: "anime", label: "Animes & mangas", cards: 0 },
    { theme: "movie", label: "Films", cards: 689 },
    { theme: "series", label: "Séries", cards: 85 },
    { theme: "mixed", label: "Mélange", cards: 774 },
    { theme: "netflix", label: "Netflix", cards: 320 },
    { theme: "disney", label: "Disney+", cards: 0 },
  ],
  stats: [
    { rarity: "common", owned: 1, total: 1, chance_percent: 50 },
    { rarity: "divine", owned: 0, total: 1, chance_percent: 0.5 },
  ],
  cards: [
    carte(1, "common", "Affiche", { owned: true }),
    carte(2, "rare", "Oracle"),
    carte(3, "epic", "Morpheus", { craft_cost: 75 }),
    carte(4, "divine", "Neo", { craft_cost: null }),
  ],
};

function afficher() {
  render(
    <AuthProvider>
      <MemoryRouter initialEntries={["/cartes"]}>
        <AppRoutes />
      </MemoryRouter>
    </AuthProvider>,
  );
}

describe("Cartes", () => {
  it("affiche la collection, les cartes à découvrir et la fabrication", async () => {
    mockFetch({ ...CONNECTE, "GET /api/cards/me": { status: 200, body: COLLECTION } });
    afficher();

    expect(await screen.findByText("🎁 1 booster à ouvrir")).toBeTruthy();
    expect(screen.getByText("2:05")).toBeTruthy(); // prochain booster gratuit
    // Pack sans cartes (catalogue en préparation) : désactivé.
    const anime = screen.getByRole("button", { name: "Ouvrir un pack Animes & mangas" }) as HTMLButtonElement;
    expect(anime.disabled).toBe(true);
    // Packs par plateforme.
    expect((screen.getByRole("button", { name: "Ouvrir un pack Netflix" }) as HTMLButtonElement).disabled).toBe(false);
    expect((screen.getByRole("button", { name: "Ouvrir un pack Disney+" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("link", { name: "Voir les cartes du pack Netflix" }).getAttribute("href")).toBe(
      "/cartes/pack/netflix",
    );
    // Divine : impossible à fabriquer, aucun bouton.
    expect(screen.queryByRole("button", { name: /Fabriquer une carte Divine/ })).toBeNull();
    // 30 fragments : la Rare (25) est fabricable, pas l'Épique (75).
    const rare = screen.getByRole("button", { name: /Fabriquer une carte Rare/ }) as HTMLButtonElement;
    const epique = screen.getByRole("button", { name: /Fabriquer une carte Épique/ }) as HTMLButtonElement;
    expect(rare.disabled).toBe(false);
    expect(epique.disabled).toBe(true);
  });

  it("révèle la dernière carte Légendaire avec suspense", async () => {
    mockFetch({
      ...CONNECTE,
      "GET /api/cards/me": { status: 200, body: COLLECTION },
      "POST /api/cards/boosters/open": {
        status: 200,
        body: {
          theme: "movie",
          cards: [
            ...[1, 1, 1, 1].map((id) => ({ card: carte(id, "common", "Figurant"), is_new: false, fragments: 1 })),
            { card: carte(5, "legendary", "Neo"), is_new: true, fragments: 0 },
          ],
          fragments: 34,
          boosters_left: 0,
        },
      },
    });
    afficher();

    fireEvent.click(await screen.findByRole("button", { name: "Ouvrir un pack Films" }));

    const fenetre = await screen.findByRole("dialog", { name: /Votre booster/ });
    fireEvent.click(within(fenetre).getByRole("button", { name: "Retourner la carte 1" }));
    expect(within(fenetre).getByRole("button", { name: "Figurant, Commune" })).toBeTruthy();

    vi.useFakeTimers();
    try {
      fireEvent.click(within(fenetre).getByRole("button", { name: "Tout retourner" }));
      // Les 4 premières sont retournées ; la dernière se fait attendre…
      expect(within(fenetre).getAllByText("Doublon · +1 💎")).toHaveLength(4);
      expect(within(fenetre).getByText(/Quelque chose de rare arrive/)).toBeTruthy();
      expect(within(fenetre).getByRole("button", { name: "Retourner la carte 5" })).toBeTruthy();

      act(() => vi.advanceTimersByTime(2000));
      // … puis elle se retourne, avec la bannière.
      expect(within(fenetre).getByRole("button", { name: "Neo, Légendaire, nouvelle" })).toBeTruthy();
      expect(screen.getByRole("status").textContent).toContain("Légendaire !");
      expect(within(fenetre).getByText("Fragments : 34 💎")).toBeTruthy();
    } finally {
      vi.useRealTimers();
    }
  });
});
