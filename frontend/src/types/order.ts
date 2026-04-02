/**
 * TypeScript interfaces matching backend Pydantic schemas.
 */

export enum OrderStatus {
  EXTRACTED = 'extracted',
  EXTRACTION_FAILED = 'extraction_failed',
  IN_REVIEW = 'in_review',
  APPROVED = 'approved',
  REJECTED = 'rejected',
}

export interface LineItem {
  id?: string;
  row_number: number;
  part_number: string | null;
  supplier_part_number: string | null;
  description: string | null;
  additional_text: string | null;
  quantity: number | null;
  unit: string | null;
  delivery_date: string | null;
  unit_price: number | null;
  discount: number | null;
  reference_number: string | null;
}

export interface Order {
  id: string;
  status: OrderStatus;
  source_filename: string;
  order_number: string | null;
  order_date: string | null;
  buyer_name: string | null;
  buyer_street: string | null;
  buyer_zip_city: string | null;
  buyer_country: string | null;
  buyer_reference: string | null;
  delivery_name: string | null;
  delivery_street1: string | null;
  delivery_street2: string | null;
  delivery_zip_city: string | null;
  delivery_country: string | null;
  delivery_method: string | null;
  transport_payer: string | null;
  payment_terms_days: number | null;
  currency: string | null;
  line_items: LineItem[];
  field_confidence: Record<string, number>;
  extraction_notes: string | null;
  extraction_error: string | null;
  // Customer match
  buyer_customer_number: string | null;
  matched_customer_id: string | null;
  customer_match_status: 'matched_exact' | 'matched_fuzzy' | 'unmatched' | 'skipped' | null;
  customer_match_score: number | null;
  customer_match_note: string | null;

  erp_pushed_at: string | null;
  erp_push_status: string | null;  // 'success' | 'failed' | null
  created_at: string;
  updated_at: string;
}

export interface OrderListItem {
  id: string;
  status: OrderStatus;
  source_filename: string;
  order_number: string | null;
  order_date: string | null;
  buyer_name: string | null;
  buyer_reference: string | null;
  line_item_count: number;
  has_low_confidence: boolean;
  customer_match_status: 'matched_exact' | 'matched_fuzzy' | 'unmatched' | 'skipped' | null;
  created_at: string;
}

export interface OrderUpdateRequest {
  order_number?: string;
  order_date?: string;
  buyer_name?: string;
  buyer_street?: string;
  buyer_zip_city?: string;
  buyer_country?: string;
  buyer_reference?: string;
  buyer_customer_number?: string;
  delivery_name?: string;
  delivery_street1?: string;
  delivery_street2?: string;
  delivery_zip_city?: string;
  delivery_country?: string;
  delivery_method?: string;
  transport_payer?: string;
  payment_terms_days?: number;
  currency?: string;
  line_items?: LineItem[];
}

export interface OrderApproveResponse {
  id: string;
  status: OrderStatus;
  message: string;
  xml_download_url: string;
}

export interface ERPPushResponse {
  success: boolean;
  message: string;
  erp_push_status: string;
}

/** Maps status to user-friendly label and color */
export const STATUS_CONFIG: Record<OrderStatus, { label: string; color: string }> = {
  [OrderStatus.EXTRACTED]: { label: 'Ready for Review', color: '#3b82f6' },
  [OrderStatus.EXTRACTION_FAILED]: { label: 'Extraction Failed', color: '#ef4444' },
  [OrderStatus.IN_REVIEW]: { label: 'In Review', color: '#8b5cf6' },
  [OrderStatus.APPROVED]: { label: 'Approved', color: '#10b981' },
  [OrderStatus.REJECTED]: { label: 'Rejected', color: '#6b7280' },
};

/** Threshold below which a field is highlighted as uncertain */
export const CONFIDENCE_THRESHOLD = 0.8;
