import { notFound, redirect } from "next/navigation";
import { AUTH_ENABLED } from "@/lib/config";
import { getSession } from "@/lib/session";
import { isSection } from "@/lib/sections";
import { Shell } from "@/components/shell";

// Общий каркас всех четырёх программ. Чужую программу открыть нельзя: сервер решает, какая у компании.
export default async function SectionLayout({ children, params }: LayoutProps<"/[section]">) {
  const { section } = await params;
  if (!isSection(section)) notFound();

  if (!AUTH_ENABLED) {
    return <Shell section={section} name="" canLogout={false}>{children}</Shell>;
  }

  const session = await getSession();
  if (!session) redirect("/login");
  if (!session.section) redirect("/razdel");
  if (session.section !== section) redirect(`/${session.section}`);
  return (
    <Shell section={section} name={session.name} canLogout>
      {children}
    </Shell>
  );
}
