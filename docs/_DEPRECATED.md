# 待删除文件清单 ⚠️ 测试通过前不执行任何 rm

> 创建时间：2026-06-17
> 配套文档：[MIGRATION_INVENTORY.md](./_MIGRATION_INVENTORY.md)
> **触发条件**：仅当 v2（book-v2）端的 pytest + E2E 全绿、且功能对等 v1 后，才执行

## A. v1（Flask + JS）— 整目录归档
```
backend/                              # 全部
frontend/                             # 全部
backend/static/                       # 旧 SPA 构建产物
frontend/dist/                        # 构建产物
```

## B. v2 占位/重复代码
```
book-v2/backend/app/api/recommend.py  # 删除 _placeholder 函数（被 v1 算法替代后）
book-v2/frontend-v2/src/api/client.ts # 用 frontend/src/api 替代（统一封装）
```

## C. 临时/调试脚本
```
_*.py                                  # 根目录所有下划线开头的临时脚本
_*.ps1
_shots/
dump.rdb
pgsql/
book-v2/pgsql/
```

## D. 文档归档（v2 实施完成后移入 docs/_archive/）
```
docs/superpowers/plans/2026-06-13-book-recommend-v2-implementation-plan.md
docs/superpowers/specs/2026-06-13-book-recommend-v2-design.md
docs/superpowers/specs/2026-06-13-ui-optimization-design.md
plan.md                               # 根目录
design.md                             # 根目录
```

## E. 删除前必须确认的检查项

- [ ] `pytest book-v2/backend/tests/` 全部通过
- [ ] 浏览器端到端测试 5 个核心场景全绿
- [ ] v1 端点调用对 v2 端点调用产生等价的响应（API 行为对比）
- [ ] 数据库迁移：MySQL 27 万册 / 38 万评分数据已成功导入 PG
- [ ] embedding 索引重建：FAISS 索引已迁移到 PG pgvector
- [ ] AI 助手端点 `/api/ai/chat` 在 v2 端响应 ≥ 95% 准确率
- [ ] 至少保留 7 天灰度运行后无重大问题
- [ ] `git log` 检查 v2 替代 v1 的所有代码 commit 已合入

## F. 删除执行命令（仅当上述全过）

```bash
# 1. 备份（防止误删）
git tag v1-deprecated-snapshot
git branch v1-archive main

# 2. 删除
git rm -r backend/ frontend/
git rm -r backend/static/ frontend/dist/
git rm -r _*.py _*.ps1 _shots/

# 3. 提交
git add -A
git commit -m "chore: 删除 v1 资产，v2 全面接管"
git push origin main --tags
```
