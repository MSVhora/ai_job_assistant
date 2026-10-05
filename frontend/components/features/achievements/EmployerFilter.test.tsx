"use client";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import type { EmployerGroup } from "@/lib/api";

import { EmployerFilter } from "./EmployerFilter";

const GROUPS: EmployerGroup[] = [
  { kind: "employer", label: "Acme", total: 3, eligible: 2, repositories: [] },
  { kind: "personal", label: "Personal", total: 1, eligible: 0, repositories: [] },
];

describe("EmployerFilter", () => {
  it("lists each employer with its draft count and reports the choice", async () => {
    const onChange = vi.fn();
    render(<EmployerFilter groups={GROUPS} value="" onChange={onChange} />);

    expect(screen.getByRole("option", { name: "All employers (4)" })).toBeInTheDocument();
    await userEvent.selectOptions(screen.getByLabelText("Employer"), "employer:Acme");

    expect(onChange).toHaveBeenCalledWith("employer:Acme");
  });

  it("renders nothing without drafts", () => {
    render(<EmployerFilter groups={[]} value="" onChange={vi.fn()} />);

    expect(screen.queryByLabelText("Employer")).not.toBeInTheDocument();
  });
});
