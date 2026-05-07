import { lazy, Suspense, useEffect, useState } from 'react';
import { Card } from './components/common/Card';
import { AppLayout } from './components/layout/AppLayout';
import type { ThemeMode, View } from './types';
import { viewMeta } from './types';

const AgentWorkspacePage = lazy(() =>
  import('./pages/AgentWorkspacePage').then(module => ({ default: module.AgentWorkspacePage })),
);
const AgentRunsPage = lazy(() => import('./pages/AgentRunsPage').then(module => ({ default: module.AgentRunsPage })));
const TestPlanPage = lazy(() => import('./pages/TestPlanPage').then(module => ({ default: module.TestPlanPage })));
const ResourceMapPage = lazy(() =>
  import('./pages/ResourceMapPage').then(module => ({ default: module.ResourceMapPage })),
);
const CodegenPage = lazy(() => import('./pages/CodegenPage').then(module => ({ default: module.CodegenPage })));
const DiagnosisPage = lazy(() => import('./pages/DiagnosisPage').then(module => ({ default: module.DiagnosisPage })));
const KnowledgeBasePage = lazy(() =>
  import('./pages/KnowledgeBasePage').then(module => ({ default: module.KnowledgeBasePage })),
);
const SettingsPage = lazy(() => import('./pages/SettingsPage').then(module => ({ default: module.SettingsPage })));

const THEME_STORAGE_KEY = 'ate_theme_mode';

function resolveInitialTheme(): ThemeMode {
  if (typeof window === 'undefined') return 'dark';
  const stored = window.localStorage.getItem(THEME_STORAGE_KEY);
  return stored === 'light' ? 'light' : 'dark';
}

export default function App() {
  const [currentView, setCurrentView] = useState<View>('agent-workspace');
  const [themeMode, setThemeMode] = useState<ThemeMode>(resolveInitialTheme);

  useEffect(() => {
    document.documentElement.dataset.theme = themeMode;
    window.localStorage.setItem(THEME_STORAGE_KEY, themeMode);
  }, [themeMode]);

  let page;
  switch (currentView) {
    case 'agent-workspace':
      page = <AgentWorkspacePage />;
      break;
    case 'agent-runs':
      page = <AgentRunsPage />;
      break;
    case 'testplan':
      page = <TestPlanPage />;
      break;
    case 'resource-map':
      page = <ResourceMapPage />;
      break;
    case 'codegen':
      page = <CodegenPage />;
      break;
    case 'diagnosis':
      page = <DiagnosisPage />;
      break;
    case 'knowledge-base':
      page = <KnowledgeBasePage />;
      break;
    case 'settings':
      page = <SettingsPage themeMode={themeMode} onThemeChange={setThemeMode} />;
      break;
    default:
      page = <AgentWorkspacePage />;
      break;
  }

  return (
    <AppLayout
      currentView={currentView}
      onViewChange={setCurrentView}
      title={viewMeta[currentView].title}
      description={viewMeta[currentView].description}
    >
      <Suspense
        fallback={
          <Card title="页面加载中" subtitle="正在按需加载当前模块资源，请稍候。">
            <div className="flex items-center gap-3 py-2 text-sm text-on-surface-variant/80">
              <span className="inline-flex h-2.5 w-2.5 animate-pulse rounded-full bg-primary" />
              正在准备 {viewMeta[currentView].title}
            </div>
          </Card>
        }
      >
        {page}
      </Suspense>
    </AppLayout>
  );
}
