"use client";

import { useState } from "react";

type MasterServiceItem = {
  id: string;
  name: string;
  price: number;
  duration: string;
};

const MASTER_SERVICES: MasterServiceItem[] = [
  { id: "1", name: "Парение дубовым веником", price: 1200, duration: "25 мин" },
  { id: "2", name: "Парение березовым веником с травами", price: 1500, duration: "30 мин" },
  { id: "3", name: "Массаж классический общий", price: 2000, duration: "45 мин" },
  { id: "4", name: "Массаж спины и шейно-воротниковой зоны", price: 1200, duration: "30 мин" },
  { id: "5", name: "Солевой пилинг всего тела", price: 1000, duration: "20 мин" },
  { id: "6", name: "Медовое растирание", price: 800, duration: "15 мин" },
];

export function BathMasterServicesScreen() {
  const [braceletNumber, setBraceletNumber] = useState("М03");
  const [selectedService, setSelectedService] = useState<MasterServiceItem | null>(MASTER_SERVICES[0]);
  const [selectedMaster, setSelectedMaster] = useState("Нурлан Б. (Банщик)");
  const [masterSharePct] = useState(30);

  const mastersOnShift = [
    "Нурлан Б. (Банщик)",
    "Алмаз К. (Массажист)",
    "Айдар С. (Банщик)",
  ];

  const calculatedCommission = selectedService
    ? Math.round((selectedService.price * masterSharePct) / 100)
    : 0;

  return (
    <div className="flex flex-col gap-6">
      <div className="rounded-2xl border border-line bg-card p-5 shadow-sm">
        <h2 className="text-base font-black text-ink">Запись услуги мастера в счёт гостя</h2>
        <p className="mt-1 text-xs text-ink-soft">
          Мастер отмечает оказанную процедуру: сумма уходит в долг гостя, а процент начисляется мастеру.
        </p>

        <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-2">
          <div>
            <label className="text-xs font-bold text-ink-soft">Номер браслета гостя</label>
            <input
              type="text"
              value={braceletNumber}
              onChange={(e) => setBraceletNumber(e.target.value.toUpperCase())}
              placeholder="Например М03"
              className="mt-1 w-full rounded-xl border border-line px-3 py-2 text-base font-black uppercase text-primary focus:border-gold focus:outline-none"
            />
          </div>

          <div>
            <label className="text-xs font-bold text-ink-soft">Кто оказал услугу (мастера на смене)</label>
            <select
              value={selectedMaster}
              onChange={(e) => setSelectedMaster(e.target.value)}
              className="mt-1 w-full rounded-xl border border-line bg-card px-3 py-2 text-xs font-bold focus:border-gold focus:outline-none"
            >
              {mastersOnShift.map((m) => (
                <option key={m} value={m}>
                  {m}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Список услуг (плитки) */}
        <div className="lg:col-span-2">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            {MASTER_SERVICES.map((s) => {
              const isSelected = selectedService?.id === s.id;
              return (
                <button
                  key={s.id}
                  onClick={() => setSelectedService(s)}
                  className={`flex flex-col justify-between rounded-2xl border p-4 text-left transition-all hover:scale-[1.01] ${
                    isSelected
                      ? "border-gold bg-gold/10 shadow-sm ring-1 ring-gold"
                      : "border-line bg-card hover:border-line-soft"
                  }`}
                >
                  <div className="flex items-center justify-between">
                    <span className="text-sm font-bold text-ink">{s.name}</span>
                    <span className="text-xs font-semibold text-ink-soft">{s.duration}</span>
                  </div>
                  <div className="mt-3 flex items-baseline justify-between">
                    <span className="text-base font-black text-primary">{s.price.toLocaleString()} сом</span>
                    <span className="text-[11px] font-bold text-emerald-600">
                      мастеру: +{Math.round((s.price * masterSharePct) / 100)} с ({masterSharePct}%)
                    </span>
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Сводка и подтверждение записи */}
        <div className="rounded-2xl border border-line bg-card p-5 shadow-sm">
          <h3 className="text-xs font-bold uppercase text-ink-soft">Проверьте перед записью</h3>

          {selectedService ? (
            <div className="mt-4 flex flex-col gap-3">
              <div className="rounded-xl bg-bg p-3 text-xs">
                <div className="text-ink-soft">Браслет:</div>
                <div className="text-lg font-black text-ink">{braceletNumber}</div>
              </div>

              <div className="rounded-xl bg-bg p-3 text-xs">
                <div className="text-ink-soft">Услуга:</div>
                <div className="font-bold text-ink">{selectedService.name}</div>
                <div className="mt-1 text-base font-black text-primary">{selectedService.price} сом</div>
              </div>

              <div className="rounded-xl border border-emerald-200 bg-emerald-50/60 p-3 text-xs">
                <div className="font-bold text-emerald-800">Мастер: {selectedMaster}</div>
                <div className="mt-1 text-xs font-black text-emerald-700">
                  Начисление в зарплату: +{calculatedCommission} сом ({masterSharePct}%)
                </div>
              </div>

              <button
                onClick={() => {
                  alert(
                    `Услуга "${selectedService.name}" (${selectedService.price} с) записана на браслет ${braceletNumber}.\nМастеру начислено: ${calculatedCommission} с.`
                  );
                }}
                className="mt-3 w-full rounded-xl bg-gold py-3 text-center text-xs font-black text-primary hover:brightness-105"
              >
                Записать услугу в счёт {braceletNumber}
              </button>
            </div>
          ) : (
            <div className="py-8 text-center text-xs text-ink-soft">Выберите услугу из списка слева</div>
          )}
        </div>
      </div>
    </div>
  );
}
