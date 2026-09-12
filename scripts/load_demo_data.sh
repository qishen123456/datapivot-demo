#!/usr/bin/env bash
# ============================================================
# DataPulse 脉策智能 演示版 —— 脱敏数据导入脚本
# ============================================================
# 作用：把 exports_mock/smartask_database_dump.sql（脱敏模拟数据）
#       导入到已启动的 postgres 容器中，供问数演示使用。
#
# 用法：
#   ./scripts/load_demo_data.sh
#
# 数据库名/用户名会自动从项目根目录的 .env 读取
# （SMARTASK_DB_DATABASE / SMARTASK_DB_USERNAME），
# 未配置时回落到 smartask_db / smartask_user。
#
# 说明：
#   1) 脚本会先重建 public schema，因此可重复执行（幂等）。
#   2) dump 由 pg_dump 16.15 生成，含 \restrict / \unrestrict 安全标记，
#      旧版 psql 不识别，导入前会自动过滤掉这两行。
#   3) 导入的是一套【虚构的脱敏数据】（占位品牌「DataPulse 脉策智能」），
#      与真实业务数据无关，可安全用于对外演示。
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"
DUMP_FILE="$ROOT_DIR/exports_mock/smartask_database_dump.sql"
ENV_FILE="$ROOT_DIR/.env"
CONTAINER="smartask-postgres"

# ---- 从 .env 读取数据库配置（不 source，逐行安全提取）----
read_env() {
  local key="$1" default="$2"
  if [[ -f "$ENV_FILE" ]]; then
    local val
    val="$(grep -E "^${key}=" "$ENV_FILE" | tail -1 | cut -d= -f2- | tr -d '\r' | sed 's/^["'"'"']//; s/["'"'"']$//')"
    [[ -n "$val" ]] && { echo "$val"; return; }
  fi
  echo "$default"
}

DB_NAME="$(read_env SMARTASK_DB_DATABASE smartask_db)"
DB_USER="$(read_env SMARTASK_DB_USERNAME smartask_user)"

if [[ ! -f "$DUMP_FILE" ]]; then
  echo "[ERROR] 未找到数据文件：$DUMP_FILE" >&2
  exit 1
fi

echo "==> 目标：容器=$CONTAINER  库=$DB_NAME  用户=$DB_USER"

if ! docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  echo "[ERROR] 容器 $CONTAINER 未运行，请先执行：docker compose up -d" >&2
  exit 1
fi

echo "==> 重建 public schema（清空既有数据）"
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
  -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;"

echo "==> 导入脱敏数据：$DUMP_FILE"
# 过滤 pg_dump 16.15 的 \restrict / \unrestrict 标记行，兼容旧版 psql
grep -v -E '^\\(un)?restrict ' "$DUMP_FILE" \
  | docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" -v ON_ERROR_STOP=1

echo "==> 导入完成，当前表清单："
docker exec -i "$CONTAINER" psql -U "$DB_USER" -d "$DB_NAME" \
  -c "\dt" | head -30

echo ""
echo "✔ 脱敏数据已就绪，可以开始问数演示。"
