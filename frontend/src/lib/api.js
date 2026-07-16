import axios from "axios";

export const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const api = axios.create({
  baseURL: API,
  withCredentials: true,
});

const NO_REFRESH = /\/auth\/(login|register|refresh|logout)/;

api.interceptors.response.use(
  (res) => res,
  async (error) => {
    const original = error.config;
    if (error.response?.status === 401 && original && !original._retry && !NO_REFRESH.test(original.url)) {
      original._retry = true;
      try {
        await api.post("/auth/refresh");
        return api(original);
      } catch {}
    }
    return Promise.reject(error);
  }
);
