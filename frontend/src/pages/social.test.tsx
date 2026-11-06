import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
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
  "GET /api/users/me": { status: 200, body: { ...UTILISATEUR, bio: null } },
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

describe("Amis", () => {
  it("cherche un pseudo, envoie une demande et accepte une demande reçue", async () => {
    const fetchMock = mockFetch({
      ...CONNECTE,
      "GET /api/friends": {
        status: 200,
        body: {
          friends: [],
          incoming: [{ username: "luffy", avatar_url: null, relation: "incoming" }],
          outgoing: [],
        },
      },
      "GET /api/users/search?q=zor": {
        status: 200,
        body: [{ username: "zoro", avatar_url: null, relation: "none" }],
      },
      "POST /api/friends/zoro": {
        status: 200,
        body: { username: "zoro", avatar_url: null, relation: "outgoing" },
      },
      "POST /api/friends/luffy": {
        status: 200,
        body: { username: "luffy", avatar_url: null, relation: "friends" },
      },
    });
    afficher("/amis");

    // Demande reçue : bouton « Accepter ».
    fireEvent.click(await screen.findByRole("button", { name: "Accepter la demande : luffy" }));
    await waitFor(() =>
      expect(fetchMock.mock.calls.some(([url, init]) => url === "/api/friends/luffy" && init?.method === "POST")).toBe(true),
    );

    fireEvent.change(screen.getByLabelText("Chercher un utilisateur par pseudo"), {
      target: { value: "zor" },
    });
    fireEvent.click(await screen.findByRole("button", { name: "Ajouter en ami : zoro" }));
    expect(await screen.findByRole("button", { name: "Annuler la demande : zoro" })).toBeTruthy();
  });

  it("affiche un profil privé sans ses statistiques", async () => {
    mockFetch({
      ...CONNECTE,
      "GET /api/users/nami/profile": {
        status: 200,
        body: {
          username: "nami",
          avatar_url: null,
          relation: "none",
          visible: false,
          is_public: false,
          bio: null,
          member_since: null,
          stats: null,
        },
      },
    });
    afficher("/u/nami");

    expect(await screen.findByRole("heading", { name: "nami" })).toBeTruthy();
    expect(screen.getByText(/Ce profil est privé/)).toBeTruthy();
    expect(screen.getByRole("button", { name: "Ajouter en ami : nami" })).toBeTruthy();
  });
});
