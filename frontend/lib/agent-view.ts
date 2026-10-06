import type { AgentCitation } from "@/lib/api";

const MARKER = /\[(A\d+|E\d+|P|J)\]/g;

export type AnswerSegment = { kind: "text"; text: string } | { kind: "marker"; marker: string };

export function splitAnswer(content: string): AnswerSegment[] {
  const segments: AnswerSegment[] = [];
  let last = 0;
  for (const match of content.matchAll(MARKER)) {
    if (match.index > last) segments.push({ kind: "text", text: content.slice(last, match.index) });
    segments.push({ kind: "marker", marker: match[1] ?? "" });
    last = match.index + match[0].length;
  }
  if (last < content.length) segments.push({ kind: "text", text: content.slice(last) });
  return segments;
}

export function plainAnswer(content: string): string {
  return content
    .replace(MARKER, "")
    .replace(/[ \t]+([.,;:!?])/g, "$1")
    .replace(/[ \t]{2,}/g, " ")
    .trim();
}

export function answerWithCitations(content: string, citations: AgentCitation[]): string {
  const sources = citations.map((citation, index) => {
    const quote = citation.quote && citation.quote !== citation.label ? `: ${citation.quote}` : "";
    const link = citation.url ? ` (${citation.url})` : "";
    return `${String(index + 1)}. ${citation.label}${quote}${link}`;
  });
  return sources.length === 0 ? content : `${content}\n\nSources:\n${sources.join("\n")}`;
}

export interface Starter {
  label: string;
  question: string;
}

export const STARTERS: Starter[] = [
  { label: "Tell me about yourself", question: "Tell me about yourself." },
  { label: "What have I built with Python?", question: "What have I built with Python?" },
  { label: "Summarise my last two years", question: "Summarise my last two years of work." },
];

export const KIND_LABELS: Record<AgentCitation["kind"], string> = {
  achievement: "Achievement",
  evidence: "Evidence",
  profile: "Your profile",
  job: "The job",
};

export function noteDraftFor(question: string): { title: string; body: string } {
  return { title: question.slice(0, 120), body: "" };
}
