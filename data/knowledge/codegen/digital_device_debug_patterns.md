# Digital device debug patterns

适用场景：
- TTL / CMOS 数字器件测试程序调试
- 向量失败后的定位
- 结合 PMU / DIO / TMU 的联合排错

建议的排错顺序：
1. 看工程是否成功装载 `.pgs + .vecdio`
2. 看 `UserLoad()` 是否成功 `LoadVectorFile`
3. 先跑 `CON`
4. 再跑 `FUN`
5. 再跑阈值/电流/电源类参数
6. 若涉及时序参数，再切到 `QTMU + CBIT` 路径

为什么这个顺序重要：
- `CON` 解决“物理连接对不对”
- `FUN` 解决“逻辑向量对不对”
- 参数测试解决“边界和量值对不对”
- 时序测试最后做，能避免把基础错误误判成速度问题

向量失败时先看什么：
- `GetPatternRunResult()`
- `SaveFailMap()`
- pin 的 `SetResultRemark()`

如果功能测试失败：
- 先确认：
  - VCC 是否正确
  - DIO pin mapping 是否正确
  - logic level 是否贴合 datasheet
  - vecdio label 是否选对
- 再看 fail line 是否集中在固定 label 或固定 pin

如果 PMU 参数异常：
- 先确认当前 pin 是否已从 DIO 路径切到 PMU 路径
- 看 PMU 量程和模式是否正确：
  - `FVMI` 还是 `FIMV`
- 看是否在测前做了 `pmu.Reset()`

如果时间参数异常：
- 先确认功能向量能真正翻转输入/输出
- 再确认 `CBIT + TMU` 路径是否切对
- 最后再看 trigger 电平、边沿和 timeout

工程建议：
- 对每个测试项都保留清晰 remark，定位速度会快很多
- 新器件首次调试时，先只跑最小真值表和最少几个参数
- 不要一上来全量跑所有参数，否则很难判断是连接、向量还是资源路径的问题
