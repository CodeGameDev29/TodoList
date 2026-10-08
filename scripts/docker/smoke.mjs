import { execFileSync } from 'node:child_process';
import assert from 'node:assert/strict';
import { randomUUID } from 'node:crypto';

const image = process.argv[2] || 'todolist:smoke';
const suffix = randomUUID();
const container = `todolist-smoke-${suffix}`;
const volume = `todolist-smoke-data-${suffix}`;
const docker = (...args) =>
  execFileSync('docker', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] }).trim();
const pause = () => new Promise((resolve) => setTimeout(resolve, 500));
let baseUrl;

async function start() {
  docker(
    'run',
    '-d',
    '--name',
    container,
    '-p',
    '127.0.0.1::3001',
    '--mount',
    `type=volume,source=${volume},target=/data`,
    image,
  );
  baseUrl = `http://${docker('port', container, '3001/tcp')}`;
  for (let attempt = 0; attempt < 120; attempt++) {
    const health = docker('inspect', '--format', '{{.State.Health.Status}}', container);
    if (health === 'healthy') return;
    if (health === 'unhealthy') throw new Error('Container health check failed');
    await pause();
  }
  throw new Error('Container did not become healthy within 60 seconds');
}

try {
  docker('volume', 'create', volume);
  await start();
  assert.equal(
    docker('exec', container, 'id', '-u'),
    '1000',
    'Runtime must use the non-root node user',
  );
  assert.equal(
    docker(
      'exec',
      container,
      'node',
      '-e',
      "try{require.resolve('vite');process.exit(1)}catch{process.exit(0)}",
    ),
    '',
  );
  const page = await fetch(baseUrl);
  assert.equal(page.status, 200);
  assert.match(await page.text(), /<div id="root"><\/div>/);
  const created = await fetch(`${baseUrl}/api/todos`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ title: 'Isolated container persistence test' }),
  });
  assert.equal(created.status, 201);
  const task = await created.json();
  docker('rm', '-f', container);
  await start();
  const recovered = await fetch(`${baseUrl}/api/todos/${task.id}`);
  assert.equal(recovered.status, 200);
  assert.deepEqual(await recovered.json(), task);
  console.log(
    'PASS: healthy API, production SPA, non-root runtime, production dependencies, and persistence across container replacement',
  );
} catch (error) {
  try {
    console.error(docker('logs', container));
  } catch {}
  throw error;
} finally {
  // Names are unique to this invocation; never touch the Compose/user volume.
  try {
    docker('rm', '-f', container);
  } catch {}
  try {
    docker('volume', 'rm', volume);
  } catch {}
}
