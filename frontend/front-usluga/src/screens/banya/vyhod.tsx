"use client";

import { useState } from "react";

type VisitCheckout = {
  bracelet: string;
  guest: string;
  entryTariff: string;
  entryTime: string;
  duration: string;
  timeCharge: number;
  barAmount: number;
  servicesAmount: number;
  oldClientDebt: number;
  companyGroup?: string;
  items: { name: string; sum: number; source: string }[];
};

const SAMPLE_GUEST: VisitCheckout = {
  bracelet: "М03",
  guest: "Бакыт Сейдалиев",
  entryTariff: "3 часа (500 сом)",
  entryTime: "13:10",
  duration: "3 ч 35 мин",
  timeCharge: 100, // доплата за начатый 4-й час
  barAmount: 600,
  servicesAmount: 1200,
  oldClientDebt: 0,
  companyGroup: "Компания №2 (М03, М04)",
  items: [
    { name: "Входной тариф (3 ч)", sum: 500, source: "Вход" },
    { name: "Перерасход времени (35 мин)", sum: 100, source: "Время" },
    { name: "Пиво крафтовое × 2", sum: 360, source: "Бар" },
    { name: "Чай травяной в чайнике", sum: 240, source: "Бар" },
    { name: "Парение дубовым веником", sum: 1200, source: "Мастер" },
  ],
};

export function BathCheckoutScreen() {
  const [braceletInput, setBraceletInput] = useState("М03");
  const [guestData, setGuestData] = useState<VisitCheckout | null>(SAMPLE_GUEST);
  const [payForCompany, setPayForCompany] = useState(false);
  const [includeOldDebt, setIncludeOldDebt] = useState(true);
  const [paymentMethod, setPaymentMethod] = useState("MBank QR");

  const totalCurrentDebt = guestData
    ? guestData.items.reduce((acc, cur) => acc + cur.sum, 0)
    : 0;

  const totalToPay =
    totalCurrentDebt + (includeOldDebt && guestData ? guestData.oldClientDebt : 0);

  const handleCheckout = () => {
    if (!guestData) return;
    alert(
      `Оплата принята: ${totalToPay} сом через ${paymentMethod}.\nШкафчик ${guestData.bracelet} освобожден и готов к выдаче!`
    );
    setGuestData(null);
  };

  const handleReleaseWithDebt = () => {
    if (!guestData) return;
    alert(
      `Гость ${guestData.guest} отпущен с долгом ${totalToPay} сом. Сумма перенесена в карточку клиента.`
    );
    setGuestData(null);
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Поиск браслета */}
      <div className="rounded-2xl border border-line bg-card p-5 shadow-sm">
        <h2 className="text-base font-black text-ink">Выход, оплата и контроль долга</h2>
        <div className="mt-3 flex max-w-md gap-2">
          <input
            type="text"
            value={braceletInput}
            onChange={(e) => setBraceletInput(e.target.value.toUpperCase())}
            placeholder="Номер браслета гостя (напр. М03)"
            className="w-full rounded-xl border border-line px-3 py-2 text-base font-black uppercase text-primary focus:border-gold focus:outline-none"
          />
          <button
            onClick={() => setGuestData(SAMPLE_GUEST)}
            className="rounded-xl bg-gold px-5 py-2 text-xs font-black text-primary hover:brightness-105"
          >
            Найти
          </button>
        </div>
      </div>

      {guestData ? (
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          {/* Детализация счета (2 колонки) */}
          <div className="lg:col-span-2 flex flex-col gap-4">
            {/* Красная плашка предупреждения о долге */}
            <div className="rounded-2xl border border-rose-300 bg-rose-50 p-4">
              <div className="flex items-center gap-2 text-rose-800 font-black text-sm">
                <span>⚠️ Не отпускайте без оплаты!</span>
              </div>
              <p className="mt-1 text-xs text-rose-700">
                У гостя открыт счёт на браслет {guestData.bracelet}. Шкафчик не освободится, пока не проведена оплата или решение отпустить с долгом.
              </p>
            </div>

            <div className="rounded-2xl border border-line bg-card p-5 shadow-sm">
              <div className="flex items-center justify-between border-b border-line pb-3">
                <div>
                  <span className="text-xl font-black text-ink">{guestData.bracelet}</span>
                  <span className="ml-2 text-sm font-bold text-ink-soft">{guestData.guest}</span>
                </div>
                <span className="rounded-lg bg-line/60 px-2.5 py-1 text-xs font-bold text-ink">
                  Внутри: {guestData.duration}
                </span>
              </div>

              {/* Таблица позиций счёта */}
              <div className="mt-4 flex flex-col gap-2">
                {guestData.items.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between rounded-xl border border-line/60 bg-bg p-3 text-xs"
                  >
                    <div>
                      <div className="font-bold text-ink">{item.name}</div>
                      <div className="text-[11px] text-ink-soft">Источник: {item.source}</div>
                    </div>
                    <div className="text-sm font-black text-primary">{item.sum} с</div>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Правая колонка: форма расчета */}
          <div className="rounded-2xl border border-line bg-card p-5 shadow-sm">
            <h3 className="text-xs font-bold uppercase text-ink-soft">Расчёт на выходе</h3>

            <div className="mt-4 flex flex-col gap-3">
              <div className="rounded-xl bg-bg p-3 text-xs">
                <div className="flex justify-between py-1">
                  <span className="text-ink-soft">Счёт за визит:</span>
                  <span className="font-bold text-ink">{totalCurrentDebt.toLocaleString()} с</span>
                </div>
                {guestData.oldClientDebt > 0 && (
                  <div className="flex justify-between py-1 text-rose-600 font-bold">
                    <span>Долг с прошлых раз:</span>
                    <span>+{guestData.oldClientDebt} с</span>
                  </div>
                )}
              </div>

              {/* Выбор способа оплаты */}
              <div>
                <label className="text-[11px] font-bold text-ink-soft">Способ оплаты</label>
                <div className="mt-1.5 grid grid-cols-2 gap-2">
                  {["Наличные", "MBank QR", "О!Деньги", "Банковская карта"].map((method) => (
                    <button
                      key={method}
                      onClick={() => setPaymentMethod(method)}
                      className={`rounded-xl border p-2 text-center text-xs font-bold transition-all ${
                        paymentMethod === method
                          ? "border-primary bg-primary text-white"
                          : "border-line bg-bg text-ink hover:bg-line/30"
                      }`}
                    >
                      {method}
                    </button>
                  ))}
                </div>
              </div>

              {/* Итого к оплате */}
              <div className="mt-3 border-t border-line pt-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-bold text-ink-soft">Итого к оплате:</span>
                  <span className="text-2xl font-black text-primary">{totalToPay.toLocaleString()} сом</span>
                </div>

                <button
                  onClick={handleCheckout}
                  className="mt-4 w-full rounded-xl bg-gold py-3 text-center text-xs font-black text-primary transition-all hover:brightness-105"
                >
                  Принять {totalToPay.toLocaleString()} с и освободить {guestData.bracelet}
                </button>

                <button
                  onClick={handleReleaseWithDebt}
                  className="mt-2 w-full rounded-xl border border-line py-2 text-center text-xs font-bold text-ink-soft hover:bg-line/30 hover:text-rose-600"
                >
                  Отпустить с долгом на клиента
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <div className="rounded-2xl border border-dashed border-line p-12 text-center">
          <div className="text-sm font-bold text-ink">Введите номер браслета в поле выше</div>
          <p className="mt-1 text-xs text-ink-soft">Система загрузит открытый счёт и проверит долг гостя.</p>
        </div>
      )}
    </div>
  );
}
