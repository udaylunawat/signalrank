import { redirect } from "next/navigation";

export default function AuthLayout({ children }: { children: React.ReactNode }) {
  if (
    process.env.SIGNALRANK_MODE === "desktop" ||
    process.env.NEXT_PUBLIC_SIGNALRANK_MODE === "desktop"
  ) {
    redirect("/desktop-setup");
  }
  return children;
}
