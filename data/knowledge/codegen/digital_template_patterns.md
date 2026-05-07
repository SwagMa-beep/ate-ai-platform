# 数字器件模板程序模式

模板工程中可观察到的共性模式：
- `UserLoad()` 负责初始化 DIO 和加载向量文件
- `HardWareCfg()` 负责硬件检查与资源分配
- `InitBeforeTestFlow()` 和 `InitAfterTestFlow()` 负责上电和恢复
- `CON` 测试使用 `pmu.SetAndMeas(...)` 做连接性检查
- `FUN` 测试使用 `dio.Run(...)` 运行向量并用 `GetPatternRunResult()` 获取结果

代码审查时建议优先看：
1. 向量文件是否加载成功
2. DIO 电平是否合理设置
3. `SetTestResult(...)` 和 `SetResultRemark(...)` 是否完整
4. `pmu.Reset()` / `dio.Disconnect()` 是否及时执行

适合沉淀成模板规则的点：
- CON 场景：逐引脚测量并给 remark
- FUN 场景：跑 pattern、存 fail map、再上报结果
- 电源恢复动作：测试结束后回零并断开
