// Типы данных программы «Услуги». Пока данные примерные (src/data/sample), потом те же типы — из API.

import type { Industry, IntakeMode } from "../lib/industry";

export type Id = string;

export type Branch = {
  id: Id;
  name: string;
  address: string;
  phone: string;
  hours: string;
  active: boolean;
  showcaseOnly: boolean; // «для рекламы»: виден клиентам, без записи
};

export type Position = { id: Id; name: string };

export type Role = "owner" | "admin" | "master";
export type Employment = "staff" | "contract" | "self_employed" | "rent";

// Роль доступа: какие разделы открыты. Владелец и Администратор встроенные, их нельзя менять и удалять.
export type AccessLevel = "view" | "manage";
// Уровень по разделу: нет записи = раздел скрыт, view = только смотреть, manage = смотреть и менять.
export type AccessMap = Record<string, AccessLevel>;

export type AccessRole = {
  id: Id;
  name: string;
  pages: string[]; // какие разделы видны (для совместимости); уровни — в access
  access: AccessMap;
  builtin: boolean;
  ownOnly: boolean; // видит только свои записи, смены и зарплату (как мастер)
};

export type Staff = {
  id: Id;
  name: string;
  phone: string;
  positionId: Id;
  branchIds: Id[];
  role: Role; // поведение: owner — всё, admin — филиал, master — только своё (выводится из роли доступа)
  roleId: Id; // роль доступа из db.roles
  pages: string[] | null; // индивидуальный доступ, когда «Единый доступ» выключен; null = как у роли
  access: AccessMap | null; // уровни индивидуального доступа; null = как у роли
  employment: Employment;
  hiredAt: string; // YYYY-MM-DD
  active: boolean;
  schemeId: Id | null;
  serviceIds: Id[];
  color: string; // цвет колонки в журнале
};

export type ServiceCategory = { id: Id; name: string };

export type Service = {
  id: Id;
  name: string;
  categoryId: Id;
  duration: number; // минут
  price: number;
  pricesByPosition: Record<Id, number>; // цена по должности (грейду), если отличается
  addon: boolean; // доп. услуга
  materialsCost: number; // техкарта: стоимость материалов на одну услугу
  discountAtExpense: "salon" | "master"; // чья скидка при расчёте зарплаты
  online: boolean;
  active: boolean;
};

export type ClientCategory = "new" | "regular" | "vip" | "blacklist";

export type Client = {
  id: Id;
  name: string;
  phone: string;
  birthday: string | null;
  category: ClientCategory;
  notes: string;
  consent: boolean;
  createdAt: string;
};

export type AppointmentStatus = "pending" | "confirmed" | "arrived" | "no_show" | "paid" | "canceled";
export type AppointmentSource = "admin" | "online" | "bot";

export type Appointment = {
  id: Id;
  branchId: Id;
  staffId: Id;
  clientId: Id;
  start: string; // ISO local, например 2026-10-12T10:00
  duration: number;
  serviceIds: Id[];
  status: AppointmentStatus;
  source: AppointmentSource;
  createdById: Id | null; // кто оформил запись (для начисления «за запись»)
  note: string;
  visitId: Id | null;
};

// Кто делал строку и в какой доле (%). Нет поля = вся строка мастеру чека.
export type LineSplit = { staffId: Id; share: number };

export type VisitLine = {
  kind: "service" | "addon" | "product" | "package";
  refId: Id;
  name: string;
  price: number;
  qty: number;
  discount: number; // сумма скидки на строку
  discountAtExpense: "salon" | "master";
  materialsCost: number;
  splits?: LineSplit[]; // делёж строки между исполнителями
  packageId?: Id; // услуга списана с абонемента клиента: к оплате 0, цена = цена одного посещения
};

export type Visit = {
  id: Id;
  appointmentId: Id | null;
  branchId: Id;
  staffId: Id;
  clientId: Id | null;
  closedAt: string; // ISO local
  closedById: Id | null;
  lines: VisitLine[];
  tip: number;
  tipChannel: "cash_register" | "direct";
  payment: { cash: number; card: number; balance: number };
  total: number;
  refundedAt: string | null;
  refundAmount: number;
};

export type Shift = {
  id: Id;
  staffId: Id;
  branchId: Id;
  date: string; // YYYY-MM-DD
  from: string; // HH:MM
  to: string;
  breakMin: number;
  fact: "planned" | "worked" | "missed";
  absence?: "absent" | "vacation" | "sick" | "dayoff"; // причина, если fact = missed
  lateMin?: number; // опоздание, минут
  earlyMin?: number; // ранний уход, минут
};

export type Product = {
  id: Id;
  name: string;
  category: string;
  stock: number;
  minStock: number;
  cost: number;
  price: number;
  branchId: Id;
};

export type CashRegister = { id: Id; branchId: Id; name: string; kind: "cash" | "card" };

export type CashOperation = {
  id: Id;
  branchId: Id;
  registerId: Id;
  date: string; // ISO local
  kind: "in" | "out";
  article: string;
  amount: number;
  staffId: Id | null;
  comment: string;
  refType: "visit" | "payout" | "receipt" | null;
  refId: Id | null;
  stornoOf?: Id; // обратная операция к ошибочной: проведённое не удаляется, а сторнируется
  status?: "pending" | "approved" | "rejected"; // расход выше лимита ждёт подтверждения владельца; нет поля = проведена
  approvedById?: Id;
};

// Абонемент (шаблон): пакет посещений по выбранным услугам на срок.
export type PackageTemplate = {
  id: Id;
  name: string;
  serviceIds: Id[];
  visits: number;
  validDays: number;
  price: number;
  active: boolean;
};

// Абонемент, купленный клиентом.
export type ClientPackage = {
  id: Id;
  clientId: Id;
  templateId: Id;
  name: string;
  serviceIds: Id[];
  visitsTotal: number;
  visitsUsed: number;
  price: number;
  purchasedAt: string; // YYYY-MM-DD
  expiresAt: string; // YYYY-MM-DD, сдвигается на дни заморозки
  frozenFrom: string | null;
  status: "active" | "refunded";
  refundAmount: number;
  visitId: Id | null; // чек продажи
};

// Напоминания клиентам о записи.
export type ReminderSettings = {
  enabled: boolean;
  hoursBefore: number[];
  channel: "whatsapp" | "sms" | "telegram";
  template: string;
};

// Закрытый месяц: начисления заморожены снимком, правки задним числом запрещены.
export type ClosedPeriod = {
  period: string; // YYYY-MM
  closedAt: string;
  closedById: Id | null;
  snapshot: Accrual[]; // начисления на момент закрытия (с расшифровкой)
};

export type BookingRequest = {
  id: Id;
  branchId: Id;
  clientName: string;
  phone: string;
  serviceId: Id | null; // первая услуга (для старых записей)
  serviceIds: Id[];
  comment: string;
  staffId: Id | null;
  wishedAt: string | null; // ISO или null = любое время
  source: AppointmentSource;
  status: "new" | "confirmed" | "declined" | "converted";
  createdAt: string;
};

// Настройки онлайн-витрины (публичная страница записи).
export type BookingSettings = {
  enabled: boolean;
  title: string;
  intro: string;
  slotMin: number; // шаг слотов
  leadHours: number; // минимум часов до записи
  showPrices: boolean;
  chooseMaster: boolean;
  maxDays: number; // на сколько дней вперёд
};

// Реквизиты компании («Моя компания» на сайте NurCRM).
export type CompanySettings = {
  name: string;
  legalName: string;
  inn: string;
  okpo: string;
  account: string;
  bik: string;
  address: string;
  phones: string; // телефоны для витрины / WhatsApp, через запятую
};

// Чековое оборудование: принтер чеков.
export type ReceiptSettings = {
  connection: "none" | "usb" | "network" | "bluetooth";
  model: string;
  address: string; // IP или имя устройства
  paperWidth: 58 | 80;
  autoPrint: boolean;
  printLogo: boolean;
  footer: string;
};

// Обращение в техподдержку.
export type SupportTicket = {
  id: Id;
  createdAt: string;
  topic: "industry" | "setup" | "bug" | "other";
  message: string;
  contact: string;
  shareAccess: boolean; // передать поддержке временный доступ
  status: "new" | "in_progress" | "done";
  companyId?: Id; // для панели поддержки: чьё обращение (нет = текущая компания)
  assignee?: string; // кто из поддержки взял
  reply?: string; // ответ клиенту
};

// Запись в журнале действий поддержки.
export type SupportLogEntry = {
  id: Id;
  at: string;
  agent: string;
  companyId: Id;
  action: string;
};

// Другие компании в панели поддержки (примерные). Текущая компания хранится в DB целиком.
export type CompanyCard = {
  id: Id;
  name: string;
  phone: string;
  inn: string;
  industry: Industry;
  intake: IntakeMode;
  branches: number;
  staff: number;
  plan: "free" | "trial" | "paid";
  lastLogin: string;
  blocked: boolean;
  tempAccessUntil: string | null; // временный доступ поддержки
};

export type ClientDocument = {
  id: Id;
  clientId: Id;
  type: "consent" | "contract" | "photo" | "file";
  title: string;
  date: string;
  addedById: Id | null;
};

export type AuditEntry = {
  id: Id;
  at: string;
  staffId: Id | null;
  entity: string;
  entityId: Id;
  action: "create" | "update" | "delete";
  summary: string;
};

// ----- Зарплата -----

export type RateMode = "percent" | "fixed";

export type SchemeComponent =
  | {
      kind: "service_rate"; // ставка за услугу: % или фикс, с переопределением по услуге
      mode: RateMode;
      value: number;
      overrides: { serviceId: Id; mode: RateMode; value: number }[];
      deductMaterials: boolean; // вычитать материалы по техкарте из базы
    }
  | {
      kind: "booking_fee"; // за оформленную запись: фикс или % от чека (тому, кто оформил)
      mode: RateMode;
      value: number;
    }
  | { kind: "monthly_salary"; amount: number } // оклад за месяц
  | {
      kind: "daily_count_bonus"; // выполнил за день N записей → X % от выручки дня
      tiers: { minCount: number; percent: number }[];
    }
  | {
      kind: "branch_revenue_share"; // администратору: % от выручки филиала за месяц при пороге
      percent: number;
      threshold: number;
      metric: "revenue" | "profit";
    }
  | {
      kind: "shift_rate"; // за отработанную смену или за час по табелю (fact = worked)
      mode: "per_shift" | "per_hour";
      value: number;
    }
  | {
      kind: "stepped_percent"; // ступенчатый % от личного оборота за месяц: чем больше оборот, тем выше %
      tiers: { minRevenue: number; percent: number }[];
    };

export type Scheme = {
  id: Id;
  name: string;
  positionId: Id | null;
  effectiveFrom: string; // YYYY-MM-DD
  components: SchemeComponent[];
};

export type AccrualSource = "visit" | "booking" | "salary" | "daily_bonus" | "branch_share" | "shift" | "stepped" | "refund" | "adjustment";

export type Accrual = {
  id: Id;
  staffId: Id;
  branchId: Id;
  date: string; // YYYY-MM-DD
  period: string; // YYYY-MM
  source: AccrualSource;
  sourceId: Id;
  componentKind: SchemeComponent["kind"] | "manual";
  base: number;
  rateText: string;
  amount: number;
  explanation: string;
};

export type PayslipStatus = "draft" | "review" | "acknowledged" | "disputed" | "approved" | "paid";

export type Dispute = { accrualId: Id; comment: string; reply: string; status: "open" | "resolved" };

export type Payslip = {
  id: Id;
  staffId: Id;
  period: string;
  status: PayslipStatus;
  acknowledgedAt: string | null;
  disputes: Dispute[];
};

export type Payout = {
  id: Id;
  staffId: Id;
  period: string;
  amount: number;
  date: string;
  registerId: Id;
  kind: "advance" | "final";
};

export type Adjustment = {
  id: Id;
  staffId: Id;
  date: string;
  amount: number; // + премия, − штраф/вычет
  reason: string;
};
