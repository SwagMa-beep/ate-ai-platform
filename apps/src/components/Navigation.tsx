import React from 'react';
import { LayoutDashboard, BrainCircuit, Network, Terminal, Microscope, Radio } from 'lucide-react';
import { motion } from 'motion/react';
import { View } from '../types';

interface NavProps {
  currentView: View;
  onViewChange: (view: View) => void;
}

export function TopNav({ currentView, onViewChange }: NavProps) {
  const navItems: { id: View; label: string; icon: any }[] = [
    { id: 'dashboard', label: '仪表盘', icon: LayoutDashboard },
    { id: 'extractor', label: '提取器', icon: BrainCircuit },
    { id: 'resources', label: '资源', icon: Network },
    { id: 'codelab', label: '代码实验室', icon: Terminal },
    { id: 'failure', label: '故障', icon: Microscope },
  ];

  return (
    <header className="fixed top-0 z-50 w-full bg-surface border-b border-outline-variant/10 px-6 py-4 flex justify-between items-center backdrop-blur-md bg-surface/80">
      <div className="flex items-center gap-3 opacity-90 transition-all hover:scale-105 cursor-pointer">
        <div className="p-1.5 bg-primary/10 rounded-lg">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 10, repeat: Infinity, ease: "linear" }}
          >
            <Radio className="w-6 h-6 text-primary" />
          </motion.div>
        </div>
        <span className="text-xl font-headline font-bold tracking-widest text-primary uppercase">ATE Agent Pro</span>
      </div>

      <nav className="hidden md:flex items-center gap-2">
        {navItems.map((item) => (
          <button
            key={item.id}
            onClick={() => onViewChange(item.id)}
            className={`flex items-center gap-2 px-4 py-2 rounded-xl transition-all duration-300 ${
              currentView === item.id 
                ? 'bg-primary/10 text-primary' 
                : 'text-on-surface-variant hover:text-primary hover:bg-primary/5'
            }`}
          >
            <item.icon className="w-4 h-4" />
            <span className="font-sans text-xs font-medium tracking-wider uppercase">{item.label}</span>
          </button>
        ))}
      </nav>

      <button className="text-primary hover:text-primary/70 transition-colors flex items-center justify-center p-2 rounded-full hover:bg-surface-bright">
        <Radio className="w-5 h-5 pulse-dot" />
      </button>
    </header>
  );
}

export function BottomNav({ currentView, onViewChange }: NavProps) {
  const navItems: { id: View; label: string; icon: any }[] = [
    { id: 'dashboard', label: '仪表盘', icon: LayoutDashboard },
    { id: 'extractor', label: '提取器', icon: BrainCircuit },
    { id: 'resources', label: '资源', icon: Network },
    { id: 'codelab', label: '代码实验室', icon: Terminal },
    { id: 'failure', label: '故障', icon: Microscope },
  ];

  return (
    <nav className="md:hidden fixed bottom-0 w-full z-50 flex justify-around items-center px-4 pb-8 pt-4 bg-surface-container-low/90 backdrop-blur-xl border-t border-outline-variant/10 shadow-lg">
      {navItems.map((item) => (
        <button
          key={item.id}
          onClick={() => onViewChange(item.id)}
          className={`flex flex-col items-center gap-1.5 px-3 py-1.5 rounded-xl transition-all ${
            currentView === item.id 
              ? 'text-primary bg-primary/10' 
              : 'text-on-surface-variant'
          }`}
        >
          <item.icon className="w-5 h-5" />
          <span className="text-[10px] font-medium tracking-tight whitespace-nowrap">{item.label}</span>
        </button>
      ))}
    </nav>
  );
}
