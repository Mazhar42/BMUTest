import { Logo } from "@bmu/ui";
import { lazy, Suspense, type ReactNode } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router-dom";

import { welcomed } from "./components/Layout";
import { useSession } from "./lib/session";
import { HomePage } from "./pages/HomePage";
import { LoginPage } from "./pages/LoginPage";
import { WelcomePage } from "./pages/WelcomePage";

const WhoForPage = lazy(() => import("./pages/WhoForPage"));
const AddFamilyPage = lazy(() => import("./pages/AddFamilyPage"));
const BookPage = lazy(() => import("./pages/BookPage"));
const OrdersPage = lazy(() => import("./pages/OrdersPage"));
const OrderPage = lazy(() => import("./pages/OrderPage"));
const ReportsPage = lazy(() => import("./pages/ReportsPage"));

function Splash() {
  return (
    <div className="grid min-h-dvh place-items-center bg-paper">
      <Logo />
    </div>
  );
}

function Private({ children }: { children: ReactNode }) {
  const { authed } = useSession();
  const location = useLocation();
  if (!authed) return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  return <>{children}</>;
}

export function App() {
  const { ready } = useSession();
  if (!ready) return <Splash />;
  return (
    <Suspense fallback={<Splash />}>
      <Routes>
        <Route path="/welcome" element={<WelcomePage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/" element={welcomed() ? <Private><HomePage /></Private> : <Navigate to="/welcome" replace />} />
        <Route path="/book" element={<Private><WhoForPage /></Private>} />
        <Route path="/book/:patientId" element={<Private><BookPage /></Private>} />
        <Route path="/family/new" element={<Private><AddFamilyPage /></Private>} />
        <Route path="/orders" element={<Private><OrdersPage /></Private>} />
        <Route path="/orders/:ref" element={<Private><OrderPage /></Private>} />
        <Route path="/o/:ref" element={<Private><OrderPage /></Private>} />
        <Route path="/reports" element={<Private><ReportsPage /></Private>} />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </Suspense>
  );
}
