/**
 * Axios HTTP client.
 *
 * FIXED (#5): Tokens are stored in HttpOnly cookies set by the backend.
 * JavaScript never sees or touches token values.
 *
 * baseURL strategy:
 *   - Development: VITE_API_URL is unset → Vite proxy forwards /api → localhost:8000
 *   - Production:  VITE_API_URL = backend Azure App Service URL (set in Azure env vars)
 *     e.g. https://orderflow-pro-dev-be-aea8aahmeah9dsht.swedencentral-01.azurewebsites.net
 */
import axios from 'axios';

const BASE_URL = import.meta.env.VITE_API_URL
  ? `${import.meta.env.VITE_API_URL as string}/api/v1`
  : '/api/v1';

const apiClient = axios.create({
  baseURL: BASE_URL,
  timeout: 30_000,
  withCredentials: true,          // send & receive HttpOnly cookies
  headers: { 'Content-Type': 'application/json' },
});

// ── Response interceptor — silent token rotation ──────────────────────────

let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value: unknown) => void;
  reject: (reason: unknown) => void;
}> = [];

function processQueue(error: unknown) {
  failedQueue.forEach(({ resolve, reject }) =>
    error ? reject(error) : resolve(null),
  );
  failedQueue = [];
}

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    const originalRequest = error.config;
    const httpStatus = error.response?.status;

    // On 401, try a silent cookie-based token refresh
    if (
      httpStatus === 401 &&
      !originalRequest._retry &&
      !originalRequest.url?.includes('/auth/')
    ) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        }).then(() => apiClient(originalRequest));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        // POST to /refresh — backend reads the HttpOnly refresh cookie
        // and sets new HttpOnly access + refresh cookies.
        await axios.post(`${BASE_URL}/auth/refresh`, null, { withCredentials: true });
        processQueue(null);
        return apiClient(originalRequest);
      } catch (refreshError) {
        processQueue(refreshError);
        window.location.href = '/login';
        return Promise.reject(refreshError);
      } finally {
        isRefreshing = false;
      }
    }

    // Standard error extraction
    const serverMessage = error.response?.data?.error?.message;
    const serverCode = error.response?.data?.error?.code;
    let message: string;

    if (error.code === 'ECONNABORTED') {
      message = 'Request timed out — please check the Orders page.';
    } else if (serverMessage) {
      message = serverMessage;
    } else if (httpStatus) {
      message = `Server error (${httpStatus}): ${error.message}`;
    } else {
      message = error.message ?? 'Network error — check your connection';
    }

    console.error('[API Error]', message, { status: httpStatus, code: serverCode });
    return Promise.reject(new Error(message));
  },
);

export default apiClient;