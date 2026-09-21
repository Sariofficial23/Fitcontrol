import { NavLink, Navigate, Route, Routes } from "react-router-dom";
import { useI18n } from "./i18n";
import { useApp } from "./state";
import { ErrorState, Loading } from "./ui";
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

function Header() {
  const { t, lang, setLang } = useI18n();
  const { me, activeClub, selectClub } = useApp();
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
        <select
          className="select-sm"
          value={lang}
          onChange={(e) => setLang(e.target.value as "ru" | "uz")}
        >
          <option value="ru">RU</option>
          <option value="uz">UZ</option>
        </select>
      </div>
    </header>
  );
}

function BottomNav() {
  const { t } = useI18n();
  const { me } = useApp();
  const tabs = [
    { to: "/overview", label: t("nav_overview"), icon: "📊" },
    { to: "/clients", label: t("nav_clients"), icon: "👥" },
    { to: "/subscriptions", label: t("nav_subscriptions"), icon: "🎫" },
    { to: "/visits", label: t("nav_visits"), icon: "✅" },
    { to: "/finance", label: t("nav_finance"), icon: "💰" },
    { to: "/settings", label: t("nav_settings"), icon: "⚙️" },
    ...(me?.user.is_platform_admin
      ? [{ to: "/platform", label: t("nav_platform"), icon: "🛠" }]
      : []),
  ];
  return (
    <nav className="bottom-nav">
      {tabs.map((tab) => (
        <NavLink
          key={tab.to}
          to={tab.to}
          className={({ isActive }) => `nav-item ${isActive ? "active" : ""}`}
        >
          <span className="nav-icon">{tab.icon}</span>
          <span className="nav-label">{tab.label}</span>
        </NavLink>
      ))}
    </nav>
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
