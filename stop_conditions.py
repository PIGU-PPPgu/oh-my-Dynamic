"""
停机条件 —— 什么时候该停止迭代？

来自 VMAO 论文 (arXiv 2603.11445) 的 5 种停机条件：
  1. ReadyForSynthesis — 80% 子问题已回答
  2. HighConfidence — 高置信度 + 50% 完成
  3. DiminishingReturns — 改善 < 5%
  4. TokenBudget — token 用尽
  5. MaxIterations — 迭代次数到上限

实践中，>75% 的查询通过资源类条件（3/4/5）终止。
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional
from abc import ABC, abstractmethod


@dataclass
class IterationState:
    """
    每次迭代后的状态快照。
    
    StopConditionManager 收集这些数据，
    传给每个 StopCondition 判断是否该停。
    """
    iteration_count: int = 0
    total_nodes: int = 0
    completed_nodes: int = 0
    failed_nodes: int = 0
    avg_completeness: float = 0.0     # 0.0-1.0 平均完备度
    avg_confidence: float = 0.0       # 0.0-1.0 平均置信度
    total_tokens_used: int = 0
    total_duration_s: float = 0.0
    
    # 历史记录（用于检测边际递减）
    completeness_history: list[float] = field(default_factory=list)
    
    @property
    def completion_ratio(self) -> float:
        """完成率"""
        return self.completed_nodes / max(self.total_nodes, 1)
    
    def snapshot(self) -> dict:
        """导出当前状态"""
        return {
            "iteration": self.iteration_count,
            "completed": f"{self.completed_nodes}/{self.total_nodes}",
            "completeness": f"{self.avg_completeness:.2%}",
            "confidence": f"{self.avg_confidence:.2%}",
            "tokens": self.total_tokens_used,
            "duration": f"{self.total_duration_s:.0f}s",
        }


class StopCondition(ABC):
    """停机条件基类"""
    
    @abstractmethod
    def should_stop(self, state: IterationState) -> tuple[bool, str]:
        """
        判断是否应该停止。
        返回 (should_stop, reason)
        """
        ...
    
    @property
    @abstractmethod
    def name(self) -> str:
        """条件名称"""
        ...


class ReadyForSynthesis(StopCondition):
    """
    准备就绪 — 80% 的子问题已回答。
    
    来自 VMAO 论文：当完备度达到阈值时，
    剩余未回答的问题对最终结果影响有限，
    可以进入综合阶段。
    """
    
    def __init__(self, threshold: float = 0.80):
        self.threshold = threshold
    
    @property
    def name(self) -> str:
        return f"ReadyForSynthesis({self.threshold:.0%})"
    
    def should_stop(self, state: IterationState) -> tuple[bool, str]:
        if state.avg_completeness >= self.threshold:
            return True, f"完备度 {state.avg_completeness:.0%} ≥ {self.threshold:.0%}，可以进入综合阶段"
        return False, ""


class HighConfidence(StopCondition):
    """
    高置信度 — 75% 置信度 + 50% 完成。
    
    来自 VMAO 论文：虽然覆盖不完整，
    但已有结果质量很高，
    继续迭代不如直接综合。
    """
    
    def __init__(self, confidence_threshold: float = 0.75, min_completion: float = 0.50):
        self.confidence_threshold = confidence_threshold
        self.min_completion = min_completion
    
    @property
    def name(self) -> str:
        return f"HighConfidence(conf>={self.confidence_threshold:.0%}, done>={self.min_completion:.0%})"
    
    def should_stop(self, state: IterationState) -> tuple[bool, str]:
        if (state.avg_confidence >= self.confidence_threshold 
            and state.completion_ratio >= self.min_completion):
            return True, (f"高置信度 {state.avg_confidence:.0%} ≥ {self.confidence_threshold:.0%} "
                         f"且完成率 {state.completion_ratio:.0%} ≥ {self.min_completion:.0%}")
        return False, ""


class DiminishingReturns(StopCondition):
    """
    边际递减 — 最近两次迭代改善 < 5%。
    
    来自 VMAO 论文：最常见的前两个终止条件之一。
    进一步迭代收益很小。
    """
    
    def __init__(self, min_improvement: float = 0.05):
        self.min_improvement = min_improvement
    
    @property
    def name(self) -> str:
        return f"DiminishingReturns(gain<{self.min_improvement:.0%})"
    
    def should_stop(self, state: IterationState) -> tuple[bool, str]:
        if len(state.completeness_history) < 2:
            return False, ""
        
        recent_gain = state.completeness_history[-1] - state.completeness_history[-2]
        
        if recent_gain < self.min_improvement and state.iteration_count >= 2:
            return True, f"最近改善 {recent_gain:.1%} < {self.min_improvement:.0%}，边际递减"
        return False, ""


class TokenBudget(StopCondition):
    """
    Token 预算耗尽。
    
    来自 VMAO 论文：硬性成本限制。
    默认 1M token。
    """
    
    def __init__(self, max_tokens: int = 1_000_000):
        self.max_tokens = max_tokens
    
    @property
    def name(self) -> str:
        return f"TokenBudget({self.max_tokens:,})"
    
    def should_stop(self, state: IterationState) -> tuple[bool, str]:
        if state.total_tokens_used >= self.max_tokens:
            return True, f"Token 用量 {state.total_tokens_used:,} ≥ 预算 {self.max_tokens:,}"
        return False, ""


class MaxIterations(StopCondition):
    """
    最大迭代次数。
    
    来自 VMAO 论文：硬性迭代限制。
    默认 3 次。
    """
    
    def __init__(self, max_iterations: int = 3):
        self.max_iterations = max_iterations
    
    @property
    def name(self) -> str:
        return f"MaxIterations({self.max_iterations})"
    
    def should_stop(self, state: IterationState) -> tuple[bool, str]:
        if state.iteration_count >= self.max_iterations:
            return True, f"迭代 {state.iteration_count} ≥ 上限 {self.max_iterations}"
        return False, ""


class StopConditionManager:
    """
    停机条件管理器。
    
    检查顺序：先检查硬限制（Token/迭代），再检查质量条件。
    
    用法：
        manager = StopConditionManager.default()
        
        state = IterationState(
            iteration_count=2,
            total_nodes=10,
            completed_nodes=8,
            avg_completeness=0.85,
            ...
        )
        
        should_stop, reason = manager.check_all(state)
        if should_stop:
            print(f"停止迭代: {reason}")
    """
    
    def __init__(self, conditions: Optional[list[StopCondition]] = None):
        # 硬限制优先
        self._hard_limits: list[StopCondition] = []
        self._quality_conditions: list[StopCondition] = []
        
        if conditions:
            for c in conditions:
                if isinstance(c, (TokenBudget, MaxIterations)):
                    self._hard_limits.append(c)
                else:
                    self._quality_conditions.append(c)
    
    @classmethod
    def default(
        cls,
        max_tokens: int = 1_000_000,
        max_iterations: int = 3,
        completeness_threshold: float = 0.80,
        confidence_threshold: float = 0.75,
        min_improvement: float = 0.05,
    ) -> "StopConditionManager":
        """默认配置（对标 VMAO 论文参数）"""
        return cls([
            TokenBudget(max_tokens),
            MaxIterations(max_iterations),
            ReadyForSynthesis(completeness_threshold),
            HighConfidence(confidence_threshold),
            DiminishingReturns(min_improvement),
        ])
    
    def check_all(self, state: IterationState) -> tuple[bool, str]:
        """
        检查所有条件。
        硬限制优先 → 质量条件其次。
        """
        # 先检查硬限制
        for condition in self._hard_limits:
            should_stop, reason = condition.should_stop(state)
            if should_stop:
                return True, f"[{condition.name}] {reason}"
        
        # 再检查质量条件
        for condition in self._quality_conditions:
            should_stop, reason = condition.should_stop(state)
            if should_stop:
                return True, f"[{condition.name}] {reason}"
        
        return False, ""
    
    def list_conditions(self) -> list[str]:
        """列出所有条件"""
        return [c.name for c in self._hard_limits + self._quality_conditions]
