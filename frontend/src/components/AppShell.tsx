import { NavLink, Outlet } from "react-router";

import { RewardToaster } from "./RewardToaster";

const NAV_ITEMS = [
  { to: "/", label: "Accueil", icon: "M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" },
  { to: "/recherche", label: "Recherche", icon: "M10.5 4a6.5 6.5 0 1 0 4.03 11.6l4.43 4.43 1.41-1.41-4.43-4.43A6.5 6.5 0 0 0 10.5 4m0 2a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9" },
  { to: "/suivi", label: "Suivi", icon: "M14 10H3v2h11zm0-4H3v2h11zM3 16h7v-2H3zm18.5-4.5L23 13l-6.99 7-4.51-4.5L13 14l3.01 3z" },
  { to: "/bibliotheques", label: "Biblio", icon: "M4 6H2v14a2 2 0 0 0 2 2h14v-2H4zm16-4H8a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V4a2 2 0 0 0-2-2m0 10-2.5-1.5L15 12V4h5z" },
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
        <ul className="mx-auto flex max-w-md">
          {NAV_ITEMS.map((item) => (
            <li key={item.to} className="flex-1">
              <NavLink
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex flex-col items-center gap-1 px-1 py-2.5 text-xs font-medium ${
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
