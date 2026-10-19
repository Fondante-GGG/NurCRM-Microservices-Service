"use client";

import { useEffect, useState, type ReactNode } from "react";
import { usePathname } from "next/navigation";
import { useI18n } from "@/i18n/provider";
import type { SectionSlug } from "@/lib/sections";
import { Icon } from "./icon";
import { ProfileButton } from "./profile";
import { BranchSwitch } from "./branch-switch";
import { SidebarNav, useSidebarCollapsed } from "./sidebar";
import { useStore } from "@/data/store";
import { SetupWizard } from "@/screens/setup-wizard";

// Общий каркас: слева сворачиваемая панель с меню, сверху шапка, на телефоне — шторка.
export function Shell({ section, name, canLogout, children }: { section: SectionSlug; name: string; canLogout: boolean; children: ReactNode }) {
  const { t } = useI18n();
  const { db, ready, supportAgent, setSupportAgent, update } = useStore();
  const { collapsed, toggle } = useSidebarCollapsed();
  const [drawer, setDrawer] = useState(false);
  const [drawerClosing, setDrawerClosing] = useState(false);
  const pathname = usePathname();
  const pageKey = pathname.split("/")[2] ?? "";
  const pageTitle = pageKey === "zapisi" && db.intake === "flow" ? t.u.flow.title : pageKey === "zapisi" && db.intake === "mixed" ? t.u.flow.mixedTitle : t.menu[pageKey] ?? "";

  const closeDrawer = () => {
    if (!drawer) return;
    setDrawerClosing(true);
    window.setTimeout(() => { setDrawer(false); setDrawerClosing(false); }, 200);
  };
  useEffect(() => { setDrawer(false); setDrawerClosing(false); }, [pathname]);

  useEffect(() => {
    fetch("/api/auth/me")
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => {
        if (data?.impersonated_by) {
          setSupportAgent(data.impersonated_by);
        }
      })
      .catch(() => {});
  }, [setSupportAgent]);

  if (!ready) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-paper">
        <p className="text-sm text-ink-soft" aria-live="polite">{t.u.common.loading}</p>
      </div>
    );
  }

  if (section === "usluga" && !db.industry) return <SetupWizard />;

  const exitSupport = async () => {
    try {
      const res = await fetch("/api/auth/impersonate-exit", { method: "POST" });
      const data = await res.json().catch(() => ({}));
      setSupportAgent(null);
      window.location.href = data.next || "/support";
    } catch {
      setSupportAgent(null);
      window.location.href = "/support";
    }
  };

  return (
    <div className="flex min-h-screen flex-col">
      {supportAgent && (
        <div className="sticky top-0 z-40 flex h-10 items-center justify-between gap-2 bg-warn px-4 text-sm font-bold text-white">
          <span>{t.u.sp.banner.replace("{company}", db.settings.company.name).replace("{agent}", supportAgent)}</span>
          <button type="button" onClick={exitSupport} className="press rounded-lg border border-white/50 px-3 py-1 text-xs font-bold hover:bg-white/10">{t.u.sp.exit}</button>
        </div>
      )}
      <div className="flex flex-1">
      <aside
        className={`sticky hidden shrink-0 flex-col bg-nav py-4 text-white transition-[width] duration-200 md:flex ${supportAgent ? "top-10 h-[calc(100vh-2.5rem)]" : "top-0 h-screen"} ${
          collapsed ? "w-16 px-2" : "w-72 px-3"
        }`}
      >
        <div className={`flex items-center ${collapsed ? "justify-center" : "justify-between px-2"}`}>
          {collapsed ? (
            /* eslint-disable-next-line @next/next/no-img-element */
            <img src="/kezek-icon-dark.png" alt="KEZEK" className="size-8 object-contain" />
          ) : (
            <div className="flex min-w-0 items-center gap-2.5">
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src="/kezek-logo-dark.png" alt="KEZEK by NurCRM" className="h-8 w-auto max-w-[190px] object-contain" />
            </div>
          )}
          <button
            type="button"
            onClick={toggle}
            aria-label={collapsed ? t.shell.expand : t.shell.collapse}
            title={collapsed ? t.shell.expand : t.shell.collapse}
            className="press rounded-lg p-1.5 text-nav-text hover:bg-white/10 hover:text-white"
          >
            <Icon name={collapsed ? "panel-open" : "panel-close"} />
          </button>
        </div>
        <div className="mt-6 flex-1 overflow-y-auto [scrollbar-width:thin]">
          <SidebarNav section={section} collapsed={collapsed} />
        </div>
      </aside>

      {(drawer || drawerClosing) && (
        <div className="fixed inset-0 z-40 md:hidden">
          <button type="button" aria-label={t.shell.closeMenu} onClick={closeDrawer} className={`absolute inset-0 bg-ink/40 ${drawerClosing ? "anim-fade-out" : "anim-fade-in"}`} />
          <aside className={`absolute inset-y-0 left-0 flex w-72 max-w-[85vw] flex-col bg-nav px-3 py-4 text-white shadow-xl ${drawerClosing ? "anim-slide-out-left" : "anim-slide-in-left"}`}>
            <div className="flex items-center justify-between px-2">
              <div className="flex items-center gap-2.5">
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img src="/kezek-logo-dark.png" alt="KEZEK by NurCRM" className="h-8 w-auto max-w-[190px] object-contain" />
              </div>
              <button type="button" onClick={closeDrawer} aria-label={t.shell.closeMenu} className="press rounded-lg p-1.5 text-nav-text hover:bg-white/10">
                <Icon name="x" />
              </button>
            </div>
            <div className="mt-6 flex-1 overflow-y-auto [scrollbar-width:thin]">
              <SidebarNav section={section} collapsed={false} onNavigate={closeDrawer} />
            </div>
          </aside>
        </div>
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className={`sticky ${supportAgent ? "top-10" : "top-0"} z-30 flex items-center justify-between gap-3 border-b border-line bg-card px-3 py-2.5 sm:px-6`}>
          <div className="flex min-w-0 items-center gap-2">
            <button type="button" onClick={() => setDrawer(true)} aria-label={t.shell.openMenu} className="press rounded-lg p-1.5 hover:bg-paper md:hidden">
              <Icon name="menu" />
            </button>
            <div className="min-w-0 truncate text-sm text-ink-soft">
              <span className="font-bold text-ink md:hidden">{t.appName} </span>
              <span className="hidden md:inline">{name ? `${t.shell.hello}, ${name}` : t.sections[section]}{pageTitle && <span className="text-ink"> › {pageTitle}</span>}</span>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <BranchSwitch />
            <ProfileButton />
            {canLogout && (
              <form action="/api/auth/logout" method="post">
                <button
                  type="submit"
                  onClick={() => {
                    try {
                      localStorage.clear();
                    } catch {}
                  }}
                  className="rounded-lg border border-line px-3 py-1.5 text-sm font-semibold hover:bg-paper"
                >
                  {t.shell.logout}
                </button>
              </form>
            )}
          </div>
        </header>
        <main key={pathname} className="anim-rise flex-1 px-4 py-6 sm:px-6">{children}</main>
      </div>
      </div>
    </div>
  );
}
