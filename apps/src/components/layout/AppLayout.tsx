import type { ReactNode } from 'react';
import { Sidebar } from './Sidebar';
import { Topbar } from './Topbar';
import { View } from '../../types';

export function AppLayout({
  currentView,
  onViewChange,
  title,
  description,
  children,
}: {
  currentView: View;
  onViewChange: (view: View) => void;
  title: string;
  description: string;
  children: ReactNode;
}) {
  return (
    <div className="flex min-h-screen bg-surface text-on-surface">
      <div className="hidden lg:block">
        <Sidebar currentView={currentView} onViewChange={onViewChange} />
      </div>
      <div className="flex min-w-0 flex-1 flex-col">
        <Topbar title={title} description={description} />
        <main className="min-w-0 flex-1 overflow-y-auto px-4 py-4 md:px-6 md:py-6">{children}</main>
      </div>
    </div>
  );
}
