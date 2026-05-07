# Digital adapter mapping patterns

适用场景：
- 24PIN 数字通用适配器
- TTL / CMOS 数字器件
- 数字模板程序和自定义数字测试程序

典型资源分布：
- D0-D23：数字通道
- CBIT0-CBIT39：继电器控制位
- DGND / AGND / JGND：不同地参考
- J5V：固定 5V
- VDD / VSS：固定 ±15V
- FH / SH：FOVI 的 FORCE / SENSE
- TMU：时间测量辅助资源

电源与地的实现思路：
- 适配器通过拨码开关决定哪些插座 pin 接到 VCC / GND
- 支持 VCC1 与 VCC2 两路电源
- 外部上拉/下拉模块可使用额外 FOVI 路径提供偏置

数字适配器的典型逻辑：
- DIO 提供逻辑激励与比较
- FOVI / PMU 提供直流参数测量能力
- CBIT 控制辅助路径、上拉/下拉、继电器切换
- TMU 只在有时间参数测试需求时介入

工程建议：
- 做数字器件 ResourceMap 时，不只要画 pin 对 DIO，还要同时标记：
  - pin 对应的电源路径
  - 是否需要 PMU 测量
  - 是否需要外部上拉/下拉
  - 是否需要 TMU 辅助
- 对双电源数字器件，提前确定哪些参数走 VCC1，哪些要拉起 VCC2

与模板程序的关系：
- `.vecdio` 负责数字向量
- `Template.pgs` 负责测试条件
- 适配器实际资源决定哪些测试条件在平台上可实现

常见风险：
- 只完成 DIO pin mapping，没有完成 VCC/GND 路径映射
- 忘记上拉/下拉辅助通路，导致开漏/三态器件行为异常
- 需要 PMU 测试的 pin 没有设计合适切换路径
- 将数字 pin、模拟源、继电器关系分开管理，后期很难排查
