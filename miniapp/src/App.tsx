import { useState } from "react";
import { NavLink, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useI18n } from "./i18n";
import { useApp } from "./state";
import { ErrorState, Loading } from "./ui";
import {
  IconClients,
  IconFinance,
  IconMoon,
  IconOverview,
  IconPlans,
  IconPlatform,
  IconPlus,
  IconSettings,
  IconSun,
  IconVisits,
} from "./icons";
import Onboarding from "./pages/Onboarding";
import Overview from "./pages/Overview";
import Clients from "./pages/Clients";
import ClientDetail from "./pages/ClientDetail";
import Subscriptions from "./pages/Subscriptions";
import Visits from "./pages/Visits";
import Finance from "./pages/Finance";
import Settings from "./pages/Settings";
import Platform from "./pages/Platform";
import SubscriptionBlocked from "./pages/SubscriptionBlocked";

function resolvedTheme(): "light" | "dark" {
  const attr = document.documentElement.getAttribute("data-theme");
  if (attr === "light" || attr === "dark") return attr;
  return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

function Header() {
  const { t, lang, setLang } = useI18n();
  const { me, activeClub, selectClub } = useApp();
  const nav = useNavigate();
  const [theme, setThemeState] = useState<"light" | "dark">(resolvedTheme());

  function toggleTheme() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    try {
      localStorage.setItem("fc_theme", next);
    } catch {
      /* ignore */
    }
    setThemeState(next);
  }

  return (
    <header className="app-header">
      <div className="brand">{t("app_name")}</div>
      <div className="header-controls">
        {me && me.clubs.length > 1 && activeClub && (
          <select
            className="select-sm"
            value={activeClub.club.id}
            onChange={(e) => selectClub(Number(e.target.value))}
          >
            {me.clubs.map((c) => (
              <option key={c.club.id} value={c.club.id}>
                {c.club.name}
              </option>
            ))}
          </select>
        )}
        <button
          className="hdr-btn"
          onClick={toggleTheme}
          aria-label="Theme"
          title={theme === "dark" ? "Светлая тема" : "Тёмная тема"}
        >
          {theme === "dark" ? <IconSun /> : <IconMoon />}
        </button>
        <select
          className="select-sm"
          value={lang}
          onChange={(e) => setLang(e.target.value as "ru" | "uz")}
        >
          <option value="ru">RU</option>
          <option value="uz">UZ</option>
        </select>
        {me?.user.is_platform_admin && (
          <button
            className="hdr-btn"
            onClick={() => nav("/platform")}
            aria-label={t("nav_platform")}
            title={t("nav_platform")}
          >
            <IconPlatform />
          </button>
        )}
        <button
          className="hdr-btn"
          onClick={() => nav("/settings")}
          aria-label={t("nav_settings")}
          title={t("nav_settings")}
        >
          <IconSettings />
        </button>
      </div>
    </header>
  );
}

function BottomNav() {
  const { t } = useI18n();
  const nav = useNavigate();
  const [sheet, setSheet] = useState(false);

  // Four tabs (2 left + 2 right) so the center FAB sits in an empty gap and
  // never overlaps a tab. Settings & Platform live in the header.
  const tabs = [
    { to: "/overview", label: t("nav_overview"), Icon: IconOverview },
    { to: "/clients", label: t("nav_clients"), Icon: IconClients },
    { to: "/subscriptions", label: t("nav_subscriptions"), Icon: IconPlans },
    { to: "/finance", label: t("nav_finance"), Icon: IconFinance },
  ];

  function go(to: string) {
    setSheet(false);
    nav(to);
  }

  return (
    <>
      {sheet && (
        <div className="sheet-backdrop" onClick={() => setSheet(false)}>
          <div className="action-sheet" onClick={(e) => e.stopPropagation()}>
            <div className="sheet-title">{t("quick_actions")}</div>
            <button className="sheet-item" onClick={() => go("/visits")}>
              <IconVisits className="sheet-ic" />
              <span>{t("register_visit")}</span>
            </button>
            <button className="sheet-item" onClick={() => go("/clients")}>
              <IconClients className="sheet-ic" />
              <span>{t("new_client_action")}</span>
            </button>
            <button className="sheet-cancel" onClick={() => setSheet(false)}>
              {t("cancel")}
            </button>
          </div>
        </div>
      )}
      <nav className="bottom-nav nav-glow" style={{ ["--tabs" as string]: tabs.length } as Record<string, number>}>
        {tabs.map((tab) => {
          const Icon = tab.Icon;
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
            >
              <span className="nav-ic">
                <Icon className="nav-svg" />
              </span>
              <span className="nav-label">{tab.label}</span>
            </NavLink>
          );
        })}
        <button className="nav-fab" onClick={() => setSheet(true)} aria-label={t("quick_actions")}>
          <IconPlus />
        </button>
      </nav>
    </>
  );
}

export default function App() {
  const { loading, error, me, activeClub, subscription, reload } = useApp();

  if (loading) return <Loading />;
  if (error) return <ErrorState message={error} onRetry={reload} />;
  if (!me) return <ErrorState message="No session" onRetry={reload} />;

  if (!activeClub) {
    return (
      <div className="app">
        <Header />
        <main className="content">
          <Onboarding />
        </main>
      </div>
    );
  }

  // Server-side gate is authoritative; this mirrors it in the UI. Platform
  // admins are exempt (they need access to manage clubs).
  const blocked =
    subscription != null && !subscription.allowed && !me.user.is_platform_admin;
  if (blocked) {
    return (
      <div className="app">
        <Header />
        <main className="content">
          <SubscriptionBlocked />
        </main>
      </div>
    );
  }

  return (
    <div className="app">
      <Header />
      <main className="content">
        <Routes>
          <Route path="/" element={<Navigate to="/overview" replace />} />
          <Route path="/overview" element={<Overview />} />
          <Route path="/clients" element={<Clients />} />
          <Route path="/clients/:id" element={<ClientDetail />} />
          <Route path="/subscriptions" element={<Subscriptions />} />
          <Route path="/visits" element={<Visits />} />
          <Route path="/finance" element={<Finance />} />
          <Route path="/settings" element={<Settings />} />
          {me.user.is_platform_admin && (
            <Route path="/platform" element={<Platform />} />
          )}
          <Route path="*" element={<Navigate to="/overview" replace />} />
        </Routes>
      </main>
      <BottomNav />
    </div>
  );
}
