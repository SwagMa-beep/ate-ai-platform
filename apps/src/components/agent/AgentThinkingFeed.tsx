import { Brain, ChevronDown, ChevronRight, Clock3, Sparkles } from 'lucide-react';

export interface ThinkingFeedEntry {
  id: string;
  time: string;
  label: string;
  detail: string;
  tone?: 'running' | 'completed' | 'warning';
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

function getSummary(entries: ThinkingFeedEntry[]) {
  const last = entries[entries.length - 1];
  const running = entries.some(entry => entry.tone === 'running');
  return {
    count: entries.length,
    running,
    latestLabel: last?.label || '暂无记录',
    latestDetail: last?.detail || '当前还没有可展示的实时思考记录。',
    latestTime: last?.time || '',
  };
}

export function AgentThinkingFeed({
  entries,
  collapsed,
  onToggle,
}: {
  entries: ThinkingFeedEntry[];
  collapsed?: boolean;
  onToggle?: () => void;
}) {
  if (!entries.length) {
    return (
      <div className="rounded-2xl border border-dashed border-outline-variant/20 bg-surface-container px-4 py-6 text-sm text-on-surface-variant/75">
        当前还没有可展示的实时思考记录。启动一次新 run 后，这里会按时间顺序滚动追加 Agent 的阶段动作。
      </div>
    );
  }

  const summary = getSummary(entries);

  if (collapsed) {
    return (
      <button
        type="button"
        onClick={onToggle}
        className="w-full rounded-2xl border border-outline-variant/12 bg-surface-container p-4 text-left transition hover:border-primary/25 hover:bg-surface-container-high"
      >
        <div className="flex items-start justify-between gap-4">
          <div className="flex min-w-0 gap-3">
            <div className={`rounded-full p-2 ${summary.running ? 'bg-primary/10 text-primary' : 'bg-surface text-on-surface-variant'}`}>
              {summary.running ? <Brain className="h-4 w-4 animate-pulse" /> : <Sparkles className="h-4 w-4" />}
            </div>
            <div className="min-w-0">
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className="font-semibold text-on-surface">Thinking Feed 已折叠</span>
                <span className="rounded-full bg-surface px-2 py-0.5 text-on-surface-variant/70">{summary.count} 条记录</span>
                <span className="rounded-full bg-surface px-2 py-0.5 text-on-surface-variant/70">{summary.latestLabel}</span>
              </div>
              <div className="mt-2 line-clamp-2 text-sm leading-relaxed text-on-surface-variant/80">{summary.latestDetail}</div>
              <div className="mt-2 inline-flex items-center gap-1 text-xs text-on-surface-variant/60">
                <Clock3 className="h-3 w-3" />
                最近更新 {formatClock(summary.latestTime)}
              </div>
            </div>
          </div>
          <div className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary">
            <ChevronRight className="h-3.5 w-3.5" />
            展开
          </div>
        </div>
      </button>
    );
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between gap-3 rounded-2xl border border-outline-variant/12 bg-surface-container px-4 py-3">
        <div className="flex items-center gap-2 text-xs text-on-surface-variant/75">
          <span className="font-semibold text-on-surface">实时思考记录</span>
          <span className="rounded-full bg-surface px-2 py-0.5">{summary.count} 条</span>
          <span className={`rounded-full px-2 py-0.5 ${summary.running ? 'bg-primary/10 text-primary' : 'bg-surface text-on-surface-variant/70'}`}>
            {summary.running ? '执行中' : '已完成'}
          </span>
        </div>
        {onToggle ? (
          <button
            type="button"
            onClick={onToggle}
            className="inline-flex items-center gap-1 rounded-full bg-primary/10 px-2.5 py-1 text-xs font-semibold text-primary transition hover:brightness-110"
          >
            <ChevronDown className="h-3.5 w-3.5" />
            折叠
          </button>
        ) : null}
      </div>

      {entries.map((entry, index) => {
        const running = entry.tone === 'running';
        const toneClass =
          entry.tone === 'completed'
            ? 'border-emerald-400/15 bg-emerald-500/5'
            : entry.tone === 'warning'
              ? 'border-tertiary/15 bg-tertiary/5'
              : 'border-primary/15 bg-primary/5';
        return (
          <div key={entry.id} className={`rounded-2xl border px-4 py-3 ${toneClass}`}>
            <div className="flex items-start gap-3">
              <div className={`mt-0.5 rounded-full p-2 ${running ? 'bg-primary/10 text-primary' : 'bg-surface text-on-surface-variant'}`}>
                {running ? <Brain className="h-4 w-4 animate-pulse" /> : <Sparkles className="h-4 w-4" />}
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2 text-xs">
                  <span className="font-semibold text-on-surface">#{String(index + 1).padStart(2, '0')}</span>
                  <span className="rounded-full bg-surface px-2 py-0.5 text-on-surface-variant/70">{entry.label}</span>
                  <span className="inline-flex items-center gap-1 text-on-surface-variant/60">
                    <Clock3 className="h-3 w-3" />
                    {formatClock(entry.time)}
                  </span>
                </div>
                <div className={`mt-2 text-sm leading-relaxed ${running ? 'text-primary animate-pulse' : 'text-on-surface-variant/85'}`}>{entry.detail}</div>
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
