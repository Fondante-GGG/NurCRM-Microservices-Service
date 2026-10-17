// ПРИМЕРНЫЕ ДАННЫЕ для показа каркаса. Генерируются детерминированно от «сегодня».
// Настоящие данные придут из API NurCRM; типы те же (src/data/types.ts).
import type {
  AccessLevel, AccessMap, AccessRole, Adjustment, ClientPackage, ClosedPeriod, PackageTemplate, ReminderSettings, BookingSettings, CompanyCard, CompanySettings, ReceiptSettings, SupportLogEntry, SupportTicket, Appointment, AuditEntry, BookingRequest, Branch, CashOperation, CashRegister, Client, ClientDocument,
  Payout, Payslip, Position, Product, Scheme, Service, ServiceCategory, Shift, Staff, Visit, VisitLine,
} from "../types";
import { addDays, addMonths, daysInPeriod, periodOf, toIsoLocal, todayKey, parseIso, hhmmOf } from "../../lib/dates";
import { PROFILES, type Industry, type IntakeMode } from "../../lib/industry";

export type DB = {
  version: number;
  seededAt: string;
  branches: Branch[];
  positions: Position[];
  staff: Staff[];
  categories: ServiceCategory[];
  services: Service[];
  clients: Client[];
  appointments: Appointment[];
  visits: Visit[];
  shifts: Shift[];
  products: Product[];
  registers: CashRegister[];
  cashOps: CashOperation[];
  requests: BookingRequest[];
  documents: ClientDocument[];
  audit: AuditEntry[];
  schemes: Scheme[];
  payslips: Payslip[];
  payouts: Payout[];
  adjustments: Adjustment[];
  roles: AccessRole[];
  industry: Industry | null; // null = сфера ещё не выбрана (новый аккаунт)
  intake: IntakeMode;
  support: SupportTicket[];
  companies: CompanyCard[]; // другие компании для панели поддержки
  supportLog: SupportLogEntry[];
  tempAccessUntil: string | null; // временный доступ поддержки к этой компании
  packages: PackageTemplate[];
  clientPackages: ClientPackage[];
  closedPeriods: ClosedPeriod[];
  settings: { fotThreshold: number; workFrom: string; workTo: string; slotMin: number; unifiedAccess: boolean; approvalLimit: number; booking: BookingSettings; company: CompanySettings; receipt: ReceiptSettings; reminders: ReminderSettings };
};

export const DB_VERSION = 14;

export const CURRENT_COMPANY_ID = "c_self";

export const DEFAULT_COMPANY: CompanySettings = { name: "Premium", legalName: "ОсОО «Премиум Барбер»", inn: "", okpo: "", account: "", bik: "", address: "г. Ош, ул. Ленина, 123", phones: "+996 700 123 456" };
export const DEFAULT_REMINDERS: ReminderSettings = {
  enabled: true,
  hoursBefore: [24, 2],
  channel: "whatsapp",
  template: "{имя}, напоминаем о записи {дата} в {время} к мастеру {мастер}. Адрес: {адрес}. Если планы изменились, ответьте на это сообщение.",
};
export const DEFAULT_RECEIPT: ReceiptSettings = { connection: "none", model: "", address: "", paperWidth: 80, autoPrint: false, printLogo: true, footer: "Спасибо, что выбрали нас!" };

export const DEFAULT_BOOKING: BookingSettings = {
  enabled: true,
  title: "Онлайн-запись",
  intro: "Выберите услугу, мастера и удобное время. Мы подтвердим запись сообщением.",
  slotMin: 30,
  leadHours: 2,
  showPrices: true,
  chooseMaster: true,
  maxDays: 14,
};

export const ALL_PAGES = ["analitika", "zapisi", "zayavki", "klienty", "dokumenty-klientov", "uslugi", "dop-uslugi", "prodazha", "sklad", "kassa", "smeny", "istoriya", "sotrudniki", "zarplata", "filialy", "nastrojki"];

// Роли доступа по умолчанию. Владелец и Администратор встроенные; «Мастер» — обычная роль, её можно менять.
export function accessOf(pages: string[], manage: string[] | "all" = "all"): AccessMap {
  const m: AccessMap = {};
  for (const p of pages) m[p] = manage === "all" || manage.includes(p) ? "manage" : "view";
  return m;
}
export function pagesOf(access: AccessMap): string[] {
  return Object.keys(access);
}
export function levelOf(access: AccessMap | null | undefined, page: string): AccessLevel | null {
  return access?.[page] ?? null;
}

const ADMIN_PAGES = ["analitika", "zapisi", "zayavki", "klienty", "dokumenty-klientov", "uslugi", "dop-uslugi", "prodazha", "sklad", "kassa", "smeny", "sotrudniki"];
const MASTER_ACCESS = accessOf(["zapisi", "klienty", "smeny", "zarplata"], ["zapisi"]);
// Бухгалтер: свой логин, касса и зарплата под управлением, остальное только смотреть. Записей и клиентов не видит.
const ACCOUNTANT_ACCESS = accessOf(["analitika", "prodazha", "sklad", "kassa", "smeny", "istoriya", "sotrudniki", "zarplata"], ["kassa", "zarplata"]);
export const DEFAULT_ROLES: AccessRole[] = [
  { id: "r_owner", name: "Владелец", pages: ALL_PAGES, access: accessOf(ALL_PAGES), builtin: true, ownOnly: false },
  { id: "r_admin", name: "Администратор", pages: ADMIN_PAGES, access: accessOf(ADMIN_PAGES, ["zapisi", "zayavki", "klienty", "dokumenty-klientov", "prodazha", "sklad", "kassa", "smeny"]), builtin: true, ownOnly: false },
  { id: "r_accountant", name: "Бухгалтер", pages: pagesOf(ACCOUNTANT_ACCESS), access: ACCOUNTANT_ACCESS, builtin: true, ownOnly: false },
  { id: "r_master", name: "Мастер", pages: pagesOf(MASTER_ACCESS), access: MASTER_ACCESS, builtin: false, ownOnly: true },
];

export function roleKind(role: AccessRole | undefined): "owner" | "admin" | "master" {
  if (!role) return "master";
  if (role.id === "r_owner") return "owner";
  return role.ownOnly ? "master" : "admin";
}

function rng(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const FIRST = ["Азамат", "Бекжан", "Нурлан", "Эмир", "Талгат", "Данияр", "Адилет", "Кубат", "Улан", "Мирлан", "Эрлан", "Самат", "Бакыт", "Жаныбек", "Тимур", "Руслан", "Айбек", "Чынгыз", "Нурбек", "Искендер", "Алмаз", "Элдар", "Санжар", "Марат"];
const LAST = ["Асанов", "Токтосунов", "Жумабеков", "Калыков", "Сыдыков", "Мамбетов", "Осмонов", "Садыков", "Исаков", "Абдыкадыров", "Турдубаев", "Эсенов", "Омуров", "Бекбоев", "Шамшиев"];

export function makeSeed(today = todayKey(), industry: Industry | null = null): DB {
  const prof = PROFILES[industry ?? "barber"];
  const r = rng(20261012);
  const pick = <T,>(arr: T[]) => arr[Math.floor(r() * arr.length)];
  const int = (a: number, b: number) => a + Math.floor(r() * (b - a + 1));

  const branches: Branch[] = [
    { id: "b1", name: prof.companyName, address: "г. Ош, ул. Ленина, 123", phone: "+996 700 123 456", hours: "Ежедневно 09:00–21:00", active: true, showcaseOnly: false },
    { id: "b2", name: `${prof.companyName} Сити`, address: "г. Ош, ул. Курманжан Датки, 45", phone: "+996 700 654 321", hours: "Ежедневно 10:00–20:00", active: true, showcaseOnly: true },
  ];
  const positions: Position[] = [
    ...prof.positions.map((p) => ({ id: p.id, name: p.name })),
    { id: "p_admin", name: "Администратор" },
    { id: "p_accountant", name: "Бухгалтер" },
    { id: "p_owner", name: "Владелец" },
  ];
  const posName = (id: string) => prof.positions.find((p) => p.id === id)?.name ?? id;
  const schemes: Scheme[] = [
    {
      id: "s_barber", name: `${posName("p_barber")}: 40 % от услуг`, positionId: "p_barber", effectiveFrom: "2026-01-01",
      components: [
        { kind: "service_rate", mode: "percent", value: 40, overrides: [{ serviceId: "sv_kids", mode: "fixed", value: 250 }], deductMaterials: true },
        { kind: "daily_count_bonus", tiers: [{ minCount: 6, percent: 5 }, { minCount: 8, percent: 10 }] },
      ],
    },
    {
      id: "s_top", name: `${posName("p_top")}: 45 % от услуг`, positionId: "p_top", effectiveFrom: "2026-01-01",
      components: [
        { kind: "service_rate", mode: "percent", value: 45, overrides: [], deductMaterials: true },
        { kind: "daily_count_bonus", tiers: [{ minCount: 6, percent: 5 }, { minCount: 8, percent: 10 }] },
      ],
    },
    {
      id: "s_admin", name: "Администратор: оклад + за запись + доля филиала", positionId: "p_admin", effectiveFrom: "2026-01-01",
      components: [
        { kind: "monthly_salary", amount: 25000 },
        { kind: "booking_fee", mode: "fixed", value: 20 },
        { kind: "branch_revenue_share", percent: 10, threshold: 300000, metric: "revenue" },
      ],
    },
  ];
  const staff: Staff[] = [
    { id: "u_owner", name: "Умар Абдыкадыров", phone: "+996 700 000 001", positionId: "p_owner", branchIds: ["b1", "b2"], role: "owner", roleId: "r_owner", pages: null, access: null, employment: "staff", hiredAt: "2025-01-01", active: true, schemeId: null, serviceIds: [], color: "#64748b" },
    { id: "u_admin", name: "Айгерим Токтосунова", phone: "+996 700 000 002", positionId: "p_admin", branchIds: ["b1"], role: "admin", roleId: "r_admin", pages: null, access: null, employment: "staff", hiredAt: "2025-03-01", active: true, schemeId: "s_admin", serviceIds: [], color: "#8b5cf6" },
    { id: "u_buh", name: "Гульмира Осмонова", phone: "+996 700 000 008", positionId: "p_accountant", branchIds: ["b1", "b2"], role: "admin", roleId: "r_accountant", pages: null, access: null, employment: "contract", hiredAt: "2025-04-01", active: true, schemeId: null, serviceIds: [], color: "#0f766e" },
    { id: "u_azamat", name: "Азамат Асанов", phone: "+996 700 000 003", positionId: "p_top", branchIds: ["b1"], role: "master", roleId: "r_master", pages: null, access: null, employment: "self_employed", hiredAt: "2025-02-01", active: true, schemeId: "s_top", serviceIds: ["sv_cut", "sv_beard", "sv_combo", "sv_kids", "sv_shave", "sv_gray", "ad_beardcare", "ad_mask", "ad_style"], color: "#0e7c86" },
    { id: "u_bekzhan", name: "Бекжан Жумабеков", phone: "+996 700 000 004", positionId: "p_barber", branchIds: ["b1"], role: "master", roleId: "r_master", pages: null, access: null, employment: "contract", hiredAt: "2025-06-15", active: true, schemeId: "s_barber", serviceIds: ["sv_cut", "sv_beard", "sv_combo", "sv_kids", "ad_beardcare", "ad_style"], color: "#2563eb" },
    { id: "u_nurlan", name: "Нурлан Калыков", phone: "+996 700 000 005", positionId: "p_barber", branchIds: ["b1"], role: "master", roleId: "r_master", pages: null, access: null, employment: "contract", hiredAt: "2025-09-01", active: true, schemeId: "s_barber", serviceIds: ["sv_cut", "sv_beard", "sv_combo", "sv_kids", "sv_shave", "ad_mask", "ad_style"], color: "#d97706" },
    { id: "u_emir", name: "Эмир Сыдыков", phone: "+996 700 000 006", positionId: "p_barber", branchIds: ["b1"], role: "master", roleId: "r_master", pages: null, access: null, employment: "contract", hiredAt: "2026-03-01", active: true, schemeId: "s_barber", serviceIds: ["sv_cut", "sv_beard", "sv_combo", "sv_kids", "ad_style"], color: "#dc2626" },
    { id: "u_talgat", name: "Талгат Мамбетов", phone: "+996 700 000 007", positionId: "p_barber", branchIds: ["b2"], role: "master", roleId: "r_master", pages: null, access: null, employment: "rent", hiredAt: "2026-05-01", active: true, schemeId: "s_barber", serviceIds: ["sv_cut", "sv_beard", "sv_combo"], color: "#16a34a" },
  ];
  // В сферах, где обычно работают женщины (салон, ногти, брови, косметология, процедурный), примерные специалисты — женщины.
  const FEMALE: Record<string, string> = { u_azamat: "Айзада Асанова", u_bekzhan: "Бермет Жумабекова", u_nurlan: "Нургуль Калыкова", u_emir: "Элима Сыдыкова", u_talgat: "Толгонай Мамбетова" };
  if (industry && ["beauty", "nails", "brows", "cosmetology", "procedure"].includes(industry)) {
    for (const st of staff) if (FEMALE[st.id]) st.name = FEMALE[st.id];
  }
  const categories: ServiceCategory[] = prof.categories.map((c) => ({ id: c.id, name: c.name }));
  const services: Service[] = prof.services.map((x) => ({
    id: x.id, name: x.name, categoryId: x.cat, duration: x.duration, price: x.price,
    pricesByPosition: (x.topPrice ? { p_top: x.topPrice } : {}) as Record<string, number>, addon: !!x.addon, materialsCost: x.materials,
    discountAtExpense: x.discountAt ?? "salon", online: x.online ?? true, active: true,
  }));
  const sv = (id: string) => services.find((s) => s.id === id)!;

  const clients: Client[] = Array.from({ length: 70 }, (_, i) => ({
    id: `cl${i + 1}`,
    name: `${pick(FIRST)} ${pick(LAST)}`,
    phone: `+996 ${pick(["550", "555", "700", "705", "770", "777"])} ${int(100, 999)} ${int(100, 999)}`,
    birthday: r() < 0.6 ? `${int(1985, 2004)}-${String(int(1, 12)).padStart(2, "0")}-${String(int(1, 28)).padStart(2, "0")}` : null,
    category: "new",
    notes: "",
    consent: r() < 0.8,
    createdAt: addDays(today, -int(10, 400)),
  }));

  // Смены: барберы 2/2, админ 5/2, за 70 дней назад и 14 вперёд.
  const shifts: Shift[] = [];
  const masters = staff.filter((s) => s.role === "master");
  for (let d = -70; d <= 14; d++) {
    const date = addDays(today, d);
    const dow = (parseIso(date).getDay() + 6) % 7;
    masters.forEach((m, idx) => {
      const cycle = (d + idx * 2 + 1000) % 4;
      if (cycle < 2) shifts.push({ id: `sh-${m.id}-${date}`, staffId: m.id, branchId: m.branchIds[0], date, from: "10:00", to: "20:00", breakMin: 60, fact: d < 0 ? (r() < 0.04 ? "missed" : "worked") : "planned" });
    });
    if (dow < 5) shifts.push({ id: `sh-u_admin-${date}`, staffId: "u_admin", branchId: "b1", date, from: "09:00", to: "21:00", breakMin: 60, fact: d < 0 ? "worked" : "planned" });
  }

  // Записи и визиты: по сменам, 4–8 в день у мастера; прошлое — оплачено, будущее — ожидает.
  const appointments: Appointment[] = [];
  const visits: Visit[] = [];
  let n = 0;
  for (const sh of shifts) {
    const m = staff.find((s) => s.id === sh.staffId)!;
    if (m.role !== "master" || sh.fact === "missed") continue;
    const dOff = Math.round((parseIso(sh.date).getTime() - parseIso(today).getTime()) / 86400000);
    const count = dOff > 0 ? int(2, 5) : int(4, 8);
    let t = 10 * 60;
    for (let i = 0; i < count && t < 19 * 60; i++) {
      const mainIds = m.serviceIds.filter((id) => !sv(id).addon);
      const main = sv(pick(mainIds));
      const ids = [main.id];
      if (r() < 0.3) {
        const addons = m.serviceIds.filter((id) => sv(id).addon);
        if (addons.length) ids.push(pick(addons));
      }
      const duration = ids.reduce((s, id) => s + sv(id).duration, 0);
      const start = `${sh.date}T${hhmmOf(t)}`;
      // Последние две недели приходят и новые клиенты (последние 10 в списке), раньше — только старые.
      const client = dOff > -14 && r() < 0.25 ? clients[60 + int(0, 9)] : clients[int(0, 59)];
      n += 1;
      const id = `ap${n}`;
      let status: Appointment["status"] = "pending";
      if (dOff < 0) status = r() < 0.07 ? "no_show" : "paid";
      else if (dOff === 0) status = t < 13 * 60 ? "paid" : t < 15 * 60 ? "arrived" : r() < 0.6 ? "confirmed" : "pending";
      else status = r() < 0.5 ? "confirmed" : "pending";
      const source: Appointment["source"] = r() < 0.4 ? "bot" : r() < 0.2 ? "online" : "admin";
      const appt: Appointment = { id, branchId: sh.branchId, staffId: m.id, clientId: client.id, start, duration, serviceIds: ids, status, source, createdById: source === "admin" ? "u_admin" : null, note: "", visitId: null };
      if (status === "paid") {
        const lines: VisitLine[] = ids.map((sid) => {
          const s = sv(sid);
          const price = s.pricesByPosition[m.positionId] ?? s.price;
          const discount = r() < 0.15 ? Math.round(price * 0.1) : 0;
          return { kind: s.addon ? "addon" : "service", refId: s.id, name: s.name, price, qty: 1, discount, discountAtExpense: s.discountAtExpense, materialsCost: s.materialsCost };
        });
        const total = lines.reduce((s, l) => s + l.price * l.qty - l.discount, 0);
        const card = r() < 0.5 ? total : 0;
        const vid = `v${n}`;
        const refunded = dOff < -3 && r() < 0.015;
        visits.push({ id: vid, appointmentId: id, branchId: sh.branchId, staffId: m.id, clientId: client.id, closedAt: `${sh.date}T${hhmmOf(t + duration)}`, closedById: "u_admin", lines, tip: r() < 0.25 ? pick([50, 100, 200]) : 0, tipChannel: "direct", payment: { cash: total - card, card, balance: 0 }, total, refundedAt: refunded ? `${addDays(sh.date, 1)}T12:00` : null, refundAmount: refunded ? total : 0 });
        appt.visitId = vid;
      }
      appointments.push(appt);
      t += duration + pick([0, 15, 15, 30]);
    }
  }

  // Категория клиента по факту: VIP — пять самых больших сумм, постоянный — от 3 визитов.
  const spent = new Map<string, { n: number; sum: number }>();
  for (const v of visits) {
    const cur = spent.get(v.clientId ?? "") ?? { n: 0, sum: 0 };
    cur.n += 1;
    cur.sum += v.total;
    spent.set(v.clientId ?? "", cur);
  }
  const vipIds = new Set([...spent.entries()].sort((a, b) => b[1].sum - a[1].sum).slice(0, 5).map(([id]) => id));
  for (const c of clients) {
    const st = spent.get(c.id);
    c.category = vipIds.has(c.id) ? "vip" : (st?.n ?? 0) >= 3 ? "regular" : "new";
  }

  // Поток: несколько клиентов сегодня в живой очереди и один принимается прямо сейчас.
  if (prof.defaultIntake === "flow") {
    const now = new Date();
    const stamp = (minAgo: number) => toIsoLocal(new Date(now.getTime() - minAgo * 60000));
    const nurse = masters.find((m) => m.branchIds.includes("b1"));
    [["cl61", 12, "pending", null], ["cl62", 7, "pending", null], ["cl63", 3, "pending", null], ["cl64", 4, "arrived", nurse?.id ?? null]].forEach(([cid, ago, st, sid], k) => {
      n += 1;
      appointments.push({ id: `apq${k}`, branchId: "b1", staffId: (sid as string | null) ?? "", clientId: cid as string, start: stamp(ago as number), duration: 10, serviceIds: [k % 2 ? "sv_kids" : "sv_cut"], status: st as Appointment["status"], source: "admin", createdById: "u_admin", note: "", visitId: null });
    });
  }

  // Товары и расходники по сфере: у салона не должно быть «масла для бороды».
  const P = (id: string, name: string, category: string, stock: number, minStock: number, cost: number, price: number): Product => ({ id, name, category, stock, minStock, cost, price, branchId: "b1" });
  const group = industry ?? "barber";
  const PRODUCTS: Record<string, Product[]> = {
    barber: [P("pr1", "Воск для волос Matte", "Укладка", 12, 5, 450, 900), P("pr2", "Масло для бороды", "Борода", 3, 5, 380, 750), P("pr3", "Шампунь мужской 250 мл", "Уход", 20, 6, 300, 600), P("pr4", "Краска камуфляж седины", "Расходники", 7, 4, 250, 0), P("pr5", "Лезвия (уп. 100)", "Расходники", 2, 2, 600, 0), P("pr6", "Чёрная маска 500 г", "Расходники", 4, 2, 900, 0)],
    beauty: [P("pr1", "Шампунь восстанавливающий", "Уход", 10, 4, 600, 1200), P("pr2", "Маска для волос", "Уход", 3, 4, 700, 1400), P("pr3", "Термозащита спрей", "Укладка", 8, 3, 450, 900), P("pr4", "Краска для волос (туба)", "Расходники", 24, 10, 350, 0), P("pr5", "Оксид 6 % 1 л", "Расходники", 2, 3, 500, 0), P("pr6", "Фольга (рулон)", "Расходники", 5, 2, 400, 0)],
    nails: [P("pr1", "Масло для кутикулы", "Уход", 15, 5, 150, 400), P("pr2", "Крем для рук", "Уход", 6, 4, 250, 600), P("pr3", "Гель-лак (флакон)", "Расходники", 40, 15, 300, 0), P("pr4", "База и топ", "Расходники", 3, 4, 600, 0), P("pr5", "Фрезы (набор)", "Расходники", 5, 2, 900, 0), P("pr6", "Пилки (уп. 50)", "Расходники", 2, 2, 500, 0)],
    brows: [P("pr1", "Гель для бровей", "Уход", 9, 4, 300, 700), P("pr2", "Сыворотка для ресниц", "Уход", 4, 3, 900, 1800), P("pr3", "Ресницы для наращивания (лоток)", "Расходники", 18, 8, 450, 0), P("pr4", "Клей для ресниц", "Расходники", 2, 3, 900, 0), P("pr5", "Хна для бровей", "Расходники", 6, 3, 500, 0), P("pr6", "Составы для ламинирования", "Расходники", 3, 2, 1200, 0)],
    cosmetology: [P("pr1", "Крем SPF 50", "Уход", 7, 4, 900, 1900), P("pr2", "Сыворотка с витамином C", "Уход", 3, 3, 1300, 2600), P("pr3", "Пилинг-состав (флакон)", "Расходники", 5, 2, 1800, 0), P("pr4", "Гиалуроновый препарат (шприц)", "Расходники", 4, 3, 3500, 0), P("pr5", "Перчатки нитрил (уп.)", "Расходники", 6, 3, 450, 0), P("pr6", "Маска альгинатная (уп.)", "Расходники", 2, 2, 800, 0)],
    tattoo: [P("pr1", "Заживляющий крем", "Уход", 14, 5, 250, 600), P("pr2", "Плёнка для заживления", "Уход", 5, 4, 400, 900), P("pr3", "Пигменты (флакон)", "Расходники", 22, 8, 700, 0), P("pr4", "Картриджи (уп. 20)", "Расходники", 3, 4, 900, 0), P("pr5", "Перчатки нитрил (уп.)", "Расходники", 6, 3, 450, 0), P("pr6", "Трансферная бумага", "Расходники", 2, 2, 600, 0)],
    procedure: [P("pr1", "Витамины группы B (уп.)", "Препараты", 12, 5, 300, 0), P("pr2", "Физраствор 200 мл", "Расходники", 30, 15, 60, 0), P("pr3", "Шприцы 5 мл (уп. 100)", "Расходники", 2, 3, 900, 0), P("pr4", "Системы для капельниц", "Расходники", 25, 10, 40, 0), P("pr5", "Перчатки нитрил (уп.)", "Расходники", 6, 3, 450, 0), P("pr6", "Спиртовые салфетки (уп.)", "Расходники", 4, 3, 150, 0)],
    massage: [P("pr1", "Массажное масло 500 мл", "Расходники", 8, 4, 600, 0), P("pr2", "Крем для массажа", "Расходники", 3, 4, 500, 0), P("pr3", "Ароматическое масло", "Уход", 10, 3, 300, 700), P("pr4", "Одноразовые простыни (уп.)", "Расходники", 5, 3, 700, 0), P("pr5", "Камни для стоун-терапии", "Инвентарь", 1, 1, 4000, 0), P("pr6", "Бальзам для тела", "Уход", 6, 3, 450, 1000)],
    spa: [P("pr1", "Соль для ванн", "Уход", 12, 4, 300, 700), P("pr2", "Скраб для тела", "Уход", 3, 4, 500, 1100), P("pr3", "Веники берёзовые", "Расходники", 20, 10, 150, 0), P("pr4", "Одноразовые тапочки (уп.)", "Расходники", 4, 4, 600, 0), P("pr5", "Чай травяной (кг)", "Бар", 2, 2, 900, 0), P("pr6", "Полотенца одноразовые (уп.)", "Расходники", 6, 3, 800, 0)],
    other: [P("pr1", "Товар для продажи", "Товары", 10, 4, 300, 700), P("pr2", "Подарочный сертификат", "Товары", 20, 5, 0, 1000), P("pr3", "Расходник 1", "Расходники", 8, 3, 200, 0), P("pr4", "Расходник 2", "Расходники", 2, 3, 400, 0), P("pr5", "Перчатки (уп.)", "Расходники", 6, 3, 450, 0), P("pr6", "Салфетки (уп.)", "Расходники", 4, 3, 150, 0)],
  };
  const products: Product[] = PRODUCTS[group] ?? PRODUCTS.barber;
  const registers: CashRegister[] = [
    { id: "r_cash_b1", branchId: "b1", name: "Наличные", kind: "cash" },
    { id: "r_card_b1", branchId: "b1", name: "Терминал", kind: "card" },
    { id: "r_cash_b2", branchId: "b2", name: "Наличные", kind: "cash" },
  ];
  const cashOps: CashOperation[] = [];
  for (const v of visits) {
    if (v.payment.cash > 0) cashOps.push({ id: `co-${v.id}-c`, branchId: v.branchId, registerId: v.branchId === "b1" ? "r_cash_b1" : "r_cash_b2", date: v.closedAt, kind: "in", article: "Услуги", amount: v.payment.cash, staffId: v.staffId, comment: "", refType: "visit", refId: v.id });
    if (v.payment.card > 0) cashOps.push({ id: `co-${v.id}-k`, branchId: v.branchId, registerId: "r_card_b1", date: v.closedAt, kind: "in", article: "Услуги", amount: v.payment.card, staffId: v.staffId, comment: "", refType: "visit", refId: v.id });
  }
  const curPeriod = periodOf(today);
  const prevPeriod = addMonths(curPeriod, -1);
  for (const p of [prevPeriod, curPeriod]) {
    cashOps.push({ id: `co-rent-${p}`, branchId: "b1", registerId: "r_cash_b1", date: `${p}-05T12:00`, kind: "out", article: "Аренда", amount: 60000, staffId: "u_owner", comment: "Аренда помещения", refType: null, refId: null });
    cashOps.push({ id: `co-mat-${p}`, branchId: "b1", registerId: "r_cash_b1", date: `${p}-10T15:00`, kind: "out", article: "Материалы", amount: 18500, staffId: "u_admin", comment: "Закупка расходников", refType: "receipt", refId: null });
  }
  // Расход администратора выше лимита: ждёт подтверждения владельца.
  cashOps.push({ id: "co-pending-1", branchId: "b1", registerId: "r_cash_b1", date: `${today}T11:30`, kind: "out", article: "Прочее", amount: 14000, staffId: "u_admin", comment: "Ремонт кондиционера", refType: null, refId: null, status: "pending" });

  const requests: BookingRequest[] = [
    { id: "rq1", branchId: "b1", clientName: "Бакыт Омуров", phone: "+996 555 101 202", serviceId: "sv_combo", serviceIds: ["sv_combo"], comment: "", staffId: "u_azamat", wishedAt: `${addDays(today, 1)}T18:00`, source: "bot", status: "new", createdAt: `${today}T09:12` },
    { id: "rq2", branchId: "b1", clientName: "Санжар Исаков", phone: "+996 770 303 404", serviceId: "sv_cut", serviceIds: ["sv_cut"], comment: "", staffId: null, wishedAt: null, source: "online", status: "new", createdAt: `${today}T10:40` },
    { id: "rq3", branchId: "b1", clientName: "Марат Эсенов", phone: "+996 700 505 606", serviceId: "sv_beard", serviceIds: ["sv_beard"], comment: "", staffId: "u_bekzhan", wishedAt: `${addDays(today, 2)}T12:00`, source: "bot", status: "new", createdAt: `${today}T11:05` },
    { id: "rq4", branchId: "b1", clientName: "Элдар Шамшиев", phone: "+996 555 707 808", serviceId: "sv_kids", serviceIds: ["sv_kids"], comment: "", staffId: null, wishedAt: `${addDays(today, -1)}T16:00`, source: "online", status: "converted", createdAt: `${addDays(today, -2)}T18:30` },
  ];
  const documents: ClientDocument[] = [
    { id: "d1", clientId: "cl1", type: "consent", title: "Согласие на обработку данных", date: addDays(today, -30), addedById: "u_admin" },
    { id: "d2", clientId: "cl1", type: "photo", title: `Фото до/после, ${services[0]?.name.toLowerCase() ?? ""}`, date: addDays(today, -12), addedById: "u_azamat" },
    { id: "d3", clientId: "cl2", type: "consent", title: "Согласие на обработку данных", date: addDays(today, -8), addedById: "u_admin" },
  ];
  const audit: AuditEntry[] = [
    { id: "a1", at: `${addDays(today, -1)}T18:42`, staffId: "u_admin", entity: "appointment", entityId: "ap10", action: "update", summary: "Перенос записи: 15:00 → 16:30" },
    { id: "a2", at: `${addDays(today, -1)}T12:10`, staffId: "u_owner", entity: "service", entityId: "sv_cut", action: "update", summary: `Цена «${services[0]?.name ?? ""}»: ${(Math.round((services[0]?.price ?? 800) * 0.94 / 10) * 10).toLocaleString("ru-RU")} → ${(services[0]?.price ?? 800).toLocaleString("ru-RU")} с` },
    { id: "a3", at: `${addDays(today, -3)}T20:05`, staffId: "u_admin", entity: "visit", entityId: "v40", action: "update", summary: `Скидка 10 % на «${services[4]?.name ?? ""}», за счёт салона` },
    { id: "a4", at: `${addDays(today, -7)}T10:00`, staffId: "u_owner", entity: "scheme", entityId: "s_barber", action: "update", summary: `Схема «${posName("p_barber")}»: добавлен бонус 10 % при 8 записях в день` },
  ];
  const payslips: Payslip[] = staff
    .filter((s) => s.schemeId)
    .flatMap((s) => [
      // Прошлый месяц утверждён и ждёт выплаты: выплат в примере нет, поэтому не «Выплачена».
      { id: `ps-${s.id}-${prevPeriod}`, staffId: s.id, period: prevPeriod, status: "approved" as const, acknowledgedAt: `${curPeriod}-02T10:00`, disputes: [] },
      { id: `ps-${s.id}-${curPeriod}`, staffId: s.id, period: curPeriod, status: "draft" as const, acknowledgedAt: null, disputes: [] },
    ]);
  const payouts: Payout[] = [
    { id: "po1", staffId: "u_azamat", period: curPeriod, amount: 8000, date: `${curPeriod}-${today.slice(8, 10) < "15" ? "01" : "15"}`, registerId: "r_cash_b1", kind: "advance" },
    { id: "po2", staffId: "u_bekzhan", period: curPeriod, amount: 5000, date: `${curPeriod}-${today.slice(8, 10) < "15" ? "01" : "15"}`, registerId: "r_cash_b1", kind: "advance" },
  ];
  const adjustments: Adjustment[] = [
    { id: "adj1", staffId: "u_nurlan", date: `${curPeriod}-08`, amount: 1500, reason: "Премия: отзыв 5★ от клиента" },
    { id: "adj2", staffId: "u_emir", date: `${curPeriod}-11`, amount: -500, reason: "Опоздание на смену 40 минут" },
  ];
  // Абонементы: два шаблона по сфере (первые услуги профиля) и пара проданных клиентам.
  const svc0 = services.find((s) => !s.addon);
  const svc1 = services.filter((s) => !s.addon)[3] ?? svc0;
  const packages: PackageTemplate[] = svc0 && svc1 ? [
    { id: "pk1", name: `${svc0.name} × 5`, serviceIds: [svc0.id], visits: 5, validDays: 90, price: Math.round(svc0.price * 5 * 0.85), active: true },
    { id: "pk2", name: `${svc1.name} × 10`, serviceIds: [svc1.id], visits: 10, validDays: 180, price: Math.round(svc1.price * 10 * 0.8), active: true },
  ] : [];
  const clientPackages: ClientPackage[] = packages.length ? [
    { id: "cp1", clientId: "cl1", templateId: "pk1", name: packages[0].name, serviceIds: packages[0].serviceIds, visitsTotal: 5, visitsUsed: 2, price: packages[0].price, purchasedAt: addDays(today, -20), expiresAt: addDays(today, 70), frozenFrom: null, status: "active", refundAmount: 0, visitId: null },
    { id: "cp2", clientId: "cl2", templateId: "pk2", name: packages[1].name, serviceIds: packages[1].serviceIds, visitsTotal: 10, visitsUsed: 9, price: packages[1].price, purchasedAt: addDays(today, -150), expiresAt: addDays(today, 30), frozenFrom: null, status: "active", refundAmount: 0, visitId: null },
  ] : [];
  void daysInPeriod;
  return {
    version: DB_VERSION,
    seededAt: toIsoLocal(new Date()),
    branches, positions, staff, categories, services, clients, appointments, visits, shifts, products, registers, cashOps, requests, documents, audit, schemes, payslips, payouts, adjustments,
    roles: DEFAULT_ROLES,
    industry,
    intake: prof.defaultIntake,
    support: [
      { id: "tk_s1", createdAt: `${addDays(today, -1)}T15:20`, topic: "setup", message: "Помогите настроить онлайн-витрину: не понимаю, как поставить шаг 20 минут", contact: "+996 700 000 001", shareAccess: false, status: "done", assignee: "Айдана", reply: "Настроили: Настройки → Онлайн-витрина → Шаг времени. Проверьте, пожалуйста." },
    ],
    companies: [
      { id: "c_bella", name: "Studio Glam", phone: "+996 555 200 300", inn: "01234567890123", industry: "beauty", intake: "schedule", branches: 1, staff: 5, plan: "paid", lastLogin: `${today}T09:12`, blocked: false, tempAccessUntil: null },
      { id: "c_med", name: "МедПункт на Масалиева", phone: "+996 770 400 500", inn: "02345678901234", industry: "procedure", intake: "flow", branches: 2, staff: 7, plan: "trial", lastLogin: `${addDays(today, -1)}T18:40`, blocked: false, tempAccessUntil: `${addDays(today, 2)}T18:40` },
      { id: "c_relax", name: "Релакс Спа", phone: "+996 700 600 700", inn: "", industry: "massage", intake: "schedule", branches: 1, staff: 3, plan: "free", lastLogin: `${addDays(today, -9)}T12:05`, blocked: false, tempAccessUntil: null },
      { id: "c_old", name: "Барбер у Алмаза", phone: "+996 555 800 900", inn: "03456789012345", industry: "barber", intake: "schedule", branches: 1, staff: 2, plan: "free", lastLogin: `${addDays(today, -40)}T10:00`, blocked: true, tempAccessUntil: null },
    ],
    supportLog: [
      { id: "sl1", at: `${addDays(today, -1)}T15:40`, agent: "Айдана", companyId: "c_self", action: "Закрыла обращение «Онлайн-витрина»: настроен шаг 20 мин" },
      { id: "sl2", at: `${addDays(today, -2)}T11:05`, agent: "Бакыт", companyId: "c_med", action: "Включил режим «Поток без записи»" },
      { id: "sl3", at: `${addDays(today, -2)}T11:00`, agent: "Бакыт", companyId: "c_med", action: "Подключил филиал «МедПункт — Сулайман-Тоо»" },
    ],
    tempAccessUntil: null,
    packages,
    clientPackages,
    closedPeriods: [],
    settings: { fotThreshold: 45, workFrom: "09:00", workTo: "21:00", slotMin: 15, unifiedAccess: true, approvalLimit: 10000, booking: DEFAULT_BOOKING, company: { ...DEFAULT_COMPANY, name: prof.companyName, legalName: prof.legalName }, receipt: DEFAULT_RECEIPT, reminders: DEFAULT_REMINDERS },
  };
}
