"use client";

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            "!rounded-lg !border !border-gray-200 !bg-white !text-gray-900 !shadow-lg",
          description: "!text-gray-600",
        },
      }}
    />
  );
}
