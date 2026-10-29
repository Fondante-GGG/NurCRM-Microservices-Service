"use client";

import { useState } from "react";

type ActRow = {
  date: string;
  doc: string;
  debit: number;
  credit: number;
  balance: number;
};

const SAMPLE_ACT_ROWS: ActRow[] = [
  { date: "01.10.2026", doc: "Начисление аренды за Октябрь 2026 (бутик 102)", debit: 46200, credit: 0, balance: 46200 },
  { date: "08.10.2026", doc: "Оплата по чеку № 142 (Банк KICB)", debit: 0, credit: 20000, balance: 26200 },
  { date: "15.10.2026", doc: "Взыскание: Загромождение прохода (Штраф)", debit: 2000, credit: 0, balance: 28200 },
  { date: "20.10.2026", doc: "Пеня за просрочку платежа (15 дней)", debit: 393, credit: 0, balance: 28593 },
];

export function CommercialReconciliationScreen() {
  const [selectedTenant, setSelectedTenant] = useState("ИП Сейдалиев Бакыт");
  const [periodFrom, setPeriodFrom] = useState("2026-10-01");
  const [periodTo, setPeriodTo] = useState("2026-10-31");
  const [openingBalance] = useState(0);

  const totalDebit = SAMPLE_ACT_ROWS.reduce((acc, cur) => acc + cur.debit, 0);
  const totalCredit = SAMPLE_ACT_ROWS.reduce((acc, cur) => acc + cur.credit, 0);
  const closingBalance = openingBalance + totalDebit - totalCredit;

  return (
    <div className="flex flex-col gap-6">
      {/* Шапка фильтров */}
      <div className="flex flex-wrap items-center justify-between gap-4 rounded-2xl border border-line bg-card p-5 shadow-sm">
        <div className="flex flex-wrap items-center gap-3">
          <div>
            <label className="text-[11px] font-bold text-ink-soft">Арендатор</label>
            <select
              value={selectedTenant}
              onChange={(e) => setSelectedTenant(e.target.value)}
              className="mt-1 block rounded-xl border border-line bg-card px-3 py-1.5 text-xs font-bold focus:border-gold focus:outline-none"
            >
              <option value="ИП Сейдалиев Бакыт">ИП Сейдалиев Бакыт (бутик 102)</option>
              <option value="ОсОО «LC Waikiki»">ОсОО «LC Waikiki» (бутик 101)</option>
              <option value="ИП Кофе Поинт">ИП Кофе Поинт (островок 103)</option>
            </select>
          </div>

          <div>
            <label className="text-[11px] font-bold text-ink-soft">Период с</label>
            <input
              type="date"
              value={periodFrom}
              onChange={(e) => setPeriodFrom(e.target.value)}
              className="mt-1 block rounded-xl border border-line bg-card px-3 py-1 text-xs font-semibold focus:border-gold focus:outline-none"
            />
          </div>

          <div>
            <label className="text-[11px] font-bold text-ink-soft">по</label>
            <input
              type="date"
              value={periodTo}
              onChange={(e) => setPeriodTo(e.target.value)}
              className="mt-1 block rounded-xl border border-line bg-card px-3 py-1 text-xs font-semibold focus:border-gold focus:outline-none"
            />
          </div>
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => window.print()}
            className="rounded-xl border border-line bg-bg px-4 py-2 text-xs font-bold text-ink hover:bg-line/40"
          >
            Печать
          </button>
          <button
            onClick={() => alert("Выгрузка акта сверки в формате PDF...")}
            className="rounded-xl bg-gold px-4 py-2 text-xs font-black text-primary hover:brightness-105"
          >
            Скачать PDF
          </button>
        </div>
      </div>

      {/* Официальный бланк Акта сверки */}
      <div className="rounded-2xl border border-line bg-card p-8 shadow-sm">
        <div className="text-center border-b border-line pb-6">
          <h2 className="text-lg font-black text-ink uppercase tracking-wide">
            Акт сверки взаимных расчетов
          </h2>
          <p className="mt-1 text-xs text-ink-soft">
            за период с {periodFrom} по {periodTo} между Арендодателем (ОсОО «ТЦ Азия Молл») и {selectedTenant}
          </p>
        </div>

        {/* Сальдо на начало */}
        <div className="mt-6 flex justify-between bg-bg p-3 rounded-xl text-xs font-bold text-ink">
          <span>Сальдо начальное на {periodFrom}:</span>
          <span>{openingBalance.toLocaleString()} сом</span>
        </div>

        {/* Таблица строк */}
        <div className="mt-4 overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="border-b border-line text-ink-soft">
                <th className="py-2.5 font-bold">Дата</th>
                <th className="py-2.5 font-bold">Документ / Основание</th>
                <th className="py-2.5 text-right font-bold">Дебет (начислено)</th>
                <th className="py-2.5 text-right font-bold">Кредит (оплачено)</th>
                <th className="py-2.5 text-right font-bold">Текущее сальдо</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-line/60">
              {SAMPLE_ACT_ROWS.map((row, idx) => (
                <tr key={idx} className="hover:bg-line/20">
                  <td className="py-2.5 font-semibold text-ink-soft">{row.date}</td>
                  <td className="py-2.5 font-medium text-ink">{row.doc}</td>
                  <td className="py-2.5 text-right font-bold text-rose-600">
                    {row.debit > 0 ? `${row.debit.toLocaleString()} с` : "—"}
                  </td>
                  <td className="py-2.5 text-right font-bold text-emerald-600">
                    {row.credit > 0 ? `${row.credit.toLocaleString()} с` : "—"}
                  </td>
                  <td className="py-2.5 text-right font-black text-primary">
                    {row.balance.toLocaleString()} с
                  </td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-line font-black text-ink">
                <td colSpan={2} className="py-3">
                  Обороты за период:
                </td>
                <td className="py-3 text-right text-rose-600">{totalDebit.toLocaleString()} с</td>
                <td className="py-3 text-right text-emerald-600">{totalCredit.toLocaleString()} с</td>
                <td className="py-3 text-right text-primary">{closingBalance.toLocaleString()} с</td>
              </tr>
            </tfoot>
          </table>
        </div>

        {/* Итоговая бухгалтерская фраза (из ТЗ) */}
        <div className="mt-6 rounded-xl border border-amber-200 bg-amber-50/60 p-4 text-xs">
          <span className="font-bold text-amber-900">Итог сверки: </span>
          <span className="font-black text-ink">
            задолженность в пользу Арендодателя составляет {closingBalance.toLocaleString()} сом (двадцать восемь тысяч пятьсот девяносто три сома).
          </span>
        </div>

        {/* Подписи сторон */}
        <div className="mt-10 grid grid-cols-2 gap-8 border-t border-line pt-8 text-xs">
          <div>
            <div className="font-bold text-ink">От Арендодателя:</div>
            <div className="mt-1 text-ink-soft">Генеральный директор / Главный бухгалтер</div>
            <div className="mt-6 border-b border-dashed border-ink/30 w-48" />
            <div className="mt-1 text-[10px] text-ink-soft">М.П. / подпись / расшифровка</div>
          </div>
          <div>
            <div className="font-bold text-ink">От Арендатора:</div>
            <div className="mt-1 text-ink-soft">{selectedTenant}</div>
            <div className="mt-6 border-b border-dashed border-ink/30 w-48" />
            <div className="mt-1 text-[10px] text-ink-soft">М.П. / подпись / расшифровка</div>
          </div>
        </div>
      </div>
    </div>
  );
}
