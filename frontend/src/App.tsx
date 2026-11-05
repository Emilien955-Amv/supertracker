import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { AuthProvider } from "./auth/AuthContext";
import { GuestOnly, RequireAuth } from "./auth/guards";
import { AppShell } from "./components/AppShell";
import ContentPage from "./pages/ContentPage";
import HomePage from "./pages/HomePage";
import LoginPage from "./pages/LoginPage";
import RegisterPage from "./pages/RegisterPage";
import SearchPage from "./pages/SearchPage";

/** Table des routes : quelle page afficher pour quelle adresse. */
export function AppRoutes() {
  return (
    <Routes>
      {/* Pages connectées : protégées par RequireAuth, dans le cadre commun
          (barre de navigation en bas). Les routes « enfants » s'affichent à
          l'emplacement <Outlet /> d'AppShell. */}
      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<HomePage />} />
        <Route path="/recherche" element={<SearchPage />} />
        <Route path="/contenu/:source/:kind/:id" element={<ContentPage />} />
      </Route>

      <Route
        path="/connexion"
        element={
          <GuestOnly>
            <LoginPage />
          </GuestOnly>
        }
      />
      <Route
        path="/inscription"
        element={
          <GuestOnly>
            <RegisterPage />
          </GuestOnly>
        }
      />
      {/* Adresse inconnue : retour à l'accueil. */}
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <AppRoutes />
      </BrowserRouter>
    </AuthProvider>
  );
}
