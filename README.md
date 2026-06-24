# 信息收集整合系统代码骨架

这是组长负责的可运行代码骨架，覆盖项目主流程：

- 数据源配置
- 采集任务
- 原始数据入库
- 清洗与关键词提取
- 趋势分析与主题详情
- 信息检索与信息详情
- XLSX/PDF 报表生成、列表和下载
- 健康检查

## 项目时间线

本项目按课程结题周期在 2026-06-13 至 2026-06-24 内推进，采用“先分工与文档框架、再模块实现与联调、最后测试验收和交付整理”的节奏。

| 日期 | 主要工作 | 负责人 |
|---|---|---|
| 2026-06-13 | 项目选题、目标确认、分工初稿和 GB 文档清单整理 | 组长 |
| 2026-06-14 | 需求边界、模块接口和演示目标确认 | 组长 |
| 2026-06-15 | 数据源、采集字段和可行性材料整理 | 崔昊晨、兰玉杰、组长 |
| 2026-06-16 | 数据清洗、去重、关键词提取和存储结构整理 | 罗源恒、组长 |
| 2026-06-17 | 趋势算法、时间衰减和主题分析逻辑整理 | 兰玉杰、组长 |
| 2026-06-18 | 前端页面结构、交互草图和接口字段对齐 | 王永成、组长 |
| 2026-06-19 | 后端接口骨架、演示数据和数据库初始化 | 组长 |
| 2026-06-20 | 采集、清洗、趋势、检索接口联调 | 组长、各模块负责人 |
| 2026-06-21 | 前端联调、用户手册和操作手册整理 | 王永成、组长 |
| 2026-06-22 | 单元测试、接口测试、性能测试和测试记录整理 | 郭子凌、组长 |
| 2026-06-23 | 演示检查材料、最终验收清单和提交说明整理 | 组长、全体成员 |
| 2026-06-24 | 最终复核、报表导出增强、文档格式统一和交付包重建 | 组长 |

## 环境准备

```powershell
python -m pip install -r requirements.txt
```

## 运行

```powershell
python -m app.main --host 127.0.0.1 --port 8000
```

打开：

```text
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

页面包含系统首页、趋势分析、信息搜索、数据源管理和报表中心，默认连接：

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

## 报表示例

```powershell
curl -X POST http://127.0.0.1:8000/api/v1/reports ^
  -H "Content-Type: application/json" ^
  -d "{\"report_type\":\"detail\",\"format\":\"xlsx\",\"generated_by\":\"组长\"}"
```

`report_type` 支持 `summary`、`detail`，`format` 支持 `xlsx`、`pdf`。生成文件保存到 `data/reports/`，返回值中的 `download_url` 可直接下载。
