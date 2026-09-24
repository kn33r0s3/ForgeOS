"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useState } from "react";

const links = [
  { href: "/", label: "Overview" },
  { href: "/analyze", label: "Analyze" },
  { href: "/opportunities", label: "Opportunities" },
  { href: "/world", label: "World" },
  { href: "/network", label: "Network" },
  { href: "/actions", label: "Actions" },
  { href: "/research", label: "Research" },
  { href: "/outcomes", label: "Outcomes" },
  { href: "/runtime", label: "Runtime" },
  { href: "/flow", label: "System flow" },
  { href: "/products", label: "Products" },
  { href: "/execution", label: "Execution" },
  { href: "/revenue", label: "Revenue" },
  { href: "/repair-shop", label: "Repair shop" },
  { href: "/knowledge", label: "Knowledge" },
  { href: "/earn", label: "Earn" },
];

export default function Nav() {
  const pathname = usePathname();
  const [open, setOpen] = useState(false);
  return <nav className="sticky top-0 z-30 border-b border-white/[0.08] bg-[#08090b]/80 backdrop-blur-2xl">
    <div className="mx-auto flex h-[4.5rem] max-w-7xl items-center justify-between px-5 sm:px-6">
      <Link href="/" className="flex items-center gap-3" onClick={() => setOpen(false)}><span className="flex h-9 w-9 items-center justify-center rounded-xl bg-white text-sm font-bold text-black shadow-[0_0_25px_-8px_rgba(168,139,255,.9)]">F</span><span><span className="block font-display text-sm font-bold tracking-[-.03em] text-white">FORGE<span className="text-forge-accent2">OS</span></span><span className="hidden text-[9px] uppercase tracking-[.16em] text-neutral-600 sm:block">Intelligence, made legible</span></span></Link>
      <button className="rounded-full border border-white/[0.1] px-3 py-2 text-xs text-neutral-400 md:hidden" onClick={() => setOpen(!open)}>{open ? "Close" : "Menu"}</button>
      <div className={`${open ? "absolute left-4 right-4 top-[4.8rem] flex" : "hidden"} flex-col gap-1 rounded-2xl border border-white/[0.1] bg-[#101216] p-2 shadow-2xl md:static md:flex md:flex-row md:items-center md:gap-1 md:border-0 md:bg-transparent md:p-0 md:shadow-none`}>
        {links.map((link) => { const active = pathname === link.href; return <Link key={link.href} href={link.href} onClick={() => setOpen(false)} className={`rounded-full px-4 py-2 text-xs font-medium transition ${active ? "bg-white text-black" : "text-neutral-500 hover:bg-white/[0.07] hover:text-white"}`}>{link.label}</Link>; })}
      </div>
    </div>
  </nav>;
}
