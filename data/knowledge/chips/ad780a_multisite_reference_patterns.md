# AD780A multisite reference patterns

器件定位：
- 精密基准源 / reference 类器件
- 案例程序采用双工位并行测试

案例中的资源结构：
- `VIN` 用 FOVI 做输入供电
- `VOUT` 用 FOVI 做输出电流负载与电压测量
- `CBIT128` 用于切换 2.5V / 3.0V 输出相关路径
- `SiteNum = 2`
- `HardWareCfg()` 里对两组 FOVI 通道做明确工位绑定

双工位实现要点：
- `StsSetModuleToSite(MD_FOVI, SITE_1, 8, 9, -1)`
- `StsSetModuleToSite(MD_FOVI, SITE_2, 13, 12, -1)`
- 测试结果循环按 `for (int i = 0; i < SiteNum; i++)` 写回
- 适合做“同一测试流、多 site 同步采样”的参考模板

核心测试项模式：
- `VO1 / VO2`：直接静态测输出电压
- `LNR1 / LNR2`：输入电压扫描，算线性调整率
- `LDR1 / LDR2`：输出负载扫描，算负载调整率
- `IQ / IOS`：静态电流 / 短路电流类

AWG 动态扫描的典型套路：
1. `AwgClear()`
2. `STSAWGCreateRampData(...)` 构造输入或负载波形
3. `AwgLoader(...)`
4. `AwgSelect(...)`
5. `MeasureVI(..., MEAS_AWG)`
6. `STSEnableAWG(...)`
7. `STSEnableMeas(...)`
8. `STSAWGRun()`
9. 在指定 sample 区间平均采样结果

线性调整率 LNR 的实现思路：
- 固定输出空载条件
- 扫输入电压，例如 4V -> 36V
- 在两个稳定区间内分别求平均输出电压
- 用 `ΔVout / ΔVin` 再做单位换算，得到 uV/V 级结果

负载调整率 LDR 的实现思路：
- 固定输入电压
- 让 `VOUT` 作为 force current 负载做阶跃扫描
- 比较不同负载区间的输出电压平均值
- 用 `ΔVout / ΔIout` 或等效方式得到负载调整率

CBIT 使用意义：
- 切 2.5V / 3.0V 输出路径时，先 `SetCBITOn`，测完再 `SetCBITOff`
- 说明参考源/可调输出类器件通常不仅要扫源和负载，还要配合继电器切配置

工程建议：
- 多工位参考源测试优先确认 site 间资源是否 truly independent
- AWG 结果计算时，明确“取哪一段 sample 点做平均”
- 对基准源类器件，稳定时间和平均窗口比单点读数更重要

常见风险：
- site 绑定顺序和实际通道不一致，导致两个工位读数串位
- 采样区间没避开 AWG 上升/下降沿，导致调整率计算漂
- 切换 2.5V / 3.0V 路径后忘了恢复 CBIT 状态
