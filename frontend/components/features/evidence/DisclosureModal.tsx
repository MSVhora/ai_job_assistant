"use client";

import { Button } from "@/components/ui/button";
import { Modal } from "@/components/ui/modal";

export function DisclosureModal({
  repo,
  firstTime,
  pending,
  onConfirm,
  onCancel,
}: {
  repo: string | null;
  firstTime: boolean;
  pending: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}) {
  return (
    <Modal
      open={repo !== null}
      onOpenChange={(open) => {
        if (!open) onCancel();
      }}
      title={firstTime ? "Use a private repository?" : `Enable ${repo ?? "this repository"}?`}
      description={repo ?? undefined}
    >
      {firstTime ? (
        <div className="flex flex-col gap-3 text-sm text-gray-700">
          <p>
            Fetching from GitHub stays on your machine. Text from this repository reaches your LLM
            provider only when you run an extraction — and you see an estimate, including how much
            of it is private, before that happens.
          </p>
          <p>
            <strong>What can be sent:</strong> commit messages, pull request, issue and review text,
            README text and the names of files a pull request touched.
          </p>
          <p>
            <strong>What is never sent:</strong> file contents, diffs and your GitHub token.
          </p>
          <p>
            Anything derived from this repository is marked{" "}
            <em>Generated from private repository data</em> wherever it appears.
          </p>
        </div>
      ) : (
        <p className="text-sm text-gray-700">
          This is a private repository. Its text can reach your LLM provider at extraction, and
          anything derived from it is marked as private.
        </p>
      )}
      <div className="mt-5 flex justify-end gap-2">
        <Button variant="secondary" onClick={onCancel}>
          Cancel
        </Button>
        <Button onClick={onConfirm} disabled={pending}>
          {firstTime ? "I understand — enable" : "Enable"}
        </Button>
      </div>
    </Modal>
  );
}
