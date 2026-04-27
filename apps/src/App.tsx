/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { AnimatePresence, motion } from 'motion/react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { View } from './types.ts';
import { TopNav, BottomNav } from './components/Navigation.tsx';
import { Dashboard } from './components/Dashboard.tsx';
import { Extractor } from './components/Extractor.tsx';
import { Resources } from './components/Resources.tsx';
import { CodeLab } from './components/CodeLab.tsx';
import { AgentRuns } from './components/AgentRuns.tsx';
import { FailureAnalysis } from './components/FailureAnalysis.tsx';

interface ErrorBoundaryState {
  hasError: boolean;
  message: string;
}

class ErrorBoundary extends React.Component<{ children: React.ReactNode; onReset: () => void }, ErrorBoundaryState> {
  state: ErrorBoundaryState = { hasError: false, message: '' };

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return {
      hasError: true,
      message: error.message || '未知页面错误',
    };
  }

  handleReset = () => {
    this.setState({ hasError: false, message: '' });
    this.props.onReset();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center gap-6 px-8 py-32">
          <div className="rounded-2xl bg-error/10 p-4">
            <AlertTriangle className="h-12 w-12 text-error" />
          </div>

          <div className="text-center">
            <h2 className="mb-2 font-headline text-2xl font-bold text-on-surface">页面组件异常</h2>
            <p className="max-w-lg break-all rounded-lg bg-surface-container px-4 py-2 font-mono text-sm text-on-surface-variant">
              {this.state.message}
            </p>
          </div>

          <button
            type="button"
            onClick={this.handleReset}
            className="flex items-center gap-2 rounded-xl bg-primary px-8 py-4 text-sm font-bold text-on-primary transition-all hover:brightness-110"
          >
            <RefreshCw className="h-4 w-4" />
            返回首页
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default function App() {
  const [currentView, setCurrentView] = useState<View>('dashboard');

  const renderView = () => {
    switch (currentView) {
      case 'dashboard':
        return <Dashboard onViewChange={setCurrentView} />;
      case 'extractor':
        return <Extractor />;
      case 'resources':
        return <Resources />;
      case 'codelab':
        return <CodeLab />;
      case 'agentruns':
        return <AgentRuns />;
      case 'failure':
        return <FailureAnalysis />;
      default:
        return <Dashboard onViewChange={setCurrentView} />;
    }
  };

  return (
    <div className="flex min-h-screen flex-col pb-28 pt-20 md:pb-8">
      <TopNav currentView={currentView} onViewChange={setCurrentView} />

      <main className="mx-auto w-full max-w-[1800px] flex-1 p-4 md:p-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentView}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
            className="w-full"
          >
            <ErrorBoundary onReset={() => setCurrentView('dashboard')}>{renderView()}</ErrorBoundary>
          </motion.div>
        </AnimatePresence>
      </main>

      <BottomNav currentView={currentView} onViewChange={setCurrentView} />
    </div>
  );
}
