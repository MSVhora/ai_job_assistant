"use client";

import { Card } from "@/components/ui/card";
import type { ResumeDocument } from "@/lib/api";
import type { ResumeBlock } from "@/lib/resume-view";

import { ReviewBlock } from "./ReviewBlock";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h3 className="border-b border-gray-200 pb-1 text-sm font-bold tracking-wide text-gray-500 uppercase">
        {title}
      </h3>
      {children}
    </section>
  );
}

function Lines({ lines }: { lines: string[] }) {
  return (
    <ul className="flex flex-col gap-1 text-sm text-gray-800 select-text">
      {lines.map((line) => (
        <li key={line}>{line}</li>
      ))}
    </ul>
  );
}

export function ReviewSections({ document }: { document: ResumeDocument }) {
  const { content, layout } = document;
  const included = new Set(layout.included_ids);
  const withContent = (blocks: ResumeBlock[]) =>
    blocks.filter((block) => block.highlights.some((bullet) => included.has(bullet.id)));
  const renderBlocks = (blocks: ResumeBlock[]) =>
    withContent(blocks).map((block) => (
      <ReviewBlock
        key={block.id}
        documentId={document.id}
        block={block}
        included={included}
        comments={document.comments}
      />
    ));
  const jobs = withContent(content.work);
  const projects = withContent(content.projects);

  return (
    <Card title={<h2 className="text-lg font-semibold text-gray-900">Review your resume</h2>}>
      <section aria-label="Resume content" className="flex flex-col gap-6">
        <div>
          <p className="text-base font-semibold text-gray-900 select-text">
            {content.basics.full_name}
          </p>
          <p className="text-xs text-gray-500 select-text">
            {[content.basics.email, content.basics.phone, content.basics.location]
              .filter(Boolean)
              .join(" · ")}
          </p>
        </div>
        {content.basics.summary ? (
          <Section title="Summary">
            <p className="text-sm text-gray-800 select-text">{content.basics.summary}</p>
          </Section>
        ) : null}
        {jobs.length > 0 && <Section title="Experience">{renderBlocks(content.work)}</Section>}
        {projects.length > 0 && (
          <Section title="Projects">{renderBlocks(content.projects)}</Section>
        )}
        {content.skills.length > 0 && (
          <Section title="Skills">
            <p className="text-sm text-gray-800 select-text">{content.skills.join(", ")}</p>
          </Section>
        )}
        {content.education.length > 0 && (
          <Section title="Education">
            <Lines
              lines={content.education.map((item) =>
                [item.degree, item.field, item.institution].filter(Boolean).join(", "),
              )}
            />
          </Section>
        )}
        {content.certificates.length > 0 && (
          <Section title="Certifications">
            <Lines lines={content.certificates.map((item) => item.name)} />
          </Section>
        )}
        {content.awards.length > 0 && (
          <Section title="Awards">
            <Lines lines={content.awards.map((item) => item.title)} />
          </Section>
        )}
        {content.extra_sections.map((extra) => (
          <Section key={extra.title} title={extra.title}>
            <Lines lines={extra.entries} />
          </Section>
        ))}
      </section>
    </Card>
  );
}
