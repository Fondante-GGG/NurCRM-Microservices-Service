"use client";

// Общие элементы интерфейса: заголовок экрана, кнопки, таблица, боковая панель, поля формы.
import { useEffect, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { Icon } from "../icon";
import { useI18n } from "@/i18n/provider";

export function PageHeader({ title, subtitle, actions }: { title: string; subtitle?: string; actions?: ReactNode }) {
  return (
    <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
      <div>
        <h1 className="text-2xl font-extrabold tracking-tight">{title}</h1>
        {subtitle && <p className="mt-1 text-sm text-ink-soft">{subtitle}</p>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

type BtnProps = React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" | "danger"; size?: "sm" | "md" };

export function Button({ variant = "secondary", size = "md", className = "", ...rest }: BtnProps) {
  const base = "press inline-flex items-center justify-center gap-2 rounded-xl font-bold disabled:cursor-not-allowed disabled:opacity-50";
  const sizes = size === "sm" ? "h-9 px-3 text-[13px]" : "h-11 px-4 text-sm";
  const variants = {
    primary: "bg-gold font-extrabold text-primary hover:bg-[#f2cb00]",
    secondary: "border-[1.5px] border-line-strong bg-card text-ink-mid hover:bg-paper",
    ghost: "text-ink-mid hover:bg-paper",
    danger: "border-[1.5px] border-danger/40 bg-card text-danger hover:bg-bad-soft",
  }[variant];
  return <button className={`${base} ${sizes} ${variants} ${className}`} {...rest} />;
}

// Кнопка опасного действия: первый клик спрашивает «Точно?», второй выполняет.
export function ConfirmButton({ onConfirm, children, variant = "danger", size = "sm", className = "" }: { onConfirm: () => void; children: ReactNode; variant?: BtnProps["variant"]; size?: BtnProps["size"]; className?: string }) {
  const { t } = useI18n();
  const [asking, setAsking] = useState(false);
  useEffect(() => {
    if (!asking) return;
    const id = window.setTimeout(() => setAsking(false), 8000);
    return () => window.clearTimeout(id);
  }, [asking]);
  if (asking) {
    return (
      <span className={`anim-fade-in inline-flex items-center gap-1.5 ${className}`} role="group" aria-label={t.u.common.confirm}>
        <span className="text-sm text-ink-soft">{t.u.common.confirm}</span>
        <Button size={size} variant="danger" onClick={() => { setAsking(false); onConfirm(); }}>{t.u.common.confirmYes}</Button>
        <Button size={size} variant="ghost" onClick={() => setAsking(false)}>{t.u.common.confirmNo}</Button>
      </span>
    );
  }
  return <Button size={size} variant={variant} className={className} onClick={() => setAsking(true)}>{children}</Button>;
}

export function Card({ children, className = "" }: { children: ReactNode; className?: string }) {
  return <div className={`rounded-2xl border border-line bg-card ${className}`}>{children}</div>;
}

export function Stat({ label, value, hint, tone }: { label: string; value: string; hint?: string; tone?: "good" | "bad" }) {
  return (
    <Card className="px-4 py-3.5">
      <div className="text-xs font-semibold text-ink-soft">{label}</div>
      <div className={`mt-1 text-2xl font-extrabold tabular-nums tracking-tight ${tone === "bad" ? "text-danger" : tone === "good" ? "text-positive" : "text-primary"}`}>{value}</div>
      {hint && <div className="mt-0.5 text-xs text-ink-soft">{hint}</div>}
    </Card>
  );
}

export function Table({ head, children, empty }: { head: ReactNode[]; children: ReactNode; empty?: string }) {
  const rows = Array.isArray(children) ? children.filter(Boolean) : children;
  const isEmpty = Array.isArray(rows) ? rows.length === 0 : !rows;
  return (
    <Card className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-line text-left text-xs text-ink-soft">
            {head.map((h, i) => (
              <th key={i} className="px-4 py-3 font-bold">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {isEmpty ? (
            <tr>
              <td colSpan={head.length} className="px-4 py-8 text-center text-ink-soft">
                {empty ?? "—"}
              </td>
            </tr>
          ) : (
            rows
          )}
        </tbody>
      </table>
    </Card>
  );
}

export function Row({ children, onClick, active, className = "" }: { children: ReactNode; onClick?: () => void; active?: boolean; className?: string }) {
  return (
    <tr
      onClick={onClick}
      tabIndex={onClick ? 0 : undefined}
      onKeyDown={onClick ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } } : undefined}
      className={`border-b border-line-soft last:border-0 ${onClick ? "cursor-pointer hover:bg-paper focus-visible:bg-paper focus-visible:outline-none" : ""} ${active ? "bg-gold-soft" : ""} ${className}`}
    >
      {children}
    </tr>
  );
}

export function Cell({ children, className = "", right, title }: { children?: ReactNode; className?: string; right?: boolean; title?: string }) {
  return <td title={title} className={`px-4 py-3 align-middle ${right ? "whitespace-nowrap text-right tabular-nums" : ""} ${className}`}>{children}</td>;
}

export function Badge({ children, tone = "neutral" }: { children: ReactNode; tone?: "neutral" | "good" | "warn" | "bad" | "info" }) {
  const tones = {
    neutral: "bg-line-soft text-ink-mid",
    good: "bg-positive-soft text-positive",
    warn: "bg-warn-soft text-warn",
    bad: "bg-bad-soft text-[#b42318]",
    info: "bg-gold-soft text-primary",
  }[tone];
  return <span className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-bold ${tones}`}>{children}</span>;
}

// Правая выезжающая панель (карточка записи, сотрудника и т. п.) с анимацией входа и выхода.
export function Drawer({ open, onClose, title, children, footer, wide }: { open: boolean; onClose: () => void; title: string; children: ReactNode; footer?: ReactNode; wide?: boolean }) {
  const [mounted, setMounted] = useState(open);
  const [closing, setClosing] = useState(false);
  const { t } = useI18n();

  useEffect(() => {
    if (open) {
      setMounted(true);
      setClosing(false);
      return;
    }
    if (!mounted) return;
    setClosing(true);
    const id = window.setTimeout(() => { setMounted(false); setClosing(false); }, 200);
    return () => window.clearTimeout(id);
  }, [open, mounted]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!mounted) return null;
  // Портал в body: панель не зависит от transform/animation родителей и не меняет размер страницы.
  return createPortal(
    <div className="fixed inset-0 z-50">
      <button type="button" aria-label={t.u.common.close} onClick={onClose} className={`absolute inset-0 bg-ink/40 ${closing ? "anim-fade-out" : "anim-fade-in"}`} />
      <aside role="dialog" aria-modal="true" aria-label={title} className={`absolute inset-y-0 right-0 flex w-full flex-col bg-card shadow-xl ${wide ? "max-w-3xl" : "max-w-xl"} ${closing ? "anim-slide-out-right" : "anim-slide-in-right"}`}>
        <div className="flex items-center justify-between border-b border-line px-5 py-4">
          <h2 className="text-lg font-extrabold tracking-tight">{title}</h2>
          <button type="button" onClick={onClose} aria-label={t.u.common.close} className="press flex size-10 items-center justify-center rounded-xl border border-line text-ink-mid hover:bg-paper">
            <Icon name="x" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-4 [overscroll-behavior:contain]">{children}</div>
        {footer && <div className="flex flex-wrap items-center justify-end gap-2 border-t border-line bg-[#fcfcfd] px-5 py-3">{footer}</div>}
      </aside>
    </div>,
    document.body,
  );
}

// group — для набора переключателей или нескольких полей: тогда это не <label>,
// иначе браузер связывает подпись с первой кнопкой и подсвечивает её при нажатии на другие.
export function Field({ label, children, hint, group }: { label: string; children: ReactNode; hint?: string; group?: boolean }) {
  const Tag = group ? "div" : "label";
  return (
    <Tag className="block" role={group ? "group" : undefined} aria-label={group ? label : undefined}>
      <span className="text-xs font-bold text-ink-soft">{label}</span>
      <div className="mt-1.5">{children}</div>
      {hint && <span className="mt-1 block text-xs text-ink-soft">{hint}</span>}
    </Tag>
  );
}

export const inputCls = "h-11 w-full rounded-xl border border-line-strong bg-card px-3.5 text-sm outline-none focus:border-primary disabled:cursor-not-allowed disabled:bg-paper disabled:text-ink-soft";

// Свой размер поля: заданные h-/w-/px- заменяют стандартные, а не спорят с ними.
function fieldCls(extra?: string): string {
  if (!extra) return inputCls;
  const own = extra.split(/\s+/).filter(Boolean);
  const has = (p: string) => own.some((c) => c.startsWith(p));
  const base = inputCls.split(" ").filter((c) => !(c.startsWith("h-") && has("h-")) && !(c.startsWith("w-") && has("w-")) && !(c.startsWith("px-") && has("px-")));
  return `${base.join(" ")} ${extra}`;
}

export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  return <input {...props} className={fieldCls(props.className)} />;
}

export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  return <select {...props} className={fieldCls(props.className)} />;
}

export function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button type="button" role="switch" aria-checked={checked} onClick={() => onChange(!checked)} className="group flex items-center gap-3 text-left text-sm">
      <span
        className={`relative inline-block h-6 w-11 shrink-0 rounded-full border transition-colors duration-200 ${checked ? "border-primary bg-primary" : "border-ink-soft/40 bg-ink-soft/25"}`}
        style={{ width: 44, height: 24 }}
      >
        <span
          className="spring absolute rounded-full bg-white shadow transition-[left,transform] duration-300 group-active:scale-90"
          style={{ width: 18, height: 18, top: 2, left: checked ? 22 : 2 }}
        />
      </span>
      <span>{label}</span>
    </button>
  );
}

export function Segmented<T extends string>({ value, onChange, options }: { value: T; onChange: (v: T) => void; options: { value: T; label: string }[] }) {
  return (
    <div className="inline-flex rounded-xl bg-segment p-1">
      {options.map((o) => (
        <button
          key={o.value}
          type="button"
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={`press whitespace-nowrap rounded-[10px] px-3.5 py-2 text-[13px] font-bold ${value === o.value ? "bg-card text-primary shadow-[0_1px_2px_rgba(16,24,40,.08)]" : "text-[#475467] hover:text-ink"}`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Empty({ text }: { text: string }) {
  return <div className="rounded-2xl border border-dashed border-line px-4 py-10 text-center text-sm text-ink-soft">{text}</div>;
}
