/**
 * @license
 * SPDX-License-Identifier: Apache-2.0
 */

import React, { useState } from 'react';
import { motion, AnimatePresence } from 'motion/react';
import { AlertTriangle, RefreshCw } from 'lucide-react';
import { View } from './types.ts';
import { TopNav, BottomNav } from './components/Navigation.tsx';
import { Dashboard } from './components/Dashboard.tsx';
import { Extractor } from './components/Extractor.tsx';
import { Resources } from './components/Resources.tsx';
import { CodeLab } from './components/CodeLab.tsx';
import { FailureAnalysis } from './components/FailureAnalysis.tsx';

// ─── Error Boundary：捕获子组件渲染崩溃，防止整页黑屏 ─────────
interface EBState { hasError: boolean; message: string }
class ErrorBoundary extends React.Component<
  { children: React.ReactNode; onReset: () => void },
  EBState
> {
  state: EBState = { hasError: false, message: '' };

  static getDerivedStateFromError(error: Error): EBState {
    return { hasError: true, message: error.message || '未知渲染错误' };
  }

  handleReset = () => {
    this.setState({ hasError: false, message: '' });
    this.props.onReset();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div className="flex flex-col items-center justify-center gap-6 py-32 px-8">
          <div className="p-4 bg-error/10 rounded-2xl">
            <AlertTriangle className="w-12 h-12 text-error" />
          </div>
          <div className="text-center">
            <h2 className="font-headline text-2xl font-bold text-on-surface mb-2">页面组件出错</h2>
            <p className="text-sm text-on-surface-variant font-mono bg-surface-container px-4 py-2 rounded-lg max-w-lg break-all">
              {this.state.message}
            </p>
          </div>
          <button
            onClick={this.handleReset}
            className="flex items-center gap-2 bg-primary text-on-primary font-bold text-sm px-8 py-4 rounded-xl hover:brightness-110 transition-all"
          >
            <RefreshCw className="w-4 h-4" /> 返回主页
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
      case 'failure':
        return <FailureAnalysis />;
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="min-h-screen flex flex-col pt-20 pb-28 md:pb-8">
      <TopNav currentView={currentView} onViewChange={setCurrentView} />
      
      <main className="flex-1 w-full max-w-[1800px] mx-auto p-4 md:p-8">
        <AnimatePresence mode="wait">
          <motion.div
            key={currentView}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.3 }}
            className="w-full"
          >
            <ErrorBoundary onReset={() => setCurrentView('dashboard')}>
              {renderView()}
            </ErrorBoundary>
          </motion.div>
        </AnimatePresence>
      </main>

      <BottomNav currentView={currentView} onViewChange={setCurrentView} />
    </div>
  );
}
