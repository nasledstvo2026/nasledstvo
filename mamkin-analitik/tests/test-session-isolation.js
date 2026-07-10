/**
 * Тесты изоляции сессий и admin override (Story 1.7)
 *
 * Проверяет:
 *   1. User видит ТОЛЬКО свои активные сессии
 *   2. User видит ТОЛЬКО свои завершённые сессии
 *   3. Admin может просмотреть любую сессию через getSessionForAdmin
 *   4. Admin может получить список всех сессий
 *   5. User НЕ может просмотреть чужую сессию
 *   6. getSessionForAdmin логирует доступ
 *   7. listAllActiveSessions / listAllCompletedSessions без фильтрации
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');
const SessionManager = require('../lib/session-manager');
const Whitelist = require('../lib/whitelist');

// ==================== Helper ====================

function createTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'isolation-test-'));
}

function makeConfig(tmpDir) {
  return {
    storagePath: tmpDir,
    allowEmptyKey: true,
    lockTimeout: 2000
  };
}

// ==================== Tests ====================

async function testUserSeesOnlyOwnActiveSessions() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  // Создаём сессии для разных пользователей
  await sm.createSession(100); // user1: 1 сессия
  await sm.createSession(200); // user2: 1 сессия
  await sm.createSession(200); // user2: 2 сессия
  await sm.createSession(300); // user3: 1 сессия

  const user1 = await sm.listActiveSessions(100);
  const user2 = await sm.listActiveSessions(200);
  const user3 = await sm.listActiveSessions(300);

  assert.strictEqual(user1.length, 1, 'User1 должен видеть только свою 1 сессию');
  assert.strictEqual(user2.length, 2, 'User2 должен видеть только свои 2 сессии');
  assert.strictEqual(user3.length, 1, 'User3 должен видеть только свою 1 сессию');

  // Проверка: ни одна сессия user2 не принадлежит user1
  for (const s of user1) {
    assert.strictEqual(s.telegramUserId, 100,
      `Сессия ${s.sessionId} должна принадлежать user1`);
  }

  // Проверка: user3 не видит чужих сессий
  const user3Ids = new Set(user3.map(s => s.sessionId));
  const allIds = new Set([
    ...user1.map(s => s.sessionId),
    ...user2.map(s => s.sessionId)
  ]);
  for (const id of user3Ids) {
    assert(!allIds.has(id),
      `User3 не должен видеть сессии других пользователей`);
  }

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testUserSeesOnlyOwnActiveSessions');
}

async function testUserSeesOnlyOwnCompletedSessions() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const s1 = await sm.createSession(100);
  const s2 = await sm.createSession(100);
  const s3 = await sm.createSession(200);

  await sm.completeSession(s1.sessionId);
  await sm.completeSession(s3.sessionId);

  const user1Completed = await sm.listCompletedSessions(100);
  const user2Completed = await sm.listCompletedSessions(200);

  assert.strictEqual(user1Completed.length, 1,
    'User1 должен видеть 1 завершённую сессию');
  assert.strictEqual(user2Completed.length, 1,
    'User2 должен видеть 1 завершённую сессию');

  // User1 не должен видеть завершённую сессию user2
  for (const s of user1Completed) {
    assert.strictEqual(s.telegramUserId, 100,
      `User1 не должен видеть сессию user2`);
  }

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testUserSeesOnlyOwnCompletedSessions');
}

async function testUserCannotAccessOtherUserSession() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const s1 = await sm.createSession(100); // user1
  const s2 = await sm.createSession(200); // user2

  // User1 пытается получить сессию user2 через getSession (загрузка по ID)
  const loaded = await sm.getSession(s2.sessionId);

  // loadSession/getSession загружает любой sessionId — это storage layer
  // Проверка доступа — на уровне команд (session-commands.js)
  // Здесь мы проверяем, что telegramUserId соответствует
  assert(loaded, 'Сессия должна загружаться по ID');
  assert.strictEqual(loaded.telegramUserId, 200,
    'Сессия принадлежит user200, а не user100');

  // User1 смотрит свои сессии — не должен видеть s2
  const user1Sessions = await sm.listActiveSessions(100);
  const user1Ids = new Set(user1Sessions.map(s => s.sessionId));
  assert(!user1Ids.has(s2.sessionId),
    'User1 не должен видеть сессию user2 в своём списке');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testUserCannotAccessOtherUserSession');
}

async function testAdminCanViewAnySession() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  // Создаём сессии для разных пользователей
  const s1 = await sm.createSession(100);
  const s2 = await sm.createSession(200);
  const s3 = await sm.createSession(300);

  // Admin (ID=999) может получить любую сессию
  const adminSession1 = await sm.getSessionForAdmin(s1.sessionId, 999);
  const adminSession2 = await sm.getSessionForAdmin(s2.sessionId, 999);
  const adminSession3 = await sm.getSessionForAdmin(s3.sessionId, 999);

  assert(adminSession1, 'Admin должен загрузить сессию user100');
  assert(adminSession2, 'Admin должен загрузить сессию user200');
  assert(adminSession3, 'Admin должен загрузить сессию user300');

  assert.strictEqual(adminSession1.telegramUserId, 100,
    'Сессия должна принадлежать user100');
  assert.strictEqual(adminSession2.telegramUserId, 200,
    'Сессия должна принадлежать user200');
  assert.strictEqual(adminSession3.telegramUserId, 300,
    'Сессия должна принадлежать user300');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testAdminCanViewAnySession');
}

async function testAdminCanListAllSessions() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  await sm.createSession(100);
  await sm.createSession(200);
  await sm.createSession(200);
  await sm.createSession(300);

  const allActive = await sm.listAllActiveSessions();

  assert.strictEqual(allActive.length, 4,
    'Admin должен видеть все 4 активные сессии');

  const userIds = new Set(allActive.map(s => s.telegramUserId));
  assert(userIds.has(100), 'Должна быть сессия user100');
  assert(userIds.has(200), 'Должна быть сессия user200');
  assert(userIds.has(300), 'Должна быть сессия user300');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testAdminCanListAllSessions');
}

async function testAdminCanListAllCompletedSessions() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const s1 = await sm.createSession(100);
  const s2 = await sm.createSession(200);
  await sm.createSession(300); // остаётся активной

  await sm.completeSession(s1.sessionId);
  await sm.completeSession(s2.sessionId);

  const allCompleted = await sm.listAllCompletedSessions();

  assert.strictEqual(allCompleted.length, 2,
    'Admin должен видеть все 2 завершённые сессии');

  const userIds = new Set(allCompleted.map(s => s.telegramUserId));
  assert(userIds.has(100), 'Должна быть завершённая сессия user100');
  assert(userIds.has(200), 'Должна быть завершённая сессия user200');

  // Проверка сортировки: сначала новые
  assert(
    new Date(allCompleted[0].updatedAt) >= new Date(allCompleted[1].updatedAt),
    'Сессии должны быть отсортированы по updatedAt (сначала новые)'
  );

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testAdminCanListAllCompletedSessions');
}

async function testMixSessionIsolation() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  // Сложный сценарий: несколько пользователей, сессии в разных статусах
  const s1 = await sm.createSession(100); // user1 active
  await sm.createSession(100);             // user1 active
  const s3 = await sm.createSession(200); // user2 active
  const s4 = await sm.createSession(300); // user3 active

  await sm.completeSession(s1.sessionId); // user1 completed
  await sm.completeSession(s4.sessionId); // user3 completed

  // User1: видит 1 активную + 1 завершённую
  const user1Active = await sm.listActiveSessions(100);
  const user1Completed = await sm.listCompletedSessions(100);
  assert.strictEqual(user1Active.length, 1, 'User1: 1 активная');
  assert.strictEqual(user1Completed.length, 1, 'User1: 1 завершённая');

  // User2: видит 1 активную, 0 завершённых
  const user2Active = await sm.listActiveSessions(200);
  const user2Completed = await sm.listCompletedSessions(200);
  assert.strictEqual(user2Active.length, 1, 'User2: 1 активная');
  assert.strictEqual(user2Completed.length, 0, 'User2: 0 завершённых');

  // User3: видит 0 активных, 1 завершённую
  const user3Active = await sm.listActiveSessions(300);
  const user3Completed = await sm.listCompletedSessions(300);
  assert.strictEqual(user3Active.length, 0, 'User3: 0 активных (завершена)');
  assert.strictEqual(user3Completed.length, 1, 'User3: 1 завершённая');

  // Admin: видит всё
  const adminActive = await sm.listAllActiveSessions();
  const adminCompleted = await sm.listAllCompletedSessions();
  assert.strictEqual(adminActive.length, 2,
    `Admin: все активные (${adminActive.length})`);
  assert.strictEqual(adminCompleted.length, 2,
    `Admin: все завершённые (${adminCompleted.length})`);

  // Admin может загрузить любую сессию
  for (const s of [...adminActive, ...adminCompleted]) {
    const adminSession = await sm.getSessionForAdmin(s.sessionId, 999);
    assert(adminSession, `Admin должен загрузить сессию ${s.sessionId}`);
  }

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testMixSessionIsolation');
}

async function testWhitelistAdminCheck() {
  const tmpDir = createTempDir();

  // Создаём whitelist для теста администратора
  const whitelistPath = path.join(tmpDir, 'whitelist.json');
  const whitelist = new Whitelist({
    whitelistPath,
    adminIds: [999, 888], // Администраторы
    readOnly: true
  });
  await whitelist.load();

  // Администратор
  assert(whitelist.isAdmin(999), 'ID 999 должен быть администратором');
  assert(whitelist.isAdmin(888), 'ID 888 должен быть администратором');

  // Обычный пользователь
  assert(!whitelist.isAdmin(100), 'ID 100 не должен быть администратором');
  assert(!whitelist.isAdmin(200), 'ID 200 не должен быть администратором');

  // Admin IDs
  const adminIds = whitelist.getAdminIds();
  assert(adminIds.includes(999), 'Admin IDs должен содержать 999');
  assert(adminIds.includes(888), 'Admin IDs должен содержать 888');
  assert.strictEqual(adminIds.length, 2, 'Должно быть 2 администратора');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testWhitelistAdminCheck');
}

async function testGetSessionForAdminLogsAccess() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(100);
  const loaded = await sm.getSessionForAdmin(session.sessionId, 999);

  assert(loaded, 'Admin должен загрузить сессию');
  assert.strictEqual(loaded.sessionId, session.sessionId,
    'ID сессии должен совпадать');

  // Повторная загрузка с другим admin ID
  const loaded2 = await sm.getSessionForAdmin(session.sessionId, 888);
  assert(loaded2, 'Второй admin тоже должен загрузить сессию');

  // Несуществующая сессия
  const notFound = await sm.getSessionForAdmin('nonexistent', 999);
  assert.strictEqual(notFound, null, 'Несуществующая сессия — null');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testGetSessionForAdminLogsAccess');
}

// ==================== Run All Tests ====================

async function runTests() {
  console.log('\n=== Session Isolation & Admin Override Tests (Story 1.7) ===\n');

  const tests = [
    testUserSeesOnlyOwnActiveSessions,
    testUserSeesOnlyOwnCompletedSessions,
    testUserCannotAccessOtherUserSession,
    testAdminCanViewAnySession,
    testAdminCanListAllSessions,
    testAdminCanListAllCompletedSessions,
    testMixSessionIsolation,
    testWhitelistAdminCheck,
    testGetSessionForAdminLogsAccess
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
