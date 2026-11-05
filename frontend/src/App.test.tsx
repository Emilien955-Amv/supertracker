import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import App from "./App";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("Page d'accueil", () => {
  it("affiche l'API comme opérationnelle quand /api/health répond ok", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        json: async () => ({ status: "ok", database: true, redis: true, version: "0.1.0" }),
      }),
    );

    render(<App />);

    expect(await screen.findByText(/Opérationnelle/)).toBeTruthy();
  });

  it("affiche un message d'erreur si l'API est injoignable", async () => {
    vi.stubGlobal("fetch", vi.fn().mockRejectedValue(new Error("réseau coupé")));

    render(<App />);

    expect(await screen.findByRole("alert")).toBeTruthy();
  });
});
