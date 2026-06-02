"""
完整演示 —— Dynamic Workflows + Agent Teams 级别的多 Agent 编排。

演示场景：数据基座项目
  - Lead 规划：拆成 3 个子任务
  - 3 个 builder 并行执行
  - Reviewer 验收
  - 对抗验证
  - 动态 replan（如果发现问题）
"""

import sys
import os
import time
import json
from datetime import datetime

# 确保能 import 同目录的模块
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from team_engine import TeamEngine
from dynamic_replan import DynamicReplanner, AdversarialVerifier
from message_bus import MessageBus, Message
from agents import PLANNER, BUILDER, REVIEWER


def demo_agent_teams():
    """演示 Agent Teams 级别的并行编排"""
    
    print("=" * 60)
    print("🚀 多 Agent 并行编排演示")
    print(f"   时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)
    
    # ========== 1. TeamCreate ==========
    engine = TeamEngine(
        team_name="data-base-demo",
        max_parallel=3,        # 3 个 builder 并行
        model="glm-5.1",
        auto_approve=True,     # 跳过 reviewer 加速演示
        verbose=True,
    )
    engine.create_team(description="数据基座概念验证团队")
    
    # ========== 2. 手动创建任务（不用 planner，节省 API 调用） ==========
    t1 = engine.create_task(
        subject="设计数据基座的分层架构",
        description="设计一个教育数据基座的分层架构：数据采集层、数据治理层、数据服务层。每层列出核心功能模块和关键接口。",
        priority=1,
    )
    
    t2 = engine.create_task(
        subject="列出数据采集模块的技术选型",
        description="针对教育场景，列出数据采集层的技术选型：ETL工具、数据源接入方式、实时vs批量方案。要求对比至少2种方案的优缺点。",
        priority=2,
    )
    
    t3 = engine.create_task(
        subject="设计数据质量检查规则",
        description="设计一套数据质量检查规则：完整性、准确性、一致性、时效性四个维度。每个维度列出3-5条具体规则。",
        priority=2,
    )
    
    # ========== 3. Spawn Agents ==========
    engine.spawn_agent("architect", BUILDER)
    engine.spawn_agent("collector", BUILDER)
    engine.spawn_agent("qa-engineer", BUILDER)
    
    # ========== 4. 并行执行 ==========
    print("\n" + "=" * 60)
    print("🔨 并行执行阶段")
    print("=" * 60)
    
    result = engine.run(goal="", context="")  # 任务已手动创建，不需要 planner
    
    # ========== 5. 输出结果 ==========
    print("\n" + "=" * 60)
    print("📊 执行结果")
    print("=" * 60)
    
    print(f"\n状态: {result['status']}")
    print(f"完成: {result['completed']}/{result['total']}")
    print(f"失败: {result['failed']}")
    print(f"耗时: {result['duration_s']}s")
    
    print("\n📋 任务详情:")
    for t in result['tasks']:
        icon = "✅" if t['status'] == 'completed' else "❌"
        print(f"  {icon} {t['subject'][:50]} (执行者: {t['owner']})")
    
    if result['lead_messages']:
        print("\n📩 Lead 收到的消息:")
        for m in result['lead_messages']:
            print(f"  [{m['from']}] {m['subject']}: {m['body'][:80]}")
    
    if result['final_output']:
        print("\n📄 最终输出:")
        print("-" * 40)
        print(result['final_output'][:1500])
        if len(result['final_output']) > 1500:
            print(f"\n... (共 {len(result['final_output'])} 字符)")
    
    # ========== 6. 对抗验证 ==========
    print("\n" + "=" * 60)
    print("⚔️ 对抗验证")
    print("=" * 60)
    
    verifier = AdversarialVerifier(model="glm-5.1")
    
    # 对第一个完成的任务做对抗验证
    tasks = engine._load_tasks()
    completed = [t for t in tasks if t.status == "completed" and t.result]
    
    if completed:
        sample = completed[0]
        verification = verifier.verify(
            task_subject=sample.subject,
            task_desc=sample.description,
            result=sample.result,
        )
        print(f"\n验证结果: {'✅ 通过' if verification['passed'] else '⚠️ 未通过'}")
        print(f"严重度: {verification['severity']}")
        if verification['issues']:
            print(f"问题: {verification['issues'][:200]}")
    
    # ========== 7. 清理 ==========
    engine.delete_team()
    
    return result


def demo_dynamic_replan():
    """演示动态重规划"""
    
    print("\n\n" + "=" * 60)
    print("🔄 动态重规划演示")
    print("=" * 60)
    
    replanner = DynamicReplanner(model="glm-5.1")
    
    # 模拟一个有问题的任务结果
    problematic_task = {
        "subject": "设计数据库 schema",
        "description": "设计教育数据基座的数据库表结构",
        "result": "CREATE TABLE students (id INT, name VARCHAR(50));",  # 明显不完整
    }
    
    goal = "设计一个完整的教育数据基座系统"
    all_tasks = [
        {"id": "t1", "subject": "设计数据库 schema", "status": "completed"},
        {"id": "t2", "subject": "编写 ETL 脚本", "status": "pending"},
        {"id": "t3", "subject": "设计 API 接口", "status": "pending"},
    ]
    
    print("\n检查任务结果...")
    needs_replan, actions = replanner.check_and_replan(
        completed_task=problematic_task,
        goal=goal,
        context="",
        all_tasks=all_tasks,
    )
    
    if needs_replan:
        print(f"\n需要重规划! 生成了 {len(actions)} 个调整:")
        for a in actions:
            print(f"  {a.action.upper()} {a.task_id}: {a.subject[:40]}")
            print(f"    原因: {a.reason[:60]}")
    else:
        print("\n结果没问题，无需调整。")
    
    return actions


def demo_message_bus():
    """演示消息总线"""
    
    print("\n\n" + "=" * 60)
    print("💬 消息总线演示")
    print("=" * 60)
    
    bus = MessageBus(base_dir=".orchestry/demo-messages")
    
    # Direct message
    bus.send(Message.create(
        channel="direct",
        from_agent="architect",
        to_agent="coder",
        subject="schema 已更新",
        body="students 表新增了 class_id 字段，请在 ETL 脚本里同步更新。",
    ))
    
    # Broadcast
    bus.send(Message.create(
        channel="broadcast",
        from_agent="lead",
        subject="全体注意",
        body="数据源从 MySQL 切换到 PostgreSQL，请重新检查 SQL 语法兼容性。",
    ))
    
    # Lead report
    bus.send(Message.create(
        channel="lead",
        from_agent="coder",
        subject="ETL 脚本已更新",
        body="已适配 PostgreSQL 语法，新增 class_id 字段映射。",
    ))
    
    # 读取消息
    print("\n📬 coder 的收件箱:")
    msgs = bus.read_inbox("coder")
    for m in msgs:
        print(f"  [{m.channel}] {m.from_agent}: {m.subject}")
    
    print("\n📬 lead 的收件箱:")
    msgs = bus.read_inbox("lead")
    for m in msgs:
        print(f"  [{m.channel}] {m.from_agent}: {m.subject}")
    
    # 清理
    import shutil
    shutil.rmtree(".orchestry/demo-messages", ignore_errors=True)
    
    print("\n✅ 消息总线工作正常")


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "all"
    
    if mode in ("all", "messages"):
        demo_message_bus()
    
    if mode in ("all", "replan"):
        demo_dynamic_replan()
    
    if mode in ("all", "team"):
        demo_agent_teams()
    
    if mode == "unit":
        # 快速单元测试
        print("🧪 单元测试")
        demo_message_bus()
        print("\n✅ 所有测试通过")
