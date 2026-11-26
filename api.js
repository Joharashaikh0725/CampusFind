const API = window.API_BASE || location.origin;
const api = {
  token: localStorage.getItem('cf_token'),
  setToken(t) { api.token = t; t ? localStorage.setItem('cf_token', t) : localStorage.removeItem('cf_token'); },
  async req(path, method = 'GET', body) {
    const headers = { 'Content-Type': 'application/json' };
    if (api.token) headers.Authorization = 'Bearer ' + api.token;
    let res;
    try {
      res = await fetch(API + path, { method, headers, body: body ? JSON.stringify(body) : undefined });
    } catch (e) {
      throw new Error('Cannot reach the server. Check that the backend is running.');
    }
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      if (res.status === 401 && api.token) { api.setToken(null); location.reload(); }
      const d = data.detail, first = Array.isArray(d) ? d[0] : null;
      const field = first && first.loc ? String(first.loc[first.loc.length - 1]).replace(/_/g, ' ') : '';
      throw new Error(typeof d === 'string' ? d : first && first.msg ? `${field ? field + ': ' : ''}${first.msg}` : 'Check the form and try again.');
    }
    return data;
  },
};
