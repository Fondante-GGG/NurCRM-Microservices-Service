"use client";

import { useI18n } from "@/i18n/provider";
import { SECTIONS } from "@/lib/sections";

// Левая панель входа: одна мысль — вход один, программ четыре.
export function BrandPanel() {
  const { t } = useI18n();
  return (
    <aside className="flex flex-col justify-between bg-primary px-6 py-8 text-white lg:w-[46%] lg:px-14 lg:py-12">
      <div className="flex items-center gap-3"><span className="flex size-12 items-center justify-center rounded-[14px] bg-gold text-[22px] font-extrabold text-primary">N</span><span className="text-[22px] font-bold">{t.appName}</span></div>
      <div className="my-10 lg:my-0">
        <h1 className="max-w-[16ch] text-3xl font-extrabold leading-[1.05] tracking-tight sm:text-4xl lg:text-5xl">
          {t.login.title}
        </h1>
        <ul className="mt-8 grid max-w-md grid-cols-2 gap-x-6 gap-y-4">
          {SECTIONS.map((s) => (
            <li key={s} className="border-l-2 border-gold pl-3">
              <div className="font-semibold">{t.sections[s]}</div>
              <div className="text-sm text-white/70">{t.sectionHints[s]}</div>
            </li>
          ))}
        </ul>
      </div>
      <div className="hidden text-sm text-white/60 lg:block">nurcrm.kg</div>
    </aside>
  );
}
