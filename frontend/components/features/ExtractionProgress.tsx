import { CheckIcon } from "./upload-icons";

const STAGES = [
  { label: "Uploading resume", end: 35 },
  { label: "Reading your resume", end: 60 },
  { label: "Drafting your profile with AI", end: 90 },
  { label: "Almost done", end: 100 },
] as const;

export function ExtractionProgress({ progress }: { progress: number }) {
  const stageIndex = STAGES.findIndex((stage) => progress < stage.end);
  const currentStage = STAGES[stageIndex === -1 ? STAGES.length - 1 : stageIndex] ?? STAGES[0];

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col gap-2 rounded-2xl border border-violet-100 bg-white p-4 shadow-sm"
    >
      <div className="flex items-center justify-between text-sm">
        <span className="font-semibold text-gray-900">{currentStage.label}…</span>
        <span className="font-semibold text-violet-700">{progress}%</span>
      </div>
      <div
        className="h-2.5 w-full overflow-hidden rounded-full bg-violet-100"
        role="progressbar"
        aria-valuenow={progress}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label="Extraction progress"
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-violet-500 to-fuchsia-500 transition-all duration-300 ease-out"
          style={{ width: `${progress}%` }}
        />
      </div>
      <ol className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs">
        {STAGES.map((stage, index) => {
          const done = progress >= stage.end;
          const active = index === stageIndex;
          return (
            <li
              key={stage.label}
              className={`flex items-center gap-1 ${
                done
                  ? "text-emerald-600"
                  : active
                    ? "font-semibold text-violet-700"
                    : "text-gray-400"
              }`}
            >
              {done ? <CheckIcon /> : <span aria-hidden>{index + 1}.</span>}
              {stage.label}
            </li>
          );
        })}
      </ol>
    </div>
  );
}
