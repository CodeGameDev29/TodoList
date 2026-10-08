import express from 'express';
import { fileURLToPath } from 'node:url';
import { existsSync } from 'node:fs';
import { createTaskService } from './service.js';

export function createApp(
  repository,
  {
    serveWeb = false,
    webPath = fileURLToPath(new URL('../../web/dist/', import.meta.url)),
    now,
  } = {},
) {
  const app = express();
  const service = createTaskService(repository, { now });
  app.disable('x-powered-by');
  app.use('/api', express.json({ limit: '100kb' }));
  app.get('/api/todos', (req, res) =>
    res.json(service.list(new URL(req.originalUrl, 'http://localhost').searchParams)),
  );
  app.post('/api/todos', (req, res) => {
    const task = service.create(req.body);
    res.location(`/api/todos/${task.id}`).status(201).json(task);
  });
  app.get('/api/todos/:id', (req, res) => res.json(service.get(req.params.id)));
  app.patch('/api/todos/:id', (req, res) => res.json(service.update(req.params.id, req.body)));
  app.delete('/api/todos/:id', (req, res) => {
    service.delete(req.params.id);
    res.status(204).end();
  });
  app.use('/api', (req, res) =>
    res.status(404).json({ error: { message: 'API route not found.' } }),
  );
  if (serveWeb && existsSync(webPath)) {
    app.use(express.static(webPath));
    app.get('/{*path}', (req, res) => res.sendFile('index.html', { root: webPath }));
  }
  app.use((error, req, res, next) => {
    if (res.headersSent) return next(error);
    const bodyError = error.type === 'entity.parse.failed' || error.type === 'entity.too.large';
    const status = bodyError ? 400 : (error.status ?? 500);
    const message = bodyError
      ? 'Request body must contain valid JSON within 100kb.'
      : status < 500
        ? error.message
        : 'An unexpected error occurred.';
    res
      .status(status)
      .json({ error: { message, ...(error.fields ? { fields: error.fields } : {}) } });
  });
  return app;
}
