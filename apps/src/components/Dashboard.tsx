import React, { useEffect, useState } from 'react';
import { TrendingUp, AlertTriangle, Lightbulb, Cpu, FileDigit, Upload, Bug, History, BrainCircuit, Wifi, WifiOff } from 'lucide-react';
import { motion } from 'motion/react';
import { checkHealth } from '../api/backend';
import { extractionStore, type ExtractionState } from '../store/extractionStore';
import type { View } from '../types';

interface DashboardProps {
  onViewChange?: (view: View) => void;
}

export function Dashboard({ onViewChange }: DashboardProps) {
  const [backendStatus, setBackendStatus] = useState<'checking' | 'online' | 'offline'>('checking');
  const [backendVersion, setBackendVersion] = useState('');
  const [extractState, setExtractState] = useState<ExtractionState>(extractionStore.getState());

  useEffect(() => {
    checkHealth()
      .then(res => {
        if (res.status === 'success' && res.data) {
          setBackendStatus('online');
          setBackendVersion(res.data.version);
        } else {
          setBackendStatus('offline');
        }
      })
      .catch(() => setBackendStatus('offline'));
    
    // 订阅提取进度
    const unsubscribe = extractionStore.subscribe(setExtractState);
    return unsubscribe;
  }, []);

  const insights = [
    {
      id: 'extraction-info',
      type: extractState.stage === 'error' ? 'critical' : 'info',
      icon: extractState.stage === 'error' ? AlertTriangle : (extractState.stage === 'done' ? Cpu : BrainCircuit),
      color: extractState.stage === 'error' ? 'text-tertiary' : 'text-primary',
      borderColor: extractState.stage === 'error' ? 'border-tertiary' : 'border-primary',
      title: extractState.stage === 'idle' ? '等待新任务' : (extractState.stage === 'done' ? `提取完成: ${extractState.result?.chip_name}` : `正在处理: ${extractState.fileInfo?.filename || 'PDF文件'}`),
      description: extractState.message || '系统准备就绪，可随时开始芯片参数提取。',
      time: '实时'
    },
    {
      id: '1',
      type: 'critical',
      icon: AlertTriangle,
      color: 'text-tertiary',
      borderColor: 'border-tertiary',
      title: '检测到 Lot XA-992 良率下降',
      description: 'Bin 4 故障增加 12%。可能原因：在模式 T_045 期间发生 VDD 电压降。',
      time: '刚刚'
    },
    {
      id: '3',
      type: 'info',
      icon: Cpu,
      color: 'text-secondary',
      borderColor: 'border-secondary',
      title: '测试机 04 处理机卡住',
      description: '已成功启动自动恢复序列。',
      time: '1 小时前'
    }
  ];

  const showActiveContext = extractState.stage !== 'idle';
  const displayProgress = extractState.progress;
  const displayFile = extractState.fileInfo?.filename || '正在提取...';

  return (
    <div className="flex flex-col gap-6 animate-in fade-in duration-500">
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Global Health Card */}
        <section className="lg:col-span-8 bg-surface-container-low rounded-2xl p-8 relative overflow-hidden flex flex-col justify-between min-h-[400px] border border-outline-variant/5">
          <div className="absolute top-0 left-0 w-[600px] h-[600px] bg-primary/10 rounded-full blur-[120px] -ml-40 -mt-40 pointer-events-none" />
          
          <div className="flex flex-col md:flex-row justify-between items-start gap-8 relative z-10">
            <div className="flex flex-col gap-3">
              <div className="flex items-center gap-2">
                <span className="relative flex h-2.5 w-2.5">
                  <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75"></span>
                  <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-primary"></span>
                </span>
                <h2 className="text-on-surface-variant font-sans text-xs uppercase tracking-widest font-semibold">全球机队良率</h2>
              </div>
              
              <div className="flex items-baseline gap-3 mt-2">
                <motion.span 
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  className="font-headline text-8xl md:text-9xl font-bold text-primary tracking-tighter"
                >
                  98.4
                </motion.span>
                <span className="font-mono text-2xl text-primary/60">%</span>
              </div>
              
              <p className="text-on-surface-variant text-sm mt-3 font-mono flex items-center gap-2 bg-surface-container/50 px-3 py-1.5 rounded-full w-fit">
                <TrendingUp className="w-4 h-4 text-tertiary" />
                <span className="text-tertiary">+0.2%</span> 较上一批次
              </p>
            </div>

            <div className="glass-panel rounded-xl p-6 min-w-[240px] border-l-4 border-l-primary">
              <p className="font-sans text-[10px] text-on-surface-variant uppercase tracking-widest mb-5 font-bold">活跃操作</p>
              <div className="flex flex-col gap-4">
                {[
                  { label: '在线节点', value: '4,092' },
                  { label: '数据吞吐量', value: '1.2 TB/s' },
                  { label: 'AI 推理延迟', value: '12ms' },
                ].map((item, i) => (
                  <div key={i} className="flex justify-between items-center font-mono text-sm group">
                    <span className="text-on-surface-variant group-hover:text-on-surface transition-colors">{item.label}</span>
                    <span className="text-primary font-bold">{item.value}</span>
                  </div>
                ))}
                {/* 后端连接状态 */}
                <div className="flex justify-between items-center font-mono text-sm group mt-2 pt-3 border-t border-outline-variant/10">
                  <span className="text-on-surface-variant flex items-center gap-1.5">
                    {backendStatus === 'online'
                      ? <Wifi className="w-3.5 h-3.5 text-primary" />
                      : backendStatus === 'offline'
                      ? <WifiOff className="w-3.5 h-3.5 text-error" />
                      : <span className="w-3.5 h-3.5 rounded-full bg-on-surface-variant animate-pulse inline-block" />
                    }
                    后端 API
                  </span>
                  <span className={`font-bold text-xs ${
                    backendStatus === 'online' ? 'text-primary' :
                    backendStatus === 'offline' ? 'text-error' : 'text-on-surface-variant'
                  }`}>
                    {backendStatus === 'online' ? `v${backendVersion}` :
                     backendStatus === 'offline' ? '未连接' : '检测中...'}
                  </span>
                </div>
              </div>
            </div>
          </div>

          <div className="relative h-28 w-full mt-12 flex items-end gap-1.5 opacity-40 z-10 overflow-hidden">
            {[30, 60, 40, 80, 95, 70, 45, 20, 50, 85, 60, 35, 15, 45, 30].map((h, i) => (
              <motion.div 
                key={i}
                initial={{ height: 0 }}
                animate={{ height: `${h}%` }}
                transition={{ delay: i * 0.05, duration: 0.8 }}
                className={`w-full rounded-t-sm ${h > 80 ? 'bg-tertiary' : 'bg-primary/50'}`} 
              />
            ))}
          </div>
        </section>

        {/* AI Insight Feed */}
        <section className="lg:col-span-4 bg-surface-container rounded-2xl p-6 flex flex-col gap-6 border border-outline-variant/10">
          <div className="flex justify-between items-center">
            <h3 className="font-headline text-lg font-bold text-on-surface flex items-center gap-2">
              <BrainCircuit className="w-5 h-5 text-secondary" />
              AI 洞察源
            </h3>
            <button className="text-primary text-xs font-bold hover:underline">清除</button>
          </div>
          
          <div className="flex flex-col gap-4 overflow-y-auto pr-1 custom-scrollbar max-h-[400px]">
            {insights.map((insight) => (
              <motion.div 
                key={insight.id}
                whileHover={{ x: 4 }}
                className={`bg-surface-container-highest p-4 rounded-xl border-l-2 ${insight.borderColor} cursor-pointer`}
              >
                <div className="flex items-start gap-4">
                  <insight.icon className={`w-5 h-5 ${insight.color} shrink-0 mt-0.5`} />
                  <div>
                    <p className="text-sm text-on-surface font-sans leading-relaxed tracking-tight">
                      {insight.title}
                    </p>
                    <p className="text-xs text-on-surface-variant mt-2 leading-relaxed italic">
                      {insight.description}
                    </p>
                    <span className="text-[10px] text-on-surface-variant/60 font-mono mt-3 block uppercase">
                      {insight.time}
                    </span>
                  </div>
                </div>
              </motion.div>
            ))}
          </div>
        </section>

        {/* Bottom Bento Row */}
        <div className="lg:col-span-12 grid grid-cols-1 lg:grid-cols-3 gap-6 mt-2">
          {/* Analysis Progress */}
          <section className="lg:col-span-2 bg-surface-container-low rounded-2xl p-7 flex flex-col gap-6 border border-outline-variant/10">
            <h3 className="font-headline text-lg font-bold text-on-surface flex items-center gap-2">
              <FileDigit className="w-5 h-5 text-primary" />
              活动上下文：数据手册提取
            </h3>
            
            <div className="flex flex-col gap-5">
              <div className="flex justify-between items-end">
                <div className="flex flex-col gap-1.5 max-w-[70%]">
                  <span className="text-[10px] font-sans text-on-surface-variant uppercase tracking-[0.2em] font-bold">
                    {showActiveContext ? '当前分析文件' : '等待任务'}
                  </span>
                  <span className={`font-mono text-sm px-3 py-1 rounded-lg border truncate ${
                    showActiveContext 
                      ? 'text-primary bg-primary/10 border-primary/20' 
                      : 'text-on-surface-variant/40 bg-surface-container border-outline-variant/10'
                  }`}>
                    {showActiveContext ? displayFile : '无活跃任务'}
                  </span>
                </div>
                <div className="flex flex-col items-end">
                  <span className="font-headline text-4xl text-on-surface font-bold tracking-tighter">
                    {displayProgress}%
                  </span>
                </div>
              </div>

              <div className="h-2.5 w-full bg-surface-container-highest rounded-full overflow-hidden">
                <motion.div 
                  initial={{ width: 0 }}
                  animate={{ width: `${displayProgress}%` }}
                  transition={{ duration: 1.0, ease: "easeOut" }}
                  className={`h-full bg-gradient-to-r ${
                    extractState.stage === 'error' 
                      ? 'from-error to-error/50' 
                      : 'from-secondary to-primary'
                  }`} 
                />
              </div>

              <div className="grid grid-cols-3 gap-8 mt-2">
                {[
                  { 
                    label: '状态', 
                    value: extractState.stage === 'done' ? '完成' : (extractState.stage === 'error' ? '错误' : (extractState.stage === 'idle' ? '待机' : '执行中')), 
                    color: extractState.stage === 'error' ? 'text-error' : (extractState.stage === 'done' ? 'text-primary' : 'text-on-surface') 
                  },
                  { 
                    label: '提取参数', 
                    value: extractState.result?.statistics.total || '0', 
                    color: 'text-on-surface' 
                  },
                  { 
                    label: '当前步骤', 
                    value: extractState.message.slice(0, 10) || '准备中', 
                    color: 'text-tertiary' 
                  }
                ].map((stat, i) => (
                  <div key={i} className="flex flex-col gap-1">
                    <span className="text-[10px] font-sans text-on-surface-variant uppercase tracking-widest font-bold">{stat.label}</span>
                    <span className={`font-mono text-sm font-semibold truncate ${stat.color}`}>{stat.value}</span>
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Quick Actions */}
          <section className="lg:col-span-1 grid grid-cols-2 gap-4">
            <motion.button 
              whileTap={{ scale: 0.95 }}
              onClick={() => onViewChange?.('extractor')}
              className="bg-primary text-on-primary rounded-2xl p-6 flex flex-col items-center justify-center gap-4 hover:brightness-110 shadow-lg shadow-primary/10 transition-all border border-primary/20"
            >
              <Upload className="w-8 h-8 font-bold" />
              <span className="font-sans text-xs font-bold uppercase tracking-widest">新建提取</span>
            </motion.button>
            <motion.button 
              whileTap={{ scale: 0.95 }}
              onClick={() => onViewChange?.('resources')}
              className="bg-surface-container border border-outline-variant/30 text-primary rounded-2xl p-6 flex flex-col items-center justify-center gap-4 hover:bg-surface-bright transition-all"
            >
              <Bug className="w-8 h-8" />
              <span className="font-sans text-xs font-bold uppercase tracking-widest">资源映射</span>
            </motion.button>
            <motion.button 
              whileTap={{ scale: 0.98 }}
              className="bg-surface-container border border-outline-variant/20 text-on-surface-variant rounded-2xl p-5 flex flex-col items-center justify-center gap-3 hover:bg-surface-bright transition-all col-span-2 group"
            >
              <History className="w-6 h-6 group-hover:rotate-[-45deg] transition-transform" />
              <span className="font-sans text-[10px] font-bold uppercase tracking-[0.3em]">查看历史操作日志</span>
            </motion.button>
          </section>
        </div>
      </div>
    </div>
  );
}
