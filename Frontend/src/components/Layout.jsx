import { NavLink, Outlet } from "react-router-dom";

const LINKS = [
  { to: "/home", label: "Home" },
  { to: "/history", label: "Scan History" },
  { to: "/models", label: "Model Evaluation" },
];

const STATUS_TEXT = { checking: "connecting...", online: "online", offline: "offline" };

export default function Layout({ status, onRetry, models }) {
  return (
    <>
      <header className="topbar">
        <div className="container topbar-inner">
          <div className="brand">
            <div className="logo">LC</div>
            <div>
              <div className="site-title">Lung Cancer Detection from CT Scans</div>
              <div className="site-sub">MSc Project &ndash; CNN, VGG16 and InceptionV3 comparison</div>
            </div>
          </div>
          <div className={`server server-${status}`}>Server: {STATUS_TEXT[status]}</div>
        </div>
      </header>

      <nav className="navbar">
        <div className="container">
          {LINKS.map((l) => (
            <NavLink key={l.to} to={l.to} end={l.to !== "/history"}>
              {l.label}
            </NavLink>
          ))}
        </div>
      </nav>

      <main className="container main">
        {status === "offline" && (
          <div className="alert alert-error">
            Cannot connect to the Flask server. Start it with <code>python app.py</code> inside the Backend folder.{" "}
            <button className="btn btn-small" onClick={onRetry}>Retry</button>
          </div>
        )}
        <Outlet context={{ models, status }} />
      </main>

      <footer className="footer">
        <div className="container">
          This is an academic prototype built for an MSc research project. It is not a medical device and must not be
          used for clinical diagnosis.
        </div>
      </footer>
    </>
  );
}
