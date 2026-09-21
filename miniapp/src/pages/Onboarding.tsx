import { useState } from "react";
import { api } from "../api";
import { useI18n } from "../i18n";
import { useApp } from "../state";
import { Card, Field } from "../ui";
import type { Membership } from "../types";

export default function Onboarding() {
  const { t } = useI18n();
  const { reload } = useApp();
  const [code, setCode] = useState("");
  const [name, setName] = useState("");
  const [invite, setInvite] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function redeem() {
    if (!code.trim() || !name.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await api<Membership>("/activation/redeem", {
        method: "POST",
        body: { code: code.trim().toUpperCase(), name: name.trim() },
        clubScoped: false,
      });
      await reload();
    } catch (e: any) {
      setErr(e?.message ?? t("error"));
    } finally {
      setBusy(false);
    }
  }

  async function acceptInvite() {
    if (!invite.trim()) return;
    setBusy(true);
    setErr(null);
    try {
      await api<Membership>("/staff/invites/accept", {
        method: "POST",
        body: { code: invite },
        clubScoped: false,
      });
      await reload();
    } catch (e: any) {
      setErr(e?.message ?? t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div>
      <h2>{t("welcome")}</h2>
      <p className="muted">{t("onboarding_code_hint")}</p>
      {err && <div className="field-error">{err}</div>}

      <Card>
        <h3>{t("activate_club")}</h3>
        <div style={{ height: 12 }} />
        <Field label={t("activation_code")}>
          <input
            value={code}
            onChange={(e) => setCode(e.target.value.toUpperCase())}
            placeholder="FC-XXXXXXXXXX"
          />
        </Field>
        <Field label={t("club_name")}>
          <input value={name} onChange={(e) => setName(e.target.value)} />
        </Field>
        <button
          className="btn btn-block"
          disabled={busy || !code.trim() || !name.trim()}
          onClick={redeem}
        >
          {t("activate")}
        </button>
        <p className="muted small" style={{ marginTop: 8 }}>
          {t("no_code_hint")}
        </p>
      </Card>

      <Card>
        <h3>{t("accept_invite")}</h3>
        <div style={{ height: 12 }} />
        <Field label={t("invite_code")}>
          <input
            value={invite}
            onChange={(e) => setInvite(e.target.value.toUpperCase())}
            placeholder="ABCD1234"
          />
        </Field>
        <button
          className="btn btn-secondary btn-block"
          disabled={busy || !invite.trim()}
          onClick={acceptInvite}
        >
          {t("accept_invite")}
        </button>
      </Card>
    </div>
  );
}
