import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../App";
import { AuthProvider } from "../auth/AuthContext";
import type { CardRead } from "../lib/cards";
import type { Trade } from "../lib/trades";
import { JETON, UTILISATEUR, mockFetch } from "../test/mockFetch";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const CONNECTE = {
  "POST /api/auth/refresh": { status: 200, body: JETON },
  "GET /api/users/me": { status: 200, body: { ...UTILISATEUR, bio: null } },
};

function carte(id: number, title: string): CardRead {
  return {
    id,
    rarity: "rare",
    kind: "character",
    title,
    subtitle: null,
    image_url: "https://exemple.fr/perso.jpg",
    content: { id: 7, source: "anilist", kind: "anime", external_id: "21", title: "One Piece" },
  };
}

const RECU: Trade = {
  id: 3,
  status: "pending",
  direction: "incoming",
  partner: "luffy",
  message: "Je te file Nami",
  gives: [carte(1, "Nami")],
  takes: [carte(2, "Zoro")],
  created_at: "2026-11-06T10:00:00Z",
  resolved_at: null,
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

describe("Échanges", () => {
  it("affiche un échange reçu et l'accepte", async () => {
    const fetchMock = mockFetch({
      ...CONNECTE,
      "GET /api/trades": { status: 200, body: [RECU] },
      "GET /api/friends": {
        status: 200,
        body: { friends: [{ username: "luffy", avatar_url: null, relation: "friends" }], incoming: [], outgoing: [] },
      },
      "POST /api/trades/3/accept": { status: 200, body: { masteries: [] } },
    });
    afficher("/echanges");

    expect(await screen.findByText("« Je te file Nami »")).toBeTruthy();
    expect(screen.getByRole("link", { name: "avec luffy" })).toBeTruthy();
    fireEvent.click(screen.getByRole("button", { name: "Accepter" }));
    await waitFor(() =>
      expect(
        fetchMock.mock.calls.some(([url, init]) => url === "/api/trades/3/accept" && init?.method === "POST"),
      ).toBe(true),
    );
    expect(await screen.findByText(/Échange réussi/)).toBeTruthy();
  });

  it("compose un échange : une carte donnée, une demandée", async () => {
    const fetchMock = mockFetch({
      ...CONNECTE,
      "GET /api/trades/partner/luffy/works": {
        status: 200,
        body: [
          {
            content: { ...carte(0, "").content, poster_url: null, year: 1999 },
            mine: 1,
            theirs: 1,
          },
        ],
      },
      "GET /api/trades/partner/luffy/works/7": {
        status: 200,
        body: [
          { card: carte(2, "Zoro"), mine: 2, theirs: 0 },
          { card: carte(1, "Nami"), mine: 0, theirs: 1 },
        ],
      },
      "POST /api/trades": { status: 201, body: { ...RECU, direction: "outgoing" } },
      "GET /api/trades": { status: 200, body: [] },
      "GET /api/friends": { status: 200, body: { friends: [], incoming: [], outgoing: [] } },
    });
    afficher("/echanges/nouveau/luffy");

    const select = await screen.findByRole("combobox", { name: "Œuvre" });
    await screen.findByRole("option", { name: /One Piece/ });
    fireEvent.change(select, { target: { value: "7" } });
    fireEvent.click(await screen.findByRole("button", { name: "Donner Zoro (Rare)" }));
    fireEvent.click(screen.getByRole("button", { name: "Demander Nami (Rare)" }));
    fireEvent.click(screen.getByRole("button", { name: "Proposer" }));

    await waitFor(() => {
      const envoi = fetchMock.mock.calls.find(([url, init]) => url === "/api/trades" && init?.method === "POST");
      expect(envoi).toBeTruthy();
      expect(JSON.parse(String(envoi![1]!.body))).toMatchObject({ username: "luffy", give: [2], take: [1] });
    });
  });
});
