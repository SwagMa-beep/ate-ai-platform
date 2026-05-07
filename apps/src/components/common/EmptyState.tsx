import type { ReactNode } from 'react';

export function EmptyState({ title, description, icon }: { title: string; description: string; icon?: ReactNode }) {
  return (
    <div className="flex min-h-40 flex-col items-center justify-center rounded-2xl border border-dashed border-outline-variant/20 bg-surface-container px-6 py-10 text-center">
      {icon ? <div className="mb-4 text-primary">{icon}</div> : null}
      <h3 className="text-sm font-semibold text-on-surface">{title}</h3>
      <p className="mt-2 max-w-md text-sm leading-relaxed text-on-surface-variant/80">{description}</p>
    </div>
  );
}
