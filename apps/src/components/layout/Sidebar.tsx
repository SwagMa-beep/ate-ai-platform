import { useEffect, useState } from 'react';
import {
  Bot,
  BookMarked,
  ChevronLeft,
  ChevronRight,
  Gauge,
  Microscope,
  Network,
  Settings2,
  TerminalSquare,
  Workflow,
} from 'lucide-react';
import type { View } from '../../types';

const SIDEBAR_STORAGE_KEY = 'ate-sidebar-collapsed';

const navGroups: Array<{
  title: string;
  items: Array<{ label: string; key: View; icon: typeof Bot }>;
}> = [
  {
    title: '智能开发',
    items: [
      { label: 'ATE Agent 工作台', key: 'agent-workspace', icon: Bot },
      { label: 'Agent 运行中心', key: 'agent-runs', icon: Workflow },
    ],
  },
  {
    title: '功能模块',
    items: [
      { label: 'Datasheet / TestPlan', key: 'testplan', icon: BookMarked },
      { label: 'STS8200S 资源映射', key: 'resource-map', icon: Network },
      { label: 'RAG 测试代码生成', key: 'codegen', icon: TerminalSquare },
      { label: '良率诊断', key: 'diagnosis', icon: Microscope },
    ],
  },
  {
    title: '系统',
    items: [
      { label: '知识库管理', key: 'knowledge-base', icon: Gauge },
      { label: '设置', key: 'settings', icon: Settings2 },
    ],
  },
];

export function Sidebar({
  currentView,
  onViewChange,
}: {
  currentView: View;
  onViewChange: (view: View) => void;
}) {
  const [collapsed, setCollapsed] = useState(false);
  const [hoverExpanded, setHoverExpanded] = useState(false);

  const expanded = !collapsed || hoverExpanded;

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const saved = window.localStorage.getItem(SIDEBAR_STORAGE_KEY);
    setCollapsed(saved === 'true');
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(collapsed));
  }, [collapsed]);

  return (
    <aside
      onMouseEnter={() => {
        if (collapsed) {
          setHoverExpanded(true);
        }
      }}
      onMouseLeave={() => setHoverExpanded(false)}
      className={`flex h-full shrink-0 flex-col border-r border-outline-variant/10 bg-surface-container-low px-4 py-5 transition-[width,padding] duration-300 ${
        expanded ? 'w-[280px]' : 'w-[92px]'
      }`}
    >
      <div className="mb-6 flex items-start justify-between gap-3">
        {expanded ? (
          <div className="rounded-2xl border border-primary/15 bg-primary/5 px-4 py-4">
            <div className="text-[11px] font-bold uppercase tracking-[0.25em] text-primary">ATE AI Platform</div>
            <div className="mt-2 text-lg font-semibold text-on-surface">Agent 工作流与手动工具协同</div>
            <p className="mt-2 text-sm leading-relaxed text-on-surface-variant/75">
              通过 Agent 工作台串联完整开发流程，同时保留各模块页面，方便单独查看、校验和手动处理。
            </p>
          </div>
        ) : (
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl border border-primary/15 bg-primary/6 text-primary">
            <Bot className="h-6 w-6" />
          </div>
        )}

        <button
          type="button"
          onClick={() => setCollapsed(value => !value)}
          className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-outline-variant/20 bg-surface-container text-on-surface-variant transition hover:border-primary/25 hover:text-on-surface"
          aria-label={collapsed ? '展开侧栏' : '折叠侧栏'}
          title={collapsed ? '展开侧栏' : '折叠侧栏'}
        >
          {collapsed ? <ChevronRight className="h-4 w-4" /> : <ChevronLeft className="h-4 w-4" />}
        </button>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto custom-scrollbar pr-1">
        {navGroups.map(group => (
          <div key={group.title}>
            {expanded ? (
              <div className="mb-2 px-2 text-[10px] font-bold uppercase tracking-[0.25em] text-on-surface-variant/55">
                {group.title}
              </div>
            ) : null}

            <div className="space-y-1">
              {group.items.map(item => {
                const active = currentView === item.key;
                const Icon = item.icon;
                return (
                  <button
                    key={item.key}
                    type="button"
                    onClick={() => onViewChange(item.key)}
                    className={`flex w-full items-center rounded-xl text-left transition ${
                      expanded ? 'gap-3 px-3 py-3' : 'justify-center px-0 py-3'
                    } ${
                      active
                        ? 'bg-primary/12 text-primary shadow-[0_0_0_1px_rgba(83,221,252,0.15)]'
                        : 'text-on-surface-variant hover:bg-surface-container hover:text-on-surface'
                    }`}
                    aria-label={item.label}
                    title={item.label}
                  >
                    <Icon className="h-4 w-4 shrink-0" />
                    {expanded ? <span className="text-sm font-medium">{item.label}</span> : null}
                  </button>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
