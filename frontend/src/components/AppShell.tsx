import { NavLink, Outlet } from "react-router";

import { RewardToaster } from "./RewardToaster";

const NAV_ITEMS = [
  { to: "/", label: "Accueil", icon: "M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" },
  { to: "/recherche", label: "Recherche", icon: "M10.5 4a6.5 6.5 0 1 0 4.03 11.6l4.43 4.43 1.41-1.41-4.43-4.43A6.5 6.5 0 0 0 10.5 4m0 2a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9" },
  { to: "/suivi", label: "Suivi", icon: "M14 10H3v2h11zm0-4H3v2h11zM3 16h7v-2H3zm18.5-4.5L23 13l-6.99 7-4.51-4.5L13 14l3.01 3z" },
  { to: "/bibliotheques", label: "Biblio", icon: "M4 6H2v14a2 2 0 0 0 2 2h14v-2H4zm16-4H8a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2m0 10-2.5-1.5L15 12V4h5z" },
  { to: "/cartes", label: "Cartes", icon: "M2.53 19.65l1.34.56v-9.03l-2.43 5.86c-.41 1.02.08 2.19 1.09 2.61m19.5-3.7L17.07 3.98a2.01 2.01 0 0 0-1.81-1.23c-.26 0-.53.04-.79.15L7.1 5.95a2 2 0 0 0-1.08 2.6l4.96 11.97a2 2 0 0 0 2.6 1.08l7.36-3.05a2 2 0 0 0 1.09-2.6M7.88 8.75c-.55 0-1-.45-1-1s.45-1 1-1 1 .45 1 1-.45 1-1 1m-2 11c0 1.1.9 2 2 2h1.45l-3.45-8.34z" },
  { to: "/profil", label: "Profil", icon: "M19 5h-2V3H7v2H5a2 2 0 0 0-2 2v1c0 2.55 1.92 4.63 4.39 4.94A5 5 0 0 0 11 15.9V19H7v2h10v-2h-4v-3.1a5 5 0 0 0 3.61-2.96C19.08 12.63 21 10.55 21 8V7a2 2 0 0 0-2-2M5 8V7h2v3.82A3 3 0 0 1 5 8m14 0a3 3 0 0 1-2 2.82V7h2z" },
];

/** Cadre des pages connectées : contenu + barre de navigation en bas
 * (à portée de pouce sur mobile). */
export function AppShell() {
  return (
    <div className="min-h-dvh pb-20">
      <Outlet />
      <RewardToaster />
      <nav
        aria-label="Navigation principale"
        className="fixed inset-x-0 bottom-0 border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
      >
        <ul className="mx-auto flex max-w-lg">
          {NAV_ITEMS.map((item) => (
            <li key={item.to} className="flex-1">
              <NavLink
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex flex-col items-center gap-1 px-0.5 py-2.5 text-[11px] font-medium ${
                    isActive ? "text-accent" : "text-muted hover:text-text"
                  }`
                }
              >
                <svg aria-hidden="true" viewBox="0 0 24 24" className="h-6 w-6 fill-current">
                  <path d={item.icon} />
                </svg>
                {item.label}
              </NavLink>
            </li>
          ))}
        </ul>
      </nav>
    </div>
  );
}
