import { Check, Sparkles } from "lucide-react";
import { Brand } from "@/components/app-shell";

const benefits = [
  "Jobs ranked against your actual experience",
  "Clear match signals instead of keyword noise",
  "A simple pipeline from shortlist to offer",
];

export default function AuthShell({
  eyebrow,
  title,
  description,
  children,
}: {
  eyebrow: string;
  title: string;
  description: string;
  children: React.ReactNode;
}) {
  return (
    <main className="grid min-h-screen lg:grid-cols-[minmax(0,0.95fr)_minmax(520px,1.05fr)]">
      <section className="relative hidden overflow-hidden bg-[#17152d] px-12 py-10 text-white lg:flex lg:flex-col">
        <div className="absolute -left-32 top-36 size-96 rounded-full bg-primary/35 blur-3xl" />
        <div className="absolute -right-32 bottom-12 size-80 rounded-full bg-emerald-400/20 blur-3xl" />
        <div className="relative [&_a]:text-white">
          <Brand />
        </div>
        <div className="relative my-auto max-w-lg">
          <span className="inline-flex items-center gap-2 rounded-full border border-white/12 bg-white/8 px-3 py-1.5 text-xs font-medium text-white/75">
            <Sparkles className="size-3.5" />
            Search with signal
          </span>
          <h2 className="mt-6 text-4xl font-semibold leading-[1.08] tracking-[-0.045em]">
            Spend your energy on roles that deserve it.
          </h2>
          <div className="mt-8 space-y-4">
            {benefits.map((benefit) => (
              <div key={benefit} className="flex items-center gap-3 text-sm text-white/72">
                <span className="grid size-6 place-items-center rounded-full bg-white/10">
                  <Check className="size-3.5" />
                </span>
                {benefit}
              </div>
            ))}
          </div>
        </div>
        <p className="relative text-xs text-white/40">Focused search. Explainable ranking.</p>
      </section>

      <section className="flex min-h-screen items-center justify-center px-5 py-10 sm:px-10">
        <div className="w-full max-w-md">
          <div className="mb-10 lg:hidden">
            <Brand />
          </div>
          <p className="text-xs font-semibold uppercase tracking-[0.16em] text-primary">{eyebrow}</p>
          <h1 className="mt-3 text-3xl font-semibold tracking-[-0.045em]">{title}</h1>
          <p className="mt-2 text-sm leading-6 text-muted-foreground">{description}</p>
          <div className="mt-8">{children}</div>
        </div>
      </section>
    </main>
  );
}
