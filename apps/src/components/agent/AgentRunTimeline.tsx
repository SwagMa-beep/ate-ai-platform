import { AlertTriangle, CheckCircle2, Clock3, Loader2, PauseCircle } from 'lucide-react';
import { type AgentRunStep } from '../../api/backend';
import { getRunStatusPresentation, getStepLabel } from '../../utils/runPresentation';
import { StatusBadge } from '../common/StatusBadge';

const icons = {
  completed: CheckCircle2,
  warning: AlertTriangle,
  failed: AlertTriangle,
  running: Loader2,
  pending: Clock3,
  skipped: PauseCircle,
  human_review_required: AlertTriangle,
  approved: CheckCircle2,
  rejected: AlertTriangle,
} as const;

function readStepTime(step: AgentRunStep, field: 'started_at' | 'finished_at') {
  const metadata = (step.metadata as Record<string, unknown> | undefined) || {};
  return typeof metadata[field] === 'string' ? metadata[field] : '';
}

function readStepDuration(step: AgentRunStep) {
  const metadata = (step.metadata as Record<string, unknown> | undefined) || {};
  return typeof metadata.duration_seconds === 'number' ? metadata.duration_seconds : null;
}

function formatClock(value?: string) {
  if (!value) return '--:--:--';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '--:--:--';
  return new Intl.DateTimeFormat('zh-CN', {
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  }).format(date);
}

function formatDuration(value: number | null) {
  if (value == null) return '进行中';
  if (value < 1) return `${Math.max(value, 0.01).toFixed(2)} 秒`;
  if (value < 60) return `${value.toFixed(1)} 秒`;
  const minutes = Math.floor(value / 60);
  const seconds = Math.round(value % 60);
  return `${minutes} 分 ${seconds} 秒`;
}

function getStatusKey(status?: string) {
  if (status === 'completed') return 'success';
  if (status === 'warning' || status === 'failed' || status === 'running' || status === 'pending' || status === 'skipped' || status === 'human_review_required') {
    return status;
  }
  return 'pending';
}

export function AgentRunTimeline({ steps }: { steps: AgentRunStep[] }) {
  return (
    <div className="space-y-4">
      {steps.map((step, index) => {
        const presentation = getRunStatusPresentation(step.status);
        const statusKey = getStatusKey(step.status);
        const Icon = icons[statusKey] ?? Clock3;
        const startedAt = readStepTime(step, 'started_at');
        const finishedAt = readStepTime(step, 'finished_at');
        const duration = readStepDuration(step);
        const isRunning = step.status === 'running';
        const riskFlags = step.quality?.risk_flags || [];

        return (
          <div
            key={`${step.agent}-${index}`}
            className={`relative overflow-hidden rounded-2xl border bg-surface-container p-4 transition-all ${
              isRunning ? 'border-primary/30 shadow-lg shadow-primary/10' : 'border-outline-variant/12'
            }`}
          >
            {isRunning ? (
              <div className="pointer-events-none absolute inset-x-0 top-0 h-0.5 bg-gradient-to-r from-transparent via-primary to-transparent opacity-80 animate-pulse" />
            ) : null}

            <div className="flex flex-wrap items-start justify-between gap-3">
              <div className="flex gap-3">
                <div className="mt-0.5 flex h-10 w-10 items-center justify-center rounded-full border border-outline-variant/10 bg-surface">
                  <Icon className={`h-5 w-5 ${isRunning ? 'animate-spin text-primary' : presentation.tone.split(' ')[0]}`} />
                </div>
                <div>
                  <div className="flex flex-wrap items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-on-surface-variant/55">
                    <span>步骤 {index + 1}</span>
                    {isRunning ? (
                      <span className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2 py-0.5 text-primary">
                        <span className="h-1.5 w-1.5 rounded-full bg-primary animate-pulse" />
                        正在思考
                      </span>
                    ) : null}
                  </div>
                  <div className="mt-1 text-sm font-semibold text-on-surface">{getStepLabel(step.agent)}</div>
                  <div className={`mt-1 text-sm leading-relaxed ${isRunning ? 'text-primary/90 animate-pulse' : 'text-on-surface-variant/80'}`}>
                    {step.message || '该阶段未返回额外说明。'}
                  </div>
                  {step.next_action ? <div className="mt-2 text-xs text-primary">下一步：{step.next_action}</div> : null}
                </div>
              </div>

              <div className="flex flex-col items-end gap-2">
                <StatusBadge status={statusKey} label={presentation.label} />
                <div className="rounded-full bg-surface px-2.5 py-1 text-[11px] text-on-surface-variant/70">
                  耗时 {formatDuration(duration)}
                </div>
              </div>
            </div>

            <div className="mt-4 grid gap-3 lg:grid-cols-[minmax(0,1fr)_240px]">
              <div className="space-y-3">
                <div className="flex flex-wrap gap-2 text-xs text-on-surface-variant/75">
                  {step.quality ? (
                    <span
                      className={`rounded-full px-2.5 py-1 font-medium ${
                        step.quality.score >= 0.8
                          ? 'bg-emerald-500/15 text-emerald-300'
                          : step.quality.score >= 0.5
                            ? 'bg-tertiary/15 text-tertiary'
                            : 'bg-rose-500/15 text-rose-300'
                      }`}
                    >
                      质量 {(step.quality.score * 100).toFixed(0)}%
                    </span>
                  ) : null}
                  <span className="rounded-full bg-surface-bright px-2.5 py-1">产物 {step.artifacts?.length ?? 0}</span>
                  <span className="rounded-full bg-surface-bright px-2.5 py-1">警告 {step.warnings?.length ?? 0}</span>
                  <span className="rounded-full bg-surface-bright px-2.5 py-1">错误 {step.errors?.length ?? 0}</span>
                  {typeof step.metadata?.attempts === 'number' ? <span className="rounded-full bg-surface-bright px-2.5 py-1">尝试 {step.metadata.attempts}</span> : null}
                  {typeof step.metadata?.retries_used === 'number' ? <span className="rounded-full bg-surface-bright px-2.5 py-1">重试 {step.metadata.retries_used}</span> : null}
                </div>

                {(step.errors?.length || step.warnings?.length || riskFlags.length) ? (
                  <div className="grid gap-2">
                    {step.errors?.slice(0, 2).map(error => (
                      <div key={error} className="rounded-xl border border-rose-400/15 bg-rose-500/5 px-3 py-2 text-xs leading-relaxed text-rose-300">
                        {error}
                      </div>
                    ))}
                    {!step.errors?.length &&
                      step.warnings?.slice(0, 2).map(warning => (
                        <div key={warning} className="rounded-xl border border-tertiary/15 bg-tertiary/5 px-3 py-2 text-xs leading-relaxed text-tertiary">
                          {warning}
                        </div>
                      ))}
                    {!step.errors?.length &&
                      !step.warnings?.length &&
                      riskFlags.slice(0, 2).map(flag => (
                        <div key={flag} className="rounded-xl border border-outline-variant/12 bg-surface px-3 py-2 text-xs leading-relaxed text-on-surface-variant/80">
                          {flag}
                        </div>
                      ))}
                  </div>
                ) : null}
              </div>

              <div className="rounded-2xl border border-outline-variant/10 bg-surface px-4 py-3">
                <div className="text-[10px] font-semibold uppercase tracking-widest text-on-surface-variant/55">时间记录</div>
                <div className="mt-3 space-y-2 text-xs text-on-surface-variant/75">
                  <div className="flex items-center justify-between gap-3">
                    <span>开始</span>
                    <span className="font-mono text-on-surface">{formatClock(startedAt)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>结束</span>
                    <span className="font-mono text-on-surface">{finishedAt ? formatClock(finishedAt) : '进行中'}</span>
                  </div>
                  <div className="flex items-center justify-between gap-3">
                    <span>阶段耗时</span>
                    <span className="font-mono text-primary">{formatDuration(duration)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
