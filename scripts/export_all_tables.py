# -*- coding: utf-8 -*-
"""
智能问数数据库全量表导出脚本
支持导出 CSV (UTF-8 BOM), Excel (.xlsx), 以及 SQL 结构与数据
"""

import os
import sys
import datetime
import pandas as pd
from sqlalchemy import create_engine, inspect

def sanitize_dataframe_for_excel(df: pd.DataFrame) -> pd.DataFrame:
    """清理 DataFrame 中不被 Excel 原生支持的数据类型（如带时区的时间戳、复杂字典/列表等）"""
    excel_df = df.copy()
    for col in excel_df.columns:
        # 处理 datetime 时区问题
        if pd.api.types.is_datetime64_any_dtype(excel_df[col]):
            try:
                if getattr(excel_df[col].dt, 'tz', None) is not None:
                    excel_df[col] = excel_df[col].dt.tz_localize(None)
            except Exception:
                excel_df[col] = excel_df[col].astype(str)
        # 处理 object 中可能嵌套的 dict/list 或 timezone 对象
        elif excel_df[col].dtype == object:
            # 检查是否包含 datetime 对象或复杂对象
            sample = excel_df[col].dropna().iloc[0] if not excel_df[col].dropna().empty else None
            if isinstance(sample, (dict, list, set)):
                import json
                excel_df[col] = excel_df[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, (dict, list)) else x)
            elif isinstance(sample, datetime.datetime) and sample.tzinfo is not None:
                excel_df[col] = excel_df[col].apply(lambda x: x.replace(tzinfo=None) if isinstance(x, datetime.datetime) else x)
    return excel_df

def main():
    db_host = os.environ.get("SMARTASK_DB_HOST", "postgres")
    db_port = os.environ.get("SMARTASK_DB_PORT", "5432")
    db_user = os.environ.get("SMARTASK_DB_USERNAME", "postgres")
    db_password = os.environ.get("SMARTASK_POSTGRES_PASSWORD", os.environ.get("SMARTASK_DB_PASSWORD", "6670326"))
    db_name = os.environ.get("SMARTASK_DB_DATABASE", "postgres")

    conn_str = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"
    print(f"Connecting to database: {db_host}:{db_port}/{db_name} ...")
    engine = create_engine(conn_str)

    export_dir = "/app/exports"
    os.makedirs(export_dir, exist_ok=True)
    csv_dir = os.path.join(export_dir, "csv")
    os.makedirs(csv_dir, exist_ok=True)

    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    excel_path = os.path.join(export_dir, f"smartask_all_tables_{timestamp}.xlsx")

    inspector = inspect(engine)
    tables = inspector.get_table_names(schema="public")
    tables.sort()

    print(f"Found {len(tables)} tables in public schema.")

    summary_records = []

    with pd.ExcelWriter(excel_path, engine="openpyxl") as writer:
        for tbl in tables:
            print(f"Exporting table: {tbl} ...")
            df = pd.read_sql_table(tbl, engine, schema="public")
            row_count = len(df)
            col_count = len(df.columns)
            summary_records.append({
                "表名": tbl,
                "行数": row_count,
                "列数": col_count,
                "字段列表": ", ".join([str(c) for c in df.columns])
            })

            # 导出 CSV (utf-8-sig 保证 Excel 打开中文不乱码)
            csv_file = os.path.join(csv_dir, f"{tbl}.csv")
            df.to_csv(csv_file, index=False, encoding="utf-8-sig")

            # 写入 Excel Sheet（sheet 名称最多 31 字符）
            clean_df = sanitize_dataframe_for_excel(df)
            sheet_name = tbl[:31]
            clean_df.to_excel(writer, sheet_name=sheet_name, index=False)

        # 写入概览 Sheet
        summary_df = pd.DataFrame(summary_records)
        summary_df.to_excel(writer, sheet_name="数据表目录概览", index=False)

    print(f"\nExcel 汇总文件已保存至: {excel_path}")
    print(f"各表 CSV 文件已保存至: {csv_dir}")
    print(f"共导出 {len(tables)} 张表的数据。")

if __name__ == "__main__":
    main()
