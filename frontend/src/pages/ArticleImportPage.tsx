import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  Package,
  RefreshCw,
  ShieldCheck,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { importArticles, type ArticleImportResponse } from '../api/articles';
import { BRAND } from '../config/branding';

const catalogueHighlights = [
  {
    icon: Package,
    label: 'Article validation',
    value: 'Searchable catalogue',
    detail: 'Reviewers can confirm supplier part numbers against fresh data.',
  },
  {
    icon: RefreshCw,
    label: 'Smart updates',
    value: 'Create and refresh',
    detail: 'New items are added and existing records are updated in place.',
  },
  {
    icon: ShieldCheck,
    label: 'Safer imports',
    value: 'Empty values ignored',
    detail: 'Current article data is not replaced with blank cells during sync.',
  },
] as const;

export default function ArticleImportPage() {
  const [isImporting, setIsImporting] = useState(false);
  const [result, setResult] = useState<ArticleImportResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setIsImporting(true);
    setError(null);
    setResult(null);

    try {
      const data = await importArticles(file);
      setResult(data);
      toast.success(
        `${data.imported} new, ${data.updated} updated, ${data.skipped} skipped`,
      );
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Import failed';
      setError(message);
      toast.error(message);
    } finally {
      setIsImporting(false);
    }
  }, []);

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (files) => void onDrop(files),
    accept: {
      'text/csv': ['.csv'],
      'text/plain': ['.csv'],
      'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet': ['.xlsx'],
    },
    maxFiles: 1,
    disabled: isImporting,
  });

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div className="hero-panel-copy">
          <span className="hero-eyebrow">Article sync</span>
          <h2 className="hero-title">Refresh article data</h2>
          <p className="hero-subtitle">
            Upload the latest {BRAND.erpSystemName} {BRAND.articleListLabel}.
          </p>
          <div className="hero-chip-row">
            <span className="hero-chip">CSV or XLSX</span>
            <span className="hero-chip">Add and update</span>
            <span className="hero-chip">Keep existing data</span>
          </div>
        </div>

        <div className="metric-grid metric-grid-compact">
          {catalogueHighlights.map(({ icon: Icon, label, value, detail }) => (
            <article key={label} className="metric-card">
              <span className="metric-icon">
                <Icon size={18} />
              </span>
              <span className="metric-label">{label}</span>
              <strong className="metric-value">{value}</strong>
              <p className="metric-description">{detail}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="content-grid content-grid-asymmetric">
        <div className="card card-emphasis">
          <div className="card-header card-header-stack">
            <div>
              <h3 className="card-title">Article catalogue import</h3>
              <p className="card-subtitle">
                Use a CSV or Excel export from your ERP.
              </p>
            </div>
            <span className="hero-chip">Catalogue sync</span>
          </div>

          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? 'active' : ''}`}
          >
            <input {...getInputProps()} />
            {isImporting ? (
              <div className="loading-container">
                <div className="spinner spinner-lg" />
                <p>Importing articles...</p>
              </div>
            ) : (
              <>
                <div className="dropzone-icon">
                  {isDragActive ? <FileText size={64} /> : <Package size={64} />}
                </div>
                <p className="dropzone-text">
                  {isDragActive
                    ? 'Drop the article file here'
                    : `Drag and drop the ${BRAND.articleListLabel}`}
                </p>
                <p className="dropzone-hint">Click to browse for a CSV or XLSX file.</p>
              </>
            )}
          </div>
        </div>

        <aside className="stack-md">
          <div className="card">
            <h3 className="card-title">Include</h3>
            <ul className="section-list">
              <li>Article numbers and descriptions.</li>
              <li>The latest catalogue export.</li>
              <li>Full records when available.</li>
            </ul>
          </div>

          <div className="card">
            <h3 className="card-title">Why it matters</h3>
            <ul className="section-list">
              <li>Reviewers can validate part numbers faster.</li>
              <li>Article suggestions stay reliable.</li>
              <li>Exports stay cleaner.</li>
            </ul>
          </div>
        </aside>
      </section>

      {result && (
        <div className="notice notice-success">
          <CheckCircle2 size={18} />
          <div className="notice-copy">
            <strong className="notice-title">Catalogue updated</strong>
            <p>
              {result.imported} new articles added, {result.updated} updated, and{' '}
              {result.skipped} skipped or unchanged.
            </p>
            {(result.errors ?? []).length > 0 && (
              <details className="notice-details">
                <summary>{result.errors.length} non-fatal issue(s)</summary>
                <ul className="section-list compact">
                  {result.errors.map((item, index) => (
                    <li key={`${item}-${index}`}>{item}</li>
                  ))}
                </ul>
              </details>
            )}
          </div>
        </div>
      )}

      {error && (
        <div className="notice notice-danger">
          <AlertCircle size={18} />
          <div className="notice-copy">
            <strong className="notice-title">Article import failed</strong>
            <p>{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
