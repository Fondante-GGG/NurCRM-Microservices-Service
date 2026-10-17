import type { Metadata } from "next";
import { Montserrat } from "next/font/google";
import { I18nProvider } from "@/i18n/provider";
import { StoreProvider } from "@/data/store";
import "./globals.css";

const montserrat = Montserrat({
  variable: "--font-montserrat",
  subsets: ["latin", "cyrillic"],
  weight: ["400", "500", "600", "700", "800"],
});

export const metadata: Metadata = {
  title: "NurCRM",
  description: "Программа для бизнеса: услуги, склад, маркет, производство",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ru" className={`${montserrat.variable} h-full antialiased`}>
      <body className="min-h-full flex flex-col">
        <I18nProvider>
          <StoreProvider>{children}</StoreProvider>
        </I18nProvider>
      </body>
    </html>
  );
}
