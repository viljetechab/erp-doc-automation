/**
 * OAuthCallbackPage — handles the redirect from Microsoft OAuth.
 *
 * Extracts the `code` and `state` query parameters, exchanges them for
 * tokens via the backend, and redirects to the home page.
 */
import { useEffect, useRef, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import toast from 'react-hot-toast';
import { useAuth } from '../contexts/AuthContext';

export default function OAuthCallbackPage() {
  const { handleOAuthCallback } = useAuth();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const [error, setError] = useState<string | null>(null);
  const hasRun = useRef(false);

  useEffect(() => {
    // Prevent double-execution in React StrictMode
    if (hasRun.current) return;
    hasRun.current = true;

    const code = searchParams.get('code');
    const state = searchParams.get('state');
    const oauthError = searchParams.get('error');

    if (oauthError) {
      const desc =
        searchParams.get('error_description') ??
        'Microsoft login was cancelled or denied.';
      setError(desc);
      toast.error(desc);
      return;
    }

    if (!code) {
      setError('No authorization code received from Microsoft.');
      return;
    }

    if (!state) {
      setError(
        'OAuth state parameter missing. This may indicate a CSRF attack. Please retry login.',
      );
      return;
    }

    const exchange = async () => {
      try {
        await handleOAuthCallback('microsoft', code, state);
        toast.success('Signed in with Microsoft');
        navigate('/', { replace: true });
      } catch (err) {
        const msg = err instanceof Error ? err.message : 'Microsoft login failed';
        setError(msg);
        toast.error(msg);
      }
    };

    void exchange();
  }, [searchParams, handleOAuthCallback, navigate]);

  if (error) {
    return (
      <div className="login-page">
        <div className="login-card">
          <h1 className="login-title">Login Failed</h1>
          <p className="login-subtitle" style={{ color: 'var(--color-danger)' }}>
            {error}
          </p>
          <button
            className="btn btn-primary login-submit"
            onClick={() => navigate('/login', { replace: true })}
          >
            Back to Login
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="login-page">
      <div className="login-card" style={{ textAlign: 'center' }}>
        <div className="spinner spinner-lg" style={{ margin: '0 auto 1rem' }} />
        <p className="login-subtitle">Completing Microsoft sign-in…</p>
      </div>
    </div>
  );
}
