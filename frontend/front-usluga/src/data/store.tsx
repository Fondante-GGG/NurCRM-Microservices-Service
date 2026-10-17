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
    setDb({
      ...seed,
      intake: opts?.intake ?? seed.intake,
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
