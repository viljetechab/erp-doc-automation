import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  RefreshCw,
  ShieldCheck,
  Users,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { importCustomerCsv } from '../api/orders';
import { BRAND } from '../config/branding';

interface ImportResult {
  imported: number;
  skipped: number;
  errors: string[];
}

const importHighlights = [
  {
    icon: Users,
    label: 'Matching quality',
    value: 'Fresh customer data',
    detail: 'Keep buyer matching accurate during order review.',
  },
  {
    icon: RefreshCw,
    label: 'Safe re-import',
    value: 'Update existing rows',
    detail: 'Re-uploading refreshes records instead of creating duplicates.',
  },
  {
    icon: ShieldCheck,
    label: 'Operational safety',
    value: 'Import summaries',
    detail: 'See what was imported, skipped, or rejected after each run.',
  },
] as const;

export default function CustomerImportPage() {
  const [isImporting, setIsImporting] = useState(false);
  const [result, setResult] = useState<ImportResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(async (acceptedFiles: File[]) => {
    const file = acceptedFiles[0];
    if (!file) return;

    setIsImporting(true);
    setError(null);
    setResult(null);

    try {
      const data = await importCustomerCsv(file);
      setResult(data);
      toast.success(`Imported ${data.imported} customer records`);
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
    accept: { 'text/csv': ['.csv'], 'text/plain': ['.csv'] },
    maxFiles: 1,
    disabled: isImporting,
  });

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div className="hero-panel-copy">
          <span className="hero-eyebrow">Customer sync</span>
          <h2 className="hero-title">Refresh customer matching</h2>
          <p className="hero-subtitle">
            Upload the latest {BRAND.erpSystemName} {BRAND.customerListLabel}.
          </p>
          <div className="hero-chip-row">
            <span className="hero-chip">CSV only</span>
            <span className="hero-chip">Re-upload safe</span>
            <span className="hero-chip">No duplicates</span>
          </div>
        </div>

        <div className="metric-grid metric-grid-compact">
          {importHighlights.map(({ icon: Icon, label, value, detail }) => (
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
              <h3 className="card-title">Customer import</h3>
              <p className="card-subtitle">
                Use the exported customer CSV from your ERP.
              </p>
            </div>
            <span className="hero-chip">Customer master</span>
          </div>

          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? 'active' : ''}`}
          >
            <input {...getInputProps()} />
            {isImporting ? (
              <div className="loading-container">
                <div className="spinner spinner-lg" />
                <p>Importing customer data...</p>
              </div>
            ) : (
              <>
                <div className="dropzone-icon">
                  {isDragActive ? <FileText size={64} /> : <Users size={64} />}
                </div>
                <p className="dropzone-text">
                  {isDragActive
                    ? 'Drop the customer file here'
                    : `Drag and drop the ${BRAND.customerListLabel}`}
                </p>
                <p className="dropzone-hint">Click to browse for a CSV file.</p>
              </>
            )}
          </div>
        </div>

        <aside className="stack-md">
          <div className="card">
            <h3 className="card-title">Include</h3>
            <ul className="section-list">
              <li>Customer IDs and names.</li>
              <li>Address and company details.</li>
              <li>The latest export from ERP.</li>
            </ul>
          </div>

          <div className="card">
            <h3 className="card-title">Before import</h3>
            <ul className="section-list">
              <li>Use a fresh export, not an old file.</li>
              <li>Keep the CSV structure unchanged.</li>
              <li>Re-import after major customer updates.</li>
            </ul>
          </div>
        </aside>
      </section>

      {result && (
        <div className="notice notice-success">
          <CheckCircle2 size={18} />
          <div className="notice-copy">
            <strong className="notice-title">Import complete</strong>
            <p>
              {result.imported} customers imported and {result.skipped} rows skipped.
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
            <strong className="notice-title">Customer import failed</strong>
            <p>{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
