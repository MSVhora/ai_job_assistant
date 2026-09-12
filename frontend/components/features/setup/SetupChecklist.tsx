"use client";

import { Badge } from "@/components/ui/badge";
import { useSetupCheck } from "@/hooks/use-setup";
import { CheckCircleIcon, ExternalLinkIcon, KeyIcon } from "./icons";

type ProviderStep = {
  name: string;
  description: string;
  guideHref: string;
  guideLabel: string;
  envVars: string[];
  isConfigured: (data: {
    llm_configured: boolean;
    embedding_configured: boolean;
    adzuna_configured: boolean;
    apify_configured: boolean;
  }) => boolean;
};

const STEPS: ProviderStep[] = [
  {
    name: "Gemini API key",
    description:
      "Powers resume extraction, match explanations, and job embeddings. Free tier includes a generous daily quota.",
    guideHref: "https://aistudio.google.com/apikey",
    guideLabel: "Get a free Gemini API key",
    envVars: ["GEMINI_API_KEY"],
    isConfigured: (data) => data.llm_configured && data.embedding_configured,
  },
  {
    name: "Adzuna app ID + key",
    description:
      "The official job-search API used to find job postings. Free to register, no credit card needed.",
    guideHref: "https://developer.adzuna.com/signup",
    guideLabel: "Create free Adzuna API keys",
    envVars: ["ADZUNA_APP_ID", "ADZUNA_APP_KEY"],
    isConfigured: (data) => data.adzuna_configured,
  },
  {
    name: "Apify token",
    description:
      "Optional — only needed for the LinkedIn scraper source. Runs on your own Apify account, paid per result.",
    guideHref: "https://console.apify.com/settings/integrations",
    guideLabel: "Get your Apify token",
    envVars: ["APIFY_TOKEN"],
    isConfigured: (data) => data.apify_configured,
  },
];

export function SetupChecklist() {
  const { data, isPending, isError, refetch, isFetching } = useSetupCheck();

  if (isPending) {
    return (
      <div
        className="flex flex-col gap-3 rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur"
        aria-busy="true"
        aria-live="polite"
      >
        {[0, 1, 2].map((index) => (
          <div
            key={index}
            className="h-20 animate-pulse rounded-2xl border border-violet-100 bg-violet-50/50"
          />
        ))}
      </div>
    );
  }

  if (isError || data === undefined) {
    return (
      <section className="rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur">
        <p className="text-sm text-red-700">
          Could not load the provider status from the backend. Make sure the API is running.
        </p>
        <button
          type="button"
          onClick={() => void refetch()}
          className="mt-3 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-5 py-2 text-sm font-semibold text-white shadow-md shadow-violet-300 hover:shadow-lg hover:shadow-violet-400/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          Retry
        </button>
      </section>
    );
  }

  const configuredCount = STEPS.filter((step) => step.isConfigured(data)).length;

  return (
    <section
      className="rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur sm:p-8"
      aria-labelledby="api-keys-heading"
    >
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200">
            <KeyIcon className="h-4.5 w-4.5" />
          </span>
          <div>
            <h2 id="api-keys-heading" className="text-base font-bold tracking-tight text-gray-900">
              API keys
            </h2>
            <p className="text-xs text-gray-500">
              {configuredCount} of {STEPS.length} configured
            </p>
          </div>
        </div>
        <button
          type="button"
          onClick={() => void refetch()}
          disabled={isFetching}
          className="rounded-full border border-violet-200 bg-white px-4 py-2 text-sm font-semibold text-violet-700 shadow-sm shadow-violet-100 transition hover:-translate-y-0.5 hover:shadow-md hover:shadow-violet-200 disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:translate-y-0 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
        >
          {isFetching ? "Checking…" : "Re-check status"}
        </button>
      </div>

      {configuredCount === STEPS.length && (
        <p className="mb-5 flex items-center gap-2 rounded-2xl border border-emerald-200 bg-emerald-50 p-3 text-sm font-medium text-emerald-800">
          <CheckCircleIcon className="h-4.5 w-4.5 shrink-0" />
          All keys are configured — you are ready to go.
        </p>
      )}

      <ol className="flex flex-col gap-3">
        {STEPS.map((step, index) => {
          const done = step.isConfigured(data);
          return (
            <li
              key={step.name}
              className={`rounded-2xl border p-4 transition-colors ${
                done
                  ? "border-emerald-200 bg-emerald-50/50"
                  : "border-violet-100 bg-violet-50/40"
              }`}
            >
              <div className="flex items-start gap-3">
                <span
                  aria-hidden="true"
                  className={`flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-sm font-bold ${
                    done
                      ? "bg-emerald-100 text-emerald-700"
                      : "bg-gradient-to-br from-violet-500 to-fuchsia-500 text-white shadow-md shadow-violet-200"
                  }`}
                >
                  {done ? <CheckCircleIcon className="h-4.5 w-4.5" /> : index + 1}
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-semibold text-gray-900">{step.name}</p>
                    <Badge variant={done ? "success" : "warn"}>
                      {done ? "Configured" : "Missing"}
                    </Badge>
                  </div>
                  <p className="mt-1 text-sm leading-relaxed text-gray-600">{step.description}</p>
                  {done ? (
                    <p className="mt-2 text-xs text-emerald-700">
                      Detected in your backend{" "}
                      <code className="rounded bg-emerald-100/70 px-1 py-0.5 font-mono">.env</code>.
                    </p>
                  ) : (
                    <div className="mt-3 flex flex-col gap-2">
                      <a
                        href={step.guideHref}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex w-fit items-center gap-1.5 rounded-full bg-gradient-to-r from-violet-600 to-purple-600 px-4 py-2 text-sm font-semibold text-white shadow-md shadow-violet-300 transition hover:-translate-y-0.5 hover:shadow-lg hover:shadow-violet-400/50 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600"
                      >
                        {step.guideLabel}
                        <ExternalLinkIcon className="h-3.5 w-3.5" />
                      </a>
                      <p className="text-xs text-gray-500">
                        Then paste it into{" "}
                        {step.envVars.map((envVar, envIndex) => (
                          <span key={envVar}>
                            {envIndex > 0 && " and "}
                            <code className="rounded bg-violet-100/80 px-1 py-0.5 font-mono text-violet-700">
                              {envVar}
                            </code>
                          </span>
                        ))}{" "}
                        in{" "}
                        <code className="rounded bg-violet-100/80 px-1 py-0.5 font-mono text-violet-700">
                          backend/.env
                        </code>{" "}
                        and restart the API.
                      </p>
                    </div>
                  )}
                </div>
              </div>
            </li>
          );
        })}
      </ol>

      {data.warnings.length > 0 && (
        <ul className="mt-5 rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
          {data.warnings.map((warning) => (
            <li key={warning}>{warning}</li>
          ))}
        </ul>
      )}
    </section>
  );
}
