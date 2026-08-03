import NextAuth from "next-auth";
import Credentials from "next-auth/providers/credentials";
import { api } from "@/lib/api";

const desktopMode =
  process.env.SIGNALRANK_MODE === "desktop" ||
  process.env.NEXT_PUBLIC_SIGNALRANK_MODE === "desktop";
const desktopCookieOptions = {
  httpOnly: true,
  sameSite: "lax" as const,
  path: "/",
  secure: false,
};

export const { handlers, auth, signIn, signOut } = NextAuth({
  cookies: desktopMode
    ? {
        sessionToken: {
          name: "signalrank.desktop.session-token",
          options: desktopCookieOptions,
        },
        callbackUrl: {
          name: "signalrank.desktop.callback-url",
          options: desktopCookieOptions,
        },
        csrfToken: {
          name: "signalrank.desktop.csrf-token",
          options: desktopCookieOptions,
        },
      }
    : undefined,
  providers: [
    Credentials({
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
        desktop: { label: "Desktop", type: "text" },
      },
      async authorize(credentials) {
        if (desktopMode) {
          try {
            const data = await api.desktop.session();
            if (!data.access_token) return null;
            return {
              id: "desktop-user",
              email: "local@signalrank.desktop",
              accessToken: data.access_token,
            };
          } catch (error) {
            console.error(
              "[auth] desktop backend session failed:",
              error instanceof Error ? `${error.name}: ${error.message}` : "unknown error",
            );
            return null;
          }
        }
        if (!credentials?.email || !credentials?.password) return null;
        try {
          const data = await api.auth.login(
            credentials.email as string,
            credentials.password as string
          );
          return { id: "user", email: credentials.email as string, accessToken: data.access_token };
        } catch {
          return null;
        }
      },
    }),
  ],
  callbacks: {
    async jwt({ token, user }) {
      if (user) token.accessToken = (user as { accessToken?: string }).accessToken;
      return token;
    },
    async session({ session, token }) {
      (session as { accessToken?: string }).accessToken = token.accessToken as string;
      return session;
    },
  },
  pages: {
    signIn: "/login",
  },
});
