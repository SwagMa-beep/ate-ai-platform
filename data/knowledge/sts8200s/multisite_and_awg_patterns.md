# STS8200S 多工位与 AWG 模式经验

多工位要点：
- `HardWareCfg()` 中需要显式配置模块到 site 的映射
- 同一套测试程序在多工位下必须确认每个 site 的资源编号一致或明确可转换
- site 间误差不能直接归因为 DUT，需要先排除资源和治具差异

AWG 相关经验：
- 线性调整率、负载调整率、dropout 等测试常使用 AWG 创建扫描波形
- 常见流程是：
  1. `AwgClear()`
  2. `STSAWGCreateRampData(...)`
  3. `AwgLoader(...)`
  4. `AwgSelect(...)`
  5. `MeasureVI(..., MEAS_AWG)`
  6. `STSEnableAWG(...)`
  7. `STSEnableMeas(...)`
  8. `STSAWGRun()` 或 `STSAWGRunTriggerStop(...)`

适合用 AWG 的场景：
- VIN 扫描
- 负载电流扫描
- 启动时间测量
- dropout 触发点测量

实现风险：
- 取样窗口定义不一致，导致同一测试项重复性差
- 扫描区间包含过渡态，但统计时没有剔除
- 不同量程下直接复用同一 AWG 模板，导致保护和分辨率都不理想
