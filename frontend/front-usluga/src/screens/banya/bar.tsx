"use client";

import { useState } from "react";

type BarProduct = {
  id: string;
  name: string;
  price: number;
  cost: number;
  stock: number | null; // null = uncounted
  category: string;
};

const INITIAL_PRODUCTS: BarProduct[] = [
  { id: "1", name: "Пиво крафтовое", price: 180, cost: 95, stock: 4, category: "Напитки" },
  { id: "2", name: "Квас домашний", price: 120, cost: 50, stock: 12, category: "Напитки" },
  { id: "3", name: "Минеральная вода", price: 80, cost: 35, stock: 25, category: "Напитки" },
  { id: "4", name: "Чай в чайнике (травяной)", price: 250, cost: 40, stock: null, category: "Напитки" },
  { id: "5", name: "Самса с мясом", price: 150, cost: 80, stock: 0, category: "Еда" },
  { id: "6", name: "Шашлык ассорти", price: 650, cost: 380, stock: 8, category: "Еда" },
  { id: "7", name: "Веник дубовый премиум", price: 350, cost: 180, stock: 15, category: "Банное" },
  { id: "8", name: "Простыня банная (аренда)", price: 100, cost: 20, stock: null, category: "Банное" },
];

export function BathBarScreen() {
  const [products, setProducts] = useState<BarProduct[]>(INITIAL_PRODUCTS);
  const [targetLocker, setTargetLocker] = useState("М03");
  const [cart, setCart] = useState<{ product: BarProduct; qty: number }[]>([]);
  const [activeTab, setActiveTab] = useState("Все");
  const [showAddCustomModal, setShowAddCustomModal] = useState(false);
  const [customName, setCustomName] = useState("");
  const [customPrice, setCustomPrice] = useState("");
  const [customCost, setCustomCost] = useState("");

  const categories = ["Все", "Напитки", "Еда", "Банное"];

  const filteredProducts = activeTab === "Все" ? products : products.filter((p) => p.category === activeTab);

  const addToCart = (product: BarProduct) => {
    if (product.stock !== null && product.stock <= 0) return;
    setCart((prev) => {
      const existing = prev.find((item) => item.product.id === product.id);
      if (existing) {
        if (product.stock !== null && existing.qty >= product.stock) {
          alert(`Осталось только ${product.stock} шт.`);
          return prev;
        }
        return prev.map((item) => (item.product.id === product.id ? { ...item, qty: item.qty + 1 } : item));
      }
      return [...prev, { product, qty: 1 }];
    });
  };

  const removeFromCart = (productId: string) => {
    setCart((prev) =>
      prev
        .map((item) => (item.product.id === productId ? { ...item, qty: item.qty - 1 } : item))
        .filter((item) => item.qty > 0)
    );
  };

  const totalCartAmount = cart.reduce((acc, cur) => acc + cur.product.price * cur.qty, 0);

  const handleAddCustom = (e: React.FormEvent) => {
    e.preventDefault();
    if (!customName || !customPrice) return;
    const newProd: BarProduct = {
      id: Date.now().toString(),
      name: customName,
      price: Number(customPrice),
      cost: Number(customCost || 0),
      stock: null,
      category: "Доп. услуги",
    };
    setProducts((prev) => [newProd, ...prev]);
    addToCart(newProd);
    setShowAddCustomModal(false);
    setCustomName("");
    setCustomPrice("");
    setCustomCost("");
  };

  return (
    <div className="flex flex-col gap-6">
      {/* Верхняя плашка остатков */}
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-card p-4 shadow-sm">
        <div className="flex items-center gap-3 text-xs">
          <span className="font-bold text-rose-600">Закончилось: Самса с мясом</span>
          <span className="text-line">•</span>
          <span className="font-semibold text-amber-600">Заканчивается: Пиво крафтовое (4 шт)</span>
        </div>
        <button
          onClick={() => setShowAddCustomModal(true)}
          className="rounded-xl border border-dashed border-gold/80 bg-gold/10 px-3 py-1.5 text-xs font-bold text-primary hover:bg-gold/20"
        >
          + Доп. услуга из мяса/продуктов гостя
        </button>
      </div>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
        {/* Каталог плиток (2 колонки) */}
        <div className="lg:col-span-2">
          {/* Фильтры категорий */}
          <div className="mb-4 flex gap-2">
            {categories.map((c) => (
              <button
                key={c}
                onClick={() => setActiveTab(c)}
                className={`rounded-xl px-3 py-1.5 text-xs font-bold transition-all ${
                  activeTab === c ? "bg-primary text-white" : "border border-line bg-card text-ink hover:bg-line/20"
                }`}
              >
                {c}
              </button>
            ))}
          </div>

          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {filteredProducts.map((p) => {
              const isOut = p.stock !== null && p.stock <= 0;
              const isLow = p.stock !== null && p.stock > 0 && p.stock <= 5;

              return (
                <button
                  key={p.id}
                  disabled={isOut}
                  onClick={() => addToCart(p)}
                  className={`flex flex-col justify-between rounded-2xl border p-4 text-left transition-all hover:scale-[1.02] ${
                    isOut
                      ? "border-line/60 bg-bg opacity-50 cursor-not-allowed"
                      : "border-line bg-card shadow-sm hover:border-gold"
                  }`}
                >
                  <div>
                    <div className="text-xs font-bold text-ink">{p.name}</div>
                    <div className="mt-1 text-sm font-black text-primary">{p.price} сом</div>
                  </div>
                  <div className="mt-3 flex items-center justify-between text-[11px]">
                    <span className="text-ink-soft">{p.category}</span>
                    {p.stock === null ? (
                      <span className="font-semibold text-ink-soft">без остатка</span>
                    ) : isOut ? (
                      <span className="font-bold text-rose-600">нет</span>
                    ) : (
                      <span className={`font-bold ${isLow ? "text-amber-600" : "text-emerald-600"}`}>
                        ост. {p.stock} шт
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Правый сайдбар: Корзина заказа на номер браслета */}
        <div className="rounded-2xl border border-line bg-card p-5 shadow-sm">
          <div className="flex items-center justify-between border-b border-line pb-3">
            <span className="text-xs font-bold uppercase text-ink-soft">Заказ в счёт</span>
            <input
              type="text"
              value={targetLocker}
              onChange={(e) => setTargetLocker(e.target.value.toUpperCase())}
              placeholder="Номер браслета"
              className="w-24 rounded-lg border border-line px-2 py-1 text-center font-black text-primary uppercase focus:border-gold focus:outline-none"
            />
          </div>

          <div className="mt-3 rounded-xl bg-bg p-3 text-xs">
            <div className="flex justify-between font-semibold">
              <span className="text-ink-soft">Гость: Бакыт С.</span>
              <span className="text-ink">Лимит: 5 000 с</span>
            </div>
            <div className="mt-1 text-[11px] text-ink-soft">Текущий долг: 2 400 с</div>
          </div>

          {/* Список выбранных товаров */}
          <div className="mt-4 flex flex-col gap-2 max-h-60 overflow-y-auto">
            {cart.length === 0 ? (
              <div className="py-8 text-center text-xs text-ink-soft">Нажмите на плитку товара, чтобы добавить в счёт</div>
            ) : (
              cart.map((item) => (
                <div key={item.product.id} className="flex items-center justify-between rounded-xl border border-line/60 bg-bg p-2 text-xs">
                  <div>
                    <div className="font-bold text-ink">{item.product.name}</div>
                    <div className="text-[11px] text-ink-soft">
                      {item.product.price} с × {item.qty}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="font-extrabold text-primary">{item.product.price * item.qty} с</span>
                    <button
                      onClick={() => removeFromCart(item.product.id)}
                      className="size-6 rounded-lg bg-line/60 font-black text-ink hover:bg-rose-100 hover:text-rose-600"
                    >
                      −
                    </button>
                  </div>
                </div>
              ))
            )}
          </div>

          {/* Итог корзины */}
          <div className="mt-5 border-t border-line pt-4">
            <div className="flex items-center justify-between">
              <span className="text-xs font-bold text-ink-soft">Итого к счёту:</span>
              <span className="text-xl font-black text-primary">{totalCartAmount.toLocaleString()} сом</span>
            </div>

            <button
              disabled={cart.length === 0}
              onClick={() => {
                alert(`Успешно записано ${totalCartAmount} сом в счёт браслета ${targetLocker}`);
                setCart([]);
              }}
              className="mt-4 w-full rounded-xl bg-gold py-3 text-center text-xs font-black text-primary transition-all hover:brightness-105 disabled:opacity-50"
            >
              Записать в счёт {targetLocker}
            </button>
          </div>
        </div>
      </div>

      {/* Модалка добавления доп. услуги */}
      {showAddCustomModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm">
          <form onSubmit={handleAddCustom} className="w-full max-w-sm rounded-2xl border border-line bg-card p-6 shadow-2xl">
            <h3 className="text-base font-black text-ink">Доп. услуга на лету</h3>
            <p className="mt-1 text-xs text-ink-soft">Приготовление мяса гостя, аренда мангала, прокат и т.д.</p>

            <div className="mt-4 flex flex-col gap-3">
              <div>
                <label className="text-[11px] font-bold text-ink-soft">Название</label>
                <input
                  required
                  type="text"
                  placeholder="Приготовить шашлык из мяса гостя"
                  value={customName}
                  onChange={(e) => setCustomName(e.target.value)}
                  className="mt-1 w-full rounded-xl border border-line px-3 py-2 text-xs font-semibold focus:border-gold focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-2 gap-2">
                <div>
                  <label className="text-[11px] font-bold text-ink-soft">Цена (сом)</label>
                  <input
                    required
                    type="number"
                    placeholder="300"
                    value={customPrice}
                    onChange={(e) => setCustomPrice(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-line px-3 py-2 text-xs font-semibold focus:border-gold focus:outline-none"
                  />
                </div>
                <div>
                  <label className="text-[11px] font-bold text-ink-soft">Себестоимость</label>
                  <input
                    type="number"
                    placeholder="50"
                    value={customCost}
                    onChange={(e) => setCustomCost(e.target.value)}
                    className="mt-1 w-full rounded-xl border border-line px-3 py-2 text-xs font-semibold focus:border-gold focus:outline-none"
                  />
                </div>
              </div>
            </div>

            <div className="mt-5 grid grid-cols-2 gap-3">
              <button
                type="button"
                onClick={() => setShowAddCustomModal(false)}
                className="rounded-xl border border-line px-4 py-2 text-xs font-bold text-ink hover:bg-line/30"
              >
                Отмена
              </button>
              <button
                type="submit"
                className="rounded-xl bg-gold px-4 py-2 text-xs font-black text-primary hover:brightness-105"
              >
                Сохранить в заказ
              </button>
            </div>
          </form>
        </div>
      )}
    </div>
  );
}
