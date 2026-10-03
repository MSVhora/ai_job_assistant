import { STEP_LABELS } from "./search-steps";

export function StepIndicator({ step }: { step: number }) {
  return (
    <ol aria-label="Steps" className="flex flex-wrap items-center gap-2 text-xs">
      {STEP_LABELS.map((label, index) => {
        const number = index + 1;
        const current = number === step;
        return (
          <li
            key={label}
            aria-current={current ? "step" : undefined}
            className={`flex items-center gap-1.5 rounded-full border px-3 py-1 font-semibold ${
              current
                ? "border-violet-400 bg-violet-50 text-violet-800"
                : number < step
                  ? "border-gray-200 bg-gray-50 text-gray-600"
                  : "border-dashed border-gray-200 text-gray-400"
            }`}
          >
            <span>{number}.</span>
            <span>{label}</span>
          </li>
        );
      })}
    </ol>
  );
}
