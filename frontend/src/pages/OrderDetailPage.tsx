import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { ArrowLeft, Check, X, Download, AlertCircle, AlertTriangle, Eye, Trash2, Upload } from 'lucide-react';
import toast from 'react-hot-toast';
import { getOrder, updateOrder, approveOrder, rejectOrder, downloadXml, pushToERP, matchOrderCustomer } from '../api/orders';
import { validatePartNumbers } from '../api/articles';
import type { ArticleResult } from '../api/articles';
import { formatCurrency, formatDateTime, formatNumber } from '../utils/formatters';
import type { Order, LineItem } from '../types/order';
import { STATUS_CONFIG, OrderStatus, CONFIDENCE_THRESHOLD } from '../types/order';
import ArticleSearch from '../components/ArticleSearch';
import CustomerMatchBadge from '../components/CustomerMatchBadge';
import PreviewModal from './PreviewModal';

export default function OrderDetailPage() {
  const { orderId } = useParams<{ orderId: string }>();
  const navigate = useNavigate();
  const [order, setOrder] = useState<Order | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [approving, setApproving] = useState(false);
  const [rejecting, setRejecting] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  // Article validation: maps supplier_part_number -> 'valid' | 'invalid' | null
  const [articleValidation, setArticleValidation] = useState<Record<string, 'valid' | 'invalid' | null>>({});
  const [matchingCustomer, setMatchingCustomer] = useState(false);

  // ── Undo last article selection ───────────────────────────────────────
  const UNDO_TIMEOUT_MS = 8000;
  const [pendingUndo, setPendingUndo] = useState<{
    rowIndex: number;
    prevPartNumber: string;
    prevDescription: string;
    timerId: ReturnType<typeof setTimeout>;
  } | null>(null);

  // ── Validate supplier part numbers (Ert Artikelnr) against articles catalogue ──
  const validateArticles = useCallback(async (lineItems: LineItem[]) => {
    const partNumbers = lineItems
      .map((item) => item.supplier_part_number)
      .filter((pn): pn is string => Boolean(pn && pn.trim()));
    if (partNumbers.length === 0) return;

    try {
      const result = await validatePartNumbers([...new Set(partNumbers)]);
      const newValidation: Record<string, 'valid' | 'invalid' | null> = {};
      for (const v of result.valid) {
        newValidation[v.artikelnummer] = 'valid';
      }
      for (const inv of result.invalid) {
        newValidation[inv] = 'invalid';
      }
      setArticleValidation(newValidation);
    } catch (err) {
      console.warn('Article validation failed (non-blocking):', err);
    }
  }, []);

  useEffect(() => {
    if (!orderId) return;
    const fetchOrder = async () => {
      setLoading(true);
      try {
        const data = await getOrder(orderId);
        // Guard: ensure line_items is always an array even if API returns null
        setOrder({ ...data, line_items: Array.isArray(data.line_items) ? data.line_items : [] });
        // Validate all part numbers on load
        void validateArticles(data.line_items);
      } catch (err) {
        toast.error('Failed to load order');
        console.error(err);
      } finally {
        setLoading(false);
      }
    };
    void fetchOrder();
  }, [orderId, validateArticles]);

  const handleFieldChange = (field: keyof Order, value: string | number) => {
    setOrder((prev) => {
      if (!prev) return prev;
      return { ...prev, [field]: value };
    });
  };

  const handleLineItemChange = (
    index: number,
    field: keyof LineItem,
    value: string | number,
  ) => {
    setOrder((prev) => {
      if (!prev) return prev;
      const updatedItems = [...prev.line_items];
      const item = updatedItems[index];
      if (!item) return prev;
      updatedItems[index] = { ...item, [field]: value };
      return { ...prev, line_items: updatedItems };
    });
  };



  const clearUndo = () => {
    setPendingUndo((u) => {
      if (u) clearTimeout(u.timerId);
      return null;
    });
  };

  const handleUndoArticleSelect = () => {
    if (!pendingUndo) return;
    clearTimeout(pendingUndo.timerId);
    handleLineItemChange(pendingUndo.rowIndex, 'supplier_part_number', pendingUndo.prevPartNumber);
    handleLineItemChange(pendingUndo.rowIndex, 'description', pendingUndo.prevDescription);
    setPendingUndo(null);
  };

  const handleDeleteLineItem = (index: number) => {
    if (!order) return;
    const updatedItems = order.line_items.filter((_, i) => i !== index);
    // FIXED (#26): use map to produce new objects instead of mutating in-place
    const renumbered = updatedItems.map((item, i) => ({ ...item, row_number: i + 1 }));
    setOrder({ ...order, line_items: renumbered });
  };

  /**
   * Persist current in-memory edits to the backend.
   * Returns true on success so callers (preview, approve) can gate on it.
   * When `silent` is true the success toast is suppressed (used by auto-save).
   */
  const handleSave = async (options?: { silent?: boolean }): Promise<boolean> => {
    if (!order || !orderId) return false;
    setSaving(true);
    try {
      const updated = await updateOrder(orderId, {
        order_number: order.order_number ?? undefined,
        order_date: order.order_date ?? undefined,
        buyer_name: order.buyer_name ?? undefined,
        buyer_street: order.buyer_street ?? undefined,
        buyer_zip_city: order.buyer_zip_city ?? undefined,
        buyer_country: order.buyer_country ?? undefined,
        buyer_reference: order.buyer_reference ?? undefined,
        delivery_name: order.delivery_name ?? undefined,
        delivery_street1: order.delivery_street1 ?? undefined,
        delivery_street2: order.delivery_street2 ?? undefined,
        delivery_zip_city: order.delivery_zip_city ?? undefined,
        delivery_country: order.delivery_country ?? undefined,
        delivery_method: order.delivery_method ?? undefined,
        transport_payer: order.transport_payer ?? undefined,
        payment_terms_days: order.payment_terms_days ?? undefined,
        currency: order.currency ?? undefined,
        line_items: order.line_items,
      });
      setOrder(updated);
      if (!options?.silent) toast.success('Changes saved');
      return true;
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Save failed');
      return false;
    } finally {
      setSaving(false);
    }
  };

  const handleApprove = async () => {
    if (!orderId) return;

    // Auto-save pending edits so the backend generates XML from current data
    const saved = await handleSave({ silent: true });
    if (!saved) return;

    setApproving(true);
    try {
      const approved = await approveOrder(orderId);
      toast.success(approved.message);

      // Refresh order to show updated status
      const updated = await getOrder(orderId);
      setOrder(updated);

      // Automatically download the generated XML
      try {
        await downloadXml(orderId, updated.order_number);
      } catch {
        toast.error('Approval succeeded but XML download failed. Use the Download XML button.');
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Approval failed');
    } finally {
      setApproving(false);
    }
  };

  const handlePushToERP = async () => {
    if (!orderId) return;
    setPushing(true);
    try {
      const result = await pushToERP(orderId);
      if (result.success) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
      // Refresh order to show updated erp_push_status
      const updated = await getOrder(orderId);
      setOrder(updated);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Failed to push to ERP');
    } finally {
      setPushing(false);
    }
  };

  const handleReject = async () => {
    if (!orderId) return;
    setRejecting(true);
    try {
      const updated = await rejectOrder(orderId);
      setOrder(updated);
      toast.success('Order rejected — edit fields and re-approve when ready');
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Rejection failed');
    } finally {
      setRejecting(false);
    }
  };

  const handleMatchCustomer = async () => {
    if (!orderId) return;
    setMatchingCustomer(true);
    try {
      const result = await matchOrderCustomer(orderId);
      toast.success(`Customer match: ${result.status.replace(/_/g, ' ')}`);
      try {
        const updated = await getOrder(orderId);
        setOrder(updated);
      } catch (refreshErr) {
        console.warn('Failed to refresh order after match:', refreshErr);
      }
    } catch (err) {
      toast.error(err instanceof Error ? err.message : 'Customer matching failed');
    } finally {
      setMatchingCustomer(false);
    }
  };

  /** Check if a specific field has low confidence */
  const isLowConfidence = (fieldName: string): boolean => {
    if (!order?.field_confidence) return false;
    const score = order.field_confidence[fieldName];
    return score !== undefined && score < CONFIDENCE_THRESHOLD;
  };

  /** Get confidence score display for a field */
  const getConfidenceLabel = (fieldName: string): string | null => {
    if (!order?.field_confidence) return null;
    const score = order.field_confidence[fieldName];
    if (score === undefined) return null;
    return `${Math.round(score * 100)}%`;
  };

  if (loading) {
    return (
      <div className="loading-container">
        <div className="spinner spinner-lg" />
        <p>Loading order…</p>
      </div>
    );
  }

  if (!order) {
    return (
      <div className="empty-state">
        <AlertCircle size={48} />
        <p>Order not found</p>
      </div>
    );
  }

  const statusConf = STATUS_CONFIG[order.status];
  const isEditable =
    order.status === OrderStatus.EXTRACTED ||
    order.status === OrderStatus.IN_REVIEW ||
    order.status === OrderStatus.REJECTED;
  const canReject =
    order.status === OrderStatus.EXTRACTED ||
    order.status === OrderStatus.IN_REVIEW ||
    order.status === OrderStatus.APPROVED;

  // Check if there are any low-confidence fields
  const hasUncertainFields =
    order.field_confidence &&
    Object.values(order.field_confidence).some((s) => s < CONFIDENCE_THRESHOLD);
  const uncertainFieldCount = order.field_confidence
    ? Object.values(order.field_confidence).filter(
        (score) => score < CONFIDENCE_THRESHOLD,
      ).length
    : 0;
  const customerMatchSummary = order.customer_match_status
    ? order.customer_match_status.replace(/_/g, ' ')
    : 'not matched yet';

  return (
    <div className="page-stack">
      <section className="page-header detail-header">
        <div className="detail-hero">
          <div className="detail-hero-copy">
            <button
              className="btn btn-outline"
              onClick={() => navigate('/orders')}
            >
              <ArrowLeft size={16} />
              Back to Orders
            </button>
            <h2 className="page-title">
              Order {order.order_number ?? order.source_filename}
            </h2>
            <p className="page-subtitle">Source document: {order.source_filename}</p>
          </div>

          <div className="detail-hero-meta">
            <span
              className="status-badge"
              style={{
                background: `${statusConf.color}20`,
                color: statusConf.color,
              }}
            >
              <span
                className="status-dot"
                style={{ background: statusConf.color }}
              />
              {statusConf.label}
            </span>

            <div className="hero-chip-row">
              <span className="hero-chip">
                {order.line_items.length} line item{order.line_items.length === 1 ? '' : 's'}
              </span>
              <span className="hero-chip">Customer {customerMatchSummary}</span>
              <span className={`hero-chip${uncertainFieldCount > 0 ? ' warning' : ''}`}>
                {uncertainFieldCount > 0
                  ? `${uncertainFieldCount} uncertain field${uncertainFieldCount === 1 ? '' : 's'}`
                  : 'No low-confidence fields'}
              </span>
              <span className="hero-chip">Updated {formatDateTime(order.updated_at)}</span>
            </div>
          </div>
        </div>
      </section>

      {hasUncertainFields && (
        <div className="notice notice-warning">
          <AlertTriangle size={18} />
          <div className="notice-copy">
            <strong className="notice-title">Uncertain fields detected</strong>
            <p>
              Some fields were extracted with low confidence and are highlighted for
              review before approval.
            </p>
            {order.extraction_notes && <p>AI notes: {order.extraction_notes}</p>}
          </div>
        </div>
      )}

      {order.extraction_error && (
        <div className="notice notice-danger">
          <AlertCircle size={18} />
          <div className="notice-copy">
            <strong className="notice-title">Extraction error</strong>
            <p>{order.extraction_error}</p>
          </div>
        </div>
      )}

      {/* Order Header Fields */}
      <div className="card detail-card">
        <div className="form-section">
          <h3 className="form-section-title">Order Details</h3>
          <div className="form-grid">
            <ConfidenceField
              label="Order Number"
              value={order.order_number}
              fieldName="order_number"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('order_number', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Order Date"
              value={order.order_date}
              fieldName="order_date"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('order_date', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Currency"
              value={order.currency}
              fieldName="currency"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('currency', v)}
              readOnly={!isEditable}
            />
          </div>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Buyer</h3>
          <div className="form-grid">
            <ConfidenceField
              label="Company"
              value={order.buyer_name}
              fieldName="buyer_name"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('buyer_name', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Street"
              value={order.buyer_street}
              fieldName="buyer_street"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('buyer_street', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Zip / City"
              value={order.buyer_zip_city}
              fieldName="buyer_zip_city"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('buyer_zip_city', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Country"
              value={order.buyer_country}
              fieldName="buyer_country"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('buyer_country', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Reference"
              value={order.buyer_reference}
              fieldName="buyer_reference"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('buyer_reference', v)}
              readOnly={!isEditable}
            />
          </div>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Delivery Address</h3>
          <div className="form-grid">
            <ConfidenceField
              label="Company"
              value={order.delivery_name}
              fieldName="delivery_name"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('delivery_name', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Street Line 1"
              value={order.delivery_street1}
              fieldName="delivery_street1"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('delivery_street1', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Street Line 2"
              value={order.delivery_street2}
              fieldName="delivery_street2"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('delivery_street2', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Zip / City"
              value={order.delivery_zip_city}
              fieldName="delivery_zip_city"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('delivery_zip_city', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Country"
              value={order.delivery_country}
              fieldName="delivery_country"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('delivery_country', v)}
              readOnly={!isEditable}
            />
          </div>
        </div>

        <div className="form-section">
          <h3 className="form-section-title">Terms</h3>
          <div className="form-grid">
            <ConfidenceField
              label="Delivery Method"
              value={order.delivery_method}
              fieldName="delivery_method"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('delivery_method', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Transport Payer"
              value={order.transport_payer}
              fieldName="transport_payer"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('transport_payer', v)}
              readOnly={!isEditable}
            />
            <ConfidenceField
              label="Payment Terms (days)"
              value={order.payment_terms_days?.toString()}
              fieldName="payment_terms_days"
              confidence={order.field_confidence}
              onChange={(v) => handleFieldChange('payment_terms_days', parseInt(v, 10) || 0)}
              readOnly={!isEditable}
            />
          </div>
        </div>

        <div className="form-section">
          <div className="form-section-header">
            <h3 className="form-section-title">Customer Match</h3>
            <button
              className="btn btn-outline btn-sm"
              onClick={() => void handleMatchCustomer()}
              disabled={matchingCustomer}
              title="Re-run customer matching against the ERP database"
            >
              {matchingCustomer ? <div className="spinner" /> : null}
              {matchingCustomer ? 'Matching...' : 'Re-match'}
            </button>
          </div>
          <div className="section-body">
            {order.customer_match_status ? (
              <CustomerMatchBadge
                status={order.customer_match_status}
                erpCustomerId={order.buyer_customer_number}
                score={order.customer_match_score}
                note={order.customer_match_note}
              />
            ) : (
              <span className="table-secondary-text">
                No match attempted yet. Click Re-match to run.
              </span>
            )}
          </div>
          {order.customer_match_status === 'matched_fuzzy' && (
            <div className="notice notice-warning compact">
              <AlertTriangle size={18} />
              <div className="notice-copy">
                <strong className="notice-title">Possible customer match</strong>
                <p>
                  Verify the buyer name before approval. {order.customer_match_note}
                </p>
              </div>
            </div>
          )}
          {order.customer_match_status === 'unmatched' && (
            <div className="notice notice-danger compact">
              <AlertCircle size={18} />
              <div className="notice-copy">
                <strong className="notice-title">No matching customer found</strong>
                <p>
                  Check the buyer details and confirm that the customer database is up to date.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Undo banner — shown for 8s after an accidental article selection */}
      {pendingUndo && (
        <div className="undo-banner">
          <span>
            Article auto-filled on row {pendingUndo.rowIndex + 1}. Previous value:{' '}
            <strong>{pendingUndo.prevPartNumber || '(empty)'}</strong>
          </span>
          <button
            type="button"
            onClick={handleUndoArticleSelect}
            className="undo-banner-button"
            aria-label="Undo article autofill"
            title="Undo article autofill"
          >
            ↩ Undo
          </button>
        </div>
      )}

      <div className="card table-card">
        <div className="card-header">
          <div>
            <h3 className="card-title">Line Items ({order.line_items.length})</h3>
            <p className="card-subtitle">
              Review article numbers, descriptions, and delivery details before approval.
            </p>
          </div>
          {isLowConfidence('line_items') && (
            <span className="hero-chip warning">
              <AlertTriangle size={14} />
              Confidence {getConfidenceLabel('line_items')}
            </span>
          )}
        </div>
        <div className="table-wrap">
          <table className="data-table data-table-mobile" id="line-items-table">
            <thead>
              <tr>
                <th>#</th>
                <th>Artikelnr</th>
                <th>Ert Artikelnr</th>
                <th>Artikelbenämning</th>
                <th>Qty</th>
                <th>Unit</th>
                <th>Unit Price</th>
                <th>Discount %</th>
                <th>Delivery</th>
                {isEditable && <th>Actions</th>}
              </tr>
            </thead>
            <tbody>
              {order.line_items.map((item, idx) => (
                <tr key={item.id ?? idx}>
                  <td data-label="Row">{item.row_number}</td>
                  <td data-label="Artikelnr">
                    {isEditable ? (
                      <input
                        className="form-input line-item-input"
                        value={item.part_number ?? ''}
                        onChange={(e) =>
                          handleLineItemChange(idx, 'part_number', e.target.value)
                        }
                      />
                    ) : (
                      item.part_number ?? '—'
                    )}
                  </td>
                  <td data-label="Ert Artikelnr">
                    {isEditable ? (
                      <ArticleSearch
                        value={item.supplier_part_number ?? ''}
                        onChange={(val) => {
                          handleLineItemChange(idx, 'supplier_part_number', val);
                          // Clear validation for this item while typing
                          if (item.supplier_part_number !== val) {
                            setArticleValidation((prev) => {
                              const next = { ...prev };
                              delete next[item.supplier_part_number ?? ''];
                              return next;
                            });
                          }
                        }}
                        onSelect={(article: ArticleResult) => {
                          // Save previous values so the user can undo accidental selection
                          const prevPartNumber = item.supplier_part_number ?? '';
                          const prevDescription = item.description ?? '';
                          clearUndo();
                          handleLineItemChange(idx, 'supplier_part_number', article.artikelnummer);
                          handleLineItemChange(idx, 'description', article.artikelbenamning);
                          setArticleValidation((prev) => ({
                            ...prev,
                            [article.artikelnummer]: 'valid',
                          }));
                          const timerId = setTimeout(clearUndo, UNDO_TIMEOUT_MS);
                          setPendingUndo({ rowIndex: idx, prevPartNumber, prevDescription, timerId });
                        }}
                        validationStatus={articleValidation[item.supplier_part_number ?? ''] ?? null}
                      />
                    ) : (
                      item.supplier_part_number ?? '—'
                    )}
                  </td>
                  <td>
                    {item.description ?? '—'}
                  </td>
                  <td>{formatNumber(item.quantity)}</td>
                  <td>{item.unit ?? '—'}</td>
                  <td>{formatCurrency(item.unit_price, order.currency ?? 'SEK')}</td>
                  <td>{item.discount != null ? `${item.discount}%` : '—'}</td>
                  <td>{item.delivery_date ?? '—'}</td>
                  {isEditable && (
                    <td style={{ textAlign: 'center', padding: '0.25rem' }}>
                      <button
                        className="btn"
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: 'var(--color-danger)',
                          padding: '0.25rem',
                          cursor: 'pointer',
                        }}
                        onClick={() => handleDeleteLineItem(idx)}
                        title="Delete Row"
                      >
                        <Trash2 size={16} />
                      </button>
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>

      </div>

      {/* Action Bar */}
      <div className="action-bar action-bar-sticky">
        <button
          className="btn btn-outline"
          onClick={() => navigate('/orders')}
        >
          <ArrowLeft size={16} />
          Back
        </button>
        <div className="action-bar-spacer" />

        {canReject && (
          <button
            className="btn btn-danger"
            onClick={() => void handleReject()}
            disabled={rejecting}
          >
            {rejecting ? <div className="spinner" /> : <X size={16} />}
            Reject
          </button>
        )}

        {isEditable && (
          <>
            <button
              className="btn btn-primary"
              onClick={() => void handleSave()}
              disabled={saving}
            >
              {saving ? <div className="spinner" /> : null}
              Save Changes
            </button>
            <button
              className="btn btn-outline preview-btn"
              onClick={async () => {
                // Auto-save so the backend preview-xml endpoint sees current data
                const saved = await handleSave({ silent: true });
                if (saved) setShowPreview(true);
              }}
              id="preview-btn"
            >
              <Eye size={16} />
              Preview
            </button>
            <button
              className="btn btn-success"
              onClick={() => void handlePushToERP()}
              disabled={pushing}
              title="Push order XML to ERP System directly from here"
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
            >
              {pushing ? <div className="spinner" /> : <Upload size={16} />}
              Push to ERP
              {order.erp_push_status === 'success' && !pushing && (
                <span
                  style={{
                    marginLeft: '0.25rem',
                    background: 'rgba(255,255,255,0.25)',
                    borderRadius: '999px',
                    padding: '0 0.4rem',
                    fontSize: 'var(--font-size-xs)',
                    fontWeight: 700,
                    letterSpacing: '0.02em',
                  }}
                >
                  ✓ Pushed
                </span>
              )}
            </button>
            <button
              className="btn btn-success"
              onClick={() => void handleApprove()}
              disabled={approving || pushing}
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
            >
              {approving ? <div className="spinner" /> : <Check size={16} />}
              Approve & Generate XML
            </button>
          </>
        )}

        {order.status === OrderStatus.APPROVED && (
          <>
            <button
              className="btn btn-primary"
              onClick={() => {
                void downloadXml(order.id, order.order_number).catch(() => {
                  toast.error('Failed to download XML');
                });
              }}
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
            >
              <Download size={16} />
              Download XML
            </button>
            <button
              className="btn btn-success"
              onClick={() => void handlePushToERP()}
              disabled={pushing}
              title="Push order XML to ERP System"
              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}
            >
              {pushing ? <div className="spinner" /> : <Upload size={16} />}
              Push to ERP
              {order.erp_push_status === 'success' && !pushing && (
                <span
                  style={{
                    marginLeft: '0.25rem',
                    background: 'rgba(255,255,255,0.25)',
                    borderRadius: '999px',
                    padding: '0 0.4rem',
                    fontSize: 'var(--font-size-xs)',
                    fontWeight: 700,
                    letterSpacing: '0.02em',
                  }}
                >
                  ✓ Pushed
                </span>
              )}
            </button>
          </>
        )}
      </div>

      {/* Preview Modal */}
      {showPreview && (
        <PreviewModal
          orderId={orderId!}
          orderNumber={order.order_number}
          onClose={() => setShowPreview(false)}
        />
      )}
    </div>
  );
}

/** Input field with confidence indicator — highlights in yellow when AI confidence is low */
function ConfidenceField({
  label,
  value,
  fieldName,
  confidence,
  onChange,
  readOnly = false,
}: {
  label: string;
  value: string | null | undefined;
  fieldName: string;
  confidence: Record<string, number>;
  onChange: (value: string) => void;
  readOnly?: boolean;
}) {
  const score = confidence?.[fieldName];
  const isUncertain = score !== undefined && score < CONFIDENCE_THRESHOLD;
  const confidencePercent = score !== undefined ? `${Math.round(score * 100)}%` : null;

  return (
    <div className={`form-group confidence-field${isUncertain ? ' is-uncertain' : ''}${readOnly ? ' is-readonly' : ''}`}>
      <label className="form-label confidence-label">
        <span>{label}</span>
        {confidencePercent && (
          <span
            className={`confidence-meta${isUncertain ? ' warning' : ''}`}
            title={`AI confidence: ${confidencePercent}`}
          >
            {isUncertain && <AlertTriangle size={12} />}
            {confidencePercent}
          </span>
        )}
      </label>
      <input
        className="form-input confidence-input"
        type="text"
        value={value ?? ''}
        onChange={(e) => onChange(e.target.value)}
        readOnly={readOnly}
      />
    </div>
  );
}
