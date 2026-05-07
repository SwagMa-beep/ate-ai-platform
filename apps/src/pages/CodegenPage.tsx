import { ShieldAlert } from 'lucide-react';
import { CodeLab } from '../components/CodeLab';

export function CodegenPage() {
  return (
    <div className="space-y-4">
      <div className="rounded-2xl border border-tertiary/20 bg-tertiary/10 px-4 py-3 text-sm text-tertiary">
        <div className="flex items-start gap-2">
          <ShieldAlert className="mt-0.5 h-4 w-4 shrink-0" />
          <span>生成结果仅用于辅助 ATE 测试开发，需由 ATE 工程师复核后再上机使用。</span>
        </div>
      </div>
      <CodeLab />
    </div>
  );
}
