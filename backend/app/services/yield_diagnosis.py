"""
良率诊断服务 - 目标④
基于 IsolationForest 的无监督异常检测 + 线性回归预测良率趋势
使用仿真数据驱动真实 ML 模型，演示边缘 AI 量产诊断能力
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional

# ── ML 依赖（可选）──────────────────────────────────────────────
try:
    import numpy as np
    from sklearn.ensemble import IsolationForest
    from sklearn.preprocessing import StandardScaler
    ML_AVAILABLE = True
except ImportError:
    ML_AVAILABLE = False


@dataclass
class WaveformPoint:
    t_us:    float  # 时间（μs）
    voltage: float  # 电压（V）
    current: float  # 电流（mA）
    is_anomaly: bool = False


@dataclass
class AnomalyEvent:
    type:        str    # "relay_degradation" | "thermal_drift" | "contact_noise" | "esd_spike"
    confidence:  float  # 0.0-1.0
    description: str
    severity:    str    # "high" | "medium" | "low"
    timestamp:   str    = ""
    channel:     int    = 0


@dataclass
class DiagnosisResult:
    yield_rate:      float          # 当前良率 %
    yield_trend:     float          # 趋势（%/hr，负数为下降）
    yield_predicted: float          # T+4H 预测良率
    fty_rolling:     float          # 一次通过率（1H 滚动）
    anomalies:       List[AnomalyEvent] = field(default_factory=list)
    waveform:        List[Dict]         = field(default_factory=list)
    sample_count:    int    = 0
    anomaly_ratio:   float  = 0.0
    model_backend:   str    = "IsolationForest"
    analysis_time_ms: float = 0.0

    def to_dict(self) -> Dict:
        return {
            "yield_rate":       round(self.yield_rate, 2),
            "yield_trend":      round(self.yield_trend, 3),
            "yield_predicted":  round(self.yield_predicted, 2),
            "fty_rolling":      round(self.fty_rolling, 2),
            "sample_count":     self.sample_count,
            "anomaly_ratio":    round(self.anomaly_ratio, 4),
            "model_backend":    self.model_backend,
            "analysis_time_ms": round(self.analysis_time_ms, 1),
            "anomalies": [
                {
                    "type":        a.type,
                    "confidence":  round(a.confidence, 2),
                    "description": a.description,
                    "severity":    a.severity,
                    "timestamp":   a.timestamp,
                    "channel":     a.channel,
                }
                for a in self.anomalies
            ],
            "waveform": self.waveform,
        }


class YieldDiagnosisService:
    """边缘 AI 量产良率诊断引擎"""

    def __init__(self):
        self._history: List[float] = []  # 历史良率记录
        self._model_backend = "IsolationForest" if ML_AVAILABLE else "Rule-Based"

    # ── 主接口 ────────────────────────────────────────────────────

    def run_diagnosis(
        self,
        n_samples:      int  = 200,
        inject_anomaly: bool = True,
        anomaly_ratio:  float = 0.08,
        channel:        int  = 4,
    ) -> DiagnosisResult:
        """运行一次完整的良率诊断分析。"""
        t0 = time.time()

        # 1. 生成仿真波形数据
        waveform, raw_data = self._simulate_waveform(
            n_samples      = n_samples,
            inject_anomaly = inject_anomaly,
            anomaly_ratio  = anomaly_ratio,
        )

        # 2. 异常检测
        anomaly_flags, scores = self._detect_anomalies(raw_data)
        real_anomaly_count = sum(anomaly_flags)
        real_anomaly_ratio = real_anomaly_count / max(len(anomaly_flags), 1)

        # 3. 良率计算
        yield_rate = round(100.0 * (1 - real_anomaly_ratio) * random.uniform(0.95, 1.05), 2)
        yield_rate = max(60.0, min(99.9, yield_rate))
        self._history.append(yield_rate)
        if len(self._history) > 20:
            self._history.pop(0)

        # 4. 良率趋势预测
        trend, predicted = self._predict_trend(self._history, horizon_hours=4)

        # 5. 识别故障类型
        anomalies = self._classify_anomalies(
            waveform       = waveform,
            anomaly_flags  = anomaly_flags,
            scores         = scores,
            channel        = channel,
        )

        # 6. 准备波形数据（降采样至100点）
        step = max(1, len(waveform) // 100)
        wf_data = [
            {
                "t":    round(p.t_us, 2),
                "v":    round(p.voltage, 4),
                "i":    round(p.current, 4),
                "flag": p.is_anomaly,
            }
            for p in waveform[::step]
        ]

        elapsed_ms = (time.time() - t0) * 1000

        fty = yield_rate * random.uniform(0.97, 1.00)

        return DiagnosisResult(
            yield_rate       = yield_rate,
            yield_trend      = trend,
            yield_predicted  = predicted,
            fty_rolling      = round(fty, 2),
            anomalies        = anomalies,
            waveform         = wf_data,
            sample_count     = n_samples,
            anomaly_ratio    = real_anomaly_ratio,
            model_backend    = self._model_backend,
            analysis_time_ms = elapsed_ms,
        )

    # ── 仿真数据生成 ──────────────────────────────────────────────

    def _simulate_waveform(
        self,
        n_samples:      int,
        inject_anomaly: bool,
        anomaly_ratio:  float,
    ):
        """生成符合 ATE VI 数字化仪真实特征的仿真波形数据"""
        waveform  = []
        raw_data  = []   # 用于 ML 的特征向量

        anomaly_indices = set()
        if inject_anomaly:
            n_anomaly = max(1, int(n_samples * anomaly_ratio))
            anomaly_start = random.randint(int(n_samples * 0.5), int(n_samples * 0.8))
            anomaly_indices = set(range(anomaly_start, min(anomaly_start + n_anomaly, n_samples)))

        for i in range(n_samples):
            t_us = i * 10.0   # 10μs 采样间隔

            is_anom = i in anomaly_indices

            if is_anom:
                # 继电器退化：瞬态尖峰 + 抖动
                voltage = 5.0 + random.gauss(0, 0.3) + random.choice([1.5, -1.5, 2.0, -2.0])
                current = 0.1 + random.gauss(0, 0.05) + random.uniform(0.3, 0.8)
            else:
                # 正常工作态：轻微高斯噪声
                voltage = 5.0 + random.gauss(0, 0.02)
                current = 0.1 + random.gauss(0, 0.003)

            waveform.append(WaveformPoint(
                t_us=t_us, voltage=voltage,
                current=current, is_anomaly=is_anom,
            ))
            raw_data.append([voltage, current, abs(voltage - 5.0), abs(current - 0.1)])

        return waveform, raw_data

    # ── 异常检测 ──────────────────────────────────────────────────

    def _detect_anomalies(self, raw_data) -> tuple:
        """IsolationForest 无监督异常检测"""
        if not ML_AVAILABLE or len(raw_data) < 10:
            # 降级：简单阈值检测
            flags = [abs(d[0] - 5.0) > 0.5 or abs(d[1] - 0.1) > 0.2 for d in raw_data]
            scores = [abs(d[0] - 5.0) for d in raw_data]
            return flags, scores

        import numpy as np
        X = np.array(raw_data)
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        model = IsolationForest(
            contamination=0.08,
            n_estimators=100,
            random_state=42,
        )
        preds  = model.fit_predict(X_scaled)
        scores = -model.score_samples(X_scaled)  # 越高越异常

        flags = [p == -1 for p in preds]
        return flags, scores.tolist()

    # ── 良率趋势预测 ──────────────────────────────────────────────

    def _predict_trend(
        self,
        history: List[float],
        horizon_hours: int = 4,
    ):
        """线性回归预测良率趋势"""
        if len(history) < 3:
            return -0.5, max(60.0, history[-1] - 2.0) if history else 80.0

        if ML_AVAILABLE:
            import numpy as np
            x = np.arange(len(history), dtype=float)
            y = np.array(history)
            # 最小二乘线性回归
            A = np.vstack([x, np.ones(len(x))]).T
            m, _ = np.linalg.lstsq(A, y, rcond=None)[0]
            # m 为每次采样的斜率，转换为 %/hr（假设每次采样间隔 15min）
            trend_per_hr = m * 4
            predicted = max(60.0, history[-1] + trend_per_hr * horizon_hours)
        else:
            # 简单差分
            trend_per_hr = (history[-1] - history[0]) / max(len(history) - 1, 1) * 4
            predicted = max(60.0, history[-1] + trend_per_hr * horizon_hours)

        return round(trend_per_hr, 3), round(predicted, 2)

    # ── 故障分类 ──────────────────────────────────────────────────

    def _classify_anomalies(
        self,
        waveform:      List[WaveformPoint],
        anomaly_flags: List[bool],
        scores:        List[float],
        channel:       int,
    ) -> List[AnomalyEvent]:
        """基于异常特征分类故障类型"""
        events = []
        now_str = datetime.now().strftime("%H:%M:%S")

        anomaly_pts = [p for p, f in zip(waveform, anomaly_flags) if f]
        if not anomaly_pts:
            return events

        # 检测继电器退化（大幅电压尖峰）
        spike_pts = [p for p in anomaly_pts if abs(p.voltage - 5.0) > 1.0]
        if spike_pts:
            conf = min(0.99, 0.70 + 0.03 * len(spike_pts))
            events.append(AnomalyEvent(
                type        = "relay_degradation",
                confidence  = conf,
                description = (
                    f"瞬态电压尖峰超过典型阈值 {round(abs(spike_pts[0].voltage - 5.0) / 5.0 * 100, 0):.0f}%。"
                    f"特征与继电器触点退化引起的弧放电高度吻合，建议立即检查测试板 K{channel+1}。"
                ),
                severity    = "high",
                timestamp   = now_str,
                channel     = channel,
            ))

        # 检测热漂移（基线缓慢偏移）
        if len(waveform) > 50:
            first_v = sum(p.voltage for p in waveform[:20]) / 20
            last_v  = sum(p.voltage for p in waveform[-20:]) / 20
            drift   = abs(last_v - first_v)
            if 0.05 < drift < 1.0:
                events.append(AnomalyEvent(
                    type        = "thermal_drift",
                    confidence  = 0.55 + drift,
                    description = (
                        f"DUT 基线电压在测试周期内漂移 {drift*1000:.1f}mV。"
                        f"与夹具热漂移特征吻合，可能导致模拟模块轻微测量偏移。"
                    ),
                    severity    = "medium",
                    timestamp   = now_str,
                    channel     = channel,
                ))

        # 检测接触噪声（小幅高频抖动）
        small_noise = [p for p in anomaly_pts if 0.1 < abs(p.voltage - 5.0) <= 1.0]
        if small_noise and not spike_pts:
            events.append(AnomalyEvent(
                type        = "contact_noise",
                confidence  = 0.18 + random.uniform(0, 0.15),
                description = (
                    f"CH{channel} 检测到轻微接触噪声（{len(small_noise)} 个采样点）。"
                    f"与探针间歇性接触特征部分吻合，符合当前维护周期的典型情况。"
                ),
                severity    = "low",
                timestamp   = now_str,
                channel     = channel,
            ))

        return events
