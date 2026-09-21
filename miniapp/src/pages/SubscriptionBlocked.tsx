import { formatDate } from "../format";
import { useI18n } from "../i18n";
import { useApp } from "../state";
import { Card } from "../ui";

export default function SubscriptionBlocked() {
  const { t, lang } = useI18n();
  const { subscription } = useApp();
  const suspended = subscription?.status === "suspended";
  return (
    <div style={{ paddingTop: 24 }}>
      <Card>
        <div style={{ textAlign: "center" }}>
          <div style={{ fontSize: 42 }}>🔒</div>
          <h2 style={{ marginTop: 8 }}>{t("sub_expired_title")}</h2>
          <p className="muted">
            {suspended ? t("sub_suspended_text") : t("sub_expired_text")}
          </p>
          {subscription?.expires_at && (
            <p className="small">
              {t("sub_expires")}: {formatDate(subscription.expires_at, lang)}
            </p>
          )}
          <p className="small muted" style={{ marginTop: 12 }}>
            {t("renew_hint")}
          </p>
        </div>
      </Card>
    </div>
  );
}
