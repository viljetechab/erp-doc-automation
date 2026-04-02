/**
 * Order API calls — all HTTP interactions for orders.
 *
 * Upload uses a 5-minute timeout because OpenAI Vision can take
 * 2–4 minutes for multi-page PDFs.
 */
import apiClient from './client';
import type {
  Order,
  OrderListItem,
  OrderUpdateRequest,
  OrderApproveResponse,
  ERPPushResponse,
} from '../types/order';

/** Upload timeout: 5 minutes (OpenAI Vision is slow on multi-page PDFs). */
const UPLOAD_TIMEOUT_MS = 5 * 60 * 1000;

export async function uploadPdf(file: File): Promise<Order> {
  if (!file) throw new Error('No file provided');
  if (file.type !== 'application/pdf' && !file.name.endsWith('.pdf')) {
    throw new Error('Only PDF files are accepted');
  }
  const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;
  if (file.size > MAX_UPLOAD_BYTES) {
    throw new Error('File exceeds 50 MB limit');
  }

  const formData = new FormData();
  formData.append('file', file);

  const response = await apiClient.post<Order>('/orders/upload', formData, {
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: UPLOAD_TIMEOUT_MS,
  });
  return response.data;
}

export async function listOrders(params?: {
  status?: string;
  limit?: number;
  offset?: number;
}): Promise<OrderListItem[]> {
  const response = await apiClient.get<OrderListItem[]>('/orders', { params });
  return response.data;
}

export async function getOrder(orderId: string): Promise<Order> {
  const response = await apiClient.get<Order>(`/orders/${orderId}`);
  return response.data;
}

export async function updateOrder(
  orderId: string,
  data: OrderUpdateRequest,
): Promise<Order> {
  const response = await apiClient.patch<Order>(`/orders/${orderId}`, data);
  return response.data;
}

export async function approveOrder(
  orderId: string,
): Promise<OrderApproveResponse> {
  const response = await apiClient.post<OrderApproveResponse>(
    `/orders/${orderId}/approve`,
  );
  return response.data;
}

export async function rejectOrder(orderId: string): Promise<Order> {
  const response = await apiClient.post<Order>(
    `/orders/${orderId}/reject`,
  );
  return response.data;
}

/**
 * Fetch the PDF via axios (with JWT) and return a blob: URL.
 * Revoke the previous blob URL if provided to avoid memory leaks.
 */
export async function fetchPdfBlobUrl(
  orderId: string,
  previousUrl?: string,
): Promise<string> {
  if (previousUrl) {
    URL.revokeObjectURL(previousUrl);
  }
  const response = await apiClient.get(`/orders/${orderId}/pdf`, {
    responseType: 'blob',
  });
  return URL.createObjectURL(response.data as Blob);
}

/**
 * Download the XML file via axios (with JWT), then trigger a
 * browser download via a temporary anchor element.
 */
export async function downloadXml(orderId: string, orderNumber?: string | null): Promise<void> {
  const response = await apiClient.get(`/orders/${orderId}/xml`, {
    responseType: 'blob',
  });
  const blob = response.data as Blob;
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `order_${orderNumber ?? orderId}.xml`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

/** @deprecated Use fetchPdfBlobUrl instead. Kept for backwards compat. */
export function getPdfUrl(orderId: string): string {
  return `/api/v1/orders/${orderId}/pdf`;
}

/** @deprecated Use downloadXml instead. Kept for backwards compat. */
export function getXmlDownloadUrl(orderId: string): string {
  return `/api/v1/orders/${orderId}/xml`;
}

export async function getPreviewXml(orderId: string): Promise<string> {
  const response = await apiClient.get<string>(`/orders/${orderId}/preview-xml`, {
    headers: { Accept: 'application/xml' },
    transformResponse: [(data: string) => data], // keep raw XML string
  });
  return response.data;
}

export async function pushToERP(orderId: string): Promise<ERPPushResponse> {
  const response = await apiClient.post<ERPPushResponse>(
    `/orders/${orderId}/push-to-erp`,
  );
  return response.data;
}


// ── Customer Matching & Import ──────────────────────────────────────────

export interface CustomerMatchResult {
  status: 'matched_exact' | 'matched_fuzzy' | 'unmatched' | 'skipped';
  customer_id: string | null;
  erp_customer_id: string | null;
  customer_name: string | null;
  score: number | null;
  note: string | null;
}

export async function matchOrderCustomer(orderId: string): Promise<CustomerMatchResult> {
  const response = await apiClient.post<CustomerMatchResult>(
    `/customers/${orderId}/match`,
  );
  return response.data;
}

export interface CustomerImportResponse {
  imported: number;
  skipped: number;
  errors: string[];
}

export async function importCustomerCsv(file: File): Promise<CustomerImportResponse> {
  if (!file) throw new Error('No file provided');
  if (!file.name.endsWith('.csv')) {
    throw new Error('Only CSV files are accepted');
  }
  const MAX_CSV_BYTES = 10 * 1024 * 1024;
  if (file.size > MAX_CSV_BYTES) {
    throw new Error('File exceeds 10 MB limit');
  }

  const formData = new FormData();
  formData.append('file', file);
  const response = await apiClient.post<CustomerImportResponse>(
    '/customers/import',
    formData,
    {
      headers: { 'Content-Type': 'multipart/form-data' },
      timeout: 120_000,  // 2 min — large Kundlista CSVs take time to upsert
    },
  );
  return response.data;
}