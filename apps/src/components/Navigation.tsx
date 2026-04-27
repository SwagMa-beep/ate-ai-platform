import React from 'react';
import { BrainCircuit, LayoutDashboard, Microscope, Network, Radio, Terminal, Workflow } from 'lucide-react';
import { motion } from 'motion/react';
import { View } from '../types';

interface NavProps {
  currentView: View;
  onViewChange: (view: View) => void;
}

const navItems: Array<{ id: View; label: string; icon: React.ComponentType<{ className?: string }> }> = [
  { id: 'dashboard', label: '仪表盘', icon: LayoutDashboard },
  { id: 'extractor', label: '提取器', icon: BrainCircuit },
  { id: 'resources', label: '资源映射', icon: Network },
  { id: 'codelab', label: '代码实验室', icon: Terminal },
  { id: 'agentruns', label: '运行中心', icon: Workflow },
  { id: 'failure', label: '故障诊断', icon: Microscope },
];

export function TopNav({ currentView, onViewChange }: NavProps) {
  return (
    <header className="fixed top-0 z-50 flex w-full items-center justify-between border-b border-outline-variant/10 bg-surface/80 px-6 py-4 backdrop-blur-md">
      <button type="button" onClick={() => onViewChange('dashboard')} className="flex items-center gap-3 opacity-90 transition-all hover:scale-[1.01]">
        <div className="rounded-lg bg-primary/10 p-1.5">
          <motion.div animate={{ rotate: 360 }} transition={{ duration: 10, repeat: Infinity, ease: 'linear' }}>
            <Radio className="h-6 w-6 text-primary" />
          </motion.div>
        </div>
        <span className="font-headline text-xl font-bold uppercase tracking-widest text-primary">ATE AI Platform</span>
      </button>

      <nav className="hidden items-center gap-2 md:flex">
        {navItems.map(item => (
          <button
            key={item.id}
            type="button"
            onClick={() => onViewChange(item.id)}
            className={`flex items-center gap-2 rounded-xl px-4 py-2 transition-all duration-300 ${
              currentView === item.id ? 'bg-primary/10 text-primary' : 'text-on-surface-variant hover:bg-primary/5 hover:text-primary'
            }`}
          >
            <item.icon className="h-4 w-4" />
            <span className="font-sans text-xs font-medium tracking-wider">{item.label}</span>
          </button>
        ))}
      </nav>

      <div className="flex items-center justify-center rounded-full p-2 text-primary">
        <Radio className="pulse-dot h-5 w-5" />
      </div>
    </header>
  );
}

export function BottomNav({ currentView, onViewChange }: NavProps) {
  return (
    <nav className="fixed bottom-0 z-50 flex w-full items-center justify-around border-t border-outline-variant/10 bg-surface-container-low/90 px-4 pb-8 pt-4 shadow-lg backdrop-blur-xl md:hidden">
      {navItems.map(item => (
        <button
          key={item.id}
          type="button"
          onClick={() => onViewChange(item.id)}
          className={`flex flex-col items-center gap-1.5 rounded-xl px-3 py-1.5 transition-all ${
            currentView === item.id ? 'bg-primary/10 text-primary' : 'text-on-surface-variant'
          }`}
        >
          <item.icon className="h-5 w-5" />
          <span className="whitespace-nowrap text-[10px] font-medium tracking-tight">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
