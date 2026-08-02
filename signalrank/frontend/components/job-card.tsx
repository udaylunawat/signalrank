import {
  ArrowUpRight,
  BookmarkPlus,
  Building2,
  ChevronDown,
  ChevronUp,
  CircleAlert,
  Clock3,
  LoaderCircle,
  MapPin,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { memo, useState } from "react";
import type {
  Job,
  JobDetail,
  JobFeedbackReason,
  JobFeedbackValue,
} from "@/types";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { openExternal } from "@/lib/desktop";

const feedbackReasons: Array<{ value: JobFeedbackReason; label: string }> = [
  { value: "wrong_role", label: "Wrong role" },
  { value: "wrong_seniority", label: "Wrong seniority" },
  { value: "wrong_location", label: "Wrong location" },
  { value: "other", label: "Other" },
];

function scoreMeta(score: number | null) {
  const value = score == null ? null : Math.round(score);
  if (value == null) {
    return { value: "—", label: "Unscored", tone: "bg-muted text-muted-foreground" };
  }
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

function formatDate(value: string | null) {
  if (!value) return "Unavailable";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Unavailable";
  return date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
}

function scoreRows(job: Job) {
  return [
    ["Role relevance", job.semantic_score],
    ["Skills", job.skills_score],
    ["Company", job.company_score],
    ["Seniority", job.seniority_score],
    ["Location", job.location_score],
    ["Recency", job.recency_score],
  ].filter(([, score]) => score != null) as Array<[string, number]>;
}

function JobCard({
  job,
  compact = false,
  dense = false,
  tracked = false,
  tracking = false,
  onTrack,
  feedback,
  feedbacking = false,
  onFeedback,
  expanded = false,
  detail,
  detailLoading = false,
  detailError = "",
  onToggleDetails,
}: {
  job: Job;
  compact?: boolean;
  dense?: boolean;
  tracked?: boolean;
  tracking?: boolean;
  onTrack?: (job: Job) => void;
  feedback?: JobFeedbackValue | null;
  feedbacking?: boolean;
  onFeedback?: (
    job: Job,
    value: JobFeedbackValue,
    reason?: JobFeedbackReason,
  ) => void;
  expanded?: boolean;
  detail?: JobDetail | null;
  detailLoading?: boolean;
  detailError?: string;
  onToggleDetails?: (job: Job) => void;
}) {
  const [showFeedbackReasons, setShowFeedbackReasons] = useState(false);
  const [externalError, setExternalError] = useState("");
  const score = scoreMeta(job.final_score);
  const posted = postedLabel(job.date_posted);
  const reputationTier = job.company_tier?.replace(/^tier_/, "").toUpperCase();
  const matchedSkills = job.explanation?.matched_skills?.slice(0, 4) ?? [];
  const detailJob = detail ?? job;

  async function handleOpenRole() {
    setExternalError("");
    try {
      await openExternal(job.job_url);
    } catch {
      setExternalError("This role does not have a secure link we can open.");
    }
  }

  function submitNegativeFeedback(reason: JobFeedbackReason) {
    setShowFeedbackReasons(false);
    onFeedback?.(job, "not_relevant", reason);
  }

  return (
    <article className={cn(
      "group rounded-2xl border border-border/75 bg-white/90 shadow-[0_1px_2px_rgba(20,20,35,0.03)] transition-all hover:-translate-y-0.5 hover:border-primary/25 hover:shadow-[0_16px_38px_rgba(58,48,120,0.09)]",
      dense ? "p-3 sm:p-4" : "p-4 sm:p-5",
    )}>
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

          <div className="mt-4 flex flex-wrap items-center gap-2">
            {!compact && onToggleDetails && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="min-h-10 rounded-xl"
                aria-expanded={expanded}
                onClick={() => onToggleDetails(job)}
              >
                Why it fits
                {expanded ? <ChevronUp data-icon="inline-end" /> : <ChevronDown data-icon="inline-end" />}
              </Button>
            )}
            <Button
              type="button"
              size="sm"
              className="min-h-10 rounded-xl"
              onClick={() => void handleOpenRole()}
            >
              View role
              <ArrowUpRight data-icon="inline-end" />
            </Button>
            {onTrack && (
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="min-h-10 rounded-xl"
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
                  className="min-h-10 rounded-xl"
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
                  className="min-h-10 rounded-xl"
                  disabled={feedbacking}
                  onClick={() => setShowFeedbackReasons((current) => !current)}
                >
                  <ThumbsDown data-icon="inline-start" />
                  Not a fit
                </Button>
              </>
            )}
          </div>

          {externalError && (
            <p role="alert" className="mt-3 text-sm text-destructive">{externalError}</p>
          )}

          {!compact && showFeedbackReasons && (
            <fieldset className="mt-4 rounded-xl border border-border/80 bg-muted/35 p-3">
              <legend className="px-1 text-sm font-medium">What missed the mark?</legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {feedbackReasons.map((reason) => (
                  <Button
                    key={reason.value}
                    type="button"
                    variant="outline"
                    size="sm"
                    className="min-h-10 rounded-xl"
                    disabled={feedbacking}
                    onClick={() => submitNegativeFeedback(reason.value)}
                  >
                    {reason.label}
                  </Button>
                ))}
              </div>
            </fieldset>
          )}

          {!compact && expanded && (
            <section className="mt-5 rounded-xl border border-primary/12 bg-primary/3 p-4" aria-label={`Why ${job.title} fits`}>
              {detailLoading ? (
                <div className="flex min-h-32 items-center justify-center gap-2 text-sm text-muted-foreground">
                  <LoaderCircle className="size-4 animate-spin" />
                  Loading the match explanation…
                </div>
              ) : detailError ? (
                <p role="alert" className="text-sm text-destructive">{detailError}</p>
              ) : detail ? (
                <div className="space-y-5">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h4 className="font-semibold tracking-[-0.02em]">Why this role fits</h4>
                      <p className="mt-1 text-sm text-muted-foreground">
                        Ranked from your latest completed search on {formatDate(detail.completed_at)}.
                      </p>
                    </div>
                    {detailJob.explanation?.role_fit?.lane && (
                      <Badge variant="secondary">{detailJob.explanation.role_fit.lane} lane</Badge>
                    )}
                  </div>

                  <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
                    {scoreRows(detailJob).map(([label, value]) => (
                      <div key={label} className="rounded-lg border border-border/70 bg-white/75 px-3 py-2">
                        <p className="text-xs text-muted-foreground">{label}</p>
                        <p className="mt-0.5 text-sm font-semibold tabular-nums">{Math.round(value)}</p>
                      </div>
                    ))}
                    {scoreRows(detailJob).length === 0 && (
                      <p className="text-sm text-muted-foreground">Score details are unavailable for this role.</p>
                    )}
                  </div>

                  <div className="grid gap-4 lg:grid-cols-2">
                    <div>
                      <h5 className="text-sm font-medium">Matched signals</h5>
                      {detailJob.explanation?.matched_skills?.length ? (
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {detailJob.explanation.matched_skills.map((skill) => (
                            <Badge key={skill} variant="outline">{skill}</Badge>
                          ))}
                        </div>
                      ) : (
                        <p className="mt-2 text-sm text-muted-foreground">No matched skills were provided.</p>
                      )}
                    </div>
                    <div>
                      <h5 className="text-sm font-medium">Possible gaps</h5>
                      {detailJob.explanation?.concerns?.length ? (
                        <ul className="mt-2 space-y-1 text-sm text-muted-foreground">
                          {detailJob.explanation.concerns.map((concern) => (
                            <li key={concern} className="flex gap-2">
                              <CircleAlert className="mt-0.5 size-4 shrink-0 text-amber-700" />
                              <span>{concern}</span>
                            </li>
                          ))}
                        </ul>
                      ) : (
                        <p className="mt-2 text-sm text-muted-foreground">No concerns were identified.</p>
                      )}
                    </div>
                  </div>

                  <div>
                    <h5 className="text-sm font-medium">Role details</h5>
                    <p className="mt-2 max-h-72 overflow-y-auto whitespace-pre-wrap text-sm leading-6 text-muted-foreground">
                      {detailJob.description || "A job description was not available from this source."}
                    </p>
                  </div>
                </div>
              ) : null}
            </section>
          )}
        </div>
      </div>
    </article>
  );
}

export default memo(JobCard);
