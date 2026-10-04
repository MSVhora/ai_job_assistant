"use client";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";

const LISTED_REPOS = 5;

function titleFor(repos: string[], firstTime: boolean): string {
  const single = repos.length === 1;
  if (firstTime) return single ? "Use a private repository?" : "Use private repositories?";
  return single
    ? `Enable ${repos[0] ?? "this repository"}?`
    : `Enable ${repos.length} private repositories?`;
}

function descriptionFor(repos: string[]): string | undefined {
  if (repos.length === 0) return undefined;
  if (repos.length <= LISTED_REPOS) return repos.join(", ");
  return `${repos.slice(0, LISTED_REPOS).join(", ")} and ${repos.length - LISTED_REPOS} more`;
}

export function DisclosureModal({
  repos,
  firstTime,
  pending,
  onConfirm,
  onCancel,
}: {
  repos: string[];
  firstTime: boolean;
  pending: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  const many = repos.length > 1;
  return (
    <Modal
      open={repos.length > 0}
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
      title={titleFor(repos, firstTime)}
      description={descriptionFor(repos)}
    >
      {firstTime ? (
        <div className="flex flex-col gap-3 text-sm text-gray-700">
          <p>
            Fetching from GitHub stays on your machine. Text from{" "}
            {many ? "these repositories" : "this repository"} reaches your LLM provider only when
            you run an extraction — and you see an estimate, including how much of it is private,
            before that happens.
          </p>
          <p>
            <strong>What can be sent:</strong> commit messages, pull request, issue and review text,
            README text and the names of files a pull request touched.
          </p>
          <p>
            <strong>What is never sent:</strong> file contents, diffs and your GitHub token.
          </p>
          <p>
            Anything derived from {many ? "these repositories" : "this repository"} is marked{" "}
            <em>Generated from private repository data</em> wherever it appears.
          </p>
        </div>
      ) : (
        <p className="text-sm text-gray-700">
          {many ? "These are private repositories" : "This is a private repository"}. Their text can
          reach your LLM provider at extraction, and anything derived from them is marked as
          private.
        </p>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={onConfirm} disabled={pending}>
          {firstTime ? "I understand — save" : "Save"}
        </Button>
      </div>
    </Modal>
  );
}
