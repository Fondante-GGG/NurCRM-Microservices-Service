import { LoginForm } from "./login-form";
import { BrandPanel } from "./brand-panel";
import { LangSwitch } from "@/components/lang-switch";

export default function LoginPage() {
  return (
    <main className="flex min-h-screen flex-col lg:flex-row">
      <BrandPanel />
      <section className="relative flex flex-1 items-center justify-center px-4 py-10 sm:px-8">
        <LangSwitch className="absolute right-4 top-4 sm:right-8 sm:top-6" />
        <LoginForm />
      </section>
    </main>
  );
}
