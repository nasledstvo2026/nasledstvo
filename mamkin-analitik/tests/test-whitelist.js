/**
 * Whitelist — Тесты
 *
 * Story 1.4 — Telegram Bot Connector + Whitelist
 *
 * Покрытие:
 *   1. Загрузка пустого whitelist
 *   2. Добавление пользователя
 *   3. isWhitelisted: существующий / несуществующий
 *   4. isAdmin: администратор / не администратор
 *   5. getAdminIds()
 *   6. getUser(): существующий / несуществующий
 *   7. getAllUsers()
 *   8. Дубликат пользователя (ошибка)
 *   9. Удаление пользователя
 *   10. Удаление несуществующего (false)
 *   11. Невалидный telegramId (ошибка)
 *   12. Персистентность: reload из файла
 *   13. ReadOnly режим
 *   14. Валидация испорченного файла
 *   15. Пустой массив
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');

const Whitelist = require('../lib/whitelist');

// ==================== Helper ====================

let testCount = 0;
let passedCount = 0;

function assertEqual(actual, expected, label) {
  testCount++;
  try {
    assert.deepStrictEqual(actual, expected);
    passedCount++;
    console.log(`  ✓ ${label}`);
  } catch (e) {
    console.log(`  ✗ ${label}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
    if (e.stack) console.error(e.stack.slice(0, 500));
  }
}

function assertMatch(actual, pattern, label) {
  testCount++;
  try {
    assert.ok(pattern.test(actual), `${label}: expected ${JSON.stringify(actual)} to match ${pattern}`);
    passedCount++;
    console.log(`  ✓ ${label}`);
  } catch (e) {
    console.log(`  ✗ ${label}: ${e.message}`);
  }
}

async function withTempDir(run) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'wl-uitest-'));
  try {
    await run(tmpDir);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

// ==================== Tests ====================

(async function() {
  console.log('=== Whitelist Tests ===\n');

  // === Test 1: Load empty whitelist ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: false });
    await wl.load();

    assertEqual(wl.getCount(), 0, '1.1 Пустой whitelist, count = 0');
    assertEqual(wl.getAllUsers(), [], '1.2 Пустой whitelist, все пользователи = []');
    assertEqual(wl.isWhitelisted(123), false, '1.3 Пустой whitelist, isWhitelisted = false');
  });

  // === Test 2: Add user ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: false });
    await wl.load();

    const entry = await wl.addUser(12345, 1, 'ivanov');
    assertEqual(entry.telegramId, 12345, '2.1 addUser возвращает telegramId');
    assertEqual(entry.username, 'ivanov', '2.2 addUser возвращает username');
    assertEqual(entry.addedBy, 1, '2.3 addUser возвращает addedBy');
    assert.ok(entry.addedAt, '2.4 addUser возвращает addedAt');
    assertEqual(wl.getCount(), 1, '2.5 После addUser count = 1');
    assertEqual(wl.isWhitelisted(12345), true, '2.6 isWhitelisted(12345) = true');
    assertEqual(wl.isWhitelisted(99999), false, '2.7 isWhitelisted(99999) = false');
  });

  // === Test 3: Add user without username ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: false });
    await wl.load();

    const entry = await wl.addUser(12345, 1);
    assertEqual(entry.username, null, '3.1 addUser без username = null');
  });

  // === Test 4: Admin checks ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1, 100, 200], readOnly: true });
    await wl.load();

    assertEqual(wl.isAdmin(1), true, '4.1 isAdmin(1) = true');
    assertEqual(wl.isAdmin(100), true, '4.2 isAdmin(100) = true');
    assertEqual(wl.isAdmin(200), true, '4.3 isAdmin(200) = true');
    assertEqual(wl.isAdmin(300), false, '4.4 isAdmin(300) = false');

    const adminIds = wl.getAdminIds();
    assertEqual(adminIds.length, 3, '4.5 getAdminIds length = 3');
    assertEqual(adminIds, [1, 100, 200], '4.6 getAdminIds = [1, 100, 200]');
  });

  // === Test 5: getUser ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: false });
    await wl.load();

    await wl.addUser(12345, 1, 'ivanov');
    await wl.addUser(54321, 1, 'petrov');

    const user1 = wl.getUser(12345);
    assertEqual(user1.telegramId, 12345, '5.1 getUser(12345).telegramId = 12345');
    assertEqual(user1.username, 'ivanov', '5.2 getUser(12345).username = "ivanov"');

    const user2 = wl.getUser(99999);
    assertEqual(user2, null, '5.3 getUser(99999) = null');

    const allUsers = wl.getAllUsers();
    assertEqual(allUsers.length, 2, '5.4 getAllUsers length = 2');
  });

  // === Test 6: Duplicate user (error) ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: false });
    await wl.load();

    await wl.addUser(12345, 1);
    try {
      await wl.addUser(12345, 1);
      assertEqual('no error', 'expected error', '6.1 Дубликат: должен быть выброшен Error');
    } catch (e) {
      assertMatch(e.message, /уже в белом списке/, '6.1 Дубликат: сообщение об ошибке');
    }
  });

  // === Test 7: Remove user ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: false });
    await wl.load();

    await wl.addUser(12345, 1);
    assertEqual(wl.getCount(), 1, '7.1 До удаления count = 1');

    const removed = await wl.removeUser(12345);
    assertEqual(removed, true, '7.2 removeUser(12345) = true');
    assertEqual(wl.getCount(), 0, '7.3 После удаления count = 0');
    assertEqual(wl.isWhitelisted(12345), false, '7.4 После удаления isWhitelisted = false');

    // Удаление несуществующего
    const removed2 = await wl.removeUser(99999);
    assertEqual(removed2, false, '7.5 removeUser(99999) = false');
  });

  // === Test 8: Invalid telegramId ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: false });
    await wl.load();

    // Negative ID
    try {
      await wl.addUser(-1, 1);
      assertEqual('no error', 'expected error', '8.1 Отрицательный ID: должен быть Error');
    } catch (e) {
      assertMatch(e.message, /невалидный telegramId/, '8.1 Отрицательный ID: валидация');
    }

    // Non-integer
    try {
      await wl.addUser(1.5, 1);
      assertEqual('no error', 'expected error', '8.2 Дробный ID: должен быть Error');
    } catch (e) {
      assertMatch(e.message, /невалидный telegramId/, '8.2 Дробный ID: валидация');
    }

    // Zero
    try {
      await wl.addUser(0, 1);
      assertEqual('no error', 'expected error', '8.3 Нулевой ID: должен быть Error');
    } catch (e) {
      assertMatch(e.message, /невалидный telegramId/, '8.3 Нулевой ID: валидация');
    }
  });

  // === Test 9: Persistence (file reload) ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');

    // Первая загрузка — добавляем пользователей
    const wl1 = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: false });
    await wl1.load();
    await wl1.addUser(12345, 1, 'ivanov');
    await wl1.addUser(54321, 1, 'petrov');

    // Вторая загрузка (новый экземпляр)
    const wl2 = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl2.load();
    assertEqual(wl2.getCount(), 2, '9.1 Персистентность: count = 2 после перезагрузки');
    assertEqual(wl2.isWhitelisted(12345), true, '9.2 Персистентность: isWhitelisted(12345)');
    assertEqual(wl2.isWhitelisted(54321), true, '9.3 Персистентность: isWhitelisted(54321)');

    const user = wl2.getUser(12345);
    assertEqual(user.username, 'ivanov', '9.4 Персистентность: username сохранён');
    assertEqual(user.addedBy, 1, '9.5 Персистентность: addedBy сохранён');
  });

  // === Test 10: ReadOnly mode ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');

    // Создаём файл явно
    const initialData = [
      { telegramId: 12345, username: 'readonly_test', addedBy: 1, addedAt: '2026-01-01T00:00:00.000Z' }
    ];
    fs.writeFileSync(wlPath, JSON.stringify(initialData), 'utf-8');

    // ReadOnly загрузка
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    assertEqual(wl.getCount(), 1, '10.1 ReadOnly: count = 1');
    assertEqual(wl.isWhitelisted(12345), true, '10.2 ReadOnly: isWhitelisted(12345)');

    // После addUser readOnly не сохраняет (но будет ошибка при _save)
    // На readOnly _save не вызывается нормально
  });

  // === Test 11: Corrupted whitelist file ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    fs.writeFileSync(wlPath, '{invalid json}', 'utf-8');

    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    try {
      await wl.load();
      assertEqual('no error', 'expected error', '11.1 Испорченный файл: должен быть Error');
    } catch (e) {
      assertMatch(e.message, /ошибка загрузки/, '11.1 Испорченный файл: сообщение об ошибке');
    }
  });

  // === Test 12: Empty array in file ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    fs.writeFileSync(wlPath, '[]', 'utf-8');

    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    assertEqual(wl.getCount(), 0, '12.1 Пустой массив: count = 0');
  });

  // === Test 13: Environment variable admin IDs ===
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    process.env.TELEGRAM_ADMIN_IDS = '10,20,30';
    const wl = new Whitelist({ whitelistPath: wlPath, readOnly: true });
    await wl.load();
    assertEqual(wl.isAdmin(10), true, '13.1 ENV admin: isAdmin(10)');
    assertEqual(wl.isAdmin(20), true, '13.2 ENV admin: isAdmin(20)');
    assertEqual(wl.isAdmin(40), false, '13.3 ENV admin: isAdmin(40)');
    assertEqual(wl.getAdminIds().length, 3, '13.4 ENV admin: count = 3');
    delete process.env.TELEGRAM_ADMIN_IDS;
  });

  // ==================== Summary ====================
  const total = testCount;
  const passed = passedCount;
  const failed = total - passed;
  console.log(`\n=== Результаты: ${passed}/${total} пройдено ${failed > 0 ? `, ${failed} не пройдено` : '✓'} ===`);

  if (failed > 0) {
    process.exitCode = 1;
  }
})();
