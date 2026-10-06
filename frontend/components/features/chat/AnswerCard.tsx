"use client";

import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { answerWithCitations, plainAnswer, splitAnswer } from "@/lib/agent-view";
import type { AgentCitation, AgentMessage } from "@/lib/api";

import { CitationChip } from "./CitationChip";
import { GroundingBadge, PrivateBadge } from "./GroundingBadge";
import { NoEvidenceCard } from "./NoEvidenceCard";

async function copy(text: string, done: string) {
  try {
    await navigator.clipboard.writeText(text);
    toast.success(done);
  } catch {
    toast.error("Could not copy to the clipboard");
  }
}

function AnswerText({
  message,
  onOpen,
}: {
  message: AgentMessage;
  onOpen: (citation: AgentCitation) => void;
}) {
  const byMarker = new Map(
    message.citations.map((citation, index) => [citation.marker, { citation, number: index + 1 }]),
  );
  return (
    <p className="text-sm leading-relaxed whitespace-pre-wrap text-gray-900">
      {splitAnswer(message.content).map((segment, index) => {
        if (segment.kind === "text") return segment.text;
        const source = byMarker.get(segment.marker);
        return source ? (
          <CitationChip
            key={index}
            citation={source.citation}
            number={source.number}
            onOpen={onOpen}
          />
        ) : null;
      })}
    </p>
  );
}

export function AnswerCard({
  message,
  question,
  busy,
  onOpenCitation,
  onReask,
}: {
  message: AgentMessage;
  question: string;
  busy: boolean;
  onOpenCitation: (citation: AgentCitation) => void;
  onReask: (question: string) => void;
}) {
  const { grounding } = message;
  if (grounding.error) {
    return (
      <div
        role="alert"
        className="rounded-2xl border border-red-200 bg-red-50 p-4 text-sm text-red-800"
      >
        <p>{message.content}</p>
        <Button
          className="mt-3"
          variant="secondary"
          disabled={busy}
          onClick={() => {
            onReask(question);
          }}
        >
          Try again
        </Button>
      </div>
    );
  }
  if (grounding.no_evidence) {
    return (
      <NoEvidenceCard
        content={message.content}
        question={question}
        onReask={onReask}
        disabled={busy}
      />
    );
  }
  const answered = grounding.status === "grounded" || grounding.status === "partial";
  return (
    <div className="flex flex-col gap-3 rounded-2xl border border-violet-100 bg-white p-4 shadow-sm">
      <AnswerText message={message} onOpen={onOpenCitation} />
      {grounding.used_private ? (
        <p className="flex items-center gap-2 text-xs text-gray-600">
          <PrivateBadge /> Generated from private repository data
        </p>
      ) : null}
      {grounding.gaps.length > 0 || grounding.flagged_sentences.length > 0 ? (
        <div className="rounded-xl bg-amber-50 p-3 text-xs text-amber-900">
          {grounding.gaps.map((gap) => (
            <p key={gap}>{gap}</p>
          ))}
          {grounding.flagged_sentences.length > 0 ? (
            <details>
              <summary className="cursor-pointer font-semibold">
                Left out because it could not be confirmed
              </summary>
              <ul className="mt-1 list-disc pl-4">
                {grounding.flagged_sentences.map((sentence) => (
                  <li key={sentence}>{plainAnswer(sentence)}</li>
                ))}
              </ul>
            </details>
          ) : null}
        </div>
      ) : null}
      <div className="flex flex-wrap items-center gap-2">
        <GroundingBadge grounding={grounding} />
        {grounding.judge_unavailable ? (
          <span className="text-xs text-gray-500">Support check unavailable</span>
        ) : null}
        {answered ? (
          <span className="ml-auto flex gap-2">
            <Button
              variant="secondary"
              className="px-3 py-1 text-xs"
              onClick={() => void copy(plainAnswer(message.content), "Answer copied")}
            >
              Copy answer
            </Button>
            <Button
              variant="secondary"
              className="px-3 py-1 text-xs"
              onClick={() =>
                void copy(
                  answerWithCitations(plainAnswer(message.content), message.citations),
                  "Answer and sources copied",
                )
              }
            >
              Copy with citations
            </Button>
          </span>
        ) : null}
      </div>
    </div>
  );
}
