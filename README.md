# 信息收集整合系统代码骨架

这是组长负责的可运行代码骨架，覆盖项目主流程：

- 数据源配置
- 采集任务
- 原始数据入库
- 清洗与关键词提取
- 趋势分析
- 信息检索
- 报表记录
- 健康检查

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
| POST | `/api/v1/reports` | 生成报表记录 |
