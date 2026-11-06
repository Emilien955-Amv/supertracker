import { BrowserRouter, Navigate, Route, Routes } from "react-router";

import { AuthProvider } from "./auth/AuthContext";
import { GuestOnly, RequireAuth } from "./auth/guards";
import { AppShell } from "./components/AppShell";
import BinderPage from "./pages/BinderPage";
import CardsPage from "./pages/CardsPage";
import PackPage from "./pages/PackPage";
import ContentPage from "./pages/ContentPage";
import HomePage from "./pages/HomePage";
import LibrariesPage from "./pages/LibrariesPage";
import LibraryPage from "./pages/LibraryPage";
import LoginPage from "./pages/LoginPage";
import FriendsPage from "./pages/FriendsPage";
import ProfilePage from "./pages/ProfilePage";
import RequestsPage from "./pages/RequestsPage";
import UserProfilePage from "./pages/UserProfilePage";
import RegisterPage from "./pages/RegisterPage";
import SearchPage from "./pages/SearchPage";
import TrackingListPage from "./pages/TrackingListPage";

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
        <Route path="/suivi" element={<TrackingListPage />} />
        <Route path="/bibliotheques" element={<LibrariesPage />} />
        <Route path="/bibliotheques/:id" element={<LibraryPage />} />
        <Route path="/profil" element={<ProfilePage />} />
        <Route path="/amis" element={<FriendsPage />} />
        <Route path="/u/:username" element={<UserProfilePage />} />
        <Route path="/cartes" element={<CardsPage />} />
        <Route path="/cartes/pack/:theme" element={<PackPage />} />
        <Route path="/cartes/oeuvre/:id" element={<BinderPage />} />
        <Route path="/cartes/demandes" element={<RequestsPage />} />
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
