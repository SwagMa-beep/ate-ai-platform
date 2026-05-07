import type { ReactNode } from 'react';
import { MoonStar, SunMedium } from 'lucide-react';
import { Card } from '../components/common/Card';
import type { ThemeMode } from '../types';

function ThemeOption({
  active,
  icon,
  title,
  description,
  onClick,
}: {
  active: boolean;
  icon: ReactNode;
  title: string;
  description: string;
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
        <div>
          <div className="text-sm font-semibold text-on-surface">{title}</div>
          <div className="mt-1 text-xs text-on-surface-variant/80">{description}</div>
        </div>
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
      <Card title="主题设置" subtitle="切换更适合白天办公或夜间调试的界面主题。切换后会自动记住你的选择。">
        <div className="grid gap-4 lg:grid-cols-2">
          <ThemeOption
            active={themeMode === 'dark'}
            icon={<MoonStar className="h-5 w-5" />}
            title="工业深色"
            description="适合长时间看代码、运行时间线和诊断结果，降低夜间视觉刺激。"
            onClick={() => onThemeChange('dark')}
          />
          <ThemeOption
            active={themeMode === 'light'}
            icon={<SunMedium className="h-5 w-5" />}
            title="白天浅色"
            description="白底黑字，适合白天办公、汇报展示和长时间阅读表格文档。"
            onClick={() => onThemeChange('light')}
          />
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="当前阶段" subtitle="第一版先补主题切换，后续再接更细的系统配置能力。">
          <p className="text-sm leading-relaxed text-on-surface-variant/80">
            当前设置页优先提供桌面端最有感知的全局主题切换，不破坏现有 Electron / Vite 启动方式。
          </p>
        </Card>
        <Card title="安全边界" subtitle="保持前端配置可控，不引入敏感信息。">
          <p className="text-sm leading-relaxed text-on-surface-variant/80">
            不在前端写入敏感 Key，不把主题切换和业务接口耦合，确保 Web 与 Electron 双端都能稳定生效。
          </p>
        </Card>
      </div>
    </div>
  );
}
