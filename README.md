# 集思 · 信息收集整合系统（Jisi InfoHub）代码骨架

这是罗元恒负责的可运行代码骨架，覆盖项目主流程：

- 数据源配置
- 真实搜索源采集（SearXNG / Exa）
- 采集任务与网页正文抓取
- 原始数据入库
- 清洗与关键词提取
- 趋势分析与主题详情
- 信息检索与信息详情
- 全网检索 + AI 智能分析
- XLSX/PDF 报表生成、列表和下载
- 健康检查

## 项目时间线

本项目按课程结题周期在 2026-06-13 至 2026-06-24 内推进，采用“先分工与文档框架、再模块实现与联调、最后测试验收和交付整理”的节奏。

| 日期 | 主要工作 | 负责人 |
|---|---|---|
| 2026-06-13 | 项目选题、目标确认、分工初稿和 GB 文档清单整理 | 罗元恒 |
| 2026-06-14 | 需求边界、模块接口和演示目标确认 | 罗元恒 |
| 2026-06-15 | 数据源、采集字段和可行性材料整理 | 崔昊晨、兰玉杰、罗元恒 |
| 2026-06-16 | 数据清洗、去重、关键词提取和存储结构整理 | 罗昆昊、罗元恒 |
| 2026-06-17 | 趋势算法、时间衰减和主题分析逻辑整理 | 兰玉杰、罗元恒 |
| 2026-06-18 | 前端页面结构、交互草图和接口字段对齐 | 王永成、罗元恒 |
| 2026-06-19 | 后端接口骨架、演示数据和数据库初始化 | 罗元恒 |
| 2026-06-20 | 采集、清洗、趋势、检索接口联调 | 罗元恒、各模块负责人 |
| 2026-06-21 | 前端联调、用户手册和操作手册整理 | 王永成、罗元恒 |
| 2026-06-22 | 单元测试、接口测试、性能测试和测试记录整理 | 郭子凌、罗元恒 |
| 2026-06-23 | 演示检查材料、最终验收清单和提交说明整理 | 罗元恒、全体成员 |
| 2026-06-24 | 最终复核、真实搜索源与 AI 分析联调、前端 UI 优化、文档格式统一和教师提交文档包重建 | 罗元恒 |

## 环境准备

```powershell
python -m pip install -r requirements.txt
```

如需演示「智能分析」，复制 `.env.example` 为 `.env`，至少填写：

```text
AI_API_KEY="your-api-key"
SEARXNG_URL="https://sh.ranai.de5.net"
```

`EXA_API_KEY` 为可选项，配置后可增强 Exa 搜索覆盖。`AI_API_BASE`、`AI_MODEL` 可按 OpenAI 兼容服务实际配置调整。

## 运行

```powershell
python -m app.main --host 127.0.0.1 --port 8000
```

打开：

```text
http://127.0.0.1:8000/
http://127.0.0.1:8000/api/v1/health
http://127.0.0.1:8000/api/v1/sources
http://127.0.0.1:8000/api/v1/items
http://127.0.0.1:8000/api/v1/trends
```

## 前端演示

启动后端服务后，直接用浏览器打开：

```text
frontend/index.html
```

页面包含系统首页、趋势分析、信息搜索、数据源管理、报表中心和智能分析，默认连接：

```text
http://127.0.0.1:8000
```

## 测试

```powershell
python -m unittest discover -s tests -v
```

当前自动化测试覆盖清洗分析、存储、接口、边界输入、报表下载和性能场景。

## 主要接口

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/v1/health` | 系统健康检查 |
| GET | `/api/v1/sources` | 查询数据源 |
| POST | `/api/v1/sources` | 新增数据源 |
| POST | `/api/v1/tasks/collect` | 启动采集任务 |
| GET | `/api/v1/tasks/{task_id}` | 查询任务状态 |
| GET | `/api/v1/items` | 查询信息明细 |
| GET | `/api/v1/items/{item_id}` | 查询信息详情 |
| GET | `/api/v1/trends` | 查询趋势榜单 |
| GET | `/api/v1/trends/{topic}` | 查询主题详情和关联信息 |
| GET | `/api/v1/reports` | 查询报表记录 |
| POST | `/api/v1/reports` | 生成 XLSX/PDF 报表文件 |
| GET | `/api/v1/reports/{report_id}/download` | 下载报表文件 |
| POST | `/api/v1/analyze` | 真实搜索源检索并生成 AI 分析报告 |

## 智能分析示例

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/analyze ^
  -H "Content-Type: application/json" ^
  -d "{\"topic\":\"人工智能产业趋势\"}"
```

该接口先通过 SearXNG 检索公开网页结果，并可选合并 Exa 结果；随后调用 OpenAI 兼容 API 生成 Markdown 格式的中文分析报告。前端「智能分析」页面会以安全 DOM 渲染报告内容和来源链接。

## 报表示例

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/reports ^
  -H "Content-Type: application/json" ^
  -d "{\"report_type\":\"detail\",\"format\":\"xlsx\",\"generated_by\":\"罗元恒\"}"
```

`report_type` 支持 `summary`、`detail`，`format` 支持 `xlsx`、`pdf`。生成文件保存到 `data/reports/`，返回值中的 `download_url` 可直接下载。
