"""Deterministic payload generator for the syyb briefing.

This is the Phase-0 fallback when the configured LLM is slow/unavailable.
It uses the known structure in docs/提示词和数据.md and still produces the same
Bookshelf payload shape as DatasetCopilot.generate().
"""

from __future__ import annotations

from typing import Any, Dict, List


AGENT1_PROMPT = """
你是 Agent1（语义路由、上下文指代消解与口径澄清）。

任务：识别用户问题对应的数据集、统计主体、统计层级和必要的澄清动作。

硬性规则：
1. 围绕 datapivot_core_data（2026年）语义做判断；涉及当前年/最新年/本年统一按 2026。
2. 必须读取最近对话上下文：用户问“那沧澜呢”“淼澜也看一下”“两个相比呢”等省略表达时，沿用上一轮的数据集、维度和分析口径，只替换新主体。
3. 当问题包含“战区/片区/行业部/客户经理/线”且可能产生统计口径歧义，先判断是否可由上下文消解；不可消解时触发确认。
4. 多数据集候选接近时，必须返回 confirmation_question 与 2-4 个 options，每个 option 需要包含 dataset_id、label、scope_filter。
5. 置信度高且上下文明确时不要打断用户，不要为了保险而反复确认。
6. 单体组织分析要识别“管理链路”：事业群 -> 战区/行业部 -> 片区 -> 客户经理。用户问某战区/片区/行业部“怎么样”时，应让下游返回命中节点及全部下级节点，方便报告下钻。
7. 统计上级层级时，必须提醒下游“不含下级明细行”的层级隔离口径，同时保留下级节点用于展开分析。
8. 输出偏好：若样本命中高，优先 direct_execute，否则 generate_sql。
""".strip()


AGENT2_PROMPT = """
你是 Agent2（SQL生成专家），专门处理飞书多维表格落库到 PostgreSQL 的 JSONB 数据。
只允许输出只读 SQL（SELECT/WITH/SHOW），禁止增删改。

固定上下文：
1. 当前数据库：{database_name}（PostgreSQL）。
2. 仅使用 datapivot_core_data 表（字段 fields 为 JSONB）。
3. 年份口径固定：2026。

必须遵守：
1. 统一 CTE：WITH raw_data/字段提取 -> flattened_tree/层级树 -> summarized_nodes/汇总节点。单体组织分析优先使用 WITH RECURSIVE 递归下钻。
2. JSONB 字段必须使用 jsonb_typeof 兼容数组/文本。
3. 金额字段必须使用 regexp_replace(..., '[^0-9.-]', '', 'g') 清理后转 NUMERIC。
4. WHERE 必须包含 当前年 = '2026'；如果源数据当前年为空，可按 2026 兜底。
5. 层级隔离和去重：
   - 第一层必须按 战区、片区、客户经理、行业部 GROUP BY 后再汇总，避免源表重复行导致金额翻倍。
   - 片区统计：片区<>'' AND (客户经理 IS NULL OR 客户经理='')。
   - 战区/行业部统计：(片区 IS NULL OR 片区='') AND (客户经理 IS NULL OR 客户经理='')。
   - 客户经理统计：客户经理<>''。
6. 涉及多个主体对比时，必须保留 线、层级、节点名称、上级名称，禁止把多个主体合成一行。
7. 追问场景应沿用上轮口径；如 scope_filter 已由确认流程给出，必须写入 WHERE。
8. 单体组织分析（如“某战区/某片区业绩怎么样”）必须返回完整管理链路：命中节点 + 子节点 + 孙级明细节点。必须基于汇总结果使用 WITH RECURSIVE 命中链路，按 子节点.上级名称 = 父节点.节点名称 下钻，不能只写“节点名称=主体 OR 上级名称=主体”导致只返回直接下级。
9. 只输出 SQL 正文，不要解释、不要 Markdown。
""".strip()


AGENT3_PROMPT = """
你是 Agent3（SQL复核官）。你要对 Agent2 SQL 进行口径、安全、可执行性复核，并在必要时修正。

复核清单：
1. 只读安全，仅 SELECT/WITH/SHOW。
2. 仅使用 datapivot_core_data。
3. JSONB 提取是否使用 jsonb_typeof + ->> 兼容数组/文本。
4. 金额是否使用 regexp_replace 清洗。
5. 是否包含 当前年='2026'。
6. 层级隔离是否正确，上级不含下级明细，且 raw_data 已按组织字段从源头去重。
7. 达成率、剩余任务金额计算是否正确且避免除零。
8. 多主体对比是否保留主体维度。
9. 单体组织分析是否使用递归链路返回全量下级，不允许只返回直接下级。
10. 是否具备 LIMIT。

若发现问题，直接返回修正后的 final_sql。
""".strip()


AGENT4_PROMPT = """
你是 Agent4（业务解读官），面向商用事业群管理层输出结论。

要求：
1. 先给结论：目标达成、风险层级、优先动作。
2. 必须基于查询结果，不编造数据。
3. 分层说明：事业群 -> 线 -> 战区/行业部 -> 片区 -> 客户经理；如果结果包含多层级，必须说明每层最高/最低风险节点。
4. 追问场景必须读取上一轮分析摘要，沿用上一轮的口径与节点选择，只分析用户新增或替换的主体。
5. 涉及对比时，必须明确对比对象、达成率差距、剩余任务差距。
6. 禁止重复复读同一句结论；按“核心结论 -> 亮点 -> 风险 -> 建议”输出，给出 2-3 条可执行动作建议。
""".strip()


BASE_SQL = """
WITH raw_data AS (
    SELECT
        TRIM(COALESCE(CASE WHEN jsonb_typeof(fields->'战区') = 'array' THEN fields->'战区'->0->>'text' ELSE fields->>'战区' END, '')) AS 战区,
        TRIM(COALESCE(CASE WHEN jsonb_typeof(fields->'片区') = 'array' THEN fields->'片区'->0->>'text' ELSE fields->>'片区' END, '')) AS 片区,
        TRIM(COALESCE(CASE WHEN jsonb_typeof(fields->'客户经理') = 'array' THEN fields->'客户经理'->0->>'text' ELSE fields->>'客户经理' END, '')) AS 客户经理,
        TRIM(COALESCE(CASE WHEN jsonb_typeof(fields->'行业部') = 'array' THEN fields->'行业部'->0->>'text' ELSE fields->>'行业部' END, '')) AS 行业部,
        SUM(COALESCE(NULLIF(regexp_replace(COALESCE(CASE WHEN jsonb_typeof(fields->'总任务（金额）') = 'array' THEN fields->'总任务（金额）'->0->>'text' ELSE fields->>'总任务（金额）' END, '0'), '[^0-9.-]', '', 'g'), ''), '0')::NUMERIC) AS 总任务金额,
        SUM(COALESCE(NULLIF(regexp_replace(COALESCE(CASE WHEN jsonb_typeof(fields->'年度开单金额') = 'array' THEN fields->'年度开单金额'->0->>'text' ELSE fields->>'年度开单金额' END, '0'), '[^0-9.-]', '', 'g'), ''), '0')::NUMERIC) AS 年度开单金额
    FROM datapivot_core_data
    WHERE COALESCE(NULLIF(TRIM(CASE WHEN jsonb_typeof(fields->'当前年') = 'array' THEN fields->'当前年'->0->>'text' ELSE fields->>'当前年' END), ''), '2026') = '2026'
    GROUP BY 1, 2, 3, 4
),
flattened_tree AS (
    SELECT
        CASE
            WHEN 客户经理 <> '' THEN '客户经理'
            WHEN 片区 <> '' THEN '片区'
            WHEN 战区 <> '' AND 战区 LIKE '%行业部' THEN '行业部'
            WHEN 行业部 <> '' THEN '行业部'
            WHEN 战区 <> '' THEN '战区'
            ELSE '事业群'
        END AS 层级,
        CASE
            WHEN 客户经理 <> '' THEN COALESCE(NULLIF(片区, ''), NULLIF(行业部, ''), NULLIF(战区, ''), '商用事业群')
            WHEN 片区 <> '' THEN NULLIF(战区, '')
            WHEN 战区 <> '' OR 行业部 <> '' THEN '商用事业群'
            ELSE NULL
        END AS 上级名称,
        CASE
            WHEN 客户经理 <> '' THEN 客户经理
            WHEN 片区 <> '' THEN 片区
            WHEN 战区 <> '' THEN 战区
            WHEN 行业部 <> '' THEN 行业部
            ELSE '商用事业群'
        END AS 节点名称,
        CASE
            WHEN COALESCE(NULLIF(战区, ''), NULLIF(行业部, '')) LIKE '%行业部' THEN '行业线'
            WHEN COALESCE(NULLIF(战区, ''), NULLIF(行业部, '')) LIKE '%战区' THEN '区域线'
            ELSE '事业群层级'
        END AS 线,
        '商用事业群' AS 事业群,
        战区,
        片区,
        行业部,
        客户经理,
        总任务金额,
        年度开单金额
    FROM raw_data
),
summarized_nodes AS (
    SELECT
        线,
        层级,
        上级名称,
        节点名称,
        MAX(事业群) AS 事业群,
        MAX(战区) AS 战区,
        MAX(片区) AS 片区,
        MAX(行业部) AS 行业部,
        MAX(客户经理) AS 客户经理,
        SUM(总任务金额) AS 总任务金额,
        SUM(年度开单金额) AS 年度开单金额
    FROM flattened_tree
    WHERE 节点名称 <> ''
    GROUP BY 线, 层级, 上级名称, 节点名称
)
SELECT
    线,
    层级,
    节点名称,
    上级名称,
    事业群,
    战区,
    片区,
    行业部,
    客户经理,
    总任务金额,
    年度开单金额,
    CASE WHEN 总任务金额 = 0 THEN 0 ELSE ROUND((年度开单金额 / 总任务金额) * 100, 2) END AS 达成率,
    ROUND(总任务金额 - 年度开单金额, 2) AS 剩余任务金额
FROM summarized_nodes
""".strip()


def _sql_with_filter(where_clause: str, order_by: str = "线 DESC, 层级 DESC, 上级名称, 节点名称", limit: int = 10000) -> str:
    return f"""
WITH 汇总结果 AS (
{BASE_SQL}
)
SELECT *
FROM 汇总结果
WHERE {where_clause}
ORDER BY {order_by}
LIMIT {limit};
""".strip()


def _sql_with_descendants(anchor_clause: str) -> str:
    return f"""
WITH RECURSIVE 汇总结果 AS (
{BASE_SQL}
),
命中链路 AS (
    SELECT *
    FROM 汇总结果
    WHERE {anchor_clause}
    UNION ALL
    SELECT 子节点.*
    FROM 汇总结果 子节点
    JOIN 命中链路 父节点
      ON 子节点.上级名称 = 父节点.节点名称
)
SELECT *
FROM 命中链路
ORDER BY 线 DESC,
  CASE 层级
    WHEN '战区' THEN 1
    WHEN '片区' THEN 2
    WHEN '客户经理' THEN 3
    WHEN '行业部' THEN 1
    ELSE 9
  END,
  上级名称,
  节点名称
LIMIT 10000;
""".strip()


def build_syyb_payload(doc_text: str, dataset_meta: Dict[str, Any]) -> Dict[str, Any]:
    lld = f"""
# 商用事业群智能问数 LLD

## 业务范围
星澜商用事业群 2026 年销售任务与年度开单分析。数据来自飞书多维表格落库表 `datapivot_core_data`，业务字段存放在 `fields` JSONB 中。

## 组织链路
- 区域链路：商用事业群 -> 战区 -> 片区 -> 客户经理。
- 行业链路：商用事业群 -> 食饮行业部/工业健康行业部/楼宇办公行业部 -> 客户经理。

## 指标
- 总任务金额：`fields->'总任务（金额）'` 清洗后转 NUMERIC。
- 年度开单金额：`fields->'年度开单金额'` 清洗后转 NUMERIC。
- 达成率：年度开单金额 / 总任务金额 * 100。
- 剩余任务金额：总任务金额 - 年度开单金额。

## 红线规则
1. 年份固定为 2026。
2. 统计片区时必须排除客户经理明细行。
3. 统计战区/行业部时必须排除片区与客户经理明细行。
4. 多主体对比不得合并主体。
5. 所有结论必须基于查询结果，禁止编造。

## 对话上下文和歧义确认
- 追问必须沿用上一轮数据集、主体、层级和过滤条件。
- 多数据集候选接近或实体名歧义时，必须触发智能确认。

## 底稿摘要
{doc_text[:2000]}
""".strip()

    fields = [
        ("id", None, "记录ID", "integer", "主键"),
        ("fields", None, "飞书字段JSON", "jsonb", "飞书多维表格原始字段"),
        ("战区", "战区", "战区/行业部", "text", "jsonb_typeof 兼容数组/文本"),
        ("片区", "片区", "片区", "text", "jsonb_typeof 兼容数组/文本"),
        ("客户经理", "客户经理", "客户经理", "text", "jsonb_typeof 兼容数组/文本"),
        ("当前年", "当前年", "年份", "text", "固定过滤 2026"),
        ("总任务（金额）", "总任务（金额）", "总任务金额", "numeric", "regexp_replace 清洗非数字字符"),
        ("年度开单金额", "年度开单金额", "年度开单金额", "numeric", "regexp_replace 清洗非数字字符"),
        ("线", None, "线", "text", "战区 LIKE '%战区' 为区域线；LIKE '%行业部' 为行业线"),
        ("层级", None, "层级", "text", "事业群/战区/片区/行业部/客户经理"),
        ("节点名称", None, "节点名称", "text", "当前统计节点"),
        ("上级名称", None, "上级名称", "text", "当前统计节点父级"),
        ("达成率", None, "达成率", "numeric", "开单金额/任务金额*100"),
        ("剩余任务金额", None, "剩余任务金额", "numeric", "任务金额-开单金额"),
    ]

    golden_sql = [
        ("aggregation", "商用事业群整体业绩怎么样？", f"{BASE_SQL}\nORDER BY 线 DESC, 层级 DESC, 上级名称, 节点名称\nLIMIT 10000;", ["整体", "全维度"]),
        ("single_entity", "沧澜战区业绩怎么样？", _sql_with_descendants("节点名称 = '沧澜战区'"), ["战区", "沧澜", "下钻"]),
        ("single_entity", "淮岸片区业绩怎么样？", _sql_with_descendants("节点名称 = '淮岸片区'"), ["片区", "淮岸", "下钻"]),
        ("comparative", "沧澜战区和淼澜战区哪个完成得更好？", _sql_with_filter("节点名称 IN ('沧澜战区','淼澜战区') OR 上级名称 IN ('沧澜战区','淼澜战区')"), ["对比", "战区"]),
        ("topn", "行业线 Top5 客户经理是谁？", _sql_with_filter("线 = '行业线' AND 层级 = '客户经理'", "年度开单金额 DESC", 5), ["行业", "TopN"]),
        ("risk", "达成率低于10%的单元有哪些？", _sql_with_filter("达成率 < 10", "达成率 ASC", 100), ["风险", "低达成"]),
    ]

    return {
        "synonyms": [
            {"synonym": "商用事业群", "normalized_synonym": "商用事业群", "weight": 10},
            {"synonym": "syyb", "normalized_synonym": "syyb", "weight": 8},
            {"synonym": "星澜商用", "normalized_synonym": "星澜商用", "weight": 8},
            {"synonym": "业绩", "normalized_synonym": "业绩", "weight": 4},
        ],
        "lld_documents": [{"version": 1, "title": "商用事业群 2026 销售业绩 LLD", "content": lld, "redline_rules": ["年份固定2026", "层级隔离", "多主体保留主体维度", "禁止编造"], "is_active": True}],
        "schema_definition": [{"table_name": "datapivot_core_data", "ddl_sql": "CREATE TABLE datapivot_core_data (id BIGSERIAL PRIMARY KEY, fields JSONB NOT NULL, created_at TIMESTAMP DEFAULT NOW(), updated_at TIMESTAMP DEFAULT NOW());", "description": "飞书多维表格商用事业群 2026 销售业绩数据"}],
        "data_dictionary": [{"table_name": "datapivot_core_data", "column_name": c, "jsonb_key": k, "semantic_name": s, "data_type": t, "enum_mapping": {}, "extraction_rule": r, "is_active": True} for c, k, s, t, r in fields],
        "table_relations": [],
        "golden_sql_samples": [{"intent_type": i, "question": q, "sql_text": sql, "tags": tags, "quality_score": 95 if idx == 0 else 90} for idx, (i, q, sql, tags) in enumerate(golden_sql)],
        "agent_prompts": [
            {"agent_no": 1, "prompt_content": AGENT1_PROMPT},
            {"agent_no": 2, "prompt_content": AGENT2_PROMPT},
            {"agent_no": 3, "prompt_content": AGENT3_PROMPT},
            {"agent_no": 4, "prompt_content": AGENT4_PROMPT},
        ],
        "common_questions": [
            {"question_text": "沧澜战区业绩怎么样？", "intent_hint": "single_entity", "sort_order": 1},
            {"question_text": "淮岸片区业绩怎么样？", "intent_hint": "single_entity", "sort_order": 2},
            {"question_text": "沧澜战区和淼澜战区哪个完成得更好？", "intent_hint": "comparative", "sort_order": 3},
            {"question_text": "行业线 Top5 客户经理是谁？", "intent_hint": "topn", "sort_order": 4},
            {"question_text": "达成率低于10%的单元有哪些？", "intent_hint": "risk", "sort_order": 5},
            {"question_text": "商用事业群整体业绩怎么样？", "intent_hint": "aggregation", "sort_order": 6},
        ],
        "regression_cases": [
            {"question_text": "沧澜战区业绩怎么样？", "expected_intent": "single_entity", "expected_sql_keywords": ["沧澜战区", "层级", "达成率"], "sort_order": 1},
            {"question_text": "那淼澜呢？", "expected_intent": "context_followup", "expected_sql_keywords": ["淼澜战区"], "sort_order": 2},
            {"question_text": "沧澜战区和淼澜战区哪个完成得更好？", "expected_intent": "comparative", "expected_sql_keywords": ["IN", "沧澜战区", "淼澜战区"], "sort_order": 3},
            {"question_text": "淮岸片区业绩怎么样？", "expected_intent": "single_entity", "expected_sql_keywords": ["淮岸片区", "客户经理"], "sort_order": 4},
        ],
        "external_configs": [],
        "report_config": {
            "nameColumn": "节点名称",
            "parentColumn": "上级名称",
            "trackColumn": "线",
            "levelColumn": "层级",
            "businessContext": "商用事业群 2026 年经营分析。源数据来自 datapivot_core_data.fields JSONB，组织层级和父子关系由 SQL 投影生成，而不是源表物理列。",
            "sourceFields": {
                "organization": ["战区", "片区", "客户经理"],
                "time": ["当前年"],
                "metrics": ["总任务（金额）", "年度开单金额"],
            },
            "sqlOutputContract": {
                "requiredColumns": ["线", "层级", "节点名称", "上级名称"],
                "metricColumns": ["总任务金额", "年度开单金额", "达成率", "剩余任务金额"],
                "notes": [
                    "源表没有 节点名称/上级名称/层级/线 时，必须在 SQL 中用 SELECT 别名生成这些标准列。",
                    "区域链路按 商用事业群 -> 战区 -> 片区 -> 客户经理 输出。",
                    "行业链路按 商用事业群 -> 行业部 -> 客户经理 输出。",
                    "统计上级节点时必须做层级隔离，不能把下级明细行重复累加到上级汇总行。",
                    "如用户查询某个战区，应同时返回该战区、其片区、以及片区下客户经理，方便前端动态下钻。",
                ],
            },
            "analysisDimensions": [
                {
                    "key": "regional_chain",
                    "label": "区域管理链条",
                    "path": ["商用事业群", "战区", "片区", "客户经理"],
                    "sourceFields": ["战区", "片区", "客户经理"],
                    "trackValue": "区域线",
                    "purpose": "分析各区域市场覆盖深度、战区/片区任务完成、客户经理风险和优秀样本。",
                },
                {
                    "key": "industry_chain",
                    "label": "行业管理链条",
                    "path": ["商用事业群", "行业部", "客户经理"],
                    "sourceFields": ["战区", "客户经理"],
                    "trackValue": "行业线",
                    "purpose": "分析食饮、工业健康、楼宇办公等行业线专业产出和个人产能。",
                },
            ],
            "metrics": [
                {"key": "task", "label": "总任务金额", "column": "总任务金额", "format": "amount"},
                {"key": "actual", "label": "年度开单金额", "column": "年度开单金额", "format": "amount"},
                {"key": "rate", "label": "达成率", "column": "达成率", "format": "percent"},
                {"key": "remain", "label": "剩余任务金额", "column": "剩余任务金额", "format": "amount"},
            ],
            "levels": [
                {"name": "机构层", "values": ["片区", "战区", "行业部"]},
                {"name": "个人层", "values": ["客户经理", "业务员", "业务"]},
            ],
            "trackValues": {"org": "区域线", "personal": "行业线"},
                "riskThreshold": 10,
                "officeRiskThreshold": 10,
                "officeBenchmarkThreshold": 15,
                "personRiskThreshold": 10,
                "personBenchmarkThreshold": 20,
                "signalRules": [
                    {"key": "rate", "op": ">=", "value": 15, "tone": "good", "label": "标杆"},
                    {"key": "rate", "op": ">=", "value": 10, "tone": "warn", "label": "中等"},
                    {"key": "rate", "op": "<", "value": 10, "tone": "danger", "label": "风险"},
                ],
            "sections": ["core", "group", "risk", "strategy"],
            "reportTitle": "经营分析报告",
            "agentReportGuidance": "报告结构由 SQL 标准列和动态树决定。战区场景先横向比较战区，再纵向下钻直接下级片区；客户经理只作为片区后的证据层，不直接替代片区管理判断。Agent4 不维护组织树，只基于指标、风险节点、优秀节点和 analysisDimensions 输出洞察、风险解释和建议。",
        },
    }
