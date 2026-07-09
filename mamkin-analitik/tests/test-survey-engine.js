/**
 * Тесты Survey Engine (Story 1.6 — Автоматическое сохранение черновиков)
 *
 * Тестирует:
 *   - startSurvey() — старт опроса, первый L1-вопрос
 *   - processAnswer() — оценка глубины, L1→L2→L3, переход по подразделам
 *   - getCurrentQuestion() — текущий вопрос
 *   - getProgress() — прогресс
 *   - _evaluateDepth() — оценка глубины ответа
 *   - buildResumeCard() — Session Resume Card
 *   - needsResumeCard() — проверка паузы >30 минут
 *   - retryFailedSave() — повтор при ошибке ФС
 *   - _extractRisks() — извлечение рисков
 *   - Транзакционное сохранение (через SessionManager)
 *   - Error notification при ошибке ФС
 *
 * Mock-based: использует allowEmptyKey для crypto, временные директории.
 *
 * Depth scoring thresholds (из data/depth-config.json):
 *   0.0–0.3 → остаёмся на L1
 *   0.3–0.6 → переходим на L2 (или L2→L3)
 *   0.6–1.0 → достаточная глубина, переходим к следующему подразделу
 *
 * Depth-индикаторы для score ≥0.6: числа + причинно-следственные связи + индикаторы глубины
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');
const SessionManager = require('../lib/session-manager');
const TemplateEngine = require('../lib/template-engine');
const SurveyEngine = require('../lib/survey-engine');
const SessionContext = require('../lib/session-context');

// ==================== Test Setup ====================

/** Создаёт временную директорию для тестов */
function createTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'survey-test-'));
}

/** Создаёт конфиг для SessionManager */
function makeSessionConfig(tmpDir) {
  return {
    storagePath: tmpDir,
    allowEmptyKey: true,
    lockTimeout: 2000
  };
}

/** Путь к шаблону */
const TEMPLATE_PATH = path.resolve(__dirname, '..', 'data', 'template.json');

/** Путь к depth-config */
const DEPTH_CONFIG_PATH = path.resolve(__dirname, '..', 'data', 'depth-config.json');

/**
 * Глубокий ответ, который гарантированно набирает score ≥ 0.6:
 * - ≥ 5 предложений → 0.2
 * - содержит числа → 0.15
 * - содержит индикатор глубины (например, "конкретно") → 0.15
 * - содержит причинно-следственную связь → 0.2
 * - длина → ~0.03
 * Итого: ~0.73
 */
const DEEP_ANSWER =
  'Мы работаем над платформой для автоматизации закупок в крупной торговой сети. ' +
  'Сейчас процесс полностью ручной, менеджеры тратят по 3–4 часа в день на согласование. ' +
  'Из-за этого регулярно возникают ошибки — примерно 15% заказов уходят с неправильными позициями. ' +
  'В прошлом месяце потеряли крупного поставщика на 2 миллиона рублей. ' +
  'Потому что каждый менеджер работает в своём Excel и данные не синхронизируются. ' +
  'Конкретный пример: на прошлой неделе отгрузили не тот товар клиенту.';

/**
 * Средний ответ с фактами, но без глубины (score ~0.3–0.6):
 * - 3–4 предложения → 0.1
 * - числа есть → 0.15
 * - нет индикаторов глубины
 * - есть причинно-следственная связь → 0.2
 * Итого: ~0.47
 */
const MEDIUM_ANSWER =
  'Работаем над автоматизацией. Потери составляют 2 млн в месяц. ' +
  'Потому что процессы не настроены как надо.';

/**
 * Story 2.2 helper: processAnswer + автоматическое подтверждение рефлексии.
 * Если processAnswer возвращает reflection_needed, автоматически подтверждает.
 */
async function processWithReflection(surveyEngine, session, answer, maxIter = 5) {
  let current = await surveyEngine.processAnswer(session, answer);
  let iter = 0;
  while (current.action === 'reflection_needed' && iter < maxIter) {
    current = await surveyEngine.processAnswer(current.session, 'да');
    iter++;
  }
  return current;
}

/**
 * Story 2.2 helper: поверхностный ответ, гарантированно не проходящий _isL1DeepEnough.
 * 1 предложение, 0 фактов.
 */
const SHALLOW_L1_ANSWER = 'Да, работаем.';

/** Инициализация тестового окружения */
async function setup() {
  const tmpDir = createTempDir();
  const sessionManager = new SessionManager(makeSessionConfig(tmpDir));
  const templateEngine = new TemplateEngine();

  // Загружаем template
  templateEngine.loadSync(TEMPLATE_PATH);

  const surveyEngine = new SurveyEngine({
    sessionManager,
    templateEngine,
    depthConfigPath: DEPTH_CONFIG_PATH
  });

  return { tmpDir, sessionManager, templateEngine, surveyEngine };
}

/** Очистка после тестов */
function cleanup(tmpDir) {
  if (tmpDir && fs.existsSync(tmpDir)) {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
}

// ==================== Тесты startSurvey ====================

async function testStartSurvey() {
  const { tmpDir, sessionManager, templateEngine, surveyEngine } = await setup();
  try {
    // Создаём сессию
    const session = await sessionManager.createSession(12345, { username: 'test_user' });

    // Запускаем опрос
    const result = await surveyEngine.startSurvey(session);

    // Проверяем результат
    assert(result, 'startSurvey should return a result');
    assert(result.question, 'Should return a question');
    assert.strictEqual(typeof result.question, 'string', 'Question should be a string');
    assert(result.question.length > 0, 'Question should not be empty');

    // Проверяем, что вопрос — L1 из первого подраздела
    const firstBlock = templateEngine.getBlock(1);
    const firstSub = firstBlock.subsections[0];
    assert.strictEqual(result.question, firstSub.questions.L1,
      'Should return L1 question from first subsection');

    // Проверяем прогресс
    assert(result.progress, 'Should return progress');
    assert.strictEqual(result.progress.block, 1, 'Should be at block 1');
    assert.strictEqual(result.progress.totalBlocks, 7, 'Total blocks should be 7');
    assert.strictEqual(result.progress.subsection, '1.1', 'Should be at subsection 1.1');

    // Проверяем обновлённую сессию
    assert(result.session, 'Should return session');
    assert.strictEqual(result.session.template.block, 1);
    assert.strictEqual(result.session.template.subsection, '1.1');
    assert.strictEqual(result.session.template.depth, 'L1');

    console.log('✓ testStartSurvey');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тесты processAnswer ====================

async function testProcessAnswer_DeepResponse_MovesToNextSubsection() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Story 2.2: DEEP_ANSWER имеет ≥3 предложений → reflection_needed, затем подтверждение
    // Используем processWithReflection для авто-подтверждения
    const result = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);

    assert(result, 'processAnswer should return a result');
    assert(result.action === 'next_question', 'Should go to next subsection');
    assert(result.question, 'Should return next question');
    assert(result.session, 'Should return updated session');

    // Должен перейти к подразделу 1.2 (следующий после 1.1)
    assert(result.session.template.subsection === '1.2',
      `Should be at subsection 1.2, got ${result.session.template.subsection}`);
    assert.strictEqual(result.session.template.depth, 'L1',
      'Depth should reset to L1 for new subsection');

    // Ответ должен быть сохранён в сессии
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert(savedSession.answers['1.1'], 'Answer for 1.1 should exist');
    assert(savedSession.answers['1.1'].L1 === DEEP_ANSWER, 'L1 answer should be saved');

    console.log('✓ testProcessAnswer_DeepResponse_MovesToNextSubsection');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_ShallowResponse_GoesToL2() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Поверхностный ответ (score < 0.3) — должен перейти на L2
    const answer = 'Да, работаем.';

    const result = await surveyEngine.processAnswer(startResult.session, answer);

    assert.strictEqual(result.action, 'next_question', 'Should be next_question');
    assert(result.question, 'Should have a question');

    // Должен остаться на том же подразделе, но на L2
    assert.strictEqual(result.session.template.subsection, '1.1',
      'Should stay at subsection 1.1');
    assert.strictEqual(result.session.template.depth, 'L2',
      'Depth should move to L2');

    console.log('✓ testProcessAnswer_ShallowResponse_GoesToL2');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L2toL3() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Очень короткий ответ (score < 0.1) → L2
    let answer = 'Пока не знаю.';
    let result = await surveyEngine.processAnswer(startResult.session, answer);
    assert(result.session.template.depth === 'L2', 'Very short L1 → L2');

    // Снова короткий на L2 → L3
    answer = 'Ну, просто автоматизировать надо.';
    result = await surveyEngine.processAnswer(result.session, answer);

    assert(result.session.template.depth === 'L3',
      'Short L2 response should go to L3');
    assert(result.session.template.subsection === '1.1',
      'Should stay at same subsection');

    console.log('✓ testProcessAnswer_L2toL3');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_MediumResponse_GoesToL2() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // MEDIUM_ANSWER содержит 3 предложения + числа + причинно-следственные связи
    // → Story 2.2: _isL1DeepEnough = true (≥3 предложений) → reflection_needed
    // Только поверхностный ответ (<3 предложений, <2 фактов) идёт на L2
    const result = await surveyEngine.processAnswer(startResult.session, MEDIUM_ANSWER);

    assert(result.action === 'reflection_needed',
      `Medium answer with 3 sentences should trigger reflection, got ${result.action}`);
    assert(result.session.reflectionPending === true,
      'reflectionPending should be set');

    // Подтверждаем
    const confirmed = await surveyEngine.processAnswer(result.session, 'да');
    assert.strictEqual(confirmed.session.template.subsection, '1.2',
      `After confirmation should advance, got ${confirmed.session.template.subsection}`);

    console.log('✓ testProcessAnswer_MediumResponse_GoesToL2 (now reflection → confirm)');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_FullBlockTransition() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Story 2.2: DEEP_ANSWER на L1 → reflection_needed → подтверждение → след.подраздел
    // Используем processWithReflection для авто-подтверждения

    // Подраздел 1.1 → глубокий ответ + подтверждение → 1.2
    let result = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);
    assert(result.session.template.subsection === '1.2',
      `Expected 1.2, got ${result.session.template.subsection}`);

    // Подраздел 1.2 → глубокий ответ + подтверждение → 1.3
    result = await processWithReflection(surveyEngine, result.session, DEEP_ANSWER);
    assert.strictEqual(result.session.template.subsection, '1.3');

    // Подраздел 1.3 → глубокий ответ + подтверждение → Блок 2 (2.1)
    result = await processWithReflection(surveyEngine, result.session, DEEP_ANSWER);

    assert(result.session.template.block === 2,
      `Should be at block 2, got block ${result.session.template.block}`);
    assert.strictEqual(result.session.template.subsection, '2.1',
      `Should be at subsection 2.1, got ${result.session.template.subsection}`);
    assert.strictEqual(result.session.template.depth, 'L1');

    console.log('✓ testProcessAnswer_FullBlockTransition');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_SurveyComplete() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Story 2.2: DEEP_ANSWER на L1 → reflection → подтверждение. Используем processWithReflection
    let currentResult = startResult;
    const maxIterations = 20;

    for (let i = 0; i < maxIterations; i++) {
      if (currentResult.action === 'survey_complete') break;
      currentResult = await processWithReflection(surveyEngine, currentResult.session, DEEP_ANSWER);
    }

    assert(currentResult.action === 'survey_complete',
      `Expected survey_complete, got ${currentResult.action} after ${maxIterations} iterations`);

    console.log('✓ testProcessAnswer_SurveyComplete');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тесты getCurrentQuestion ====================

async function testGetCurrentQuestion() {
  const { tmpDir, sessionManager, surveyEngine, templateEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Получаем текущий вопрос
    const question = surveyEngine.getCurrentQuestion(startResult.session);

    assert(question, 'getCurrentQuestion should return a question');
    assert(question.question, 'Should have question text');
    assert(question.depth, 'Should have depth');
    assert(question.subsectionId, 'Should have subsection ID');
    assert(question.blockId, 'Should have block ID');

    // Проверяем, что это L1 из первого подраздела
    const firstSub = templateEngine.getBlock(1).subsections[0];
    assert.strictEqual(question.question, firstSub.questions.L1);
    assert.strictEqual(question.depth, 'L1');
    assert.strictEqual(question.subsectionId, '1.1');
    assert.strictEqual(question.blockId, 1);

    console.log('✓ testGetCurrentQuestion');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тесты getProgress ====================

async function testGetProgress() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);

    // Прогресс до старта (ещё не начат опрос, templateEngine загружен)
    const progressEmpty = surveyEngine.getProgress(session);

    // После startSurvey
    const startResult = await surveyEngine.startSurvey(session);
    const progressStart = surveyEngine.getProgress(startResult.session);

    assert.strictEqual(progressStart.block, 1);
    assert.strictEqual(progressStart.totalBlocks, 7);
    assert.strictEqual(progressStart.subsection, '1.1');
    assert.strictEqual(progressStart.depth, 'L1');
    assert.strictEqual(progressStart.completedSubsections, 0,
      'No subsections completed yet');

    // Story 2.2: DEEP_ANSWER → reflection + confirmation
    const result = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);
    const progressAfter = surveyEngine.getProgress(result.session);

    assert(progressAfter.completedSubsections === 1,
      `Expected 1 subsection completed, got ${progressAfter.completedSubsections}`);
    assert(progressAfter.percent >= 0, 'Percent should be >= 0');

    console.log('✓ testGetProgress');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тесты _evaluateDepth ====================

async function testEvaluateDepth() {
  const { surveyEngine } = await setup();

  // Сверхкороткий ответ → низкий score
  const veryShort = 'Да.';
  const shortScore = surveyEngine._evaluateDepth(veryShort);
  assert(shortScore < 0.3, `Very short answer should score < 0.3, got ${shortScore}`);

  // Средний ответ с фактами
  const medium = 'Работаем над автоматизацией закупок. Это важно, потому что процессы долгие. ' +
    'Пример: менеджеры тратят 3 часа в день на email.';
  const mediumScore = surveyEngine._evaluateDepth(medium);
  assert(mediumScore > 0.2, `Medium answer should score > 0.2, got ${mediumScore}`);

  // Глубокий ответ с цифрами, причинами и примерами
  const deep = 'Мы работаем над платформой для автоматизации закупок в крупной торговой сети. ' +
    'Сейчас процесс полностью ручной: менеджеры тратят по 3-4 часа в день на согласование заказов по email. ' +
    'Из-за этого регулярно возникают ошибки — примерно 15% заказов уходят с неправильными позициями. ' +
    'В прошлом месяце из-за такой ошибки потеряли крупного поставщика на 2 миллиона рублей. ' +
    'Коренная причина в том, что нет единой системы — каждый менеджер работает в своём Excel. ' +
    'Следовательно, данные не синхронизируются, и ошибки накапливаются.';
  const deepScore = surveyEngine._evaluateDepth(deep);
  assert(deepScore > 0.5, `Deep answer should score > 0.5, got ${deepScore}`);

  // Размытый ответ с vague-фразами
  const vague = 'Всё плохо, надо автоматизировать. Нужно улучшить, сделать удобно.';
  const vagueScore = surveyEngine._evaluateDepth(vague);
  assert(vagueScore < 0.5, `Vague answer should score < 0.5, got ${vagueScore}`);

  console.log('✓ testEvaluateDepth');
}

// ==================== Тесты buildResumeCard ====================

async function testBuildResumeCard() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Story 2.2: DEEP_ANSWER → reflection + confirmation
    const result = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);

    // Строим Resume Card
    const card = surveyEngine.buildResumeCard(result.session);

    assert(card, 'Should build a resume card');
    assert(card.text, 'Card should have text');
    assert(card.text.includes('С возвращением'), 'Card should have greeting');
    // В карточке есть "последний ответ" — проверяем часть слова
    assert(card.text.includes('ответ'), 'Card should mention answer');
    assert(card.lastAnswer, 'Should include last answer text');
    assert(card.blockInfo, 'Should have block info');

    console.log('✓ testBuildResumeCard');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тесты needsResumeCard ====================

async function testNeedsResumeCard() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);

    // Только что созданная сессия — не нужно карточки
    assert(!surveyEngine.needsResumeCard(session),
      'Fresh session should not need resume card');

    // Сессия с updatedAt = 40 минут назад — нужно
    const pastDate = new Date(Date.now() - 40 * 60 * 1000).toISOString();
    const oldSession = Object.assign({}, session, { updatedAt: pastDate });
    assert(surveyEngine.needsResumeCard(oldSession),
      'Session 40min old should need resume card');

    // Сессия с updatedAt = 25 минут назад — не нужно
    const recentDate = new Date(Date.now() - 25 * 60 * 1000).toISOString();
    const recentSession = Object.assign({}, session, { updatedAt: recentDate });
    assert(!surveyEngine.needsResumeCard(recentSession),
      'Session 25min old should NOT need resume card');

    // Сессия без updatedAt — не нужно
    assert(!surveyEngine.needsResumeCard({}));

    // null/undefined — не нужно
    assert(!surveyEngine.needsResumeCard(null));
    assert(!surveyEngine.needsResumeCard(undefined));

    console.log('✓ testNeedsResumeCard');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тесты _extractRisks ====================

async function testExtractRisks() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);

    // Ответ с рисками
    const answer = 'Есть риск, что пользователи не примут новую систему. ' +
      'Проблема в том, что команда не справится с интеграцией. ' +
      'Бюджет проекта ограничен.';

    const risks = surveyEngine._extractRisks(answer, session, '1.1');

    assert(Array.isArray(risks), 'Should return array');
    assert(risks.length >= 1, `Should extract at least one risk, got ${risks.length}`);
    assert(risks[0].text, 'Risk should have text');
    assert(risks[0].collectedAt, 'Risk should have collectedAt');
    assert(risks[0].category, 'Risk should have category');

    // Проверяем категории
    const categories = risks.map(r => r.category);
    assert(categories.includes('business') || categories.includes('adoption'),
      'Should include business or adoption risk');

    // Пустой ответ — без рисков
    const noRisks = surveyEngine._extractRisks('Всё хорошо.', session, '1.2');
    assert.strictEqual(noRisks.length, 0, 'Should not extract risks from safe answer');

    console.log('✓ testExtractRisks');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тесты retryFailedSave ====================

async function testRetryFailedSave() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);

    // Имитируем ошибку ФС — записываем в кэш
    surveyEngine._fsErrorCache.set(session.sessionId, {
      session,
      lastError: 'ENOSPC: no space left on device',
      retries: 0
    });

    // Первая попытка — должна сработать (ФС доступна)
    const result = await surveyEngine.retryFailedSave(session.sessionId);
    assert(result, 'Retry should succeed');
    assert(result.sessionId === session.sessionId, 'Should return the correct session');

    // Кэш должен быть очищен
    assert(!surveyEngine._fsErrorCache.has(session.sessionId),
      'Cache should be cleared after successful retry');

    // Несуществующий sessionId
    const noResult = await surveyEngine.retryFailedSave('nonexistent');
    assert.strictEqual(noResult, null, 'Should return null for nonexistent session');

    console.log('✓ testRetryFailedSave');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тест транзакционного сохранения ====================

async function testTransactionalSave() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Даём ответ — сохраняется через SessionManager (транзакционно)
    const result = await surveyEngine.processAnswer(startResult.session, DEEP_ANSWER);

    // Проверяем, что файл существует
    const activeDir = path.join(tmpDir, 'active');
    const files = fs.readdirSync(activeDir).filter(f => f.endsWith('.json'));
    assert(files.length > 0, 'Session file should exist');

    // Проверяем, что нет .tmp-файлов (чистота транзакционной записи)
    const tmpFiles = fs.readdirSync(activeDir).filter(f => f.includes('.tmp'));
    assert.strictEqual(tmpFiles.length, 0, 'No temp files should remain');

    // Читаем файл — проверяем, что ответ сохранён
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert(savedSession.answers['1.1'], 'Answer should be saved');
    assert(savedSession.answers['1.1'].L1 === DEEP_ANSWER, 'Answer text should match');

    console.log('✓ testTransactionalSave');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тест интеграции с session-manager ====================

async function testIntegrationWithSessionManager() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let currentSession = session;

    // Делаем startSurvey и сразу получаем обновлённый session
    const start = await surveyEngine.startSurvey(session);
    currentSession = start.session;

    // Story 2.2: DEEP_ANSWER на L1 → reflection → confirmation. Используем processWithReflection.
    const expectedSubsections = ['1.1', '1.2', '1.3'];
    const answers = [
      { text: DEEP_ANSWER, expectedSub: '1.1' },
      { text: DEEP_ANSWER, expectedSub: '1.2' }
    ];

    for (const ans of answers) {
      const result = await processWithReflection(surveyEngine, currentSession, ans.text);
      currentSession = result.session;
    }

    // Проверяем через SessionManager, что ответы сохранились
    const loadedSession = await sessionManager.getSession(currentSession.sessionId);
    assert(loadedSession, 'Session should be loadable');

    for (const ans of answers) {
      assert(loadedSession.answers[ans.expectedSub],
        `Answer for ${ans.expectedSub} should exist`);
      assert(loadedSession.answers[ans.expectedSub].L1,
        `L1 answer for ${ans.expectedSub} should exist`);
    }

    // Третий ответ должен перейти к блоку 2
    const result3 = await processWithReflection(surveyEngine, currentSession, DEEP_ANSWER);
    const loadedAfter = await sessionManager.getSession(result3.session.sessionId);
    assert(loadedAfter.answers['1.3'],
      'Answer for 1.3 should exist after third deep answer');
    assert.strictEqual(loadedAfter.template.block, 2,
      'Should be at block 2 after processing all block 1 subsections');

    console.log('✓ testIntegrationWithSessionManager');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тест ошибки ФС ====================

async function testFsErrorCache() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);

    // Симулируем ошибку ФС в кэше
    surveyEngine._fsErrorCache.set(session.sessionId, {
      session,
      lastError: 'EACCES: permission denied',
      retries: 1
    });

    // Проверяем, что при retries < MAX попытка срабатывает
    surveyEngine.MAX_FS_RETRIES = 2;
    const entryBefore = surveyEngine._fsErrorCache.get(session.sessionId);
    assert(entryBefore, 'Entry should be in cache');

    // Это будет вторая попытка, retries=1 < MAX(2), должна сработать
    const result = await surveyEngine.retryFailedSave(session.sessionId);
    assert(result, 'Retry should succeed when FS is available');
    assert(!surveyEngine._fsErrorCache.has(session.sessionId),
      'Cache should be cleared after success');

    // Тест превышения MAX попыток
    surveyEngine._fsErrorCache.set(session.sessionId, {
      session,
      lastError: 'ENOSPC: no space left on device',
      retries: 2
    });
    surveyEngine.MAX_FS_RETRIES = 2;
    const exhausted = await surveyEngine.retryFailedSave(session.sessionId);
    assert(exhausted === null, 'Should return null when max retries exceeded');
    assert(!surveyEngine._fsErrorCache.has(session.sessionId),
      'Cache should be cleared after max retries');

    console.log('✓ testFsErrorCache');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тест глубины с разными типами ответов ====================

async function testDepthScoringScenarios() {
  const { surveyEngine } = await setup();
  const evaluate = (txt) => surveyEngine._evaluateDepth(txt);

  // 1. Пустой ответ
  assert(evaluate('') < 0.1, 'Empty answer score < 0.1');
  assert(evaluate(null) < 0.1, 'Null answer score < 0.1');

  // 2. Одно слово
  const oneWord = evaluate('Да');
  assert(oneWord < 0.2, 'One-word answer score < 0.2');

  // 3. Только общие фразы (vague)
  const vague = evaluate('Всё плохо, надо сделать удобно, ну как-то автоматизировать.');
  assert(vague < 0.5, `Vague answer score < 0.5, got ${vague}`);

  // 4. С цифрами, но без причин
  const withNumbers = evaluate('У нас 500 пользователей. Система обрабатывает 1000 заказов в день. ' +
    'Время отклика 3 секунды. Средняя нагрузка 200 запросов.');
  assert(withNumbers > 0.2, `Answer with numbers score > 0.2, got ${withNumbers}`);

  // 5. С причинно-следственными связями
  const causal = evaluate('Потому что нет автоматизации. Из-за этого теряем деньги. ' +
    'В результате страдает бизнес. Причина в ручных процессах.');
  assert(causal > 0.3, `Causal answer score > 0.3, got ${causal}`);

  // 6. Полноценный ответ (всё вместе)
  const full = evaluate(DEEP_ANSWER);
  assert(full > 0.5, `Full answer score > 0.5, got ${full}`);

  // 7. Структурированный ответ (список)
  const structured = evaluate(
    '- Проблема: ручные процессы\n' +
    '- Потери: 500 тыс руб в месяц\n' +
    '- Причина: нет интеграции\n' +
    '- Решение: внедрить платформу'
  );
  assert(structured > 0.3, `Structured answer score > 0.3, got ${structured}`);

  // 8. DEEP_ANSWER должен быть ≥ 0.6 (для тестов перехода между подразделами)
  const deepScore = evaluate(DEEP_ANSWER);
  assert(deepScore >= 0.6, `DEEP_ANSWER should score >= 0.6 for reliable transitions, got ${deepScore}`);

  console.log('✓ testDepthScoringScenarios');
}

// ==================== Тесты getSessionContext (Story 2.1) ====================

async function testGetSessionContext_Basic() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Создаём SessionContext из опроса
    const ctx = surveyEngine.getSessionContext(startResult.session);

    assert(ctx, 'getSessionContext should return a context');
    assert(ctx instanceof SessionContext, 'Should be a SessionContext instance');
    assert.strictEqual(ctx.sessionId, startResult.session.sessionId,
      'Session ID should match');
    assert.strictEqual(ctx.telegramUserId, 12345,
      'Telegram user ID should match');
    assert.strictEqual(ctx.currentBlock, 1,
      'Current block should be 1');
    assert.strictEqual(ctx.currentSubsection, '1.1',
      'Current subsection should be 1.1');
    assert.strictEqual(ctx.depth, 'L1',
      'Depth should be L1');
    assert.strictEqual(ctx.status, 'in_progress',
      'Status should be in_progress');

    // Проверяем, что answers пусты (ещё нет ответов)
    assert.strictEqual(ctx.getAnsweredCount(), 0,
      'No answers yet');
    assert.strictEqual(ctx.risks.length, 0,
      'No risks yet');

    console.log('✓ testGetSessionContext_Basic');
  } finally {
    cleanup(tmpDir);
  }
}

async function testGetSessionContext_WithAnswers() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Даём глубокий ответ
    const result1 = await surveyEngine.processAnswer(startResult.session, DEEP_ANSWER);

    // Создаём SessionContext после ответа
    const ctx = surveyEngine.getSessionContext(result1.session);

    assert(ctx, 'Should return context');
    assert(ctx.getAnsweredCount() >= 1,
      `Should have at least 1 answer, got ${ctx.getAnsweredCount()}`);

    // Проверяем, что ответ сохранён в контексте
    const answer = ctx.getAnswer('1.1');
    assert(answer, 'Should have answer for 1.1');
    assert.strictEqual(answer, DEEP_ANSWER,
      'Answer text should match');

    // Проверяем прогресс
    assert(ctx.progress > 0,
      `Progress should be > 0, got ${ctx.progress}`);

    // Проверяем сериализацию
    const json = ctx.toJSON();
    assert(json.sessionId, 'JSON should have sessionId');
    assert(json.answers, 'JSON should have answers');
    assert(json.answers['1.1'], 'JSON should have answer for 1.1');

    // Проверяем десериализацию
    const serialized = ctx.serialize();
    const deserialized = SessionContext.fromJSON(serialized);
    assert(deserialized instanceof SessionContext,
      'Deserialized should be SessionContext');
    assert.strictEqual(deserialized.sessionId, ctx.sessionId,
      'Deserialized sessionId should match');

    console.log('✓ testGetSessionContext_WithAnswers');
  } finally {
    cleanup(tmpDir);
  }
}

async function testGetSessionContext_WithRisks() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Ответ с рисками
    const riskyAnswer = 'Есть риск, что пользователи не примут новую систему. ' +
      'Проблема в том, что команда не справится с интеграцией. ' +
      'Бюджет проекта ограничен.';

    const result = await surveyEngine.processAnswer(startResult.session, riskyAnswer);
    const ctx = surveyEngine.getSessionContext(result.session);

    // Должны быть риски
    assert(ctx.risks.length > 0,
      `Should have risks, got ${ctx.risks.length}`);

    // Проверяем категории рисков
    for (const risk of ctx.risks) {
      assert(risk.text, 'Risk should have text');
      assert(risk.category, 'Risk should have category');
      assert(risk.collectedAt, 'Risk should have collectedAt');
    }

    console.log('✓ testGetSessionContext_WithRisks');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Тесты allSectionsComplete (Story 2.1) ====================

async function testAllSectionsComplete_FalseInitially() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);

    // Только что созданная сессия — не завершена
    const complete = surveyEngine.allSectionsComplete(session);
    assert.strictEqual(complete, false,
      'Fresh session should not be complete');

    console.log('✓ testAllSectionsComplete_FalseInitially');
  } finally {
    cleanup(tmpDir);
  }
}

async function testAllSectionsComplete_AfterStart() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // После старта — ещё не завершено
    const complete = surveyEngine.allSectionsComplete(startResult.session);
    assert.strictEqual(complete, false,
      'After start, survey should not be complete');

    console.log('✓ testAllSectionsComplete_AfterStart');
  } finally {
    cleanup(tmpDir);
  }
}

async function testAllSectionsComplete_AfterPartialProgress() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let currentResult = await surveyEngine.startSurvey(session);

    // Проходим 2 подраздела из 15
    currentResult = await surveyEngine.processAnswer(currentResult.session, DEEP_ANSWER); // → 1.2
    currentResult = await surveyEngine.processAnswer(currentResult.session, DEEP_ANSWER); // → 1.3

    const complete = surveyEngine.allSectionsComplete(currentResult.session);
    assert.strictEqual(complete, false,
      'After 2 subsections, survey should not be complete');

    console.log('✓ testAllSectionsComplete_AfterPartialProgress');
  } finally {
    cleanup(tmpDir);
  }
}

async function testAllSectionsComplete_FullSurvey() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let currentResult = await surveyEngine.startSurvey(session);

    // Story 2.2: DEEP_ANSWER на L1 → reflection → confirmation. Используем processWithReflection.
    // 7 блоков = 15 подразделов, достаточно 20 итераций
    const maxIterations = 20;
    for (let i = 0; i < maxIterations; i++) {
      if (currentResult.action === 'survey_complete') break;
      currentResult = await processWithReflection(surveyEngine, currentResult.session, DEEP_ANSWER);
    }

    assert(currentResult.action === 'survey_complete',
      `Should reach survey_complete, got ${currentResult.action}`);

    const complete = surveyEngine.allSectionsComplete(currentResult.session);
    assert.strictEqual(complete, true,
      'After full survey, allSectionsComplete should be true');

    console.log('✓ testAllSectionsComplete_FullSurvey');
  } finally {
    cleanup(tmpDir);
  }
}

async function testAllSectionsComplete_NullSession() {
  const { surveyEngine } = await setup();

  assert.strictEqual(surveyEngine.allSectionsComplete(null), false,
    'Null session should return false');
  assert.strictEqual(surveyEngine.allSectionsComplete(undefined), false,
    'Undefined session should return false');
  assert.strictEqual(surveyEngine.allSectionsComplete({}), false,
    'Empty object session should return false');

  console.log('✓ testAllSectionsComplete_NullSession');
}

// ==================== Тесты signalCompletion (Story 2.1) ====================

async function testSignalCompletion_ReturnsMessageAndContext() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let currentResult = await surveyEngine.startSurvey(session);

    // Story 2.2: DEEP_ANSWER → reflection + confirmation через processWithReflection
    const maxIterations = 20;
    for (let i = 0; i < maxIterations; i++) {
      if (currentResult.action === 'survey_complete') break;
      currentResult = await processWithReflection(surveyEngine, currentResult.session, DEEP_ANSWER);
    }

    // Вызываем signalCompletion
    const result = await surveyEngine.signalCompletion(currentResult.session);

    assert(result, 'signalCompletion should return a result');
    assert(result.message, 'Should have a message');
    assert(typeof result.message === 'string', 'Message should be a string');
    assert(result.message.length > 0, 'Message should not be empty');

    // Проверяем, что сообщение содержит ключевые фразы
    assert(result.message.includes('заверш'),
      'Message should mention completion');
    assert(result.message.includes('составителю'),
      'Message should mention passing to compiler');

    console.log('✓ testSignalCompletion_ReturnsMessageAndContext');
  } finally {
    cleanup(tmpDir);
  }
}

async function testSignalCompletion_ReturnsSessionContext() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let currentResult = await surveyEngine.startSurvey(session);

    // Story 2.2: DEEP_ANSWER → reflection + confirmation через processWithReflection
    const maxIterations = 20;
    for (let i = 0; i < maxIterations; i++) {
      if (currentResult.action === 'survey_complete') break;
      currentResult = await processWithReflection(surveyEngine, currentResult.session, DEEP_ANSWER);
    }

    const result = await surveyEngine.signalCompletion(currentResult.session);

    // Проверяем, что контекст — валидный SessionContext
    const ctx = result.context;
    assert(ctx, 'Should have a context');
    assert(ctx instanceof SessionContext, 'Context should be SessionContext');
    assert.strictEqual(ctx.status, 'completed',
      'Status should be completed');
    assert.strictEqual(ctx.progress, 100,
      'Progress should be 100%');
    assert(ctx.meta.completedAt, 'Should have completedAt timestamp');

    // Все ответы должны быть в контексте
    const answeredCount = ctx.getAnsweredCount();
    assert(answeredCount > 0,
      `Should have answers, got ${answeredCount}`);

    // Должна быть возможность передать JSON следующему агенту
    const json = ctx.toJSON();
    assert(json.sessionId, 'JSON should have sessionId');
    assert(json.answers, 'JSON should have answers');
    assert.deepStrictEqual(json.status, 'completed',
      'JSON status should be completed');

    console.log('✓ testSignalCompletion_ReturnsSessionContext');
  } finally {
    cleanup(tmpDir);
  }
}

async function testSignalCompletion_SetsSessionCompleted() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let currentResult = await surveyEngine.startSurvey(session);

    // Проходим все блоки
    const maxIterations = 20;
    for (let i = 0; i < maxIterations; i++) {
      if (currentResult.action === 'survey_complete') break;
      currentResult = await surveyEngine.processAnswer(currentResult.session, DEEP_ANSWER);
    }

    // Вызываем signalCompletion
    const result = await surveyEngine.signalCompletion(currentResult.session);

    // Проверяем, что статус в SessionContext изменился
    assert(result.context.status === 'completed',
      'Context status should be completed, got ' + result.context.status);
    assert(result.context.meta.completedAt,
      'Context should have completedAt timestamp');

    // Проверяем, что сессия сохранена (файл существует)
    const savedSession = await sessionManager.getSession(result.context.sessionId);
    assert(savedSession, 'Session should be loadable from storage');

    // Статус в файле остаётся in_progress (SessionContext хранит 'completed')
    // Файл остаётся в active/ до вызова SessionManager.completeSession()
    assert(!savedSession.completedAt || savedSession.status === 'in_progress',
      'Session file stays in active/ until full pipeline completes');

    // Проверяем, что контекст можно сериализовать для передачи следующему агенту
    const serialized = result.context.serialize();
    const parsed = JSON.parse(serialized);
    assert.strictEqual(parsed.status, 'completed',
      'Serialized context should have completed status');

    console.log('✓ testSignalCompletion_SetsSessionCompleted');
  } finally {
    cleanup(tmpDir);
  }
}

async function testSignalCompletion_ThrowsOnNull() {
  const { surveyEngine } = await setup();

  try {
    await surveyEngine.signalCompletion(null);
    assert(false, 'Should have thrown on null session');
  } catch (err) {
    assert(err.message.includes('сессия'),
      'Error should mention session');
  }

  console.log('✓ testSignalCompletion_ThrowsOnNull');
}

// ==================== Тест интеграции: полный цикл опроса → SessionContext → signalCompletion ====================

async function testFullSurveyPipelineWithContext() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);

    // 1. Старт опроса
    const startResult = await surveyEngine.startSurvey(session);
    assert(startResult, 'Should start survey');

    // Story 2.2: DEEP_ANSWER → reflection + confirmation через processWithReflection
    let currentResult = startResult;
    const maxIterations = 20;
    for (let i = 0; i < maxIterations; i++) {
      if (currentResult.action === 'survey_complete') break;
      currentResult = await processWithReflection(surveyEngine, currentResult.session, DEEP_ANSWER);
    }

    assert.strictEqual(currentResult.action, 'survey_complete',
      'Survey should complete');

    // 3. Проверяем allSectionsComplete
    assert(surveyEngine.allSectionsComplete(currentResult.session),
      'All sections should be complete');

    // 4. Получаем SessionContext
    const ctx = surveyEngine.getSessionContext(currentResult.session);
    assert(ctx, 'SessionContext should be created');
    assert(ctx.getAnsweredCount() > 0, 'Should have answers in context');

    // 5. Сигнализируем завершение
    const completion = await surveyEngine.signalCompletion(currentResult.session);
    assert(completion.message, 'Completion message should exist');
    assert(completion.context, 'Completion context should exist');
    assert.strictEqual(completion.context.status, 'completed',
      'Context should be completed');

    // 6. Проверяем, что контекст можно сериализовать для передачи агенту-составителю
    const serialized = completion.context.serialize();
    assert(typeof serialized === 'string', 'Serialized should be a string');

    const parsed = JSON.parse(serialized);
    assert(parsed.sessionId, 'Parsed should have sessionId');
    assert(parsed.answers, 'Parsed should have answers');
    assert(parsed.risks !== undefined, 'Parsed should have risks');
    assert(parsed.status === 'completed', 'Parsed status should be completed');

    console.log('✓ testFullSurveyPipelineWithContext');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Запуск всех тестов ====================



// ==================== Story 2.6: Return to earlier blocks ====================

async function testReturnToBlock() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // First answer some questions in block 1
    let current = startResult;
    current = await processWithReflection(surveyEngine, current.session, DEEP_ANSWER);
    current = await processWithReflection(surveyEngine, current.session, DEEP_ANSWER);

    // Now navigate to block 2
    const result = await surveyEngine.returnToBlock(current.session, 2);

    assert(result, 'returnToBlock should return a result');
    assert(result.question, 'Should return a question');
    assert(result.session.template.block === 2,
      `Should be at block 2, got ${result.session.template.block}`);
    assert(result.session.template.subsection === '2.1',
      `Should be at subsection 2.1, got ${result.session.template.subsection}`);
    assert(result.session.template.depth === 'L1',
      'Depth should be L1 after return');
    assert(result.blockName, 'Should have block name');
    assert(result.confirmationText, 'Should have confirmation text');
    assert(result.confirmationText.includes('Вернуться к блоку 2'),
      'Confirmation should mention block 2');

    // Previous answers from block 1 should be preserved
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert(savedSession.answers['1.1'], 'Answer for 1.1 should be preserved');
    assert(savedSession.answers['1.2'], 'Answer for 1.2 should be preserved');

    console.log('✓ testReturnToBlock');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReturnToBlock_InvalidBlock() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    try {
      await surveyEngine.returnToBlock(startResult.session, 0);
      assert(false, 'Should throw for block 0');
    } catch (err) {
      assert(err.message.includes('не найден'), 'Error should mention block not found');
    }

    try {
      await surveyEngine.returnToBlock(startResult.session, 99);
      assert(false, 'Should throw for block 99');
    } catch (err) {
      assert(err.message.includes('не найден'), 'Error should mention block not found');
    }

    console.log('✓ testReturnToBlock_InvalidBlock');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReturnToPrevious() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Answer first subsection
    let current = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);
    assert.strictEqual(current.session.template.subsection, '1.2',
      'Should be at 1.2 after answering 1.1');

    // Navigate back
    const result = await surveyEngine.returnToPrevious(current.session);

    assert(result, 'returnToPrevious should return a result');
    assert(result.previousSubsection, 'Should find previous subsection');
    assert.strictEqual(result.previousSubsection.fullKey, '1.1',
      `Previous should be 1.1, got ${result.previousSubsection.fullKey}`);
    assert(result.confirmationText, 'Should have confirmation text');
    assert(result.confirmationText.includes('Вернуться к подразделу 1.1'),
      'Confirmation should mention subsection 1.1');

    console.log('✓ testReturnToPrevious');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReturnToPrevious_AtStart() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // At the very first subsection, no previous available
    const result = await surveyEngine.returnToPrevious(startResult.session);

    assert(result, 'returnToPrevious should return a result');
    assert.strictEqual(result.previousSubsection, null,
      'Should not have previous subsection at start');
    assert(result.confirmationText.includes('начале опроса'),
      'Should say already at start');

    console.log('✓ testReturnToPrevious_AtStart');
  } finally {
    cleanup(tmpDir);
  }
}

async function testExecuteReturnToSubsection() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Answer first two subsections
    let current = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);
    assert.strictEqual(current.session.template.subsection, '1.2');

    // Execute return to subsection 1.1
    const subsection = { blockId: 1, fullKey: '1.1', name: 'Контекст инициативы' };
    const result = await surveyEngine.executeReturnToSubsection(current.session, subsection);

    assert(result, 'executeReturnToSubsection should return a result');
    assert(result.question, 'Should return a question');
    assert.strictEqual(result.session.template.block, 1,
      `Should be at block 1, got ${result.session.template.block}`);
    assert.strictEqual(result.session.template.subsection, '1.1',
      `Should be at subsection 1.1, got ${result.session.template.subsection}`);
    assert(result.previousAnswer, 'Should have previous answer');

    console.log('✓ testExecuteReturnToSubsection');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReturnToBlockPreservesAnswers() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Answer all of block 1
    let current = startResult;
    for (let i = 0; i < 3; i++) {
      current = await processWithReflection(surveyEngine, current.session, DEEP_ANSWER);
    }
    assert.strictEqual(current.session.template.block, 2,
      'Should be at block 2 after completing block 1');

    // Navigate back to block 1
    const result = await surveyEngine.returnToBlock(current.session, 1);

    assert(result.previousAnswers, 'Should have previous answers');
    assert(Object.keys(result.previousAnswers).length === 3,
      `Should have 3 previous answers, got ${Object.keys(result.previousAnswers).length}`);

    // Verify answers are preserved in storage
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert(savedSession.answers['1.1'].L1 === DEEP_ANSWER,
      'Answer for 1.1 should be preserved');
    assert(savedSession.answers['1.2'].L1 === DEEP_ANSWER,
      'Answer for 1.2 should be preserved');
    assert(savedSession.answers['1.3'].L1 === DEEP_ANSWER,
      'Answer for 1.3 should be preserved');

    console.log('✓ testReturnToBlockPreservesAnswers');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Story 2.7: Conversational UX Components ====================

async function testBuildProgressMessage() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    const progress = surveyEngine.getProgress(startResult.session);
    const msg = surveyEngine.buildProgressMessage(progress);

    assert(msg, 'buildProgressMessage should return a string');
    assert(msg.length > 0, 'Message should not be empty');
    assert(msg.includes('Прогресс'), 'Should mention progress');
    assert(msg.includes('Блок 1'), 'Should mention block 1');
    assert(msg.includes('0%'), 'Progress at 0% at start');

    // After answering one subsection
    const result = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);
    const progress2 = surveyEngine.getProgress(result.session);
    const msg2 = surveyEngine.buildProgressMessage(progress2);

    assert(msg2, 'Should return message after progress');
    assert(progress2.completedSubsections >= 1,
      `Should have at least 1 completed subsection, got ${progress2.completedSubsections}`);

    console.log('✓ testBuildProgressMessage');
  } finally {
    cleanup(tmpDir);
  }
}

async function testBuildDepthIndicator() {
  const { surveyEngine } = await setup();

  // L1 → L2
  const l1tol2 = surveyEngine.buildDepthIndicator('L1', 'L2');
  assert(l1tol2, 'Should return string');
  assert(l1tol2.includes('L1'), 'Should mention L1');
  assert(l1tol2.includes('L2'), 'Should mention L2');
  assert(l1tol2.includes('🔍'), 'Should have magnifier emoji');

  // L2 → L3
  const l2tol3 = surveyEngine.buildDepthIndicator('L2', 'L3');
  assert(l2tol3.includes('L3'), 'Should mention L3');
  assert(l2tol3.includes('корневой'), 'Should mention root level');

  // Empty input
  assert.strictEqual(surveyEngine.buildDepthIndicator('', 'L2'), '',
    'Empty from should return empty');
  assert.strictEqual(surveyEngine.buildDepthIndicator(null, 'L2'), '',
    'Null from should return empty');

  console.log('✓ testBuildDepthIndicator');
}

async function testBuildReflection() {
  const { surveyEngine } = await setup();

  // Normal answer
  const answer = 'Мы работаем над платформой для автоматизации закупок.';
  const reflection = surveyEngine.buildReflection(answer);
  assert(reflection, 'Should return reflection');
  assert(reflection.includes('Вы упомянули'), 'Should mention "Вы упомянули"');
  assert(reflection.includes('💭'), 'Should have thought emoji');

  // Short answer - no reflection
  const shortReflection = surveyEngine.buildReflection('Да.');
  assert.strictEqual(shortReflection, null,
    'Short answer should return null');

  // With cross-reference
  const allAnswers = {
    '2.1': { L1: 'Хотим автоматизировать закупки и снизить затраты' },
    '2.2': { L1: 'Критерии успеха: снижение времени обработки' }
  };
  const crossReflection = surveyEngine.buildReflection(
    'Автоматизация закупок даст нам сокращение затрат на 20%',
    allAnswers
  );
  assert(crossReflection, 'Should return cross-reference reflection');
  assert(crossReflection.includes('упоминали'), 'Might include cross-reference');

  // Short form
  const shortForm = surveyEngine.buildReflection(answer, null, { short: true });
  assert(shortForm.includes('Упомянуто'), 'Short form should say "Упомянуто"');

  console.log('✓ testBuildReflection');
}

async function testBuildQuestion() {
  const { surveyEngine } = await setup();

  // L1 question
  const l1 = surveyEngine.buildQuestion('Расскажите о проекте.', 'L1');
  assert(l1, 'Should return formatted L1 question');
  assert(l1.includes('Расскажите'), 'Should contain the question');

  // L2 question with context
  const l2 = surveyEngine.buildQuestion('Уточните детали.', 'L2', {
    previousAnswer: 'Мы автоматизируем закупки'
  });
  assert(l2, 'Should return formatted L2 question');
  assert(l2.includes('Уточним'), 'L2 should say "Уточним"');
  assert(l2.includes('🔍'), 'L2 should have magnifier');

  // L3 question
  const l3 = surveyEngine.buildQuestion('Доберитесь до сути.', 'L3');
  assert(l3.includes('добраться до сути'), 'L3 should mention root cause');

  // Empty question
  assert.strictEqual(surveyEngine.buildQuestion('', 'L1'), '',
    'Empty question should return empty');

  console.log('✓ testBuildQuestion');
}

async function testBuildQualityFeedback() {
  const { surveyEngine } = await setup();

  // Deep answer (score >= 0.6)
  const deepFeedback = surveyEngine.buildQualityFeedback(DEEP_ANSWER, 0.75);
  assert(deepFeedback, 'Should return feedback for deep answer');
  assert(deepFeedback.includes('Спасибо'), 'Should say thanks');

  // Medium answer (score 0.3-0.6)
  const mediumFeedback = surveyEngine.buildQualityFeedback(MEDIUM_ANSWER, 0.45);
  assert(mediumFeedback, 'Should return feedback for medium answer');

  // Shallow answer (score < 0.3)
  const shallowFeedback = surveyEngine.buildQualityFeedback(SHALLOW_L1_ANSWER, 0.15);
  assert(shallowFeedback, 'Should return feedback for shallow answer');

  // Null/empty
  assert.strictEqual(surveyEngine.buildQualityFeedback('', 0.5), null,
    'Empty answer should return null');
  assert.strictEqual(surveyEngine.buildQualityFeedback('test', null), null,
    'Null score should return null');

  console.log('✓ testBuildQualityFeedback');
}

async function testBuildSessionResumeCard() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Resume card for fresh session
    const card = surveyEngine.buildSessionResumeCard(session);
    assert(card, 'Should return resume card');
    assert(card.text.includes('С возвращением'), 'Should have greeting');
    assert(card.text.includes('Прогресс'), 'Should mention progress');
    assert(card.blockInfo, 'Should have block info');

    // After some progress
    const result = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);
    const card2 = surveyEngine.buildSessionResumeCard(result.session);
    assert(card2.lastAnswer, 'Should have last answer after progress');
    assert(card2.progressMessage, 'Should have progress message');

    // Null session
    const nullCard = surveyEngine.buildSessionResumeCard(null);
    assert.strictEqual(nullCard.text, '', 'Null session should return empty text');

    console.log('✓ testBuildSessionResumeCard');
  } finally {
    cleanup(tmpDir);
  }
}

async function testUXComponentsIntegration() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Test full message composition using UX components
    const progress = surveyEngine.getProgress(startResult.session);
    const progressMsg = surveyEngine.buildProgressMessage(progress);
    const question = surveyEngine.getCurrentQuestion(startResult.session);
    const formattedQuestion = surveyEngine.buildQuestion(question.question, question.depth);

    // Compose a full UX message
    const fullMessage = [
      progressMsg,
      '',
      formattedQuestion
    ].join('\n');

    assert(fullMessage.includes('Прогресс'), 'Full message should have progress');
    assert(fullMessage.includes(question.question), 'Full message should have question');

    // Answer and test quality feedback
    const result = await surveyEngine.processAnswer(startResult.session, DEEP_ANSWER);
    const score = surveyEngine._evaluateDepth(DEEP_ANSWER);
    const feedback = surveyEngine.buildQualityFeedback(DEEP_ANSWER, score);

    if (feedback) {
      assert(typeof feedback === 'string', 'Feedback should be a string');
    }

    console.log('✓ testUXComponentsIntegration');
  } finally {
    cleanup(tmpDir);
  }
}


async function runAllTests() {
  const tests = [
    testStartSurvey,
    testProcessAnswer_DeepResponse_MovesToNextSubsection,
    testProcessAnswer_ShallowResponse_GoesToL2,
    testProcessAnswer_L2toL3,
    testProcessAnswer_MediumResponse_GoesToL2,
    testProcessAnswer_FullBlockTransition,
    testProcessAnswer_SurveyComplete,
    testGetCurrentQuestion,
    testGetProgress,
    testEvaluateDepth,
    testBuildResumeCard,
    testNeedsResumeCard,
    testExtractRisks,
    testRetryFailedSave,
    testTransactionalSave,
    testIntegrationWithSessionManager,
    testFsErrorCache,
    testDepthScoringScenarios,
    // Story 2.1 — Session Context integration
    testGetSessionContext_Basic,
    testGetSessionContext_WithAnswers,
    testGetSessionContext_WithRisks,
    testAllSectionsComplete_FalseInitially,
    testAllSectionsComplete_AfterStart,
    testAllSectionsComplete_AfterPartialProgress,
    testAllSectionsComplete_FullSurvey,
    testAllSectionsComplete_NullSession,
    testSignalCompletion_ReturnsMessageAndContext,
    testSignalCompletion_ReturnsSessionContext,
    testSignalCompletion_SetsSessionCompleted,
    testSignalCompletion_ThrowsOnNull,
    testFullSurveyPipelineWithContext,
    // Story 2.6: Return to earlier blocks
    testReturnToBlock,
    testReturnToBlock_InvalidBlock,
    testReturnToPrevious,
    testReturnToPrevious_AtStart,
    testExecuteReturnToSubsection,
    testReturnToBlockPreservesAnswers,
    // Story 2.7: Conversational UX Components
    testBuildProgressMessage,
    testBuildDepthIndicator,
    testBuildReflection,
    testBuildQuestion,
    testBuildQualityFeedback,
    testBuildSessionResumeCard,
    testUXComponentsIntegration
  ];

  let passed = 0;
  let failed = 0;

  console.log('\n=== Survey Engine Tests (Story 1.6) ===\n');

  for (const test of tests) {
    try {
      await test();
      passed++;
    } catch (err) {
      console.error(`✗ ${test.name}: FAILED`);
      console.error(`  ${err.message}`);
      if (err.stack) {
        console.error(`  ${err.stack.split('\n').slice(1, 4).join('\n  ')}`);
      }
      failed++;
    }
  }

  const total = passed + failed;
  console.log(`\n=== Results: ${passed}/${total} passed, ${failed} failed ===\n`);

  return { passed, failed, total };
}

// Запуск
if (require.main === module) {
  runAllTests().then(({ passed, failed }) => {
    process.exit(failed > 0 ? 1 : 0);
  });
}

module.exports = { runAllTests };
