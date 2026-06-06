"""
验证框架 —— 怎么证明编排脚本真的有效？

验证分三层：
  1. 单元测试：每个组件独立正确（状态机、解析器）
  2. 集成测试：API 调用链路通畅（mock 或真实调用）
  3. 端到端测试：完整编排流程能跑通并产出正确结果

核心验证指标：
  - 任务完成率 = completed / total
  - 一次通过率 = 首次 review 通过的任务数 / total
  - 状态机正确性 = 是否有非法转换
  - 依赖正确性 = B 是否真的等 A 完成后才开始
  - 输出质量 = 最终结果是否符合预期（人工判断）
"""

from __future__ import annotations
import json
import time
from typing import Callable, Optional

from oh_my_dynamic.runtime.task import Task, TaskStatus, can_transition, is_blocked, is_dispatchable, is_terminal
from oh_my_dynamic.runtime.orchestrator import Orchestrator, parse_plan


# ============================================================
# Layer 1: 单元测试
# ============================================================

def test_state_machine():
    """测试状态机的所有合法和非法转换"""
    print("\n" + "="*50)
    print("🧪 Layer 1: 状态机单元测试")
    print("="*50)

    tests_passed = 0
    tests_failed = 0

    # 合法转换
    legal = [
        (TaskStatus.TODO, TaskStatus.IN_PROGRESS),
        (TaskStatus.IN_PROGRESS, TaskStatus.REVIEWING),
        (TaskStatus.REVIEWING, TaskStatus.DONE),
        (TaskStatus.REVIEWING, TaskStatus.TODO),   # 打回
        (TaskStatus.FAILED, TaskStatus.RETRYING),
        (TaskStatus.TODO, TaskStatus.CANCELLED),
    ]
    for frm, to in legal:
        ok = can_transition(frm, to)
        if ok:
            tests_passed += 1
            print(f"  ✅ {frm.value} → {to.value}")
        else:
            tests_failed += 1
            print(f"  ❌ {frm.value} → {to.value} (应该合法但不通过)")

    # 非法转换
    illegal = [
        (TaskStatus.TODO, TaskStatus.DONE),        # 不能直接完成
        (TaskStatus.DONE, TaskStatus.IN_PROGRESS),  # 完成后不能回去
        (TaskStatus.CANCELLED, TaskStatus.DONE),    # 取消后不能完成
    ]
    for frm, to in illegal:
        ok = can_transition(frm, to)
        if not ok:
            tests_passed += 1
            print(f"  ✅ {frm.value} → {to.value} (正确拒绝)")
        else:
            tests_failed += 1
            print(f"  ❌ {frm.value} → {to.value} (不应该允许)")

    # 终态判断
    for s in [TaskStatus.DONE, TaskStatus.FAILED, TaskStatus.CANCELLED]:
        if is_terminal(s):
            tests_passed += 1
            print(f"  ✅ {s.value} 是终态")
        else:
            tests_failed += 1

    # 可派发判断
    for s in [TaskStatus.TODO, TaskStatus.RETRYING]:
        if is_dispatchable(s):
            tests_passed += 1
            print(f"  ✅ {s.value} 可派发")
        else:
            tests_failed += 1

    print(f"\n  结果: {tests_passed} 通过, {tests_failed} 失败")
    return tests_failed == 0


def test_dependency_blocking():
    """测试依赖阻塞逻辑"""
    print("\n" + "="*50)
    print("🧪 Layer 1: 依赖阻塞测试")
    print("="*50)

    t1 = Task(id="t1", title="任务A", description="")
    t2 = Task(id="t2", title="任务B", description="", depends_on=["t1"])
    t3 = Task(id="t3", title="任务C", description="", depends_on=["t1", "t2"])

    all_tasks = {"t1": t1, "t2": t2, "t3": t3}

    # t1 未完成 → t2 被阻塞
    assert is_blocked(t2, all_tasks) == True, "t2 应该被阻塞"
    print("  ✅ t1=todo, t2 被阻塞")

    # t1 完成 → t2 不阻塞
    t1.status = TaskStatus.DONE
    assert is_blocked(t2, all_tasks) == False, "t2 不应该被阻塞"
    print("  ✅ t1=done, t2 不阻塞")

    # t1 完成 但 t2 未完成 → t3 仍被阻塞
    t2.status = TaskStatus.IN_PROGRESS
    assert is_blocked(t3, all_tasks) == True, "t3 应该被阻塞（等 t2）"
    print("  ✅ t1=done, t2=in_progress, t3 被阻塞")

    # 全部完成 → t3 不阻塞
    t2.status = TaskStatus.DONE
    assert is_blocked(t3, all_tasks) == False, "t3 不应该被阻塞"
    print("  ✅ t1=done, t2=done, t3 不阻塞")

    print("  结果: 全部通过 ✅")
    return True


def test_plan_parser():
    """测试 planner 输出解析器"""
    print("\n" + "="*50)
    print("🧪 Layer 1: Plan 解析器测试")
    print("="*50)

    # 模拟 planner 的输出
    sample_output = """
TASK: 数据清洗
DESC: 读取 CSV 文件，处理缺失值和异常值
ROLE: builder
PRIORITY: 1
DEPS: none

TASK: 数据分析
DESC: 对清洗后的数据进行统计分析
ROLE: builder
PRIORITY: 2
DEPS: 1

TASK: 生成报告
DESC: 审查分析结果，确认结论正确
ROLE: reviewer
PRIORITY: 3
DEPS: 2
"""

    plan = parse_plan(sample_output)

    assert len(plan) == 3, f"应该解析出3个任务，实际{len(plan)}"
    print(f"  ✅ 解析出 {len(plan)} 个任务")

    assert plan[0]['title'] == '数据清洗'
    assert plan[0]['role'] == 'builder'
    assert plan[0]['deps'] == []
    print(f"  ✅ 任务1: {plan[0]['title']} (角色={plan[0]['role']}, 依赖={plan[0]['deps']})")

    assert plan[1]['deps'] == ['1']
    print(f"  ✅ 任务2: {plan[1]['title']} (依赖任务1)")

    assert plan[2]['role'] == 'reviewer'
    print(f"  ✅ 任务3: {plan[2]['title']} (角色=reviewer)")

    print("  结果: 全部通过 ✅")
    return True


# ============================================================
# Layer 2: 集成测试（真实 API 调用）
# ============================================================

def test_single_agent_call():
    """测试单次 API 调用是否通畅"""
    print("\n" + "="*50)
    print("🧪 Layer 2: 单次 API 调用测试")
    print("="*50)

    try:
        from oh_my_dynamic.core.llm_client import call_llm

        response = call_llm(
            system_prompt="你是一个数学老师。",
            user_prompt="请计算 17 × 23，直接给出答案。",
            model="glm-5.1",
        )

        # 检查响应是否包含 391
        has_answer = '391' in response
        print(f"  模型响应: {response[:200]}")
        print(f"  {'✅ 包含正确答案 391' if has_answer else '⚠️ 未包含 391，但 API 调用成功'}")
        return True

    except Exception as e:
        print(f"  ❌ API 调用失败: {e}")
        return False


# ============================================================
# Layer 3: 端到端测试
# ============================================================

# 预定义的测试场景（从简到难）
TEST_SCENARIOS = {
    "easy": {
        "goal": "写一首关于编程的四行诗",
        "context": "风格要求：幽默、押韵",
        "validator": lambda result: len(result) > 20,  # 最基本：有输出
        "description": "简单创作任务，验证基本流程",
    },
    "medium": {
        "goal": "分析一个班级的考试成绩并给出建议",
        "context": "班级：707班，50名学生。数学平均分78，最高分98，最低分32。及格率72%。",
        "validator": lambda result: len(result) > 100 and ('建议' in result or '建议' in result),
        "description": "数据分析任务，验证 planner 能拆成多步骤",
    },
    "hard": {
        "goal": "设计一个学生成绩管理的数据库 schema",
        "context": "需求：支持多班级、多学科、多次考试，能统计排名和趋势",
        "validator": lambda result: 'CREATE' in result.upper() or '表' in result,
        "description": "技术设计任务，验证多步骤依赖和 review",
    },
}


def run_e2e_test(
    scenario: str = "easy",
    model: str = "glm-5.1",
    auto_approve: bool = False,
    custom_goal: str = "",
    custom_context: str = "",
    custom_validator: Optional[Callable] = None,
):
    """
    运行端到端测试。

    参数：
      scenario: "easy" | "medium" | "hard" | 预定义场景名
      model: 模型名称
      auto_approve: True=跳过 reviewer（更快，但不验证质量）
      custom_goal: 自定义目标（覆盖预定义场景）
      custom_context: 自定义上下文
      custom_validator: 自定义验证函数 (result_str) -> bool
    """
    print("\n" + "="*60)
    print("🧪 Layer 3: 端到端测试")
    print("="*60)

    # 选择场景
    if custom_goal:
        goal = custom_goal
        context = custom_context
        validator = custom_validator or (lambda r: len(r) > 10)
        desc = "自定义场景"
    else:
        sc = TEST_SCENARIOS.get(scenario, TEST_SCENARIOS["easy"])
        goal = sc["goal"]
        context = sc["context"]
        validator = sc["validator"]
        desc = sc["description"]

    print(f"\n  场景: {desc}")
    print(f"  目标: {goal}")
    print(f"  模型: {model}")
    print(f"  自动审批: {'是' if auto_approve else '否（走 reviewer）'}")
    print()

    # 运行编排
    engine = Orchestrator(model=model, auto_approve=auto_approve, verbose=True)
    result = engine.run(goal=goal, context=context)

    # 输出结果
    print("\n" + "="*60)
    print("📊 测试结果")
    print("="*60)

    status = result["status"]
    print(f"  编排状态: {'✅ ' + status if status == 'success' else '⚠️ ' + status}")
    print(f"  任务完成: {result['completed']}/{result['total']}")
    print(f"  耗时: {result['duration_s']}s")

    # 任务详情
    print("\n  任务执行详情:")
    for t in result["tasks"]:
        icon = {"done": "✅", "failed": "❌", "cancelled": "🚫"}.get(t["status"], "⏳")
        retry_info = f" (重试{t['attempts']-1}次)" if t["attempts"] > 1 else ""
        print(f"    {icon} {t['id']}: {t['title'][:35]} [{t['status']}]{retry_info}")
        if t.get("feedback"):
            print(f"       反馈: {t['feedback'][:100]}...")

    # 验证最终输出
    print("\n  最终输出验证:")
    output = result["final_output"]
    if validator(output):
        print("  ✅ 输出通过验证函数")
    else:
        print("  ⚠️ 输出未通过验证函数（可能质量不达标）")

    print(f"\n  输出长度: {len(output)} 字符")
    print(f"  输出预览:\n{'─'*40}")
    preview = output[:500] + ("..." if len(output) > 500 else "")
    print(preview)
    print("─" * 40)

    # 返回完整结果供进一步分析
    return result


# ============================================================
# 一键全量测试
# ============================================================

def run_all_tests(include_api: bool = False, include_e2e: bool = False, model: str = "glm-5.1"):
    """运行所有测试"""
    print("╔══════════════════════════════════════╗")
    print("║   多 Agent 编排脚本 · 验证框架      ║")
    print("╚══════════════════════════════════════╝")

    results = {}

    # Layer 1
    results["state_machine"] = test_state_machine()
    results["dependency"] = test_dependency_blocking()
    results["parser"] = test_plan_parser()

    # Layer 2
    if include_api:
        results["api_call"] = test_single_agent_call()

    # Layer 3
    if include_e2e:
        results["e2e_easy"] = run_e2e_test("easy", model=model, auto_approve=True)

    # 汇总
    print("\n" + "="*60)
    print("📋 测试汇总")
    print("="*60)
    for name, passed in results.items():
        icon = "✅" if passed else "❌"
        print(f"  {icon} {name}")

    all_passed = all(results.values())
    print(f"\n  总计: {'✅ 全部通过' if all_passed else '❌ 有失败项'}")
    return all_passed


# ============================================================
# CLI 入口
# ============================================================

if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1:
        cmd = sys.argv[1]

        if cmd == "unit":
            # 只跑单元测试
            test_state_machine()
            test_dependency_blocking()
            test_plan_parser()

        elif cmd == "api":
            # 测试 API 连通性
            test_single_agent_call()

        elif cmd == "e2e":
            # 端到端测试
            scenario = sys.argv[2] if len(sys.argv) > 2 else "easy"
            model = sys.argv[3] if len(sys.argv) > 3 else "glm-5.1"
            auto = "--auto" in sys.argv
            run_e2e_test(scenario, model=model, auto_approve=auto)

        elif cmd == "custom":
            # 自定义测试
            goal = sys.argv[2] if len(sys.argv) > 2 else "写一个 hello world"
            model = sys.argv[3] if len(sys.argv) > 3 else "glm-5.1"
            run_e2e_test(
                custom_goal=goal,
                model=model,
                auto_approve="--auto" in sys.argv,
                custom_context="",
            )

        elif cmd == "all":
            model = sys.argv[2] if len(sys.argv) > 2 else "glm-5.1"
            run_all_tests(include_api=True, include_e2e=True, model=model)

        else:
            print(__doc__)

    else:
        print("""
用法：
  python validator.py unit          # 只跑单元测试（不需要 API Key）
  python validator.py api            # 测试 API 连通性
  python validator.py e2e [场景] [模型]  # 端到端测试
                                    # 场景: easy / medium / hard
                                    # 加 --auto 跳过 reviewer
  python validator.py custom "目标" [模型]  # 自定义目标测试
  python validator.py all [模型]     # 全量测试

示例：
  python validator.py unit
  python validator.py e2e easy glm-5.1
  python validator.py e2e medium glm-5.1 --auto
  python validator.py custom "写一个排序算法" glm-5.1
  python validator.py all glm-5.1
        """)
