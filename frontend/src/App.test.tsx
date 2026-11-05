import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "./App";
import { AuthProvider } from "./auth/AuthContext";
import { validateRegistration } from "./pages/RegisterPage";
import { JETON, UTILISATEUR, mockFetch } from "./test/mockFetch";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

const SANS_SESSION = { "POST /api/auth/refresh": { status: 401, body: { detail: "Session expirée." } } };
const SANTE_OK = {
  "GET /api/health": { status: 200, body: { status: "ok", database: true, redis: true, version: "0.1.0" } },
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

/** Attend que le champ apparaisse (fin du chargement de session), puis le remplit. */
async function saisir(label: RegExp, valeur: string) {
  fireEvent.change(await screen.findByLabelText(label), { target: { value: valeur } });
}

describe("Navigation selon la session", () => {
  it("redirige un visiteur non connecté vers la page de connexion", async () => {
    mockFetch(SANS_SESSION);
    afficher("/");
    expect(await screen.findByRole("heading", { name: "Connexion" })).toBeTruthy();
  });

  it("retrouve la session existante grâce au cookie et accueille l'utilisateur", async () => {
    mockFetch({
      ...SANTE_OK,
      "POST /api/auth/refresh": { status: 200, body: JETON },
      "GET /api/users/me": { status: 200, body: UTILISATEUR },
    });
    afficher("/");
    expect(await screen.findByRole("heading", { name: /Bonjour emilien/ })).toBeTruthy();
    expect(await screen.findByText(/Opérationnelle/)).toBeTruthy();
  });
});

describe("Connexion", () => {
  it("affiche le message du serveur si les identifiants sont faux", async () => {
    mockFetch({
      ...SANS_SESSION,
      "POST /api/auth/login": { status: 401, body: { detail: "E-mail ou mot de passe incorrect." } },
    });
    afficher("/connexion");

    await saisir(/E-mail/, "emilien@exemple.fr");
    await saisir(/Mot de passe/, "mauvais");
    fireEvent.click(await screen.findByRole("button", { name: "Se connecter" }));

    expect((await screen.findByRole("alert")).textContent).toContain("incorrect");
  });

  it("connecte l'utilisateur et l'envoie vers l'accueil", async () => {
    mockFetch({
      ...SANS_SESSION,
      ...SANTE_OK,
      "POST /api/auth/login": { status: 200, body: JETON },
      "GET /api/users/me": { status: 200, body: UTILISATEUR },
    });
    afficher("/connexion");

    await saisir(/E-mail/, "emilien@exemple.fr");
    await saisir(/Mot de passe/, "un-mot-de-passe-solide");
    fireEvent.click(await screen.findByRole("button", { name: "Se connecter" }));

    expect(await screen.findByRole("heading", { name: /Bonjour emilien/ })).toBeTruthy();
  });
});

describe("Inscription", () => {
  it("vérifie les champs avant d'appeler le serveur", async () => {
    const fetchMock = mockFetch(SANS_SESSION);
    afficher("/inscription");

    await saisir(/E-mail/, "emilien@exemple.fr");
    await saisir(/Pseudo/, "emilien");
    await saisir(/^Mot de passe/, "court");
    fireEvent.click(await screen.findByRole("button", { name: "Créer mon compte" }));

    expect(await screen.findByText("Au moins 10 caractères.")).toBeTruthy();
    const appels = fetchMock.mock.calls.map(([url]) => url);
    expect(appels).not.toContain("/api/auth/register");
  });

  it("valide le format de chaque champ", () => {
    expect(validateRegistration("emilien@exemple.fr", "emilien_95", "un-mot-de-passe")).toEqual({});

    const erreurs = validateRegistration("pas-un-email", "é!", "court");
    expect(Object.keys(erreurs).sort()).toEqual(["email", "password", "username"]);
  });
});
