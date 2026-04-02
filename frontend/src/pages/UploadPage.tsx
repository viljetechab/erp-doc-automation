import { useCallback, useState } from 'react';
import { useDropzone } from 'react-dropzone';
import { useNavigate } from 'react-router-dom';
import {
  AlertCircle,
  CheckCircle2,
  FileText,
  ShieldCheck,
  Upload,
  Workflow,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { uploadPdf } from '../api/orders';

const workflowHighlights = [
  {
    icon: Workflow,
    label: 'Extraction workflow',
    value: 'AI + human review',
    detail: 'Move each document from raw PDF to validated order data.',
  },
  {
    icon: CheckCircle2,
    label: 'Approval ready',
    value: 'XML output',
    detail: 'Generate export-ready XML after review and approval.',
  },
  {
    icon: ShieldCheck,
    label: 'Safer handoff',
    value: 'Confidence flags',
    detail: 'Low-confidence fields stay visible so nothing slips through.',
  },
] as const;

export default function UploadPage() {
  const navigate = useNavigate();
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const onDrop = useCallback(
    async (acceptedFiles: File[]) => {
      const file = acceptedFiles[0];
      if (!file) return;

      setIsUploading(true);
      setError(null);

      try {
        const order = await uploadPdf(file);
        toast.success(`Order ${order.order_number ?? 'uploaded'} is ready for review`);
        navigate(`/orders/${order.id}`);
      } catch (err) {
        const message = err instanceof Error ? err.message : 'Upload failed';
        setError(message);
        toast.error(message);
      } finally {
        setIsUploading(false);
      }
    },
    [navigate],
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'application/pdf': ['.pdf'] },
    maxFiles: 1,
    disabled: isUploading,
  });

  return (
    <div className="page-stack">
      <section className="hero-panel">
        <div className="hero-panel-copy">
          <span className="hero-eyebrow">Order intake</span>
          <h2 className="hero-title">Upload a purchase order</h2>
          <p className="hero-subtitle">
            Drop in a PDF and open the extracted order in review.
          </p>
          <div className="hero-chip-row">
            <span className="hero-chip">PDF upload</span>
            <span className="hero-chip">AI extract</span>
            <span className="hero-chip">Review ready</span>
          </div>
        </div>

        <div className="metric-grid metric-grid-compact">
          {workflowHighlights.map(({ icon: Icon, label, value, detail }) => (
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
              <h3 className="card-title">New order intake</h3>
              <p className="card-subtitle">
                Upload once and continue in the review screen.
              </p>
            </div>
            <span className="hero-chip">PDF only</span>
          </div>

          <div
            {...getRootProps()}
            className={`dropzone ${isDragActive ? 'active' : ''}`}
            id="pdf-dropzone"
          >
            <input {...getInputProps()} id="pdf-file-input" />

            {isUploading ? (
              <div className="loading-container">
                <div className="spinner spinner-lg" />
                <p>Extracting order data with AI. This may take a moment.</p>
              </div>
            ) : (
              <>
                <div className="dropzone-icon">
                  {isDragActive ? <FileText size={64} /> : <Upload size={64} />}
                </div>
                <p className="dropzone-text">
                  {isDragActive
                    ? 'Drop the purchase order here'
                    : 'Drag and drop a purchase order PDF'}
                </p>
                <p className="dropzone-hint">
                  Click to browse or drop a file here. Maximum size: 50 MB.
                </p>
              </>
            )}
          </div>
        </div>

        <aside className="stack-md">
          <div className="card">
            <h3 className="card-title">After upload</h3>
            <ul className="section-list">
              <li>The PDF is converted into structured order data.</li>
              <li>Low-confidence fields stay visible for review.</li>
              <li>Approved orders can be exported to ERP.</li>
            </ul>
          </div>

          <div className="card">
            <h3 className="card-title">Best results</h3>
            <ul className="section-list">
              <li>Use clean PDFs, not photos or screenshots.</li>
              <li>Keep one order per file.</li>
              <li>Refresh customers and articles first.</li>
            </ul>
          </div>
        </aside>
      </section>

      {error && (
        <div className="notice notice-danger">
          <AlertCircle size={18} />
          <div className="notice-copy">
            <strong className="notice-title">Upload failed</strong>
            <p>{error}</p>
          </div>
        </div>
      )}
    </div>
  );
}
