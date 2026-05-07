import { Database, ShieldAlert } from 'lucide-react';
import { Card } from '../components/common/Card';

export function KnowledgeBasePage() {
  return (
    <Card title="知识库管理">
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="flex items-center gap-2 text-primary">
            <Database className="h-4 w-4" />
            企业样例知识
          </div>
          <p className="mt-2 text-sm text-on-surface-variant/80">代码生成 / 测试项推荐 / 平台 API</p>
        </div>
        <div className="rounded-2xl border border-tertiary/20 bg-tertiary/10 p-4 text-sm text-tertiary">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4" />
            已接入
          </div>
        </div>
      </div>
    </Card>
  );
}
