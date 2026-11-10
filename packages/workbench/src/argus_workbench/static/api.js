// Calls to /api. The per-start token is read from the meta tag of index.html and sent in a header, never in a URL.
// Every error from the server is {"error": {"code", "field", "message"}}; it becomes an ApiError with those fields.

const TOKEN_HEADER = 'X-Workbench-Token';

export class ApiError extends Error {
  constructor(code, field, message, status) {
    super(message);
    this.code = code;
    this.field = field;
    this.status = status;
  }
}

function token() {
  const meta = document.querySelector('meta[name="argus-token"]');
  return meta ? meta.getAttribute('content') : '';
}

export async function api(method, path, body) {
  const headers = {};
  const init = { method, headers, credentials: 'same-origin' };
  if (method !== 'GET' && method !== 'HEAD') {
    headers[TOKEN_HEADER] = token();
    if (body instanceof FormData) init.body = body;
    else if (body !== undefined) {
      headers['Content-Type'] = 'application/json';
      init.body = JSON.stringify(body);
    }
  }
  const response = await fetch(path, init);
  let data = null;
  try {
    data = await response.json();
  } catch {
    // not JSON: handled below
  }
  if (!response.ok) {
    const e = data && data.error ? data.error : {};
    throw new ApiError(e.code || 'bad_response', e.field || null, e.message || `HTTP ${response.status}`, response.status);
  }
  return data;
}
