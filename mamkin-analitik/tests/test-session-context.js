/**
 * Тесты Session Context (Story 1.7)
 *
 * Проверяет:
 *   1. Создание SessionContext из сессии
 *   2. Сериализация/десериализация JSON
 *   3. Обновление контекста (update)
 *   4. Добавление рисков
 *   5. Установка черновика
 *   6. Маркировка documentReady
 *   7. getAnswer / getDepthReached / getAnswersByBlock
 *   8. getSummary / getProgressText
 *   9. getNextAgent — маршрутизация между агентами
 *  10. Сквозной тест: сессия → контекст → агент → обновление → сохранение
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');
const SessionManager = require('../lib/session-manager');
const SessionContext = require('../lib/session-context');

// ==================== Helper ====================

function createTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'context-test-'));
}

function makeConfig(tmpDir) {
  return {
    storagePath: tmpDir,
    allowEmptyKey: true
  };
}

function createMockSession(overrides = {}) {
  return {
    sessionId: overrides.sessionId || 'test-session-123',
    telegramUserId: overrides.telegramUserId || 12345,
    username: overrides.username || 'test_user',
    status: overrides.status || 'in_progress',
    createdAt: overrides.createdAt || '2026-07-08T12:00:00.000Z',
    updatedAt: overrides.updatedAt || '2026-07-08T12:00:00.000Z',
    template: overrides.template || {
      block: 1,
      subsection: '1.1',
      depth: 'L1'
    },
    answers: overrides.answers || {},
    risks: overrides.risks || [],
    documentReady: overrides.documentReady || false,
    qualityGate: overrides.qualityGate || {
      approved: false,
      issues: [],
      iteration: 0
    },
    draft: overrides.draft || null,
    documentUrl: overrides.documentUrl || null,
    completedAt: overrides.completedAt || null
  };
}

// ==================== Tests ====================

async function testCreateContextFromSession() {
  const session = createMockSession({
    sessionId: 'ctx-test-1',
    telegramUserId: 100,
    username: 'ivan',
    answers: {
      '1.1': { L1: 'Ответ на 1.1', depthReached: 'L1' },
      '1.2': { L1: 'Ответ на 1.2', L2: 'Уточнение', depthReached: 'L2' }
    },
    risks: [
      { text: 'Риск 1', category: 'business', collectedAt: 'block_1' }
    ],
    template: { block: 1, subsection: '1.3', depth: 'L1' }
  });

  const ctx = SessionContext.fromSession(session);

  assert(ctx, 'Context должен быть создан');
  assert.strictEqual(ctx.sessionId, 'ctx-test-1', 'sessionId должен совпадать');
  assert.strictEqual(ctx.telegramUserId, 100, 'telegramUserId должен совпадать');
  assert.strictEqual(ctx.currentBlock, 1, 'currentBlock должен быть 1');
  assert.strictEqual(ctx.currentSubsection, '1.3', 'currentSubsection должен быть 1.3');
  assert.strictEqual(ctx.depth, 'L1', 'depth должен быть L1');
  assert.strictEqual(ctx.risks.length, 1, 'Должен быть 1 риск');
  assert.strictEqual(ctx.getAnsweredCount(), 2, 'Должно быть 2 отвеченных подраздела');

  console.log('✓ testCreateContextFromSession');
}

async function testContextSerialization() {
  const session = createMockSession({
    sessionId: 'ser-test',
    answers: {
      '2.1': { L1: 'Ответ', depthReached: 'L1' }
    }
  });

  const ctx = SessionContext.fromSession(session);

  // Сериализация
  const json = ctx.serialize();
  assert(json, 'JSON-строка не должна быть пустой');

  const parsed = JSON.parse(json);
  assert.strictEqual(parsed.sessionId, 'ser-test', 'sessionId в JSON должен совпадать');
  assert.strictEqual(parsed.answers['2.1'].L1, 'Ответ', 'Ответ в JSON должен совпадать');

  // Десериализация обратно
  const ctx2 = SessionContext.fromJSON(json);
  assert(ctx2, 'Контекст должен создаваться из JSON');
  assert.strictEqual(ctx2.sessionId, 'ser-test', 'sessionId после десериализации');
  assert.strictEqual(ctx2.getAnswer('2.1'), 'Ответ', 'Ответ после десериализации');

  // toJSON
  const obj = ctx.toJSON();
  assert(obj.sessionId, 'toJSON должен содержать sessionId');
  assert(obj.answers, 'toJSON должен содержать answers');
  assert(obj.meta, 'toJSON должен содержать meta');

  console.log('✓ testContextSerialization');
}

async function testContextUpdate() {
  const session = createMockSession();
  const ctx = SessionContext.fromSession(session);

  // Обновляем позицию опроса
  ctx.update({
    currentBlock: 2,
    currentSubsection: '2.3',
    depth: 'L2'
  });

  assert.strictEqual(ctx.currentBlock, 2, 'currentBlock должен обновиться');
  assert.strictEqual(ctx.currentSubsection, '2.3', 'currentSubsection должен обновиться');
  assert.strictEqual(ctx.depth, 'L2', 'depth должен обновиться');

  // meta.updatedAt должен обновиться
  assert(ctx.meta.updatedAt > '2026-07-08T12:00:00.000Z',
    'updatedAt должен обновиться при update');

  // Обновляем ответы
  ctx.update({
    answers: {
      '1.1': { L1: 'Новый ответ', depthReached: 'L1' }
    }
  });

  assert.strictEqual(ctx.answers['1.1'].L1, 'Новый ответ',
    'Ответ должен обновиться');

  // Проверка: статус не обновился (не обновляли)
  assert.strictEqual(ctx.status, 'in_progress', 'Статус не должен меняться');

  console.log('✓ testContextUpdate');
}

async function testAddRisk() {
  const session = createMockSession({ template: { block: 3, subsection: '3.1', depth: 'L1' } });
  const ctx = SessionContext.fromSession(session);

  ctx.addRisk('Бюджет может быть превышен', 'business');
  ctx.addRisk('Команда не готова к срокам', 'org');

  assert.strictEqual(ctx.risks.length, 2, 'Должно быть 2 риска');
  assert.strictEqual(ctx.risks[0].text, 'Бюджет может быть превышен');
  assert.strictEqual(ctx.risks[0].category, 'business');
  assert.strictEqual(ctx.risks[0].collectedAt, 'block_3',
    'collectedAt должен быть текущим блоком');

  assert.strictEqual(ctx.risks[1].text, 'Команда не готова к срокам');
  assert.strictEqual(ctx.risks[1].category, 'org');

  // Все поля риска
  for (const risk of ctx.risks) {
    assert('probability' in risk, 'Риск должен иметь поле probability');
    assert('impact' in risk, 'Риск должен иметь поле impact');
    assert('mitigation' in risk, 'Риск должен иметь поле mitigation');
    assert.strictEqual(risk.probability, null, 'probability должен быть null по умолчанию');
  }

  console.log('✓ testAddRisk');
}

async function testSetDraft() {
  const session = createMockSession();
  const ctx = SessionContext.fromSession(session);

  const draft = {
    blocks: [
      { id: 1, name: 'Предпосылки', content: 'Тестовый контент' },
      { id: 2, name: 'Стейкхолдеры', content: 'Ещё контент' }
    ]
  };

  ctx.setDraft(draft);

  assert(ctx.draft, 'Черновик должен быть установлен');
  assert.strictEqual(ctx.draft.blocks.length, 2, 'Черновик должен содержать 2 блока');
  assert.strictEqual(ctx.draft.blocks[0].name, 'Предпосылки', 'Название блока должно совпадать');

  // updatedAt должен обновиться
  const updatedAt1 = ctx.meta.updatedAt;

  // Задержка для different timestamp
  await new Promise(r => setTimeout(r, 10));

  ctx.setDraft({ blocks: [...draft.blocks, { id: 3, name: 'Требования', content: '...' }] });
  assert(ctx.meta.updatedAt > updatedAt1, 'updatedAt должен обновиться при setDraft');

  console.log('✓ testSetDraft');
}

async function testMarkDocumentReady() {
  const session = createMockSession();
  const ctx = SessionContext.fromSession(session);

  ctx.markDocumentReady();

  assert.strictEqual(ctx.documentReady, true, 'documentReady должен быть true');
  assert.strictEqual(ctx.status, 'completed', 'Статус должен стать completed');
  assert(ctx.meta.completedAt, 'completedAt должен быть установлен');

  const completedAt = new Date(ctx.meta.completedAt);
  assert(completedAt instanceof Date && !isNaN(completedAt),
    'completedAt должен быть валидной датой');

  console.log('✓ testMarkDocumentReady');
}

async function testGetAnswer() {
  const session = createMockSession({
    answers: {
      '1.1': { L1: 'Ответ L1', L2: 'Ответ L2', L3: 'Ответ L3', depthReached: 'L3' },
      '2.1': { L1: 'Только L1', depthReached: 'L1' },
      '3.1': {} // Нет ответов
    }
  });

  const ctx = SessionContext.fromSession(session);

  // getAnswer возвращает максимальную глубину
  assert.strictEqual(ctx.getAnswer('1.1'), 'Ответ L3',
    'getAnswer должен вернуть L3 (максимальная глубина)');
  assert.strictEqual(ctx.getAnswer('2.1'), 'Только L1',
    'getAnswer должен вернуть L1 (единственный ответ)');
  assert.strictEqual(ctx.getAnswer('3.1'), null,
    'getAnswer для пустого подраздела — null');

  // getDepthReached
  assert.strictEqual(ctx.getDepthReached('1.1'), 'L3',
    'depthReached для 1.1 — L3');
  assert.strictEqual(ctx.getDepthReached('2.1'), 'L1',
    'depthReached для 2.1 — L1');
  assert.strictEqual(ctx.getDepthReached('3.1'), null,
    'depthReached для пустого — null');

  console.log('✓ testGetAnswer');
}

async function testGetAnswersByBlock() {
  const session = createMockSession({
    answers: {
      '1.1': { L1: 'A1', depthReached: 'L1' },
      '1.2': { L1: 'A2', depthReached: 'L1' },
      '2.1': { L1: 'B1', depthReached: 'L1' },
      '3.1': { L1: 'C1', depthReached: 'L1' },
      '3.2': { L1: 'C2', depthReached: 'L1' }
    }
  });

  const ctx = SessionContext.fromSession(session);
  const byBlock = ctx.getAnswersByBlock();

  assert(byBlock['1'], 'Блок 1 должен быть');
  assert(byBlock['2'], 'Блок 2 должен быть');
  assert(byBlock['3'], 'Блок 3 должен быть');

  assert.strictEqual(Object.keys(byBlock['1']).length, 2, 'Блок 1: 2 подраздела');
  assert.strictEqual(Object.keys(byBlock['2']).length, 1, 'Блок 2: 1 подраздел');
  assert.strictEqual(Object.keys(byBlock['3']).length, 2, 'Блок 3: 2 подраздела');

  assert.strictEqual(byBlock['1']['1.1'].L1, 'A1', 'Ответ A1 в блоке 1');

  console.log('✓ testGetAnswersByBlock');
}

async function testGetSummary() {
  const session = createMockSession({
    answers: {
      '1.1': { L1: 'test', depthReached: 'L1' },
      '1.2': { L1: 'test', depthReached: 'L1' }
    },
    risks: [{ text: 'R1', category: 'business', collectedAt: 'block_1' }]
  });

  const ctx = SessionContext.fromSession(session);
  ctx.setProgress(50);

  const summary = ctx.getSummary();

  assert.strictEqual(summary.sessionId, session.sessionId, 'summary.sessionId');
  assert.strictEqual(summary.user, 12345, 'summary.user');
  assert.strictEqual(summary.status, 'in_progress', 'summary.status');
  assert.strictEqual(summary.progress, 50, 'summary.progress');
  assert.strictEqual(summary.answersCount, 2, 'summary.answersCount');
  assert.strictEqual(summary.risksCount, 1, 'summary.risksCount');
  assert.strictEqual(summary.hasDraft, false, 'summary.hasDraft');

  console.log('✓ testGetSummary');
}

async function testGetProgressText() {
  const session = createMockSession({
    answers: {
      '1.1': { L1: 'test', depthReached: 'L1' },
      '2.1': { L1: 'test', depthReached: 'L1' }
    }
  });

  const ctx = SessionContext.fromSession(session);
  const text = ctx.getProgressText();

  assert(text.includes('✅'), 'Блок 1 должен быть ✅');
  assert(text.includes('⬜'), 'Некоторые блоки должны быть ⬜');
  assert(text.includes('Блок 1: Предпосылки'), 'Должен быть блок Предпосылки');
  assert(text.includes('Блок 7: Риски'), 'Должен быть блок Риски');

  const lines = text.split('\n');
  assert.strictEqual(lines.length, 7, 'Должно быть 7 блоков');

  console.log('✓ testGetProgressText');
}

async function testGetNextAgent() {
  // Статус in_progress → questioner
  const ctx1 = SessionContext.fromSession(createMockSession({ status: 'in_progress' }));
  const q1 = ctx1.getNextAgent();
  assert.strictEqual(q1.nextAgent, 'questioner', 'in_progress → questioner');

  // Статус completed без draft → compiler
  const ctx2 = SessionContext.fromSession(createMockSession({ status: 'completed' }));
  const q2 = ctx2.getNextAgent();
  assert.strictEqual(q2.nextAgent, 'compiler', 'completed без draft → compiler');

  // Draft без approved → controller
  const ctx3 = SessionContext.fromSession(createMockSession({
    status: 'completed',
    draft: { blocks: [] }
  }));
  const q3 = ctx3.getNextAgent();
  assert.strictEqual(q3.nextAgent, 'controller', 'draft без approved → controller');

  // Document ready → generator (нужен статус completed + quality approved)
  const ctx4 = SessionContext.fromSession(createMockSession({
    status: 'completed',
    documentReady: true,
    draft: { blocks: [] },
    qualityGate: { approved: true, issues: [], iteration: 1 }
  }));
  const q4 = ctx4.getNextAgent();
  assert.strictEqual(q4.nextAgent, 'generator', 'documentReady → generator');

  // Quality issues max iteration → generator (force accept)
  const ctx5 = SessionContext.fromSession(createMockSession({
    status: 'completed',
    draft: { blocks: [] },
    qualityGate: { approved: false, issues: [{ block: 1, issue: 'test' }], iteration: 3 }
  }));
  const q5 = ctx5.getNextAgent();
  assert.strictEqual(q5.nextAgent, 'generator',
    'max iterations → generator (force)');

  console.log('✓ testGetNextAgent');
}

async function testEndToEndContextFlow() {
  // Сквозной тест: сессия → контекст → обновление → сериализация → десериализация
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  // 1. Создаём сессию
  const session = await sm.createSession(999, { username: 'e2e_user' });
  const sessionId = session.sessionId;

  // 2. Создаём Context
  let ctx = SessionContext.fromSession(session);
  assert(ctx, 'Context создан');

  // 3. Обновляем через агента-опросчика
  ctx.update({
    answers: {
      '1.1': { L1: 'Первый ответ', depthReached: 'L1' }
    },
    currentBlock: 1,
    currentSubsection: '1.2',
    depth: 'L1',
    progress: 10
  });

  // 4. Добавляем риск
  ctx.addRisk('Риск превышения бюджета', 'business');

  // 5. Сериализуем контекст (передача агенту)
  const serialized = ctx.serialize();

  // 6. Другой агент получает контекст
  const ctx2 = SessionContext.fromJSON(serialized);
  assert.strictEqual(ctx2.sessionId, sessionId, 'ID сессии сохраняется');
  assert.strictEqual(ctx2.getAnswer('1.1'), 'Первый ответ', 'Ответ сохраняется');
  assert.strictEqual(ctx2.risks.length, 1, 'Риски сохраняются');

  // 7. Агент-составитель обновляет контекст
  ctx2.update({
    draft: {
      title: 'Бизнес-требования',
      blocks: [{ id: 1, content: 'Сформированный текст' }]
    },
    progress: 70
  });

  // 8. Агент-контролёр проверяет
  const ctx3 = SessionContext.fromJSON(ctx2.serialize());
  assert.strictEqual(ctx3.draft.blocks.length, 1, 'Черновик сохраняется');

  // 9. Маркируем готовность (без изменения статуса — SessionManager управляет файлами)
  ctx3.documentReady = true;
  ctx3.meta.completedAt = new Date().toISOString();
  ctx3.meta.updatedAt = new Date().toISOString();
  assert.strictEqual(ctx3.documentReady, true, 'documentReady = true');

  // 10. Сохраняем обратно в сессию (сохраняем статус in_progress,
  //     а завершение делаем через completeSession)
  const saveData = ctx3.toJSON();
  saveData.status = 'in_progress'; // Статус не меняем — SessionManager управляет
  await sm.updateSession(sessionId, saveData);

  // 11. Проверяем сохранённое
  const saved = await sm.loadSession(sessionId);
  assert(saved, 'Сессия загружена');
  assert.strictEqual(saved.documentReady, true, 'documentReady сохранён');
  assert.strictEqual(saved.draft.blocks.length, 1, 'Черновик сохранён');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testEndToEndContextFlow');
}

async function testCtxRejectsInvalidSession() {
  try {
    new SessionContext(null);
    assert.fail('Должен выбросить ошибку для null');
  } catch (err) {
    assert(err.message.includes('валидный объект сессии'), 'Правильное сообщение');
  }

  try {
    new SessionContext({});
    assert.fail('Должен выбросить ошибку для пустого объекта');
  } catch (err) {
    assert(err.message.includes('валидный объект сессии'), 'Правильное сообщение');
  }

  try {
    new SessionContext({ sessionId: null });
    assert.fail('Должен выбросить ошибку для null sessionId');
  } catch (err) {
    assert(err.message.includes('валидный объект сессии'), 'Правильное сообщение');
  }

  console.log('✓ testCtxRejectsInvalidSession');
}

// ==================== Run All Tests ====================

async function runTests() {
  console.log('\n=== Session Context Tests (Story 1.7) ===\n');

  const tests = [
    testCreateContextFromSession,
    testContextSerialization,
    testContextUpdate,
    testAddRisk,
    testSetDraft,
    testMarkDocumentReady,
    testGetAnswer,
    testGetAnswersByBlock,
    testGetSummary,
    testGetProgressText,
    testGetNextAgent,
    testEndToEndContextFlow,
    testCtxRejectsInvalidSession
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
