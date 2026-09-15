"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ProfileResponse, SourceInfo } from "@/lib/api";

import { SearchStepperModal } from "./SearchStepperModal";

const sleep = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

const source = source_fixture();

function source_fixture(): SourceInfo {
  return {
    name: "adzuna",
    is_official_api: true,
    disclosure_required: false,
    is_configured: true,
    enabled: true,
    supports_exclusions: true,
    filters: [
      {
        key: "title_only",
        label: "Title-only search",
        type: "boolean",
        required: false,
      },
    ],
  };
}

const profileResponse = {
  name: "Backend track",
  profile_id: "p-1",
  structured_profile: {
    contact: {
      full_name: "Jane",
      email: null,
      phone: null,
      location: "Berlin",
      country: "de",
      links: [],
    },
    headline: "Engineer",
    summary: null,
    skills: ["Kotlin"],
    experience: [],
    projects: [],
    education: [],
    certifications: [],
    awards: [],
    extra_sections: [],
    preferences: null,
  },
} as unknown as ProfileResponse;

const startMutation = vi.fn();
const onSearchStarted = vi.fn();
const onOpenChange = vi.fn();

vi.mock("@/hooks/use-job-search", async (importOriginal) => {
  const original = await importOriginal<Record<string, unknown>>();
  return {
    ...original,
    useStartJobSearch: () => ({ mutate: startMutation, isPending: false, isError: false, error: null }),
  };
});

vi.mock("@/hooks/use-profiles", async (importOriginal) => ({
  ...(await importOriginal<Record<string, unknown>>()),
  useProfile: () => ({
    data: profileResponse,
    isPending: false,
    isError: false,
  }),
}));

function mount(open = true) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <SearchStepperModal
        open={open}
        onOpenChange={onOpenChange}
        profilesPending={false}
        profilesError={false}
        profilesList={[{ profile_id: "p-1", name: "Backend track" } as never]}
        activeProfileId="p-1"
        onSelectProfile={() => {}}
        sources={[source]}
        onSearchStarted={onSearchStarted}
      />
    </QueryClientProvider>,
  );
}

async function goThrough(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("button", { name: "Next" }));
  await user.click(screen.getByRole("radio", { name: "Search adzuna" }));
  await user.click(screen.getByRole("button", { name: "Next" }));
}

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

describe("SearchStepperModal", () => {
  beforeEach(() => {
    startMutation.mockReset();
    onSearchStarted.mockReset();
    onOpenChange.mockReset();
  });

  it("details hosts the source filters accordion; review lists every field without starting a run", async () => {
    const user = userEvent.setup();
    mount();

    expect(screen.getByText("Profile")).toBeInTheDocument();
    await goThrough(user);

    expect(screen.getByText("AI search queries")).toBeInTheDocument();
    expect(
      screen.getByRole("button", { name: /More filters for this source/ }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /More filters for this source/ }));
    expect(
      screen.getByRole("checkbox", { name: "Title-only search" }),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Next" }));

    const review = screen.getByRole("region", { name: /Review of the search/ });
    expect(review).toHaveTextContent("Review");
    expect(review).toHaveTextContent("Profile");
    expect(review).toHaveTextContent("Posted within");
    expect(review).toHaveTextContent("Advanced filters");
    expect(startMutation).not.toHaveBeenCalled();
  });

  it("starts the search only from the step-4 submit button", async () => {
    const user = userEvent.setup();
    mount();

    await goThrough(user);
    await user.click(screen.getByRole("button", { name: "Next" }));

    // The submit button is inert for its first moments on the review step, so
    // wait the guard out before the genuine press.
    await new Promise((resolve) => setTimeout(resolve, 450));
    await user.click(screen.getByRole("button", { name: "Start search" }));
    expect(startMutation).toHaveBeenCalledTimes(1);
  });

  it("a submit event on the details step advances the wizard instead of starting a run", async () => {
    const user = userEvent.setup();
    mount();

    await goThrough(user);
    expect(screen.getByText("AI search queries")).toBeInTheDocument();

    // Implicit submissions (Enter in a field, browser defaults) land on the
    // form at any step (Radix portals it to document.body) — they must be
    // inert until the review step.
    fireEvent.submit(document.querySelector("form") as HTMLFormElement);
    await sleep(0);
    expect(startMutation).not.toHaveBeenCalled();
    expect(screen.getByRole("region", { name: /Review of the search/ })).toBeInTheDocument();
  });

  it("a submit landing right after the review step renders is ignored", async () => {
    const user = userEvent.setup();
    mount();
    await goThrough(user);
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("region", { name: /Review of the search/ })).toBeInTheDocument();

    fireEvent.submit(document.querySelector("form") as HTMLFormElement);
    await sleep(0);
    expect(startMutation).not.toHaveBeenCalled();

    await new Promise((resolve) => setTimeout(resolve, 450));
    await user.click(screen.getByRole("button", { name: "Start search" }));
    expect(startMutation).toHaveBeenCalledTimes(1);
  });
});
