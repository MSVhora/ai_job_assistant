"use client";

import type { ResumeComment } from "@/lib/api";
import { blockTitle, blockToText, commentsFor, type ResumeBlock } from "@/lib/resume-view";

import { BulletRow } from "./BulletRow";
import { CommentBox } from "./CommentBox";
import { CopyButton } from "./CopyButton";

function subtitle(block: ResumeBlock): string {
  if ("name" in block) return [block.role, block.url].filter(Boolean).join(" · ");
  const finish = block.is_current && !block.end_date ? "Present" : block.end_date;
  const when = [block.start_date, finish].filter(Boolean).join(" - ");
  return [block.location, when].filter(Boolean).join(" · ");
}

export function ReviewBlock({
  documentId,
  block,
  included,
  comments,
}: {
  documentId: string;
  block: ResumeBlock;
  included: ReadonlySet<string>;
  comments: ResumeComment[];
}) {
  const section = "name" in block ? "projects" : "work";
  const bullets = block.highlights.filter((bullet) => included.has(bullet.id));

  return (
    <article className="flex flex-col gap-2" aria-label={blockTitle(block)}>
      <header className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h4 className="text-sm font-semibold text-gray-900">{blockTitle(block)}</h4>
          <p className="text-xs text-gray-500">{subtitle(block)}</p>
        </div>
        <div className="flex">
          <CopyButton
            label="Copy text"
            ariaLabel={`Copy ${blockTitle(block)} as plain text`}
            getText={() => blockToText(block, included, "text")}
          />
          <CopyButton
            label="Copy Markdown"
            ariaLabel={`Copy ${blockTitle(block)} as Markdown`}
            getText={() => blockToText(block, included, "markdown")}
          />
        </div>
      </header>
      <ul className="flex flex-col gap-2">
        {bullets.map((bullet) => (
          <BulletRow
            key={bullet.id}
            documentId={documentId}
            section={section}
            blockId={block.id}
            bullet={bullet}
            comments={commentsFor(comments, block.id, bullet.id)}
          />
        ))}
      </ul>
      <CommentBox
        documentId={documentId}
        target={{ section, block_id: block.id }}
        comments={commentsFor(comments, block.id, null)}
        noun="section"
      />
    </article>
  );
}
