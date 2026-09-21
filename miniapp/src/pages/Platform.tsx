import { useEffect, useState } from "react";
import { api } from "../api";
import { formatDate } from "../format";
import { useI18n } from "../i18n";
import { confirmDanger } from "../telegram";
import { Badge, Card, EmptyState, ErrorState, Field, Loading, Modal } from "../ui";
import type { ActivationCode, PlatformClub } from "../types";

function tone(status: string): string {
  if (status === "active" || status === "trial") return "success";
  if (status === "expired" || status === "suspended") return "danger";
  return "neutral";
}

export default function Platform() {
  const { t, lang } = useI18n();
  const [tab, setTab] = useState<"clubs" | "codes">("clubs");
  const [clubs, setClubs] = useState<PlatformClub[] | null>(null);
  const [codes, setCodes] = useState<ActivationCode[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [showGen, setShowGen] = useState(false);

  async function load() {
    setLoading(true);
    setErr(null);
    try {
      const [c, k] = await Promise.all([
        api<PlatformClub[]>("/platform/clubs", { clubScoped: false }),
        api<ActivationCode[]>("/platform/activation-codes", { clubScoped: false }),
      ]);
      setClubs(c);
      setCodes(k);
    } catch (e: any) {
      setErr(e?.message ?? t("error"));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function extend(club: PlatformClub) {
    const days = Number(window.prompt(t("extend_days"), "30"));
    if (!days || days <= 0) return;
    await api(`/platform/clubs/${club.id}/extend`, {
      method: "POST",
      body: { days },
      clubScoped: false,
    });
    load();
  }

  async function toggleSuspend(club: PlatformClub) {
    const suspend = club.subscription_status !== "suspended";
    if (suspend && !(await confirmDanger(t("suspend") + "?"))) return;
    await api(`/platform/clubs/${club.id}/${suspend ? "suspend" : "resume"}`, {
      method: "POST",
      clubScoped: false,
    });
    load();
  }

  return (
    <div>
      <h2>{t("nav_platform")}</h2>
      <div className="pills">
        <button className={`pill ${tab === "clubs" ? "active" : ""}`} onClick={() => setTab("clubs")}>
          {t("platform_clubs")}
        </button>
        <button className={`pill ${tab === "codes" ? "active" : ""}`} onClick={() => setTab("codes")}>
          {t("platform_codes")}
        </button>
      </div>

      {loading && <Loading />}
      {err && <ErrorState message={err} onRetry={load} />}

      {tab === "clubs" && clubs && !loading && (
        <Card>
          {clubs.length === 0 && <EmptyState />}
          {clubs.map((c) => (
            <div className="row" key={c.id}>
              <div>
                <div>{c.name}</div>
                <div className="muted small">
                  {c.plan_tier ?? "—"} ·{" "}
                  {c.expires_at ? formatDate(c.expires_at, lang) : "∞"}
                  {c.days_left != null ? ` · ${c.days_left}${t("days")[0]}` : ""}
                  {c.owner_telegram_id ? ` · TG ${c.owner_telegram_id}` : ""}
                </div>
              </div>
              <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                <Badge text={c.subscription_status} tone={tone(c.subscription_status)} />
                <button className="btn btn-secondary" onClick={() => extend(c)}>
                  {t("extend")}
                </button>
                <button className="icon-btn" title={t("suspend")} onClick={() => toggleSuspend(c)}>
                  {c.subscription_status === "suspended" ? "▶" : "⏸"}
                </button>
              </div>
            </div>
          ))}
        </Card>
      )}

      {tab === "codes" && codes && !loading && (
        <>
          <button className="btn btn-block" onClick={() => setShowGen(true)}>
            + {t("gen_code")}
          </button>
          <div style={{ height: 12 }} />
          <Card>
            {codes.length === 0 && <EmptyState />}
            {codes.map((k) => (
              <div className="row" key={k.id}>
                <div>
                  <div style={{ fontFamily: "monospace" }}>{k.code}</div>
                  <div className="muted small">
                    {k.plan_tier} · {k.duration_days}
                    {t("days")[0]} · {k.uses_count}/{k.max_uses}
                    {k.is_trial ? ` · ${t("is_trial")}` : ""}
                  </div>
                </div>
                <Badge
                  text={k.status}
                  tone={k.status === "active" && k.uses_count < k.max_uses ? "success" : "neutral"}
                />
              </div>
            ))}
          </Card>
        </>
      )}

      {showGen && (
        <GenCodeModal
          onClose={() => setShowGen(false)}
          onDone={() => {
            setShowGen(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function GenCodeModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const [form, setForm] = useState({
    plan_tier: "basic",
    duration_days: "30",
    is_trial: false,
    max_uses: "1",
  });
  const [created, setCreated] = useState<ActivationCode | null>(null);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    setBusy(true);
    setErr(null);
    try {
      const ac = await api<ActivationCode>("/platform/activation-codes", {
        method: "POST",
        clubScoped: false,
        body: {
          plan_tier: form.plan_tier || "basic",
          duration_days: Number(form.duration_days),
          is_trial: form.is_trial,
          max_uses: Number(form.max_uses),
        },
      });
      setCreated(ac);
    } catch (e: any) {
      setErr(e?.message ?? t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={t("gen_code")} onClose={created ? onDone : onClose}>
      {err && <div className="field-error">{err}</div>}
      {created ? (
        <div style={{ textAlign: "center" }}>
          <p>{t("code_created")}:</p>
          <h2 style={{ fontFamily: "monospace", letterSpacing: 1 }}>{created.code}</h2>
          <p className="muted small">
            {created.plan_tier} · {created.duration_days} {t("days")}
            {created.is_trial ? ` · ${t("is_trial")}` : ""}
          </p>
          <button className="btn btn-block" onClick={onDone}>
            {t("save")}
          </button>
        </div>
      ) : (
        <>
          <Field label={t("plan_tier")}>
            <input
              value={form.plan_tier}
              onChange={(e) => setForm({ ...form, plan_tier: e.target.value })}
            />
          </Field>
          <Field label={t("duration_days")}>
            <input
              type="number"
              value={form.duration_days}
              onChange={(e) => setForm({ ...form, duration_days: e.target.value })}
            />
          </Field>
          <Field label={t("max_uses")}>
            <input
              type="number"
              value={form.max_uses}
              onChange={(e) => setForm({ ...form, max_uses: e.target.value })}
            />
          </Field>
          <label className="row" style={{ cursor: "pointer" }}>
            <span>{t("is_trial")}</span>
            <input
              type="checkbox"
              style={{ width: 20, height: 20 }}
              checked={form.is_trial}
              onChange={(e) => setForm({ ...form, is_trial: e.target.checked })}
            />
          </label>
          <button className="btn btn-block" disabled={busy} onClick={submit}>
            {t("gen_code")}
          </button>
        </>
      )}
    </Modal>
  );
}
