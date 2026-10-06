import { createApp } from './app.js';
import { createRepository, defaultDatabasePath } from './repository.js';

const repository = createRepository(process.env.DATABASE_PATH || defaultDatabasePath);
const app = createApp(repository, { serveWeb: process.argv.includes('--serve-web') || process.env.NODE_ENV === 'production' });
const server = app.listen(Number(process.env.PORT || 3001), process.env.HOST || '127.0.0.1', () => {
  console.log(`TodoList listening on http://${process.env.HOST || '127.0.0.1'}:${server.address().port}`);
});
for (const signal of ['SIGINT', 'SIGTERM']) {
  process.once(signal, () => server.close(() => { repository.close(); process.exit(0); }));
}
