import { notFound, redirect } from "next/navigation";
import { firstPage } from "@/lib/menu";
import { isSection } from "@/lib/sections";

// Корень программы открывает её первый пункт меню.
export default async function SectionHome({ params }: PageProps<"/[section]">) {
  const { section } = await params;
  if (!isSection(section)) notFound();
  redirect(`/${section}/${firstPage(section)}`);
}
