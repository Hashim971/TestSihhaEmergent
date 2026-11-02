const KEY = "sihha_recent_accounts";
const CURRENT = "sihha_current_account";

export const getRecentAccounts = () => {
  try {
    return JSON.parse(localStorage.getItem(KEY)) || [];
  } catch {
    return [];
  }
};

export const getCurrentAccount = () => {
  try {
    return JSON.parse(localStorage.getItem(CURRENT));
  } catch {
    return null;
  }
};

export const rememberAccount = ({ account_id, name }) => {
  const next = [{ account_id, name }, ...getRecentAccounts().filter((a) => a.account_id !== account_id)].slice(0, 6);
  localStorage.setItem(KEY, JSON.stringify(next));
  localStorage.setItem(CURRENT, JSON.stringify({ account_id, name }));
  window.dispatchEvent(new Event("sihha:account-switched"));
};
