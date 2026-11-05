import { useCallback, useEffect, useState } from "react";

import { ApiError, apiFetch } from "./api";

export type ApiState<T> =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; error: ApiError | Error }
  | { status: "success"; data: T };

/**
 * Charge une ressource de l'API et suit son état (chargement, erreur, succès).
 *
 * - path = null : ne charge rien (ex. recherche encore vide).
 * - Si path change avant la fin du chargement, l'ancienne requête est annulée :
 *   une réponse lente ne peut jamais écraser une réponse plus récente.
 */
export function useApi<T>(path: string | null): ApiState<T> {
  return useApiResource<T>(path)[0];
}

/**
 * Comme useApi, mais renvoie aussi « setData » pour remplacer la donnée
 * affichée (ex. par la réponse d'une modification), sans recharger.
 */
export function useApiResource<T>(
  path: string | null,
): [ApiState<T>, (data: T) => void] {
  const [state, setState] = useState<ApiState<T>>({ status: "idle" });
  const setData = useCallback((data: T) => setState({ status: "success", data }), []);

  useEffect(() => {
    if (path === null) {
      setState({ status: "idle" });
      return;
    }
    const controller = new AbortController();
    setState({ status: "loading" });
    apiFetch<T>(path, { signal: controller.signal })
      .then((data) => setState({ status: "success", data }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setState({
          status: "error",
          error: error instanceof Error ? error : new Error("Erreur inconnue"),
        });
      });
    return () => controller.abort();
  }, [path]);

  return [state, setData];
}

/** Renvoie la valeur seulement après « delay » ms sans changement : on évite
 * ainsi d'interroger l'API à chaque lettre tapée. */
export function useDebouncedValue<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
