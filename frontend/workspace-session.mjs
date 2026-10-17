// Only an authentication failure permits starting a fresh sample session.
export async function ensureWorkspace(api, refresh) {
  try {
    await refresh();
  } catch (error) {
    if (error.httpStatus !== 401) throw error;
    await api('/api/demo', {});
    await refresh();
  }
}
