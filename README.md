# 数枢 DataPivot · 智能问数系统（演示版）

> **这是一套对外演示版本。** 仓库中的业务数据全部为**虚构的脱敏模拟数据**
> （占位品牌「星澜集团」），与任何真实企业无关，可安全用于演示与评审。

基于自然语言的数据问答系统：用户用中文提问，系统自动理解意图、生成 SQL、
执行查询并用图表/结论呈现结果。

---

## 一、快速开始

### 前置要求

- Docker 20.10+ 与 Docker Compose v2
- 可用内存 ≥ 4GB

### 启动步骤

```bash
# 1. 准备环境变量（首次必须）
cp .env.example .env
#    然后编辑 .env，至少填写：
#      SMARTASK_DB_PASSWORD   —— 数据库密码（自行设定）
#      SMARTASK_AI_API_KEY    —— 大模型 API Key（问数功能必需）
#      SMARTASK_AI_BASE_URL   —— 模型服务地址
#      SMARTASK_AI_MODEL      —— 模型名称

# 2. 启动全部服务
docker compose up -d

# 3. 导入脱敏演示数据（首次必须，可重复执行）
./scripts/load_demo_data.sh

# 4. 访问系统
#    前端：http://localhost:8888
```

### 服务端口

| 服务 | 容器名 | 端口 |
|---|---|---|
| 前端 Web | `smartask-frontend` | **8888** |
| 后端 API | `smartask-backend` | 5002 |
| PostgreSQL | `smartask-postgres` | 5433（容器内 5432） |

### 演示账号

系统首次启动后，用下列账号登录（密码为演示默认密码）：

| 登录账号 | 密码 | 角色 |
|---|---|---|
| `13800000001` | `12345678` | 管理员 |
| `13800000002` | `12345678` | 普通用户 |

> 账号均为虚构号码。可在「管理后台 → 用户与权限」中新增账号或重置密码。

---

## 二、首次启动会自动完成的事

| 事项 | 说明 |
|---|---|
| 数据库建表 | `docker/postgres/init/*.sql` 在容器首次初始化时自动执行 |
| 数据集索引重建 | 若 `config/dataset_node_index.json` 缺失，后端启动时自动重建 |
| 组织树初始化 | 缺失时使用空结构（可在管理后台自行维护） |

> 也可以在系统启动后，直接在管理后台通过界面配置数据源、组织树与权限。

---

## 三、目录结构

```
.
├── backend/                # 后端服务（Flask，问数引擎 / 控制器 / 数据集）
├── frontend/               # 前端（Vue 3 + Vite）
├── docker/
│   └── postgres/init/      # 数据库初始化 SQL
├── config/                 # 运行时配置（业务配置；凭证类需自行填写）
├── exports_mock/           # ★ 脱敏后的模拟数据
│   ├── csv/                #   各表数据（CSV 形式）
│   └── smartask_database_dump.sql   # 完整数据库转储（导入脚本使用）
├── nginx/                  # 反向代理配置
├── scripts/
│   └── load_demo_data.sh   # ★ 脱敏数据导入脚本
├── docker-compose.yml      # 本地开发编排
├── docker-compose.prod.yml # 生产编排
└── .env.example            # 环境变量模板
```

---

## 四、数据说明

- 数据为**逐叶子随机扰动 + 父级按子级重算**生成的模拟数据，
  保留了"报表对得上账"的层级勾稽关系（如 事业群 = Σ战区）。
- 组织层级术语：事业群 / 战区 / 片区 / 客户经理。
- 行业线：食饮 / 楼宇办公 / 工业健康。
- 该数据集**不包含任何真实企业名称、人员姓名或经营数据**。

---

## 五、常见问题

**Q：前端打开后没有数据？**
A：确认已执行 `./scripts/load_demo_data.sh`，且容器名与 `.env` 中的数据库名一致。

**Q：问数没有结果 / 报模型错误？**
A：检查 `.env` 中的 `SMARTASK_AI_API_KEY`、`SMARTASK_AI_BASE_URL`、`SMARTASK_AI_MODEL` 是否配置正确。

**Q：想重新导入数据？**
A：直接再次执行 `./scripts/load_demo_data.sh` 即可（脚本会先重建 schema，幂等）。

**Q：如何查看日志？**
A：`docker compose logs -f backend`（或 `frontend` / `postgres`）。

**Q：如何停止？**
A：`docker compose down`；如需同时清除数据卷：`docker compose down -v`。
