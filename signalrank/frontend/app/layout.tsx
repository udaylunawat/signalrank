import type { Metadata } from "next";
import NextAuthSessionProvider from "@/components/session-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "SignalRank",
  description: "A focused job search, ranked around you.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className="h-full antialiased"
    >
      <body className="min-h-full">
        <NextAuthSessionProvider>{children}</NextAuthSessionProvider>
      </body>
    </html>
  );
}
