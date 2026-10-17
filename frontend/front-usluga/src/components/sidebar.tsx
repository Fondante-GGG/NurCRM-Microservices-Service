"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { useI18n } from "@/i18n/provider";
import { MENU } from "@/lib/menu";
import { useStore } from "@/data/store";
import type { SectionSlug } from "@/lib/sections";
import { Icon } from "./icon";

const KEY = "nurcrm_sidebar";

export function useSidebarCollapsed() {
  const [collapsed, setCollapsed] = useState(false);
  useEffect(() => {
    try {
      setCollapsed(localStorage.getItem(KEY) === "1");
    } catch {}
  }, []);
  const toggle = () => {
    setCollapsed((c) => {
      try {
        localStorage.setItem(KEY, c ? "0" : "1");
      } catch {}
      return !c;
    });
  };
  return { collapsed, toggle };
}

// Список пунктов: один и тот же в широкой панели, в узкой (только иконки) и в мобильной шторке.
export function SidebarNav({ section, collapsed, onNavigate }: { section: SectionSlug; collapsed: boolean; onNavigate?: () => void }) {
  const { t } = useI18n();
  const pathname = usePathname();
  const { canSee, db } = useStore();

  return (
    <nav className="flex flex-col gap-4" aria-label={t.sections[section]}>
      {MENU[section].map((g) => ({ ...g, items: g.items.filter((i) => section !== "usluga" || canSee(i.key)) })).filter((g) => g.items.length > 0).map((group) => {
        const label = t.menuGroups[group.key];
        return (
          <div key={group.key}>
            {label && !collapsed && <div className="mb-1 px-3 text-[11px] font-extrabold uppercase tracking-[.05em] text-nav-muted">{label}</div>}
            {label && collapsed && <div className="mx-3 mb-2 border-t border-white/10" />}
            <ul className="flex flex-col gap-0.5">
              {group.items.map((item) => {
                const href = `/${section}/${item.key}`;
                const active = pathname === href || pathname.startsWith(href + "/");
                const name = item.key === "zapisi" && db.intake === "flow" ? t.u.flow.title : item.key === "zapisi" && db.intake === "mixed" ? t.u.flow.mixedTitle : t.menu[item.key];
                return (
                  <li key={item.key}>
                    <Link
                      href={href}
                      onClick={onNavigate}
                      aria-current={active ? "page" : undefined}
                      title={collapsed ? name : undefined}
                      className={`press flex items-center gap-3 rounded-[10px] px-3 py-2 text-sm ${
                        active ? "bg-gold font-extrabold text-primary" : "font-semibold text-nav-text hover:bg-white/10 hover:text-white"
                      } ${collapsed ? "justify-center" : ""}`}
                    >
                      <Icon name={item.icon} />
                      {!collapsed && <span className="truncate">{name}</span>}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        );
      })}
    </nav>
  );
}
