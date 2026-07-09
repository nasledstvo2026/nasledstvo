/**
 * Тесты L1/L2/L3 глубины, Reflection Message, подтверждения (Story 2.2, Story 2.3)
 *
 * Тестирует:
 *   - _isL1DeepEnough() — бинарная оценка: ≥3 предложений или ≥2 фактов
 *   - buildReflection() — формирование сообщения-рефлексии
 *   - processAnswer() — L1 развёрнутый → reflection_needed, L1 поверхностный → L2
 *   - _handleReflectionConfirm() — подтверждение → переход, исправление → оценка
 *   - Тональность «Коуч / фасилитатор» через структуру ответов
 *   - Фиксация depthReached: "L1" после подтверждения
 *   - Полный цикл: L1 вопрос → ответ → reflection → подтверждение → следующий подраздел
 *
 * L2 (Story 2.3):
 *   - _formatL2Question() — форматирование: префикс причины + 🔍 + контекстная адаптация
 *   - _extractKeyPhrase() — извлечение ключевой фразы из ответа
 *   - processAnswer() — L2 поверхностный → L2 вопрос с форматированием
 *   - L2 развёрнутый → depthReached: "L2" → след. подраздел
 *   - L2 поверхностный → L3
 *   - Контекстная привязка L2 к предыдущему ответу
 *   - _handleReflectionConfirm → shallow correction → L2 с форматированием
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');
const SessionManager = require('../lib/session-manager');
const TemplateEngine = require('../lib/template-engine');
const SurveyEngine = require('../lib/survey-engine');

// ==================== Test Setup ====================

/** Создаёт временную директорию для тестов */
function createTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'depth-tests-'));
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
const DEPTH_CONFIG_PATH = path.resolve(__dirname, '..', 'data', 'depth-config.json');

/**
 * Развёрнутый L1-ответ: ≥3 предложений, содержит факты.
 * Должен проходить _isL1DeepEnough().
 */
const DEEP_L1_ANSWER =
  'Мы работаем над платформой для автоматизации закупок ' +
  'в крупной торговой сети. Сейчас процесс полностью ручной, ' +
  'менеджеры тратят по 3–4 часа в день на согласование. ' +
  'Из-за этого выходят ошибки — примерно 15% заказов с неправильными позициями.';

/**
 * Минимальный развёрнутый ответ: ровно 3 предложения, без цифр.
 * Должен проходить _isL1DeepEnough() по критерию ≥3 предложений.
 */
const THREE_SENTENCE_ANSWER =
  'Мы автоматизируем процесс закупок. Сейчас всё делается вручную через Excel. ' +
  'Это отнимает много времени и создаёт ошибки.';

/**
 * Короткий ответ с 2 фактами: цифра + причинно-следственная связь.
 * Должен проходить _isL1DeepEnough() по критерию ≥2 фактов.
 */
const TWO_FACT_ANSWER =
  'Автоматизируем закупки в сети из 50 магазинов. Потому что сейчас хаос.';

/**
 * Поверхностный ответ: 1 предложение, без фактов.
 * НЕ должен проходить _isL1DeepEnough().
 */
const SHALLOW_ANSWER = 'Работаем над автоматизацией.';

/**
 * Очень короткий ответ.
 * НЕ должен проходить _isL1DeepEnough().
 */
const VERY_SHORT_ANSWER = 'Да.';

/**
 * Развёрнутый L2-ответ: ≥3 предложений, цифры, причинно-следственные связи.
 * Должен иметь score ≥ 0.6 (L3_THRESHOLD) — достаточно для фиксации на L2.
 */
const DEEP_L2_ANSWER =
  'Мы автоматизируем процесс закупок для сети из 200 магазинов. ' +
  'Сейчас менеджеры тратят по 4 часа в день на ручное согласование заказов по email. ' +
  'Из-за этого примерно 12% заказов уходят с ошибками. ' +
  'В прошлом месяце из-за такой ошибки потеряли поставщика на 1.5 млн рублей. ' +
  'Потому что нет единой системы и данные не синхронизируются между отделами.';

/**
 * Поверхностный L2-ответ: 1 предложение, без фактов.
 * Должен иметь score < 0.6 — недостаточно для фиксации.
 */
const SHALLOW_L2_ANSWER = 'Ну, просто надо автоматизировать закупки, чтобы было удобно.';

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

// ==================== L1 Tests: _isL1DeepEnough ====================

async function testIsL1DeepEnough_DeepAnswer() {
  const { surveyEngine } = await setup();

  const result = surveyEngine._isL1DeepEnough(DEEP_L1_ANSWER);
  assert.strictEqual(result, true,
    `DEEP_L1_ANSWER should be deep enough for L1, got ${result}`);

  console.log('✓ testIsL1DeepEnough_DeepAnswer');
}

async function testIsL1DeepEnough_ThreeSentences() {
  const { surveyEngine } = await setup();

  const result = surveyEngine._isL1DeepEnough(THREE_SENTENCE_ANSWER);
  assert.strictEqual(result, true,
    'Three-sentence answer should be deep enough for L1');

  console.log('✓ testIsL1DeepEnough_ThreeSentences');
}

async function testIsL1DeepEnough_TwoFacts() {
  const { surveyEngine } = await setup();

  const result = surveyEngine._isL1DeepEnough(TWO_FACT_ANSWER);
  assert.strictEqual(result, true,
    'Two-fact answer should be deep enough for L1');

  console.log('✓ testIsL1DeepEnough_TwoFacts');
}

async function testIsL1DeepEnough_Shallow() {
  const { surveyEngine } = await setup();

  const resultShallow = surveyEngine._isL1DeepEnough(SHALLOW_ANSWER);
  assert.strictEqual(resultShallow, false,
    'Shallow answer should NOT be deep enough for L1');

  const resultVeryShort = surveyEngine._isL1DeepEnough(VERY_SHORT_ANSWER);
  assert.strictEqual(resultVeryShort, false,
    'Very short answer should NOT be deep enough for L1');

  const resultEmpty = surveyEngine._isL1DeepEnough('');
  assert.strictEqual(resultEmpty, false,
    'Empty answer should NOT be deep enough for L1');

  const resultNull = surveyEngine._isL1DeepEnough(null);
  assert.strictEqual(resultNull, false,
    'Null answer should NOT be deep enough for L1');

  console.log('✓ testIsL1DeepEnough_Shallow');
}

// ==================== L1 Tests: buildReflection ====================

async function testBuildReflection_Basic() {
  const { surveyEngine } = await setup();

  const reflection = surveyEngine.buildReflection(DEEP_L1_ANSWER);

  // Проверяем формат
  assert(reflection.startsWith('💡 Вы сказали:'),
    `Reflection should start with emoji + text, got: "${reflection.slice(0, 30)}..."`);
  assert(reflection.includes('Я правильно понял?'),
    `Reflection should end with confirmation question, got: "${reflection.slice(-30)}..."`);
  assert(reflection.includes('"'),
    'Reflection should contain quoted text');

  // Цитата не пустая
  const quoteStart = reflection.indexOf('"') + 1;
  const quoteEnd = reflection.indexOf('"', quoteStart);
  const quote = reflection.slice(quoteStart, quoteEnd);
  assert(quote.length > 10, 'Quote should be meaningful');

  console.log('✓ testBuildReflection_Basic');
}

async function testBuildReflection_QuoteLength() {
  const { surveyEngine } = await setup();

  // Очень длинный ответ
  const longAnswer = Array(20).fill(
    'Это предложение номер раз показывает детали проекта по автоматизации закупок.'
  ).join('. ');

  const reflection = surveyEngine.buildReflection(longAnswer);

  // Цитата не должна превышать ~150 символов
  const quoteStart = reflection.indexOf('"') + 1;
  const quoteEnd = reflection.indexOf('"', quoteStart);
  const quote = reflection.slice(quoteStart, quoteEnd);
  assert(quote.length <= 130,
    `Quote should be limited, got ${quote.length} chars: ${quote.slice(0, 50)}...`);

  console.log('✓ testBuildReflection_QuoteLength');
}

async function testBuildReflection_EmptyAnswer() {
  const { surveyEngine } = await setup();

  assert.strictEqual(surveyEngine.buildReflection(''), '',
    'Empty answer should return empty string');
  assert.strictEqual(surveyEngine.buildReflection(null), '',
    'Null answer should return empty string');
  assert.strictEqual(surveyEngine.buildReflection('   '), '',
    'Whitespace answer should return empty string');

  console.log('✓ testBuildReflection_EmptyAnswer');
}

// ==================== L1 Tests: processAnswer — L1 глубина ====================

async function testProcessAnswer_L1Deep_ReturnsReflection() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Развёрнутый L1-ответ → должен вернуть reflection_needed
    const result = await surveyEngine.processAnswer(startResult.session, DEEP_L1_ANSWER);

    assert.strictEqual(result.action, 'reflection_needed',
      `Should return reflection_needed, got ${result.action}`);

    // Проверяем, что вернулось сообщение рефлексии
    assert(result.question, 'Should have reflection question');
    assert(result.question.startsWith('💡 Вы сказали:'),
      `Reflection should start with "💡 Вы сказали:", got: "${result.question.slice(0, 30)}..."`);
    assert(result.question.includes('Я правильно понял?'),
      'Reflection should ask for confirmation');

    // Проверяем состояние сессии
    assert.strictEqual(result.session.reflectionPending, true,
      'Session should have reflectionPending = true');
    assert.strictEqual(result.session.reflectionAnswer, DEEP_L1_ANSWER,
      'Session should store original answer');
    assert.strictEqual(result.session.reflectionSubsection, '1.1',
      'Session should store current subsection');

    // Проверяем, что ответ сохранён
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert(savedSession.answers['1.1'], 'Answer for 1.1 should exist');
    assert.strictEqual(savedSession.answers['1.1'].L1, DEEP_L1_ANSWER,
      'L1 answer should be saved');
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L1',
      'depthReached should be L1 immediately');

    // Проверяем, что позиция не изменилась (ждёт подтверждения)
    assert.strictEqual(result.session.template.subsection, '1.1',
      'Should stay at same subsection waiting for confirmation');

    console.log('✓ testProcessAnswer_L1Deep_ReturnsReflection');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L1Shallow_GoesToL2() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Поверхностный L1-ответ → должен перейти на L2
    const result = await surveyEngine.processAnswer(startResult.session, SHALLOW_ANSWER);

    assert.strictEqual(result.action, 'next_question',
      `Should be next_question, got ${result.action}`);
    assert(result.question, 'Should have a question');

    // Должен остаться на том же подразделе, но на L2
    assert.strictEqual(result.session.template.subsection, '1.1',
      'Should stay at subsection 1.1');
    assert.strictEqual(result.session.template.depth, 'L2',
      'Depth should move to L2');

    // reflectionPending не должно быть true при поверхностном ответе
    assert.strictEqual(result.session.reflectionPending, undefined,
      'Shallow L1 should not set reflectionPending');

    console.log('✓ testProcessAnswer_L1Shallow_GoesToL2');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L1VeryShort_GoesToL2() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Очень короткий ответ → L2
    const result = await surveyEngine.processAnswer(startResult.session, VERY_SHORT_ANSWER);

    assert.strictEqual(result.session.template.depth, 'L2',
      'Very short L1 should go to L2');

    console.log('✓ testProcessAnswer_L1VeryShort_GoesToL2');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== L1 Tests: _handleReflectionConfirm ====================

async function testReflectionConfirm_Yes_AdvancesToNextSubsection() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // Даём глубокий L1-ответ → reflection_needed
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
    assert.strictEqual(current.action, 'reflection_needed');
    assert.strictEqual(current.session.reflectionPending, true);

    // Подтверждаем ("да")
    current = await surveyEngine.processAnswer(current.session, 'да');

    // Должны перейти к следующему подразделу (1.1 → 1.2)
    assert.strictEqual(current.action, 'next_question',
      `After confirmation should be next_question, got ${current.action}`);
    assert.strictEqual(current.session.template.subsection, '1.2',
      `Should be at subsection 1.2, got ${current.session.template.subsection}`);
    assert.strictEqual(current.session.template.depth, 'L1',
      'Depth should reset to L1');

    // reflectionPending должен быть сброшен
    assert.strictEqual(current.session.reflectionPending, false,
      'reflectionPending should be false after confirmation');

    // depthReached должен быть L1
    const savedSession = await sessionManager.getSession(current.session.sessionId);
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L1',
      'depthReached should be L1 after confirmation');

    console.log('✓ testReflectionConfirm_Yes_AdvancesToNextSubsection');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReflectionConfirm_YesVariant_Confirms() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const confirmVariants = ['верно', 'правильно', 'точно', 'да-да', 'yes', 'ok', 'ага', 'согласен'];

    for (const variant of confirmVariants) {
      const session = await sessionManager.createSession(12345 + Math.random() * 10000);
      let current = await surveyEngine.startSurvey(session);
      current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
      assert.strictEqual(current.action, 'reflection_needed',
        `"${variant}" pre-check failed: action should be reflection_needed`);

      current = await surveyEngine.processAnswer(current.session, variant);

      assert.strictEqual(current.action, 'next_question',
        `"${variant}" should confirm, got action=${current.action}`);
      assert.strictEqual(current.session.reflectionPending, false,
        `"${variant}" should clear reflectionPending`);
    }

    console.log('✓ testReflectionConfirm_YesVariant_Confirms');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReflectionConfirm_Correction_Reevaluates() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // Даём глубокий L1-ответ → reflection_needed
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
    assert.strictEqual(current.action, 'reflection_needed');

    // Исправление: новый, тоже глубокий ответ
    const correctedAnswer = 'Мы автоматизируем закупки для сети продуктовых магазинов. ' +
      'Сейчас менеджеры тратят по 4 часа на согласование. ' +
      'Из-за этого теряем поставщиков примерно раз в месяц.';
    current = await surveyEngine.processAnswer(current.session, correctedAnswer);

    // Исправленный ответ достаточно глубокий → должен перейти к следующему подразделу
    assert.strictEqual(current.action, 'next_question',
      `Correction with deep answer should transition, got ${current.action}`);
    assert.strictEqual(current.session.template.subsection, '1.2',
      'Should advance to next subsection after correction');

    // Ответ должен быть обновлён
    const savedSession = await sessionManager.getSession(current.session.sessionId);
    assert.strictEqual(savedSession.answers['1.1'].L1, correctedAnswer,
      'Answer should be updated with corrected text');
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L1',
      'depthReached should be L1');

    console.log('✓ testReflectionConfirm_Correction_Reevaluates');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReflectionConfirm_ShallowCorrection_GoesToL2() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // Даём глубокий L1-ответ → reflection_needed
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
    assert.strictEqual(current.action, 'reflection_needed');

    // Исправление: короткий поверхностный ответ
    current = await surveyEngine.processAnswer(current.session, 'Ну, работаем над автоматизацией.');

    // Поверхностное исправление → L2
    assert.strictEqual(current.action, 'next_question',
      `Shallow correction should still be next_question, got ${current.action}`);
    assert.strictEqual(current.session.template.depth, 'L2',
      'Shallow correction should go to L2');
    assert.strictEqual(current.session.template.subsection, '1.1',
      'Should stay at same subsection');

    // Проверяем, что L2-вопрос отформатирован (Story 2.3)
    assert(current.question.includes('🔍 Давайте уточним:'),
      `L2 question should contain 🔍 format, got: "${current.question.slice(0, 80)}..."`);
    assert(current.question.includes('Чтобы лучше понять ситуацию, уточню...'),
      `L2 question should have reason prefix, got: "${current.question.slice(0, 80)}..."`);

    console.log('✓ testReflectionConfirm_ShallowCorrection_GoesToL2');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReflectionConfirm_NotConfirmation_TreatedAsCorrection() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // Даём глубокий L1-ответ → reflection_needed
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
    assert.strictEqual(current.action, 'reflection_needed');

    // Ответ "нет" (не является словом-подтверждением) — это исправление
    current = await surveyEngine.processAnswer(current.session, 'Нет, не так.');

    // Должен обработаться как исправление
    assert(current.action === 'next_question' || current.action === 'reflection_needed',
      'Non-confirmation should be treated as correction');

    // reflectionPending должен быть сброшен
    assert.strictEqual(current.session.reflectionPending, false,
      'reflectionPending should be cleared');

    console.log('✓ testReflectionConfirm_NotConfirmation_TreatedAsCorrection');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== L1 Tests: Полный цикл ====================

async function testFullL1Cycle_AcrossMultipleSubsections() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // Проходим блок 1 (3 подраздела) с L1-глубиной

    // Подраздел 1.1: глубокий ответ → reflection → подтверждение → 1.2
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
    assert.strictEqual(current.action, 'reflection_needed',
      '1.1 should get reflection');
    current = await surveyEngine.processAnswer(current.session, 'да');
    assert.strictEqual(current.session.template.subsection, '1.2',
      'After confirming 1.1, should be at 1.2');

    // Подраздел 1.2: глубокий ответ → reflection → подтверждение → 1.3
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
    assert.strictEqual(current.action, 'reflection_needed',
      '1.2 should get reflection');
    current = await surveyEngine.processAnswer(current.session, 'верно');
    assert.strictEqual(current.session.template.subsection, '1.3',
      'After confirming 1.2, should be at 1.3');

    // Подраздел 1.3: глубокий ответ → reflection → подтверждение → Блок 2
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
    assert.strictEqual(current.action, 'reflection_needed',
      '1.3 should get reflection');
    current = await surveyEngine.processAnswer(current.session, 'да');
    assert.strictEqual(current.session.template.block, 2,
      'After confirming 1.3, should be at block 2');
    assert.strictEqual(current.session.template.subsection, '2.1',
      'After confirming 1.3, should be at subsection 2.1');

    console.log('✓ testFullL1Cycle_AcrossMultipleSubsections');
  } finally {
    cleanup(tmpDir);
  }
}

async function testFullL1Cycle_MixedDepths() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // Подраздел 1.1: поверхностный → L2 (традиционная глубина)
    current = await surveyEngine.processAnswer(current.session, SHALLOW_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L2',
      'Shallow L1 → L2');
    assert.strictEqual(current.session.template.subsection, '1.1',
      'Stay at 1.1');

    // Подраздел 1.2 (после прохождения 1.1 через L2 или L3)
    const SURVEY_DEEP_ANSWER = DEEP_L1_ANSWER;
    current = await surveyEngine.processAnswer(current.session, SURVEY_DEEP_ANSWER);

    // Должен перейти к 1.2 после глубокого ответа на L2
    assert(current.session.template.subsection === '1.2' || current.session.template.depth === 'L3',
      `After L2 deep, should move to 1.2 or L3, got sub=${current.session.template.subsection} depth=${current.session.template.depth}`);

    // Переходим к 1.2 в любом случае
    while (current.session.template.subsection !== '1.2' && current.action !== 'survey_complete') {
      current = await surveyEngine.processAnswer(current.session, SURVEY_DEEP_ANSWER);
    }

    // Подраздел 1.2: глубокий L1 → reflection
    current = await surveyEngine.processAnswer(current.session, THREE_SENTENCE_ANSWER);
    if (current.action === 'reflection_needed') {
      assert.strictEqual(current.session.reflectionPending, true,
        'Reflection should be pending for L1 deep at 1.2');
      current = await surveyEngine.processAnswer(current.session, 'да');
      assert.strictEqual(current.session.template.subsection, '1.3',
        'After confirming 1.2, should be at 1.3');
    }

    console.log('✓ testFullL1Cycle_MixedDepths');
  } finally {
    cleanup(tmpDir);
  }
}

async function testL1Depth_ScoreEdgeCases() {
  const { tmpDir, sessionManager, surveyEngine, templateEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // 3 предложения без цифр и индикаторов
    const threeSentNoFacts =
      'Мы автоматизируем закупки. Сейчас процесс ручной. ' +
      'Это занимает много времени.';
    let result = await surveyEngine.processAnswer(startResult.session, threeSentNoFacts);

    // 3 предложения → _isL1DeepEnough = true → reflection
    assert.strictEqual(result.action, 'reflection_needed',
      'Three plain sentences should trigger reflection');

    // 2 предложения с 2 фактами
    const twoSentTwoFacts =
      'Автоматизируем закупки в сети из 100 магазинов. ' +
      'Потому что ручной процесс создаёт потери.';
    const session2 = await sessionManager.createSession(12346);
    let start2 = await surveyEngine.startSurvey(session2);
    result = await surveyEngine.processAnswer(start2.session, twoSentTwoFacts);
    assert.strictEqual(result.action, 'reflection_needed',
      '2 sentences with 2 facts should trigger reflection');

    console.log('✓ testL1Depth_ScoreEdgeCases');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== L2 Tests: _extractKeyPhrase (Story 2.3) ====================

async function testExtractKeyPhrase_Basic() {
  const { surveyEngine } = await setup();

  const phrase = surveyEngine._extractKeyPhrase(DEEP_L1_ANSWER);
  assert(phrase, 'Should extract a key phrase');
  assert(phrase.length >= 4, `Key phrase should be meaningful: "${phrase}"`);
  // Первая буква заглавная
  assert(phrase[0] === phrase[0].toUpperCase(), `Key phrase should start with capital: "${phrase}"`);

  console.log('✓ testExtractKeyPhrase_Basic');
}

async function testExtractKeyPhrase_ShortAnswer() {
  const { surveyEngine } = await setup();

  const phrase = surveyEngine._extractKeyPhrase('Работаем над автоматизацией.');
  assert(phrase, 'Should extract from short answer');
  assert(phrase.includes('автоматизацией'), `Should include "автоматизацией", got: "${phrase}"`);

  console.log('✓ testExtractKeyPhrase_ShortAnswer');
}

async function testExtractKeyPhrase_OneWord() {
  const { surveyEngine } = await setup();

  // Односложные ответы-подтверждения — не должны давать контекст
  const confirmations = ['да', 'нет', 'верно', 'ага', 'ok'];
  for (const c of confirmations) {
    const phrase = surveyEngine._extractKeyPhrase(c);
    assert.strictEqual(phrase, null,
      `Confirmation "${c}" should return null, got "${phrase}"`);
  }

  console.log('✓ testExtractKeyPhrase_OneWord');
}

async function testExtractKeyPhrase_TwoWords() {
  const { surveyEngine } = await setup();

  // Два слова, не подтверждение
  const phrase = surveyEngine._extractKeyPhrase('Очень сложно всё.');
  assert(phrase, 'Two-word answer should extract key phrase');
  assert(phrase.includes('Очень'), `Should include "Очень", got: "${phrase}"`);

  console.log('✓ testExtractKeyPhrase_TwoWords');
}

async function testExtractKeyPhrase_Empty() {
  const { surveyEngine } = await setup();

  assert.strictEqual(surveyEngine._extractKeyPhrase(''), null,
    'Empty answer should return null');
  assert.strictEqual(surveyEngine._extractKeyPhrase(null), null,
    'Null answer should return null');
  assert.strictEqual(surveyEngine._extractKeyPhrase('   '), null,
    'Whitespace answer should return null');

  console.log('✓ testExtractKeyPhrase_Empty');
}

// ==================== L2 Tests: _formatL2Question (Story 2.3) ====================

async function testFormatL2Question_Basic() {
  const { surveyEngine } = await setup();

  // Базовое форматирование без контекста
  const question = surveyEngine._formatL2Question('1.1', undefined);

  assert(question, 'Should return a formatted question');
  assert(question.includes('🔍 Давайте уточним:'),
    'Should contain L2 format with 🔍');
  assert(question.includes('Чтобы лучше понять ситуацию, уточню...'),
    'Should contain reason prefix');
  assert(question.length > 50, 'Should be a meaningful question');

  console.log('✓ testFormatL2Question_Basic');
}

async function testFormatL2Question_WithContext() {
  const { surveyEngine } = await setup();

  // Форматирование с контекстом из предыдущего ответа
  const previousAnswer = 'Автоматизируем закупки в сети из 50 магазинов.';
  const question = surveyEngine._formatL2Question('1.1', previousAnswer);

  assert(question, 'Should return formatted question');
  assert(question.includes('🔍 Давайте уточним:'),
    'Should contain 🔍 format');
  assert(question.includes('Чтобы лучше понять ситуацию, уточню...'),
    'Should contain reason prefix');

  // Проверяем, что контекстная фраза встроена
  assert(question.includes('упомянули'),
    'Should reference previous answer: "упомянули"');

  console.log('✓ testFormatL2Question_WithContext');
}

async function testFormatL2Question_ErrorHandling() {
  const { surveyEngine } = await setup();

  // Несуществующий подраздел — должен вернуть fallback
  const question = surveyEngine._formatL2Question('99.99', 'какой-то ответ');

  assert(question, 'Should return fallback question on error');
  assert(question.includes('🔍 Давайте уточним:'),
    'Fallback should still have 🔍 format');

  console.log('✓ testFormatL2Question_ErrorHandling');
}

async function testFormatL2Question_ValidTemplateContent() {
  const { surveyEngine } = await setup();

  // Проверяем, что форматированный вопрос содержит L2-вопрос из template
  const templateQuestion = surveyEngine.templateEngine.getQuestion('1.1', 'L2');
  const formatted = surveyEngine._formatL2Question('1.1', 'Работаем над автоматизацией.');

  // Должен содержать содержимое шаблонного вопроса (или его часть)
  assert(formatted.length > templateQuestion.length,
    'Formatted question should be longer than template alone');
  assert(formatted.includes('сформулировали') || formatted.includes('суть'),
    'Should contain L2 template question content');

  console.log('✓ testFormatL2Question_ValidTemplateContent');
}

// ==================== L2 Tests: processAnswer — L1 shallow → L2 formatted (Story 2.3) ====================

async function testProcessAnswer_L1Shallow_L2FormattedQuestion() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Поверхностный L1-ответ → переходим на L2
    const result = await surveyEngine.processAnswer(startResult.session, SHALLOW_ANSWER);

    assert.strictEqual(result.action, 'next_question',
      `Should be next_question, got ${result.action}`);
    assert.strictEqual(result.session.template.depth, 'L2',
      'Depth should move to L2');

    // Проверяем форматирование L2-вопроса (Story 2.3)
    const question = result.question;
    assert(question, 'Should have a question');
    assert(question.includes('🔍 Давайте уточним:'),
      `L2 question should contain 🔍 format, got: "${question.slice(0, 80)}..."`);
    assert(question.includes('Чтобы лучше понять ситуацию, уточню...'),
      `L2 question should have reason prefix, got: "${question.slice(0, 80)}..."`);

    console.log('✓ testProcessAnswer_L1Shallow_L2FormattedQuestion');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L1Shallow_L2ContextAware() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Поверхностный L1-ответ с явным контекстом
    const contextAnswer = 'Автоматизируем закупки в крупной сети.';
    const result = await surveyEngine.processAnswer(startResult.session, contextAnswer);

    // L2-вопрос должен ссылаться на контекст
    const question = result.question;
    assert(question.includes('упомянули') || question.includes('Автоматизируем'),
      `L2 question should reference previous answer context, got: "${question.slice(0, 100)}..."`);

    console.log('✓ testProcessAnswer_L1Shallow_L2ContextAware');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L1Shallow_L2MediumScore() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Поверхностный L1 → L2
    let result = await surveyEngine.processAnswer(startResult.session, SHALLOW_ANSWER);
    assert.strictEqual(result.session.template.depth, 'L2',
      'Shallow L1 → L2');

    // Ответ со средней глубиной на L2 (score ~0.4: числа есть, но без причин)
    const mediumAnswer = 'У нас 200 магазинов, оборот 500 млн. Надо автоматизировать.';
    result = await surveyEngine.processAnswer(result.session, mediumAnswer);

    // Средняя глубина на L2 → всё равно недостаточно для фиксации → L3
    assert(result.session.template.depth === 'L3' || result.session.template.depth === 'L2',
      `Medium L2 should go to L3 or stay at L2, got depth=${result.session.template.depth}`);

    // Если остался на L2 — даём ещё один глубокий ответ
    if (result.session.template.depth === 'L2') {
      result = await surveyEngine.processAnswer(result.session, DEEP_L2_ANSWER);
      assert(result.session.template.depth === 'L3' || result.session.template.subsection !== '1.1',
        `After deep L2 should transition`);
    }

    console.log('✓ testProcessAnswer_L1Shallow_L2MediumScore');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L2Deep_AdvanceToNextSubsection() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Поверхностный L1 → L2
    let result = await surveyEngine.processAnswer(startResult.session, SHALLOW_ANSWER);
    assert.strictEqual(result.session.template.depth, 'L2',
      'Shallow L1 → L2');
    assert.strictEqual(result.session.template.subsection, '1.1',
      'Stay at 1.1');

    // Глубокий L2-ответ (score ≥ 0.6) → depthReached: "L2" → след. подраздел
    result = await surveyEngine.processAnswer(result.session, DEEP_L2_ANSWER);

    // Должен перейти к следующему подразделу (1.2)
    assert.strictEqual(result.session.template.subsection, '1.2',
      `Deep L2 answer should advance to next subsection, got ${result.session.template.subsection}`);
    assert.strictEqual(result.session.template.depth, 'L1',
      'Depth should reset to L1 for new subsection');

    // Проверяем depthReached
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L2',
      'depthReached should be L2');

    // Проверяем, что L2 ответ сохранён
    assert.strictEqual(savedSession.answers['1.1'].L2, DEEP_L2_ANSWER,
      'L2 answer should be saved');

    console.log('✓ testProcessAnswer_L2Deep_AdvanceToNextSubsection');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L2Shallow_GoesToL3() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Поверхностный L1 → L2
    let result = await surveyEngine.processAnswer(startResult.session, SHALLOW_ANSWER);
    assert.strictEqual(result.session.template.depth, 'L2',
      'Shallow L1 → L2');

    // Поверхностный L2-ответ (score < 0.6) → L3
    result = await surveyEngine.processAnswer(result.session, SHALLOW_L2_ANSWER);

    assert.strictEqual(result.session.template.depth, 'L3',
      'Shallow L2 → L3');
    assert.strictEqual(result.session.template.subsection, '1.1',
      'Should stay at same subsection');

    console.log('✓ testProcessAnswer_L2Shallow_GoesToL3');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L2toL3_WithContext() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Поверхностный L1 → L2 (с контекстом)
    const contextAnswer = 'Автоматизируем процесс закупок вручную через Excel.';
    let result = await surveyEngine.processAnswer(startResult.session, contextAnswer);
    assert.strictEqual(result.session.template.depth, 'L2',
      'Shallow L1 → L2');

    // Поверхностный L2 → L3
    result = await surveyEngine.processAnswer(result.session, SHALLOW_L2_ANSWER);

    assert.strictEqual(result.session.template.depth, 'L3',
      'Shallow L2 → L3');

    // L3-вопрос должен быть из шаблона
    const templateL3 = surveyEngine.templateEngine.getQuestion('1.1', 'L3');
    assert(result.question.includes(templateL3.slice(0, 30)) ||
           result.question.includes('добраться до сути'),
      `L3 question should reference root cause, got: "${result.question.slice(0, 80)}..."`);

    console.log('✓ testProcessAnswer_L2toL3_WithContext');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== L2 Tests: Полный цикл L1→L2→L3 (Story 2.3 + Story 2.4) ====================

async function testFullL1toL2Cycle() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // 1. L1: глубокий ответ → reflection → подтверждение → 1.2
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
    assert.strictEqual(current.action, 'reflection_needed');
    current = await surveyEngine.processAnswer(current.session, 'да');
    assert.strictEqual(current.session.template.subsection, '1.2',
      '1.1 deep → confirm → 1.2');

    // 2. L1: поверхностный на 1.2 → L2
    current = await surveyEngine.processAnswer(current.session, SHALLOW_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L2',
      '1.2 shallow → L2');
    assert.strictEqual(current.session.template.subsection, '1.2',
      'Still at 1.2');

    // 3. L2: глубокий на 1.2 → depthReached: "L2" → 1.3
    current = await surveyEngine.processAnswer(current.session, DEEP_L2_ANSWER);
    assert.strictEqual(current.session.template.subsection, '1.3',
      '1.2 deep L2 → 1.3');
    assert.strictEqual(current.session.template.depth, 'L1',
      'Depth resets to L1');

    // Проверяем фиксацию глубины
    const savedSession = await sessionManager.getSession(current.session.sessionId);
    assert.strictEqual(savedSession.answers['1.2'].depthReached, 'L2',
      'depthReached for 1.2 should be L2');
    assert(savedSession.answers['1.2'].L1, 'L1 answer for 1.2 should exist');
    assert(savedSession.answers['1.2'].L2, 'L2 answer for 1.2 should exist');

    console.log('✓ testFullL1toL2Cycle');
  } finally {
    cleanup(tmpDir);
  }
}

async function testFullL1toL2toL3Cycle() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // 1. L1: поверхностный на 1.1 → L2
    current = await surveyEngine.processAnswer(current.session, SHALLOW_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L2',
      'Shallow L1 → L2');

    // 2. L2: поверхностный на 1.1 → L3
    current = await surveyEngine.processAnswer(current.session, SHALLOW_L2_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L3',
      'Shallow L2 → L3');

    // 3. L3: любой ответ → depthReached: "L3" → следующий подраздел
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);

    // Должен перейти к 1.2 (или другому подразделу)
    assert(current.session.template.subsection === '1.2' || current.session.template.subsection === '1.3',
      `After L3, should advance to next subsection, got ${current.session.template.subsection}`);
    assert.strictEqual(current.session.template.depth, 'L1',
      'Depth should reset to L1');

    // Проверяем depthReached
    const savedSession = await sessionManager.getSession(current.session.sessionId);
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L3',
      'depthReached for 1.1 should be L3 (max depth)');

    console.log('✓ testFullL1toL2toL3Cycle');
  } finally {
    cleanup(tmpDir);
  }
}

async function testL2Transition_RisksCollected() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // L1: поверхностный → L2
    let result = await surveyEngine.processAnswer(startResult.session, SHALLOW_ANSWER);
    assert.strictEqual(result.session.template.depth, 'L2');

    // L2: ответ с рисками
    const riskyL2Answer = 'Есть риск, что пользователи не примут новую систему. ' +
      'Проблема в интеграции с существующими системами. ' +
      'Бюджет проекта ограничен — всего 2 млн. ' +
      'Из-за этого можем не уложиться в сроки.';

    result = await surveyEngine.processAnswer(result.session, riskyL2Answer);

    // Должны быть собраны риски (если L2 глубокий — следующий подраздел, если нет — L3)
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    if (savedSession.risks && savedSession.risks.length > 0) {
      const riskTexts = savedSession.risks.map(r => r.text.toLowerCase());
      assert(riskTexts.some(t => t.includes('риск' || t.includes('проблем'))),
        'Risks should contain risk-related words');
    }

    // Проверяем, что risks поле существует в сессии
    assert(!Array.isArray(savedSession.risks) || savedSession.risks.every(r => r.category),
      'Risks should have categories');

    console.log('✓ testL2Transition_RisksCollected');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== L3 Tests: _formatL3Question (Story 2.4) ====================

async function testFormatL3Question_Basic() {
  const { surveyEngine } = await setup();

  // Базовое форматирование без контекста
  const question = surveyEngine._formatL3Question('1.1', undefined);

  assert(question, 'Should return a formatted question');
  assert(question.includes('🔍 Попробуем добраться до сути:'),
    'Should contain L3 format with 🔍');
  assert(question.includes('Чтобы понять коренную причину, спрошу глубже...'),
    'Should contain root cause explanation');
  assert(question.length > 50, 'Should be a meaningful question');

  console.log('✓ testFormatL3Question_Basic');
}

async function testFormatL3Question_WithContext() {
  const { surveyEngine } = await setup();

  // Контекст с L1+L2 ответами
  const fullContext = {
    L1: 'Автоматизируем закупки в сети из 200 магазинов.',
    L2: 'Сейчас всё в Excel, менеджеры тратят по 4 часа в день.'
  };
  const question = surveyEngine._formatL3Question('1.1', fullContext);

  assert(question, 'Should return formatted question with context');
  assert(question.includes('🔍 Попробуем добраться до сути:'),
    'Should contain 🔍 format');
  assert(question.includes('Чтобы понять коренную причину, спрошу глубже...'),
    'Should contain root cause explanation');
  assert(question.includes('говорили про'),
    'Should reference previous dialogue: "говорили про"');

  console.log('✓ testFormatL3Question_WithContext');
}

async function testFormatL3Question_WithL1ContextOnly() {
  const { surveyEngine } = await setup();

  // Только L1, без L2
  const fullContext = {
    L1: 'Автоматизируем закупки в 50 магазинах.',
    L2: undefined
  };
  const question = surveyEngine._formatL3Question('1.1', fullContext);

  assert(question, 'Should return formatted question');
  assert(question.includes('🔍'), 'Should contain 🔍');
  assert(question.includes('говорили про'),
    'Should reference L1 context even without L2');

  console.log('✓ testFormatL3Question_WithL1ContextOnly');
}

async function testFormatL3Question_WithL2ContextOnly() {
  const { surveyEngine } = await setup();

  // Только L2, без L1
  const fullContext = {
    L1: undefined,
    L2: 'Менеджеры тратят по 4 часа на согласование заказов.'
  };
  const question = surveyEngine._formatL3Question('1.1', fullContext);

  assert(question, 'Should return formatted question');
  assert(question.includes('🔍'), 'Should contain 🔍');
  assert(question.includes('говорили про'),
    'Should reference L2 context even without L1');

  console.log('✓ testFormatL3Question_WithL2ContextOnly');
}

async function testFormatL3Question_ErrorHandling() {
  const { surveyEngine } = await setup();

  // Несуществующий подраздел — должен вернуть fallback
  const question = surveyEngine._formatL3Question('99.99', { L1: 'какой-то ответ' });

  assert(question, 'Should return fallback question on error');
  assert(question.includes('🔍 Попробуем добраться до сути:'),
    'Fallback should still have 🔍 format');

  console.log('✓ testFormatL3Question_ErrorHandling');
}

async function testFormatL3Question_ValidTemplateContent() {
  const { surveyEngine } = await setup();

  // Проверяем, что форматированный вопрос содержит L3-вопрос из template
  const templateQuestion = surveyEngine.templateEngine.getQuestion('1.1', 'L3');
  const formatted = surveyEngine._formatL3Question('1.1', undefined);

  assert(formatted.length > templateQuestion.length,
    'Formatted question should be longer than template alone');
  assert(formatted.toLowerCase().includes(templateQuestion.slice(0, 20).toLowerCase()),
    'Should contain L3 template question content');

  console.log('✓ testFormatL3Question_ValidTemplateContent');
}

// ==================== L3 Tests: processAnswer — L3 evaluation (Story 2.4) ====================

async function testProcessAnswer_L1toL2toL3_QuestionFormat() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let result = await surveyEngine.startSurvey(session);

    // L1: поверхностный → L2
    result = await surveyEngine.processAnswer(result.session, 'Работаем над автоматизацией.');
    assert.strictEqual(result.session.template.depth, 'L2', 'Shallow L1 → L2');

    // L2: поверхностный → L3
    result = await surveyEngine.processAnswer(result.session, 'Ну, надо автоматизировать закупки.');
    assert.strictEqual(result.session.template.depth, 'L3', 'Shallow L2 → L3');

    // L3-вопрос должен быть отформатирован
    const question = result.question;
    assert(question, 'L3 should have a question');
    assert(question.includes('🔍 Попробуем добраться до сути:'),
      `L3 question should contain root cause format, got: "${question.slice(0, 80)}..."`);
    assert(question.includes('Чтобы понять коренную причину, спрошу глубже...'),
      'L3 question should have root cause explanation');

    console.log('✓ testProcessAnswer_L1toL2toL3_QuestionFormat');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L3Deep_AdvanceToNextSubsection() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let result = await surveyEngine.startSurvey(session);

    // L1: поверхностный → L2
    result = await surveyEngine.processAnswer(result.session, SHALLOW_ANSWER);
    assert.strictEqual(result.session.template.depth, 'L2');

    // L2: поверхностный → L3 (остаёмся на 1.1)
    result = await surveyEngine.processAnswer(result.session, SHALLOW_L2_ANSWER);
    assert.strictEqual(result.session.template.depth, 'L3', 'Shallow L2 → L3');
    assert.strictEqual(result.session.template.subsection, '1.1', 'Still at 1.1');

    // L3: глубокий ответ (score ≥ 0.6) → depthReached: "L3" → след. подраздел
    result = await surveyEngine.processAnswer(result.session, DEEP_L2_ANSWER);

    // Должен перейти к следующему подразделу
    assert(result.session.template.subsection === '1.2',
      `Deep L3 answer should advance to next subsection, got ${result.session.template.subsection}`);
    assert.strictEqual(result.session.template.depth, 'L1',
      'Depth should reset to L1 for new subsection');

    // Проверяем depthReached
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L3',
      'depthReached should be L3');

    console.log('✓ testProcessAnswer_L3Deep_AdvanceToNextSubsection');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L3Shallow_AdvanceToNextSubsection() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let result = await surveyEngine.startSurvey(session);

    // L1: поверхностный → L2
    result = await surveyEngine.processAnswer(result.session, SHALLOW_ANSWER);
    assert.strictEqual(result.session.template.depth, 'L2');

    // L2: поверхностный → L3
    result = await surveyEngine.processAnswer(result.session, SHALLOW_L2_ANSWER);
    assert.strictEqual(result.session.template.depth, 'L3');

    // L3: поверхностный ответ → depthReached: "L3" max → след. подраздел
    // БЕЗ бесконечного цикла!
    result = await surveyEngine.processAnswer(result.session, SHALLOW_ANSWER);

    // Должен всё равно перейти к следующему подразделу
    assert(result.session.template.subsection === '1.2',
      `Shallow L3 should still advance (no infinite loop), got sub=${result.session.template.subsection}`);
    assert.strictEqual(result.session.template.depth, 'L1',
      'Depth should reset to L1 for new subsection');

    // Проверяем depthReached
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L3',
      'depthReached should be L3 even for shallow L3');

    console.log('✓ testProcessAnswer_L3Shallow_AdvanceToNextSubsection');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L3_depthReached_IsL3() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let result = await surveyEngine.startSurvey(session);

    // L1 → L2 → L3 → любой ответ
    result = await surveyEngine.processAnswer(result.session, SHALLOW_ANSWER);
    result = await surveyEngine.processAnswer(result.session, SHALLOW_L2_ANSWER);
    result = await surveyEngine.processAnswer(result.session, DEEP_L1_ANSWER);

    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L3',
      'depthReached should always be L3 after answering at L3');

    assert(savedSession.answers['1.1'].L3, 'L3 answer should be saved');
    assert.strictEqual(savedSession.answers['1.1'].L1, SHALLOW_ANSWER,
      'L1 answer should be preserved');
    assert.strictEqual(savedSession.answers['1.1'].L2, SHALLOW_L2_ANSWER,
      'L2 answer should be preserved');

    console.log('✓ testProcessAnswer_L3_depthReached_IsL3');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L3Shallow_depthReachedIsL3() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let result = await surveyEngine.startSurvey(session);

    // L1 → L2 → L3 → поверхностный ответ
    result = await surveyEngine.processAnswer(result.session, SHALLOW_ANSWER);
    result = await surveyEngine.processAnswer(result.session, SHALLOW_L2_ANSWER);
    result = await surveyEngine.processAnswer(result.session, 'Да.');  // очень поверхностно

    const savedSession = await sessionManager.getSession(result.session.sessionId);
    // Даже при поверхностном L3 — depthReached всё равно "L3"
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L3',
      'depthReached should be L3 even for very shallow L3 answer');

    console.log('✓ testProcessAnswer_L3Shallow_depthReachedIsL3');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L3_ContextRelevance() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let result = await surveyEngine.startSurvey(session);

    // L1: специфичный ответ о закупках
    const l1Context = 'Автоматизируем закупки для сети продуктовых магазинов.';
    result = await surveyEngine.processAnswer(result.session, l1Context);
    assert.strictEqual(result.session.template.depth, 'L2');

    // L2: поверхностный, без достаточных деталей
    result = await surveyEngine.processAnswer(result.session, 'Ну, просто надо автоматизировать.');
    assert.strictEqual(result.session.template.depth, 'L3', 'Shallow L2 → L3');

    // L3-вопрос должен ссылаться на контекст L1
    const question = result.question;
    assert(question.includes('говорили про') || question.includes('закупки'),
      `L3 question should reference dialogue context, got: "${question.slice(0, 100)}..."`);

    console.log('✓ testProcessAnswer_L3_ContextRelevance');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L3_MaxDepthNoLoop() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let result = await surveyEngine.startSurvey(session);

    // L1 → L2 → L3
    result = await surveyEngine.processAnswer(result.session, SHALLOW_ANSWER);
    result = await surveyEngine.processAnswer(result.session, SHALLOW_L2_ANSWER);

    assert.strictEqual(result.session.template.depth, 'L3',
      'At L3, depth should be exactly L3');

    // Даём самый поверхностный ответ
    result = await surveyEngine.processAnswer(result.session, 'Не знаю.');

    // После L3 ответа — переход, больше не углубляемся
    assert(result.action === 'next_question' || result.action === 'survey_complete',
      `After L3 answer, should transition, got action=${result.action}`);

    // Глубина больше не эскалируется (L3 — максимум)
    if (result.session.template.subsection !== '1.1') {
      assert.strictEqual(result.session.template.depth, 'L1',
        'After L3, depth should reset to L1 for new subsection');
    }

    console.log('✓ testProcessAnswer_L3_MaxDepthNoLoop');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L3_NoReflectionPending() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let result = await surveyEngine.startSurvey(session);

    // L1 → L2 → L3
    result = await surveyEngine.processAnswer(result.session, SHALLOW_ANSWER);
    result = await surveyEngine.processAnswer(result.session, SHALLOW_L2_ANSWER);

    // L3 развёрнутый ответ
    result = await surveyEngine.processAnswer(result.session, DEEP_L2_ANSWER);

    // L3 не должен устанавливать reflectionPending
    assert.strictEqual(result.session.reflectionPending, undefined,
      'L3 should not set reflectionPending');

    console.log('✓ testProcessAnswer_L3_NoReflectionPending');
  } finally {
    cleanup(tmpDir);
  }
}

async function testProcessAnswer_L3Shallow_NoReflectionPending() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let result = await surveyEngine.startSurvey(session);

    // L1 → L2 → L3 → поверхностный
    result = await surveyEngine.processAnswer(result.session, SHALLOW_ANSWER);
    result = await surveyEngine.processAnswer(result.session, SHALLOW_L2_ANSWER);
    result = await surveyEngine.processAnswer(result.session, 'Ну, не знаю.');

    // Даже поверхностный L3 не должен устанавливать reflection
    assert.strictEqual(result.session.reflectionPending, undefined,
      'Even shallow L3 should not set reflectionPending');

    console.log('✓ testProcessAnswer_L3Shallow_NoReflectionPending');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== L3 Tests: Полные циклы (Story 2.4) ====================

async function testFullL1toL2toL3Cycle_DeepL3() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // 1. L1: глубокий → reflection → подтверждение → 1.2
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
    assert.strictEqual(current.action, 'reflection_needed');
    current = await surveyEngine.processAnswer(current.session, 'да');
    assert.strictEqual(current.session.template.subsection, '1.2');

    // 2. 1.2 L1: поверхностный → L2
    current = await surveyEngine.processAnswer(current.session, SHALLOW_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L2');
    assert.strictEqual(current.session.template.subsection, '1.2');

    // 3. L2: поверхностный → L3
    current = await surveyEngine.processAnswer(current.session, SHALLOW_L2_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L3');

    // 4. L3: глубокий ответ → depthReached: "L3" → 1.3
    current = await surveyEngine.processAnswer(current.session, DEEP_L2_ANSWER);

    assert.strictEqual(current.session.template.subsection, '1.3',
      `Deep L3 should advance to 1.3, got ${current.session.template.subsection}`);
    assert.strictEqual(current.session.template.depth, 'L1',
      'Depth resets to L1');

    const savedSession = await sessionManager.getSession(current.session.sessionId);
    assert.strictEqual(savedSession.answers['1.2'].depthReached, 'L3',
      'depthReached for 1.2 should be L3');
    assert(savedSession.answers['1.2'].L1, 'L1 answer for 1.2 exists');
    assert(savedSession.answers['1.2'].L2, 'L2 answer for 1.2 exists');
    assert(savedSession.answers['1.2'].L3, 'L3 answer for 1.2 exists');

    console.log('✓ testFullL1toL2toL3Cycle_DeepL3');
  } finally {
    cleanup(tmpDir);
  }
}

async function testFullL1toL2toL3Cycle_ShallowL3() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // L1: поверхностный → L2
    current = await surveyEngine.processAnswer(current.session, SHALLOW_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L2');

    // L2: поверхностный → L3
    current = await surveyEngine.processAnswer(current.session, SHALLOW_L2_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L3');

    // L3: очень поверхностный ответ (1 слово) → depthReached: "L3" → всё равно переход
    // Ключевой тест: БЕЗ БЕСКОНЕЧНОГО ЦИКЛА
    current = await surveyEngine.processAnswer(current.session, 'Ну.');

    assert(current.session.template.subsection === '1.2',
      `Shallow L3 should still advance (no loop), got sub=${current.session.template.subsection}`);
    assert.strictEqual(current.session.template.depth, 'L1',
      'Depth resets to L1');

    const savedSession = await sessionManager.getSession(current.session.sessionId);
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L3',
      'depthReached should be L3 even with minimal L3 answer');

    console.log('✓ testFullL1toL2toL3Cycle_ShallowL3');
  } finally {
    cleanup(tmpDir);
  }
}

async function testFullL1toL2toL3Cycle_MultipleSubsections() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let current = await surveyEngine.startSurvey(session);

    // === Блок 1, подраздел 1.1 — L3 (shallow) ===
    current = await surveyEngine.processAnswer(current.session, SHALLOW_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L2');
    current = await surveyEngine.processAnswer(current.session, SHALLOW_L2_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L3');
    current = await surveyEngine.processAnswer(current.session, 'Проблема в людях.');
    assert.strictEqual(current.session.template.subsection, '1.2',
      '1.1 shallow L3 → 1.2');

    // === Блок 1, подраздел 1.2 — L3 (deep) ===
    current = await surveyEngine.processAnswer(current.session, SHALLOW_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L2');
    current = await surveyEngine.processAnswer(current.session, SHALLOW_L2_ANSWER);
    assert.strictEqual(current.session.template.depth, 'L3');
    current = await surveyEngine.processAnswer(current.session, DEEP_L2_ANSWER);
    assert.strictEqual(current.session.template.subsection, '1.3',
      '1.2 deep L3 → 1.3');

    // === Блок 1, подраздел 1.3 — L1 deep → reflection ===
    current = await surveyEngine.processAnswer(current.session, DEEP_L1_ANSWER);
    assert.strictEqual(current.action, 'reflection_needed',
      '1.3 L1 deep → reflection');
    current = await surveyEngine.processAnswer(current.session, 'да');
    assert.strictEqual(current.session.template.block, 2,
      'After block 1 complete → block 2');
    assert.strictEqual(current.session.template.subsection, '2.1',
      'Block 2, subsection 2.1');

    const savedSession = await sessionManager.getSession(current.session.sessionId);
    assert.strictEqual(savedSession.answers['1.1'].depthReached, 'L3',
      '1.1 depthReached L3');
    assert.strictEqual(savedSession.answers['1.2'].depthReached, 'L3',
      '1.2 depthReached L3');
    assert.strictEqual(savedSession.answers['1.3'].depthReached, 'L1',
      '1.3 depthReached L1 (deep L1 → reflection → confirm)');

    console.log('✓ testFullL1toL2toL3Cycle_MultipleSubsections');
  } finally {
    cleanup(tmpDir);
  }
}

async function testL3Transition_RisksCollected() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    let result = await surveyEngine.startSurvey(session);

    // L1 shallow → L2
    result = await surveyEngine.processAnswer(result.session, SHALLOW_ANSWER);
    assert.strictEqual(result.session.template.depth, 'L2');

    // L2 shallow → L3
    result = await surveyEngine.processAnswer(result.session, SHALLOW_L2_ANSWER);
    assert.strictEqual(result.session.template.depth, 'L3');

    // L3: ответ с рисками
    const riskyL3Answer = 'Есть риск, что пользователи не примут новую систему. ' +
      'Проблема в интеграции — нет API у старой системы. ' +
      'Из-за этого можем потерять бюджет на 3 месяца.';

    result = await surveyEngine.processAnswer(result.session, riskyL3Answer);

    const savedSession = await sessionManager.getSession(result.session.sessionId);
    if (savedSession.risks && savedSession.risks.length > 0) {
      const riskTexts = savedSession.risks.map(r => r.text.toLowerCase());
      const hasRiskKeyword = riskTexts.some(t => t.includes('риск') || t.includes('проблем'));
      assert(hasRiskKeyword,
        'Risks from L3 should contain risk-related words');
    }

    console.log('✓ testL3Transition_RisksCollected');
  } finally {
    cleanup(tmpDir);
  }
}

async function testL3_Tone_NoIrritation() {
  const { surveyEngine } = await setup();

  // Проверяем, что L3-вопрос не содержит раздражения или недовольства
  const question = surveyEngine._formatL3Question('1.1', {
    L1: 'Надо автоматизировать закупки.',
    L2: 'Ну, просто всё вручную.'
  });

  const irritationPhrases = [
    'вы уже говорили', 'повторяю', 'опять', 'снова',
    'непонятно', 'раздража', 'надоед', 'устал', 'достал'
  ];

  for (const phrase of irritationPhrases) {
    assert(!question.toLowerCase().includes(phrase),
      `L3 question should not contain irritation phrase: "${phrase}"`);
  }

  assert(question.includes('Чтобы понять коренную причину'),
    'L3 should have neutral root cause explanation');

  console.log('✓ testL3_Tone_NoIrritation');
}

// ==================== Запуск ====================

async function runAllTests() {
  const tests = [
    // _isL1DeepEnough
    testIsL1DeepEnough_DeepAnswer,
    testIsL1DeepEnough_ThreeSentences,
    testIsL1DeepEnough_TwoFacts,
    testIsL1DeepEnough_Shallow,
    // buildReflection
    testBuildReflection_Basic,
    testBuildReflection_QuoteLength,
    testBuildReflection_EmptyAnswer,
    // processAnswer L1
    testProcessAnswer_L1Deep_ReturnsReflection,
    testProcessAnswer_L1Shallow_GoesToL2,
    testProcessAnswer_L1VeryShort_GoesToL2,
    // _handleReflectionConfirm
    testReflectionConfirm_Yes_AdvancesToNextSubsection,
    testReflectionConfirm_YesVariant_Confirms,
    testReflectionConfirm_Correction_Reevaluates,
    testReflectionConfirm_ShallowCorrection_GoesToL2,
    testReflectionConfirm_NotConfirmation_TreatedAsCorrection,
    // Full L1 cycles
    testFullL1Cycle_AcrossMultipleSubsections,
    testFullL1Cycle_MixedDepths,
    testL1Depth_ScoreEdgeCases,
    // _extractKeyPhrase (Story 2.3)
    testExtractKeyPhrase_Basic,
    testExtractKeyPhrase_ShortAnswer,
    testExtractKeyPhrase_OneWord,
    testExtractKeyPhrase_TwoWords,
    testExtractKeyPhrase_Empty,
    // _formatL2Question (Story 2.3)
    testFormatL2Question_Basic,
    testFormatL2Question_WithContext,
    testFormatL2Question_ErrorHandling,
    testFormatL2Question_ValidTemplateContent,
    // processAnswer L2 (Story 2.3)
    testProcessAnswer_L1Shallow_L2FormattedQuestion,
    testProcessAnswer_L1Shallow_L2ContextAware,
    testProcessAnswer_L1Shallow_L2MediumScore,
    testProcessAnswer_L2Deep_AdvanceToNextSubsection,
    testProcessAnswer_L2Shallow_GoesToL3,
    testProcessAnswer_L2toL3_WithContext,
    // Full cycles (Story 2.3 + 2.4)
    testFullL1toL2Cycle,
    testFullL1toL2toL3Cycle,
    testL2Transition_RisksCollected,
    // L3 formatting (Story 2.4)
    testFormatL3Question_Basic,
    testFormatL3Question_WithContext,
    testFormatL3Question_WithL1ContextOnly,
    testFormatL3Question_WithL2ContextOnly,
    testFormatL3Question_ErrorHandling,
    testFormatL3Question_ValidTemplateContent,
    // L3 processAnswer (Story 2.4)
    testProcessAnswer_L1toL2toL3_QuestionFormat,
    testProcessAnswer_L3Deep_AdvanceToNextSubsection,
    testProcessAnswer_L3Shallow_AdvanceToNextSubsection,
    testProcessAnswer_L3_depthReached_IsL3,
    testProcessAnswer_L3Shallow_depthReachedIsL3,
    testProcessAnswer_L3_ContextRelevance,
    testProcessAnswer_L3_MaxDepthNoLoop,
    testProcessAnswer_L3_NoReflectionPending,
    testProcessAnswer_L3Shallow_NoReflectionPending,
    // L3 full cycles (Story 2.4)
    testFullL1toL2toL3Cycle_DeepL3,
    testFullL1toL2toL3Cycle_ShallowL3,
    testFullL1toL2toL3Cycle_MultipleSubsections,
    testL3Transition_RisksCollected,
    testL3_Tone_NoIrritation
  ];

  let passed = 0;
  let failed = 0;

  console.log('\n=== Depth Levels Tests (Stories 2.2, 2.3, 2.4) ===\n');

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
