import { HttpError, validateTask } from './validation.js';

export function createTaskService(repository) {
  const requireTask = (task) => {
    if (!task) throw new HttpError(404, 'Task not found.');
    return task;
  };
  return {
    list: () => repository.list(),
    get: (id) => requireTask(repository.get(id)),
    create: (body) => repository.create(validateTask(body)),
    update: (id, body) => requireTask(repository.update(id, validateTask(body, true))),
    delete(id) {
      if (!repository.delete(id)) throw new HttpError(404, 'Task not found.');
    },
  };
}
