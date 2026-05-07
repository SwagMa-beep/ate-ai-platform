# STS8200 hardware resource envelope

目标：
- 帮助判断机台资源上限
- 帮助在 TestPlan / ResourceMap 阶段做“平台能否实现”的预审

测试盒资源概览（不同版本略有差异）：
- CBIT128：128 路 C-Bits
- DVI400：典型 16 x DVI
- FOVI100：典型 16 x FOVI，某些版本可到 32 / 48 路 FOVI 组合
- PVI10：4~8 路 PVI
- FPVI10：4~8 路 FPVI
- QTMU_PLUS：4 路 QTMU
- ACSM_PLUS：4 路 ACSM
- QVM：4 路 QVM
- DIO：1 块数字模块入口

硬件版本差异要点：
- Rev1.3 / Rev1.4 / Rev2.0 的测试盒前面板和资源插座组合不同
- 同一个插座位置，在不同版本里可能支持：
  - DVI
  - OVI
  - FOVI
  - 混插

资源规划建议：
- 先确认测试盒版本和插座类型
- 再确认项目实际安装的模块数量
- 最后才做 ResourceMap / 工位绑定

常见预审问题：
- 设计里假设有 4 块 FOVI，但机柜实际只装 2 块
- 想做更多并行 site，但 QTMU / QVM / ACSM 数量不足
- DIO / CBIT / 模拟源之间的同步关系没有提前规划

与工位绑定的关系：
- 并行工位数不只取决于软件设置，也取决于可用模块数量
- `HardWareCfg()` 里绑定得出来，不代表机台真实资源一定够
- 最好配合 `STSEnableCfgCheck()` 提前校验

工程建议：
- 在 TestPlan 评审时就记录每个关键测试项的资源需求
- 对高价值资源单独标记：
  - FOVI
  - QTMU
  - QVM
  - DIO
  - CBIT
- 多工位目标越高，越要先看平台资源上限而不是先写程序

典型结论方式：
- “此方案需要 2 块 FOVI + 1 块 QTMU + 1 块 DIO，支持 2 工位较稳，4 工位需重新评估资源分配。”
