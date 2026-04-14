import { useEffect } from "react";

/**
 * Sets the document title to "{title} · Callisto".
 * Pass `null` to use just "Callisto".
 */
export function useDocumentTitle(title: string | null) {
  useEffect(() => {
    document.title = title ? `${title} · Callisto` : "Callisto";
  }, [title]);
}
