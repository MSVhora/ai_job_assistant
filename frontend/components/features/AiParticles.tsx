const PARTICLES = [
  "left-[3%] h-2.5 w-2.5 bg-violet-500/80 [--peak-opacity:0.9] [--drift-x:28px] [--dur:19s] [animation-delay:0s]",
  "left-[8%] h-2 w-2 bg-fuchsia-500/70 [--peak-opacity:0.8] [--drift-x:-18px] [--dur:24s] [animation-delay:6s]",
  "left-[14%] h-3 w-3 bg-purple-500/60 [--peak-opacity:0.7] [--drift-x:34px] [--dur:28s] [animation-delay:2s]",
  "left-[21%] h-2 w-2 bg-violet-500/70 [--peak-opacity:0.8] [--drift-x:-26px] [--dur:17s] [animation-delay:9s]",
  "left-[27%] h-2.5 w-2.5 bg-sky-400/70 [--peak-opacity:0.8] [--drift-x:22px] [--dur:26s] [animation-delay:4s]",
  "left-[34%] h-2 w-2 bg-fuchsia-500/80 [--peak-opacity:0.9] [--drift-x:-14px] [--dur:21s] [animation-delay:11s]",
  "left-[41%] h-3.5 w-3.5 bg-violet-400/70 [--peak-opacity:0.8] [--drift-x:30px] [--dur:30s] [animation-delay:1s]",
  "left-[48%] h-2.5 w-2.5 bg-rose-400/70 [--peak-opacity:0.8] [--drift-x:-30px] [--dur:23s] [animation-delay:7s]",
  "left-[55%] h-2 w-2 bg-purple-500/70 [--peak-opacity:0.8] [--drift-x:20px] [--dur:18s] [animation-delay:12s]",
  "left-[62%] h-2.5 w-2.5 bg-fuchsia-400/70 [--peak-opacity:0.8] [--drift-x:-24px] [--dur:27s] [animation-delay:3s]",
  "left-[69%] h-3.5 w-3.5 bg-violet-500/60 [--peak-opacity:0.7] [--drift-x:26px] [--dur:22s] [animation-delay:10s]",
  "left-[76%] h-2 w-2 bg-sky-400/70 [--peak-opacity:0.8] [--drift-x:-20px] [--dur:20s] [animation-delay:5s]",
  "left-[83%] h-2.5 w-2.5 bg-purple-400/70 [--peak-opacity:0.8] [--drift-x:32px] [--dur:25s] [animation-delay:8s]",
  "left-[90%] h-2 w-2 bg-fuchsia-500/70 [--peak-opacity:0.8] [--drift-x:-16px] [--dur:29s] [animation-delay:2.5s]",
  "left-[95%] h-3 w-3 bg-violet-500/70 [--peak-opacity:0.8] [--drift-x:24px] [--dur:18.5s] [animation-delay:13s]",
] as const;

const TWINKLES = [
  "left-[10%] top-[16%] h-5 w-5 text-violet-500 [--dur:5s] [animation-delay:0.5s]",
  "left-[86%] top-[12%] h-4 w-4 text-fuchsia-500 [--dur:6s] [animation-delay:2s]",
  "left-[70%] top-[38%] h-4.5 w-4.5 text-purple-500 [--dur:7s] [animation-delay:1.2s]",
  "left-[22%] top-[52%] h-4 w-4 text-fuchsia-400 [--dur:5.5s] [animation-delay:3s]",
  "left-[92%] top-[58%] h-5 w-5 text-violet-400 [--dur:6.5s] [animation-delay:1.8s]",
  "left-[5%] top-[74%] h-4 w-4 text-purple-400 [--dur:7.5s] [animation-delay:2.6s]",
] as const;

function Sparkle({ className }: { className: string }) {
  return (
    <svg viewBox="0 0 20 20" fill="currentColor" aria-hidden="true" className={className}>
      <path d="M10 1.5l1.8 4.7 4.7 1.8-4.7 1.8L10 14.5 8.2 9.8 3.5 8l4.7-1.8L10 1.5zM15.5 13l.9 2.3 2.3.9-2.3.9-.9 2.3-.9-2.3-2.3-.9 2.3-.9.9-2.3z" />
    </svg>
  );
}

export function AiParticles() {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 -z-10 overflow-hidden"
    >
      {TWINKLES.map((className) => (
        <Sparkle key={className} className={`ai-twinkle absolute opacity-0 ${className}`} />
      ))}
      {PARTICLES.map((className) => (
        <span
          key={className}
          className={`ai-particle absolute top-full rounded-full shadow-[0_0_12px_2px_currentColor] ${className}`}
        />
      ))}
    </div>
  );
}
