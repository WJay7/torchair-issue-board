const SUPABASE_URL = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
const SESSION_KEY = "torchair-supabase-session";

export const hasSupabaseConfig = Boolean(SUPABASE_URL && SUPABASE_KEY);

export function getStoredSession() {
  if (typeof window === "undefined") return null;
  try {
    return JSON.parse(window.localStorage.getItem(SESSION_KEY) || "null");
  } catch {
    return null;
  }
}

export function clearSession() {
  window.localStorage.removeItem(SESSION_KEY);
}

export async function signIn(email, password) {
  const response = await fetch(`${SUPABASE_URL}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { apikey: SUPABASE_KEY, "Content-Type": "application/json" },
    body: JSON.stringify({ email, password }),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(payload.error_description || payload.msg || "登录失败");
  window.localStorage.setItem(SESSION_KEY, JSON.stringify(payload));
  return payload;
}

async function restRequest(path, session, options = {}) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...options,
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${session.access_token}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.message || payload.details || "云端数据操作失败");
  }
  return response.status === 204 ? null : response.json();
}

export function listDutySchedules(session) {
  return restRequest("duty_schedules?select=duty_date,person_name&order=duty_date.asc", session);
}

export function listDutyMembers(session) {
  return restRequest("duty_members?select=person_name,gitcode_account&order=person_name.asc", session);
}

export function saveDutySchedule(session, date, name) {
  return restRequest("duty_schedules?on_conflict=duty_date", session, {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify({ duty_date: date, person_name: name, updated_at: new Date().toISOString() }),
  });
}

export function deleteDutySchedule(session, date) {
  return restRequest(`duty_schedules?duty_date=eq.${encodeURIComponent(date)}`, session, { method: "DELETE" });
}

export function saveDutyMember(session, name, account) {
  return restRequest("duty_members?on_conflict=person_name", session, {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify({ person_name: name, gitcode_account: account, updated_at: new Date().toISOString() }),
  });
}

export function deleteDutyMember(session, name) {
  return restRequest(`duty_members?person_name=eq.${encodeURIComponent(name)}`, session, { method: "DELETE" });
}
