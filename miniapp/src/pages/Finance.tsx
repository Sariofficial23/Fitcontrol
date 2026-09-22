import { useEffect, useState } from "react";
import { api } from "../api";
import { formatDate, formatMoney } from "../format";
import { useI18n } from "../i18n";
import { confirmDanger } from "../telegram";
import { atLeast, useApp } from "../state";
import { Card, EmptyState, ErrorState, Field, Loading, Modal, StatCard } from "../ui";
import type { DebtRow, Expense } from "../types";

interface IncomeByMethod {
  method: string;
  total: number;
  count: number;
}
interface IncomeReport {
  period_start: string;
  period_end: string;
  total_income: number;
  total_refunds: number;
  net_income: number;
  total_expenses: number;
  profit: number;
  by_method: IncomeByMethod[];
}

type Period = "today" | "7d" | "month";

const CAT_KEYS = ["cat_rent", "cat_salary", "cat_utilities", "cat_equipment", "cat_marketing", "cat_taxes", "cat_other"];

export default function Finance() {
  const { t, lang } = useI18n();
  const { role } = useApp();
  const isAdmin = atLeast(role, "club_admin");
  const [period, setPeriod] = useState<Period>("month");
  const [report, setReport] = useState<IncomeReport | null>(null);
  const [debts, setDebts] = useState<DebtRow[] | null>(null);
  const [expenses, setExpenses] = useState<Expense[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState<string | null>(null);
  const [showAdd, setShowAdd] = useState(false);

  async function load() {
    setLoading(true);
    setErr(null);
    try {
      const [r, d] = await Promise.all([
        api<IncomeReport>("/reports/income", { query: { period } }),
        api<DebtRow[]>("/debts"),
      ]);
      setReport(r);
      setDebts(d);
      if (isAdmin) {
        setExpenses(await api<Expense[]>("/expenses", { query: { period } }));
      }
    } catch (e: any) {
      setErr(e?.message ?? t("error"));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [period]);

  async function voidExpense(id: number) {
    if (!(await confirmDanger(t("confirm_void_expense")))) return;
    await api(`/expenses/${id}/void`, { method: "POST" });
    load();
  }

  return (
    <div>
      <h2>{t("nav_finance")}</h2>
      <div className="pills">
        {(["today", "7d", "month"] as Period[]).map((p) => (
          <button
            key={p}
            className={`pill ${period === p ? "active" : ""}`}
            onClick={() => setPeriod(p)}
          >
            {t(`period_${p}`)}
          </button>
        ))}
      </div>

      {loading && <Loading />}
      {err && <ErrorState message={err} onRetry={load} />}

      {report && !loading && (
        <>
          <div className="grid">
            <StatCard
              label={t("income")}
              value={formatMoney(report.total_income, lang)}
              accent="var(--success)"
            />
            {isAdmin && (
              <StatCard
                label={t("expenses")}
                value={formatMoney(report.total_expenses, lang)}
                accent="var(--danger)"
              />
            )}
            {isAdmin ? (
              <StatCard
                label={t("profit")}
                value={formatMoney(report.profit, lang)}
                accent={report.profit >= 0 ? "var(--success)" : "var(--danger)"}
              />
            ) : (
              <StatCard label={t("net_income")} value={formatMoney(report.net_income, lang)} />
            )}
          </div>

          <h3 style={{ margin: "16px 0 8px" }}>{t("method")}</h3>
          <Card>
            {report.by_method.length === 0 && <EmptyState />}
            {report.by_method.map((m) => (
              <div className="row" key={m.method}>
                <span>{t(`method_${m.method}`)}</span>
                <span>
                  {formatMoney(m.total, lang)} <span className="muted small">({m.count})</span>
                </span>
              </div>
            ))}
          </Card>
        </>
      )}

      {isAdmin && expenses && !loading && (
        <>
          <div className="row" style={{ marginTop: 16 }}>
            <h3>{t("expenses")}</h3>
            <button className="btn" onClick={() => setShowAdd(true)}>
              {t("add_expense")}
            </button>
          </div>
          <Card>
            {expenses.length === 0 && <EmptyState />}
            {expenses.map((e) => (
              <div className="row" key={e.id}>
                <div>
                  <div>{e.category}</div>
                  <div className="muted small">
                    {formatDate(e.spent_at, lang)}
                    {e.comment ? ` · ${e.comment}` : ""}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span style={{ color: "var(--danger)" }}>−{formatMoney(e.amount, lang)}</span>
                  <button className="icon-btn" title="✕" onClick={() => voidExpense(e.id)}>
                    🗑
                  </button>
                </div>
              </div>
            ))}
          </Card>
        </>
      )}

      <h3 style={{ margin: "16px 0 8px" }}>{t("debts")}</h3>
      {debts && (
        <Card>
          {debts.length === 0 && <EmptyState />}
          {debts.map((d) => (
            <div className="row" key={d.client_id}>
              <span>{d.client_name}</span>
              <span style={{ color: "var(--danger)" }}>{formatMoney(d.debt, lang)}</span>
            </div>
          ))}
        </Card>
      )}

      {showAdd && (
        <AddExpenseModal
          onClose={() => setShowAdd(false)}
          onDone={() => {
            setShowAdd(false);
            load();
          }}
        />
      )}
    </div>
  );
}

function AddExpenseModal({ onClose, onDone }: { onClose: () => void; onDone: () => void }) {
  const { t } = useI18n();
  const [amount, setAmount] = useState("");
  const [category, setCategory] = useState(t("cat_rent"));
  const [spentAt, setSpentAt] = useState(new Date().toISOString().slice(0, 10));
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  async function submit() {
    const amt = Number(amount);
    if (!amt || amt <= 0 || !category.trim()) {
      setErr(t("amount"));
      return;
    }
    setBusy(true);
    setErr(null);
    try {
      await api("/expenses", {
        method: "POST",
        body: {
          amount: amt,
          category: category.trim(),
          spent_at: spentAt,
          comment: comment || undefined,
        },
      });
      onDone();
    } catch (e: any) {
      setErr(e?.message ?? t("error"));
    } finally {
      setBusy(false);
    }
  }

  return (
    <Modal title={t("new_expense")} onClose={onClose}>
      {err && <div className="field-error">{err}</div>}
      <Field label={`${t("amount")} (UZS)`}>
        <input
          type="number"
          inputMode="numeric"
          value={amount}
          onChange={(e) => setAmount(e.target.value)}
        />
      </Field>
      <Field label={t("expense_category")}>
        <div className="pills" style={{ marginBottom: 8 }}>
          {CAT_KEYS.map((k) => (
            <button
              key={k}
              type="button"
              className={`pill ${category === t(k) ? "active" : ""}`}
              onClick={() => setCategory(t(k))}
            >
              {t(k)}
            </button>
          ))}
        </div>
        <input value={category} onChange={(e) => setCategory(e.target.value)} />
      </Field>
      <Field label={t("expense_date")}>
        <input type="date" value={spentAt} onChange={(e) => setSpentAt(e.target.value)} />
      </Field>
      <Field label={t("comment")}>
        <input value={comment} onChange={(e) => setComment(e.target.value)} />
      </Field>
      <button className="btn btn-block" disabled={busy} onClick={submit}>
        {t("save")}
      </button>
    </Modal>
  );
}
