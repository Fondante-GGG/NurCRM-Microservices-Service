"use client";

// Хранилище данных каркаса: примерные данные в памяти + localStorage.
// Когда появится API, экраны останутся, а функции здесь будут ходить на сервер.
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { makeSeed, DB_VERSION, DEFAULT_ROLES, DEFAULT_BOOKING, DEFAULT_COMPANY, DEFAULT_RECEIPT, DEFAULT_REMINDERS, roleKind, type DB } from "./sample/seed";
import type { AccessLevel } from "./types";
import type { Industry, IntakeMode } from "@/lib/industry";
import type { Id, Role, Staff } from "./types";

const KEY = "nurcrm_usluga_demo";

type Ctx = {
  db: DB;
  ready: boolean;
  update: (fn: (db: DB) => DB) => void;
  reset: () => void;
  chooseIndustry: (i: Industry, opts?: { intake?: IntakeMode; companyName?: string }) => void;
  branchId: Id | "all";
  setBranchId: (id: Id | "all") => void;
  userId: Id; // кто вошёл (на презентации переключается через «Смотреть как»)
  setUserId: (id: Id) => void;
  user: Staff | null;
  role: Role;
  canSee: (page: string) => boolean;
  canManage: (page: string) => boolean;
  levelFor: (page: string) => AccessLevel | null;
  // Поддержка: «вход как клиент». Строка = имя сотрудника поддержки, null = обычный режим.
  supportAgent: string | null;
  setSupportAgent: (name: string | null) => void;
};

const StoreContext = createContext<Ctx | null>(null);

function load(): DB | null {
  try {
    const raw = localStorage.getItem(KEY);
    if (!raw) return null;
    const db = JSON.parse(raw) as DB;
    if (db.version !== DB_VERSION) return null;
    // Пересеять, если данные старше суток: «сегодня» в журнале должно быть сегодня.
    if (db.seededAt.slice(0, 10) !== new Date().toISOString().slice(0, 10) && db.seededAt.slice(0, 10) !== localToday()) return null;
    return db;
  } catch {
    return null;
  }
}

function localToday(): string {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}

export function StoreProvider({ children }: { children: ReactNode }) {
  const [db, setDb] = useState<DB | null>(null);
  const [branchId, setBranchIdState] = useState<Id | "all">("b1");
  const [userId, setUserIdState] = useState<Id>("u_owner");
  const [supportAgent, setSupportAgentState] = useState<string | null>(null);

  useEffect(() => {
    const loaded = load() ?? makeSeed();
    setDb(loaded);
    try {
      const b = localStorage.getItem(KEY + "_branch");
      if (b) setBranchIdState(b);
      const u = localStorage.getItem(KEY + "_user");
      if (u && loaded.staff.some((s) => s.id === u)) setUserIdState(u);
      const a = localStorage.getItem(KEY + "_agent");
      if (a) setSupportAgentState(a);
    } catch {}

    async function syncBackend() {
      try {
        const [meRes, compRes, brRes, tempRes, tkRes, apptRes, catRes, svcRes, clRes, bkRes] = await Promise.all([
          fetch("/api/auth/me").catch(() => null),
          fetch("/api/proxy/api/main/company/").catch(() => null),
          fetch("/api/proxy/api/main/branches/").catch(() => null),
          fetch("/api/proxy/api/main/company/temp-access/").catch(() => null),
          fetch("/api/proxy/api/main/support/tickets/").catch(() => null),
          fetch("/api/proxy/api/main/appointments/").catch(() => null),
          fetch("/api/proxy/api/v1/catalog/categories/").catch(() => null),
          fetch("/api/proxy/api/v1/catalog/services/").catch(() => null),
          fetch("/api/proxy/api/v1/clients/").catch(() => null),
          fetch("/api/proxy/api/v1/bookings/").catch(() => null),
        ]);

        if (meRes && meRes.ok) {
          const me = await meRes.json().catch(() => null);
          if (me?.impersonated_by) {
            setSupportAgentState(me.impersonated_by);
          }
        }

        let compData: any = null;
        if (compRes && compRes.ok) compData = await compRes.json().catch(() => null);

        let branchesData: any[] = [];
        if (brRes && brRes.ok) {
          const list = await brRes.json().catch(() => null);
          if (Array.isArray(list) && list.length > 0) {
            branchesData = list.map((b: any) => ({
              id: b.id,
              name: b.name,
              address: b.address || "",
              phone: b.phone || "",
              hours: b.hours || "",
              active: b.active ?? true,
              showcaseOnly: b.showcaseOnly ?? false,
            }));
          }
        }

        let tempUntil: string | null = null;
        if (tempRes && tempRes.ok) {
          const t = await tempRes.json().catch(() => null);
          tempUntil = t?.until ?? null;
        }

        let serverTickets: any[] = [];
        if (tkRes && tkRes.ok) {
          const tList = await tkRes.json().catch(() => null);
          if (Array.isArray(tList) && tList.length > 0) {
            serverTickets = tList.map((t: any) => ({
              id: t.id,
              createdAt: t.created_at,
              topic: t.topic,
              message: t.message,
              contact: t.contact,
              shareAccess: t.share_access,
              status: t.status,
              reply: t.reply,
              assignee: t.assignee,
            }));
          }
        }

        let serverAppointments: any[] = [];
        if (apptRes && apptRes.ok) {
          const appts = await apptRes.json().catch(() => null);
          if (Array.isArray(appts) && appts.length > 0) {
            serverAppointments = appts.map((a: any) => ({
              id: a.id,
              branchId: a.branch_id || (branchesData[0]?.id ?? "b1"),
              staffId: a.staff_id || "",
              clientId: a.client_id || "",
              start: a.start || new Date().toISOString(),
              duration: a.duration || 30,
              serviceIds: a.service_ids || [],
              status: a.status || "pending",
              source: a.source || "admin",
              createdById: a.created_by_id || null,
              note: a.note || "",
              visitId: a.visit_id || null,
            }));
          }
        }

        let serverCategories: any[] = [];
        if (catRes && catRes.ok) {
          const cats = await catRes.json().catch(() => null);
          if (Array.isArray(cats) && cats.length > 0) {
            serverCategories = cats.map((c: any) => ({
              id: c.id,
              name: c.name,
            }));
          }
        }

        let serverServices: any[] = [];
        if (svcRes && svcRes.ok) {
          const svcs = await svcRes.json().catch(() => null);
          const sList = Array.isArray(svcs) ? svcs : (svcs?.results || svcs?.items || []);
          if (Array.isArray(sList) && sList.length > 0) {
            serverServices = sList.map((s: any) => ({
              id: s.id,
              name: s.name,
              categoryId: s.category_id || (serverCategories[0]?.id ?? "c1"),
              duration: s.time_minutes || s.time || 30,
              price: Number(s.price) || 0,
              pricesByPosition: {},
              addon: false,
              materialsCost: 0,
              discountAtExpense: "salon" as const,
              online: true,
              active: s.is_active ?? true,
            }));
          }
        }

        let serverClients: any[] = [];
        if (clRes && clRes.ok) {
          const cls = await clRes.json().catch(() => null);
          const cList = Array.isArray(cls) ? cls : (cls?.results || cls?.items || []);
          if (Array.isArray(cList) && cList.length > 0) {
            serverClients = cList.map((c: any) => ({
              id: c.id,
              name: c.full_name || "",
              phone: c.phone || "",
              birthday: c.birth_date || null,
              category: (c.status === "vip" ? "vip" : c.status === "blacklisted" ? "blacklist" : "regular") as any,
              notes: c.notes || "",
              consent: true,
              createdAt: c.created_at ? c.created_at.slice(0, 10) : localToday(),
            }));
          }
        }

        let serverBookings: any[] = [];
        if (bkRes && bkRes.ok) {
          const bks = await bkRes.json().catch(() => null);
          const bList = Array.isArray(bks) ? bks : (bks?.results || bks?.items || []);
          if (Array.isArray(bList) && bList.length > 0) {
            serverBookings = bList.map((b: any) => ({
              id: b.id,
              branchId: branchesData[0]?.id ?? "b1",
              clientName: b.client_name || "",
              phone: b.client_phone || "",
              serviceId: b.services?.[0]?.id ?? (serverServices[0]?.id ?? null),
              serviceIds: Array.isArray(b.services) ? b.services.map((s: any) => s.id) : [],
              comment: b.client_comment || "",
              staffId: b.master_id || null,
              wishedAt: b.date && b.time_start ? `${b.date}T${b.time_start.slice(0, 5)}` : null,
              source: "online" as const,
              status: (b.status === "confirmed" ? "confirmed" : b.status === "declined" ? "declined" : "new") as any,
              createdAt: b.created_at || new Date().toISOString(),
            }));
          }
        }

        setDb((cur) => {
          if (!cur) return cur;
          const updated = { ...cur };
          if (compData) {
            if (compData.industry) updated.industry = compData.industry;
            if (compData.intake) updated.intake = compData.intake;
            updated.settings = {
              ...updated.settings,
              company: {
                ...updated.settings.company,
                name: compData.name || updated.settings.company.name,
                legalName: compData.legal_name || updated.settings.company.legalName,
                inn: compData.inn || updated.settings.company.inn,
                okpo: compData.okpo || updated.settings.company.okpo,
                account: compData.account || updated.settings.company.account,
                bik: compData.bik || updated.settings.company.bik,
                address: compData.address || updated.settings.company.address,
                phones: Array.isArray(compData.phones) ? compData.phones.join(", ") : (compData.phone || updated.settings.company.phones),
              },
            };
          }
          if (branchesData.length > 0) {
            updated.branches = branchesData;
            setBranchIdState((prev) => (prev === "all" || branchesData.some((b) => b.id === prev) ? prev : branchesData[0].id));
          }
          if (tempUntil !== null) {
            updated.tempAccessUntil = tempUntil;
          }
          if (serverTickets.length > 0) {
            updated.support = serverTickets;
          }
          if (serverAppointments.length > 0) {
            updated.appointments = serverAppointments;
          }
          if (serverCategories.length > 0) {
            updated.categories = serverCategories;
          }
          if (serverServices.length > 0) {
            // merge or replace
            updated.services = serverServices;
          }
          if (serverClients.length > 0) {
            updated.clients = serverClients;
          }
          if (serverBookings.length > 0) {
            updated.requests = serverBookings;
          }
          return updated;
        });
      } catch (e) {
        console.warn("Backend sync notice:", e);
      }
    }

    syncBackend();
  }, []);

  useEffect(() => {
    if (!db) return;
    try {
      localStorage.setItem(KEY, JSON.stringify(db));
    } catch {}
  }, [db]);

  const update = useCallback((fn: (db: DB) => DB) => setDb((cur) => (cur ? fn(cur) : cur)), []);
  const reset = useCallback(() => {
    try {
      localStorage.removeItem(KEY);
    } catch {}
    setDb((cur) => makeSeed(undefined, cur?.industry ?? null));
  }, []);
  const setBranchId = useCallback((id: Id | "all") => {
    setBranchIdState(id);
    try {
      localStorage.setItem(KEY + "_branch", id);
    } catch {}
  }, []);

  const chooseIndustry = useCallback((i: Industry, opts?: { intake?: IntakeMode; companyName?: string }) => {
    try { localStorage.removeItem(KEY); } catch {}
    const seed = makeSeed(undefined, i);
    const name = opts?.companyName?.trim();
    const finalIntake = opts?.intake ?? seed.intake;

    fetch("/api/proxy/api/main/company/industry/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ industry: i }),
    }).catch(() => {});

    if (name || finalIntake) {
      fetch("/api/proxy/api/main/company/", {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name || undefined, intake: finalIntake }),
      }).catch(() => {});
    }

    setDb({
      ...seed,
      industry: i,
      intake: finalIntake,
      settings: name ? { ...seed.settings, company: { ...seed.settings.company, name } } : seed.settings,
      branches: name ? seed.branches.map((b, k) => (k === 0 ? { ...b, name } : b)) : seed.branches,
    });
  }, []);
  const setUserId = useCallback((id: Id) => {
    setUserIdState(id);
    try {
      localStorage.setItem(KEY + "_user", id);
    } catch {}
  }, []);

  const setSupportAgent = useCallback((name: string | null) => {
    setSupportAgentState(name);
    try {
      if (name) localStorage.setItem(KEY + "_agent", name); else localStorage.removeItem(KEY + "_agent");
    } catch {}
  }, []);

  const value = useMemo<Ctx>(() => {
    const data = db ?? EMPTY;
    const user = data.staff.find((s) => s.id === userId) ?? null;
    const accessRole = data.roles.find((r) => r.id === user?.roleId);
    const role: Role = user ? roleKind(accessRole) : "owner";
    const access = data.settings.unifiedAccess ? accessRole?.access ?? {} : user?.access ?? accessRole?.access ?? {};
    const levelFor = (page: string): AccessLevel | null => (role === "owner" ? "manage" : access[page] ?? null);
    const canSee = (page: string) => levelFor(page) !== null;
    const canManage = (page: string) => levelFor(page) === "manage";
    return { db: data, ready: db !== null, update, reset, chooseIndustry, branchId, setBranchId, userId, setUserId, user, role, canSee, canManage, levelFor, supportAgent, setSupportAgent };
  }, [db, update, reset, chooseIndustry, branchId, setBranchId, userId, setUserId, supportAgent, setSupportAgent]);
  return <StoreContext value={value}>{children}</StoreContext>;
}

const EMPTY: DB = {
  version: DB_VERSION, seededAt: "", branches: [], positions: [], staff: [], categories: [], services: [], clients: [], appointments: [], visits: [], shifts: [],
  products: [], registers: [], cashOps: [], requests: [], documents: [], audit: [], schemes: [], payslips: [], payouts: [], adjustments: [],
  roles: DEFAULT_ROLES,
  industry: null,
  intake: "schedule",
  support: [],
  companies: [],
  supportLog: [],
  tempAccessUntil: null,
  packages: [],
  clientPackages: [],
  closedPeriods: [],
  settings: { fotThreshold: 45, workFrom: "09:00", workTo: "21:00", slotMin: 15, unifiedAccess: true, approvalLimit: 10000, booking: DEFAULT_BOOKING, company: DEFAULT_COMPANY, receipt: DEFAULT_RECEIPT, reminders: DEFAULT_REMINDERS },
};

export function useStore(): Ctx {
  const ctx = useContext(StoreContext);
  if (!ctx) throw new Error("useStore must be used inside StoreProvider");
  return ctx;
}

// Данные с учётом выбранного филиала.
export function useBranchFilter() {
  const { branchId } = useStore();
  return useCallback(<T extends { branchId: Id }>(items: T[]) => (branchId === "all" ? items : items.filter((x) => x.branchId === branchId)), [branchId]);
}

export function newId(prefix: string): string {
  return `${prefix}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}
