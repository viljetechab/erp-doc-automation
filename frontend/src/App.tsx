import { useEffect, useMemo, useState } from 'react';
import { BrowserRouter, NavLink, Route, Routes, useLocation } from 'react-router-dom';
import {
  List,
  type LucideIcon,
  LogOut,
  Menu,
  Package,
  Upload,
  Users,
  X,
} from 'lucide-react';
import { Toaster } from 'react-hot-toast';

import { AuthProvider, useAuth } from './contexts/AuthContext';
import ProtectedRoute from './components/ProtectedRoute';

import UploadPage from './pages/UploadPage';
import OrderListPage from './pages/OrderListPage';
import OrderDetailPage from './pages/OrderDetailPage';
import LoginPage from './pages/LoginPage';
import OAuthCallbackPage from './pages/OAuthCallbackPage';
import CustomerImportPage from './pages/CustomerImportPage';
import ArticleImportPage from './pages/ArticleImportPage';
import ErrorBoundary from './components/ErrorBoundary';
import { BRAND } from './config/branding';

const NAV_ITEMS: Array<{
  to: string;
  label: string;
  description: string;
  icon: LucideIcon;
  end?: boolean;
}> = [
  {
    to: '/',
    label: 'Order Intake',
    description: 'Upload and extract',
    icon: Upload,
    end: true,
  },
  {
    to: '/orders',
    label: 'Orders',
    description: 'Review queue',
    icon: List,
  },
  {
    to: '/customers/import',
    label: 'Customers',
    description: 'Sync customer data',
    icon: Users,
  },
  {
    to: '/articles/import',
    label: 'Articles',
    description: 'Sync article data',
    icon: Package,
  },
];

function getPageContext(pathname: string) {
  if (pathname === '/') {
    return {
      eyebrow: 'Intake workspace',
      title: 'Capture incoming orders',
      description: 'Upload a PDF and open it in review.',
    };
  }

  if (pathname.startsWith('/orders/')) {
    return {
      eyebrow: 'Review workspace',
      title: 'Validate extracted order data',
      description: 'Check details, confirm matches, and export XML.',
    };
  }

  if (pathname.startsWith('/orders')) {
    return {
      eyebrow: 'Operations view',
      title: 'Track every order in flight',
      description: 'See review status and approvals in one place.',
    };
  }

  if (pathname.startsWith('/customers')) {
    return {
      eyebrow: 'Data sync',
      title: 'Refresh the customer master',
      description: 'Import the latest customer export.',
    };
  }

  if (pathname.startsWith('/articles')) {
    return {
      eyebrow: 'Catalogue sync',
      title: 'Maintain valid article numbers',
      description: 'Import the latest article catalogue.',
    };
  }

  return {
    eyebrow: 'Workspace',
    title: BRAND.appName,
    description: BRAND.appTagline,
  };
}

function AppLayout() {
  const { user, logout, isAuthenticated } = useAuth();
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname, isAuthenticated]);

  const pageContext = useMemo(
    () => getPageContext(location.pathname),
    [location.pathname],
  );

  return (
    <div className={`app-shell${isAuthenticated ? '' : ' app-shell-public'}`}>
      {isAuthenticated && (
        <>
          <button
            type="button"
            className={`app-overlay${navOpen ? ' visible' : ''}`}
            onClick={() => setNavOpen(false)}
            aria-label="Close navigation"
          />

          <aside className={`sidebar${navOpen ? ' is-open' : ''}`}>
            <div className="sidebar-brand">
              <div className="sidebar-logo">
                <img src={BRAND.logoPath} alt={BRAND.logoAlt} />
              </div>
              <div className="sidebar-brand-copy">
                <span className="sidebar-kicker">Order operations</span>
                <strong>{BRAND.appName}</strong>
                <p>AI order intake for ERP teams.</p>
              </div>
            </div>

            <nav className="sidebar-nav" aria-label="Primary">
              {NAV_ITEMS.map(({ to, label, description, icon: Icon, end }) => (
                <NavLink
                  key={to}
                  to={to}
                  end={end}
                  className={({ isActive }) =>
                    `sidebar-link${isActive ? ' active' : ''}`
                  }
                >
                  <span className="sidebar-link-icon">
                    <Icon size={18} />
                  </span>
                  <span className="sidebar-link-copy">
                    <strong>{label}</strong>
                    <small>{description}</small>
                  </span>
                </NavLink>
              ))}
            </nav>

            {user && (
              <div className="sidebar-user-card">
                <div className="sidebar-user-info">
                  {user.avatar_url ? (
                    <img
                      src={user.avatar_url}
                      alt=""
                      className="sidebar-user-avatar"
                    />
                  ) : (
                    <div className="sidebar-user-avatar-placeholder">
                      {user.display_name.charAt(0).toUpperCase()}
                    </div>
                  )}

                  <div className="sidebar-user-details">
                    <span className="sidebar-user-name">{user.display_name}</span>
                    <span className="sidebar-user-email">{user.email}</span>
                  </div>
                </div>

                <button
                  type="button"
                  className="sidebar-logout-btn"
                  onClick={() => void logout()}
                >
                  <LogOut size={14} />
                  Sign out
                </button>
              </div>
            )}
          </aside>
        </>
      )}

      <div className={`app-main-shell${isAuthenticated ? '' : ' public'}`}>
        {isAuthenticated && (
          <header className="app-topbar">
            <div className="app-topbar-left">
              <button
                type="button"
                className="mobile-nav-toggle"
                onClick={() => setNavOpen((open) => !open)}
                aria-label={navOpen ? 'Close navigation' : 'Open navigation'}
                aria-expanded={navOpen}
              >
                {navOpen ? <X size={18} /> : <Menu size={18} />}
              </button>

              <div className="app-topbar-copy">
                <span className="app-topbar-eyebrow">{pageContext.eyebrow}</span>
                <h1 className="app-topbar-title">{pageContext.title}</h1>
              </div>
            </div>

            {user && (
              <div className="app-topbar-right">
                <div className="app-status-pill">
                  <span className="app-status-dot" />
                  Live
                </div>

                <div className="topbar-user-chip">
                  <span className="topbar-user-name">{user.display_name}</span>
                  <span className="topbar-user-role">
                    {user.role.replace(/_/g, ' ')}
                  </span>
                </div>
              </div>
            )}
          </header>
        )}

        <main className={isAuthenticated ? 'main-content' : 'main-content-full'}>
          <Routes>
            <Route path="/login" element={<LoginPage />} />
            <Route
              path="/auth/microsoft/callback"
              element={<OAuthCallbackPage />}
            />

            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <UploadPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/orders"
              element={
                <ProtectedRoute>
                  <OrderListPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/orders/:orderId"
              element={
                <ProtectedRoute>
                  <OrderDetailPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/customers/import"
              element={
                <ProtectedRoute>
                  <CustomerImportPage />
                </ProtectedRoute>
              }
            />
            <Route
              path="/articles/import"
              element={
                <ProtectedRoute>
                  <ArticleImportPage />
                </ProtectedRoute>
              }
            />
          </Routes>
        </main>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ErrorBoundary>
          <AppLayout />
        </ErrorBoundary>
        <Toaster
          position="top-right"
          toastOptions={{
            duration: 4000,
            style: {
              borderRadius: '18px',
              border: '1px solid rgba(148, 163, 184, 0.22)',
              background: '#0f172a',
              color: '#f8fafc',
              boxShadow: '0 28px 60px rgba(15, 23, 42, 0.28)',
            },
          }}
        />
      </AuthProvider>
    </BrowserRouter>
  );
}
