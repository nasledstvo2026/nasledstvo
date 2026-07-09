/**
 * Session Commands — Тесты
 *
 * Story 1.5 — Команды управления сессией (resume, history, cancel, back)
 *
 * Покрытие:
 *   1. handleStartCommand — без активной сессии (онбординг + создание)
 *   2. handleStartCommand — с активной сессией (resume-диалог)
 *   3. handleStartCommand — неавторизованный пользователь
 *   4. handleResumeDialog — формат сообщения, клавиатура
 *   5. handleResumeDialog — с последним ответом
 *   6. handleHistoryCommand — пустая история
 *   7. handleHistoryCommand — с завершёнными сессиями
 *   8. handleCancelCommand — без активной сессии
 *   9. handleCancelCommand — с активной сессией (запрос подтверждения)
 *  10. handleCancelConfirm — подтверждение отмены
 *  11. handleCancelConfirm — отказ от отмены
 *  12. handleBackCommand — без активной сессии
 *  13. handleBackCommand — с активной сессией (запрос возврата)
 *  14. handleBackConfirm — подтверждение возврата
 *  15. handleCallback — резолвинг callback-запросов
 *  16. handleHistoryCallback — просмотр сессии
 *  17. handleResumeCallback — продолжение сессии
 *  18. handleResumeCallback — новая сессия
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');

const SessionCommands = require('../lib/session-commands');
const Whitelist = require('../lib/whitelist');

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
    if (e.stack) console.error(e.stack.slice(0, 300));
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
    assert.ok(pattern.test(actual), `${label}: expected "${actual}" to match ${pattern}`);
    passedCount++;
    console.log(`  ✓ ${label}`);
  } catch (e) {
    console.log(`  ✗ ${label}: ${e.message}`);
  }
}

async function withTempDir(run) {
  const tmpDir = fs.mkdtempSync(path.join(os.tmpdir(), 'sc-uitest-'));
  try {
    await run(tmpDir);
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

// ==================== Mocks ====================

/**
 * Создаёт mock TelegramConnector с перехватом sendMessage.
 */
function createMockConnector(options = {}) {
  const sentMessages = [];

  const connector = {
    botToken: 'test:token',
    sentMessages,

    sendMessage: async (chatId, text, opts) => {
      const msg = { chatId, text, opts: opts || {} };
      sentMessages.push(msg);
      return { ok: true, chatId, text };
    },

    _apiCall: async (method, body) => {
      return { ok: true };
    }
  };

  return connector;
}

/**
 * Создаёт mock SessionManager с тестовыми данными.
 */
function createMockSessionManager(sessions = {}) {
  const store = {
    sessions: sessions.active || {},
    completed: sessions.completed || []
  };

  return {
    store,
    _callLog: [],

    async getActiveSessionByUser(telegramUserId) {
      this._callLog.push({ method: 'getActiveSessionByUser', telegramUserId });
      // Ищем активную сессию по userId
      for (const [id, s] of Object.entries(store.sessions)) {
        if (s.telegramUserId === telegramUserId && s.status === 'in_progress') {
          return s;
        }
      }
      return null;
    },

    async createSession(telegramUserId, options = {}) {
      this._callLog.push({ method: 'createSession', telegramUserId, options });
      const sessionId = 'test_' + Date.now() + '_' + Math.random().toString(36).slice(2, 8);
      const session = {
        sessionId,
        telegramUserId,
        username: options.username || null,
        status: 'in_progress',
        createdAt: new Date().toISOString(),
        updatedAt: new Date().toISOString(),
        template: { block: 1, subsection: '1.1', depth: 'L1' },
        answers: {},
        risks: [],
        documentReady: false
      };
      store.sessions[sessionId] = session;
      return session;
    },

    async completeSession(sessionId) {
      this._callLog.push({ method: 'completeSession', sessionId });
      const session = store.sessions[sessionId];
      if (session) {
        session.status = 'completed';
        session.updatedAt = new Date().toISOString();
      }
      return session;
    },

    async updateSession(sessionId, updates) {
      this._callLog.push({ method: 'updateSession', sessionId, updates });
      const session = store.sessions[sessionId];
      if (session && updates) {
        Object.assign(session, updates);
      }
      return session;
    },

    async getSession(sessionId) {
      this._callLog.push({ method: 'getSession', sessionId });
      return store.sessions[sessionId] || null;
    },

    async listCompletedSessions(telegramUserId) {
      this._callLog.push({ method: 'listCompletedSessions', telegramUserId });
      return store.completed.filter(s => s.telegramUserId === telegramUserId);
    }
  };
}

/**
 * Создаёт mock TemplateEngine.
 */
function createMockTemplateEngine(options = {}) {
  const subsections = options.subsections || [
    { id: '1.1', name: 'Название и цель проекта',  questions: { L1: 'Расскажите о проекте', L2: 'Уточните цель', L3: 'Корневой вопрос' } },
    { id: '1.2', name: 'Зачем нужен проект',       questions: { L1: 'Зачем проект?', L2: 'Уточните зачем', L3: 'Корень зачем' } },
    { id: '1.3', name: 'Результаты проекта',        questions: { L1: 'Какие результаты?', L2: 'Уточните результаты', L3: 'Корень результатов' } },
    { id: '2.1', name: 'Заинтересованные стороны',  questions: { L1: 'Кто заинтересован?', L2: 'Уточните кто', L3: 'Корень кто' } }
  ];

  const blocks = options.blocks || [
    { id: 1, key: 'block.1', name: 'Бизнес-контекст', subsections: subsections.slice(0, 3) },
    { id: 2, key: 'block.2', name: 'Стейкхолдеры',   subsections: subsections.slice(3, 4) }
  ];

  return {
    blocks,
    _callLog: [],

    getBlockCount() {
      this._callLog.push({ method: 'getBlockCount' });
      return blocks.length;
    },

    getBlock(id) {
      this._callLog.push({ method: 'getBlock', id });
      return blocks.find(b => b.id === id || b.key === `block.${id}`);
    },

    getSubsection(blockId, subId) {
      this._callLog.push({ method: 'getSubsection', blockId, subId });
      const block = blocks.find(b => b.id === blockId);
      if (!block) return null;
      return block.subsections.find(s => s.id === subId || s.id === `${blockId}.${subId}`);
    },

    getNextSubsection(blockId, subId) {
      this._callLog.push({ method: 'getNextSubsection', blockId, subId });
      const allSubs = blocks.flatMap(b => b.subsections);
      const idx = allSubs.findIndex(s => s.id === subId);
      return idx >= 0 && idx + 1 < allSubs.length ? allSubs[idx + 1] : null;
    },

    getQuestion(subsectionKey, depth) {
      this._callLog.push({ method: 'getQuestion', subsectionKey, depth });
      for (const block of blocks) {
        for (const sub of block.subsections) {
          if (sub.id === subsectionKey) return sub.questions[depth];
        }
      }
      return null;
    }
  };
}

// ==================== Тестовые данные ====================

function makeActiveSession(overrides = {}) {
  return {
    sessionId: overrides.sessionId || 'test_active_001',
    telegramUserId: overrides.telegramUserId || 100,
    username: overrides.username || 'test_user',
    status: 'in_progress',
    createdAt: '2026-07-08T12:00:00.000Z',
    updatedAt: '2026-07-08T12:30:00.000Z',
    template: { block: 1, subsection: '1.2', depth: 'L1' },
    answers: {
      '1.1': { text: 'Работаем над CRM для ритейла. Проект по автоматизации продаж.', depthReached: 'L1' }
    },
    risks: [],
    documentReady: false,
    ...overrides
  };
}

function makeCompletedSession(overrides = {}) {
  return {
    sessionId: overrides.sessionId || 'test_completed_001',
    telegramUserId: overrides.telegramUserId || 100,
    username: overrides.username || 'test_user',
    status: 'completed',
    createdAt: '2026-07-07T10:00:00.000Z',
    updatedAt: '2026-07-07T10:45:00.000Z',
    template: { block: 7, subsection: '7.3', depth: 'L3' },
    answers: {
      '1.1': 'Проект по автоматизации',
      '7.3': 'Риски: сроки, бюджет',
    },
    risks: [
      { text: 'Риск срыва сроков', category: 'technical', probability: 'high' }
    ],
    documentReady: true,
    documentUrl: 'https://example.com/brd/test_completed_001',
    ...overrides
  };
}

// ==================== Tests ====================

(async function() {
  console.log('=== Session Commands Tests ===\n');

  // 1. handleStartCommand — без активной сессии (онбординг)
  console.log('--- 1. handleStartCommand: без активной сессии ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1, 'test_user');

    const sm = createMockSessionManager();
    const cmds = new SessionCommands({ sessionManager: sm, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100, username: 'test_user', first_name: 'Test' }
    };

    const result = await cmds.handleStartCommand({ msg, connector });

    assertEqual(result.action, 'started', '1.1 action = started');
    assertTrue(!!result.reply, '1.2 reply sent');
    assertTrue(!!result.session, '1.3 session created');

    const sent = connector.sentMessages[0];
    assertTrue(!!sent, '1.4 message was sent');
    assertEqual(sent.chatId, 1000, '1.5 chatId = 1000');
    assertMatch(sent.text, /Мамкин аналитик/, '1.6 contains bot name');
    assertMatch(sent.text, /Привет.*test_user/, '1.7 contains username');
  });

  // 2. handleStartCommand — с активной сессией (resume-диалог)
  console.log('\n--- 2. handleStartCommand: с активной сессией ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(200, 1, 'returning_user');

    const session = makeActiveSession({ telegramUserId: 200, username: 'returning_user' });
    const sm = createMockSessionManager({ active: { [session.sessionId]: session } });
    const te = createMockTemplateEngine();
    const cmds = new SessionCommands({ sessionManager: sm, templateEngine: te, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 2000 },
      from: { id: 200, username: 'returning_user', first_name: 'Returning' }
    };

    const result = await cmds.handleStartCommand({ msg, connector });

    assertEqual(result.action, 'resumed', '2.1 action = resumed');
    assertTrue(!!result.reply, '2.2 reply sent');
    assertEqual(result.session.sessionId, session.sessionId, '2.3 correct session');

    const sent = connector.sentMessages[0];
    assertMatch(sent.text, /С возвращением/, '2.4 contains welcome back');
    assertMatch(sent.text, /Бизнес-контекст/, '2.5 contains block name from template');
    assertMatch(sent.text, /Подраздел 1\.2/, '2.6 contains subsection');
    assertMatch(sent.text, /CRM/, '2.7 contains last answer');
  });

  // 3. handleStartCommand — неавторизованный
  console.log('\n--- 3. handleStartCommand: неавторизованный ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();

    const cmds = new SessionCommands({ whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 9999 },
      from: { id: 999, username: 'hacker' }
    };

    const result = await cmds.handleStartCommand({ msg, connector });
    assertEqual(result.action, 'unauthorized', '3.1 action = unauthorized');
    assertMatch(connector.sentMessages[0].text, /нет доступа/, '3.2 access denied');
  });

  // 4. handleResumeDialog — формат сообщения
  console.log('\n--- 4. handleResumeDialog: формат сообщения ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const session = makeActiveSession({ telegramUserId: 100 });
    const te = createMockTemplateEngine();
    const cmds = new SessionCommands({ templateEngine: te, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100, username: 'test_user', first_name: 'Test' }
    };

    const result = await cmds.handleResumeDialog({ msg, connector }, session);
    assertEqual(result.action, 'resumed', '4.1 action = resumed');

    const sent = connector.sentMessages[0];
    assertTrue(!!sent, '4.2 message sent');
    // Проверяем, что в опциях есть reply_markup (inline keyboard)
    assertTrue(!!sent.opts.reply_markup, '4.3 has inline keyboard');
    const keyboard = sent.opts.reply_markup;
    const buttons = keyboard.inline_keyboard.flat();
    assertTrue(buttons.some(b => b.callback_data === 'resume:continue'), '4.4 has continue button');
    assertTrue(buttons.some(b => b.callback_data === 'resume:new'), '4.5 has new session button');
  });

  // 5. handleResumeDialog — с последним ответом
  console.log('\n--- 5. handleResumeDialog: с последним ответом ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const session = makeActiveSession({
      telegramUserId: 100,
      answers: { '1.1': 'Работаем над CRM для ритейла. Автоматизация продаж.' }
    });
    const cmds = new SessionCommands({ whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100, username: 'test_user' }
    };

    await cmds.handleResumeDialog({ msg, connector }, session);
    const sent = connector.sentMessages[0];
    assertMatch(sent.text, /CRM/, '5.1 last answer shown');
    assertMatch(sent.text, /последний ответ/i, '5.2 "последний ответ" label');
  });

  // 6. handleHistoryCommand — пустая история
  console.log('\n--- 6. handleHistoryCommand: пустая история ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const sm = createMockSessionManager({ completed: [] });
    const cmds = new SessionCommands({ sessionManager: sm, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleHistoryCommand({ msg, connector });
    assertEqual(result.action, 'empty', '6.1 action = empty');
    assertMatch(connector.sentMessages[0].text, /нет завершённых/, '6.2 no sessions message');
  });

  // 7. handleHistoryCommand — с завершёнными сессиями
  console.log('\n--- 7. handleHistoryCommand: с завершёнными сессиями ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const completed = [
      makeCompletedSession({ sessionId: 'c1', telegramUserId: 100, documentReady: true }),
      makeCompletedSession({ sessionId: 'c2', telegramUserId: 100, documentReady: false })
    ];
    const sm = createMockSessionManager({ completed });
    const cmds = new SessionCommands({ sessionManager: sm, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleHistoryCommand({ msg, connector });
    assertEqual(result.action, 'list', '7.1 action = list');
    assertEqual(result.sessions.length, 2, '7.2 2 sessions returned');

    const sent = connector.sentMessages[0];
    assertMatch(sent.text, /История сессий/, '7.3 history title');
    assertMatch(sent.text, /завершённ/, '7.4 session count');
    assertTrue(!!sent.opts.reply_markup, '7.5 has keyboard');
  });

  // 8. handleCancelCommand — без активной сессии
  console.log('\n--- 8. handleCancelCommand: без активной сессии ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const sm = createMockSessionManager();
    const cmds = new SessionCommands({ sessionManager: sm, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleCancelCommand({ msg, connector });
    assertEqual(result.action, 'no_session', '8.1 action = no_session');
    assertMatch(connector.sentMessages[0].text, /нет активных/, '8.2 no session message');
  });

  // 9. handleCancelCommand — с активной сессией (запрос подтверждения)
  console.log('\n--- 9. handleCancelCommand: с активной сессией ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const session = makeActiveSession({ telegramUserId: 100 });
    const sm = createMockSessionManager({ active: { [session.sessionId]: session } });
    const te = createMockTemplateEngine();
    const cmds = new SessionCommands({ sessionManager: sm, templateEngine: te, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleCancelCommand({ msg, connector });
    assertEqual(result.action, 'pending_confirmation', '9.1 action = pending_confirmation');

    const sent = connector.sentMessages[0];
    assertMatch(sent.text, /уверены/, '9.2 asks confirmation');
    assertMatch(sent.text, /Бизнес-контекст/, '9.3 shows block name');
    assertMatch(sent.text, /Сохранено ответов/, '9.4 shows answer count');

    // Check keyboard
    const buttons = sent.opts.reply_markup.inline_keyboard.flat();
    assertTrue(buttons.some(b => b.callback_data === 'cancel:confirm'), '9.5 confirm button');
    assertTrue(buttons.some(b => b.callback_data === 'cancel:abort'), '9.6 abort button');
  });

  // 10. handleCancelConfirm — подтверждение отмены
  console.log('\n--- 10. handleCancelConfirm: подтверждение отмены ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const session = makeActiveSession({ telegramUserId: 100 });
    const sm = createMockSessionManager({ active: { [session.sessionId]: session } });
    const cmds = new SessionCommands({ sessionManager: sm, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleCancelConfirm({
      msg,
      connector,
      callbackData: 'cancel:confirm'
    });

    assertEqual(result.action, 'cancelled', '10.1 action = cancelled');
    assertMatch(connector.sentMessages[0].text, /Сессия завершена/, '10.2 cancelled message');
    assertEqual(session.status, 'completed', '10.3 session status updated');
    assertTrue(sm._callLog.some(c => c.method === 'completeSession'), '10.4 completeSession called');
  });

  // 11. handleCancelConfirm — отказ от отмены
  console.log('\n--- 11. handleCancelConfirm: отказ от отмены ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const cmds = new SessionCommands({ whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleCancelConfirm({
      msg,
      connector,
      callbackData: 'cancel:abort'
    });

    assertEqual(result.action, 'cancellation_aborted', '11.1 action = cancellation_aborted');
    assertMatch(connector.sentMessages[0].text, /Продолжаем опрос/, '11.2 continue message');
  });

  // 12. handleBackCommand — без активной сессии
  console.log('\n--- 12. handleBackCommand: без активной сессии ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const sm = createMockSessionManager();
    const cmds = new SessionCommands({ sessionManager: sm, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleBackCommand({ msg, connector });
    assertEqual(result.action, 'no_session', '12.1 action = no_session');
    assertMatch(connector.sentMessages[0].text, /нет активной/, '12.2 no session message');
  });

  // 13. handleBackCommand — с активной сессией
  console.log('\n--- 13. handleBackCommand: с активной сессией ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const session = makeActiveSession({
      telegramUserId: 100,
      template: { block: 1, subsection: '1.2', depth: 'L1' }
    });
    const sm = createMockSessionManager({ active: { [session.sessionId]: session } });
    const te = createMockTemplateEngine();
    const cmds = new SessionCommands({ sessionManager: sm, templateEngine: te, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleBackCommand({ msg, connector });
    assertEqual(result.action, 'pending_back', '13.1 action = pending_back');
    assertTrue(!!result.previousSubsection, '13.2 has previous subsection');
    assertEqual(result.previousSubsection.fullKey, '1.1', '13.3 previous = 1.1');
    assertTrue(!!result.previousAnswer, '13.4 has previous answer');

    const sent = connector.sentMessages[0];
    assertMatch(sent.text, /Вернуться/, '13.5 asks back confirmation');
    assertMatch(sent.text, /CRM/, '13.6 shows previous answer');
  });

  // 14. handleBackConfirm — подтверждение возврата
  console.log('\n--- 14. handleBackConfirm: подтверждение возврата ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const session = makeActiveSession({
      telegramUserId: 100,
      template: { block: 1, subsection: '1.2', depth: 'L1' },
      answers: { '1.1': 'CRM для ритейла' }
    });
    const sm = createMockSessionManager({ active: { [session.sessionId]: session } });
    const te = createMockTemplateEngine();
    const cmds = new SessionCommands({ sessionManager: sm, templateEngine: te, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleBackConfirm({
      msg,
      connector,
      callbackData: 'back:confirm'
    });

    assertEqual(result.action, 'back_completed', '14.1 action = back_completed');
    assertEqual(session.template.subsection, '1.1', '14.2 session moved to subsection 1.1');
    assertEqual(session.template.block, 1, '14.3 block unchanged (same block)');

    const sent = connector.sentMessages[0];
    assertMatch(sent.text, /Вернулись/, '14.4 back completed message');
    assertMatch(sent.text, /CRM/, '14.5 shows previous answer');
    assertMatch(sent.text, /Расскажите о проекте/, '14.6 shows L1 question');
  });

  // 15. handleCallback — резолвинг callback-запросов
  console.log('\n--- 15. handleCallback: dispatch ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const cmds = new SessionCommands({ whitelist: wl });
    const connector = createMockConnector();

    // cancel:abort
    let result = await cmds.handleCallback({
      msg: { chat: { id: 1000 }, from: { id: 100 } },
      connector,
      callbackData: 'cancel:abort'
    });
    assertEqual(result.action, 'cancellation_aborted', '15.1 cancel:abort routed');

    // back:abort
    result = await cmds.handleCallback({
      msg: { chat: { id: 1000 }, from: { id: 100 } },
      connector,
      callbackData: 'back:abort'
    });
    assertEqual(result.action, 'back_aborted', '15.2 back:abort routed');
  });

  // 16. handleHistoryCallback — просмотр сессии
  console.log('\n--- 16. handleHistoryCallback: просмотр сессии ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const session = makeCompletedSession({
      sessionId: 'session_to_view',
      telegramUserId: 100,
      documentReady: true
    });
    const sm = createMockSessionManager({ active: { session_to_view: session } });
    const cmds = new SessionCommands({ sessionManager: sm, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleCallback({
      msg,
      connector,
      callbackData: 'history:view:session_to_view'
    });

    assertEqual(result.action, 'history_viewed', '16.1 action = history_viewed');
    const sent = connector.sentMessages[0];
    assertMatch(sent.text, /session_/, '16.2 shows session id');
    assertMatch(sent.text, /Документ готов/, '16.3 shows document status');
  });

  // 17. handleResumeCallback — продолжение сессии
  console.log('\n--- 17. handleResumeCallback: продолжение сессии ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const session = makeActiveSession({ telegramUserId: 100 });
    const sm = createMockSessionManager({ active: { [session.sessionId]: session } });
    const te = createMockTemplateEngine();
    const cmds = new SessionCommands({ sessionManager: sm, templateEngine: te, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100 }
    };

    const result = await cmds.handleCallback({
      msg,
      connector,
      callbackData: 'resume:continue'
    });

    assertEqual(result.action, 'resume_continued', '17.1 action = resume_continued');
    const sent = connector.sentMessages[0];
    assertMatch(sent.text, /Продолжаем опрос/, '17.2 continue message');
    assertMatch(sent.text, /Зачем проект/, '17.3 shows question');
  });

  // 18. handleResumeCallback — новая сессия
  console.log('\n--- 18. handleResumeCallback: новая сессия ---');
  await withTempDir(async (tmpDir) => {
    const wlPath = path.join(tmpDir, 'whitelist.json');
    const wl = new Whitelist({ whitelistPath: wlPath, adminIds: [1], readOnly: true });
    await wl.load();
    await wl.addUser(100, 1);

    const sm = createMockSessionManager();
    const cmds = new SessionCommands({ sessionManager: sm, whitelist: wl });
    const connector = createMockConnector();

    const msg = {
      chat: { id: 1000 },
      from: { id: 100, username: 'fresh_start' }
    };

    const result = await cmds.handleCallback({
      msg,
      connector,
      callbackData: 'resume:new'
    });

    assertEqual(result.action, 'resume_new_session', '18.1 action = resume_new_session');
    const sent = connector.sentMessages[0];
    assertMatch(sent.text, /Мамкин аналитик/, '18.2 onboarding text');
    assertTrue(sm._callLog.some(c => c.method === 'createSession'), '18.3 createSession called');
  });

  // ==================== Summary ====================
  console.log(`\n=== Результаты: ${passedCount}/${testCount} тестов пройдено ===`);
  process.exitCode = passedCount === testCount ? 0 : 1;

})().catch(err => {
  console.error('FATAL:', err.message);
  process.exitCode = 1;
});
