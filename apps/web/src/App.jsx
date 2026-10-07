import { useEffect, useRef, useState } from 'react';
import { request } from './api.js';

const emptyForm = { title: '', description: '', dueDate: '' };

function validate(form) {
  const errors = {};
  if (!form.title.trim()) errors.title = 'Enter a title.';
  else if (form.title.trim().length > 200) errors.title = 'Use 200 characters or fewer.';
  if (form.description.length > 5000) errors.description = 'Use 5,000 characters or fewer.';
  if (form.dueDate) {
    const parsed = new Date(`${form.dueDate}T00:00:00.000Z`);
    if (!/^\d{4}-\d{2}-\d{2}$/.test(form.dueDate) || form.dueDate.startsWith('0000') ||
      Number.isNaN(parsed.getTime()) || parsed.toISOString().slice(0, 10) !== form.dueDate) {
      errors.dueDate = 'Enter a valid date.';
    }
  }
  return errors;
}

export default function App() {
  const [todos, setTodos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [listError, setListError] = useState('');
  const [status, setStatus] = useState('all');
  const [sortBy, setSortBy] = useState('createdAt');
  const [order, setOrder] = useState('desc');
  const [selectedId, setSelectedId] = useState(null);
  const [detail, setDetail] = useState(null);
  const [detailLoading, setDetailLoading] = useState(false);
  const [detailError, setDetailError] = useState('');
  const [detailAttempt, setDetailAttempt] = useState(0);
  const [editingId, setEditingId] = useState(null);
  const [form, setForm] = useState(emptyForm);
  const [fields, setFields] = useState({});
  const [error, setError] = useState('');
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState('');
  const titleRef = useRef(null);
  const listRequest = useRef(0);
  const listController = useRef(null);
  const listQuery = `?${new URLSearchParams({ status, sortBy, order })}`;

  async function loadList() {
    listController.current?.abort();
    const controller = new AbortController();
    listController.current = controller;
    const attempt = ++listRequest.current;
    setLoading(true);
    setListError('');
    try {
      const tasks = await request(listQuery, { signal: controller.signal });
      if (attempt === listRequest.current && !controller.signal.aborted) setTodos(tasks);
    } catch (failure) {
      if (attempt === listRequest.current && !controller.signal.aborted && failure.name !== 'AbortError') {
        setListError(`Unable to refresh tasks. ${failure.message}`);
      }
    } finally {
      if (attempt === listRequest.current && !controller.signal.aborted) setLoading(false);
    }
  }

  useEffect(() => {
    loadList();
    return () => listController.current?.abort();
  }, [listQuery]);

  useEffect(() => {
    setDetail(null);
    setDetailError('');
    if (!selectedId) { setDetailLoading(false); return; }
    const controller = new AbortController();
    setDetailLoading(true);
    request(`/${selectedId}`, { signal: controller.signal })
      .then(setDetail)
      .catch(failure => { if (failure.name !== 'AbortError') setDetailError(failure.message); })
      .finally(() => { if (!controller.signal.aborted) setDetailLoading(false); });
    return () => controller.abort();
  }, [selectedId, detailAttempt]);

  function newTask() {
    setEditingId(null);
    setForm(emptyForm);
    setFields({});
    setError('');
    titleRef.current?.focus();
  }

  function editTask() {
    setEditingId(detail.id);
    setForm({ title: detail.title, description: detail.description ?? '', dueDate: detail.dueDate ?? '' });
    setFields({});
    setError('');
    titleRef.current?.focus();
  }

  function replaceTask(task) {
    setTodos(current => current.map(todo => todo.id === task.id ? task : todo));
    if (selectedId === task.id) setDetail(task);
  }

  async function saveTask(event) {
    event.preventDefault();
    const invalid = validate(form);
    setFields(invalid);
    setError('');
    setNotice('');
    if (Object.keys(invalid).length) {
      document.getElementById(Object.keys(invalid)[0])?.focus();
      return;
    }
    setSaving(true);
    try {
      const task = await request(editingId ? `/${editingId}` : '', {
        method: editingId ? 'PATCH' : 'POST',
        body: JSON.stringify({ title: form.title.trim(), description: form.description || null, dueDate: form.dueDate || null }),
      });
      if (editingId) replaceTask(task);
      setNotice(editingId ? 'Task updated.' : 'Task created.');
      setSelectedId(task.id);
      newTask();
      await loadList();
    } catch (failure) {
      setError(failure.message);
      setFields(failure.fields ?? {});
    } finally { setSaving(false); }
  }

  async function toggleTask(task) {
    setSaving(true);
    setError('');
    setNotice('');
    try {
      replaceTask(await request(`/${task.id}`, { method: 'PATCH', body: JSON.stringify({ isCompleted: !task.isCompleted }) }));
      setNotice(task.isCompleted ? 'Task reopened.' : 'Task completed.');
      await loadList();
    } catch (failure) { setError(failure.message); }
    finally { setSaving(false); }
  }

  async function deleteTask() {
    if (!window.confirm(`Delete "${detail.title}"? This cannot be undone.`)) return;
    setSaving(true);
    setError('');
    setNotice('');
    try {
      await request(`/${detail.id}`, { method: 'DELETE' });
      setTodos(current => current.filter(todo => todo.id !== detail.id));
      if (editingId === detail.id) newTask();
      setSelectedId(null);
      setNotice('Task deleted.');
      await loadList();
    } catch (failure) { setError(failure.message); }
    finally { setSaving(false); }
  }

  return <main className="app">
    <header className="page-header">
      <div><p className="eyebrow">A little clarity, every day</p><h1>TodoList</h1><p className="subtitle">Keep your tasks in one place.</p></div>
      <button onClick={newTask} disabled={saving || loading}>New task</button>
    </header>
    <div className="feedback" aria-live="polite"><span>{saving ? 'Saving…' : notice}</span></div>
    {error && <p className="error-banner" role="alert">{error}</p>}
    <div className="workspace">
      <section className="panel tasks" aria-labelledby="tasks-heading">
        <div className="section-heading"><h2 id="tasks-heading">Your tasks</h2><span className="count">{todos.length}</span></div>
        <div className="list-controls">
          <div><label htmlFor="filter">Filter</label><select id="filter" value={status} disabled={saving} onChange={event => setStatus(event.target.value)}>
            <option value="all">All tasks</option><option value="incomplete">Incomplete</option><option value="completed">Completed</option><option value="overdue">Overdue</option>
          </select></div>
          <div><label htmlFor="sortBy">Sort by</label><select id="sortBy" value={sortBy} disabled={saving} onChange={event => setSortBy(event.target.value)}>
            <option value="createdAt">Created date</option><option value="dueDate">Due date</option><option value="title">Title</option>
          </select></div>
          <div><label htmlFor="order">Order</label><select id="order" value={order} disabled={saving} onChange={event => setOrder(event.target.value)}>
            <option value="asc">Ascending</option><option value="desc">Descending</option>
          </select></div>
        </div>
        {status === 'overdue' && <p className="filter-help">Incomplete tasks due before today (UTC).</p>}
        {loading ? <p role="status" className="placeholder">Loading tasks…</p> : listError ? <div className="placeholder"><p role="alert">{listError}</p><button onClick={() => loadList()} disabled={saving}>Retry loading</button></div> : !todos.length ? <div className="placeholder"><h3>{status === 'all' ? 'A fresh start' : 'No matching tasks'}</h3><p>{status === 'all' ? 'Add your first task using the form.' : 'Try another filter or add a task.'}</p></div> :
          <ul className="task-list">{todos.map(todo => <li key={todo.id} className={`${selectedId === todo.id ? 'selected' : ''} ${todo.isCompleted ? 'completed' : ''}`}>
            <input type="checkbox" checked={todo.isCompleted} disabled={saving || detailLoading} onChange={() => toggleTask(todo)} aria-label={`Mark ${todo.title} ${todo.isCompleted ? 'incomplete' : 'complete'}`} />
            <button className="task-select" disabled={saving} onClick={() => setSelectedId(todo.id)} aria-pressed={selectedId === todo.id}>
              <span className="task-title">{todo.title}</span><span className="task-meta">{todo.dueDate ? `Due ${todo.dueDate}` : 'No due date'}<span className="status-badge">{todo.isCompleted ? 'Completed' : 'Open'}</span></span>
            </button>
          </li>)}</ul>}
      </section>
      <div className="side-column">
        <section className="panel" aria-labelledby="form-heading">
          <h2 id="form-heading">{editingId ? 'Edit task' : 'Add a task'}</h2>
          <form noValidate onSubmit={saveTask}>
            <fieldset disabled={saving || loading}>
              <label htmlFor="title">Title <span className="required">(required)</span></label>
              <input id="title" ref={titleRef} value={form.title} onChange={event => setForm({ ...form, title: event.target.value })} aria-invalid={!!fields.title} aria-describedby={fields.title ? 'title-error' : undefined} />
              {fields.title && <p id="title-error" className="field-error">{fields.title}</p>}
              <label htmlFor="description">Description <span className="optional">(optional)</span></label>
              <textarea id="description" rows="3" value={form.description} onChange={event => setForm({ ...form, description: event.target.value })} aria-invalid={!!fields.description} aria-describedby={fields.description ? 'description-error' : undefined} />
              {fields.description && <p id="description-error" className="field-error">{fields.description}</p>}
              <label htmlFor="dueDate">Due date <span className="optional">(optional)</span></label>
              <input id="dueDate" type="date" min="0001-01-01" max="9999-12-31" value={form.dueDate} onChange={event => setForm({ ...form, dueDate: event.target.value })} aria-invalid={!!fields.dueDate} aria-describedby={fields.dueDate ? 'date-error' : undefined} />
              {fields.dueDate && <p id="date-error" className="field-error">{fields.dueDate}</p>}
              <div className="form-actions"><button className="primary" type="submit">{saving ? 'Saving…' : editingId ? 'Save changes' : 'Add task'}</button>{editingId && <button type="button" onClick={newTask}>Cancel edit</button>}</div>
            </fieldset>
          </form>
        </section>
        <section className="panel details" aria-labelledby="details-heading">
          <h2 id="details-heading">Task details</h2>
          {!selectedId ? <p className="muted">Select a task to see its details.</p> : detailLoading ? <p role="status">Loading details…</p> : detailError ? <div><p role="alert">{detailError}</p><button disabled={saving} onClick={() => setDetailAttempt(current => current + 1)}>Retry details</button></div> : detail && <>
            <h3>{detail.title}</h3><p className="description">{detail.description || 'No description.'}</p>
            <dl><div><dt>Status</dt><dd>{detail.isCompleted ? 'Completed' : 'Open'}</dd></div><div><dt>Due date</dt><dd>{detail.dueDate || 'No due date'}</dd></div><div><dt>Created</dt><dd><time dateTime={detail.createdAt}>{new Date(detail.createdAt).toLocaleString()}</time></dd></div></dl>
            <div className="form-actions"><button disabled={saving} onClick={editTask}>Edit task</button><button className="danger" disabled={saving} onClick={deleteTask}>Delete task</button></div>
          </>}
        </section>
      </div>
    </div>
  </main>;
}
