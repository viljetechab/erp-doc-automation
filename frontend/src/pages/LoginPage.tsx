import { useEffect, useState, type FormEvent } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { CheckCircle2, FileSearch, ShieldCheck } from 'lucide-react';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';
import { BRAND } from '../config/branding';

type Mode = 'login' | 'register';

const showcaseItems = [
  {
    icon: FileSearch,
    title: 'Fast document intake',
    description: 'Capture purchase orders, extract the key fields, and route them into review.',
  },
  {
    icon: ShieldCheck,
    title: 'Confident approvals',
    description: 'Low-confidence extraction stays visible so reviewers can correct it before export.',
  },
  {
    icon: CheckCircle2,
    title: 'Clean ERP handoff',
    description: 'Approve orders with validated customer and article data before generating XML.',
  },
] as const;

export default function LoginPage() {
  const { login, register, loginWithMicrosoft, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from =
    (location.state as { from?: { pathname: string } })?.from?.pathname ?? '/';

  const [mode, setMode] = useState<Mode>('login');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      navigate(from, { replace: true });
    }
  }, [from, isAuthenticated, navigate]);

  if (isAuthenticated) {
    return null;
  }

  const handleSubmit = async (e: FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);

    try {
      if (mode === 'login') {
        await login(email, password);
        toast.success('Signed in');
      } else {
        if (!displayName.trim()) {
          toast.error('Please enter your name');
          return;
        }
        await register(email, password, displayName);
        toast.success('Account created');
      }

      navigate(from, { replace: true });
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Authentication failed');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleMicrosoftLogin = async () => {
    try {
      await loginWithMicrosoft();
    } catch (err) {
      toast.error(
        err instanceof Error ? err.message : 'Microsoft login failed',
      );
    }
  };

  return (
    <div className="login-page">
      <div className="login-shell">
        <section className="login-showcase">
          <span className="login-badge">Order intake and review</span>
          <h1 className="login-showcase-title">{BRAND.appFullName}</h1>
          <p className="login-showcase-copy">
            {BRAND.appTagline}. Built for teams that need responsive order intake,
            clean review screens, and reliable ERP exports.
          </p>

          <div className="login-feature-list">
            {showcaseItems.map(({ icon: Icon, title, description }) => (
              <article key={title} className="login-feature-card">
                <span className="login-feature-icon">
                  <Icon size={18} />
                </span>
                <div>
                  <strong>{title}</strong>
                  <p>{description}</p>
                </div>
              </article>
            ))}
          </div>

          <div className="login-help">
            <span>{BRAND.companyName}</span>
            <span>{BRAND.erpSystemName} ready</span>
          </div>
        </section>

        <section className="login-panel">
          <div className="login-card">
            <div className="login-logo">
              <img src={BRAND.logoPath} alt={BRAND.logoAlt} />
            </div>

            <div className="login-mode-toggle" role="tablist" aria-label="Authentication mode">
              <button
                type="button"
                className={`login-mode-button${mode === 'login' ? ' active' : ''}`}
                onClick={() => setMode('login')}
              >
                Sign in
              </button>
              <button
                type="button"
                className={`login-mode-button${mode === 'register' ? ' active' : ''}`}
                onClick={() => setMode('register')}
              >
                Create account
              </button>
            </div>

            <h2 className="login-title">
              {mode === 'login' ? `Sign in to ${BRAND.appName}` : 'Create a workspace account'}
            </h2>
            <p className="login-subtitle">
              {mode === 'login'
                ? BRAND.loginSubtitle
                : 'Start with email and password, or continue with Microsoft OAuth.'}
            </p>

            <form className="login-form" onSubmit={(e) => void handleSubmit(e)}>
              {mode === 'register' && (
                <div className="form-group">
                  <label htmlFor="display-name" className="form-label">
                    Full name
                  </label>
                  <input
                    id="display-name"
                    type="text"
                    className="form-input"
                    placeholder="Jane Smith"
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    required
                    autoComplete="name"
                  />
                </div>
              )}

              <div className="form-group">
                <label htmlFor="email" className="form-label">
                  Email address
                </label>
                <input
                  id="email"
                  type="email"
                  className="form-input"
                  placeholder="you@company.com"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  autoComplete={mode === 'login' ? 'username' : 'email'}
                />
              </div>

              <div className="form-group">
                <label htmlFor="password" className="form-label">
                  Password
                </label>
                <input
                  id="password"
                  type="password"
                  className="form-input"
                  placeholder={mode === 'register' ? 'At least 8 characters' : 'Enter your password'}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                  minLength={mode === 'register' ? 8 : 1}
                  autoComplete={mode === 'login' ? 'current-password' : 'new-password'}
                />
              </div>

              <button
                type="submit"
                className="btn btn-primary login-submit"
                disabled={isSubmitting}
              >
                {isSubmitting
                  ? mode === 'login'
                    ? 'Signing in...'
                    : 'Creating account...'
                  : mode === 'login'
                    ? 'Sign in'
                    : 'Create account'}
              </button>
            </form>

            <div className="login-divider">or continue with</div>

            <button
              type="button"
              className="btn oauth-btn"
              onClick={() => void handleMicrosoftLogin()}
            >
              <svg width="18" height="18" viewBox="0 0 23 23" aria-hidden="true">
                <rect x="1" y="1" width="10" height="10" fill="#f25022" />
                <rect x="12" y="1" width="10" height="10" fill="#7fba00" />
                <rect x="1" y="12" width="10" height="10" fill="#00a4ef" />
                <rect x="12" y="12" width="10" height="10" fill="#ffb900" />
              </svg>
              {BRAND.loginButtonText}
            </button>

            <p className="login-footer-note">
              Microsoft login requires OAuth credentials configured in <code>.env</code>.
            </p>
          </div>
        </section>
      </div>
    </div>
  );
}
