import { notFound } from "next/navigation";
import { PagePlaceholder } from "@/components/page-placeholder";
import { Screen } from "@/screens";
import { hasPage } from "@/lib/menu";
import { isSection } from "@/lib/sections";

export default async function SectionPage({ params }: PageProps<"/[section]/[page]">) {
  const { section, page } = await params;
  if (!isSection(section) || !hasPage(section, page)) notFound();
  if (section !== "usluga") return <PagePlaceholder page={page} />;
  return <Screen page={page} />;
}
