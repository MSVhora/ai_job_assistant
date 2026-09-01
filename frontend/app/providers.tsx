"use client";

import {
  MutationCache,
  QueryCache,
  QueryClient,
  QueryClientProvider,
} from "@tanstack/react-query";
import { toast } from "sonner";
import { useState, type ReactNode } from "react";

import { ApiError } from "@/lib/api/client";

function notifyError(error: Error) {
  toast.error(error.message, { id: error.message });
}

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            retry: (failureCount, error) => {
              if (error instanceof ApiError && error.status >= 400 && error.status < 500) {
                return false;
              }
              return failureCount < 1;
            },
          },
          mutations: {
            retry: false,
          },
        },
        queryCache: new QueryCache({
          onError: (error, query) => {
            if (query.meta?.silent !== true) {
              notifyError(error);
            }
          },
        }),
        mutationCache: new MutationCache({
          onError: notifyError,
        }),
      }),
  );
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}
