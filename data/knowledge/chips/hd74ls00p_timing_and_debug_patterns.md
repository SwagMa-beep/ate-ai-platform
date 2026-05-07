# HD74LS00P timing and debug patterns

适用场景：
- TTL NAND 门的传播延时测试
- 数字器件功能测试失败后的定位
- DIO + CBIT + QTMU 联动测量

从案例程序可见的关键实现模式：
- `TPHL` / `TPLH` 不是直接靠 DIO 的 pass/fail，而是通过 `QTMU_PLUS` 读取时间结果
- `CBIT` 用来把特定输入脚和输出脚切到 `TMUA / TMUB`
- `DIO.Run("T6","T7")` 或 `Run("T8","T9")` 用于制造触发波形

典型时序测量流程：
1. `vcc1.Set(...)` 上电到 5V
2. `dio.Connect()` 并设置逻辑电平
3. `cbit.SetCBITOn(index)` 把待测输入输出切到 TMU 路径
4. `tmu0.Connect()`
5. 设置：
   - `SetStartInput(...)`
   - `SetStopInput(...)`
   - `SetStartTrigger(...)`
   - `SetStopTrigger(...)`
   - `SetInSource(QTMU_PLUS_DUAL_SOURCE)`
   - `ChannelSetup(...)`
6. `SetSinglePulseMeas(QTMU_PLUS_FINE, QTMU_PLUS_TIME_NS, 0)`
7. `SetTimeOut(10)`
8. `dio.Run(...)` 产生激励
9. `SinglePlsMeas(0)`
10. `GetMeasureResult(0)` 读时间结果并写 `SetTestResult`
11. 关闭 CBIT / TMU / DIO

TPHL / TPLH 的触发差异：
- `TPHL` 常见配置：
  - start trigger = 输入负跳变
  - stop trigger = 输出正跳变
  - 或根据具体 NAND 方向做对应设置
- `TPLH` 常见配置：
  - start trigger = 输入正跳变
  - stop trigger = 输出负跳变

工程建议：
- 做传播延时前，先确认功能向量本身能稳定跑通
- `CBIT` 切换路径一定要和实际被测脚对应，否则 TMU 测到的是错线
- `QTMU_PLUS_FINE + TIME_NS` 适合这类 ns 级延时
- 对 TTL 器件，触发门限值应贴近实际逻辑翻转区，不要随意照搬满量程比例

调试经验：
- 若时间读数一直为 0 或超时，优先检查：
  - `CBIT` 是否切对
  - `ChannelSetup(CHA_START/CHA_STOP)` 是否选对
  - `Run()` 的 label 是否真在切换该输入
  - start/stop edge 是否与真实波形方向一致
- 功能测试先失败时，不要直接看 TMU 结果，先用 `SaveFailMap()` 和 `GetPatternRunResult()` 定位向量问题

常见风险：
- QTMU 连接和 CBIT 路径没有对应上
- label 区间只切换了输入，没有形成预期输出翻转
- 把 TPHL / TPLH 的起止边沿配反
- 测时间前没有先确认上电、逻辑电平、DIO 向量状态
