"use client";

import { useSetupCheck } from "@/hooks/use-setup";

const TASK_LABELS: Record<string, string> = {
  classify: "Classify",
  extract: "Extract",
  write: "Write",
  judge: "Judge",
};

export function TaskModels() {
  const { data } = useSetupCheck();

  if (!data) {
    return null;
  }

  const entries = Object.entries(data.task_models);

  if (entries.length === 0) {
    return null;
  }

  return (
    <section
      className="rounded-3xl border border-violet-100 bg-white/80 p-6 shadow-xl shadow-violet-100/60 backdrop-blur sm:p-8"
      aria-labelledby="task-models-heading"
    >
      <h2 id="task-models-heading" className="text-base font-bold tracking-tight text-gray-900">
        Models per task
      </h2>
      <p className="mt-1 text-xs text-gray-500">
        Override any of these with <code className="font-mono">LLM_MODEL_&lt;TASK&gt;</code> in{" "}
        <code className="font-mono">backend/.env</code>; blank uses{" "}
        <code className="font-mono">LLM_MODEL</code>.
      </p>
      <dl className="mt-4 grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
        {entries.map(([task, model]) => (
          <div key={task} className="contents">
            <dt className="font-semibold text-gray-900">{TASK_LABELS[task] ?? task}</dt>
            <dd className="font-mono text-gray-700">{model}</dd>
          </div>
        ))}
      </dl>
    </section>
  );
}
