import axios from "axios";

// ======================================================
// API BASE URL
// ======================================================

const API_BASE_URL =
  import.meta.env.VITE_API_URL ||
  "https://student-registration-fhjf.onrender.com/api";

// ======================================================
// AXIOS INSTANCE
// ======================================================

const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    "Content-Type": "application/json",
  },
});

// ======================================================
// REQUEST INTERCEPTOR
// ======================================================

api.interceptors.request.use(
  (config) => {

    const token = localStorage.getItem("token");

    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }

    return config;
  },
  (error) => Promise.reject(error)
);

// ======================================================
// RESPONSE INTERCEPTOR
// ======================================================

api.interceptors.response.use(
  (response) => response,
  (error) => {

    if (error.response?.status === 401) {

      localStorage.removeItem("token");
      localStorage.removeItem("student");

      window.location.href = "/";
    }

    return Promise.reject(error);
  }
);

// ======================================================
// AUTH APIs
// ======================================================

export const loginStudent = async (data) => {
  const response = await api.post("/login", data);
  return response.data;
};

// ======================================================
// STUDENT APIs
// ======================================================

export const getStudent = async (studentId) => {
  const response = await api.get(`/student/${studentId}`);
  return response.data;
};

export const updateTshirt = async (data) => {
  const response = await api.post(
    "/student/update-tshirt",
    data
  );

  return response.data;
};

// ======================================================
// PRICING
// ======================================================

export const getPricing = async () => {
  const response = await api.get("/pricing");
  return response.data;
};

// ======================================================
// PAYMENT APIs
// ======================================================

export const createCheckout = async (data) => {
  const response = await api.post(
    "/payment/create-checkout",
    data
  );

  return response.data;
};

export const getPaymentStatus = async (sessionId) => {
  const response = await api.get(
    `/payment/status/${sessionId}`
  );

  return response.data;
};

// ======================================================
// ADMIN APIs
// ======================================================

export const getAdminStats = async () => {
  const response = await api.get("/admin/stats");
  return response.data;
};

// ======================================================
// HEALTH CHECK
// ======================================================

export const checkHealth = async () => {
  const response = await api.get("/health");
  return response.data;
};

// ======================================================
// EXPORT
// ======================================================

export default api;