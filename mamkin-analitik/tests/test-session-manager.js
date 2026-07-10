/**
 * Тесты Session Manager (Story 1.2)
 *
 * Mock-based тесты с временной директорией и allowEmptyKey для crypto.
 * Тестирует: createSession, loadSession, updateSession, completeSession,
 *            listActiveSessions, session locking, транзакционную запись.
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');
const SessionManager = require('../lib/session-manager');

// ==================== Test Setup ====================

/** Создаёт временную директорию для тестов */
function createTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'session-test-'));
}

/** Генерирует конфиг для тестового SessionManager */
function makeConfig(tmpDir) {
  return {
    storagePath: tmpDir,
    allowEmptyKey: true, // crypto.js: dev/test mode без реального ключа
    lockTimeout: 2000
  };
}

// ==================== Tests ====================

async function testCreateSession() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(12345, { username: 'test_user' });

  assert(session, 'Session object should be created');
  assert(session.sessionId, 'Session should have sessionId');
  assert.strictEqual(session.telegramUserId, 12345, 'telegramUserId should match');
  assert.strictEqual(session.username, 'test_user', 'username should match');
  assert.strictEqual(session.status, 'in_progress', 'Status should be in_progress');
  assert(session.createdAt, 'Should have createdAt');
  assert(session.updatedAt, 'Should have updatedAt');
  assert.deepStrictEqual(session.template, { block: 1, subsection: '1.1', depth: 'L1' },
    'Template should start at block 1');
  assert.deepStrictEqual(session.answers, {}, 'Answers should be empty');
  assert.deepStrictEqual(session.risks, [], 'Risks should be empty');
  assert.strictEqual(session.documentReady, false, 'documentReady should be false');

  // Проверяем, что файл создался
  const filePath = path.join(tmpDir, 'active', `session_${session.sessionId}.json`);
  assert(fs.existsSync(filePath), 'Session file should exist on disk');

  // Очистка
  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testCreateSession');
}

async function testLoadSession() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  // Создаём и загружаем
  const created = await sm.createSession(12345);
  const loaded = await sm.loadSession(created.sessionId);

  assert(loaded, 'Should load session');
  assert.strictEqual(loaded.sessionId, created.sessionId, 'sessionId should match');
  assert.strictEqual(loaded.telegramUserId, 12345, 'telegramUserId should match');

  // Загрузка несуществующей сессии
  const notFound = await sm.loadSession('nonexistent');
  assert.strictEqual(notFound, null, 'Should return null for nonexistent session');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testLoadSession');
}

async function testUpdateSession() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(67890);

  // Обновляем ответы
  const updated = await sm.updateSession(session.sessionId, {
    answers: {
      '1.1': {
        L1: 'Тестовый ответ на вопрос 1.1',
        L2: null,
        L3: null,
        depthReached: 'L1'
      }
    },
    template: { block: 1, subsection: '1.2', depth: 'L1' }
  });

  assert.strictEqual(updated.answers['1.1'].L1, 'Тестовый ответ на вопрос 1.1',
    'Answer should be saved');
  assert.strictEqual(updated.template.subsection, '1.2',
    'Template progress should be updated');
  assert(updated.updatedAt > session.createdAt,
    'updatedAt should be greater than createdAt');

  // Загружаем заново и проверяем персистентность
  const reloaded = await sm.loadSession(session.sessionId);
  assert.strictEqual(reloaded.answers['1.1'].L1, 'Тестовый ответ на вопрос 1.1',
    'Answer should persist on disk');
  assert.strictEqual(reloaded.template.subsection, '1.2',
    'Template progress should persist on disk');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testUpdateSession');
}

async function testCompleteSession() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(11111);
  const sessionId = session.sessionId;

  // Завершаем сессию
  const completed = await sm.completeSession(sessionId);

  assert.strictEqual(completed.status, 'completed', 'Status should be completed');

  // Файл должен быть в completed/, а не в active/
  const activePath = path.join(tmpDir, 'active', `session_${sessionId}.json`);
  const completedPath = path.join(tmpDir, 'completed', `session_${sessionId}.json`);

  assert(!fs.existsSync(activePath), 'File should NOT be in active/');
  assert(fs.existsSync(completedPath), 'File should be in completed/');

  // Загружаем из completed/
  const loaded = await sm.loadSession(sessionId);
  assert.strictEqual(loaded.status, 'completed', 'Loaded session should be completed');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testCompleteSession');
}

async function testListActiveSessions() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  // Создаём 3 сессии для user1 и 2 для user2
  await sm.createSession(100, { username: 'user1' });
  await sm.createSession(100, { username: 'user1' });
  await sm.createSession(100, { username: 'user1' });
  await sm.createSession(200, { username: 'user2' });
  await sm.createSession(200, { username: 'user2' });

  const user1Sessions = await sm.listActiveSessions(100);
  const user2Sessions = await sm.listActiveSessions(200);
  const user3Sessions = await sm.listActiveSessions(300);

  assert.strictEqual(user1Sessions.length, 3, 'User1 should have 3 active sessions');
  assert.strictEqual(user2Sessions.length, 2, 'User2 should have 2 active sessions');
  assert.strictEqual(user3Sessions.length, 0, 'User3 should have 0 active sessions');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testListActiveSessions');
}

async function testGetActiveSessionByUser() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  // Создаём две сессии, обновляем первую — она должна стать последней по updatedAt
  const s1 = await sm.createSession(100);
  const s2 = await sm.createSession(100);

  // Обновляем s1 — её updatedAt станет позже
  await sm.updateSession(s1.sessionId, { template: { block: 2 } });

  const active = await sm.getActiveSessionByUser(100);
  assert.strictEqual(active.sessionId, s1.sessionId,
    'Should return the most recently updated session');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testGetActiveSessionByUser');
}

async function testListCompletedSessions() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const s1 = await sm.createSession(100);
  await sm.createSession(100);
  await sm.completeSession(s1.sessionId);

  const user1Active = await sm.listActiveSessions(100);
  const user1Completed = await sm.listCompletedSessions(100);

  assert.strictEqual(user1Active.length, 1, 'Should have 1 active session remaining');
  assert.strictEqual(user1Completed.length, 1, 'Should have 1 completed session');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testListCompletedSessions');
}

async function testGetUserSessions() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const s1 = await sm.createSession(100);
  await sm.createSession(100);
  await sm.completeSession(s1.sessionId);

  const all = await sm.getUserSessions(100);
  assert.strictEqual(all.length, 2, 'Should return all sessions (active + completed)');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testGetUserSessions');
}

async function testConcurrentWrites() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(55555);

  // Симуляция конкурентных записей
  const promises = [];
  for (let i = 0; i < 10; i++) {
    promises.push(
      sm.updateSession(session.sessionId, {
        answers: {
          [`test.${i}`]: { L1: `Answer ${i}`, depthReached: 'L1' }
        }
      })
    );
  }

  // Все должны выполниться без ошибок
  const results = await Promise.all(promises);

  assert.strictEqual(results.length, 10, 'All concurrent writes should complete');

  // Финальная версия должна содержать последнюю запись
  const final = await sm.loadSession(session.sessionId);
  assert(Object.keys(final.answers).length >= 1,
    'Answers should have been written');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testConcurrentWrites');
}

async function testSessionFileEncryption() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(99999);
  const filePath = path.join(tmpDir, 'active', `session_${session.sessionId}.json`);

  // Читаем файл напрямую — должны увидеть шифрованные данные
  const rawData = fs.readFileSync(filePath, 'utf8');

  // С allowEmptyKey данные сохраняются как plain:...
  assert(rawData.startsWith('plain:'),
    'Data should be prefixed with plain: in dev mode');
  assert(rawData.includes(session.sessionId),
    'Session ID should be present in the plaintext portion');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testSessionFileEncryption');
}

async function testTransactionalWrite() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  await sm.createSession(77777);

  // Проверяем, что нет временных файлов
  const tmpFiles = fs.readdirSync(path.join(tmpDir, 'active'))
    .filter(f => f.includes('.tmp'));
  assert.strictEqual(tmpFiles.length, 0, 'No temp files should remain after write');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testTransactionalWrite');
}

async function testRecoverSessions() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  await sm.createSession(12345);
  await sm.createSession(12345);
  await sm.createSession(67890);

  // Симуляция перезапуска: новый инстанс
  const sm2 = new SessionManager(makeConfig(tmpDir));
  const recovered = await sm2.recoverSessions();

  assert.strictEqual(recovered, 3, 'All 3 sessions should be recovered');

  // Проверяем статус
  const sessions = await sm2.listActiveSessions(12345);
  for (const s of sessions) {
    assert.strictEqual(s.status, 'recovered',
      `Session ${s.sessionId} should be marked as recovered`);
  }

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testRecoverSessions');
}

async function testGetSessionAlias() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const created = await sm.createSession(44444);
  const byGet = await sm.getSession(created.sessionId);
  const byLoad = await sm.loadSession(created.sessionId);

  assert(byGet, 'getSession should return session');
  assert.strictEqual(byGet.sessionId, byLoad.sessionId,
    'getSession and loadSession should return same data');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testGetSessionAlias');
}

async function testSaveSessionAlias() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(33333);
  session.answers = {
    '2.1': { L1: 'Ответ из saveSession', depthReached: 'L1' }
  };

  const saved = await sm.saveSession(session);
  assert.strictEqual(saved.sessionId, session.sessionId, 'saveSession should work');

  const loaded = await sm.loadSession(session.sessionId);
  assert.strictEqual(loaded.answers['2.1'].L1, 'Ответ из saveSession',
    'saveSession should persist data');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testSaveSessionAlias');
}

async function testSessionIsolation() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  await sm.createSession(1000);
  await sm.createSession(1000);
  await sm.createSession(2000);

  const user1000 = await sm.listActiveSessions(1000);
  const user2000 = await sm.listActiveSessions(2000);

  assert.strictEqual(user1000.length, 2, 'User 1000 should see only their 2 sessions');
  assert.strictEqual(user2000.length, 1, 'User 2000 should see only their 1 session');

  // Проверяем, что у user1000 нет сессий user2000
  for (const s of user1000) {
    assert.strictEqual(s.telegramUserId, 1000,
      'User 1000 should only get their own sessions');
  }

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testSessionIsolation');
}

async function testGetSessionReturnsNull() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const result = await sm.getSession('nonexistent-session-id');
  assert.strictEqual(result, null, 'getSession should return null for missing session');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testGetSessionReturnsNull');
}

// ==================== Run All Tests ====================

async function runTests() {
  console.log('\n=== Session Manager Tests (Story 1.2) ===\n');

  const tests = [
    testCreateSession,
    testLoadSession,
    testUpdateSession,
    testCompleteSession,
    testListActiveSessions,
    testGetActiveSessionByUser,
    testListCompletedSessions,
    testGetUserSessions,
    testConcurrentWrites,
    testSessionFileEncryption,
    testTransactionalWrite,
    testRecoverSessions,
    testGetSessionAlias,
    testSaveSessionAlias,
    testSessionIsolation,
    testGetSessionReturnsNull,
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      await test();
      passed++;
    } catch (err) {
      console.error(`✗ ${test.name} FAILED:`, err.message);
      console.error(err.stack);
      failed++;
    }
  }

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
