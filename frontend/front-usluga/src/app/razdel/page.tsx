import { redirect } from "next/navigation";
import { getSession, setSessionSection } from "@/lib/session";
import { isSection } from "@/lib/sections";
import { RazdelPicker } from "./picker";

// Сюда попадают, если сервер после входа не назвал раздел.
export default async function RazdelPage() {
  const session = await getSession();
  if (!session) redirect("/login");
  if (session.section) redirect(`/${session.section}`);

  async function choose(formData: FormData) {
    "use server";
    const section = formData.get("section");
    if (!isSection(section)) return;
    await setSessionSection(section);
    redirect(`/${section}`);
  }

  return <RazdelPicker action={choose} />;
}
