"use client";

const PERCENT_STEP = 5;

export function PrioritySlider({
  value,
  onChange,
  disabled = false,
}: {
  value: number;
  onChange: (priority: number) => void;
  disabled?: boolean;
}) {
  const percent = Math.min(100, Math.max(0, Math.round(value * 100)));
  const valueText = `${percent}% role fit / ${100 - percent}% company fit`;
  return (
    <div className="flex flex-col gap-1">
      <label htmlFor="match-priority" className="text-xs font-medium text-gray-700 dark:text-gray-300">
        Priority — role fit vs company fit
      </label>
      <input
        id="match-priority"
        type="range"
        min={0}
        max={100}
        step={PERCENT_STEP}
        value={percent}
        disabled={disabled}
        aria-valuetext={valueText}
        onChange={(event) => onChange(Number(event.target.value) / 100)}
        className="w-64 accent-blue-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-blue-600 disabled:opacity-50 dark:accent-blue-400"
      />
      <p aria-live="polite" className="text-xs text-gray-500 dark:text-gray-400">
        {valueText}
        {disabled ? " (loading profile…)" : ""}
      </p>
    </div>
  );
}
