"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import RefreshControls from "./refresh-controls";

const ASSET_BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

const DEFAULT_OWNER_STATS = [
  { name: "李明", total: 42, closed: 24 },
  { name: "王雪", total: 31, closed: 19 },
  { name: "张三", total: 28, closed: 11 },
  { name: "陈晨", total: 19, closed: 8 },
];

function buildOwnerRanking(rows) {
  return [...rows]
    .map((row) => ({
      ...row,
      opened: row.opened ?? row.total - row.closed,
      rate: row.total ? (row.closed / row.total) * 100 : 0,
    }))
    .sort((a, b) => {
      if (b.rate !== a.rate) return b.rate - a.rate;
      if (b.closed !== a.closed) return b.closed - a.closed;
      if (b.total !== a.total) return b.total - a.total;
      return a.name.localeCompare(b.name, "zh-Hans-CN");
    })
    .map((row, index) => ({
      ...row,
      rank: index + 1,
    }));
}

const FALLBACK_DASHBOARD = {
  source: "mock",
  generatedAt: "2026-08-18T14:55:00+08:00",
  summary: [
    { label: "总数", value: "204", tone: "total" },
    { label: "开启数", value: "128", tone: "open" },
    { label: "关闭率", value: "37.30%", tone: "rate" },
  ],
  duty: {
    date: "2026-08-18",
    name: "张三",
    account: "zhangsan",
  },
  ownerRanking: buildOwnerRanking(DEFAULT_OWNER_STATS),
  labelStats: [
    { label: "bug", open: 31, closed: 27 },
    { label: "feature", open: 28, closed: 18 },
    { label: "infra", open: 12, closed: 23 },
    { label: "docs", open: 14, closed: 7 },
  ],
  dailyIssueStats: [
    ...Array.from({ length: 25 }, (_, index) => ({
      date: `08-${String(index + 1).padStart(2, "0")}`,
      opened: 0,
      closed: 0,
    })),
  ],
  dailyIssueDetails: [],
};

async function loadDashboard() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;

  if (supabaseUrl && supabaseKey) {
    try {
      const response = await fetch(
        `${supabaseUrl.replace(/\/$/, "")}/rest/v1/dashboard_snapshots?id=eq.1&select=payload,generated_at`,
        {
          cache: "no-store",
          headers: { apikey: supabaseKey },
        }
      );
      const rows = await response.json();
      if (response.ok && rows[0]?.payload) {
        return applyDutyOverlay(
          { ...rows[0].payload, __generatedAt: rows[0].generated_at },
          supabaseUrl,
          supabaseKey
        );
      }
    } catch {
      // Fall back to the local FastAPI endpoint during development.
    }
  }

  const baseUrl = process.env.DASHBOARD_API_BASE_URL ?? "http://127.0.0.1:8000";

  try {
    const response = await fetch(`${baseUrl}/api/dashboard`, {
      cache: "no-store",
    });

    if (response.ok) {
      return await response.json();
    }
  } catch {
    // Fall back to local sample data when the API is unavailable.
  }

  return FALLBACK_DASHBOARD;
}

function localDateString(value = new Date()) {
  const offset = value.getTimezoneOffset() * 60000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 10);
}

async function applyDutyOverlay(dashboard, supabaseUrl, supabaseKey) {
  try {
    const baseUrl = supabaseUrl.replace(/\/$/, "");
    const headers = { apikey: supabaseKey };
    const [scheduleResponse, memberResponse, issueResponse] = await Promise.all([
      fetch(`${baseUrl}/rest/v1/duty_schedules?select=duty_date,person_name`, {
        cache: "no-store",
        headers,
      }),
      fetch(`${baseUrl}/rest/v1/duty_members?select=person_name,gitcode_account`, {
        cache: "no-store",
        headers,
      }),
      fetch(`${baseUrl}/rest/v1/issues?select=issue_number,title,state,owner,created_at,issue_url,raw_payload&order=created_at.desc`, {
        cache: "no-store",
        headers,
      }),
    ]);
    if (!scheduleResponse.ok || !memberResponse.ok || !issueResponse.ok) return dashboard;
    const schedules = await scheduleResponse.json();
    const members = await memberResponse.json();
    const issues = await issueResponse.json();
    const scheduleByDate = Object.fromEntries(
      schedules.map((row) => [row.duty_date, row.person_name])
    );
    const accountByName = Object.fromEntries(
      members.map((row) => [row.person_name, row.gitcode_account])
    );
    const dutyForDate = (date) => {
      const name = scheduleByDate[date];
      return name ? { date, name, account: accountByName[name] || null } : null;
    };
    const issueOwner = (issue) => {
      if (issue.owner) return issue.owner;
      const payload = issue.raw_payload;
      const assignee = payload?.assignee;
      if (assignee && typeof assignee === "object") {
        return assignee.name || assignee.login || "未分配";
      }
      if (typeof assignee === "string" && assignee.trim()) return assignee.trim();
      return "未分配";
    };
    const allIssueDetails = issues
      .filter((issue) => issue.created_at)
      .map((issue) => {
        const date = issue.created_at.slice(0, 10);
        const duty = dutyForDate(date) || { date, name: "未排班", account: null };
        return {
          date,
          dutyName: duty.name,
          dutyAccount: duty.account,
          issueNumber: String(issue.issue_number || ""),
          issueTitle: issue.title || `Issue #${issue.issue_number}`,
          issueState: String(issue.state).toLowerCase() === "closed" ? "关闭" : "开启",
          issueUrl: issue.issue_url,
          owner: issueOwner(issue),
        };
      });
    const today = localDateString();
    return {
      ...dashboard,
      duty: dutyForDate(today) || dashboard.duty,
      dailyIssueDetails: allIssueDetails.length ? allIssueDetails : (dashboard.dailyIssueDetails || []).map((item) => {
        const duty = dutyForDate(item.date);
        return duty
          ? { ...item, dutyName: duty.name, dutyAccount: duty.account }
          : item;
      }),
    };
  } catch {
    return dashboard;
  }
}

async function requestCloudSync() {
  const supabaseUrl = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const supabaseKey = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY;
  if (!supabaseUrl || !supabaseKey) return;

  const response = await fetch(
    `${supabaseUrl.replace(/\/$/, "")}/functions/v1/trigger-sync`,
    {
      method: "POST",
      headers: { apikey: supabaseKey, "Content-Type": "application/json" },
      body: "{}",
    }
  );
  if (!response.ok) throw new Error("同步任务触发失败");
  return response.json();
}

function formatPercent(value) {
  return `${value.toFixed(2)}%`;
}

function formatShortDate(value) {
  const [year, month, day] = value.split("-");
  return `${Number(month)}.${Number(day)}`;
}

function formatIssueDate(value) {
  const [year, month, day] = value.split("-");
  return `${month.padStart(2, "0")}.${day.padStart(2, "0")}`;
}

function DashboardView({ dashboard, onRefresh }) {
  const [issueFilter, setIssueFilter] = useState("all");
  const summaryCards = dashboard.summary ?? FALLBACK_DASHBOARD.summary;
  const duty = dashboard.duty ?? FALLBACK_DASHBOARD.duty;
  const ownerRanking = dashboard.ownerRanking ?? FALLBACK_DASHBOARD.ownerRanking;
  const dailyIssueStats =
    dashboard.dailyIssueStats ?? FALLBACK_DASHBOARD.dailyIssueStats;
  const dailyIssueDetails =
    dashboard.dailyIssueDetails ?? FALLBACK_DASHBOARD.dailyIssueDetails;
  const filteredIssueDetails = dailyIssueDetails.filter((item) => {
    if (issueFilter === "open") return item.issueState === "开启";
    if (issueFilter === "closed") return item.issueState === "关闭";
    return true;
  });
  const dailyIssueGroups = Object.values(
    filteredIssueDetails.reduce((groups, item) => {
      const key = `${item.date}-${item.dutyName}-${item.dutyAccount ?? ""}`;
      if (!groups[key]) {
        groups[key] = {
          date: item.date,
          dutyName: item.dutyName,
          dutyAccount: item.dutyAccount,
          issues: [],
        };
      }
      groups[key].issues.push(item);
      return groups;
    }, {})
  );

  const maxDailyTotal = Math.max(
    ...dailyIssueStats.map((item) => item.opened + item.closed),
    1
  );

  return (
    <main className="page">
      <section className="shell hero">
        <div className="hero-title">
          <img className="site-logo" src={`${ASSET_BASE_PATH}/torchair-logo.png`} alt="TorchAir" />
          <span className="hero-accent" aria-hidden="true" />
          <h1>TorchAir issue</h1>
        </div>
        <div className="hero-meta" aria-label="今日值班信息">
          <span>{formatShortDate(duty.date)}</span>
          <span className="hero-duty">
            <span className="duty-badge">值班</span>
            <strong>{duty.name}</strong>
            {duty.account ? <span>@{duty.account}</span> : null}
          </span>
          <Link className="manage-link" href="/duty">
            排班管理
          </Link>
          <RefreshControls onRefresh={onRefresh} />
        </div>
      </section>

      <section className="shell section">
        <div className="summary-grid" aria-label="Issue 总览">
          {summaryCards.map((card) => (
            <article key={card.label} className={`metric metric-${card.tone}`}>
              <p>{card.label}</p>
              <strong>{card.value}</strong>
            </article>
          ))}
        </div>
      </section>

      <section className="shell section">
        <div className="chart-card">
          <div className="chart-legend" aria-label="每日 issue 图例">
            <span>
              <i className="swatch swatch-open" aria-hidden="true" />
              开启
            </span>
            <span>
              <i className="swatch swatch-closed" aria-hidden="true" />
              关闭
            </span>
          </div>

          <div className="chart-scroll">
            <div className="daily-chart-shell">
              <div className="daily-plot">
              {dailyIssueStats.map((item) => {
                const openedHeight = (item.opened / maxDailyTotal) * 100;
                const closedHeight = (item.closed / maxDailyTotal) * 100;
                const totalHeight = openedHeight + closedHeight;

                return (
                  <div key={item.date} className="daily-column">
                    <div className="daily-bar-track">
                      <span
                        className="daily-bar-fill daily-closed"
                        style={{ height: `${closedHeight}%` }}
                        title={`关闭：${item.closed}`}
                        aria-label={`${item.date}，关闭 ${item.closed}`}
                      />
                      <span
                        className="daily-bar-fill daily-open"
                        style={{ height: `${openedHeight}%` }}
                        title={`开启：${item.opened}`}
                        aria-label={`${item.date}，开启 ${item.opened}`}
                      />
                      <span
                        className="daily-total"
                        style={{ bottom: `calc(${totalHeight}% + 4px)` }}
                          >
                        {item.opened + item.closed}
                      </span>
                    </div>
                    <span className="chart-label">{item.date}</span>
                  </div>
                );
              })}
              </div>
            </div>
          </div>
        </div>
      </section>

      <section className="shell section">
        <div className="detail-toolbar">
          <div className="detail-filter" role="group" aria-label="Issue 状态筛选">
            {[["all", "全部"], ["open", "已开启"], ["closed", "已关闭"]].map(([value, label]) => (
              <button
                key={value}
                type="button"
                className={`detail-filter-button ${issueFilter === value ? "is-active" : ""}`}
                aria-pressed={issueFilter === value}
                onClick={() => setIssueFilter(value)}
              >
                {label}
              </button>
            ))}
          </div>
        </div>
        <div className="detail-table" role="table" aria-label="每日 issue 明细">
          <div className="detail-row detail-head" role="row">
            <span role="columnheader">日期</span>
            <span role="columnheader">值班人员</span>
            <span role="columnheader">Issue 明细</span>
          </div>
          <div className="detail-scroll" role="rowgroup">
            {dailyIssueGroups.length ? dailyIssueGroups.map((group) => (
              <div key={`${group.date}-${group.dutyName}`} className="detail-row" role="row">
                <span role="cell" data-label="日期">{formatIssueDate(group.date)}</span>
                <span role="cell" data-label="值班人员" className="duty-detail-cell">
                  <span>{group.dutyName}</span>
                  {group.dutyAccount ? <small>@{group.dutyAccount}</small> : null}
                </span>
                <span role="cell" data-label="Issue 明细" className="issue-detail-cell">
                  {group.issues.map((item) => (
                    <span className="issue-detail-line" key={item.issueNumber}>
                      {item.issueUrl ? (
                      <a
                          className="issue-link-card"
                          href={item.issueUrl}
                          target="_blank"
                          rel="noreferrer"
                          title={`#${item.issueNumber} ${item.issueTitle}`}
                        >
                          <i
                            className={`issue-status-dot issue-status-dot-${item.issueState === "关闭" ? "closed" : "open"}`}
                            title={item.issueState}
                            aria-label={item.issueState}
                          />
                          <span className="issue-title-text">#{item.issueNumber} {item.issueTitle}</span>
                        </a>
                      ) : (
                        <span className="issue-link-card" title={`#${item.issueNumber} ${item.issueTitle}`}>
                          <i
                            className={`issue-status-dot issue-status-dot-${item.issueState === "关闭" ? "closed" : "open"}`}
                            title={item.issueState}
                            aria-label={item.issueState}
                          />
                          <span className="issue-title-text">#{item.issueNumber} {item.issueTitle}</span>
                        </span>
                      )}
                      <span className="issue-owner-card" title={item.owner}>{item.owner}</span>
                    </span>
                  ))}
                </span>
              </div>
            )) : <div className="detail-empty">暂无符合条件的 issue 明细</div>}
          </div>
        </div>
      </section>

      <section className="shell section">
        <div className="rank-table" role="table" aria-label="负责人处理效率排行">
          <div className="rank-row rank-head" role="row">
            <span role="columnheader">排名</span>
            <span role="columnheader">负责人</span>
            <span role="columnheader">总数</span>
            <span role="columnheader">开启数</span>
            <span role="columnheader">关闭数</span>
            <span role="columnheader">关闭率</span>
          </div>
          {ownerRanking.map((row) => (
            <div key={row.name} className="rank-row" role="row">
              <span role="cell" data-label="排名" className="rank-cell">
                <span className={`rank-badge rank-badge-${row.rank}`}>{row.rank}</span>
              </span>
              <span role="cell" data-label="负责人" className="name-cell">
                {row.name}
              </span>
              <span role="cell" data-label="总数">
                {row.total}
              </span>
              <span role="cell" data-label="开启数">
                {row.opened}
              </span>
              <span role="cell" data-label="关闭数">
                {row.closed}
              </span>
              <span role="cell" data-label="关闭率" className="rate-cell">
                {formatPercent(row.rate)}
              </span>
            </div>
          ))}
        </div>
      </section>
    </main>
  );
}

export default function Home() {
  const [dashboard, setDashboard] = useState(null);

  const refreshDashboard = useCallback(async ({ trigger = false } = {}) => {
    const triggerResult = trigger ? await requestCloudSync() : null;

    const previousGeneratedAt = dashboard?.__generatedAt;
    let nextDashboard = await loadDashboard();
    if (trigger && triggerResult?.accepted && previousGeneratedAt) {
      for (let attempt = 0; attempt < 20; attempt += 1) {
        if (nextDashboard.__generatedAt !== previousGeneratedAt) break;
        await new Promise((resolve) => window.setTimeout(resolve, 3000));
        nextDashboard = await loadDashboard();
      }
    }
    setDashboard(nextDashboard);
  }, [dashboard?.__generatedAt]);

  useEffect(() => {
    refreshDashboard();
  }, [refreshDashboard]);

  if (!dashboard) {
    return <main className="page"><p className="empty-state">正在读取看板数据...</p></main>;
  }

  return <DashboardView dashboard={dashboard} onRefresh={refreshDashboard} />;
}
