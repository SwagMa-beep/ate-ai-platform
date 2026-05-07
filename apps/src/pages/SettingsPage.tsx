import type { ReactNode } from 'react';
import { MoonStar, SunMedium } from 'lucide-react';
import { Card } from '../components/common/Card';
import type { ThemeMode } from '../types';

function ThemeOption({
  active,
  icon,
  title,
  onClick,
}: {
  active: boolean;
  icon: ReactNode;
  title: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-2xl border p-4 text-left transition ${
        active
          ? 'border-primary/35 bg-primary/10 shadow-[0_0_0_1px_rgba(111,147,184,0.18)]'
          : 'border-outline-variant/12 bg-surface-container hover:border-primary/20 hover:bg-surface-container-high'
      }`}
    >
      <div className="flex items-center gap-3">
        <div className={`rounded-xl p-2 ${active ? 'bg-primary/15 text-primary' : 'bg-surface-bright text-on-surface-variant'}`}>{icon}</div>
        <div className="text-sm font-semibold text-on-surface">{title}</div>
      </div>
      <div className="mt-4 text-xs font-semibold text-primary">{active ? '当前已启用' : '点击切换'}</div>
    </button>
  );
}

export function SettingsPage({
  themeMode,
  onThemeChange,
}: {
  themeMode: ThemeMode;
  onThemeChange: (mode: ThemeMode) => void;
}) {
  return (
    <div className="space-y-6">
      <Card title="主题设置">
        <div className="grid gap-4 lg:grid-cols-2">
          <ThemeOption
            active={themeMode === 'dark'}
            icon={<MoonStar className="h-5 w-5" />}
            title="工业深色"
            onClick={() => onThemeChange('dark')}
          />
          <ThemeOption
            active={themeMode === 'light'}
            icon={<SunMedium className="h-5 w-5" />}
            title="白天浅色"
            onClick={() => onThemeChange('light')}
          />
        </div>
      </Card>
    </div>
  );
}
