import { UploadIcon, KeyIcon } from "./icons";

export function JobSearchPreview() {
  return (
    <div className="mt-5 flex flex-col gap-2 rounded-2xl border border-gray-100 bg-gray-50/80 p-3">
      <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white p-2.5 shadow-sm">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-blue-100 text-[10px] font-bold text-blue-700">
          IBM
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-xs font-semibold text-gray-900">
            Software Engineer, IBM
          </span>
          <span className="block text-[11px] text-gray-500">Engineering</span>
        </span>
        <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700">
          Great fit
        </span>
      </div>
      <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white p-2.5 shadow-sm">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-emerald-100 text-[10px] font-bold text-emerald-700">
          MS
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-xs font-semibold text-gray-900">
            HR Manager, Microsoft
          </span>
          <span className="block text-[11px] text-gray-500">Operations</span>
        </span>
        <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
          Applied
        </span>
      </div>
    </div>
  );
}

export function UploadPreview() {
  return (
    <div className="mt-5 flex flex-col gap-2 rounded-2xl border border-gray-100 bg-gray-50/80 p-3">
      <div className="flex items-center gap-3 rounded-xl border border-dashed border-violet-300 bg-violet-50/60 p-2.5">
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-600">
          <UploadIcon />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate text-xs font-semibold text-gray-900">
            resume_2026.pdf
          </span>
          <span className="block text-[11px] text-gray-500">Drop or browse to upload</span>
        </span>
      </div>
      <div className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white p-2.5 shadow-sm">
        <span className="h-8 w-8 shrink-0 rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-400" />
        <span className="min-w-0 flex-1 space-y-1.5">
          <span className="block h-2 w-24 rounded-full bg-gray-200" />
          <span className="block h-2 w-16 rounded-full bg-gray-100" />
        </span>
        <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700">
          AI drafting…
        </span>
      </div>
    </div>
  );
}

export function ProfilePreview() {
  return (
    <div className="mt-5 rounded-2xl border border-gray-100 bg-gray-50/80 p-3">
      <div className="rounded-xl border border-gray-100 bg-white p-3 shadow-sm">
        <div className="flex items-center gap-2.5">
          <span className="h-8 w-8 rounded-full bg-gradient-to-br from-violet-400 to-fuchsia-400" />
          <span className="flex-1">
            <span className="block h-2 w-20 rounded-full bg-gray-300" />
            <span className="mt-1.5 block h-2 w-14 rounded-full bg-gray-200" />
          </span>
          <span className="rounded-full bg-violet-100 px-2 py-0.5 text-[10px] font-semibold text-violet-700">
            Reviewed
          </span>
        </div>
        <div className="mt-3 space-y-1.5">
          <span className="block h-2 w-full rounded-full bg-gray-100" />
          <span className="block h-2 w-5/6 rounded-full bg-gray-100" />
          <span className="block h-2 w-2/3 rounded-full bg-gray-100" />
        </div>
      </div>
    </div>
  );
}

export function SetupPreview() {
  return (
    <div className="mt-5 flex flex-col gap-2 rounded-2xl border border-gray-100 bg-gray-50/80 p-3">
      {["Gemini", "Adzuna", "Apify"].map((name) => (
        <div
          key={name}
          className="flex items-center gap-3 rounded-xl border border-gray-100 bg-white p-2.5 shadow-sm"
        >
          <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-violet-100 text-violet-600">
            <KeyIcon />
          </span>
          <span className="flex-1 text-xs font-semibold text-gray-900">{name} key</span>
          <span className="rounded-full bg-emerald-100 px-2 py-0.5 text-[10px] font-semibold text-emerald-700">
            Active
          </span>
        </div>
      ))}
    </div>
  );
}

export function BarsPreview() {
  return (
    <div className="mt-5 rounded-2xl border border-gray-100 bg-white/60 p-3">
      <div className="rounded-xl border border-gray-100 bg-gray-50 p-3">
        <div className="flex items-center gap-2.5">
          <span className="h-8 w-8 rounded-lg bg-gray-200" />
          <span className="flex-1 space-y-1.5">
            <span className="block h-2 w-24 rounded-full bg-gray-200" />
            <span className="block h-2 w-16 rounded-full bg-gray-200/70" />
          </span>
        </div>
        <div className="mt-3 space-y-1.5">
          <span className="block h-2 w-full rounded-full bg-gray-200/70" />
          <span className="block h-2 w-4/5 rounded-full bg-gray-200/70" />
        </div>
      </div>
    </div>
  );
}
