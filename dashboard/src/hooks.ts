import { useCallback, useEffect, useState, useSyncExternalStore } from "react";

export type Route =
  | { page: "queue" }
  | { page: "claim"; claimId: string }
  | { page: "instructions" };

export function parseRoute(hash: string): Route {
  const claim = /^#\/claims\/([\w-]+)$/.exec(hash);
  if (claim?.[1]) return { page: "claim", claimId: claim[1] };
  if (hash === "#/instructions") return { page: "instructions" };
  return { page: "queue" };
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener("hashchange", onChange);
  return () => {
    window.removeEventListener("hashchange", onChange);
  };
}

export function useRoute(): Route {
  return parseRoute(
    useSyncExternalStore(subscribe, () => window.location.hash),
  );
}

export interface Loaded<T> {
  data?: T;
  error?: string;
  reload: () => void;
}

/** Loads data with a stable loader, and loads it again on reload(). */
export function useLoad<T>(load: () => Promise<T>): Loaded<T> {
  const [state, setState] = useState<{ data?: T; error?: string }>({});
  const [version, setVersion] = useState(0);

  useEffect(() => {
    let current = true;
    load().then(
      (data) => {
        if (current) setState({ data });
      },
      (error: unknown) => {
        if (current) setState({ error: String(error) });
      },
    );
    return () => {
      current = false;
    };
  }, [load, version]);

  const reload = useCallback(() => {
    setVersion((v) => v + 1);
  }, []);

  return { ...state, reload };
}

/** Calls tick every interval while active is true. */
export function usePolling(
  active: boolean,
  tick: () => void,
  interval: number,
): void {
  useEffect(() => {
    if (!active) return;
    const timer = setInterval(tick, interval);
    return () => {
      clearInterval(timer);
    };
  }, [active, tick, interval]);
}
