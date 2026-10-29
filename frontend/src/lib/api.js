import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

const NO_REFRESH = /\/auth\/(login|register|refresh|logout)/;
export const SERVICE_DOWN_EVENT = "sihha:service-down";
const DOWN_STATUSES = [502, 503, 504];

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const data = error.response?.data;
    if (data?.code === "service_unavailable") {
      window.dispatchEvent(new Event(SERVICE_DOWN_EVENT));
    } else if (!original?.url?.endsWith("/health") && error.code !== "ERR_CANCELED"
      && (!error.response || DOWN_STATUSES.includes(status))) {
      api.get("/health").catch(() => window.dispatchEvent(new Event(SERVICE_DOWN_EVENT)));
    }
    if (status === 401 && original && !original._retry && !NO_REFRESH.test(original.url)) {
      original._retry = true;
      try {
        await api.post("/auth/refresh");
        return api(original);
      } catch {}
    }
    return Promise.reject(error);
  }
);
