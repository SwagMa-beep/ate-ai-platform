import { Download, FileCode2, FileSpreadsheet, FileText, ImageIcon, PackageCheck, ShieldCheck } from 'lucide-react';
import { type AgentRunArtifact, type AgentRunResult, resolveBackendUrl } from '../../api/backend';
import { getArtifactLabel, getStepLabel } from '../../utils/runPresentation';
import { EmptyState } from '../common/EmptyState';

function pickIcon(type?: string) {
  if (type?.includes('code')) return FileCode2;
  if (type?.includes('excel') || type?.includes('resource') || type?.includes('testplan')) return FileSpreadsheet;
  if (type?.includes('image')) return ImageIcon;
  return FileText;
}

function triggerTextDownload(content: string, filename: string) {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 500);
}

function formatSummary(summary?: Record<string, unknown>) {
  if (!summary) return '暂无摘要信息';
  const text = Object.entries(summary)
    .slice(0, 3)
    .map(([key, value]) => `${key}: ${String(value)}`)
    .join(' | ');
  return text || '暂无摘要信息';
}

function getDeliveryContext(run: AgentRunResult | null) {
  const shared = (run?.shared as Record<string, unknown> | undefined) || {};
  const generatedResult = (shared.generated_result as Record<string, unknown> | undefined) || {};
  const packageExport = (generatedResult.package_export as Record<string, unknown> | undefined) || {};
  const deliverySummary = (shared.delivery_summary as Record<string, unknown> | undefined) || {};
  const benchChecklist = (shared.bench_checklist as Record<string, unknown> | undefined) || {};
  const deliveryPackage = (shared.delivery_package as Record<string, unknown> | undefined) || {};
  return {
    generatedCode: typeof generatedResult.code === 'string' ? generatedResult.code : '',
    generatedFilename: typeof generatedResult.filename === 'string' ? generatedResult.filename : 'generated_test.cpp',
    packageDownloadUrl: typeof packageExport.download_url === 'string' ? packageExport.download_url : '',
    packageFileCount: Array.isArray(packageExport.generated_files) ? packageExport.generated_files.length : 0,
    packageOutputDir: typeof packageExport.output_dir === 'string' ? packageExport.output_dir : '',
    packageInputs: (packageExport.inputs as Record<string, unknown> | undefined) || {},
    deliverySummary,
    benchChecklist,
    deliveryPackage,
  };
}

export function AgentArtifactsPanel({
  artifacts,
  run,
}: {
  artifacts: AgentRunArtifact[];
  run?: AgentRunResult | null;
}) {
  const {
    generatedCode,
    generatedFilename,
    packageDownloadUrl,
    packageFileCount,
    packageOutputDir,
    packageInputs,
    deliverySummary,
    benchChecklist,
    deliveryPackage,
  } = getDeliveryContext(run || null);

  const checklistItems = Array.isArray(benchChecklist.items) ? benchChecklist.items : [];
  const readyForBench = Boolean(deliveryPackage.ready_for_bench ?? benchChecklist.ready_for_bench);
  const finalPackageUrl =
    typeof deliveryPackage.download_url === 'string' && deliveryPackage.download_url
      ? deliveryPackage.download_url
      : packageDownloadUrl;
  const hasDeliverySection =
    Boolean(generatedCode) ||
    Boolean(finalPackageUrl) ||
    Object.keys(deliverySummary).length > 0 ||
    checklistItems.length > 0;

  if (!artifacts.length && !hasDeliverySection) {
    return <EmptyState title="暂无可交付产物" description="当前运行还没有可以直接下载或复核的文件，稍后可以回到这里继续查看。" />;
  }

  return (
    <div className="space-y-4">
      {hasDeliverySection ? (
        <section className="rounded-2xl border border-primary/15 bg-primary/5 p-4">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <div className="text-sm font-semibold text-on-surface">可交付文件</div>
              <p className="mt-1 text-xs leading-relaxed text-on-surface-variant/75">
                这里集中展示当前 run 已经能直接给工程师或客户使用的内容，不用再自己去时间线里翻。
              </p>
            </div>
            <div className={`rounded-full px-3 py-1 text-xs font-semibold ${readyForBench ? 'bg-primary/10 text-primary' : 'bg-tertiary/10 text-tertiary'}`}>
              {readyForBench ? '可进入上机准备' : '仍需人工确认'}
            </div>
          </div>

          <div className="grid gap-3 lg:grid-cols-2">
            {generatedCode ? (
              <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-xl bg-primary/10 p-2 text-primary">
                    <FileCode2 className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-on-surface">生成测试代码</div>
                    <div className="mt-1 text-xs text-on-surface-variant/70">{generatedFilename}</div>
                    <div className="mt-2 text-xs leading-relaxed text-on-surface-variant/75">
                      批准并不会重新生成代码，真正可用的代码通常在批准前已经生成好了，这里可以直接导出。
                    </div>
                    <button
                      type="button"
                      onClick={() => triggerTextDownload(generatedCode, generatedFilename)}
                      className="mt-3 inline-flex items-center gap-2 rounded-xl bg-primary px-3 py-2 text-xs font-semibold text-on-primary transition hover:brightness-110"
                    >
                      <Download className="h-3.5 w-3.5" />
                      下载代码
                    </button>
                  </div>
                </div>
              </div>
            ) : null}

            {finalPackageUrl ? (
              <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-xl bg-secondary/10 p-2 text-secondary">
                    <PackageCheck className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-on-surface">工程交付包</div>
                    <div className="mt-1 text-xs text-on-surface-variant/70">
                      {packageFileCount ? `已整理 ${packageFileCount} 个文件` : '已生成可下载交付包'}
                    </div>
                    {packageOutputDir ? <div className="mt-1 break-all text-[11px] text-on-surface-variant/60">{packageOutputDir}</div> : null}
                    <div className="mt-2 text-xs leading-relaxed text-on-surface-variant/75">
                      这个包里通常包含 `test.cpp`、DLL 入口文件、manifest、codegen plan、模板工程骨架以及 PGS / 向量相关起始文件。
                    </div>
                    <a
                      href={resolveBackendUrl(finalPackageUrl)}
                      className="mt-3 inline-flex items-center gap-2 rounded-xl bg-secondary px-3 py-2 text-xs font-semibold text-on-primary transition hover:brightness-110"
                    >
                      <Download className="h-3.5 w-3.5" />
                      下载工程包
                    </a>
                  </div>
                </div>
              </div>
            ) : null}

            {Object.keys(deliverySummary).length > 0 ? (
              <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-xl bg-primary/10 p-2 text-primary">
                    <ShieldCheck className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="text-sm font-semibold text-on-surface">批准后交付摘要</div>
                    <div className="mt-2 grid gap-2 text-xs text-on-surface-variant/75">
                      <div>芯片：{String(deliverySummary.chip_name || '-')}</div>
                      <div>类型：{String(deliverySummary.chip_type || '-')}</div>
                      <div>风险等级：{String(deliverySummary.risk_level || '-')}</div>
                      <div>包是否就绪：{deliverySummary.package_ready ? '是' : '否'}</div>
                      <div>是否可进入上机准备：{deliverySummary.ready_for_bench ? '是' : '否'}</div>
                    </div>
                  </div>
                </div>
              </div>
            ) : null}

            {checklistItems.length > 0 ? (
              <div className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
                <div className="text-sm font-semibold text-on-surface">上机前检查表</div>
                <div className="mt-3 space-y-2">
                  {checklistItems.slice(0, 5).map((item, index) => {
                    const row = (item as Record<string, unknown>) || {};
                    return (
                      <div key={`${String(row.id || 'item')}-${index}`} className="rounded-xl border border-outline-variant/10 bg-surface px-3 py-2 text-xs">
                        <div className="flex items-center justify-between gap-3">
                          <span className="font-medium text-on-surface">{String(row.label || '检查项')}</span>
                          <span className={row.done ? 'text-primary' : 'text-tertiary'}>{row.done ? '已确认' : '待确认'}</span>
                        </div>
                        {row.detail ? <div className="mt-1 text-on-surface-variant/70">{String(row.detail)}</div> : null}
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>

          {(packageInputs.resource_map_excel || packageInputs.bom_excel || packageInputs.schematic_svg) ? (
            <div className="mt-4 rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
              <div className="text-sm font-semibold text-on-surface">已关联的测试输入文件</div>
              <div className="mt-3 grid gap-2 text-xs text-on-surface-variant/75">
                {packageInputs.resource_map_excel ? <div>资源映射表：{String(packageInputs.resource_map_excel)}</div> : null}
                {packageInputs.bom_excel ? <div>BOM：{String(packageInputs.bom_excel)}</div> : null}
                {packageInputs.schematic_svg ? <div>原理图：{String(packageInputs.schematic_svg)}</div> : null}
              </div>
            </div>
          ) : null}
        </section>
      ) : null}

      {artifacts.length ? (
        <div className="grid gap-3 md:grid-cols-2">
          {artifacts.map((artifact, index) => {
            const Icon = pickIcon(artifact.type);
            return (
              <div key={`${artifact.name ?? artifact.type ?? 'artifact'}-${index}`} className="rounded-2xl border border-outline-variant/12 bg-surface-container p-4">
                <div className="flex items-start gap-3">
                  <div className="rounded-xl bg-primary/10 p-2 text-primary">
                    <Icon className="h-4 w-4" />
                  </div>
                  <div className="min-w-0 flex-1">
                    <div className="truncate text-sm font-semibold text-on-surface">{artifact.name || getArtifactLabel(artifact.type)}</div>
                    <div className="mt-1 text-xs text-on-surface-variant/70">
                      来源：{artifact.producer ? getStepLabel(artifact.producer) : '未知步骤'}
                    </div>
                    <div className="mt-2 text-xs leading-relaxed text-on-surface-variant/80">{formatSummary(artifact.summary)}</div>
                    {artifact.path ? <div className="mt-2 break-all text-[11px] text-on-surface-variant/60">路径：{artifact.path}</div> : null}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
