"use client";

import { toast } from "sonner";

export function CopyButton({
  label,
  ariaLabel,
  getText,
}: {
  label: string;
  ariaLabel?: string | undefined;
  getText: () => string | Promise<string>;
}) {
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(await getText());
      toast.success("Copied to the clipboard");
    } catch {
      toast.error("Could not copy — select the text and copy it manually.");
    }
  };
  return (
    <button
      type="button"
      aria-label={ariaLabel ?? label}
      onClick={() => void copy()}
      className="rounded-full px-2.5 py-1 text-xs font-semibold text-violet-700 hover:bg-violet-50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
    >
      {label}
    </button>
  );
}
