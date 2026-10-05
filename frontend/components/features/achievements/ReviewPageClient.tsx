"use client";

import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useAchievementGroups } from "@/hooks/use-achievements";
import type { Achievement } from "@/lib/api";

import { AchievementDrawer } from "./AchievementDrawer";
import { AchievementList } from "./AchievementList";
import { BulkApproveModal } from "./BulkApproveModal";
import { EmployerFilter } from "./EmployerFilter";
import { ImpactFilters } from "./ImpactFilters";
import { MergeDialog, type MergeCandidate } from "./MergeDialog";
import { MergeProposals } from "./MergeProposals";
import { employerRepositories } from "@/lib/draft-groups";
import { RepositoryFilter } from "./RepositoryFilter";
import { ReviewTabs } from "./ReviewTabs";
import { ViewActions } from "./ViewActions";
import { TAB_HINTS, type MetricFilter, type ReviewTab } from "./review-tabs";

export function ReviewPageClient() {
  const [tab, setTab] = useState<ReviewTab>("draft");
  const [privateOnly, setPrivateOnly] = useState(false);
  const [repository, setRepository] = useState("");
  const [employer, setEmployer] = useState("");
  const [impact, setImpact] = useState("");
  const [metric, setMetric] = useState<MetricFilter>("");
  const groups = useAchievementGroups(tab === "draft").data?.groups ?? [];
  const [offset, setOffset] = useState(0);
  const [selected, setSelected] = useState<ReadonlyMap<string, string>>(new Map());
  const [openId, setOpenId] = useState<string | null>(null);
  const [bulkOpen, setBulkOpen] = useState(false);
  const [mergePair, setMergePair] = useState<MergeCandidate[]>([]);

  const toggle = (achievement: Achievement, value: boolean) => {
    setSelected((current) => {
      const next = new Map(current);
      if (value) next.set(achievement.id, achievement.title);
      else next.delete(achievement.id);
      return next;
    });
  };

  const changeTab = (next: ReviewTab) => {
    setTab(next);
    setEmployer("");
    setOffset(0);
    setSelected(new Map());
  };

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <ReviewTabs active={tab} onChange={changeTab} />
        <Link href="/evidence" className="text-sm font-semibold text-violet-700 underline">
          Back to evidence
        </Link>
      </div>
      <p className="text-sm text-gray-600">{TAB_HINTS[tab]}</p>
      <div className="flex flex-wrap items-center gap-3">
        <label className="flex items-center gap-2 text-sm text-gray-700">
          <input
            type="checkbox"
            checked={privateOnly}
            onChange={(event) => {
              setPrivateOnly(event.target.checked);
              setOffset(0);
            }}
            className="h-4 w-4 rounded border-gray-300 text-violet-600"
          />
          Private-derived only
        </label>
        {tab === "draft" && (
          <Button
            variant="secondary"
            onClick={() => {
              setBulkOpen(true);
            }}
          >
            Approve all fully-evidenced…
          </Button>
        )}
        {selected.size >= 2 && (
          <Button
            onClick={() => {
              setMergePair([...selected].map(([id, title]) => ({ id, title })));
            }}
          >
            Merge {selected.size} selected
          </Button>
        )}
      </div>
      {tab === "draft" && (
        <EmployerFilter
          groups={groups}
          value={employer}
          onChange={(next) => {
            setEmployer(next);
            const allowed = employerRepositories(groups, next);
            if (allowed !== undefined && !allowed.has(repository)) setRepository("");
            setOffset(0);
            setSelected(new Map());
          }}
        />
      )}
      <RepositoryFilter
        value={repository}
        allowed={tab === "draft" ? employerRepositories(groups, employer) : undefined}
        onChange={(next) => {
          setRepository(next);
          setOffset(0);
          setSelected(new Map());
        }}
      />
      <ImpactFilters
        impact={impact}
        metric={metric}
        onImpact={(next) => {
          setImpact(next);
          setOffset(0);
        }}
        onMetric={(next) => {
          setMetric(next);
          setOffset(0);
        }}
      />
      {tab === "draft" && (
        <ViewActions groups={groups} employer={employer} repository={repository} />
      )}
      {tab === "draft" && <MergeProposals onMerge={setMergePair} />}
      <AchievementList
        tab={tab}
        filters={{ privateOnly, repository, employer, impact, metric }}
        offset={offset}
        selected={selected}
        onSelect={toggle}
        onOpen={setOpenId}
        onPage={setOffset}
      />
      <AchievementDrawer
        achievementId={openId}
        onClose={() => {
          setOpenId(null);
        }}
        onOpen={setOpenId}
      />
      {bulkOpen && (
        <BulkApproveModal
          open
          onClose={() => {
            setBulkOpen(false);
          }}
        />
      )}
      <MergeDialog
        key={mergePair.map((candidate) => candidate.id).join(",")}
        candidates={mergePair}
        onClose={() => {
          setMergePair([]);
        }}
        onMerged={(id) => {
          setMergePair([]);
          setSelected(new Map());
          setOpenId(id);
        }}
      />
    </div>
  );
}
