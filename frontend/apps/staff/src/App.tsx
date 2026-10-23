import { lazy, Suspense } from "react";
import { Navigate, Route, Routes } from "react-router-dom";

import { FullPageSpinner, LockScreen, Shell } from "./layout/Shell";
import { NAV } from "./layout/nav";
import { useSession } from "./lib/session";
import { ForcePasswordChange } from "./pages/AccountDialogs";
import { ComingSoonPage } from "./pages/ComingSoonPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";

const HelpDeskPage = lazy(() => import("./pages/HelpDeskPage"));
const VerificationQueuePage = lazy(() => import("./pages/VerificationQueuePage"));
const VerifyOrderPage = lazy(() => import("./pages/VerifyOrderPage"));
const WaiversPage = lazy(() => import("./pages/WaiversPage"));
const OrdersPage = lazy(() => import("./pages/OrdersPage"));
const OrderDetailPage = lazy(() => import("./pages/OrderDetailPage"));
const PatientsPage = lazy(() => import("./pages/PatientsPage"));
const CatalogPage = lazy(() => import("./pages/CatalogPage"));
const StaffAdminPage = lazy(() => import("./pages/StaffAdminPage"));
const TellerPage = lazy(() => import("./pages/TellerPage"));
const CashierPage = lazy(() => import("./pages/CashierPage"));
const RefundsPage = lazy(() => import("./pages/RefundsPage"));
const ReconciliationPage = lazy(() => import("./pages/ReconciliationPage"));

export function App() {
  const { me, loading, locked } = useSession();
  if (loading) return <FullPageSpinner />;
  if (!me) return <LoginPage />;
  if (me.must_change_password) return <ForcePasswordChange />;
  const later = NAV.flatMap((g) => g.items).filter((i) => i.milestone);
  return (
    <>
      <Shell>
        <Suspense fallback={<div className="py-20 text-center text-sand-400">…</div>}>
          <Routes>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/helpdesk" element={<HelpDeskPage />} />
            <Route path="/verification" element={<VerificationQueuePage />} />
            <Route path="/verification/:orderId" element={<VerifyOrderPage />} />
            <Route path="/waivers" element={<WaiversPage />} />
            <Route path="/orders" element={<OrdersPage />} />
            <Route path="/orders/:ref" element={<OrderDetailPage />} />
            <Route path="/patients" element={<PatientsPage />} />
            <Route path="/admin/catalog" element={<CatalogPage />} />
            <Route path="/admin/staff" element={<StaffAdminPage />} />
            <Route path="/teller" element={<TellerPage />} />
            <Route path="/cashier" element={<CashierPage />} />
            <Route path="/refunds" element={<RefundsPage />} />
            <Route path="/reconciliation" element={<ReconciliationPage />} />
            {later.map((item) => (
              <Route key={item.key} path={item.path} element={<ComingSoonPage item={item} />} />
            ))}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </Shell>
      {locked && <LockScreen />}
    </>
  );
}
