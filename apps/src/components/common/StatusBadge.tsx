export function StatusBadge({
  status,
  label,
}: {
  status: 'success' | 'warning' | 'failed' | 'running' | 'pending' | 'skipped' | 'human_review_required';
  label?: string;
}) {
  const styles: Record<string, string> = {
    success: 'bg-emerald-500/15 text-emerald-300 border-emerald-400/20',
    warning: 'bg-tertiary/10 text-tertiary border-tertiary/25',
    failed: 'bg-rose-500/15 text-rose-300 border-rose-400/20',
    running: 'bg-primary/10 text-primary border-primary/20',
    pending: 'bg-slate-500/15 text-slate-300 border-slate-400/20',
    skipped: 'bg-slate-500/15 text-slate-300 border-slate-400/20',
    human_review_required: 'bg-tertiary/15 text-tertiary border-tertiary/30',
  };

  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-1 text-xs font-semibold ${styles[status]}`}>
      {label ?? status}
    </span>
  );
}
