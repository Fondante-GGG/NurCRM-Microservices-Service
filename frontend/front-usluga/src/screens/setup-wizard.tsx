"use client";

import { useEffect, useState } from "react";
import { Icon } from "@/components/icon";
import { Field, Input } from "@/components/ui";
import { useStore } from "@/data/store";
import { useI18n } from "@/i18n/provider";
import { INDUSTRY_GROUPS, INTAKE_MODES, PROFILES, type Industry, type IntakeMode } from "@/lib/industry";

type IconName = "scissors" | "sparkles" | "badge" | "users" | "clock" | "pin" | "file" | "calendar" | "chart" | "settings";
const ICONS: Record<Industry, IconName> = { barber: "scissors", beauty: "sparkles", nails: "sparkles", brows: "sparkles", cosmetology: "badge", tattoo: "pin", procedure: "badge", massage: "users", spa: "clock", other: "settings" };

// Первый экран нового аккаунта: три шага — сфера, приём клиентов, итог. Потом сферу меняет только техподдержка.
export function SetupWizard() {
  const { chooseIndustry } = useStore();
  const { t } = useI18n();
  const i = t.u.industry;
  const w = i.wizard;
  const [step, setStep] = useState<0 | 1 | 2>(0);
  const [industry, setIndustry] = useState<Industry | null>(null);
  const [intake, setIntake] = useState<IntakeMode>("schedule");
  const [name, setName] = useState("");
  const steps = ["industry", "intake", "summary"] as const;
  const prof = industry ? PROFILES[industry] : null;
  // Новый шаг всегда с начала страницы.
  useEffect(() => { window.scrollTo({ top: 0 }); }, [step]);

  function pickIndustry(k: Industry) {
    setIndustry(k);
    setIntake(PROFILES[k].defaultIntake);
    if (!name.trim() || Object.values(PROFILES).some((p) => p.companyName === name)) setName(PROFILES[k].companyName);
  }
  const canNext = step === 0 ? !!industry : step === 1 ? name.trim().length > 0 : true;
  const next = () => (step < 2 ? setStep((s) => (s + 1) as 0 | 1 | 2) : industry && chooseIndustry(industry, { intake, companyName: name }));

  const gets: string[] = prof
    ? [
        intake === "schedule" ? w.gets.journal : intake === "flow" ? w.gets.flow : w.gets.mixed,
        `${w.gets.services}: ${prof.services.filter((s) => !s.addon).length} + ${prof.services.filter((s) => s.addon).length} ${w.addons}`,
        `${w.gets.positions}: ${prof.positions.map((p) => p.name).join(", ")}`,
        w.gets.clients,
        w.gets.payroll,
        w.gets.cash,
        w.gets.booking,
      ]
    : [];

  return (
    <main className="flex min-h-screen items-start justify-center bg-paper px-4 py-10">
      <div className="anim-rise w-full max-w-3xl">
        <div className="mb-6 flex items-center gap-3">
          <span className="flex size-12 items-center justify-center rounded-[14px] bg-gold text-[22px] font-extrabold text-primary">N</span>
          <div>
            <div className="text-[22px] font-bold leading-tight">{w.welcome}</div>
            <div className="text-sm text-ink-soft">{w.sub}</div>
          </div>
        </div>

        <ol className="mb-6 flex gap-2" aria-label={`${w.step} ${step + 1} ${w.of} 3`}>
          {steps.map((k, n) => (
            <li key={k} className={`flex-1 rounded-xl border px-3 py-2 text-xs font-bold ${n === step ? "border-gold bg-gold-soft text-ink" : n < step ? "border-line bg-card text-primary" : "border-line bg-card text-ink-soft"}`}>
              <span className="mr-1 text-ink-soft">{n + 1}.</span>{w.steps[k]}
            </li>
          ))}
        </ol>

        <section key={step} className="anim-fade-in">
          {step === 0 && (
            <>
              <h1 className="text-2xl font-extrabold tracking-tight">{i.title}</h1>
              <p className="mt-1 max-w-xl text-sm text-ink-soft">{i.hint}</p>
              {INDUSTRY_GROUPS.map((g) => (
                <div key={g.id} className="mt-5">
                  <div className="mb-2 text-[11px] font-extrabold uppercase tracking-[.05em] text-ink-soft">{i.groups[g.id]}</div>
                  <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                    {g.items.map((k) => (
                      <button key={k} type="button" onClick={() => pickIndustry(k)} aria-pressed={industry === k}
                        className={`press flex h-full flex-col items-start rounded-2xl border-2 bg-card p-4 text-left ${industry === k ? "border-gold bg-gold-soft" : "border-line hover:border-line-strong"}`}>
                        <span className={`flex size-9 items-center justify-center rounded-xl ${industry === k ? "bg-gold text-primary" : "bg-primary-soft text-primary"}`}><Icon name={ICONS[k]} /></span>
                        <span className="mt-2 block font-extrabold">{i.names[k]}</span>
                        <span className="mt-0.5 block text-xs text-ink-soft">{i.descs[k]}</span>
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </>
          )}

          {step === 1 && prof && (
            <>
              <h1 className="text-2xl font-extrabold tracking-tight">{w.steps.intake}</h1>
              <div className="mt-4 grid gap-3">
                {INTAKE_MODES.filter((m) => m === "schedule" || prof.allowFlow).map((m) => (
                  <button key={m} type="button" onClick={() => setIntake(m)} aria-pressed={intake === m}
                    className={`press rounded-2xl border-2 bg-card p-4 text-left ${intake === m ? "border-gold bg-gold-soft" : "border-line hover:border-line-strong"}`}>
                    <span className="block font-extrabold">{i.intakeModes[m]}</span>
                    <span className="mt-0.5 block text-sm text-ink-soft">{w.intakeOptions[m]}</span>
                  </button>
                ))}
              </div>
              {!prof.allowFlow && <p className="mt-2 text-xs text-ink-soft">{w.onlySchedule}</p>}
              <div className="mt-6 max-w-md">
                <Field label={w.companyName}><Input value={name} placeholder={w.companyPlaceholder} onChange={(e) => setName(e.target.value)} /></Field>
              </div>
            </>
          )}

          {step === 2 && prof && (
            <>
              <h1 className="text-2xl font-extrabold tracking-tight">{w.summaryTitle}</h1>
              <p className="mt-1 text-sm text-ink-soft">{w.summaryHint}</p>
              <div className="mt-4 rounded-2xl border border-line bg-card p-5">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="rounded-xl bg-primary px-3 py-1.5 text-sm font-extrabold text-white">{name}</span>
                  <span className="rounded-xl bg-gold-soft px-3 py-1.5 text-sm font-bold">{industry && i.names[industry]}</span>
                  <span className="rounded-xl bg-segment px-3 py-1.5 text-sm font-bold">{i.intakeModes[intake]}</span>
                </div>
                <h2 className="mt-5 text-sm font-semibold">{w.youGet}</h2>
                <ul className="mt-2 space-y-2">
                  {gets.map((g) => (
                    <li key={g} className="flex items-start gap-2 text-sm"><span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-positive-soft text-[11px] font-extrabold text-positive">✓</span><span>{g}</span></li>
                  ))}
                </ul>
                <p className="mt-4 text-xs text-ink-soft">{w.demo}</p>
              </div>
            </>
          )}
        </section>

        <div className="sticky bottom-0 -mx-4 mt-6 flex items-center justify-between border-t border-line bg-paper/95 px-4 py-3 backdrop-blur">
          <button type="button" disabled={step === 0} onClick={() => setStep((s) => (s - 1) as 0 | 1 | 2)} className="press h-11 rounded-xl border-[1.5px] border-line-strong bg-card px-5 text-sm font-bold text-[#344054] disabled:opacity-0">{w.back}</button>
          <button type="button" disabled={!canNext} onClick={next} className="press h-12 rounded-xl bg-gold px-6 text-base font-extrabold text-primary disabled:opacity-50">
            {step < 2 ? `${w.next} ›` : w.finish}
          </button>
        </div>
      </div>
    </main>
  );
}
