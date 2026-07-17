import { redirect } from "next/navigation";
import { auth } from "@/auth";

export default async function HomePage() {
  if (
    process.env.SIGNALRANK_MODE === "desktop" ||
    process.env.NEXT_PUBLIC_SIGNALRANK_MODE === "desktop"
  ) {
    redirect("/desktop-setup");
  }
  const session = await auth();
  if (session) redirect("/dashboard");
  redirect("/login");
}
