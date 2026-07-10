/**
 * Telegram Connector — Тесты
 *
 * Story 1.4 — Telegram Bot Connector + Whitelist
 *
 * Покрытие:
 *   1. extractUserInfo: админ, whitelisted, неавторизованный, null
 *   2. handleStartCommand с мокированными API вызовами
 *   3. handleAddUser: админ может добавить, не-админ не может
 *   4. handleRemoveUser: админ может удалить, защита администраторов
 *   5. Валидация аргументов команд
 *   6. Команда /help
 *   7. Команда /cancel
 *   8. Команда /admin
 *   9. Неизвестная команда
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');

const Whitelist = require('../lib/whitelist');
const TelegramConnector = require('../lib/telegram-connector');

// ==================== Counter + Helpers ====================

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

function assertTrue(actual, label) {
  testCount++;
  if (actual) {
    passedCount++;
    console.log(`  ✓ ${label}`);
  } else {
    console.log(`  ✗ ${label}: expected true, got ${JSON.stringify(actual)}`);
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
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'tg-uitest-'));
  try {
    await run(tmpDir);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

/**
 * Создаёт TelegramConnector с заглушками вместо реальных API вызовов.
 * Заменяет _apiCall и sendMessage на моки.
 */
function createMockConnector(options = {}) {
  const {
    adminIds = [1, 999],
    whitelistUsers = [],
    skipInit = true
  } = options;

  const connector = new TelegramConnector({
    adminIds,
    skipInit,
    botToken: 'test:token',
    ...options
  });

  // Мокируем _apiCall
  connector._apiCall = async (method, body) => {
    if (method === 'sendMessage') {
      return {
        message_id: 100,
        chat: { id: body.chat_id },
        text: body.text,
        date: Math.floor(Date.now() / 1000)
      };
    }
    if (method === 'getMe') {
      return { id: 123456, username: 'TestBot', first_name: 'Test' };
    }
    // Для неизвестных методов
    return null;
  };

  // Явно добавляем sendMessage чтобы не проходил через _apiCall
  connector.sendMessage = async (chatId, text, opts) => {
    return await connector._apiCall('sendMessage', {
      chat_id: chatId,
      text,
      ...opts
    });
  };

  return connector;
}

/**
 * Создаёт готовый к тестам TelegramConnector с whitelist.
 */
async function createReadyConnector(tmpDir, options = {}) {
  const wlPath = path.join(tmpDir, 'whitelist.json');
  const adminIds = options.adminIds || [1, 999];

  const wl = new Whitelist({ whitelistPath: wlPath, adminIds, readOnly: true });
  await wl.load();

  // Добавляем тестовых пользователей
  if (options.whitelistUsers !== undefined) {
    for (const u of options.whitelistUsers) {
      await wl.addUser(u.id, u.addedBy || 1, u.username || null);
    }
  }

  const connector = createMockConnector({
    whitelist: wl,
    adminIds,
    skipInit: true,
    ...options
  });
  await connector.initialize();

  return { tmpDir, wl, connector };
}

// ==================== Tests ====================

(async function() {
  console.log('=== Telegram Connector Tests ===\n');

  // === Test 1: extractUserInfo ===
  console.log('--- 1. extractUserInfo ---');
  await withTempDir(async (tmpDir) => {
    const { connector, wl } = await createReadyConnector(tmpDir, {
      whitelistUsers: [
        { id: 100, addedBy: 1, username: 'regular_user' }
      ]
    });

    // Admin
    const adminMsg = {
      from: { id: 1, username: 'admin', first_name: 'Admin', last_name: 'Adminov', language_code: 'ru' },
      chat: { id: 1000 }
    };
    const adminInfo = connector.extractUserInfo(adminMsg);
    assertEqual(adminInfo.telegramId, 1, '1.1 admin telegramId');
    assertTrue(adminInfo.isAdmin, '1.2 admin isAdmin');
    assertEqual(adminInfo.isWhitelisted, false, '1.3 admin isWhitelisted (admin не в whitelist)');
    assertEqual(adminInfo.username, 'admin', '1.4 admin username');
    assertEqual(adminInfo.languageCode, 'ru', '1.5 admin languageCode');

    // Whitelisted user
    const userMsg = {
      from: { id: 100, username: 'regular_user', first_name: 'Regular' },
      chat: { id: 1001 }
    };
    const userInfo = connector.extractUserInfo(userMsg);
    assertEqual(userInfo.telegramId, 100, '1.6 user telegramId');
    assertEqual(userInfo.isAdmin, false, '1.7 user isAdmin');
    assertTrue(userInfo.isWhitelisted, '1.8 user isWhitelisted');

    // Unknown user
    const unknownMsg = {
      from: { id: 200, username: 'hacker', first_name: 'Hacker' },
      chat: { id: 1002 }
    };
    const unknownInfo = connector.extractUserInfo(unknownMsg);
    assertEqual(unknownInfo.isWhitelisted, false, '1.9 unknown isWhitelisted');

    // Null
    assertEqual(connector.extractUserInfo(null), null, '1.10 null msg = null');
    assertEqual(connector.extractUserInfo({}), null, '1.11 msg without from = null');
  });

  // === Test 2: handleStartCommand — unauthorized ===
  console.log('\n--- 2. handleStartCommand: unauthorized ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      whitelistUsers: []
    });

    const msg = {
      from: { id: 9999, username: 'stranger', first_name: 'Stranger' },
      chat: { id: 2000 }
    };

    const result = await connector.handleStartCommand(msg);
    assertTrue(!!result, '2.1 Результат не null');
    assertMatch(result.text, /нет доступа/, '2.2 Сообщение об отказе в доступе');
    assertEqual(result.chat.id, 2000, '2.3 chat.id = 2000');
  });

  // === Test 3: handleStartCommand — authorized user ===
  console.log('\n--- 3. handleStartCommand: authorized ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      whitelistUsers: [
        { id: 100, addedBy: 1, username: 'authorized_user' }
      ]
    });

    const msg = {
      from: { id: 100, username: 'authorized_user', first_name: 'Authorized' },
      chat: { id: 3000 }
    };

    const result = await connector.handleStartCommand(msg);
    assertTrue(!!result, '3.1 Результат не null');
    // Должен быть онбординг, а не отказ
    assertMatch(result.text, /Привет|Мамкин аналитик|Начнём|продолжить/i, '3.2 Онбординг/продолжение');
    assertEqual(result.chat.id, 3000, '3.3 chat.id = 3000');
  });

  // === Test 4: handleAddUser — non-admin gets error ===
  console.log('\n--- 4. handleAddUser: non-admin ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      whitelistUsers: [
        { id: 100, addedBy: 1, username: 'regular_user' }
      ]
    });

    const msg = {
      from: { id: 100, username: 'regular_user' },
      chat: { id: 4000 }
    };

    const result = await connector.handleAddUser(msg, ['12345']);
    assertTrue(!!result, '4.1 Результат не null');
    assertMatch(result.text, /нет прав/, '4.2 Сообщение о недостатке прав');
  });

  // === Test 5: handleAddUser — admin adds user ===
  console.log('\n--- 5. handleAddUser: admin adds user ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      adminIds: [1],
      whitelistUsers: []
    });

    const msg = {
      from: { id: 1, username: 'admin', first_name: 'Admin' },
      chat: { id: 5000 }
    };

    const result = await connector.handleAddUser(msg, ['12345', 'new_user']);
    assertTrue(!!result, '5.1 Результат не null');
    assertMatch(result.text, /добавлен/, '5.2 Сообщение об успешном добавлении');
    assertTrue(connector.whitelist.isWhitelisted(12345), '5.3 Пользователь добавлен в whitelist');
  });

  // === Test 6: handleAddUser — invalid arguments ===
  console.log('\n--- 6. handleAddUser: invalid args ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      adminIds: [1],
      whitelistUsers: []
    });

    const msg = {
      from: { id: 1, username: 'admin' },
      chat: { id: 6000 }
    };

    // No args
    let result = await connector.handleAddUser(msg, []);
    assertMatch(result.text, /Использование|использование/, '6.1 Пустые аргументы: показана справка');

    // Invalid ID (string)
    result = await connector.handleAddUser(msg, ['abc']);
    assertMatch(result.text, /Невалидный|невалидный/, '6.2 Невалидный ID: сообщение об ошибке');

    // Negative ID
    result = await connector.handleAddUser(msg, ['-1']);
    assertMatch(result.text, /Невалидный|невалидный/, '6.3 Отрицательный ID: сообщение об ошибке');
  });

  // === Test 7: handleRemoveUser — non-admin ===
  console.log('\n--- 7. handleRemoveUser: non-admin ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      whitelistUsers: [
        { id: 100, addedBy: 1, username: 'regular' }
      ]
    });

    const msg = {
      from: { id: 100, username: 'regular' },
      chat: { id: 7000 }
    };

    const result = await connector.handleRemoveUser(msg, ['12345']);
    assertMatch(result.text, /нет прав/, '7.1 Не-админ: сообщение о недостатке прав');
  });

  // === Test 8: handleRemoveUser — admin removes user ===
  console.log('\n--- 8. handleRemoveUser: admin removes user ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      adminIds: [1],
      whitelistUsers: [
        { id: 100, addedBy: 1, username: 'to_remove' }
      ]
    });

    assertTrue(connector.whitelist.isWhitelisted(100), '8.0 Перед удалением: пользователь в whitelist');

    const msg = {
      from: { id: 1, username: 'admin' },
      chat: { id: 8000 }
    };

    const result = await connector.handleRemoveUser(msg, ['100']);
    assertMatch(result.text, /удалён/, '8.1 Сообщение об успешном удалении');
    assertEqual(connector.whitelist.isWhitelisted(100), false, '8.2 После удаления: пользователя нет в whitelist');
  });

  // === Test 9: handleRemoveUser — admin cannot remove admin ===
  console.log('\n--- 9. handleRemoveUser: admin can\'t remove admin ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      adminIds: [1, 999],
      whitelistUsers: [
        { id: 999, addedBy: 1, username: 'admin2' }
      ]
    });

    const msg = {
      from: { id: 1, username: 'admin' },
      chat: { id: 9000 }
    };

    const result = await connector.handleRemoveUser(msg, ['999']);
    assertMatch(result.text, /Нельзя удалить администратора/, '9.1 Защита админа: сообщение');
    assertTrue(connector.whitelist.isWhitelisted(999), '9.2 Админ остался в whitelist');
  });

  // === Test 10: handleRemoveUser — invalid args ===
  console.log('\n--- 10. handleRemoveUser: invalid args ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      adminIds: [1],
      whitelistUsers: []
    });

    const msg = {
      from: { id: 1, username: 'admin' },
      chat: { id: 10000 }
    };

    // No args
    let result = await connector.handleRemoveUser(msg, []);
    assertMatch(result.text, /Использование|использование/, '10.1 Пустые аргументы: справка');

    // Invalid ID
    result = await connector.handleRemoveUser(msg, ['abc']);
    assertMatch(result.text, /Невалидный|невалидный/, '10.2 Невалидный ID: ошибка');

    // Non-existent user (valid ID format but not in whitelist)
    result = await connector.handleRemoveUser(msg, ['77777']);
    assertMatch(result.text, /не найден/, '10.3 Несуществующий: сообщение');
  });

  // === Test 11: Unknown command ===
  console.log('\n--- 11. Unknown command ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      whitelistUsers: [{ id: 100, addedBy: 1 }]
    });

    const msg = {
      from: { id: 100, username: 'user' },
      chat: { id: 11000 },
      text: '/nonexistent'
    };

    // Используем _handleMessage — он сам определит команду
    const result = await connector._handleMessage(msg);
    assertTrue(!!result, '11.1 Результат не null');
    assertMatch(result.text, /Неизвестная команда|неизвестная команда/, '11.2 Сообщение о неизвестной команде');
  });

  // === Test 12: processUpdate ===
  console.log('\n--- 12. processUpdate ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      whitelistUsers: []
    });

    // Null update
    const nullResult = await connector.processUpdate(null);
    assertEqual(nullResult, null, '12.1 null update = null');

    // Unknown type
    const unknownResult = await connector.processUpdate({
      update_id: 1,
      unknown_field: true
    });
    assertEqual(unknownResult, null, '12.2 Unknown update type = null');

    // Message (should process)
    const msgResult = await connector.processUpdate({
      update_id: 2,
      message: {
        message_id: 200,
        from: { id: 9999, username: 'stranger' },
        chat: { id: 12000 },
        text: '/start'
      }
    });
    assertTrue(!!msgResult, '12.3 Update with message returned result');
    assertMatch(msgResult.text, /нет доступа/, '12.4 /start для неавторизованного = отказ');
  });

  // === Test 13: Admin can list whitelist (command /admin) ===
  console.log('\n--- 13. /admin command ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      adminIds: [1],
      whitelistUsers: [
        { id: 100, addedBy: 1, username: 'first_user' }
      ]
    });

    // Admin tries /admin
    const adminMsg = {
      from: { id: 1, username: 'admin' },
      chat: { id: 13000 }
    };
    const result = await connector._handleAdminCommand(adminMsg);
    assertTrue(!!result, '13.1 Результат не null');
    assertMatch(result.text, /Whitelist|whitelist|Пользователи/i, '13.2 Содержит информацию о whitelist');
    assertMatch(result.text, /1/, '13.3 Содержит количество пользователей');
  });

  // === Test 14: Non-admin can't run /admin ===
  console.log('\n--- 14. /admin for non-admin ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      whitelistUsers: [
        { id: 100, addedBy: 1, username: 'regular' }
      ]
    });

    const msg = {
      from: { id: 100, username: 'regular' },
      chat: { id: 14000 }
    };
    const result = await connector._handleAdminCommand(msg);
    assertMatch(result.text, /нет прав/, '14.1 Не-админ: нет прав');
  });

  // === Test 15: /help command ===
  console.log('\n--- 15. /help command ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      adminIds: [1],
      whitelistUsers: [
        { id: 100, addedBy: 1, username: 'regular' },
        { id: 1, addedBy: 1, username: 'admin' }
      ]
    });

    // Non-admin help
    const userMsg = {
      from: { id: 100, username: 'regular' },
      chat: { id: 15000 }
    };
    const userResult = await connector._handleHelpCommand(userMsg);
    assertTrue(!!userResult, '15.1 Результат не null');
    assertMatch(userResult.text, /Доступные команды|доступные команды/i, '15.2 Содержит список команд');
    // Non-admin should NOT see admin commands
    assertEqual(userResult.text.includes('/adduser'), false, '15.3 У user нет /adduser в help');

    // Admin help
    const adminMsg = {
      from: { id: 1, username: 'admin' },
      chat: { id: 15001 }
    };
    const adminResult = await connector._handleHelpCommand(adminMsg);
    assertTrue(adminResult.text.includes('/adduser'), '15.4 У админа есть /adduser в help');
    assertTrue(adminResult.text.includes('/admin'), '15.5 У админа есть /admin в help');
  });

  // === Test 16: Unauthorized user can't get help ===
  console.log('\n--- 16. Unauthorized help ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      whitelistUsers: []
    });

    const msg = {
      from: { id: 9999, username: 'stranger' },
      chat: { id: 16000 }
    };
    const result = await connector._handleHelpCommand(msg);
    assertMatch(result.text, /нет доступа/, '16.1 Неавторизованный: отказ');
  });

  // === Test 17: /создатьбт command (aliased /start) ===
  console.log('\n--- 17. /создатьбт command ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      adminIds: [1],
      whitelistUsers: [
        { id: 100, addedBy: 1, username: 'first_user' },
        { id: 1, addedBy: 1, username: 'admin' }
      ]
    });

    // Authorized user sends /создатьбт
    const authMsg = {
      from: { id: 100, username: 'first_user' },
      chat: { id: 17000 }
    };
    const result = await connector._handleCommand(authMsg, '/создатьбт');
    assertTrue(!!result, '17.1 /создатьбт = результат');
    assertMatch(result.text, /бизнес-требований|бизнес требования|опрос/i, '17.2 /создатьбт приветствие');

    // Unauthorized
    const unauthMsg = {
      from: { id: 9999, username: 'stranger' },
      chat: { id: 17001 }
    };
    const unauthResult = await connector._handleCommand(unauthMsg, '/создатьбт');
    assertTrue(!!unauthResult, '17.3 /создатьбт неавториз = результат');
    assertMatch(unauthResult.text, /нет доступа/, '17.4 /создатьбт неавториз = отказ');

    // /start backward compat
    const startResult = await connector._handleCommand(authMsg, '/start');
    assertTrue(!!startResult, '17.5 /start совместимость = результат');
    assertMatch(startResult.text, /бизнес-требований|бизнес требования|опрос/i, '17.6 /start тоже работает');
  });


  // === Test 17: Delete webhook ===
  console.log('\n--- 17. Webhook operations ---');
  await withTempDir(async (tmpDir) => {
    const { connector } = await createReadyConnector(tmpDir, {
      whitelistUsers: []
    });

    // deleteWebhook возвращает результат от _apiCall
    const result = await connector.deleteWebhook();
    assertEqual(result, null, '17.1 deleteWebhook returns result from _apiCall');

    // setWebhook
    const webhookResult = await connector.setWebhook('https://example.com/webhook');
    assertEqual(webhookResult, null, '17.2 setWebhook returns result');

    // getWebhookInfo
    const info = await connector.getWebhookInfo();
    assertEqual(info, null, '17.3 getWebhookInfo returns result');
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
