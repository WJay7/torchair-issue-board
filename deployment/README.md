# 免费部署方案

当前采用以下结构：

```text
GitHub Pages     静态托管前端
Supabase         保存值班表、人员账号、Issue 和看板快照
GitHub Actions   定时抓取 GitCode 并执行自动分配
```

## 重要说明

本地版本仍然使用 FastAPI + SQLite，方便继续开发和回退。在线版本不能把
GitCode Token 放进前端，也不能给匿名访客开放值班表写权限。

上线前需要完成两个迁移步骤：

1. 在 Supabase SQL Editor 执行 `supabase/schema.sql`。
2. 将后端同步逻辑拆成 GitHub Actions 可执行的同步任务，并将结果写入
   `dashboard_snapshots`。

值班管理页还需要接入 Supabase Auth。否则 GitHub Pages 是公开网页，任何人
   都可以伪造请求修改排班表。

## GitHub Secrets

同步任务完成后，在仓库的 Settings -> Secrets and variables -> Actions 中配置：

- `GITCODE_TOKEN`
- `SUPABASE_URL`
- `SUPABASE_SERVICE_ROLE_KEY`

其中 `SUPABASE_SERVICE_ROLE_KEY` 只能用于 GitHub Actions，不能写入前端代码。

