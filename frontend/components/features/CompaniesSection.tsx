import { MatchShowcase } from "@/components/features/MatchShowcase";

const COMPANIES = [
  { name: "Spotify", dot: "bg-green-500" },
  { name: "Microsoft", dot: "bg-blue-500" },
  { name: "Meta", dot: "bg-sky-500" },
  { name: "SpaceX", dot: "bg-gray-800" },
  { name: "Deloitte", dot: "bg-emerald-600" },
  { name: "Stripe", dot: "bg-indigo-500" },
  { name: "Airbnb", dot: "bg-rose-500" },
  { name: "Notion", dot: "bg-gray-900" },
  { name: "Figma", dot: "bg-fuchsia-500" },
  { name: "Uber", dot: "bg-gray-900" },
  { name: "Shopify", dot: "bg-lime-600" },
  { name: "HubSpot", dot: "bg-orange-500" },
] as const;

const HIRES = [
  { company: "Tesla", role: "Firmware Engineer, Autopilot", dot: "bg-red-500", ago: "15 min ago" },
  { company: "Salesforce", role: "Lead Full-Stack Developer", dot: "bg-sky-500", ago: "18 min ago" },
  { company: "Airbnb", role: "Senior Data Scientist", dot: "bg-rose-500", ago: "22 min ago" },
  { company: "Uber", role: "Engineering Manager", dot: "bg-gray-800", ago: "25 min ago" },
  { company: "Stripe", role: "Staff Frontend Engineer", dot: "bg-indigo-500", ago: "31 min ago" },
  { company: "Notion", role: "Product Designer", dot: "bg-gray-900", ago: "38 min ago" },
] as const;

function LogoMarquee() {
  const doubled = [...COMPANIES, ...COMPANIES];
  return (
    <div className="marquee-mask overflow-hidden">
      <ul className="marquee-track flex w-max items-center gap-4">
        {doubled.map((company, i) => (
          <li
            key={`${company.name}-${i}`}
            className="flex items-center gap-2.5 rounded-2xl border border-gray-100 bg-white px-6 py-3.5 shadow-md shadow-violet-100/60"
          >
            <span className={`h-3 w-3 rounded-full ${company.dot}`} />
            <span className="text-base font-bold tracking-tight text-gray-800">{company.name}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function HiringTicker() {
  const doubled = [...HIRES, ...HIRES];
  return (
    <div className="marquee-mask overflow-hidden">
      <ul className="marquee-track-reverse flex w-max items-center gap-3">
        {doubled.map((hire, i) => (
          <li
            key={`${hire.company}-${i}`}
            className="flex items-center gap-2 rounded-full border border-gray-100 bg-white py-1.5 pl-1.5 pr-4 shadow-md shadow-violet-100/60"
          >
            <span
              className={`flex h-7 w-7 items-center justify-center rounded-full text-[10px] font-bold text-white ${hire.dot}`}
            >
              {hire.company.charAt(0)}
            </span>
            <span className="text-sm font-bold text-gray-900">{hire.company}</span>
            <span className="text-[10px] font-medium text-gray-400">{hire.ago}</span>
            <span className="text-xs font-semibold text-violet-700">{hire.role}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function CompaniesSection() {
  return (
    <section className="relative overflow-hidden bg-gradient-to-b from-transparent via-fuchsia-100/40 to-transparent py-20 text-gray-900">
      <div className="mx-auto max-w-6xl px-6">
        <p className="text-center text-sm font-medium text-gray-500">
          Get hired by top companies worldwide
        </p>
        <div className="mt-8">
          <LogoMarquee />
        </div>

        <MatchShowcase />

        <p className="mt-10 text-center text-sm font-semibold text-gray-700">
          Just hired — via AI-matched applications
        </p>
        <div className="mt-4">
          <HiringTicker />
        </div>
      </div>
    </section>
  );
}
