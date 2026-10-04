"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { generateResumePdf } from "@/lib/api";

export type PdfState =
  | { status: "idle" }
  | { status: "pending" }
  | { status: "ready"; url: string }
  | { status: "error"; message: string };

/**
 * Explicit "Generate PDF": nothing is requested until `generate` is called. Responses that
 * arrive out of order (an older request finishing after a newer one) are discarded, and the
 * previous blob URL is released whenever it is replaced or the component unmounts.
 */
export function useResumePdf(documentId: string) {
  const [state, setState] = useState<PdfState>({ status: "idle" });
  const latest = useRef(0);
  const current = useRef<string | null>(null);

  const release = useCallback(() => {
    if (current.current !== null) URL.revokeObjectURL(current.current);
    current.current = null;
  }, []);

  const generate = useCallback(async () => {
    latest.current += 1;
    const requestId = latest.current;
    setState({ status: "pending" });
    try {
      const blob = await generateResumePdf(documentId);
      if (requestId !== latest.current) return;
      release();
      current.current = URL.createObjectURL(blob);
      setState({ status: "ready", url: current.current });
    } catch (error) {
      if (requestId !== latest.current) return;
      setState({
        status: "error",
        message: error instanceof Error ? error.message : "The PDF could not be generated.",
      });
    }
  }, [documentId, release]);

  const reset = useCallback(() => {
    latest.current += 1;
    release();
    setState({ status: "idle" });
  }, [release]);

  useEffect(() => release, [release]);

  return { state, generate, reset };
}
