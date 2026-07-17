import { signIn } from "@/auth";

export async function POST() {
  if (process.env.SIGNALRANK_MODE !== "desktop") {
    return Response.json({ detail: "Desktop mode is disabled" }, { status: 404 });
  }
  try {
    await signIn("credentials", { desktop: "true", redirect: false });
    return Response.json({ status: "ok" });
  } catch {
    return Response.json(
      { detail: "The protected local session could not be started" },
      { status: 503 },
    );
  }
}
