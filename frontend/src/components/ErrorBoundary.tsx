/**
 * React ErrorBoundary — catches unhandled component render errors and
 * displays a friendly fallback UI instead of a blank white screen (#27).
 *
 * Usage:
 *   <ErrorBoundary>
 *     <MyComponent />
 *   </ErrorBoundary>
 *
 * Or with a custom fallback:
 *   <ErrorBoundary fallback={<p>Something went wrong.</p>}>
 *     <MyComponent />
 *   </ErrorBoundary>
 */
import { Component, type ErrorInfo, type ReactNode } from 'react';

interface Props {
  children: ReactNode;
  fallback?: ReactNode;
}

interface State {
  hasError: boolean;
  errorMessage: string;
}

export default class ErrorBoundary extends Component<Props, State> {
  constructor(props: Props) {
    super(props);
    this.state = { hasError: false, errorMessage: '' };
  }

  static getDerivedStateFromError(error: Error): State {
    return { hasError: true, errorMessage: error.message };
  }

  componentDidCatch(error: Error, info: ErrorInfo): void {
    // Log to console in development; hook into error monitoring (e.g. Sentry) in production
    console.error('[ErrorBoundary] Unhandled render error:', error, info);
  }

  handleReset = (): void => {
    this.setState({ hasError: false, errorMessage: '' });
  };

  render(): ReactNode {
    if (this.state.hasError) {
      if (this.props.fallback) {
        return this.props.fallback;
      }
      return (
        <div className="error-boundary-fallback">
          <div className="error-boundary-content">
            <h2>Something went wrong</h2>
            <p className="error-boundary-message">
              {this.state.errorMessage || 'An unexpected error occurred.'}
            </p>
            <button
              className="btn btn-primary"
              onClick={this.handleReset}
            >
              Try again
            </button>
            <button
              className="btn btn-outline"
              onClick={() => window.location.reload()}
              style={{ marginLeft: '0.5rem' }}
            >
              Reload page
            </button>
          </div>
        </div>
      );
    }

    return this.props.children;
  }
}
