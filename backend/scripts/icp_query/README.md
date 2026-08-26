# ICP 备案反查服务部署说明

公司全称 → 官方域名 的权威映射层（工信部 ICP 备案），用于自动补全流水线的第 3 级
（映射 → A股库 → **ICP** → Bing 搜索）。服务本体为开源项目 **HG-ha/ICP_Query**（Python，内置 WebUI 与 JSON API）。

> ⚠️ 注意：该仓库未声明 LICENSE，README 注明「仅学习交流」。个人自用可行，请勿商用分发。

## 部署（推荐 Docker 一键）

1. 安装 [Docker Desktop](https://www.docker.com/products/docker-desktop/) 并启动。
2. 在本目录执行：

   ```bash
   docker compose up -d
   ```

   或直接用官方镜像：

   ```bash
   docker run -d -p 16181:16181 --name ymicp --restart unless-stopped yiminger/ymicp
   ```

3. 验证服务可用（浏览器访问 WebUI http://127.0.0.1:16181 或命令行）：

   ```bash
   curl "http://127.0.0.1:16181/query/web?search=字节跳动"
   # 期望返回 {"code":200,"params":{"list":[{"serviceName":"bytedance.com",...}]}}
   ```

## 对接本工具后端

后端 `app/fetcher/icp.py` 会按公司名查询 `{ICP_API_URL}/query/web?search=公司名`。
设置环境变量后启动 backend 即可：

```bash
# Windows PowerShell
$env:ICP_API_URL = "http://127.0.0.1:16181"
cd backend && python run.py

# Git Bash / Linux
ICP_API_URL=http://127.0.0.1:16181 python run.py
```

未设置该变量时自动跳过 ICP 层（走 Bing 兜底），查询结果会缓存进 SQLite `icp_cache` 表 90 天。

## 常见问题

- **查询返回「当前访问已被创宇盾拦截」/超时**：工信部备案平台（beian.miit.gov.cn）对部分网络出口（数据中心 IP、境外 IP）屏蔽。开发/测试沙箱实测返回 HTTP 521 或 DNS 无法解析。若你的网络被屏蔽，需在服务配置里启用代理（官方项目 `config.yml` 的 `proxy` 段：隧道代理 / 代理池 / 本机 IPv6 池），或改用能访问备案平台的网络环境。
- **验证码识别**：服务内置滑块验证码识别模型（首次拉取镜像含模型，约 100MB），AMD 9600X 平均识别 0.09s；识别失败自动重试（默认 10 次）。
- **批量查询**：支持 POST 批量接口与 WebUI 翻页；本工具按需单条查询即可，无需批量配置。
