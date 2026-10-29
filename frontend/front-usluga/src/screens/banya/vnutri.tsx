"use client";

import { useState } from "react";
import { Icon } from "@/components/icon";

type Locker = {
  id: string;
  code: string;
  category: "male" | "female" | "vip";
  status: "free" | "busy" | "reserved" | "repair";
  guest?: string;
  tariff?: string;
  debt?: number;
  entryTime?: string;
  overageMinutes?: number;
};

const INITIAL_LOCKERS: Locker[] = [
  { id: "1", code: "М01", category: "male", status: "free" },
  { id: "2", code: "М02", category: "male", status: "busy", guest: "Азамат Т.", tariff: "3 ч (500 с)", debt: 1250, entryTime: "15:20", overageMinutes: 0 },
  { id: "3", code: "М03", category: "male", status: "busy", guest: "Бакыт С.", tariff: "3 ч (500 с)", debt: 2400, entryTime: "13:10", overageMinutes: 35 },
  { id: "4", code: "М04", category: "male", status: "reserved", guest: "Кубат К. (к 19:30)" },
  { id: "5", code: "М05", category: "male", status: "free" },
  { id: "6", code: "М06", category: "male", status: "busy", guest: "Эрлан Б.", tariff: "Безлимит (800 с)", debt: 1650, entryTime: "16:00" },
  { id: "7", code: "М07", category: "male", status: "repair" },
  { id: "8", code: "М08", category: "male", status: "free" },
  { id: "9", code: "Ж01", category: "female", status: "busy", guest: "Айгуль М.", tariff: "3 ч (500 с)", debt: 1900, entryTime: "14:40" },
  { id: "10", code: "Ж02", category: "female", status: "free" },
  { id: "11", code: "Ж03", category: "female", status: "busy", guest: "Динара К.", tariff: "3 ч (500 с)", debt: 950, entryTime: "16:15" },
  { id: "12", code: "V01", category: "vip", status: "busy", guest: "Улан С. (VIP)", tariff: "VIP 3 ч (1500 с)", debt: 6800, entryTime: "14:00", overageMinutes: 45 },
  { id: "13", code: "V02", category: "vip", status: "free" },
];

export function BathInsideScreen() {
  const [lockers, setLockers] = useState<Locker[]>(INITIAL_LOCKERS);
  const [activeCategory, setActiveCategory] = useState<"all" | "male" | "female" | "vip">("all");
  const [selectedLocker, setSelectedLocker] = useState<Locker | null>(null);
  const [searchQuery, setSearchQuery] = useState("");

  const filtered = lockers.filter((l) => {
    if (activeCategory !== "all" && l.category !== activeCategory) return false;
    if (searchQuery && !l.code.toLowerCase().includes(searchQuery.toLowerCase()) && !l.guest?.toLowerCase().includes(searchQuery.toLowerCase())) {
      return false;
    }
    return true;
  });

  const guestsInside = lockers.filter((l) => l.status === "busy").length;
  const totalDebt = lockers.filter((l) => l.status === "busy").reduce((acc, cur) => acc + (cur.debt || 0), 0);
  const freeCount = lockers.filter((l) => l.status === "free").length;
  const overageCount = lockers.filter((l) => (l.overageMinutes || 0) > 0).length;

  return (
    <div className="flex flex-col gap-6">
      {/* 4 верхних показателя */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="rounded-2xl border border-line bg-card p-4 shadow-sm">
          <div className="text-xs font-semibold text-ink-soft">Гостей внутри</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-ink">{guestsInside}</span>
            <span className="text-xs text-ink-soft">из {lockers.length} шкафчиков</span>
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-card p-4 shadow-sm">
          <div className="text-xs font-semibold text-ink-soft">Неоплаченные счета</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-primary">{totalDebt.toLocaleString()} с</span>
            <span className="text-xs font-semibold text-warn">в счетах гостей</span>
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-card p-4 shadow-sm">
          <div className="text-xs font-semibold text-ink-soft">Свободно шкафчиков</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-emerald-600">{freeCount}</span>
            <span className="text-xs text-ink-soft">ещё 1 в брони</span>
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-card p-4 shadow-sm">
          <div className="text-xs font-semibold text-ink-soft">Превысили время</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-rose-600">{overageCount}</span>
            <span className="text-xs text-rose-500 font-semibold">автодоплата по тарифу</span>
          </div>
        </div>
      </div>

      {/* Панель фильтров и поиск */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex rounded-xl bg-line/40 p-1">
          <button
            onClick={() => setActiveCategory("all")}
            className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              activeCategory === "all" ? "bg-white text-ink shadow-sm" : "text-ink-soft hover:text-ink"
            }`}
          >
            Все отделения ({lockers.length})
          </button>
          <button
            onClick={() => setActiveCategory("male")}
            className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              activeCategory === "male" ? "bg-white text-ink shadow-sm" : "text-ink-soft hover:text-ink"
            }`}
          >
            Мужское
          </button>
          <button
            onClick={() => setActiveCategory("female")}
            className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              activeCategory === "female" ? "bg-white text-ink shadow-sm" : "text-ink-soft hover:text-ink"
            }`}
          >
            Женское
          </button>
          <button
            onClick={() => setActiveCategory("vip")}
            className={`rounded-lg px-3 py-1.5 text-xs font-bold transition-all ${
              activeCategory === "vip" ? "bg-white text-ink shadow-sm" : "text-ink-soft hover:text-ink"
            }`}
          >
            VIP
          </button>
        </div>

        <div className="relative w-full sm:w-64">
          <input
            type="text"
            placeholder="Номер браслета или гость…"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-line bg-card px-3 py-1.5 text-xs font-semibold placeholder:text-ink-soft/60 focus:border-gold focus:outline-none"
          />
        </div>
      </div>

      {/* Основная рабочая область: Сетка шкафчиков + Правый сайдбар */}
      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Сетка шкафчиков (2 колонки) */}
        <div className="lg:col-span-2">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 md:grid-cols-5">
            {filtered.map((locker) => {
              const isBusy = locker.status === "busy";
              const isFree = locker.status === "free";
              const isReserved = locker.status === "reserved";
              const isRepair = locker.status === "repair";
              const hasOverage = (locker.overageMinutes || 0) > 0;

              return (
                <button
                  key={locker.id}
                  onClick={() => setSelectedLocker(locker)}
                  className={`flex flex-col justify-between rounded-xl border p-3 text-left transition-all hover:scale-[1.02] ${
                    isFree
                      ? "border-emerald-200 bg-emerald-50/50 hover:border-emerald-400"
                      : isBusy
                      ? hasOverage
                        ? "border-amber-300 bg-amber-50 hover:border-amber-400"
                        : "border-sky-200 bg-sky-50/60 hover:border-sky-400"
                      : isReserved
                      ? "border-dashed border-amber-300 bg-amber-50/30"
                      : "border-gray-200 bg-gray-50 opacity-60"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-base font-black text-ink">{locker.code}</span>
                    <span
                      className={`size-2 rounded-full ${
                        isFree
                          ? "bg-emerald-500"
                          : isBusy
                          ? hasOverage
                            ? "bg-amber-500"
                            : "bg-sky-500"
                          : isReserved
                          ? "bg-amber-400"
                          : "bg-gray-400"
                      }`}
                    />
                  </div>

                  <div className="mt-3">
                    {isFree && <div className="text-[11px] font-semibold text-emerald-700">Свободен</div>}
                    {isBusy && (
                      <div>
                        <div className="truncate text-xs font-bold text-ink">{locker.guest}</div>
                        <div className="mt-0.5 text-[11px] font-extrabold text-primary">{locker.debt?.toLocaleString()} с</div>
                        {hasOverage && <div className="text-[10px] font-bold text-amber-700">+{locker.overageMinutes} мин</div>}
                      </div>
                    )}
                    {isReserved && <div className="text-[11px] font-medium text-amber-700">{locker.guest}</div>}
                    {isRepair && <div className="text-[11px] font-semibold text-gray-400 line-through">Ремонт</div>}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Правый сайдбар: Гость уходит + Лента покупок (Realtime) */}
        <div className="flex flex-col gap-4">
          <div className="rounded-2xl border border-line bg-card p-4 shadow-sm">
            <h3 className="text-sm font-black text-ink">Быстрый расчет на выходе</h3>
            <p className="mt-1 text-xs text-ink-soft">Введите номер браслета при сдаче ключа:</p>
            <div className="mt-3 flex gap-2">
              <input
                type="text"
                placeholder="Например М03"
                className="w-full rounded-xl border border-line px-3 py-2 text-sm font-bold uppercase focus:border-gold focus:outline-none"
              />
              <button className="rounded-xl bg-gold px-4 py-2 text-xs font-black text-primary hover:brightness-105">
                Найти
              </button>
            </div>
          </div>

          <div className="rounded-2xl border border-line bg-card p-4 shadow-sm">
            <div className="flex items-center justify-between">
              <h3 className="text-sm font-black text-ink">Лента покупок в бане</h3>
              <span className="flex size-2 rounded-full bg-emerald-500 animate-pulse" />
            </div>
            <div className="mt-3 flex flex-col gap-2.5">
              <div className="rounded-xl border border-line/60 bg-bg p-2.5 text-xs">
                <div className="flex items-center justify-between font-bold text-ink">
                  <span>М03 · Пиво крафтовое × 2</span>
                  <span className="font-extrabold text-primary">360 с</span>
                </div>
                <div className="mt-1 text-[11px] text-ink-soft">Бармен Талант · долг гостя: 2 400 с</div>
              </div>

              <div className="rounded-xl border border-line/60 bg-bg p-2.5 text-xs">
                <div className="flex items-center justify-between font-bold text-ink">
                  <span>М02 · Парение дубовым веником</span>
                  <span className="font-extrabold text-primary">1 200 с</span>
                </div>
                <div className="mt-1 text-[11px] text-ink-soft">Мастер Нурлан · начислено: 360 с (30%)</div>
              </div>

              <div className="rounded-xl border border-line/60 bg-bg p-2.5 text-xs">
                <div className="flex items-center justify-between font-bold text-ink">
                  <span>V01 · Чай с горными травами</span>
                  <span className="font-extrabold text-primary">250 с</span>
                </div>
                <div className="mt-1 text-[11px] text-ink-soft">Заказ в VIP · долг гостя: 6 800 с</div>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Модалка счёта выбранного гостя */}
      {selectedLocker && selectedLocker.status === "busy" && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-line bg-card p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xl font-black text-ink">{selectedLocker.code}</span>
                <span className="ml-2 text-sm text-ink-soft">{selectedLocker.guest}</span>
              </div>
              <button
                onClick={() => setSelectedLocker(null)}
                className="rounded-lg p-1 text-ink-soft hover:bg-line/40"
              >
                ✕
              </button>
            </div>

            <div className="mt-4 rounded-xl bg-bg p-3 text-xs">
              <div className="flex justify-between py-1">
                <span className="text-ink-soft">Тариф входа:</span>
                <span className="font-bold text-ink">{selectedLocker.tariff}</span>
              </div>
              <div className="flex justify-between py-1">
                <span className="text-ink-soft">Время входа:</span>
                <span className="font-bold text-ink">{selectedLocker.entryTime}</span>
              </div>
              {(selectedLocker.overageMinutes || 0) > 0 && (
                <div className="flex justify-between py-1 text-amber-700">
                  <span>Превышение времени:</span>
                  <span className="font-extrabold">+{selectedLocker.overageMinutes} мин (доплата 100 с)</span>
                </div>
              )}
            </div>

            <div className="mt-4 flex items-center justify-between border-t border-line pt-4">
              <span className="text-sm font-semibold text-ink-soft">Текущий счёт:</span>
              <span className="text-2xl font-black text-primary">{selectedLocker.debt?.toLocaleString()} с</span>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <button
                onClick={() => setSelectedLocker(null)}
                className="rounded-xl border border-line px-4 py-2 text-xs font-bold text-ink hover:bg-line/30"
              >
                Закрыть
              </button>
              <button
                onClick={() => {
                  alert(`Переход к оплате счёта ${selectedLocker.code}`);
                  setSelectedLocker(null);
                }}
                className="rounded-xl bg-gold px-4 py-2 text-xs font-black text-primary hover:brightness-105"
              >
                К оплате на выходе
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
