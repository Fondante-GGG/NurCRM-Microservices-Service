"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { translations, type Lang } from "./translations";

const KEY = "nurcrm_lang";

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: (typeof translations)["ru"] };

const I18nContext = createContext<Ctx | null>(null);

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("ru");

  useEffect(() => {
    try {
      const saved = localStorage.getItem(KEY);
      if (saved === "ru" || saved === "ky") setLangState(saved);
    } catch {}
  }, []);

  const setLang = (l: Lang) => {
    setLangState(l);
    try {
      localStorage.setItem(KEY, l);
    } catch {}
  };

  return <I18nContext value={{ lang, setLang, t: translations[lang] }}>{children}</I18nContext>;
}

export function useI18n(): Ctx {
  const ctx = useContext(I18nContext);
  if (!ctx) throw new Error("useI18n must be used inside I18nProvider");
  return ctx;
}
