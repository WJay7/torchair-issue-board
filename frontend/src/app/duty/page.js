"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import {
  deleteDutyMember,
  deleteDutySchedule,
  hasSupabaseConfig,
  listDutyMembers,
  listDutySchedules,
  saveDutyMember,
  saveDutySchedule,
} from "../supabase-client";

const API_BASE_URL =
  process.env.NEXT_PUBLIC_DASHBOARD_API_BASE_URL ?? "http://127.0.0.1:8000";
const DUTY_PAST_DAYS = 7;
const DUTY_FUTURE_DAYS = 30;
const ASSET_BASE_PATH = process.env.NEXT_PUBLIC_BASE_PATH || "";

function localDateString(value = new Date()) {
  const offset = value.getTimezoneOffset() * 60000;
  return new Date(value.getTime() - offset).toISOString().slice(0, 10);
}

function buildDutyDates() {
  const today = new Date();
  return Array.from(
    { length: DUTY_PAST_DAYS + DUTY_FUTURE_DAYS },
    (_, index) => {
    const current = new Date(today);
      current.setDate(today.getDate() + index - DUTY_PAST_DAYS);
    return localDateString(current);
    }
  );
}

export default function DutySchedulePage() {
  const [todayAnchor, setTodayAnchor] = useState(localDateString);
  const dutyDates = useMemo(buildDutyDates, [todayAnchor]);
  const [schedules, setSchedules] = useState({});
  const [savedSchedules, setSavedSchedules] = useState({});
  const [members, setMembers] = useState([]);
  const [memberName, setMemberName] = useState("");
  const [memberAccount, setMemberAccount] = useState("");
  const [loading, setLoading] = useState(true);
  const [savingAll, setSavingAll] = useState(false);
  const [savingMember, setSavingMember] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");

  async function loadSchedules() {
    if (hasSupabaseConfig) {
      const rows = await listDutySchedules();
      const nextSchedules = Object.fromEntries(
        rows.map((row) => [row.duty_date, row.person_name])
      );
      setSchedules(nextSchedules);
      setSavedSchedules(nextSchedules);
      return;
    }
    const response = await fetch(`${API_BASE_URL}/api/duty-schedules`, {
      cache: "no-store",
    });
    if (!response.ok) throw new Error("排班数据读取失败");
    const scheduleRows = await response.json();
    const nextSchedules = Object.fromEntries(
      scheduleRows.map((row) => [row.date, row.name])
    );
    setSchedules(nextSchedules);
    setSavedSchedules(nextSchedules);
  }

  async function loadMembers() {
    if (hasSupabaseConfig) {
      const rows = await listDutyMembers();
      setMembers(rows.map((row) => ({ name: row.person_name, account: row.gitcode_account })));
      return;
    }
    const response = await fetch(`${API_BASE_URL}/api/duty-members`, {
      cache: "no-store",
    });
    if (!response.ok) throw new Error("人员账号数据读取失败");
    setMembers(await response.json());
  }

  async function loadData() {
    setLoading(true);
    setError("");
    try {
      await Promise.all([loadSchedules(), loadMembers()]);
    } catch (loadError) {
      setError(loadError.message || "排班数据读取失败");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadData();
  }, [todayAnchor]);

  useEffect(() => {
    const timer = window.setInterval(() => {
      const currentDate = localDateString();
      setTodayAnchor((previous) =>
        previous === currentDate ? previous : currentDate
      );
    }, 60000);
    return () => window.clearInterval(timer);
  }, []);

  function updateScheduleName(date, name) {
    setSchedules((current) => ({ ...current, [date]: name }));
  }

  async function saveAllSchedules() {
    setSavingAll(true);
    setError("");
    setNotice("");
    try {
      const operations = dutyDates
        .filter((date) => (schedules[date] ?? "").trim() !== (savedSchedules[date] ?? ""))
        .map(async (date) => {
          const name = (schedules[date] ?? "").trim();
          if (hasSupabaseConfig) {
            if (name) await saveDutySchedule(date, name);
            else await deleteDutySchedule(date);
            return;
          }
          const response = name
            ? await fetch(`${API_BASE_URL}/api/duty-schedules/${date}`, {
                method: "PUT",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ name }),
              })
            : await fetch(`${API_BASE_URL}/api/duty-schedules/${date}`, {
                method: "DELETE",
              });
          if (!response.ok && !(response.status === 404 && !name)) {
            throw new Error("排班保存失败");
          }
        });
      await Promise.all(operations);
      setSavedSchedules({ ...schedules });
      setNotice("排班已保存");
    } catch (saveError) {
      setError(saveError.message || "排班保存失败");
    } finally {
      setSavingAll(false);
    }
  }

  async function saveMember(event) {
    event.preventDefault();
    const name = memberName.trim();
    const account = memberAccount.trim();
    if (!name || !account) {
      setError("请填写姓名和 GitCode 账号");
      return;
    }
    setSavingMember(true);
    setError("");
    setNotice("");
    const previousMembers = members;
    const nextMembers = members
      .filter((member) => member.name !== name)
      .concat({ name, account })
      .sort((a, b) => a.name.localeCompare(b.name, "zh-Hans-CN"));
    setMembers(nextMembers);
    setMemberName("");
    setMemberAccount("");
    setNotice("正在保存对应关系...");
    try {
      if (hasSupabaseConfig) {
        await saveDutyMember(name, account);
        setNotice("对应关系已保存");
        return;
      }
      const response = await fetch(
        `${API_BASE_URL}/api/duty-members/${encodeURIComponent(name)}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ account }),
        }
      );
      if (!response.ok) throw new Error("人员账号保存失败");
      setNotice("对应关系已保存");
    } catch (saveError) {
      setMembers(previousMembers);
      setMemberName(name);
      setMemberAccount(account);
      setError(saveError.message || "人员账号保存失败");
      setNotice("");
    } finally {
      setSavingMember(false);
    }
  }

  async function deleteMember(name) {
    if (!window.confirm(`确定删除 ${name} 的账号对应关系吗？`)) return;
    setError("");
    setNotice("");
    try {
      if (hasSupabaseConfig) {
        await deleteDutyMember(name);
        setMembers((current) => current.filter((member) => member.name !== name));
        setNotice("对应关系已删除");
        return;
      }
      const response = await fetch(
        `${API_BASE_URL}/api/duty-members/${encodeURIComponent(name)}`,
        { method: "DELETE" }
      );
      if (!response.ok) throw new Error("人员账号删除失败");
      await loadMembers();
      setNotice("对应关系已删除");
    } catch (deleteError) {
      setError(deleteError.message || "人员账号删除失败");
    }
  }

  return (
    <main className="page duty-page">
      <section className="shell hero">
        <div className="hero-title">
          <img className="site-logo" src={`${ASSET_BASE_PATH}/torchair-logo.png`} alt="TorchAir" />
          <span className="hero-accent" aria-hidden="true" />
          <h1>值班排班管理</h1>
        </div>
        <div className="hero-actions">
          <Link className="manage-link" href="/">
          返回看板
          </Link>
        </div>
      </section>

      <section className="shell duty-layout">
        <section className="duty-list duty-calendar" aria-label="值班排班表">
          <div className="duty-heading">
            <div className="section-heading">
              <h2>值班排班表</h2>
              <p>在对应日期填写值班人员姓名，最后一次性保存全部修改。</p>
            </div>
            <button
              className="primary-button"
              type="button"
              onClick={saveAllSchedules}
              disabled={savingAll}
            >
              {savingAll ? "保存中" : "保存全部排班"}
            </button>
          </div>
          {loading ? <p className="empty-state">正在读取排班...</p> : null}
          <div className="schedule-table">
            <div className="schedule-row schedule-head">
              <span>日期</span>
              <span>值班人员姓名</span>
            </div>
            {dutyDates.map((date) => (
              <div className="schedule-row" key={date}>
                <span>{date}</span>
                <input
                  className="schedule-name-input"
                  value={schedules[date] ?? ""}
                  onChange={(event) => updateScheduleName(date, event.target.value)}
                  placeholder="填写姓名"
                  aria-label={`${date} 值班人员姓名`}
                />
              </div>
            ))}
          </div>
        </section>

        <section className="duty-list member-panel" aria-label="人员账号对应表">
          <div className="section-heading">
            <h2>姓名与 GitCode 账号对应表</h2>
            <p>自动分配 Issue 时，根据值班姓名查找 GitCode 账号。</p>
          </div>
          <form className="member-form" onSubmit={saveMember}>
            <input
              value={memberName}
              onChange={(event) => setMemberName(event.target.value)}
              placeholder="姓名"
              aria-label="姓名"
              maxLength={80}
            />
            <input
              value={memberAccount}
              onChange={(event) => setMemberAccount(event.target.value)}
              placeholder="GitCode 账号"
              aria-label="GitCode 账号"
              maxLength={120}
            />
            <button className="primary-button" type="submit" disabled={savingMember}>
              {savingMember ? "保存中" : "保存对应关系"}
            </button>
          </form>
          <div className="member-table">
            <div className="member-row member-head">
              <span>姓名</span>
              <span>GitCode 账号</span>
              <span>操作</span>
            </div>
            {members.length === 0 ? (
              <p className="empty-state">还没有人员账号对应关系</p>
            ) : (
              members.map((member) => (
                <div className="member-row" key={member.name}>
                  <strong>{member.name}</strong>
                  <span>{member.account}</span>
                  <button type="button" onClick={() => deleteMember(member.name)}>
                    删除
                  </button>
                </div>
              ))
            )}
          </div>
        </section>
      </section>
      {error ? <p className="shell form-error page-error">{error}</p> : null}
      {notice ? <p className="shell form-success page-error">{notice}</p> : null}
    </main>
  );
}
