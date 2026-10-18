// Exercise the actual TypeScript API adapter against an isolated real Python server.
// This is a Node transport test, not a browser or visual test.
import assert from 'node:assert/strict';
import { mkdtemp, rm, realpath } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join, dirname, basename } from 'node:path';
import { pathToFileURL, fileURLToPath } from 'node:url';

const base = process.argv[2];
const nativeFetch = globalThis.fetch;
const scratchRoot = await realpath(tmpdir());
const scratch = await mkdtemp(join(scratchRoot, 'janamen-client-'));
const esbuild = await import(new URL('../frontend/node_modules/esbuild/lib/main.js', import.meta.url));
let activeSession;
globalThis.fetch = async (url, options = {}) => {
  assert.equal(options.credentials, 'include', 'Every frontend API call must include credentials');
  const headers = new Headers(options.headers);
  if (activeSession.cookie) headers.set('Cookie', activeSession.cookie);
  const response = await nativeFetch(url, { ...options, headers });
  const cookie = response.headers.get('set-cookie');
  if (cookie) activeSession.cookie = cookie.split(';')[0];
  return response;
};

async function using(session, action) {
  activeSession = session;
  return action(session.api);
}

try {
  const bundle = join(scratch, 'api.mjs');
  await esbuild.build({
    entryPoints: [fileURLToPath(new URL('../frontend/src/api/endpoints.ts', import.meta.url))],
    bundle: true, outfile: bundle, platform: 'node', format: 'esm',
    define: { 'import.meta.env.VITE_API_URL': JSON.stringify(base), 'import.meta.env.DEV': 'false' },
  });
  const employeeModule = await import(pathToFileURL(bundle).href + '?employee');
  const managerModule = await import(pathToFileURL(bundle).href + '?manager');
  const hrModule = await import(pathToFileURL(bundle).href + '?hr');
  const employee = { api: employeeModule.api, branches: employeeModule.branchApi, integrations: employeeModule.integrationApi, cookie: '' };
  const manager = { api: managerModule.api, branches: managerModule.branchApi, integrations: managerModule.integrationApi, cookie: '' };
  const hr = { api: hrModule.api, branches: hrModule.branchApi, integrations: hrModule.integrationApi, cookie: '' };
  const login = (session, account) => using(session, api => api.login(account + '@demo.local', 'Demo2026!'));
  assert.equal((await login(employee, 'employee')).user.role, 'employee');
  assert.equal((await login(manager, 'manager')).user.role, 'manager');
  assert.equal((await login(hr, 'hr')).user.role, 'hr');
  assert.equal((await using(employee, api => api.me())).user.id, 1);
  assert.equal((await using(employee, api => api.dashboard())).profile.id, 1);
  await assert.rejects(using(employee, api => api.team()), error => error.status === 403);
  assert.deepEqual((await using(manager, api => api.team())).items.map(u => u.id), [1]);
  await assert.rejects(using(manager, api => api.request(3)), error => error.status === 404);
  const bid = '70000001088185194';
  await using(hr, () => hr.branches.assign(1, bid));
  await using(hr, () => hr.branches.assign(4, bid));
  const from = new Date().toISOString().slice(0, 10);
  assert.equal((await using(employee, () => employee.branches.list(from, from))).items.length, 13);
  assert.deepEqual((await using(employee, () => employee.branches.detail(bid, from, from))).members.map(p => p.id), [1]);
  assert.equal((await using(manager, () => manager.branches.employee(bid, 1))).profile.id, 1);
  await assert.rejects(using(employee, () => employee.branches.employee(bid, 4)), error => error.status === 404);
  await assert.rejects(using(manager, () => manager.branches.assign(1, null)), error => error.status === 403);
  const integrations = await using(hr, () => hr.integrations.list());
  assert.equal(integrations.mode, 'mock');
  assert.deepEqual(integrations.items.map(i => i.id), ['1c-zup', 'documentolog']);
  const preview = await using(hr, () => hr.integrations.preview('documentolog'));
  assert.equal(preview.mode, 'mock');
  assert.equal(preview.persisted, false);
  assert.equal(preview.external_calls, false);
  await assert.rejects(using(employee, () => employee.integrations.list()), error => error.status === 403);
  await assert.rejects(using(manager, () => manager.integrations.preview('1c-zup')), error => error.status === 403);

  const ownAnswer = await using(employee, api => api.ask('Какой у меня остаток отпуска?'));
  assert.equal(ownAnswer.found, true);
  const ownSource = await using(employee, api => api.sourceDoc(ownAnswer.sources[0].url));
  assert.match(ownSource.content, /24/);
  const answer = await using(employee, api => api.ask('Как оформить отпуск?'));
  assert.equal(answer.found, true);
  assert.equal((await using(employee, api => api.sourceDoc(answer.sources[0].url))).content, answer.answer);
  assert.equal((await using(employee, api => api.ask('Когда выплачивается зарплата?'))).found, false);

  const start = new Date(Date.now() + 60 * 86400000).toISOString().slice(0, 10);
  const end = new Date(Date.now() + 62 * 86400000).toISOString().slice(0, 10);
  const request = await using(employee, api => api.createRequest({ type: 'vacation', start_date: start, end_date: end, comment: 'Проверка реального frontend API клиента' }));
  assert.equal(request.status, 'pending');
  assert.equal((await using(manager, api => api.requests('team'))).items.some(r => r.id === request.id), true);
  await using(manager, api => api.decide(request.id, 'approved', 'Проверено'));
  const updated = await using(employee, api => api.request(request.id));
  assert.equal(updated.status, 'approved');
  assert.equal(updated.history.length, 2);
  assert.equal((await using(employee, api => api.profile())).vacation_balance, 21);
  assert.equal((await using(employee, api => api.sourceDoc('/api/profile'))).content.includes('21'), true);
  const notes = await using(employee, api => api.notifications());
  const note = notes.items.find(n => n.entity_id === request.id && n.type === 'request_status');
  assert.ok(note);
  assert.equal((await using(employee, api => api.markRead(note.id))).is_read, true);
  await using(employee, api => api.markAllRead());
  assert.equal((await using(employee, api => api.notifications())).unread_count, 0);

  const course = await using(employee, api => api.course(1));
  for (const lesson of course.lessons) await using(employee, api => api.completeLesson(1, lesson.id));
  assert.equal((await using(employee, api => api.submitQuiz(1, 0))).passed, false);
  assert.equal((await using(employee, api => api.submitQuiz(1, 1))).course.progress, 100);
  assert.equal((await using(hr, api => api.adminCourses())).items.length, 2);
  await using(hr, api => api.assignCourse(2, 2));
  assert.equal((await using(manager, api => api.courses())).items.some(c => c.id === 2), true);
  await using(employee, api => api.logout());
  await assert.rejects(using(employee, api => api.me()), error => error.status === 401);
  console.log('Frontend API integration: OK (three roles, vacation, history, notifications, training, sources and logout)');
} finally {
  globalThis.fetch = nativeFetch;
  const cleanupTarget = await realpath(scratch);
  assert.equal(dirname(cleanupTarget), scratchRoot, 'Cleanup must remain in the selected temporary directory');
  assert.ok(basename(cleanupTarget).startsWith('janamen-client-'));
  await rm(scratch, { recursive: true, force: true });
}
