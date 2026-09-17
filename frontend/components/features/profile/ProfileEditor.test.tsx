"use client";

import type { ReactElement } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { ProfileResponse } from "@/lib/api";

import { EditorBody } from "./ProfileEditor";

vi.mock("@/hooks/use-profiles", () => ({
  useProfile: vi.fn(),
  useUpdateProfile: vi.fn(() => ({
    isPending: false,
    error: null,
    data: null,
    mutate: vi.fn(),
  })),
}));

vi.mock("./ProfileReviewForm", () => ({
  ProfileReviewForm: () => <section>review-form</section>,
}));

vi.mock("./GapFillChat", () => ({
  GapFillChat: () => <section>gap-fill-chat</section>,
}));

const queryClient = new QueryClient();

function wrapper(ui: ReactElement) {
  return (
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>
  );
}

function profileFixture(missingFields: string[]): ProfileResponse {
  return {
    profile_id: "p-1",
    name: "Main",
    structured_profile: { contact: { full_name: "Jane Doe" }, skills: ["SQL"] },
    missing_fields: missingFields,
  } as unknown as ProfileResponse;
}

afterEach(cleanup);

describe("EditorBody gap-fill visibility", () => {
  it("hides the chat when the profile has no missing fields", () => {
    render(wrapper(<EditorBody profile={profileFixture([])} />));
    expect(screen.queryByText("gap-fill-chat")).not.toBeInTheDocument();
    expect(screen.getByText("review-form")).toBeInTheDocument();
  });

  it("shows the chat when fields are missing", () => {
    render(wrapper(<EditorBody profile={profileFixture(["preferences.salary_band"])} />));
    expect(screen.getByText("gap-fill-chat")).toBeInTheDocument();
  });
});
