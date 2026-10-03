"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { CostEstimate } from "@/lib/api";

import { QueryCostConfirm } from "./QueryCostConfirm";

let respond: (profileId: string) => Promise<CostEstimate> = () => Promise.reject(new Error("unset"));
const requested: string[] = [];

vi.mock("@/lib/api", () => ({
  estimateTuneQueries: (profileId: string) => {
    requested.push(`tune:${profileId}`);
    return respond(profileId);
  },
  estimateRegenerateQueries: (profileId: string) => {
    requested.push(`regenerate:${profileId}`);
    return respond(profileId);
  },
}));

function renderConfirm(
  kind: "tune" | "regenerate" = "tune",
  onConfirm = vi.fn(),
  onCancel = vi.fn(),
) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={client}>
      <QueryCostConfirm
        kind={kind}
        profileId="p-1"
        onConfirm={onConfirm}
        onCancel={onCancel}
        pending={false}
      />
    </QueryClientProvider>,
  );
  return { onConfirm, onCancel };
}

const estimate = (overrides: Partial<CostEstimate>): CostEstimate => ({
  prompt_tokens: 1800,
  completion_tokens: 200,
  usd: 0.00158,
  basis: "litellm_price_map",
  message: null,
  ...overrides,
});

beforeEach(() => {
  requested.length = 0;
});
afterEach(cleanup);

describe("QueryCostConfirm", () => {
  it("shows the estimated tokens and dollars before the user confirms", async () => {
    respond = () => Promise.resolve(estimate({}));
    renderConfirm();

    expect(screen.getByText("Estimating cost…")).toBeInTheDocument();
    expect(await screen.findByText(/≈ 2,000 tokens, ≈ \$0\.0016/)).toBeInTheDocument();
    expect(requested).toEqual(["tune:p-1"]);
  });

  it("says so when the model's price is unknown", async () => {
    respond = () =>
      Promise.resolve(
        estimate({ usd: null, basis: "unavailable", message: "cost unavailable for this model" }),
      );
    renderConfirm();

    expect(await screen.findByText(/cost unavailable for this model/)).toBeInTheDocument();
    expect(screen.queryByText(/\$/)).not.toBeInTheDocument();
  });

  it("reports an estimate failure without blocking the choice", async () => {
    respond = () => Promise.reject(new Error("no signals yet"));
    const { onConfirm } = renderConfirm("tune");

    expect(await screen.findByRole("alert")).toHaveTextContent("no signals yet");
    await userEvent.click(screen.getByRole("button", { name: "Tune my queries" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("prices first-time generation with the regenerate estimate", async () => {
    respond = () => Promise.resolve(estimate({}));
    const { onConfirm } = renderConfirm("regenerate");

    expect(await screen.findByText(/≈ 2,000 tokens, ≈ \$0\.0016/)).toBeInTheDocument();
    expect(requested).toEqual(["regenerate:p-1"]);
    await userEvent.click(screen.getByRole("button", { name: "Regenerate" }));
    expect(onConfirm).toHaveBeenCalledOnce();
  });

  it("cancels", async () => {
    respond = () => Promise.resolve(estimate({}));
    const { onCancel } = renderConfirm("tune");

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onCancel).toHaveBeenCalledOnce();
  });
});
