"use client";

import { useState } from "react";

type UnitItem = {
  id: string;
  number: string;
  floor: number;
  type: string;
  area: number;
  ratePerSqm: number;
  status: "free" | "occupied" | "soon" | "overdue" | "reserved";
  tenant?: string;
  overdueDays?: number;
  debt?: number;
};

const INITIAL_UNITS: UnitItem[] = [
  { id: "1", number: "101", floor: 1, type: "Бутик", area: 45.0, ratePerSqm: 1200, status: "occupied", tenant: "ОсОО «LC Waikiki»", debt: 0 },
  { id: "2", number: "102", floor: 1, type: "Бутик", area: 38.5, ratePerSqm: 1200, status: "overdue", tenant: "ИП Сейдалиев Б.", overdueDays: 4, debt: 46200 },
  { id: "3", number: "103", floor: 1, type: "Островок", area: 12.0, ratePerSqm: 2500, status: "soon", tenant: "ИП Кофе Поинт", debt: 30000 },
  { id: "4", number: "104", floor: 1, type: "Бутик", area: 52.0, ratePerSqm: 1100, status: "free" },
  { id: "5", number: "105", floor: 1, type: "Островок", area: 8.0, ratePerSqm: 2500, status: "reserved", tenant: "Бронь: Азиз К." },
  { id: "6", number: "201", floor: 2, type: "Офис", area: 64.0, ratePerSqm: 900, status: "occupied", tenant: "ОсОО «ИТ Солюшнс»", debt: 0 },
  { id: "7", number: "202", floor: 2, type: "Офис", area: 42.0, ratePerSqm: 900, status: "overdue", tenant: "ОсОО «Трейд Экспорт»", overdueDays: 12, debt: 37800 },
  { id: "8", number: "203", floor: 2, type: "Офис", area: 35.0, ratePerSqm: 950, status: "free" },
  { id: "9", number: "301", floor: 3, type: "Фуд-корт", area: 85.0, ratePerSqm: 1500, status: "occupied", tenant: "KFC Osh", debt: 0 },
  { id: "10", number: "302", floor: 3, type: "Фуд-корт", area: 70.0, ratePerSqm: 1500, status: "soon", tenant: "Додо Пицца", debt: 105000 },
];

export function CommercialChessboardScreen() {
  const [units, setUnits] = useState<UnitItem[]>(INITIAL_UNITS);
  const [selectedFloor, setSelectedFloor] = useState<number | "all">("all");
  const [selectedStatus, setSelectedStatus] = useState<string>("all");
  const [selectedUnit, setSelectedUnit] = useState<UnitItem | null>(null);
  const [showAddUnitModal, setShowAddUnitModal] = useState(false);

  // Новое помещение поля формы
  const [newNumber, setNewNumber] = useState("");
  const [newFloor, setNewFloor] = useState(1);
  const [newArea, setNewArea] = useState("");
  const [newRate, setNewRate] = useState("");
  const [newType, setNewType] = useState("Бутик");

  const totalArea = units.reduce((acc, cur) => acc + cur.area, 0);
  const occupiedArea = units
    .filter((u) => u.status === "occupied" || u.status === "soon" || u.status === "overdue")
    .reduce((acc, cur) => acc + cur.area, 0);

  const occupancyPct = Math.round((occupiedArea / totalArea) * 100);
  const totalAccrued = units
    .filter((u) => u.status !== "free" && u.status !== "reserved")
    .reduce((acc, cur) => acc + cur.area * cur.ratePerSqm, 0);
  const totalDebt = units.reduce((acc, cur) => acc + (cur.debt || 0), 0);
  const totalCollected = totalAccrued - totalDebt;

  const filtered = units.filter((u) => {
    if (selectedFloor !== "all" && u.floor !== selectedFloor) return false;
    if (selectedStatus !== "all" && u.status !== selectedStatus) return false;
    return true;
  });

  const handleAddUnit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!newNumber || !newArea || !newRate) return;
    const item: UnitItem = {
      id: Date.now().toString(),
      number: newNumber,
      floor: Number(newFloor),
      type: newType,
      area: Number(newArea),
      ratePerSqm: Number(newRate),
      status: "free",
    };
    setUnits((prev) => [...prev, item]);
    setShowAddUnitModal(false);
    setNewNumber("");
    setNewArea("");
    setNewRate("");
  };

  return (
    <div className="flex flex-col gap-6">
      {/* 4 показателя сверху (из ТЗ) */}
      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <div className="rounded-2xl border border-line bg-card p-4 shadow-sm">
          <div className="text-xs font-semibold text-ink-soft">Заполняемость помещений</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-ink">{occupancyPct}%</span>
            <span className="text-xs text-ink-soft">
              {occupiedArea} из {totalArea} м²
            </span>
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-card p-4 shadow-sm">
          <div className="text-xs font-semibold text-ink-soft">Начислено за месяц</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-ink">{Math.round(totalAccrued).toLocaleString()} с</span>
            <span className="text-xs text-ink-soft">по {units.filter((u) => u.status !== "free").length} договорам</span>
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-card p-4 shadow-sm">
          <div className="text-xs font-semibold text-ink-soft">Собрано оплат</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-emerald-600">{Math.round(totalCollected).toLocaleString()} с</span>
            <span className="text-xs font-semibold text-emerald-600">
              {Math.round((totalCollected / totalAccrued) * 100)}% собираемость
            </span>
          </div>
        </div>

        <div className="rounded-2xl border border-line bg-card p-4 shadow-sm">
          <div className="text-xs font-semibold text-ink-soft">Долг арендаторов</div>
          <div className="mt-1 flex items-baseline gap-2">
            <span className="text-2xl font-black text-rose-600">{totalDebt.toLocaleString()} с</span>
            <span className="text-xs text-rose-500 font-semibold">просрочено</span>
          </div>
        </div>
      </div>

      {/* Панель фильтров по этажу и статусу + кнопка добавить */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-center gap-2">
          {/* Фильтр этажей */}
          <div className="flex rounded-xl bg-line/40 p-1 text-xs">
            <button
              onClick={() => setSelectedFloor("all")}
              className={`rounded-lg px-3 py-1.5 font-bold transition-all ${
                selectedFloor === "all" ? "bg-white text-ink shadow-sm" : "text-ink-soft hover:text-ink"
              }`}
            >
              Все этажи
            </button>
            {[1, 2, 3].map((f) => (
              <button
                key={f}
                onClick={() => setSelectedFloor(f)}
                className={`rounded-lg px-3 py-1.5 font-bold transition-all ${
                  selectedFloor === f ? "bg-white text-ink shadow-sm" : "text-ink-soft hover:text-ink"
                }`}
              >
                {f} этаж
              </button>
            ))}
          </div>

          {/* Фильтр статусов */}
          <select
            value={selectedStatus}
            onChange={(e) => setSelectedStatus(e.target.value)}
            className="rounded-xl border border-line bg-card px-3 py-1.5 text-xs font-semibold focus:border-gold focus:outline-none"
          >
            <option value="all">Все статусы</option>
            <option value="free">Свободно</option>
            <option value="occupied">В порядке (сдано)</option>
            <option value="soon">Скоро оплата</option>
            <option value="overdue">Просрочка</option>
            <option value="reserved">Бронь</option>
          </select>
        </div>

        <button
          onClick={() => setShowAddUnitModal(true)}
          className="rounded-xl bg-gold px-4 py-2 text-xs font-black text-primary transition-all hover:brightness-105"
        >
          + Помещение
        </button>
      </div>

      {/* Шахматка: Сетка ячеек помещений */}
      <div className="grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-5">
        {filtered.map((unit) => {
          const isFree = unit.status === "free";
          const isOccupied = unit.status === "occupied";
          const isSoon = unit.status === "soon";
          const isOverdue = unit.status === "overdue";
          const isReserved = unit.status === "reserved";

          return (
            <button
              key={unit.id}
              onClick={() => setSelectedUnit(unit)}
              className={`flex flex-col justify-between rounded-2xl border p-4 text-left transition-all hover:scale-[1.02] shadow-sm ${
                isFree
                  ? "border-dashed border-line bg-card hover:border-gold"
                  : isOccupied
                  ? "border-emerald-200 bg-[#DDEBE1]/40 hover:border-emerald-400"
                  : isSoon
                  ? "border-amber-200 bg-[#F3E8CF]/60 hover:border-amber-400"
                  : isOverdue
                  ? "border-rose-300 bg-[#F6E0D8]/70 hover:border-rose-400"
                  : "border-gray-200 bg-[#ECEDE0]/60"
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-base font-black text-ink">№ {unit.number}</span>
                  <span className="ml-1 text-[11px] text-ink-soft">({unit.floor} эт)</span>
                </div>
                <span className="text-[11px] font-bold text-ink-soft">{unit.area} м²</span>
              </div>

              <div className="mt-3">
                {isFree && <span className="text-xs font-bold text-ink-soft">Свободно</span>}
                {isOccupied && (
                  <div>
                    <div className="truncate text-xs font-bold text-ink">{unit.tenant}</div>
                    <div className="text-[10px] font-semibold text-emerald-700">Оплачено</div>
                  </div>
                )}
                {isSoon && (
                  <div>
                    <div className="truncate text-xs font-bold text-ink">{unit.tenant}</div>
                    <div className="text-[10px] font-extrabold text-[#7E6129]">Скоро оплата</div>
                  </div>
                )}
                {isOverdue && (
                  <div>
                    <div className="truncate text-xs font-bold text-ink">{unit.tenant}</div>
                    <div className="text-[10px] font-black text-rose-700">
                      Просрочка {unit.overdueDays} дн ({unit.debt?.toLocaleString()} с)
                    </div>
                  </div>
                )}
                {isReserved && <div className="text-xs font-semibold text-[#4A4C36]">{unit.tenant}</div>}
              </div>

              <div className="mt-3 flex items-center justify-between border-t border-line/40 pt-2 text-[10px] font-semibold text-ink-soft">
                <span>{unit.type}</span>
                <span>{unit.ratePerSqm} с/м²</span>
              </div>
            </button>
          );
        })}
      </div>

      {/* Модалка деталей выбранного помещения */}
      {selectedUnit && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-2xl border border-line bg-card p-6 shadow-2xl">
            <div className="flex items-center justify-between">
              <div>
                <span className="text-xl font-black text-ink">Помещение № {selectedUnit.number}</span>
                <span className="ml-2 text-xs text-ink-soft">{selectedUnit.type} · {selectedUnit.floor} этаж</span>
              </div>
              <button onClick={() => setSelectedUnit(null)} className="rounded-lg p-1 text-ink-soft hover:bg-line/40">
                ✕
              </button>
            </div>

            <div className="mt-4 rounded-xl bg-bg p-3 text-xs flex flex-col gap-1.5">
              <div className="flex justify-between">
                <span className="text-ink-soft">Площадь:</span>
                <span className="font-bold text-ink">{selectedUnit.area} м²</span>
              </div>
              <div className="flex justify-between">
                <span className="text-ink-soft">Ставка аренды:</span>
                <span className="font-bold text-ink">{selectedUnit.ratePerSqm} сом / м²</span>
              </div>
              <div className="flex justify-between border-t border-line/60 pt-1.5 font-bold">
                <span>Аренда в месяц:</span>
                <span className="text-primary font-black">
                  {(selectedUnit.area * selectedUnit.ratePerSqm).toLocaleString()} сом
                </span>
              </div>
              {selectedUnit.tenant && (
                <div className="flex justify-between border-t border-line/60 pt-1.5">
                  <span className="text-ink-soft">Арендатор:</span>
                  <span className="font-extrabold text-ink">{selectedUnit.tenant}</span>
                </div>
              )}
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <button
                onClick={() => setSelectedUnit(null)}
                className="rounded-xl border border-line px-4 py-2 text-xs font-bold text-ink hover:bg-line/30"
              >
                Закрыть
              </button>
              {selectedUnit.status === "free" ? (
                <button
                  onClick={() => {
                    alert(`Запуск мастера оформления договора аренды для помещения № ${selectedUnit.number}`);
                    setSelectedUnit(null);
                  }}
                  className="rounded-xl bg-gold px-4 py-2 text-xs font-black text-primary hover:brightness-105"
                >
                  Сдать помещение
                </button>
              ) : (
                <button
                  onClick={() => {
                    alert(`Переход в карточку арендатора ${selectedUnit.tenant}`);
                    setSelectedUnit(null);
                  }}
                  className="rounded-xl bg-gold px-4 py-2 text-xs font-black text-primary hover:brightness-105"
                >
                  Карточка арендатора
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* Модалка "+ Помещение" */}
      {showAddUnitModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <form onSubmit={handleAddUnit} className="w-full max-w-sm rounded-2xl border border-line bg-card p-6 shadow-2xl">
            <h3 className="text-base font-black text-ink">Добавить помещение</h3>
            <p className="mt-1 text-xs text-ink-soft">Помещение сразу появится на шахматке со статусом «Свободно».</p>

            <div className="mt-4 flex flex-col gap-3">
              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-bold text-ink-soft">Номер помещения</label>
                  <input
                    required
                    type="text"
                    placeholder="204"
                    value={newNumber}
                    onChange={(e) => setNewNumber(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-line px-3 py-2 text-xs font-semibold focus:border-gold focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-bold text-ink-soft">Этаж</label>
                  <input
                    required
                    type="number"
                    min="1"
                    max="10"
                    value={newFloor}
                    onChange={(e) => setNewFloor(Number(e.target.value))}
                    className="mt-1 w-full rounded-xl border border-line px-3 py-2 text-xs font-semibold focus:border-gold focus:outline-none"
                  />
                </div>
              </div>

              <div>
                <label className="text-[11px] font-bold text-ink-soft">Тип помещения</label>
                <select
                  value={newType}
                  onChange={(e) => setNewType(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-line bg-card px-3 py-2 text-xs font-semibold focus:border-gold focus:outline-none"
                >
                  <option value="Бутик">Бутик</option>
                  <option value="Островок">Островок</option>
                  <option value="Офис">Офис</option>
                  <option value="Склад">Склад</option>
                  <option value="Фуд-корт">Фуд-корт</option>
                  <option value="Рекламное место">Рекламное место</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-bold text-ink-soft">Площадь м²</label>
                  <input
                    required
                    type="number"
                    step="0.1"
                    placeholder="45.5"
                    value={newArea}
                    onChange={(e) => setNewArea(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-line px-3 py-2 text-xs font-semibold focus:border-gold focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-bold text-ink-soft">Ставка сом/м²</label>
                  <input
                    required
                    type="number"
                    placeholder="1000"
                    value={newRate}
                    onChange={(e) => setNewRate(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-line px-3 py-2 text-xs font-semibold focus:border-gold focus:outline-none"
                  />
                </div>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setShowAddUnitModal(false)}
                className="rounded-xl border border-line px-4 py-2 text-xs font-bold text-ink hover:bg-line/30"
              >
                Отмена
              </button>
              <button
                type="submit"
                className="rounded-xl bg-gold px-4 py-2 text-xs font-black text-primary hover:brightness-105"
              >
                Добавить
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
