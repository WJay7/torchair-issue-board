const SUPABASE_URL = (process.env.NEXT_PUBLIC_SUPABASE_URL || "").replace(/\/$/, "");
const SUPABASE_KEY = process.env.NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY || "";
export const hasSupabaseConfig = Boolean(SUPABASE_URL && SUPABASE_KEY);

async function restRequest(path, options = {}) {
  const response = await fetch(`${SUPABASE_URL}/rest/v1/${path}`, {
    ...options,
    headers: {
      apikey: SUPABASE_KEY,
      Authorization: `Bearer ${SUPABASE_KEY}`,
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
  });
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.message || payload.details || "云端数据操作失败");
  }
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

export function listDutySchedules() {
  return restRequest("duty_schedules?select=duty_date,person_name&order=duty_date.asc");
}

export function listDutyMembers() {
  return restRequest("duty_members?select=person_name,gitcode_account&order=person_name.asc");
}

export function saveDutySchedule(date, name) {
  return restRequest("duty_schedules?on_conflict=duty_date", {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify({ duty_date: date, person_name: name, updated_at: new Date().toISOString() }),
  });
}

export function deleteDutySchedule(date) {
  return restRequest(`duty_schedules?duty_date=eq.${encodeURIComponent(date)}`, { method: "DELETE" });
}

export function saveDutyMember(name, account) {
  return restRequest("duty_members?on_conflict=person_name", {
    method: "POST",
    headers: { Prefer: "resolution=merge-duplicates,return=minimal" },
    body: JSON.stringify({ person_name: name, gitcode_account: account, updated_at: new Date().toISOString() }),
  });
}

export function deleteDutyMember(name) {
  return restRequest(`duty_members?person_name=eq.${encodeURIComponent(name)}`, { method: "DELETE" });
}
