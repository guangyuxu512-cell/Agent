继续改造，完成以下内容：

1. 新增 worker_agent.py 独立脚本
   - 启动时注册、后台心跳线程（30秒）、启动 Celery Worker
   - 配置通过环境变量读取：SERVER_URL、MACHINE_ID、RPA_KEY

2. 新增任务派发查询接口
   - GET /api/task-dispatches（支持 machine_id、status 过滤）
   - GET /api/task-dispatches/{dispatch_id}

3. 新增一个 echo_test 任务，用于端到端验证整条链路

请按顺序实施。