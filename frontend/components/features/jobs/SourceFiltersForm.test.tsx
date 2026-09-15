"use client";

import { useState } from "react";

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useForm, FormProvider } from "react-hook-form";
import { describe, expect, it } from "vitest";

import { Accordion } from "@/components/ui/accordion";
import type { SourceFilterDecl } from "@/lib/api";

import { SourceFiltersForm } from "./SourceFiltersForm";
import { emptyQueryFields, type SearchFormValues } from "./search-form-schema";

const adzunaDecls: SourceFilterDecl[] = [
  {
    key: "title_only",
    label: "Title-only search",
    type: "boolean",
    required: false,
    help_text: "Match the title phrase only",
  },
  {
    key: "distance_km",
    label: "Radius (km)",
    type: "number",
    required: false,
    placeholder: "25",
  },
  {
    key: "sort_by",
    label: "Sort by",
    type: "select",
    required: false,
    options: [
      { value: "relevance", label: "Relevance" },
      { value: "date", label: "Date posted" },
    ],
  },
];

const linkedinDecls: SourceFilterDecl[] = [
  {
    key: "company_ids",
    label: "Company IDs",
    type: "multiselect",
    required: false,
    help_text: "LinkedIn company IDs to target",
  },
];

function Providers({ children }: { children: React.ReactNode }) {
  const form = useForm<SearchFormValues>({
    defaultValues: {
      query: emptyQueryFields(),
      source: "adzuna",
      location: "",
      country: "",
      minSalary: "",
      maxSalary: "",
      posted_within: "any",
      results_wanted: 10,
    },
  });
  return <FormProvider {...form}>{children}</FormProvider>;
}

describe("SourceFiltersForm", () => {
  it("renders the declared fields with labels for a source", () => {
    render(
      <Providers>
        <SourceFiltersForm decls={adzunaDecls} />
      </Providers>,
    );
    expect(screen.getByText("Advanced filters")).toBeInTheDocument();
    expect(screen.getByRole("checkbox", { name: "Title-only search" })).toBeInTheDocument();
    expect(screen.getByLabelText("Radius (km)")).toBeInTheDocument();
    expect(screen.getByLabelText("Sort by")).toBeInTheDocument();
    expect(screen.getByRole("option", { name: "Date posted" })).toBeInTheDocument();
    expect(screen.getByText("Match the title phrase only")).toBeInTheDocument();
  });

  it("renders a text input for multiselect declarations", () => {
    render(
      <Providers>
        <SourceFiltersForm decls={linkedinDecls} />
      </Providers>,
    );
    const input = screen.getByLabelText("Company IDs");
    expect(input.tagName).toBe("INPUT");
    expect(input.getAttribute("type")).toBe("text");
    expect(screen.getByText("LinkedIn company IDs to target")).toBeInTheDocument();
  });
});

describe("Accordion", () => {
  function Harness() {
    const [open, setOpen] = useState(false);
    return (
      <Accordion
        id="test-item"
        open={open}
        onToggle={() => setOpen((previous) => !previous)}
        trigger="Header"
      >
        <p>Body</p>
      </Accordion>
    );
  }

  it("toggles aria-expanded and renders the content region", async () => {
    const user = userEvent.setup();
    render(<Harness />);
    const trigger = screen.getByRole("button", { name: "Header" });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Body")).not.toBeInTheDocument();

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByRole("region")).toBeInTheDocument();
    expect(screen.getByText("Body")).toBeInTheDocument();

    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("Body")).not.toBeInTheDocument();
  });
});
