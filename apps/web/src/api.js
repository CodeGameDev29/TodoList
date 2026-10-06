export async function request(path = '', options = {}) {
  let response;
  try {
    response = await fetch(`/api/todos${path}`, {
      ...options,
      headers: { 'Content-Type': 'application/json', ...options.headers },
    });
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error('Unable to reach the server. Check your connection and try again.');
  }
  if (response.status === 204) return null;
  let data;
  try {
    data = await response.json();
  } catch (error) {
    if (error.name === 'AbortError') throw error;
    throw new Error(response.ok
      ? 'The server returned an unexpected response. Please try again.'
      : 'The request failed. Please try again.');
  }
  if (!response.ok) {
    const error = new Error(data?.error?.message || 'The request failed. Please try again.');
    error.fields = data?.error?.fields;
    throw error;
  }
  return data;
}
