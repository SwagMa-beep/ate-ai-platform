# STS8200S programming lifecycle and core API usage

测试程序框架函数：
- `HardWareCfg()`
- `InitBeforeTestFlow()`
- `InitAfterTestFlow()`
- `UserInit()`
- `UserLoad()`
- `UserExit()`
- `OnSot()`
- `SetupFailSite()`
- `BinOutDut()`
- `OnNewLot()`
- `OnWaferEnd()`

最常见的生命周期理解：
1. `HardWareCfg()`
   - 做工位和资源绑定
   - 定义并行工位结构
   - 典型动作：`StsSetModuleToSite(...)` 或 `STSSetMultiSite(...)`
2. `InitBeforeTestFlow()`
   - 每次测试主流程开始前执行一次
   - 用于恢复安全状态、清零板卡、准备环境
3. `InitAfterTestFlow()`
   - 每次测试主流程结束后执行一次
   - 用于释放资源、关闭输出、回到安全态
4. `UserLoad()`
   - Load 程序后的第一次测试前调用
   - 适合做一次性系统检查，例如校准检查

工位与资源绑定要点：
- `StsSetModuleToSite(MD_FOVI, SITE_1, 0, 1, -1)` 用显式通道列表绑定
- `STSSetMultiSite(MD_FOVI, SITE_1, "0-7")` 用字符串形式绑定
- 程序工位数由所有绑定模块里的最大工位数决定
- 绑定规则要考虑不同板卡的通道含义不同：
  - FOVI100 的 `0` 就是 CH0，`1` 就是 CH1
  - OVI40 的逻辑分组方式不同，不能直接照搬 FOVI 习惯

硬件配置检查建议：
- 在 `HardWareCfg()` 中结合 `STSEnableCfgCheck()` 做资源校验
- 可以提前发现“需要 4 块 FOVI，但机柜只装了 3 块”这类问题

参数读取与结果上报主链路：
1. `CParam* param = StsGetParam(funcIndex, "ParamName")`
2. 检查返回值是否为 `NULL`
3. 执行测量
4. `param->SetTestResult(site, subUnit, result)`
5. 必要时 `SetResultRemark(...)`

`StsGetParam()` 使用建议：
- 参数名必须与 PGS / TestPlan 定义一致
- 如果参数已删除或拼写错误，会返回 `NULL`
- `NULL` 不能继续用于设置结果或读取条件

`SetTestResult()` 使用建议：
- `site=0` 代表 Site1，`site=1` 代表 Site2，以此类推
- `subUnit=0` 通常对应单元 1
- 单位换算应在写结果前完成，例如电流 A -> mA
- 结果写入后才能进入主界面的统计、bin 和报表链路

常见工程规则：
- 没有 `StsGetParam()` 的测试项，通常意味着参数来源不明确
- 没有 `SetTestResult()` 的测试项，即使测到了也不会进正式结果
- `InitBeforeTestFlow()` / `InitAfterTestFlow()` 缺失会让程序更容易受上一次状态污染
- 在 `UserLoad()` 中做校准检查、配置检查，比等到测试中途失败更稳

与数字/模拟案例的联系：
- 模拟程序常见：`HardWareCfg -> InitBeforeTestFlow -> FOVI/QTMU/AWG -> SetTestResult`
- 数字模板常见：`Init -> LoadVectorFile -> Run -> SaveFailMap -> SetResultRemark / SetTestResult`
