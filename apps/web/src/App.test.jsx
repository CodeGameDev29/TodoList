import { beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App.jsx';

const initialTask = {
  id: 'task-1', title: 'Prepare interview', description: 'Review the design',
  dueDate: '2026-10-10', isCompleted: false, createdAt: '2026-10-06T12:00:00.000Z',
};

function respond(data, status = 200) {
  return { ok: status < 400, status, json: async () => data };
}

function mockServer(initial = []) {
  let tasks = initial.map(task => ({ ...task }));
  const fetch = vi.fn(async (url, options = {}) => {
    const method = options.method ?? 'GET';
    const id = url.split('/')[3];
    if (method === 'GET') return respond(id ? tasks.find(task => task.id === id) : tasks);
    if (method === 'POST') {
      const task = { ...initialTask, ...JSON.parse(options.body), id: 'task-new', isCompleted: false };
      tasks = [task, ...tasks];
      return respond(task, 201);
    }
    if (method === 'PATCH') {
      tasks = tasks.map(task => task.id === id ? { ...task, ...JSON.parse(options.body) } : task);
      return respond(tasks.find(task => task.id === id));
    }
    if (method === 'DELETE') { tasks = tasks.filter(task => task.id !== id); return respond(null, 204); }
    throw new Error('Unexpected request');
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

beforeEach(() => { vi.restoreAllMocks(); });

describe('task workflow', () => {
  it('creates, fetches details, clears optional fields, completes, reopens and confirms deletion', async () => {
    const fetch = mockServer();
    const user = userEvent.setup();
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<App />);
    await screen.findByText('A fresh start');
    await user.type(screen.getByLabelText(/Title/), 'Prepare interview');
    await user.type(screen.getByLabelText(/Description/), 'Review the design');
    await user.type(screen.getByLabelText(/Due date/), '2026-10-10');
    await user.click(screen.getByRole('button', { name: 'Add task' }));
    await screen.findByRole('button', { name: 'Edit task' });
    expect(fetch).toHaveBeenCalledWith('/api/todos/task-new', expect.objectContaining({ signal: expect.any(AbortSignal) }));
    expect(screen.getByText('Review the design')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Edit task' }));
    await user.clear(screen.getByLabelText(/Description/));
    await user.clear(screen.getByLabelText(/Due date/));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await screen.findByText('No description.');
    expect(fetch).toHaveBeenCalledWith('/api/todos/task-new', expect.objectContaining({
      method: 'PATCH', body: JSON.stringify({ title: 'Prepare interview', description: null, dueDate: null }),
    }));
    await user.click(screen.getByRole('checkbox', { name: 'Mark Prepare interview complete' }));
    await screen.findByRole('checkbox', { name: 'Mark Prepare interview incomplete' });
    await user.click(screen.getByRole('checkbox', { name: 'Mark Prepare interview incomplete' }));
    await screen.findByRole('checkbox', { name: 'Mark Prepare interview complete' });
    await user.click(screen.getByRole('button', { name: 'Delete task' }));
    expect(confirm).toHaveBeenCalledOnce();
    expect(screen.getByRole('checkbox')).toBeInTheDocument();
    expect(fetch.mock.calls.filter(([, options]) => options.method === 'DELETE')).toHaveLength(0);
    confirm.mockReturnValue(true);
    await user.click(screen.getByRole('button', { name: 'Delete task' }));
    await screen.findByText('A fresh start');
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });

  it('retains input after a failed save and permits retry', async () => {
    const fetch = mockServer();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('A fresh start');
    await user.type(screen.getByLabelText(/Title/), 'Keep my draft');
    await user.type(screen.getByLabelText(/Description/), 'Still here');
    fetch.mockRejectedValueOnce(new TypeError('Network disconnected'));
    await user.click(screen.getByRole('button', { name: 'Add task' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to reach the server');
    expect(screen.getByLabelText(/Title/)).toHaveValue('Keep my draft');
    expect(screen.getByLabelText(/Description/)).toHaveValue('Still here');
    expect(screen.getByRole('button', { name: 'Add task' })).toBeEnabled();
    await user.click(screen.getByRole('button', { name: 'Add task' }));
    await screen.findByRole('button', { name: 'Edit task' });
    expect(screen.getByText('Task created.')).toBeInTheDocument();
  });

  it('validates a whitespace title before contacting the API and focuses its field', async () => {
    const fetch = mockServer();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('A fresh start');
    await user.type(screen.getByLabelText(/Title/), '   ');
    await user.click(screen.getByRole('button', { name: 'Add task' }));
    expect(screen.getByText('Enter a title.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Title/)).toHaveFocus();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('shows a loading failure with a working retry', async () => {
    const fetch = mockServer([initialTask]);
    fetch.mockRejectedValueOnce(new TypeError('Offline'));
    const user = userEvent.setup();
    render(<App />);
    expect(screen.getByText('Loading tasks…')).toBeInTheDocument();
    await screen.findByRole('alert');
    await user.click(screen.getByRole('button', { name: 'Retry loading' }));
    await screen.findByRole('checkbox', { name: 'Mark Prepare interview complete' });
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('disables writes while a save is pending', async () => {
    const fetch = mockServer();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('A fresh start');
    await user.type(screen.getByLabelText(/Title/), 'Slow save');
    let finish;
    fetch.mockImplementationOnce(() => new Promise(resolve => { finish = resolve; }));
    await user.click(screen.getByRole('button', { name: 'Add task' }));
    expect(screen.getByLabelText(/Title/)).toBeDisabled();
    expect(screen.getByRole('button', { name: 'New task' })).toBeDisabled();
    finish(respond({ ...initialTask, title: 'Slow save' }, 201));
    await waitFor(() => expect(screen.getByLabelText(/Title/)).toBeEnabled());
  });
});
