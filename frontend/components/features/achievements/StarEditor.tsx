"use client";

import { useState, type SyntheticEvent } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { useEditAchievement } from "@/hooks/use-achievements";
import type { Achievement } from "@/lib/api";

const STAR_FIELDS = [
  { key: "situation", label: "Situation" },
  { key: "task", label: "Task" },
  { key: "action", label: "Action" },
  { key: "result", label: "Result" },
] as const;

export function StarEditor({ achievement }: { achievement: Achievement }) {
  const edit = useEditAchievement();
  const [title, setTitle] = useState(achievement.title);
  const [star, setStar] = useState({
    situation: achievement.situation ?? "",
    task: achievement.task ?? "",
    action: achievement.action ?? "",
    result: achievement.result ?? "",
  });

  const save = (event: SyntheticEvent) => {
    event.preventDefault();
    edit.mutate(
      {
        id: achievement.id,
        payload: {
          title: title.trim(),
          situation: star.situation,
          task: star.task,
          action: star.action,
          result: star.result.trim() === "" ? null : star.result,
        },
      },
      {
        onSuccess: () => {
          toast.success("Saved");
        },
      },
    );
  };

  return (
    <form onSubmit={save} className="flex flex-col gap-3" aria-label="Edit achievement">
      <Field label="Title" htmlFor="achievement-title">
        <Input
          id="achievement-title"
          value={title}
          maxLength={200}
          onChange={(event) => {
            setTitle(event.target.value);
          }}
        />
      </Field>
      {STAR_FIELDS.map((field) => (
        <Field
          key={field.key}
          label={field.label}
          htmlFor={`achievement-${field.key}`}
          hint={
            field.key === "result" && star.result.trim() === ""
              ? "No outcome is stated in the evidence. Leave this empty rather than guess."
              : undefined
          }
        >
          <Textarea
            id={`achievement-${field.key}`}
            rows={3}
            value={star[field.key]}
            onChange={(event) => {
              setStar((current) => ({ ...current, [field.key]: event.target.value }));
            }}
          />
        </Field>
      ))}
      <div>
        <Button type="submit" disabled={edit.isPending || title.trim() === ""}>
          Save changes
        </Button>
      </div>
    </form>
  );
}
