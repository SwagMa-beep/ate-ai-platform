import { Database, ShieldAlert } from 'lucide-react';
import { Card } from '../components/common/Card';

export function KnowledgeBasePage() {
  return (
    <Card
      title="知识库管理"
      subtitle="第一版先作为知识资产与接入状态总览，后续再补更细的上传、索引和检索配置。"
    >
      <div className="grid gap-4 md:grid-cols-2">
        <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
          <div className="flex items-center gap-2 text-primary">
            <Database className="h-4 w-4" />
            企业样例知识
          </div>
          <p className="mt-2 text-sm text-on-surface-variant/80">用于代码生成、测试项推荐和平台 API 用法增强。</p>
        </div>
        <div className="rounded-2xl border border-tertiary/20 bg-tertiary/10 p-4 text-sm text-tertiary">
          <div className="flex items-center gap-2">
            <ShieldAlert className="h-4 w-4" />
            说明
          </div>
          <p className="mt-2">该页当前以管理视角为主，后续可以继续接入真实知识库维护能力。</p>
        </div>
      </div>
    </Card>
  );
}
