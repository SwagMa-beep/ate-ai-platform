import { Cpu, ShieldAlert, Wifi } from 'lucide-react';

export function Topbar({ title, description }: { title: string; description: string }) {
  return (
    <header className="flex items-center justify-between border-b border-outline-variant/10 bg-surface/85 px-6 py-4 backdrop-blur-md">
      <div>
        <div className="text-[11px] font-bold uppercase tracking-[0.24em] text-primary">ATE Agent Frontend</div>
        <h1 className="mt-1 text-2xl font-bold text-on-surface">{title}</h1>
        <p className="mt-1 text-sm text-on-surface-variant/80">{description}</p>
      </div>

      <div className="hidden items-center gap-3 lg:flex">
        <div className="flex items-center gap-2 rounded-full border border-outline-variant/15 bg-surface-container px-3 py-2 text-xs text-on-surface-variant">
          <Cpu className="h-4 w-4 text-primary" />
          STS8200S
        </div>
        <div className="flex items-center gap-2 rounded-full border border-tertiary/20 bg-tertiary/10 px-3 py-2 text-xs text-tertiary">
          <ShieldAlert className="h-4 w-4" />
          自动生成结果需工程复核
        </div>
        <div className="flex items-center gap-2 rounded-full border border-outline-variant/15 bg-surface-container px-3 py-2 text-xs text-primary">
          <Wifi className="h-4 w-4" />
          Agent Runtime
        </div>
      </div>
    </header>
  );
}
