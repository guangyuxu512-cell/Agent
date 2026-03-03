# Docker 部署指南

## 资源限制架构

本项目采用**双层资源限制**策略，确保工具执行安全：

### 1. 语言层限制（Python 沙箱）

由 `backend/app/图引擎/工具加载器.py` 实现，针对每个工具执行子进程：

| 平台 | 实现方式 | 限制项 |
|------|---------|--------|
| **Windows** | Job Object | 128MB 内存 / 禁止子进程 / 自动终止 |
| **Linux** | resource.setrlimit | 128MB 虚拟内存 / 禁止子进程 / 10秒 CPU |

**代码位置**：
- Windows: `_创建受限Job()` 函数
- Linux: `_linux_preexec()` 函数（通过 `subprocess.Popen(preexec_fn=...)` 调用）

### 2. OS 层限制（容器）

由 `backend/docker-compose.yml` 配置，作用于整个容器：

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'        # 最多 2 核 CPU
      memory: 1G         # 最多 1GB 内存（所有进程共享）
pids_limit: 100          # 最多 100 个进程
```

**限制范围**：主进程 + uvicorn workers + 所有工具执行子进程

---

## 部署步骤

### 1. 构建镜像

```bash
cd backend
docker-compose build
```

### 2. 启动服务

```bash
docker-compose up -d
```

### 3. 查看日志

```bash
docker-compose logs -f backend
```

---

## 验收测试

### 测试 1: 资源限制生效

```bash
# 查看内存限制（应显示 1GB = 1073741824 字节）
docker exec agent-backend cat /sys/fs/cgroup/memory/memory.limit_in_bytes

# 查看进程数限制（应显示 100）
docker exec agent-backend cat /sys/fs/cgroup/pids/pids.max

# 实时监控资源使用
docker stats agent-backend
```

**预期输出**：
```
CONTAINER        CPU %    MEM USAGE / LIMIT    MEM %    NET I/O    BLOCK I/O
agent-backend    5.2%     256MiB / 1GiB        25%      ...        ...
```

### 测试 2: pytest 全绿（跳过 Windows-only）

```bash
# 进入容器
docker exec -it agent-backend bash

# 运行沙箱安全测试
cd /app
python -m pytest tests/security/test_sandbox.py -v

# 预期结果：
# - 测试 1-6, 8-10, 正向: PASSED
# - 测试 7 (内存耗尽): PASSED（Linux rlimit 生效）
```

### 测试 3: 工具执行内存限制

在容器内测试 Python 工具执行：

```bash
docker exec -it agent-backend python -c "
from app.图引擎.工具加载器 import 执行Python工具

# 测试内存耗尽（应被 rlimit 终止）
code = '''
def execute(params):
    x = []
    for i in range(10**9):
        x.append('A' * 10**6)
    return 'done'
'''

result = 执行Python工具({'code': code}, {})
print('结果:', result)
# 预期: '错误：Python 执行进程被终止（可能超出内存限制）'
"
```

---

## 故障排查

### 问题 1: 容器启动失败

**症状**：`docker-compose up` 报错

**排查**：
```bash
# 查看详细日志
docker-compose logs backend

# 检查端口占用
netstat -tuln | grep 8001

# 检查 .env 文件
cat backend/.env
```

### 问题 2: 资源限制未生效

**症状**：`cat /sys/fs/cgroup/memory/memory.limit_in_bytes` 显示很大的值

**原因**：Docker Compose v3 的 `deploy.resources` 仅在 Swarm 模式下生效

**解决方案**：使用 Docker Compose v2 语法（已在 docker-compose.yml 中配置）

**验证**：
```bash
# 检查 Docker Compose 版本
docker-compose --version

# 如果是 v1.x，升级到 v2.x
# Ubuntu/Debian:
sudo apt-get update && sudo apt-get install docker-compose-plugin

# 使用 docker compose（注意没有连字符）
docker compose up -d
```

### 问题 3: pytest 测试失败

**症状**：测试 7 (内存耗尽) 失败

**排查**：
```bash
# 检查 rlimit 是否生效
docker exec agent-backend python -c "
import resource
print('RLIMIT_AS:', resource.getrlimit(resource.RLIMIT_AS))
print('RLIMIT_NPROC:', resource.getrlimit(resource.RLIMIT_NPROC))
"
```

**预期输出**：
```
RLIMIT_AS: (134217728, 134217728)    # 128MB
RLIMIT_NPROC: (0, 0)                 # 禁止子进程
```

---

## 生产环境建议

### 1. 调整资源限制

根据实际负载调整 `docker-compose.yml`：

```yaml
deploy:
  resources:
    limits:
      cpus: '4.0'        # 高负载场景增加 CPU
      memory: 2G         # 高并发场景增加内存
pids_limit: 200          # 高并发场景增加进程数
```

### 2. 监控告警

使用 Prometheus + Grafana 监控容器资源：

```bash
# 安装 cAdvisor
docker run -d \
  --name=cadvisor \
  --volume=/:/rootfs:ro \
  --volume=/var/run:/var/run:ro \
  --volume=/sys:/sys:ro \
  --volume=/var/lib/docker/:/var/lib/docker:ro \
  --publish=8080:8080 \
  gcr.io/cadvisor/cadvisor:latest
```

### 3. 日志轮转

配置 Docker 日志驱动：

```yaml
services:
  backend:
    logging:
      driver: "json-file"
      options:
        max-size: "10m"
        max-file: "3"
```

---

## 安全检查清单

- [ ] 容器内存限制已配置（1GB）
- [ ] 容器进程数限制已配置（100）
- [ ] 容器 CPU 限制已配置（2.0 核）
- [ ] pytest 沙箱测试全部通过
- [ ] 工具执行内存耗尽测试通过
- [ ] 资源监控已部署（docker stats）
- [ ] 日志轮转已配置
- [ ] .env 文件权限正确（600）
- [ ] 生产环境已禁用 API 文档（APP_ENV=prod）

---

## 参考资料

- [Docker Compose 资源限制](https://docs.docker.com/compose/compose-file/deploy/)
- [Linux resource.setrlimit](https://docs.python.org/3/library/resource.html)
- [cgroups 内存限制](https://www.kernel.org/doc/Documentation/cgroup-v1/memory.txt)
