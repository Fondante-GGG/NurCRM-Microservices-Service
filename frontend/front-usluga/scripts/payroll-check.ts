// Проверка правил расчёта на примерах. Запуск: node scripts/payroll-check.ts
// Эти же примеры — приёмочные тесты для бэкенда.
import { computeAccruals, sumBy } from "../src/lib/payroll/calc.ts";
import type { Scheme, Service, Staff, Visit, Appointment, Shift } from "../src/data/types.ts";

const services: Service[] = [
  { id: "cut", name: "Стрижка", categoryId: "c", duration: 45, price: 1500, pricesByPosition: {}, addon: false, materialsCost: 50, discountAtExpense: "salon", online: true, active: true },
  { id: "kids", name: "Детская", categoryId: "c", duration: 30, price: 600, pricesByPosition: {}, addon: false, materialsCost: 30, discountAtExpense: "master", online: true, active: true },
];
const schemes: Scheme[] = [
  { id: "s1", name: "Барбер", positionId: "p", effectiveFrom: "2026-01-01", components: [
    { kind: "service_rate", mode: "percent", value: 40, overrides: [{ serviceId: "kids", mode: "fixed", value: 250 }], deductMaterials: true },
    { kind: "daily_count_bonus", tiers: [{ minCount: 2, percent: 5 }] },
  ] },
  { id: "s2", name: "Админ", positionId: "a", effectiveFrom: "2026-01-01", components: [
    { kind: "monthly_salary", amount: 25000 },
    { kind: "booking_fee", mode: "fixed", value: 20 },
    { kind: "branch_revenue_share", percent: 10, threshold: 3000, metric: "revenue" },
  ] },
  // Смена/час и ступенчатый %: отработанная смена 10:00–19:00 с перерывом 60 мин = 8 ч × 100; оборот 1850 попадает в ступень «от 1000 → 10 %»
  { id: "s3", name: "Сменщик", positionId: "p", effectiveFrom: "2026-01-01", components: [
    { kind: "shift_rate", mode: "per_hour", value: 100 },
    { kind: "stepped_percent", tiers: [{ minRevenue: 0, percent: 5 }, { minRevenue: 1000, percent: 10 }, { minRevenue: 5000, percent: 15 }] },
  ] },
];
const shifts: Shift[] = [
  { id: "sh1", staffId: "w", branchId: "b", date: "2026-10-05", from: "10:00", to: "19:00", breakMin: 60, fact: "worked" },
  { id: "sh2", staffId: "w", branchId: "b", date: "2026-10-06", from: "10:00", to: "19:00", breakMin: 0, fact: "missed" }, // не вышел — не считается
  { id: "sh3", staffId: "w", branchId: "b", date: "2026-10-07", from: "10:00", to: "14:00", breakMin: 0, fact: "planned" }, // только план — не считается
  { id: "sh4", staffId: "w", branchId: "b", date: "2026-10-08", from: "10:00", to: "14:00", breakMin: 0, fact: "worked", lateMin: 15, earlyMin: 15 }, // 4 ч − 30 мин = 3,5 ч
];
const staff: Staff[] = [
  { id: "m", name: "Мастер", phone: "", positionId: "p", branchIds: ["b"], role: "master", roleId: "r_master", pages: null, access: null, employment: "contract", hiredAt: "2026-01-01", active: true, schemeId: "s1", serviceIds: [], color: "" },
  { id: "a", name: "Админ", phone: "", positionId: "a", branchIds: ["b"], role: "admin", roleId: "r_admin", pages: null, access: null, employment: "staff", hiredAt: "2026-01-01", active: true, schemeId: "s2", serviceIds: [], color: "" },
  { id: "m2", name: "Второй мастер", phone: "", positionId: "p", branchIds: ["b3"], role: "master", roleId: "r_master", pages: null, access: null, employment: "contract", hiredAt: "2026-01-01", active: true, schemeId: "s1", serviceIds: [], color: "" },
  { id: "w", name: "Сменщик", phone: "", positionId: "p", branchIds: ["b"], role: "master", roleId: "r_master", pages: null, access: null, employment: "staff", hiredAt: "2026-01-01", active: true, schemeId: "s3", serviceIds: [], color: "" },
];
const appointments: Appointment[] = [
  { id: "ap1", branchId: "b", staffId: "m", clientId: "c1", start: "2026-10-05T10:00", duration: 45, serviceIds: ["cut"], status: "paid", source: "admin", createdById: "a", note: "", visitId: "v1" },
];
const visits: Visit[] = [
  // Стрижка 1500, скидка 150 за счёт салона (не вычитаем), материалы 50 → база 1450 × 40 % = 580
  { id: "v1", appointmentId: "ap1", branchId: "b", staffId: "m", clientId: "c1", closedAt: "2026-10-05T11:00", closedById: "a",
    lines: [{ kind: "service", refId: "cut", name: "Стрижка", price: 1500, qty: 1, discount: 150, discountAtExpense: "salon", materialsCost: 50 }],
    tip: 0, tipChannel: "direct", payment: { cash: 1350, card: 0, balance: 0 }, total: 1350, refundedAt: null, refundAmount: 0 },
  // Детская 600, скидка 100 за счёт мастера, фикс 250 → 250 (фикс не зависит от базы)
  { id: "v2", appointmentId: null, branchId: "b", staffId: "m", clientId: "c2", closedAt: "2026-10-05T12:00", closedById: null,
    lines: [{ kind: "service", refId: "kids", name: "Детская", price: 600, qty: 1, discount: 100, discountAtExpense: "master", materialsCost: 30 }],
    tip: 0, tipChannel: "direct", payment: { cash: 500, card: 0, balance: 0 }, total: 500, refundedAt: null, refundAmount: 0 },
  // Чек в другом месяце — в октябрь не попадает
  { id: "v3", appointmentId: null, branchId: "b", staffId: "m", clientId: "c3", closedAt: "2026-09-30T12:00", closedById: null,
    lines: [{ kind: "service", refId: "cut", name: "Стрижка", price: 1500, qty: 1, discount: 0, discountAtExpense: "salon", materialsCost: 50 }],
    tip: 0, tipChannel: "direct", payment: { cash: 1500, card: 0, balance: 0 }, total: 1500, refundedAt: null, refundAmount: 0 },
  // Чек 2000 с возвратом в октябре: начисление 780 в сентябре, сторно −780 в октябре
  { id: "v4", appointmentId: null, branchId: "b", staffId: "m", clientId: "c4", closedAt: "2026-09-20T12:00", closedById: null,
    lines: [{ kind: "service", refId: "cut", name: "Стрижка", price: 2000, qty: 1, discount: 0, discountAtExpense: "salon", materialsCost: 50 }],
    tip: 0, tipChannel: "direct", payment: { cash: 2000, card: 0, balance: 0 }, total: 2000, refundedAt: "2026-10-02T10:00", refundAmount: 2000 },
  // Делёж строки: стрижка 1000 без материалов, мастер 60 % / второй мастер 40 %; строка абонемента 5000 не начисляется никому
  { id: "v7", appointmentId: null, branchId: "b3", staffId: "m", clientId: "c7", closedAt: "2026-10-20T12:00", closedById: null,
    lines: [
      { kind: "service", refId: "cut", name: "Стрижка", price: 1000, qty: 1, discount: 0, discountAtExpense: "salon", materialsCost: 0, splits: [{ staffId: "m", share: 60 }, { staffId: "m2", share: 40 }] },
      { kind: "package", refId: "pk1", name: "Абонемент", price: 5000, qty: 1, discount: 0, discountAtExpense: "salon", materialsCost: 0 },
    ],
    tip: 0, tipChannel: "direct", payment: { cash: 6000, card: 0, balance: 0 }, total: 6000, refundedAt: null, refundAmount: 0 },
  // Сменщик (другой филиал b2, чтобы не менять выручку филиала b): два чека 1350 + 500 = 1850 оборота
  { id: "v5", appointmentId: null, branchId: "b2", staffId: "w", clientId: "c5", closedAt: "2026-10-05T13:00", closedById: null,
    lines: [{ kind: "service", refId: "cut", name: "Стрижка", price: 1350, qty: 1, discount: 0, discountAtExpense: "salon", materialsCost: 50 }],
    tip: 0, tipChannel: "direct", payment: { cash: 1350, card: 0, balance: 0 }, total: 1350, refundedAt: null, refundAmount: 0 },
  { id: "v6", appointmentId: null, branchId: "b2", staffId: "w", clientId: "c6", closedAt: "2026-10-07T13:00", closedById: null,
    lines: [{ kind: "service", refId: "kids", name: "Детская", price: 500, qty: 1, discount: 0, discountAtExpense: "salon", materialsCost: 30 }],
    tip: 0, tipChannel: "direct", payment: { cash: 500, card: 0, balance: 0 }, total: 500, refundedAt: null, refundAmount: 0 },
];

const acc = computeAccruals({ period: "2026-10", staff, schemes, services, visits, appointments, adjustments: [], shifts });
let failed = 0;
function expect(name: string, actual: number, wanted: number) {
  const ok = Math.abs(actual - wanted) < 0.005;
  if (!ok) failed++;
  console.log(`${ok ? "ok  " : "FAIL"} ${name}: ${actual} (ожидалось ${wanted})`);
}
const of = (staffId: string, source?: string) => acc.filter((a) => a.staffId === staffId && (!source || a.source === source));

expect("стрижка со скидкой салона: 1450 × 40 %", of("m", "visit").find((a) => a.sourceId === "v1")!.amount, 580);
expect("детская: фикс 250", of("m", "visit").find((a) => a.sourceId === "v2")!.amount, 250);
expect("бонус за 2 записи в день: 5 % от (1350+500)", sumBy(of("m", "daily_bonus"), (a) => a.amount), 92.5);
expect("сторно возврата сентябрьского чека: −(2000−50)×40 %", sumBy(of("m", "refund"), (a) => a.amount), -780);
expect("делёж строки: мастеру 60 % от 1000 × 40 %", of("m", "visit").find((a) => a.sourceId === "v7")!.amount, 240);
expect("делёж строки: второму мастеру 40 % от 1000 × 40 %", sumBy(of("m2", "visit"), (a) => a.amount), 160);
expect("строка абонемента не начисляется", acc.filter((a) => a.sourceId === "v7").length, 2);
expect("итого мастер за октябрь", sumBy(of("m"), (a) => a.amount), 580 + 250 + 92.5 - 780 + 240);
expect("за час: 8 ч + (4 ч − опоздание 15 − ранний уход 15 = 3,5 ч), пропуск и план не считаются", sumBy(of("w", "shift"), (a) => a.amount), 800 + 350);
expect("ступенчатый %: оборот 1850 → ступень от 1000 → 10 %", sumBy(of("w", "stepped"), (a) => a.amount), 185);
expect("админ: оклад", sumBy(of("a", "salary"), (a) => a.amount), 25000);
expect("админ: за запись (одна оформленная)", sumBy(of("a", "booking"), (a) => a.amount), 20);
expect("админ: доля филиала — выручка октября 1850 < 3000 → 0", sumBy(of("a", "branch_share"), (a) => a.amount), 0);
console.log(failed ? `\n${failed} проверок не прошло` : "\nВсе проверки прошли");
process.exit(failed ? 1 : 0);
