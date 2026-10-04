import type {
  NotIncluded,
  ResumeBullet,
  ResumeComment,
  ResumeDocument,
  ResumeProjectEntry,
  ResumeWorkEntry,
} from "@/lib/api";

export type ResumeBlock = ResumeWorkEntry | ResumeProjectEntry;
export type CopyFormat = "text" | "markdown";

export const REASON_LABELS: Record<NotIncluded["reason"], string> = {
  did_not_fit: "Did not fit",
  needs_review: "Needs review",
  overlap_omitted: "Overlapping role omitted",
  not_written: "Not written yet",
};

export interface NotIncludedRow {
  id: string;
  kind: "bullet" | "achievement";
  reason: NotIncluded["reason"];
  priority: number;
  label: string;
  context: string;
  flags: string[];
}

export function blockTitle(block: ResumeBlock): string {
  if ("name" in block) return block.name;
  return [block.title, block.company].filter(Boolean).join(" at ") || "Role";
}

export function blocksOf(document: ResumeDocument): ResumeBlock[] {
  return [...document.content.work, ...document.content.projects];
}

function findBullet(
  document: ResumeDocument,
  bulletId: string,
): { block: ResumeBlock; bullet: ResumeBullet } | undefined {
  for (const block of blocksOf(document)) {
    const bullet = block.highlights.find((item) => item.id === bulletId);
    if (bullet !== undefined) return { block, bullet };
  }
  return undefined;
}

/** Everything the fit left out except overlapping roles, which have their own card. */
export function notIncludedRows(document: ResumeDocument): NotIncludedRow[] {
  const rows: NotIncludedRow[] = [];
  for (const item of document.layout.not_included) {
    if (item.reason === "overlap_omitted") continue;
    if (item.reason === "not_written") {
      const entry = document.generation.pool.find((pool) => pool.achievement_id === item.id);
      rows.push({
        id: item.id,
        kind: "achievement",
        reason: item.reason,
        priority: item.priority,
        label: entry?.title ?? "An approved achievement",
        context: "",
        flags: [],
      });
      continue;
    }
    const found = findBullet(document, item.id);
    if (found === undefined) continue;
    rows.push({
      id: item.id,
      kind: "bullet",
      reason: item.reason,
      priority: item.priority,
      label: found.bullet.text,
      context: blockTitle(found.block),
      flags: found.bullet.flags,
    });
  }
  return rows;
}

export function availableCount(rows: NotIncludedRow[]): number {
  return rows.filter((row) => row.reason === "did_not_fit" || row.reason === "not_written").length;
}

export function pageUsageLine(document: ResumeDocument, available: number): string {
  const { pages } = document.layout;
  const target = document.page_target;
  if (pages === null || pages === undefined) {
    return `Nothing fits ${String(target)} page${target === 1 ? "" : "s"} yet — see the notes below.`;
  }
  const used = `${String(pages)} of ${String(target)} page${target === 1 ? "" : "s"}`;
  if (document.layout.short_on_evidence) {
    return `${used} — everything available is included; add evidence to fill more.`;
  }
  return available > 0 ? `${used} — ${String(available)} more achievements available.` : used;
}

function dates(block: ResumeBlock): string {
  const finish = "is_current" in block && block.is_current ? "Present" : block.end_date;
  return [block.start_date, finish].filter(Boolean).join(" - ");
}

/** Plain text or Markdown for one block's included bullets, as it would be pasted elsewhere. */
export function blockToText(
  block: ResumeBlock,
  included: ReadonlySet<string>,
  format: CopyFormat,
): string {
  const bullets = block.highlights.filter((bullet) => included.has(bullet.id));
  const heading = format === "markdown" ? `### ${blockTitle(block)}` : blockTitle(block);
  const when = dates(block);
  return [heading, ...(when ? [when] : []), ...bullets.map((bullet) => `- ${bullet.text}`)].join(
    "\n",
  );
}

export function commentsFor(
  comments: ResumeComment[],
  blockId: string,
  bulletId: string | null,
): ResumeComment[] {
  return comments.filter(
    (comment) =>
      comment.target.block_id === blockId && (comment.target.bullet_id ?? null) === bulletId,
  );
}

export function resumeBuilderHref(profileId: string | null, matchId?: string): string {
  const query = new URLSearchParams();
  if (profileId !== null) query.set("profile", profileId);
  if (matchId !== undefined) query.set("match", matchId);
  const suffix = query.size > 0 ? `?${query.toString()}` : "";
  return `/resume-builder${suffix}`;
}
