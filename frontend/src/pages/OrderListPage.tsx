import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  AlertTriangle,
  CheckCircle2,
  Clock3,
  List,
  RefreshCw,
  ShieldAlert,
  Upload,
} from 'lucide-react';
import toast from 'react-hot-toast';
import { listOrders } from '../api/orders';
import { formatDate, formatDateTime } from '../utils/formatters';
import type { OrderListItem } from '../types/order';
import { OrderStatus, STATUS_CONFIG } from '../types/order';
import CustomerMatchBadge from '../components/CustomerMatchBadge';

export default function OrderListPage() {
  const navigate = useNavigate();
  const [orders, setOrders] = useState<OrderListItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [fetchError, setFetchError] = useState<string | null>(null);

  const fetchOrders = async () => {
    setLoading(true);
    setFetchError(null);
    try {
      const data = await listOrders();
      setOrders(Array.isArray(data) ? data : []);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load orders';
      setFetchError(message);
      toast.error(message);
      console.error('Failed to load orders', err);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void fetchOrders();
  }, []);

  const readyCount = orders.filter(
    (order) =>
      order.status === OrderStatus.EXTRACTED ||
      order.status === OrderStatus.IN_REVIEW,
  ).length;
  const approvedCount = orders.filter(
    (order) => order.status === OrderStatus.APPROVED,
  ).length;
  const attentionCount = orders.filter(
    (order) =>
      order.has_low_confidence ||
      order.customer_match_status === 'unmatched' ||
      order.status === OrderStatus.EXTRACTION_FAILED,
  ).length;

  const summaryCards = [
    {
      icon: List,
      label: 'Total orders',
      value: orders.length,
      detail: 'Orders currently tracked in the workspace.',
    },
    {
      icon: Clock3,
      label: 'Needs review',
      value: readyCount,
      detail: 'Extracted orders waiting for a reviewer.',
    },
    {
      icon: CheckCircle2,
      label: 'Approved',
      value: approvedCount,
      detail: 'Orders already cleared for XML export or ERP push.',
    },
    {
      icon: ShieldAlert,
      label: 'Needs attention',
      value: attentionCount,
      detail: 'Orders with warnings, failed extraction, or missing matches.',
    },
  ] as const;

  return (
    <div className="page-stack">
      <section className="page-header page-header-split">
        <div>
          <h2 className="page-title">Orders</h2>
          <p className="page-subtitle">
            Review extracted orders, track approval progress, and jump into edits quickly.
          </p>
        </div>

        <button
          type="button"
          className="btn btn-outline"
          onClick={() => void fetchOrders()}
          disabled={loading}
        >
          <RefreshCw size={16} />
          Refresh
        </button>
      </section>

      <section className="metric-grid">
        {summaryCards.map(({ icon: Icon, label, value, detail }) => (
          <article key={label} className="metric-card">
            <span className="metric-icon">
              <Icon size={18} />
            </span>
            <span className="metric-label">{label}</span>
            <strong className="metric-value">{value}</strong>
            <p className="metric-description">{detail}</p>
          </article>
        ))}
      </section>

      {fetchError && !loading && (
        <div className="notice notice-danger">
          <AlertTriangle size={18} />
          <div className="notice-copy">
            <strong className="notice-title">Unable to load orders</strong>
            <p>{fetchError}</p>
          </div>
        </div>
      )}

      {loading ? (
        <div className="loading-container">
          <div className="spinner spinner-lg" />
          <p>Loading orders...</p>
        </div>
      ) : orders.length === 0 && !fetchError ? (
        <div className="empty-state">
          <div className="empty-state-icon">
            <List size={64} />
          </div>
          <p>No orders yet. Upload a PDF to get started.</p>
          <button type="button" className="btn btn-primary" onClick={() => navigate('/')}>
            <Upload size={16} />
            Upload first order
          </button>
        </div>
      ) : (
        <div className="card table-card">
          <div className="card-header">
            <div>
              <h3 className="card-title">Order queue</h3>
              <p className="card-subtitle">
                Select an order to validate extracted fields and line items.
              </p>
            </div>
            <span className="hero-chip">{orders.length} tracked</span>
          </div>

          <div className="table-wrap">
            <table className="data-table data-table-mobile" id="orders-table">
              <thead>
                <tr>
                  <th>Order</th>
                  <th>Status</th>
                  <th>Buyer</th>
                  <th>Customer match</th>
                  <th>Reference</th>
                  <th>Items</th>
                  <th>Order date</th>
                  <th>Uploaded</th>
                </tr>
              </thead>
              <tbody>
                {orders.map((order) => {
                  const statusConf = STATUS_CONFIG[order.status];
                  const primaryTitle = order.order_number ?? order.source_filename;

                  return (
                    <tr
                      key={order.id}
                      className={order.has_low_confidence ? 'table-row-warning' : ''}
                      onClick={() => navigate(`/orders/${order.id}`)}
                    >
                      <td data-label="Order">
                        <div className="table-primary-cell">
                          <span className="table-primary-text">{primaryTitle}</span>
                          {order.order_number && (
                            <span className="table-secondary-text">{order.source_filename}</span>
                          )}
                        </div>
                      </td>
                      <td data-label="Status">
                        <div className="table-status-cell">
                          <span
                            className="status-badge"
                            style={{
                              background: `${statusConf.color}1f`,
                              color: statusConf.color,
                            }}
                          >
                            <span
                              className="status-dot"
                              style={{ background: statusConf.color }}
                            />
                            {statusConf.label}
                          </span>
                          {order.has_low_confidence && (
                            <span className="table-inline-warning">
                              <AlertTriangle size={14} />
                            </span>
                          )}
                        </div>
                      </td>
                      <td data-label="Buyer">{order.buyer_name ?? '-'}</td>
                      <td data-label="Customer match">
                        {order.customer_match_status ? (
                          <CustomerMatchBadge status={order.customer_match_status} compact />
                        ) : (
                          <span className="table-secondary-text">-</span>
                        )}
                      </td>
                      <td data-label="Reference">{order.buyer_reference ?? '-'}</td>
                      <td data-label="Items">{order.line_item_count}</td>
                      <td data-label="Order date">{formatDate(order.order_date)}</td>
                      <td data-label="Uploaded">{formatDateTime(order.created_at)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
