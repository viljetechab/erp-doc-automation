/**
 * Articles API client — search and validate article/part numbers.
 */
import apiClient from './client';

export interface ArticleResult {
  id: number;
  artikelnummer: string;
  artikelbenamning: string;
  standardpris: number | null;
}

export interface ValidationResult {
  valid: ArticleResult[];
  invalid: string[];
}

/**
 * Search articles by artikelnummer or artikelbenamning.
 * Returns matching articles for the autocomplete dropdown.
 */
export async function searchArticles(
  query: string,
  limit = 15,
): Promise<ArticleResult[]> {
  if (!query.trim()) return [];
  const { data } = await apiClient.get<ArticleResult[]>('/articles/search', {
    params: { q: query, limit },
  });
  return data;
}

/**
 * Batch-validate part numbers against the articles catalogue.
 */
export async function validatePartNumbers(
  partNumbers: string[],
): Promise<ValidationResult> {
  if (partNumbers.length === 0) return { valid: [], invalid: [] };
  const { data } = await apiClient.get<ValidationResult>('/articles/validate', {
    params: { part_numbers: partNumbers.join(',') },
  });
  return data;
}

// ── Article Import ──────────────────────────────────────────────────────

export interface ArticleImportResponse {
  imported: number;
  updated: number;
  skipped: number;
  errors: string[];
}

/**
 * Upload a CSV or XLSX file to import/update articles in the catalogue.
 */
export async function importArticles(file: File): Promise<ArticleImportResponse> {
  if (!file) throw new Error('No file provided');
  const ext = file.name.split('.').pop()?.toLowerCase();
  if (ext !== 'csv' && ext !== 'xlsx') {
    throw new Error('Only CSV and XLSX files are accepted');
  }
  const MAX_BYTES = 20 * 1024 * 1024;
  if (file.size > MAX_BYTES) {
    throw new Error('File exceeds 20 MB limit');
  }
  const formData = new FormData();
  formData.append('file', file);
  const { data } = await apiClient.post<ArticleImportResponse>(
    '/articles/import',
    formData,
    { headers: { 'Content-Type': 'multipart/form-data' }, timeout: 300_000 },
  );
  return data;
}
