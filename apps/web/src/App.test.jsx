import { beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, screen, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from './App.jsx';

const initialTask = {
  id: 'task-1',
  title: 'Prepare interview',
  description: 'Review the design',
  dueDate: '2026-10-10',
  isCompleted: false,
  createdAt: '2026-10-06T12:00:00.000Z',
};

function respond(data, status = 200) {
  return { ok: status < 400, status, json: async () => data };
}

function mockServer(initial = []) {
  let tasks = initial.map((task) => ({ ...task }));
  const fetch = vi.fn(async (url, options = {}) => {
    const method = options.method ?? 'GET';
    const parsed = new URL(url, 'http://localhost');
    const id = parsed.pathname.split('/')[3];
    if (method === 'GET') {
      if (id) return respond(tasks.find((task) => task.id === id));
      const status = parsed.searchParams.get('status') ?? 'all';
      const sortBy = parsed.searchParams.get('sortBy') ?? 'createdAt';
      const direction = parsed.searchParams.get('order') === 'asc' ? 1 : -1;
      const today = new Date().toISOString().slice(0, 10);
      const result = tasks.filter(
        (task) =>
          status === 'all' ||
          (status === 'completed' && task.isCompleted) ||
          (status === 'incomplete' && !task.isCompleted) ||
          (status === 'overdue' && !task.isCompleted && task.dueDate && task.dueDate < today),
      );
      result.sort((a, b) => {
        if (sortBy === 'dueDate' && (!a.dueDate || !b.dueDate)) {
          if (!!a.dueDate !== !!b.dueDate) return a.dueDate ? -1 : 1;
        }
        const first = String(a[sortBy] ?? '').toLowerCase();
        const second = String(b[sortBy] ?? '').toLowerCase();
        return (
          (first < second ? -1 : first > second ? 1 : 0) * direction || a.id.localeCompare(b.id)
        );
      });
      return respond(result);
    }
    if (method === 'POST') {
      const task = {
        ...initialTask,
        ...JSON.parse(options.body),
        id: 'task-new',
        isCompleted: false,
      };
      tasks = [task, ...tasks];
      return respond(task, 201);
    }
    if (method === 'PATCH') {
      tasks = tasks.map((task) =>
        task.id === id ? { ...task, ...JSON.parse(options.body) } : task,
      );
      return respond(tasks.find((task) => task.id === id));
    }
    if (method === 'DELETE') {
      tasks = tasks.filter((task) => task.id !== id);
      return respond(null, 204);
    }
    throw new Error('Unexpected request');
  });
  vi.stubGlobal('fetch', fetch);
  return fetch;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

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
    expect(fetch).toHaveBeenCalledWith(
      '/api/todos/task-new',
      expect.objectContaining({ signal: expect.any(AbortSignal) }),
    );
    expect(screen.getByText('Review the design')).toBeInTheDocument();
    await user.click(screen.getByRole('button', { name: 'Edit task' }));
    await user.clear(screen.getByLabelText(/Description/));
    await user.clear(screen.getByLabelText(/Due date/));
    await user.click(screen.getByRole('button', { name: 'Save changes' }));
    await screen.findByText('No description.');
    expect(fetch).toHaveBeenCalledWith(
      '/api/todos/task-new',
      expect.objectContaining({
        method: 'PATCH',
        body: JSON.stringify({ title: 'Prepare interview', description: null, dueDate: null }),
      }),
    );
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
    fetch.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finish = resolve;
        }),
    );
    await user.click(screen.getByRole('button', { name: 'Add task' }));
    expect(screen.getByLabelText(/Title/)).toBeDisabled();
    expect(screen.getByRole('button', { name: 'New task' })).toBeDisabled();
    finish(respond({ ...initialTask, title: 'Slow save' }, 201));
    await waitFor(() => expect(screen.getByLabelText(/Title/)).toBeEnabled());
  });

  it('requests combined filter and sorting choices and displays server results in order', async () => {
    const fetch = mockServer([
      initialTask,
      { ...initialTask, id: 'task-2', title: 'Alpha', isCompleted: true },
      { ...initialTask, id: 'task-3', title: 'Zebra', isCompleted: true },
    ]);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('checkbox', { name: 'Mark Prepare interview complete' });
    await user.selectOptions(screen.getByLabelText('Filter'), 'completed');
    await screen.findByRole('checkbox', { name: 'Mark Alpha incomplete' });
    expect(
      screen.queryByRole('checkbox', { name: 'Mark Prepare interview complete' }),
    ).not.toBeInTheDocument();
    await user.selectOptions(screen.getByLabelText('Sort by'), 'title');
    await user.selectOptions(screen.getByLabelText('Order'), 'asc');
    await waitFor(() =>
      expect(
        screen.getAllByRole('checkbox').map((item) => item.getAttribute('aria-label')),
      ).toEqual(['Mark Alpha incomplete', 'Mark Zebra incomplete']),
    );
    expect(fetch).toHaveBeenCalledWith(
      '/api/todos?status=completed&sortBy=title&order=asc',
      expect.any(Object),
    );
    await user.selectOptions(screen.getByLabelText('Order'), 'desc');
    await waitFor(() =>
      expect(screen.getAllByRole('checkbox')[0]).toHaveAccessibleName('Mark Zebra incomplete'),
    );
  });

  it('refreshes the active filtered view after completion and retains its controls', async () => {
    const fetch = mockServer([initialTask]);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('checkbox');
    await user.selectOptions(screen.getByLabelText('Filter'), 'incomplete');
    await screen.findByRole('checkbox');
    await user.selectOptions(screen.getByLabelText('Sort by'), 'dueDate');
    await user.selectOptions(screen.getByLabelText('Order'), 'asc');
    await screen.findByRole('checkbox');
    await user.click(screen.getByRole('checkbox'));
    await screen.findByText('No matching tasks');
    expect(screen.queryByText('A fresh start')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Filter')).toHaveValue('incomplete');
    expect(screen.getByLabelText('Sort by')).toHaveValue('dueDate');
    expect(screen.getByLabelText('Order')).toHaveValue('asc');
    expect(fetch.mock.calls.at(-1)[0]).toBe(
      '/api/todos?status=incomplete&sortBy=dueDate&order=asc',
    );
    await user.selectOptions(screen.getByLabelText('Filter'), 'completed');
    await screen.findByRole('checkbox', { name: 'Mark Prepare interview incomplete' });
  });

  it('shows overdue matches and distinguishes a filtered empty view from an empty task list', async () => {
    mockServer([
      { ...initialTask, id: 'past', title: 'Past deadline', dueDate: '2000-01-01' },
      { ...initialTask, id: 'future', title: 'Future deadline', dueDate: '9999-01-01' },
      {
        ...initialTask,
        id: 'done',
        title: 'Already done',
        dueDate: '2000-01-01',
        isCompleted: true,
      },
      { ...initialTask, id: 'undated', title: 'No deadline', dueDate: null },
    ]);
    const user = userEvent.setup();
    render(<App />);
    await screen.findAllByRole('checkbox');
    await user.selectOptions(screen.getByLabelText('Filter'), 'overdue');
    await screen.findByRole('checkbox', { name: 'Mark Past deadline complete' });
    expect(screen.getAllByRole('checkbox')).toHaveLength(1);
    expect(screen.getByText('Incomplete tasks due before today (UTC).')).toBeInTheDocument();
    await user.click(screen.getByRole('checkbox'));
    await screen.findByText('No matching tasks');
  });

  it('retains a successful create when its list refresh fails and retries only the read', async () => {
    const fetch = mockServer();
    const user = userEvent.setup();
    render(<App />);
    await screen.findByText('A fresh start');
    await user.type(screen.getByLabelText(/Title/), 'Created once');
    // The successful write is followed by detail and list reads; fail only the list read.
    const server = fetch.getMockImplementation();
    let failRefresh = true;
    fetch.mockImplementation(async (url, options = {}) => {
      if (url.includes('?') && failRefresh) {
        failRefresh = false;
        throw new TypeError('Read offline');
      }
      return server(url, options);
    });
    await user.click(screen.getByRole('button', { name: 'Add task' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('Unable to refresh tasks');
    expect(screen.getByText('Task created.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Title/)).toHaveValue('');
    await user.click(screen.getByRole('button', { name: 'Retry loading' }));
    await screen.findByRole('checkbox', { name: 'Mark Created once complete' });
    expect(fetch.mock.calls.filter(([, options]) => options.method === 'POST')).toHaveLength(1);
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
  });

  it('ignores an older query response that finishes after the selected filter response', async () => {
    const fetch = mockServer([initialTask]);
    const user = userEvent.setup();
    render(<App />);
    await screen.findByRole('checkbox');
    let finishOlder;
    fetch.mockImplementationOnce(
      () =>
        new Promise((resolve) => {
          finishOlder = resolve;
        }),
    );
    await user.selectOptions(screen.getByLabelText('Filter'), 'incomplete');
    await user.selectOptions(screen.getByLabelText('Filter'), 'completed');
    await screen.findByText('No matching tasks');
    await act(async () => finishOlder(respond([initialTask])));
    expect(screen.getByLabelText('Filter')).toHaveValue('completed');
    expect(screen.getByText('No matching tasks')).toBeInTheDocument();
    expect(screen.queryByRole('checkbox')).not.toBeInTheDocument();
  });
});
