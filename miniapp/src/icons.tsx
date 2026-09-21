// Navigation icons (SF-Symbols-inspired line set, slightly bold) — currentColor.
import { SVGProps } from "react";

type P = SVGProps<SVGSVGElement>;
const base = {
  viewBox: "0 0 24 24",
  fill: "none",
  stroke: "currentColor",
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
};

export function IconOverview(p: P) {
  return (
    <svg {...base} strokeWidth={1.9} {...p}>
      <path d="M4.5 19.5V11M9.5 19.5V5.5M14.5 19.5v-6M19.5 19.5v-10" />
    </svg>
  );
}
export function IconClients(p: P) {
  return (
    <svg {...base} strokeWidth={1.8} {...p}>
      <circle cx="9" cy="8" r="3.2" />
      <path d="M3.4 19a5.6 5.6 0 0 1 11.2 0" />
      <path d="M16.4 5.6a3.1 3.1 0 0 1 0 5.6M18 19a5.5 5.5 0 0 0-2.6-4.7" />
    </svg>
  );
}
export function IconPlans(p: P) {
  return (
    <svg {...base} strokeWidth={1.8} {...p}>
      <path d="M4 8.6A1.6 1.6 0 0 1 5.6 7h12.8A1.6 1.6 0 0 1 20 8.6v1.9a1.8 1.8 0 0 0 0 3.4v1.5A1.6 1.6 0 0 1 18.4 17H5.6A1.6 1.6 0 0 1 4 15.4v-1.5a1.8 1.8 0 0 0 0-3.4z" />
      <path d="M12 7.6v8.8" strokeDasharray="1.4 1.9" />
    </svg>
  );
}
export function IconVisits(p: P) {
  return (
    <svg {...base} strokeWidth={1.9} {...p}>
      <circle cx="12" cy="12" r="8.5" />
      <path d="M8.3 12.2l2.5 2.5 4.7-5" />
    </svg>
  );
}
export function IconFinance(p: P) {
  return (
    <svg {...base} strokeWidth={1.8} {...p}>
      <rect x="3" y="6.3" width="18" height="11.4" rx="2.6" />
      <circle cx="12" cy="12" r="2.5" />
      <path d="M6.4 9.5h.01M17.6 14.5h.01" />
    </svg>
  );
}
export function IconSettings(p: P) {
  return (
    <svg {...base} strokeWidth={1.7} {...p}>
      <circle cx="12" cy="12" r="3.2" />
      <path d="M12 3v2.4M12 18.6V21M3 12h2.4M18.6 12H21M5.6 5.6l1.7 1.7M16.7 16.7l1.7 1.7M18.4 5.6l-1.7 1.7M7.3 16.7l-1.7 1.7" />
    </svg>
  );
}
export function IconPlatform(p: P) {
  return (
    <svg {...base} strokeWidth={1.8} {...p}>
      <path d="M12 3l7 3.5v5c0 4.2-2.9 6.7-7 8-4.1-1.3-7-3.8-7-8v-5z" />
      <path d="M9.3 12.2l1.9 1.9 3.6-3.8" />
    </svg>
  );
}
export function IconSun(p: P) {
  return (
    <svg {...base} strokeWidth={1.8} {...p}>
      <circle cx="12" cy="12" r="4" />
      <path d="M12 2.5v2.2M12 19.3v2.2M2.5 12h2.2M19.3 12h2.2M5.1 5.1l1.6 1.6M17.3 17.3l1.6 1.6M18.9 5.1l-1.6 1.6M6.7 17.3l-1.6 1.6" />
    </svg>
  );
}
export function IconMoon(p: P) {
  return (
    <svg {...base} strokeWidth={1.8} {...p}>
      <path d="M20 13.5A7.5 7.5 0 1 1 10.5 4a6 6 0 0 0 9.5 9.5z" />
    </svg>
  );
}
export function IconPlus(p: P) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2} strokeLinecap="round" {...p}>
      <path d="M12 5v14M5 12h14" />
    </svg>
  );
}
