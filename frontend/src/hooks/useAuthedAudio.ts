import { useEffect, useState } from "react";
import { isDemoMode } from "../lib/demoMode";

/**
 * Fetch an audio file with the JWT attached and return a blob URL suitable
 * for <audio src>. Native <audio> can't send custom headers, so the blob
 * indirection is the only way to serve JWT-protected audio.
 *
 * Pass a null/undefined url to disable the fetch.
 */
export function useAuthedAudio(url: string | null | undefined): string | null {
  const [objectUrl, setObjectUrl] = useState<string | null>(null);

  useEffect(() => {
    if (!url) {
      setObjectUrl(null);
      return;
    }
    // In demo mode, rewrite /api/v1/* to /api/demo/* and skip the JWT —
    // mirrors what apiFetch does for JSON requests, but for the raw
    // <audio> blob fetch.
    const demo = isDemoMode();
    const finalUrl =
      demo && url.startsWith("/api/v1/")
        ? "/api/demo/" + url.slice("/api/v1/".length)
        : url;
    const token = demo ? null : localStorage.getItem("callisto_token");
    const controller = new AbortController();
    let created: string | null = null;
    (async () => {
      try {
        const resp = await fetch(finalUrl, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: controller.signal,
        });
        if (!resp.ok) return;
        const blob = await resp.blob();
        created = URL.createObjectURL(blob);
        setObjectUrl(created);
      } catch {
        /* aborted or network error */
      }
    })();
    return () => {
      controller.abort();
      if (created) URL.revokeObjectURL(created);
      setObjectUrl(null);
    };
  }, [url]);

  return objectUrl;
}
