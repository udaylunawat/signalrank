import { ArrowUpRight, BookmarkPlus, Building2, Clock3, MapPin, ThumbsDown, ThumbsUp } from "lucide-react";
import type { Job, JobFeedbackValue } from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { openExternal } from "@/lib/desktop";

function scoreMeta(score: number | null) {
  const value = score == null ? null : Math.round(score);
  if (value == null) return { value: "—", label: "Unscored", tone: "bg-muted text-muted-foreground" };
  if (value >= 80) return { value, label: "Excellent", tone: "bg-emerald-50 text-emerald-700" };
  if (value >= 65) return { value, label: "Strong", tone: "bg-indigo-50 text-indigo-700" };
  return { value, label: "Possible", tone: "bg-amber-50 text-amber-700" };
}

function postedLabel(value: string | null) {
  if (!value) return null;
  const days = Math.floor((Date.now() - new Date(value).getTime()) / 86_400_000);
  if (Number.isNaN(days)) return null;
  if (days <= 0) return "Today";
  if (days === 1) return "Yesterday";
  return `${days}d ago`;
}

export default function JobCard({
  job,
  compact = false,
  tracked = false,
  tracking = false,
  onTrack,
  feedback,
  feedbacking = false,
  onFeedback,
}: {
  job: Job;
  compact?: boolean;
  tracked?: boolean;
  tracking?: boolean;
  onTrack?: (job: Job) => void;
  feedback?: JobFeedbackValue | null;
  feedbacking?: boolean;
  onFeedback?: (job: Job, value: JobFeedbackValue) => void;
}) {
  const score = scoreMeta(job.final_score);
  const posted = postedLabel(job.date_posted);
  const reputationTier = job.company_tier?.replace(/^tier_/, "").toUpperCase();
  const matchedSkills = job.explanation?.matched_skills?.slice(0, 4) ?? [];

  return (
    <article className="group rounded-2xl border border-border/75 bg-white/90 p-4 shadow-[0_1px_2px_rgba(20,20,35,0.03)] transition-all hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-[0_16px_38px_rgba(58,48,120,0.09)] sm:p-5">
      <div className="flex items-start gap-3 sm:gap-4">
        <div className="grid size-11 shrink-0 place-items-center rounded-xl bg-secondary text-secondary-foreground ring-1 ring-primary/8">
          <Building2 className="size-5" strokeWidth={1.8} />
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate text-[15px] font-semibold tracking-[-0.02em] sm:text-base">
                {job.title}
              </h3>
              <p className="mt-0.5 truncate text-sm text-muted-foreground">{job.company}</p>
            </div>
            <div className={cn("flex shrink-0 items-center gap-2 rounded-xl px-2.5 py-1.5", score.tone)}>
              <span className="text-sm font-semibold tabular-nums">{score.value}</span>
              <span className="hidden text-[11px] font-medium sm:inline">{score.label}</span>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
            {job.location && (
              <span className="flex items-center gap-1">
                <MapPin className="size-3.5" />
                {job.location}
              </span>
            )}
            {posted && (
              <span className="flex items-center gap-1">
                <Clock3 className="size-3.5" />
                {posted}
              </span>
            )}
            {job.site && <span className="capitalize">via {job.site}</span>}
          </div>

          {!compact && (
            <div className="mt-4 flex flex-wrap gap-1.5">
              {reputationTier &&
                reputationTier !== "DEFAULT" &&
                (job.company_reputation_confidence ?? 0) >= 0.7 && (
                <Badge variant="secondary">Company {reputationTier}</Badge>
              )}
              {job.is_contract && <Badge variant="outline">Contract</Badge>}
              {job.skills_score != null && (
                <Badge variant="outline">Skills {Math.round(job.skills_score)}%</Badge>
              )}
              {matchedSkills.map((skill) => (
                <Badge key={skill} variant="outline">{skill}</Badge>
              ))}
            </div>
          )}

          {!compact && job.company_reputation_rationale && (
            <p className="mt-3 text-xs leading-5 text-muted-foreground">
              Company signal: {job.company_reputation_rationale}
            </p>
          )}

          <div className="mt-4 flex items-center gap-2">
            <Button
              type="button"
              size="sm"
              className="rounded-xl"
              onClick={() => void openExternal(job.job_url)}
            >
              View role
              <ArrowUpRight data-icon="inline-end" />
            </Button>
            {onTrack && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="rounded-xl"
                disabled={tracked || tracking}
                onClick={() => onTrack(job)}
              >
                <BookmarkPlus data-icon="inline-start" />
                {tracked ? "Saved" : tracking ? "Saving…" : "Track"}
              </Button>
            )}
            {!compact && onFeedback && (
              <>
                <Button
                  type="button"
                  variant={feedback === "relevant" ? "default" : "outline"}
                  size="sm"
                  className="rounded-xl"
                  disabled={feedbacking}
                  onClick={() => onFeedback(job, "relevant")}
                >
                  <ThumbsUp data-icon="inline-start" />
                  Good match
                </Button>
                <Button
                  type="button"
                  variant={feedback === "not_relevant" ? "default" : "outline"}
                  size="sm"
                  className="rounded-xl"
                  disabled={feedbacking}
                  onClick={() => onFeedback(job, "not_relevant")}
                >
                  <ThumbsDown data-icon="inline-start" />
                  Not a fit
                </Button>
              </>
            )}
          </div>
        </div>
      </div>
    </article>
  );
}
