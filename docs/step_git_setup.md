# Step: Git 仓库推送计划

**日期**: 2024-11-22
**目标**: 将 lightRAG/ 推送到 https://github.com/Touricks/TravelPlanner-lightRAG.git

---

## 当前状态

**检查结果**:
- lightRAG/ 本身：❌ 不是 git 仓库
- lightRAG/lightrag/：✅ 嵌套的 git 仓库（来自 HKUDS/LightRAG）
- 目录大小：~94MB

---

## 推荐方案

### ✅ 方案 A: 完整项目推送

**策略**: 将整个 lightRAG/ 初始化为新仓库

**关键步骤**:
1. 备份当前状态
2. 移除嵌套 git 仓库 (`lightrag/.git`)
3. 创建 .gitignore
4. 初始化 Git 并提交
5. 推送到 GitHub

---

## 输出文档

- **详细计划**: `lightRAG/docs/git_push_plan.md`
- **步骤记录**: 本文档

---

## 快速执行（复制粘贴）

```bash
# 1. 备份
cd /Users/carrick/gatech/cse8803MLG/Project
cp -r lightRAG lightRAG_backup

# 2. 进入目录并清理
cd lightRAG
rm -rf lightrag/.git

# 3. 创建 .gitignore
cat > .gitignore << 'EOF'
__pycache__/
*.py[cod]
.venv/
.env
.DS_Store
florida_businesses.json
rag_storage/
*.log
EOF

# 4. 初始化 Git
git init
git add .
git commit -m "Initial commit: TravelPlanner-lightRAG project"

# 5. 推送到 GitHub
git remote add origin https://github.com/Touricks/TravelPlanner-lightRAG.git
git branch -M main
git push -u origin main
```

---

**状态**: ✅ 计划已生成
**下一步**: 等待审阅后执行
