import { redirect } from "next/navigation";
import { getSession } from "@/lib/session";
import { AUTH_ENABLED } from "@/lib/config";
import { SupportPanel } from "@/screens/support-panel";

// Панель техподдержки NurCRM. Доступ: только сотрудники с ролью «Поддержка» (на сервере).
export default async function SupportPage() {
  if (AUTH_ENABLED) {
    const session = await getSession();
    if (!session) redirect("/login");
  }
  return <SupportPanel />;
}

