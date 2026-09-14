"use client";

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RunBanners } from "./RunBanners";

afterEach(cleanup);

vi.mock("./RunBanner", () => ({
  RunBanner: ({
    searchId,
    onDismiss,
  }: {
    searchId: string;
    onDismiss: () => void;
  }) => (
    <button type="button" onClick={onDismiss}>
      dismiss-{searchId}
    </button>
  ),
}));

describe("RunBanners", () => {
  it("renders one banner per active run", () => {
    render(
      <RunBanners searchIds={["run-1", "run-2"]} profileId="p-1" onDismiss={() => {}} />,
    );
    expect(screen.getByText("dismiss-run-1")).toBeInTheDocument();
    expect(screen.getByText("dismiss-run-2")).toBeInTheDocument();
  });

  it("dismisses only the requested run", async () => {
    const user = userEvent.setup();
    const onDismiss = vi.fn();
    render(
      <RunBanners searchIds={["run-1", "run-2"]} profileId="p-1" onDismiss={onDismiss} />,
    );
    await user.click(screen.getByText("dismiss-run-1"));
    expect(onDismiss).toHaveBeenCalledWith("run-1");
    expect(onDismiss).not.toHaveBeenCalledWith("run-2");
  });

  it("renders nothing when no runs are active", () => {
    render(<RunBanners searchIds={[]} profileId="p-1" onDismiss={() => {}} />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
