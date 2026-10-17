import { redirect } from "next/navigation";

// Корень сайта: proxy.ts сам отправляет на вход или в раздел, это запасной вариант.
export default function Home() {
  redirect("/login");
}
