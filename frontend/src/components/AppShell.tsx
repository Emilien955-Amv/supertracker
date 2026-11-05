import { NavLink, Outlet } from "react-router";

const NAV_ITEMS = [
  { to: "/", label: "Accueil", icon: "M3 11.5 12 4l9 7.5V20a1 1 0 0 1-1 1h-5v-6H9v6H4a1 1 0 0 1-1-1z" },
  { to: "/recherche", label: "Recherche", icon: "M10.5 4a6.5 6.5 0 1 0 4.03 11.6l4.43 4.43 1.41-1.41-4.43-4.43A6.5 6.5 0 0 0 10.5 4m0 2a4.5 4.5 0 1 1 0 9 4.5 4.5 0 0 1 0-9" },
];

/** Cadre des pages connectées : contenu + barre de navigation en bas
 * (à portée de pouce sur mobile). */
export function AppShell() {
  return (
    <div className="min-h-dvh pb-20">
      <Outlet />
      <nav
        aria-label="Navigation principale"
        className="fixed inset-x-0 bottom-0 border-t border-border bg-surface/95 pb-[env(safe-area-inset-bottom)] backdrop-blur"
      >
        <ul className="mx-auto flex max-w-md justify-around">
          {NAV_ITEMS.map((item) => (
            <li key={item.to}>
              <NavLink
                to={item.to}
                end={item.to === "/"}
                className={({ isActive }) =>
                  `flex flex-col items-center gap-1 px-6 py-2.5 text-xs font-medium ${
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
