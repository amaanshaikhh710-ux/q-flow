import { lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthProvider } from './store/AuthContext';
import { ProtectedRoute } from './components/ProtectedRoute';
import { ErrorBoundary } from './components/ErrorBoundary';

// Lazy-loaded Patient pages for optimized production bundle splitting
const LandingPage = lazy(() => import('./pages/patient/LandingPage'));
const LoginPage = lazy(() => import('./pages/patient/LoginPage'));
const RegisterPage = lazy(() => import('./pages/patient/RegisterPage'));
const PatientDashboardPage = lazy(() => import('./pages/patient/PatientDashboardPage'));
const HospitalSelectPage = lazy(() => import('./pages/patient/HospitalSelectPage'));
const DepartmentSelectPage = lazy(() => import('./pages/patient/DepartmentSelectPage'));
const DoctorSelectPage = lazy(() => import('./pages/patient/DoctorSelectPage'));
const DoctorAvailabilityPage = lazy(() => import('./pages/patient/DoctorAvailabilityPage'));
const QueueTicketPage = lazy(() => import('./pages/patient/QueueTicketPage'));
const TravelSetupPage = lazy(() => import('./pages/patient/TravelSetupPage'));
const ArrivalPlanPage = lazy(() => import('./pages/patient/ArrivalPlanPage'));
const NotFoundPage = lazy(() => import('./pages/patient/NotFoundPage'));

// Lazy-loaded Staff pages
const StaffLandingPage = lazy(() => import('./pages/staff/StaffLandingPage'));
const QueueControlPage = lazy(() => import('./pages/staff/QueueControlPage'));
const StaffHistoricalReportsPage = lazy(() =>
  import('./pages/staff/StaffHistoricalReportsPage').then((m) => ({ default: m.StaffHistoricalReportsPage }))
);

function PageLoadingFallback() {
  return (
    <div className="min-h-screen bg-slate-50 flex items-center justify-center p-4">
      <div className="flex flex-col items-center gap-3">
        <div className="w-9 h-9 border-2 border-emerald-600 border-t-transparent rounded-full animate-spin" />
        <p className="text-xs font-semibold text-slate-500 tracking-wider uppercase">Loading Q-FLOW...</p>
      </div>
    </div>
  );
}

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: true,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <Suspense fallback={<PageLoadingFallback />}>
              <Routes>
              {/* Public */}
              <Route path="/" element={<LandingPage />} />
              <Route path="/login" element={<LoginPage />} />
              <Route path="/register" element={<RegisterPage />} />

              {/* Patient Core Dashboard & Simplified Booking */}
              <Route
                path="/dashboard"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <PatientDashboardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/appointments"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <PatientDashboardPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/book"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <Navigate to="/hospitals" replace />
                  </ProtectedRoute>
                }
              />

              {/* Discovery — accessible to patient only */}
              <Route
                path="/hospitals"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <HospitalSelectPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/departments/:hospitalId"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <DepartmentSelectPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/doctors/:departmentId"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <DoctorSelectPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/sessions/:doctorId"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <DoctorAvailabilityPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/doctor-availability/:doctorId"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <DoctorAvailabilityPage />
                  </ProtectedRoute>
                }
              />


              {/* Patient ticket + travel */}
              <Route
                path="/ticket/:entryId"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <QueueTicketPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/travel/:entryId"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <TravelSetupPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/travel-setup/:entryId"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <TravelSetupPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/arrival-plan/:entryId"
                element={
                  <ProtectedRoute requiredRole="patient">
                    <ArrivalPlanPage />
                  </ProtectedRoute>
                }
              />

              {/* Staff Control Center */}
              <Route
                path="/staff"
                element={
                  <ProtectedRoute requiredRole={['staff', 'admin']}>
                    <StaffLandingPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/staff/queue/:queueId"
                element={
                  <ProtectedRoute requiredRole={['staff', 'admin']}>
                    <QueueControlPage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/staff/historical"
                element={
                  <ProtectedRoute requiredRole={['staff', 'admin']}>
                    <StaffHistoricalReportsPage />
                  </ProtectedRoute>
                }
              />

              {/* Fallback to dedicated 404 / NotFound Page */}
              <Route path="*" element={<NotFoundPage />} />
            </Routes>
          </Suspense>
        </BrowserRouter>
      </AuthProvider>
    </QueryClientProvider>
  </ErrorBoundary>
  );
}
