"""
P0-2 回归验证: 对话链路工具查询字段
验证 获取Agent工具记录() 用 工具模型.id (而非 .名称) 查询

运行:
  cd backend
  python -c "exec(open('../tests/regression/test_p02_tool_query.py').read())"
  或:
  python -m pytest ../tests/regression/test_p02_tool_query.py -v
"""
import sys, os, json, uuid

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                os.pardir, os.pardir, "backend"))

from app.db.数据库 import 会话工厂
from app.db.模型 import 工具模型
from app.api.对话 import 获取Agent工具记录


def test_p02_query_by_id_returns_tool():
    """用工具 ID 查询必须返回该工具 (修复后行为)"""
    db = 会话工厂()
    try:
        tool = db.query(工具模型).filter(工具模型.状态 == "active").first()
        if tool is None:
            # 库里没有 active 工具, 造一条临时的
            tool = 工具模型(
                id=str(uuid.uuid4()),
                名称="p02_regression_probe",
                类型="http_api",
                描述="回归探针",
                配置=json.dumps({"url": "https://httpbin.org/get", "method": "GET"}),
                参数定义=json.dumps({}),
                状态="active",
            )
            db.add(tool)
            db.commit()
            created = True
        else:
            created = False

        # 模拟 agent 配置: tools 字段是 ID 列表
        agent_cfg = {"tools": [tool.id]}
        result = 获取Agent工具记录(db, agent_cfg)

        assert len(result) == 1, (
            f"FAIL: 用 id={tool.id} 查询返回 {len(result)} 条, 预期 1 条.\n"
            f"若返回 0 条, 说明仍在用 名称 字段匹配 UUID — P0-2 未修复."
        )
        assert result[0]["name"] == tool.名称
        print(f"PASS: 获取Agent工具记录(tools=[{tool.id}]) -> "
              f"[{{name: {result[0]['name']}}}]  (1 条)")

        if created:
            db.delete(tool)
            db.commit()
    finally:
        db.close()


def test_p02_query_by_name_must_miss():
    """用工具名称(非UUID)冒充 ID 查询必须返回空 — 确认是按 id 过滤"""
    db = 会话工厂()
    try:
        tool = db.query(工具模型).filter(工具模型.状态 == "active").first()
        if tool is None:
            print("SKIP: 无 active 工具")
            return

        # 拿名称当 ID 传 — 修复后必须匹配不到
        agent_cfg = {"tools": [tool.名称]}
        result = 获取Agent工具记录(db, agent_cfg)
        assert len(result) == 0, (
            f"FAIL: 用 name='{tool.名称}' 当作 ID 查询返回了 {len(result)} 条.\n"
            f"说明仍在用 名称 字段匹配 — P0-2 未修复."
        )
        print(f"PASS: 获取Agent工具记录(tools=['{tool.名称}']) -> [] (0 条, 符合预期)")
    finally:
        db.close()


if __name__ == "__main__":
    test_p02_query_by_id_returns_tool()
    test_p02_query_by_name_must_miss()
