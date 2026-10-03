"use client";

import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Select } from "@/components/ui/select";
import { useEditAchievement } from "@/hooks/use-achievements";
import type { Achievement, AchievementUpdate } from "@/lib/api";
import { IMPACT_LABELS, parseSkills } from "@/lib/achievement-view";

const IMPACTS = Object.keys(IMPACT_LABELS) as NonNullable<AchievementUpdate["impact_type"]>[];

export function TagsEditor({ achievement }: { achievement: Achievement }) {
  const edit = useEditAchievement();
  const [skills, setSkills] = useState(achievement.skills.join(", "));
  const [impact, setImpact] = useState(achievement.impact_type);
  const [difficulty, setDifficulty] = useState(achievement.difficulty);

  const save = () => {
    const chosen = IMPACTS.find((candidate) => candidate === impact);
    edit.mutate(
      {
        id: achievement.id,
        payload: {
          skills: parseSkills(skills),
          difficulty,
          ...(chosen === undefined ? {} : { impact_type: chosen }),
        },
      },
      {
        onSuccess: () => {
          toast.success("Tags saved");
        },
      },
    );
  };

  return (
    <div className="flex flex-col gap-3">
      <Field label="Skills" htmlFor="achievement-skills" hint="Comma separated.">
        <Input
          id="achievement-skills"
          value={skills}
          onChange={(event) => {
            setSkills(event.target.value);
          }}
        />
      </Field>
      <div className="grid gap-3 sm:grid-cols-2">
        <Field label="Impact" htmlFor="achievement-impact">
          <Select
            id="achievement-impact"
            value={impact}
            onChange={(event) => {
              setImpact(event.target.value);
            }}
          >
            {IMPACTS.map((value) => (
              <option key={value} value={value}>
                {IMPACT_LABELS[value]}
              </option>
            ))}
          </Select>
        </Field>
        <Field label="Difficulty" htmlFor="achievement-difficulty">
          <Select
            id="achievement-difficulty"
            value={String(difficulty)}
            onChange={(event) => {
              setDifficulty(Number(event.target.value));
            }}
          >
            {[1, 2, 3, 4, 5].map((value) => (
              <option key={value} value={value}>
                {value} / 5
              </option>
            ))}
          </Select>
        </Field>
      </div>
      <div>
        <Button variant="secondary" disabled={edit.isPending} onClick={save}>
          Save tags
        </Button>
      </div>
    </div>
  );
}
