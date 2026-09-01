"use client";

import { Toaster as SonnerToaster } from "sonner";

export function Toaster() {
  return (
    <SonnerToaster
      position="bottom-right"
      toastOptions={{
        classNames: {
          toast:
            "!rounded-lg !border !border-gray-200 !bg-white !text-gray-900 !shadow-lg dark:!border-gray-700 dark:!bg-gray-900 dark:!text-gray-100",
          description: "!text-gray-600 dark:!text-gray-400",
        },
      }}
    />
  );
}
