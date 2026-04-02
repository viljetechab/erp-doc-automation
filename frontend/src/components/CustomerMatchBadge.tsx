import type { CSSProperties } from 'react';
import {
  AlertCircle,
  CheckCircle,
  HelpCircle,
  MinusCircle,
} from 'lucide-react';

type MatchStatus = 'matched_exact' | 'matched_fuzzy' | 'unmatched' | 'skipped' | null;

interface CustomerMatchBadgeProps {
  status: MatchStatus;
  customerName?: string | null;
  erpCustomerId?: string | null;
  score?: number | null;
  note?: string | null;
  compact?: boolean;
}

const STATUS_CONFIG: Record<
  NonNullable<MatchStatus>,
  { label: string; color: string; Icon: React.ElementType; bg: string }
> = {
  matched_exact: {
    label: 'Customer Matched',
    color: '#16a34a',
    bg: 'rgba(22, 163, 74, 0.1)',
    Icon: CheckCircle,
  },
  matched_fuzzy: {
    label: 'Possible Match',
    color: '#d97706',
    bg: 'rgba(217, 119, 6, 0.1)',
    Icon: HelpCircle,
  },
  unmatched: {
    label: 'No Customer Match',
    color: '#dc2626',
    bg: 'rgba(220, 38, 38, 0.1)',
    Icon: AlertCircle,
  },
  skipped: {
    label: 'Match Skipped',
    color: '#6b7280',
    bg: 'rgba(107, 114, 128, 0.1)',
    Icon: MinusCircle,
  },
};

export default function CustomerMatchBadge({
  status,
  customerName,
  erpCustomerId,
  score,
  note,
  compact = false,
}: CustomerMatchBadgeProps) {
  if (!status) return null;

  const config = STATUS_CONFIG[status];
  if (!config) return null;

  const { Icon } = config;

  return (
    <div
      className={`customer-match${compact ? ' compact' : ''}`}
      style={
        {
          '--customer-match-color': config.color,
          '--customer-match-bg': config.bg,
        } as CSSProperties
      }
    >
      <div className="customer-match-head">
        <span className="customer-match-label">
          <Icon size={compact ? 12 : 14} />
          <strong>{config.label}</strong>
        </span>
        {score != null && !compact && (
          <span className="customer-match-score">
            {Math.round(score * 100)}% confidence
          </span>
        )}
      </div>

      {!compact && customerName && (
        <div className="customer-match-body">
          {customerName}
          {erpCustomerId && (
            <span className="customer-match-meta">#{erpCustomerId}</span>
          )}
        </div>
      )}

      {!compact && erpCustomerId && !customerName && (
        <div className="customer-match-body">ERP Customer #{erpCustomerId}</div>
      )}

      {!compact && note && <div className="customer-match-note">{note}</div>}
    </div>
  );
}
