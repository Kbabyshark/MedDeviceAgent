# 部署文档

## 1. 环境要求

| 组件 | 版本要求 |
|------|---------|
| Python | 3.11 |
| MySQL | 8.0 |
| Redis | 7.x |
| Qdrant | latest |
| Docker | 24+ |
| Docker Compose | 2.x |

## 2. 快速启动（开发环境）

### 2.1 配置

```bash
# 复制环境变量模板
cp .env.example .env

# 编辑 .env，填入实际值（至少修改以下项）
# DEEPSEEK_API_KEY=sk-xxx
# JWT_SECRET_KEY=<随机字符串>
# MYSQL_PASSWORD=<数据库密码>
```

### 2.2 安装依赖

```bash
# 使用 uv（推荐）
uv pip install -e ".[dev]"

# 或使用 pip
pip install -e ".[dev]"
```

### 2.3 启动服务

```bash
# 方式 1: Docker Compose 一键启动全部服务
docker compose up -d

# 方式 2: 仅启动 FastAPI（需要自行启动 MySQL/Redis/Qdrant）
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### 2.4 数据库初始化

```bash
# 运行 Migration 创建表
alembic upgrade head

# 查看 Migration 状态
alembic current
```

### 2.5 验证

```bash
# 健康检查
curl http://localhost:8000/api/health

# 系统状态（含性能指标 + 告警）
curl http://localhost:8000/api/status
```

## 3. 生产部署

### 3.1 生产配置 Checklist

- [ ] `.env` 中 `APP_ENV=production`, `APP_DEBUG=false`
- [ ] `JWT_SECRET_KEY` 改为强随机字符串（≥64字符）
- [ ] `DEEPSEEK_API_KEY` 填入生产 API Key
- [ ] `MYSQL_PASSWORD` 填入生产密码
- [ ] `REDIS_PASSWORD` 填入生产密码
- [ ] MySQL 端口仅绑定 `127.0.0.1:3306`
- [ ] 前端配置 Nginx 反向代理到 `svagent-app:8000`
- [ ] 配置 HTTPS 证书（通过 Nginx 或 Cloudflare）

### 3.2 启动生产环境

```bash
# 拉取/构建镜像
docker compose -f docker-compose.prod.yml build

# 启动所有服务
docker compose -f docker-compose.prod.yml up -d

# 查看日志
docker compose -f docker-compose.prod.yml logs -f app

# 运行 Migration
docker compose -f docker-compose.prod.yml exec app alembic upgrade head
```

### 3.3 资源限制（docker-compose.prod.yml）

| 服务 | CPU Limit | Memory Limit |
|------|----------|-------------|
| app | 2 cores | 2 GB |
| mysql | - | 1 GB |
| redis | - | 512 MB |
| qdrant | - | 1 GB |
| celery-worker | 1 core | 1 GB |

### 3.4 监控

```bash
# 系统状态（P95 延迟 + 告警）
curl http://localhost:8000/api/status

# 成本分析（需 admin 权限）
curl -H "Authorization: Bearer <admin_token>" \
  http://localhost:8000/api/v1/admin/cost?days=30

# Trace 查询
curl -H "Authorization: Bearer <token>" \
  http://localhost:8000/api/v1/trace/{trace_id}
```

## 4. 回滚策略

```bash
# 回滚到上一个版本
docker compose -f docker-compose.prod.yml down
git checkout <previous_tag>
docker compose -f docker-compose.prod.yml build
docker compose -f docker-compose.prod.yml up -d

# 回滚数据库（如需要）
alembic downgrade -1
```

## 5. 备份策略

```bash
# MySQL 备份
docker exec svagent-mysql-prod mysqldump -u root -p med_device_agent > backup_$(date +%Y%m%d).sql

# 恢复
docker exec -i svagent-mysql-prod mysql -u root -p med_device_agent < backup_20260726.sql
```

## 6. 故障排查

| 问题 | 检查 |
|------|------|
| 启动报 config_missing | `.env` 中 DEEPSEEK_API_KEY / JWT_SECRET_KEY 未设置或为默认值 |
| Trace 表写入慢 | 检查 MySQL 连接池大小和索引 |
| RAG 检索无结果 | 确认知识库已上传文档且 Embedding 完成 |
| WebSocket 频繁断连 | 检查心跳间隔和网络稳定性 |
| 高并发 5xx | 增加 worker 数量、检查连接池、Redis QPS |
