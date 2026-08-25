const corsHeaders = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Headers": "authorization, x-client-info, apikey, content-type",
  "Access-Control-Allow-Methods": "POST, OPTIONS",
};

const json = (body: Record<string, unknown>, status = 200) =>
  new Response(JSON.stringify(body), {
    status,
    headers: { ...corsHeaders, "Content-Type": "application/json" },
  });

Deno.serve(async (request) => {
  if (request.method === "OPTIONS") return new Response("ok", { headers: corsHeaders });
  if (request.method !== "POST") return json({ error: "method_not_allowed" }, 405);

  const supabaseUrl = Deno.env.get("SUPABASE_URL");
  const serviceKey = Deno.env.get("SUPABASE_SERVICE_ROLE_KEY");
  const githubToken = Deno.env.get("GITHUB_ACTIONS_TOKEN");
  if (!supabaseUrl || !serviceKey || !githubToken) {
    return json({ error: "sync_service_not_configured" }, 500);
  }

  const supabaseHeaders = {
    apikey: serviceKey,
    Authorization: `Bearer ${serviceKey}`,
    "Content-Type": "application/json",
  };
  const controlUrl = `${supabaseUrl}/rest/v1/sync_control?id=eq.1`;
  const controlResponse = await fetch(`${controlUrl}&select=last_requested_at`, {
    headers: supabaseHeaders,
  });
  if (!controlResponse.ok) return json({ error: "sync_control_read_failed" }, 502);

  const controlRows = await controlResponse.json();
  const lastRequestedAt = controlRows[0]?.last_requested_at;
  if (lastRequestedAt) {
    const elapsed = Date.now() - Date.parse(lastRequestedAt);
    if (elapsed < 240000) {
      return json({ accepted: false, retryAfterSeconds: Math.ceil((240000 - elapsed) / 1000) });
    }
  }

  const updateResponse = await fetch(controlUrl, {
    method: "PATCH",
    headers: { ...supabaseHeaders, Prefer: "return=minimal" },
    body: JSON.stringify({ last_requested_at: new Date().toISOString() }),
  });
  if (!updateResponse.ok) return json({ error: "sync_control_update_failed" }, 502);

  const githubResponse = await fetch(
    "https://api.github.com/repos/WJay7/torchair-issue-board/actions/workflows/sync.yml/dispatches",
    {
      method: "POST",
      headers: {
        Accept: "application/vnd.github+json",
        Authorization: `Bearer ${githubToken}`,
        "X-GitHub-Api-Version": "2022-11-28",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ ref: "main" }),
    }
  );
  if (!githubResponse.ok) return json({ error: "github_workflow_dispatch_failed" }, 502);
  return json({ accepted: true });
});
