"use client";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { useSetupCheck } from "@/hooks/use-setup";

const PROVIDERS = [
  { key: "llm_configured", name: "LLM (generation)", hint: "Gemini Flash via LiteLLM" },
  { key: "embedding_configured", name: "Embeddings", hint: "Needed for job matching" },
  { key: "adzuna_configured", name: "Adzuna", hint: "Official job-search API" },
  { key: "apify_configured", name: "Apify", hint: "Runs scraping actors you enable" },
] as const;

export function KeyStatusCards() {
  const { data, isPending, isError, refetch } = useSetupCheck();

  if (isPending) {
    return (
      <div className="grid gap-3 sm:grid-cols-2" aria-busy="true" aria-live="polite">
        {[0, 1, 2, 3].map((index) => (
          <div
            key={index}
            className="h-20 animate-pulse rounded-xl border border-gray-200 bg-gray-50 dark:border-gray-800 dark:bg-gray-800"
          />
        ))}
      </div>
    );
  }

  if (isError || data === undefined) {
    return (
      <Card title="Provider status">
        <p className="text-sm text-red-700 dark:text-red-400">
          Could not load the provider status from the backend.
        </p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="mt-3 rounded-lg border border-gray-300 px-3 py-2 text-sm font-medium hover:bg-gray-100 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 dark:border-gray-700 dark:hover:bg-gray-800"
        >
          Retry
        </button>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      <div className="grid gap-3 sm:grid-cols-2">
        {PROVIDERS.map((provider) => {
          const configured = data[provider.key];
          return (
            <Card key={provider.key}>
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium text-gray-900 dark:text-gray-100">{provider.name}</p>
                  <p className="mt-0.5 text-xs text-gray-500 dark:text-gray-400">
                    {provider.hint}
                  </p>
                </div>
                <Badge variant={configured ? "success" : "warn"}>
                  {configured ? "Configured" : "Missing"}
                </Badge>
              </div>
            </Card>
          );
        })}
      </div>
      {data.warnings.length > 0 && (
        <ul className="rounded-xl border border-amber-300 bg-amber-50 p-4 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950 dark:text-amber-300">
          {data.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
