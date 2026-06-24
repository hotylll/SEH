const state = { trends: [], items: [], sources: [], reports: [] };
    const apiInput = document.querySelector("#apiBase");
    const modal = document.querySelector("#detailModal");
    const modalTitle = document.querySelector("#modalTitle");
    const modalBody = document.querySelector("#modalBody");
    const activityDock = document.querySelector("#activityDock");
    const activityTitle = document.querySelector("#activityTitle");
    const activitySubtitle = document.querySelector("#activitySubtitle");
    const activityProgress = document.querySelector("#activityProgress");
    const activitySteps = document.querySelector("#activitySteps");
    let toastTimer = 0;
    let activityTimer = 0;
    let activityHideTimer = 0;
    let analysisTimer = 0;
    apiInput.value = localStorage.getItem("apiBase") || apiInput.value;

    function apiBase() {
      return apiInput.value.replace(/\/$/, "");
    }

    function showToast(text) {
      const toast = document.querySelector("#toast");
      window.clearTimeout(toastTimer);
      toast.textContent = text;
      toast.classList.add("show");
      toastTimer = window.setTimeout(() => toast.classList.remove("show"), 2800);
    }

    function setButtonBusy(button, busy) {
      if (!button) return;
      button.classList.toggle("is-busy", busy);
      button.disabled = busy;
    }

    function renderStepNodes(container, steps) {
      container.replaceChildren();
      steps.forEach(step => {
        const node = document.createElement("div");
        node.className = "activity-step";
        node.textContent = step;
        container.appendChild(node);
      });
    }

    function setStepState(nodes, index) {
      nodes.forEach((node, itemIndex) => {
        node.classList.toggle("done", itemIndex < index);
        node.classList.toggle("active", itemIndex === index);
      });
    }

    function showActivity(title, steps) {
      if (!activityDock) return;
      window.clearTimeout(activityHideTimer);
      window.clearInterval(activityTimer);
      activityTitle.textContent = title;
      activitySubtitle.textContent = steps[0] || "正在处理";
      activityProgress.style.width = "10%";
      renderStepNodes(activitySteps, steps);
      setStepState([...activitySteps.children], 0);
      activityDock.dataset.state = "active";
      activityDock.hidden = false;
    }

    function updateActivity(index, steps) {
      if (!activityDock) return;
      const stepIndex = Math.min(index, Math.max(steps.length - 1, 0));
      const percent = steps.length <= 1 ? 70 : Math.round(((stepIndex + 1) / steps.length) * 88);
      activitySubtitle.textContent = steps[stepIndex] || "正在处理";
      activityProgress.style.width = `${percent}%`;
      setStepState([...activitySteps.children], stepIndex);
    }

    function finishActivity(success, message) {
      if (!activityDock) return;
      window.clearInterval(activityTimer);
      activitySubtitle.textContent = message;
      activityProgress.style.width = "100%";
      activityDock.dataset.state = success ? "success" : "error";
      [...activitySteps.children].forEach(node => {
        node.classList.remove("active");
        node.classList.toggle("done", success);
      });
      activityHideTimer = window.setTimeout(() => {
        activityDock.hidden = true;
      }, success ? 1100 : 1800);
    }

    async function runTask({ button, title, steps, successMessage }, task) {
      const taskSteps = steps && steps.length ? steps : ["正在处理"];
      setButtonBusy(button, true);
      showActivity(title, taskSteps);
      let stepIndex = 0;
      activityTimer = window.setInterval(() => {
        stepIndex = Math.min(stepIndex + 1, taskSteps.length - 1);
        updateActivity(stepIndex, taskSteps);
      }, 900);
      try {
        const result = await task();
        finishActivity(true, successMessage || "处理完成");
        return result;
      } catch (error) {
        finishActivity(false, "处理失败");
        throw error;
      } finally {
        window.clearInterval(activityTimer);
        setButtonBusy(button, false);
      }
    }

    async function request(path, options = {}) {
      const response = await fetch(apiBase() + path, options);
      let payload;
      try {
        payload = await response.json();
      } catch (error) {
        throw new Error(`响应格式错误：${response.status}`);
      }
      if (!response.ok || payload.code !== 0) {
        throw new Error(payload.message || "请求失败");
      }
      return payload.data;
    }

    function fillCell(cell, value) {
      if (value instanceof Node) {
        cell.appendChild(value);
        return;
      }
      const text = String(value ?? "-");
      cell.textContent = text;
      cell.title = text;
    }

    function buildTable(headers, rows) {
      const table = document.createElement("table");
      const thead = document.createElement("thead");
      const headerRow = document.createElement("tr");
      headers.forEach(header => {
        const th = document.createElement("th");
        th.textContent = header;
        headerRow.appendChild(th);
      });
      thead.appendChild(headerRow);
      table.appendChild(thead);

      const tbody = document.createElement("tbody");
      if (!rows.length) {
        const emptyRow = document.createElement("tr");
        const td = document.createElement("td");
        td.colSpan = headers.length;
        td.className = "empty-cell";
        td.textContent = "暂无数据";
        emptyRow.appendChild(td);
        tbody.appendChild(emptyRow);
      } else {
        rows.forEach(row => {
          const tr = document.createElement("tr");
          row.forEach(value => {
            const td = document.createElement("td");
            fillCell(td, value);
            tr.appendChild(td);
          });
          tbody.appendChild(tr);
        });
      }
      table.appendChild(tbody);
      return table;
    }

    function setTable(selector, headers, rows) {
      const table = document.querySelector(selector);
      const next = buildTable(headers, rows);
      next.id = selector.slice(1);
      table.replaceWith(next);
    }

    function badge(text, className = "info") {
      const span = document.createElement("span");
      span.className = `badge ${className}`;
      span.textContent = text;
      return span;
    }

    function trendBadge(direction) {
      const text = { surge: "突增", up: "上升", stable: "稳定", down: "下降", plunge: "骤降" }[direction] || direction;
      return badge(text, direction);
    }

    function statusBadge(status) {
      return badge(status, status === "enabled" ? "enabled" : status === "disabled" ? "disabled" : "stable");
    }

    function qualityBadge(score) {
      const value = Number(score);
      const className = value >= 80 ? "score-good" : value >= 60 ? "score-mid" : "score-low";
      return badge(Number.isFinite(value) ? value.toFixed(1) : "-", className);
    }

    function actionButton(label, onClick, className = "action-btn") {
      const button = document.createElement("button");
      button.type = "button";
      button.className = className;
      button.textContent = label;
      button.addEventListener("click", () => Promise.resolve(onClick(button)).catch(error => showToast(error.message)));
      return button;
    }

    function linkNode(url, label = url) {
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.target = "_blank";
      anchor.rel = "noopener";
      anchor.textContent = label || url;
      return anchor;
    }

    function detailGrid(fields) {
      const grid = document.createElement("div");
      grid.className = "detail-grid";
      fields.forEach(([label, value]) => {
        const labelEl = document.createElement("div");
        labelEl.className = "detail-label";
        labelEl.textContent = label;
        const valueEl = document.createElement("div");
        valueEl.className = "detail-value";
        if (value instanceof Node) {
          valueEl.appendChild(value);
        } else {
          valueEl.textContent = String(value ?? "-");
        }
        grid.append(labelEl, valueEl);
      });
      return grid;
    }

    function showModal(title, body) {
      modalTitle.textContent = title;
      modalBody.replaceChildren(body);
      modal.hidden = false;
    }

    function closeModal() {
      modal.hidden = true;
    }

    function formatTime(value) {
      if (!value) return "-";
      return String(value).replace("T", " ").replace("+00:00", "");
    }

    function updateLastSync() {
      const node = document.querySelector("#lastSync");
      const now = new Date();
      node.textContent = `已刷新 ${now.toLocaleTimeString("zh-CN", { hour12: false })}`;
    }

    async function loadHealth() {
      const data = await request("/api/v1/health");
      document.querySelector("#healthStatus").textContent = data.status;
    }

    async function loadTrends() {
      const limit = document.querySelector("#trendLimit").value;
      const data = await request(`/api/v1/trends?limit=${encodeURIComponent(limit)}`);
      state.trends = data.topics || [];
      document.querySelector("#topicCount").textContent = state.trends.length;
      const rows = state.trends.map((t, i) => [
        i + 1,
        t.topic,
        Number(t.score).toFixed(2),
        trendBadge(t.direction),
        `${formatTime(t.period_start)} ~ ${formatTime(t.period_end)}`,
        actionButton("详情", () => showTopicDetail(t.topic))
      ]);
      setTable("#trendTable", ["#", "主题", "分数", "趋势", "周期", "操作"], rows);
      setTable("#hotTable", ["#", "主题", "分数", "趋势", "周期", "操作"], rows.slice(0, 10));
      renderBars();
    }

    function renderBars() {
      const max = Math.max(...state.trends.map(t => Number(t.score)), 1);
      const chart = document.querySelector("#barChart");
      chart.replaceChildren();
      if (!state.trends.length) {
        const empty = document.createElement("div");
        empty.className = "empty-cell";
        empty.textContent = "暂无趋势数据";
        chart.appendChild(empty);
        return;
      }
      state.trends.slice(0, 8).forEach(t => {
        const width = Math.max(4, Number(t.score) / max * 100);
        const row = document.createElement("div");
        row.className = "bar-row";
        const label = document.createElement("div");
        label.className = "bar-label";
        label.textContent = t.topic;
        label.title = t.topic;
        const track = document.createElement("div");
        track.className = "bar-track";
        const fill = document.createElement("div");
        fill.className = "bar-fill";
        fill.style.width = `${width}%`;
        const score = document.createElement("div");
        score.className = "bar-score";
        score.textContent = Number(t.score).toFixed(1);
        track.appendChild(fill);
        row.append(label, track, score);
        chart.appendChild(row);
      });
    }

    async function loadItems() {
      const keyword = document.querySelector("#keyword").value.trim();
      const sourceId = document.querySelector("#sourceId").value.trim();
      const limit = document.querySelector("#itemLimit").value;
      const query = new URLSearchParams({ limit });
      if (keyword) query.set("keyword", keyword);
      if (sourceId) query.set("source_id", sourceId);
      const data = await request(`/api/v1/items?${query}`);
      state.items = data.items || [];
      document.querySelector("#itemCount").textContent = data.total || state.items.length;
      setTable("#itemTable", ["ID", "标题", "来源", "发布时间", "关键词", "质量", "操作"], state.items.map(item => [
        item.id,
        item.title,
        item.source_name || `来源#${item.source_id}`,
        formatTime(item.published_at),
        item.keywords,
        qualityBadge(item.quality_score),
        actionButton("详情", () => showItemDetail(item.id))
      ]));
    }

    async function loadSources() {
      const data = await request("/api/v1/sources");
      state.sources = data.items || [];
      document.querySelector("#sourceCount").textContent = state.sources.length;
      setTable("#sourceTable",
        ["ID", "名称", "类型", "周期", "状态", "关键词", "操作"],
        state.sources.map(s => {
          const grp = document.createElement("span");
          grp.className = "action-group";
          grp.append(
            actionButton("采集", button => collectSource(s.id, button)),
            actionButton("删除", button => deleteSource(s.id, button), "action-btn danger")
          );
          return [s.id, s.name, s.source_type, s.schedule || "-", statusBadge(s.status), s.keywords || "-", grp];
        })
      );
    }

    async function deleteSource(id, button) {
      if (!confirm(`确定要删除数据源 #${id} 及其所有关联数据吗？`)) return;
      await runTask({
        button,
        title: `删除数据源 #${id}`,
        steps: ["确认关联数据", "删除数据源记录", "刷新列表与趋势"],
        successMessage: "数据源已删除"
      }, async () => {
        await request(`/api/v1/sources/${id}`, { method: "DELETE" });
        showToast("数据源已删除");
        await Promise.all([loadSources(), loadItems(), loadTrends()]);
        updateLastSync();
      });
    }

    async function collectSource(id, button) {
      await runTask({
        button,
        title: `采集数据源 #${id}`,
        steps: ["连接数据源", "检索公开结果", "清洗去重入库", "重建趋势指标"],
        successMessage: "采集流程已完成"
      }, async () => {
        const data = await request("/api/v1/tasks/collect", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ source_id: id })
        });
        showToast(`采集完成：新增 ${data.success_count} 条${data.duplicate_count ? `，重复 ${data.duplicate_count} 条` : ""}`);
        await Promise.all([loadItems(), loadTrends()]);
        updateLastSync();
        return data;
      });
    }

    async function showItemDetail(id) {
      const item = await request(`/api/v1/items/${encodeURIComponent(id)}`);
      const url = item.url ? linkNode(item.url, item.url) : "-";
      const body = detailGrid([
        ["标题", item.title],
        ["正文", item.normalized_content || item.content || "-"],
        ["关键词", item.keywords || "-"],
        ["来源", item.source_name || `来源#${item.source_id}`],
        ["URL", url],
        ["发布时间", formatTime(item.published_at)],
        ["质量评分", Number(item.quality_score).toFixed(1)]
      ]);
      showModal(`信息详情 #${item.id}`, body);
    }

    async function showTopicDetail(topic) {
      const data = await request(`/api/v1/trends/${encodeURIComponent(topic)}`);
      const wrap = document.createElement("div");
      const trend = data.series && data.series[0];
      wrap.appendChild(detailGrid([
        ["主题", data.topic],
        ["分数", trend ? Number(trend.score).toFixed(2) : "-"],
        ["趋势", trend ? trend.direction : "-"],
        ["周期", trend ? `${formatTime(trend.period_start)} ~ ${formatTime(trend.period_end)}` : "-"]
      ]));
      const title = document.createElement("h2");
      title.textContent = "关联信息";
      title.className = "modal-section-title";
      wrap.appendChild(title);
      wrap.appendChild(buildTable(
        ["ID", "标题", "发布时间", "关键词", "质量"],
        (data.items || []).map(item => [
          item.id,
          item.title,
          formatTime(item.published_at),
          item.keywords,
          Number(item.quality_score).toFixed(1)
        ])
      ));
      showModal("主题详情", wrap);
    }

    async function createSource(button) {
      const name = document.querySelector("#srcName").value.trim();
      if (!name) { showToast("请输入数据源名称"); document.querySelector("#srcName").focus(); return; }
      const endpoint = document.querySelector("#srcEndpoint").value.trim();
      if (!endpoint) { showToast("请输入 endpoint 地址"); document.querySelector("#srcEndpoint").focus(); return; }
      const keywords = document.querySelector("#srcKeywords").value.trim();
      if (!keywords) { showToast("请输入关键词，多个用逗号分隔"); document.querySelector("#srcKeywords").focus(); return; }
      await runTask({
        button,
        title: "保存数据源",
        steps: ["校验表单字段", "写入数据源配置", "刷新数据源列表"],
        successMessage: "数据源已保存"
      }, async () => {
        const data = await request("/api/v1/sources", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            name, type: document.querySelector("#srcType").value, endpoint, keywords,
            schedule: document.querySelector("#srcSchedule").value, status: document.querySelector("#srcStatus").value
          })
        });
        showToast(`数据源已创建：${data.name}`);
        document.querySelector("#srcName").value = "";
        document.querySelector("#srcKeywords").value = "";
        document.querySelector("#srcEndpoint").value = "";
        await loadSources();
        updateLastSync();
        return data;
      });
    }

    async function loadReports() {
      const data = await request("/api/v1/reports");
      state.reports = data.items || [];
      setTable("#reportTable", ["ID", "名称", "类型", "格式", "生成人", "生成时间", "操作"], state.reports.map(report => [
        report.id,
        report.report_name,
        report.report_type,
        report.file_format,
        report.generated_by,
        formatTime(report.generated_at),
        actionButton("下载", () => downloadReport(report))
      ]));
    }

    function downloadReport(report) {
      window.open(apiBase() + report.download_url, "_blank", "noopener");
    }

    async function createReport(button) {
      await runTask({
        button,
        title: "生成报表文件",
        steps: ["读取趋势与信息数据", "生成文件内容", "写入报表记录", "刷新报表列表"],
        successMessage: "报表文件已生成"
      }, async () => {
        const data = await request("/api/v1/reports", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            report_type: document.querySelector("#reportType").value,
            format: document.querySelector("#reportFormat").value,
            generated_by: document.querySelector("#generatedBy").value || "罗元恒"
          })
        });
        const result = document.querySelector("#reportResult");
        const download = actionButton("下载", () => downloadReport(data));
        result.replaceChildren(`${data.report_name} / ${data.file_path} `, download);
        showToast("报表文件已生成");
        await loadReports();
        updateLastSync();
        return data;
      });
    }

    async function refreshAll(button) {
      try {
        await runTask({
          button,
          title: "同步全局数据",
          steps: ["检查服务状态", "读取数据源", "加载信息明细", "刷新趋势榜单", "同步报表记录"],
          successMessage: "全部面板已同步"
        }, async () => {
        await Promise.all([loadHealth(), loadSources(), loadItems(), loadTrends(), loadReports()]);
        updateLastSync();
        });
      } catch (error) {
        showToast("刷新失败: " + error.message);
      }
    }

    /* 自动刷新（每 60 秒） */
    let autoRefreshTimer = setInterval(() => {
      if (document.visibilityState === "visible") {
        loadHealth().catch(() => {});
        updateLastSync();
      }
    }, 60000);

    function appendInline(parent, text) {
      const pattern = /(\*\*([^*]+)\*\*|`([^`]+)`)/g;
      let lastIndex = 0;
      let match;
      while ((match = pattern.exec(text)) !== null) {
        if (match.index > lastIndex) {
          parent.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
        }
        if (match[2]) {
          const strong = document.createElement("strong");
          strong.textContent = match[2];
          parent.appendChild(strong);
        } else {
          const code = document.createElement("code");
          code.textContent = match[3];
          parent.appendChild(code);
        }
        lastIndex = pattern.lastIndex;
      }
      if (lastIndex < text.length) {
        parent.appendChild(document.createTextNode(text.slice(lastIndex)));
      }
    }

    function flushParagraph(container, lines) {
      if (!lines.length) return;
      const p = document.createElement("p");
      appendInline(p, lines.join(" "));
      container.appendChild(p);
      lines.length = 0;
    }

    function renderMarkdownInto(container, text) {
      container.replaceChildren();
      const lines = String(text || "").split(/\r?\n/);
      const paragraph = [];
      let list = null;
      let ordered = false;
      let code = null;

      function closeList() {
        if (list) {
          container.appendChild(list);
          list = null;
        }
      }

      lines.forEach(rawLine => {
        const line = rawLine.trimEnd();
        if (line.startsWith("```")) {
          if (code) {
            const pre = document.createElement("pre");
            const codeEl = document.createElement("code");
            codeEl.textContent = code.join("\n");
            pre.appendChild(codeEl);
            container.appendChild(pre);
            code = null;
          } else {
            flushParagraph(container, paragraph);
            closeList();
            code = [];
          }
          return;
        }
        if (code) {
          code.push(rawLine);
          return;
        }
        const trimmed = line.trim();
        if (!trimmed) {
          flushParagraph(container, paragraph);
          closeList();
          return;
        }
        if (trimmed.startsWith("## ")) {
          flushParagraph(container, paragraph);
          closeList();
          const h2 = document.createElement("h2");
          h2.textContent = trimmed.slice(3).trim();
          container.appendChild(h2);
          return;
        }
        if (trimmed.startsWith("### ")) {
          flushParagraph(container, paragraph);
          closeList();
          const h3 = document.createElement("h3");
          h3.textContent = trimmed.slice(4).trim();
          container.appendChild(h3);
          return;
        }
        const bullet = trimmed.match(/^[-*]\s+(.+)$/);
        const numbered = trimmed.match(/^\d+[.)]\s+(.+)$/);
        if (bullet || numbered) {
          flushParagraph(container, paragraph);
          const shouldOrder = Boolean(numbered);
          if (!list || ordered !== shouldOrder) {
            closeList();
            list = document.createElement(shouldOrder ? "ol" : "ul");
            ordered = shouldOrder;
          }
          const li = document.createElement("li");
          appendInline(li, (bullet || numbered)[1]);
          list.appendChild(li);
          return;
        }
        paragraph.push(trimmed);
      });
      flushParagraph(container, paragraph);
      closeList();
      if (code) {
        const pre = document.createElement("pre");
        const codeEl = document.createElement("code");
        codeEl.textContent = code.join("\n");
        pre.appendChild(codeEl);
        container.appendChild(pre);
      }
    }

    function domainOf(url) {
      try {
        return new URL(url).hostname.replace(/^www\./, "");
      } catch {
        return url || "-";
      }
    }

    function renderSourceList(sources) {
      const sourceList = document.querySelector("#sourceList");
      sourceList.replaceChildren();
      if (!sources.length) {
        const empty = document.createElement("div");
        empty.className = "muted";
        empty.textContent = "本次未返回外部来源。";
        sourceList.appendChild(empty);
        return;
      }
      sources.forEach((src, index) => {
        const link = document.createElement("a");
        link.href = src.url;
        link.target = "_blank";
        link.rel = "noopener";
        link.className = "source-item";
        const title = document.createElement("span");
        title.className = "source-title";
        title.textContent = `${index + 1}. ${src.title || "未命名来源"}`;
        const domain = document.createElement("span");
        domain.className = "source-domain";
        domain.textContent = domainOf(src.url);
        link.append(title, domain);
        sourceList.appendChild(link);
      });
    }

    const analysisStages = ["连接搜索源", "筛选可信来源", "调用 AI 分析", "整理报告结构"];

    function updateAnalysisMotion(index, failed = false) {
      const stage = document.querySelector("#analysisStage");
      const progress = document.querySelector("#analysisProgress");
      const stepNodes = [...document.querySelectorAll("#analysisStepList .analysis-step")];
      const stepIndex = Math.min(index, analysisStages.length - 1);
      stage.textContent = failed ? "分析失败，请检查配置或网络" : analysisStages[stepIndex];
      progress.style.width = failed ? "38%" : `${Math.round(((stepIndex + 1) / analysisStages.length) * 100)}%`;
      stepNodes.forEach((node, itemIndex) => {
        node.classList.toggle("done", !failed && itemIndex < stepIndex);
        node.classList.toggle("active", !failed && itemIndex === stepIndex);
      });
    }

    function startAnalysisMotion() {
      window.clearInterval(analysisTimer);
      let index = 0;
      updateAnalysisMotion(index);
      analysisTimer = window.setInterval(() => {
        index = Math.min(index + 1, analysisStages.length - 1);
        updateAnalysisMotion(index);
      }, 1100);
    }

    function finishAnalysisMotion(success) {
      window.clearInterval(analysisTimer);
      if (success) {
        updateAnalysisMotion(analysisStages.length - 1);
        document.querySelectorAll("#analysisStepList .analysis-step").forEach(node => {
          node.classList.remove("active");
          node.classList.add("done");
        });
      } else {
        updateAnalysisMotion(0, true);
      }
    }

    async function startAnalyze() {
      const topicInput = document.querySelector("#analyzeTopic");
      const topic = topicInput.value.trim();
      if (!topic) {
        showToast("请输入分析主题");
        return;
      }

      const resultDiv = document.querySelector("#analyzeResult");
      const emptyDiv = document.querySelector("#analyzeEmpty");
      const loadingDiv = document.querySelector("#analyzeLoading");
      const contentDiv = document.querySelector("#analyzeContent");
      const badgeSpan = document.querySelector("#sourceBadge");
      const startButton = document.querySelector("#startAnalyze");

      resultDiv.hidden = true;
      emptyDiv.hidden = true;
      loadingDiv.classList.add("show");
      startAnalysisMotion();

      try {
        const data = await runTask({
          button: startButton,
          title: "智能分析",
          steps: analysisStages,
          successMessage: "分析报告已生成"
        }, async () => {
          return request("/api/v1/analyze", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ topic })
          });
        });

        finishAnalysisMotion(true);
        renderMarkdownInto(contentDiv, data.analysis);
        renderSourceList(data.sources || []);
        badgeSpan.textContent = `${data.source_count || 0} 个来源`;
        document.querySelector("#analyzeTitle").textContent = `${topic} - AI 分析报告`;
        resultDiv.hidden = false;
        showToast(`分析完成，共 ${data.source_count || 0} 个信息来源`);
      } catch (error) {
        finishAnalysisMotion(false);
        emptyDiv.hidden = false;
        showToast("分析失败：" + error.message);
      } finally {
        loadingDiv.classList.remove("show");
      }
    }

    function activateView(view, updateUrl = true) {
      const button = document.querySelector(`nav button[data-view="${view}"]`);
      const panel = document.querySelector(`#${view}`);
      if (!button || !panel) return;
      document.querySelectorAll("nav button").forEach(item => item.classList.remove("active"));
      document.querySelectorAll(".view").forEach(item => item.classList.remove("active"));
      button.classList.add("active");
      panel.classList.add("active");
      if (updateUrl) {
        const url = new URL(window.location.href);
        url.searchParams.set("view", view);
        window.history.replaceState(null, "", url);
      }
    }

    document.querySelectorAll("nav button").forEach(button => {
      button.addEventListener("click", () => activateView(button.dataset.view));
    });
    document.querySelector("#saveApi").addEventListener("click", event => {
      localStorage.setItem("apiBase", apiInput.value);
      refreshAll(event.currentTarget);
    });
    document.querySelector("#refreshAll").addEventListener("click", event => refreshAll(event.currentTarget));
    document.querySelector("#loadTrends").addEventListener("click", event => {
      runTask({
        button: event.currentTarget,
        title: "刷新趋势分析",
        steps: ["请求趋势接口", "计算热度分布", "更新榜单视图"],
        successMessage: "趋势分析已刷新"
      }, async () => {
        await loadTrends();
        updateLastSync();
      }).catch(e => showToast(e.message));
    });
    document.querySelector("#searchItems").addEventListener("click", event => {
      runTask({
        button: event.currentTarget,
        title: "检索信息明细",
        steps: ["提交筛选条件", "读取清洗数据", "渲染搜索结果"],
        successMessage: "搜索结果已更新"
      }, async () => {
        await loadItems();
        updateLastSync();
      }).catch(e => showToast(e.message));
    });
    document.querySelector("#loadSources").addEventListener("click", event => {
      runTask({
        button: event.currentTarget,
        title: "刷新数据源",
        steps: ["读取配置表", "整理状态标签", "刷新管理列表"],
        successMessage: "数据源列表已刷新"
      }, async () => {
        await loadSources();
        updateLastSync();
      }).catch(e => showToast(e.message));
    });
    document.querySelector("#loadReports").addEventListener("click", event => {
      runTask({
        button: event.currentTarget,
        title: "刷新报表记录",
        steps: ["读取报表历史", "检查下载地址", "刷新记录列表"],
        successMessage: "报表记录已刷新"
      }, async () => {
        await loadReports();
        updateLastSync();
      }).catch(e => showToast(e.message));
    });
    document.querySelector("#createSource").addEventListener("click", event => createSource(event.currentTarget).catch(e => showToast(e.message)));
    document.querySelector("#createReport").addEventListener("click", event => createReport(event.currentTarget).catch(e => showToast(e.message)));
    document.querySelector("#startAnalyze").addEventListener("click", startAnalyze);
    document.querySelector("#analyzeTopic").addEventListener("keydown", e => {
      if (e.key === "Enter") startAnalyze();
    });
    document.querySelector("#keyword").addEventListener("keydown", e => {
      if (e.key === "Enter") {
        runTask({
          title: "检索信息明细",
          steps: ["提交筛选条件", "读取清洗数据", "渲染搜索结果"],
          successMessage: "搜索结果已更新"
        }, async () => {
          await loadItems();
          updateLastSync();
        }).catch(err => showToast(err.message));
      }
    });
    document.querySelector("#copyAnalysis").addEventListener("click", async () => {
      const text = document.querySelector("#analyzeContent").textContent;
      try {
        await navigator.clipboard.writeText(text);
        showToast("已复制到剪贴板");
      } catch {
        showToast("复制失败");
      }
    });
    document.querySelector("#closeModal").addEventListener("click", closeModal);
    document.querySelector("[data-close-modal]").addEventListener("click", closeModal);
    document.addEventListener("keydown", event => {
      if (event.key === "Escape" && !modal.hidden) closeModal();
    });

    activateView(new URLSearchParams(window.location.search).get("view") || "dashboard", false);
    refreshAll();
