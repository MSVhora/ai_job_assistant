import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { achievement } from "./fixtures";
import { SourceBadges } from "./SourceBadges";

describe("SourceBadges", () => {
  it("shows the repository as a link and the employer as a separate badge", () => {
    render(
      <SourceBadges
        achievement={achievement({
          project_key: "ada/engine",
          employer_ref: { company: "Acme Corp", start_date: "Mar 2021", source: "scope" },
        })}
      />,
    );

    expect(screen.getByRole("link", { name: "Repository ada/engine" })).toHaveAttribute(
      "href",
      "https://github.com/ada/engine",
    );
    expect(screen.getByText("Employer: Acme Corp · from the repository")).toBeVisible();
  });

  it("says when you set the employer yourself, including for personal work", () => {
    render(
      <SourceBadges
        achievement={achievement({ employer_ref: { kind: "personal", source: "user" } })}
      />,
    );

    expect(screen.getByText("Employer: Personal / open source · set by you")).toBeVisible();
  });

  it("flags a suggested employer as unconfirmed", () => {
    render(
      <SourceBadges
        achievement={achievement({
          employer_ref: { company: "Old Co", start_date: "2019", source: "suggested" },
        })}
      />,
    );

    expect(screen.getByText("Employer: Old Co · suggested")).toBeVisible();
  });

  it("says the employer is not set and still shows the repository", () => {
    render(<SourceBadges achievement={achievement({ employer_ref: null })} />);

    expect(screen.getByText("Employer not set")).toBeVisible();
    expect(screen.getByRole("link", { name: "Repository ada/engine" })).toBeVisible();
  });

  it("does not link a source that is not a GitHub repository", () => {
    render(<SourceBadges achievement={achievement({ project_key: "resume:Acme Corp" })} />);

    expect(screen.getByText("Source: resume:Acme Corp")).toBeVisible();
    expect(screen.queryByRole("link")).not.toBeInTheDocument();
  });
});
