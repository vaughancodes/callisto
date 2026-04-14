import { Route, Routes } from "react-router-dom";
import { ProtectedRoute } from "./components/ProtectedRoute";
import { DashboardLayout } from "./layouts/DashboardLayout";
import { AdminPage } from "./pages/AdminPage";
import { AnalyticsPage } from "./pages/AnalyticsPage";
import { AuthCallbackPage } from "./pages/AuthCallbackPage";
import { CallDetailPage } from "./pages/CallDetailPage";
import { ContactDetailPage } from "./pages/ContactDetailPage";
import { ContactsPage } from "./pages/ContactsPage";
import { DashboardPage } from "./pages/DashboardPage";
import { LoginPage } from "./pages/LoginPage";
import { TemplatesPage } from "./pages/TemplatesPage";
import { TenantSettingsPage } from "./pages/TenantSettingsPage";

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/auth/callback" element={<AuthCallbackPage />} />
      <Route
        element={
          <ProtectedRoute>
            <DashboardLayout />
          </ProtectedRoute>
        }
      >
        <Route path="/" element={<DashboardPage />} />
        <Route path="/calls/:callId" element={<CallDetailPage />} />
        <Route path="/contacts" element={<ContactsPage />} />
        <Route path="/contacts/:contactId" element={<ContactDetailPage />} />
        <Route path="/templates" element={<TemplatesPage />} />
        <Route path="/tenant-settings" element={<TenantSettingsPage />} />
        <Route path="/analytics" element={<AnalyticsPage />} />
        <Route path="/admin" element={<AdminPage />} />
      </Route>
    </Routes>
  );
}
