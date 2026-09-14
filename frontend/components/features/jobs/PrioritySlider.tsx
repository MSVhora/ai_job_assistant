"use client";

const PERCENT_STEP = 5;

export function PrioritySlider({
  value,
  onChange,
  disabled = false,
  id = "match-priority",
}: {
  value: number;
  onChange: (priority: number) => void;
  disabled?: boolean;
  id?: string;
}) {
  const percent = Math.min(100, Math.max(0, Math.round(value * 100)));
  const valueText = `${percent}% role fit / ${100 - percent}% company fit`;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={id} className="text-xs font-medium text-gray-600">
        Priority — role fit vs company fit
      </label>
      <input
        id={id}
        type="range"
        min={0}
        max={100}
        step={PERCENT_STEP}
        value={percent}
        disabled={disabled}
        aria-valuetext={valueText}
        onChange={(event) => onChange(Number(event.target.value) / 100)}
        className="w-full max-w-md accent-violet-600 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-violet-600 disabled:opacity-50"
      />
      <p aria-live="polite" className="text-xs text-gray-500">
        {valueText}
        {disabled ? " (loading profile…)" : ""}
      </p>
    </div>
  );
}
