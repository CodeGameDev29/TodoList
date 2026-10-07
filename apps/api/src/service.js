import { HttpError, validateTask, validateListQuery } from './validation.js';

export function createTaskService(repository, { now = () => new Date() } = {}) {
  const requireTask = (task) => {
    if (!task) throw new HttpError(404, 'Task not found.');
    return task;
  };
  return {
    list: (parameters = new URLSearchParams()) => repository.list({
      ...validateListQuery(parameters), today: now().toISOString().slice(0, 10),
    }),
    get: (id) => requireTask(repository.get(id)),
    create: (body) => repository.create(validateTask(body)),
    update: (id, body) => requireTask(repository.update(id, validateTask(body, true))),
    delete(id) {
      if (!repository.delete(id)) throw new HttpError(404, 'Task not found.');
    },
  };
}
