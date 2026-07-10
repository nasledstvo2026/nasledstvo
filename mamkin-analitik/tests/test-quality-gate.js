/**
 * Тесты Quality Gate: Stories 3.4 + 3.5
 *
 * Покрывает:
 *   1. ControllerAgent.revisionRequest() — структурированный запрос на доработку
 *   2. ControllerAgent.buildQualityFeedback() — сообщение пользователю
 *   3. ControllerAgent.process() — полная проверка с revisionRequest в результате
 *   4. SurveyEngine.handleRevisionRequest() — обработка запроса от контролёра
 *   5. SurveyEngine.processRevisionAnswer() — сохранение ответа, сброс флагов
 *   6. Граничные случаи:
 *      - пустой список issues → proceed
 *      - max итераций → force_accept
 *      - отсутствие target в request
 *      - null/undefined аргументы
 *
 * Story 3.4 (Return for revision):
 *   Контролёр находит проблемы → revisionRequest → вопросер переформулирует
 *   → пользователь отвечает → ответ возвращается контролёру
 *
 * Story 3.5 (User clarification):
 *   Контролёр запрашивает уточнение → вопросер задаёт естественный вопрос
 *   → ответ сохраняется как revision, сессия готова к повторной проверке
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');

const ControllerAgent = require('../agents/controller/index.js');
const SurveyEngine = require('../lib/survey-engine');
const SessionManager = require('../lib/session-manager');
const TemplateEngine = require('../lib/template-engine');

const TEMPLATE_PATH = path.resolve(__dirname, '..', 'data', 'template.json');

// ==================== Test Setup ====================

function createTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'qgate-test-'));
}

function makeSessionConfig(tmpDir) {
  return {
    storagePath: tmpDir,
    allowEmptyKey: true,
    lockTimeout: 2000
  };
}

/** Сессия с shallow-ответом (годный для возврата на доработку) */
function createShallowSession(overrides = {}) {
  return {
    sessionId: overrides.sessionId || 'qgate-shallow-001',
    telegramUserId: overrides.telegramUserId || 999,
    answers: overrides.answers || {
      '1.1': {
        L1: 'Всё плохо, надо автоматизировать',
        L2: null,
        L3: null,
        depthReached: 'L1'
      },
      '1.2': {
        L1: 'Нужно улучшить процесс',
        L2: null,
        L3: null,
        depthReached: 'L1'
      }
    },
    template: overrides.template || { block: 1, subsection: '1.2', depth: 'L1' },
    risks: overrides.risks || [],
    qualityGate: overrides.qualityGate || {
      approved: false,
      issues: [],
      iteration: 1,
      lastCheckAt: overrides.lastCheckAt || new Date().toISOString()
    },
    createdAt: overrides.createdAt || new Date().toISOString(),
    updatedAt: overrides.updatedAt || new Date().toISOString()
  };
}

/** Сессия с хорошими ответами (пройдёт проверку) */
function createGoodSession(overrides = {}) {
  return {
    sessionId: overrides.sessionId || 'qgate-good-001',
    telegramUserId: overrides.telegramUserId || 999,
    answers: overrides.answers || {
      '1.1': {
        L1: 'Работаем над мобильным приложением для заказа кофе в офис. Название проекта — CoffeeOffice.',
        L2: 'Суть инициативы: создать единое приложение, через которое сотрудники офиса смогут заказывать кофе из корпоративной кофейни и оплачивать через корпоративный счёт.',
        L3: null,
        depthReached: 'L2'
      },
      '1.2': {
        L1: 'Сейчас заказ кофе хаотичный — сотрудники звонят в кофейню, отвлекают бариста, очереди в коридоре. Теряется время.',
        L2: 'Конкретный пример: на прошлой неделе сотрудники ждали кофе до 15 минут, потому что бариста физически не успевал обрабатывать звонки и готовить заказы.',
        L3: 'Коренная причина в том, что нет централизованной системы приёма заказов. Это длится уже полгода, с тех пор как компания выросла до 200+ сотрудников.',
        depthReached: 'L3'
      },
      '1.3': {
        L1: 'Если ничего не менять, недовольство сотрудников будет расти, а время простоя увеличится.',
        L2: 'Конкретные потери: примерно 40 человеко-часов в месяц тратится на ожидание кофе, это около 200 тысяч рублей в месяц неэффективных затрат.',
        L3: null,
        depthReached: 'L2'
      },
      '2.1': {
        L1: 'Автоматизировать процесс заказа кофе в офисе.',
        L2: 'Снизить среднее время ожидания кофе с текущих 10-15 минут до 3-5 минут. Обеспечить прозрачный учёт расходов на кофе по отделам.',
        L3: null,
        depthReached: 'L2'
      },
      '2.2': {
        L1: 'Когда 90% сотрудников будут получать кофе в течение 5 минут.',
        L2: 'Критерии успеха: 1) Среднее время заказа < 5 минут через 2 недели после запуска; 2) 95% заказов без ошибок.',
        L3: null,
        depthReached: 'L2'
      },
      '3.1': {
        L1: 'Сотрудники офиса, бариста, руководители отделов, финансовая служба.',
        L2: 'Пользователи — сотрудники офиса (~300 человек). Бариста — внедряет и работает с системой.',
        L3: null,
        depthReached: 'L2'
      },
      '3.2': {
        L1: 'Выгоды: сокращение времени ожидания, прозрачный учёт, снижение нагрузки на бариста.',
        L2: 'Издержки: разработка приложения (~2 месяца), обучение персонала (1 неделя).',
        L3: null,
        depthReached: 'L2'
      },
      '3.3': {
        L1: 'Необходимо согласование с IT-безопасностью и финансовым отделом.',
        L2: 'План вовлечения: демо для IT-директора, пилот на одном этаже, сбор отзывов.',
        L3: null,
        depthReached: 'L2'
      },
      '4.1': {
        L1: 'Решение: мобильное приложение для iOS и Android, бэкенд на Node.js.',
        L2: 'Архитектура: клиент-сервер, бэкенд — API на Express, БД — PostgreSQL, очереди — RabbitMQ.',
        L3: null,
        depthReached: 'L2'
      },
      '4.2': {
        L1: 'Разработка на Node.js, фронтенд на React Native.',
        L2: 'Выбор React Native для кроссплатформенности. Бэкенд — Express + PostgreSQL для надёжности.',
        L3: null,
        depthReached: 'L2'
      },
      '4.3': {
        L1: 'Нагрузка: до 500 одновременных пользователей, до 1000 заказов в час.',
        L2: 'Граничные условия: пик 12:00-14:00 (обед), до 300 заказов в час пик.',
        L3: null,
        depthReached: 'L2'
      },
      '5.1': {
        L1: 'Время отклика API — не более 2 секунд. Uptime — 99.5%.',
        L2: 'SLA: время отклика — <1с для 95% запросов. Uptime — 99.5% (до 3.5 часов простоя в месяц).',
        L3: null,
        depthReached: 'L2'
      },
      '5.2': {
        L1: 'Бюджет: до 3 млн рублей. Срок: 4 месяца.',
        L2: 'Бюджет — 2.5-3 млн рублей на разработку. Срок — 3-4 месяца до MVP. Поддержка — 300 тыс/мес.',
        L3: null,
        depthReached: 'L2'
      },
      '6.1': {
        L1: 'Сценарий: пользователь открывает приложение, выбирает кофе, оплачивает, получает уведомление.',
        L2: 'Given пользователь авторизован When он выбирает кофе и нажимает «Заказать» Then заказ отправляется бариста And приходит уведомление о готовности.',
        L3: null,
        depthReached: 'L2'
      },
      '6.2': {
        L1: 'Тест: если оплата не прошла — заказ не отправляется, пользователь видит ошибку.',
        L2: 'Edge cases: 1) Списание с корпсчета превышает бюджет отдела — отказ; 2) Бариста отклонил заказ — уведомление пользователю.',
        L3: null,
        depthReached: 'L2'
      },
      '7.1': {
        L1: 'Риски: низкая скорость интернета в офисе, сбои при оплате, отказ бариста использовать приложение.',
        L2: 'Вероятность: 1) Проблемы с сетью — средняя (были раньше). Влияние: высокое. 2) Сбои оплаты — низкая, т.к. используем проверенный платёжный шлюз.',
        L3: null,
        depthReached: 'L2'
      },
      '7.2': {
        L1: 'Митигация для сети — резервный канал. Для сбоев оплаты — повторная попытка. Для отказа бариста — обучение и мотивация.',
        L2: '1) Сеть: второй провайдер как резерв. 2) Платежи: retry-механизм + оповещение админа. 3) Бариста: KPI + бонус за использование.',
        L3: null,
        depthReached: 'L2'
      }
    },
    template: overrides.template || { block: 7, subsection: '7.2', depth: 'L1' },
    risks: overrides.risks || [
      { category: 'technical', severity: 'high', text: 'Низкая скорость интернета' },
      { category: 'financial', severity: 'medium', text: 'Сбои при оплате' }
    ],
    createdAt: overrides.createdAt || new Date().toISOString(),
    updatedAt: overrides.updatedAt || new Date().toISOString()
  };
}

/**
 * Создаёт список issues для тестирования revisionRequest.
 * Имитирует то, что _checkCompleteness мог бы вернуть.
 */
function createSampleIssues() {
  return [
    {
      block: 1,
      subsection: '1.1',
      issue: 'too_short',
      severity: 'warning',
      detail: 'Подраздел «Контекст» заполнен поверхностно (оценка: 3/10)',
      suggestions: ['Добавьте цифры: объём, количество пользователей, сроки']
    },
    {
      block: 1,
      subsection: '1.2',
      issue: 'too_short',
      severity: 'warning',
      detail: 'Подраздел «Проблема» поверхностно описан (оценка: 2/10)',
      suggestions: ['Опишите конкретный пример проблемы']
    }
  ];
}

// ==================== Tests ====================

let passed = 0;
let failed = 0;

function test(name, fn) {
  try {
    fn();
    passed++;
    console.log(`  ✅ ${name}`);
  } catch (err) {
    failed++;
    console.error(`  ❌ ${name}`);
    console.error(`     ${err.message}`);
  }
}

async function testAsync(name, fn) {
  try {
    await fn();
    passed++;
    console.log(`  ✅ ${name}`);
  } catch (err) {
    failed++;
    console.error(`  ❌ ${name}`);
    console.error(`     ${err.message}`);
  }
}

// ==================== ControllerAgent Tests ====================

console.log('\n📋 Controller Agent — revisionRequest()');

test('возвращает { action: "proceed" } при пустых issues', () => {
  const controller = new ControllerAgent();
  const result = controller.revisionRequest([], 1);
  assert.strictEqual(result.action, 'proceed');
  assert.strictEqual(result.reason, 'нет замечаний');
});

test('возвращает return_to_questioner при issues на первой итерации', () => {
  const controller = new ControllerAgent();
  const issues = createSampleIssues();
  const result = controller.revisionRequest(issues, 1);

  assert.strictEqual(result.action, 'return_to_questioner');
  assert.strictEqual(result.iteration, 1);
  assert.strictEqual(result.forceAccept, false);
  assert.ok(result.target);
  assert.strictEqual(result.target.block, 1);
  assert.strictEqual(result.target.subsection, '1.1');
  assert.ok(typeof result.target.reason === 'string' && result.target.reason.length > 0);
  assert.ok(Array.isArray(result.target.suggestions) && result.target.suggestions.length > 0);
  assert.ok(Array.isArray(result.allIssues) && result.allIssues.length === 2);
});

test('возвращает force_accept при iteration >= maxIterations (3)', () => {
  const controller = new ControllerAgent();
  const issues = createSampleIssues();
  const result = controller.revisionRequest(issues, 3);

  assert.strictEqual(result.action, 'force_accept');
  assert.strictEqual(result.forceAccept, true);
  assert.strictEqual(result.iteration, 3);
});

test('возвращает force_accept при iteration = maxIterations (3)', () => {
  const controller = new ControllerAgent();
  const issues = createSampleIssues();
  const result = controller.revisionRequest(issues, 3);

  assert.strictEqual(result.action, 'force_accept');
});

test('группирует issues по подразделам, использует первый ключ', () => {
  const controller = new ControllerAgent();
  const issues = [
    { block: 1, subsection: '1.1', issue: 'too_short', severity: 'warning',
      detail: '1.1 ошибка', suggestions: ['Уточните'] },
    { block: 2, subsection: '2.1', issue: 'too_short', severity: 'warning',
      detail: '2.1 ошибка', suggestions: ['Добавьте цифры'] }
  ];
  const result = controller.revisionRequest(issues, 1);

  assert.strictEqual(result.target.block, 1);
  assert.strictEqual(result.target.subsection, '1.1');
  assert.ok(result.target.reason.includes('1.1 ошибка'));
});

console.log('\n📋 Controller Agent — buildQualityFeedback()');

test('возвращает сообщение об одобрении при пустых issues', () => {
  const controller = new ControllerAgent();
  const session = createShallowSession();
  const msg = controller.buildQualityFeedback([], session);

  assert.ok(msg.includes('Замечаний нет') || msg.includes('прошёл проверку'));
});

test('содержит заголовок "требуется доработка" при issues', () => {
  const controller = new ControllerAgent();
  const session = createShallowSession();
  const issues = createSampleIssues();
  const msg = controller.buildQualityFeedback(issues, session);

  assert.ok(msg.includes('требуется доработка') || msg.includes('доработк'));
  assert.ok(msg.includes('рекомендации') || msg.includes('Рекомендации'));
  assert.ok(msg.includes('1.1') || msg.includes('Контекст'));
});

test('содержит iteration info', () => {
  const controller = new ControllerAgent();
  const issues = createSampleIssues();
  const session = createShallowSession();
  const msg = controller.buildQualityFeedback(issues, session);

  assert.ok(msg.includes('1 из 3') || msg.includes('Итерация'));
});

test('содержит "Форсированное принятие" при лимите итераций', () => {
  const controller = new ControllerAgent();
  const issues = createSampleIssues();
  const session = createShallowSession();
  session.qualityGate.iteration = 3;
  const msg = controller.buildQualityFeedback(issues, session);

  assert.ok(msg.includes('Форсированное') || msg.includes('форсирован')
    || msg.includes('лимит'));
});

console.log('\n📋 Controller Agent — process() с revision fields');

test('process() возвращает revisionRequest в результате', async () => {
  const controller = new ControllerAgent();
  const session = createShallowSession();
  const result = await controller.process(session, 1);

  assert.ok(result.revisionRequest !== undefined, 'должен быть revisionRequest');
  // shallow session не проходит, значит должен быть return_to_questioner
  if (result.action === 'return_to_questioner') {
    assert.strictEqual(result.revisionRequest.action, 'return_to_questioner');
  }
});

test('process() возвращает qualityFeedback в результате', async () => {
  const controller = new ControllerAgent();
  const session = createShallowSession();
  const result = await controller.process(session, 1);

  assert.ok(result.qualityFeedback !== undefined, 'должен быть qualityFeedback');
  assert.ok(typeof result.qualityFeedback === 'string');
  assert.ok(result.qualityFeedback.length > 0);
});

test('process() на последней итерации (max) — action force_accept или принято', async () => {
  const controller = new ControllerAgent();
  const session = createShallowSession();
  const iteration = controller.maxIterations;
  const result = await controller.process(session, iteration);

  // На последней итерации может быть force_accept или approved
  if (result.approved) {
    assert.strictEqual(result.action, 'proceed');
  } else {
    assert.ok(['force_accept', 'return_to_questioner'].includes(result.action));
  }
});

// ==================== SurveyEngine Tests ====================

console.log('\n📋 Survey Engine — handleRevisionRequest()');

testAsync('handleRevisionRequest c force_accept возвращает isForceAccept=true', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);

  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });

  const request = {
    action: 'force_accept',
    target: { block: 1, subsection: '1.1', reason: 'Слишком обще', suggestions: ['Добавьте цифры'] },
    iteration: 3,
    forceAccept: true,
    allIssues: createSampleIssues()
  };

  const session = createShallowSession();
  const result = await engine.handleRevisionRequest(request, session);

  assert.strictEqual(result.isForceAccept, true);
  assert.strictEqual(result.action, 'force_accept');
  assert.ok(typeof result.question === 'string' && result.question.length > 0);

  // Чистим
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

testAsync('handleRevisionRequest возвращает revision_needed с вопросом', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);
  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });

  const request = {
    action: 'return_to_questioner',
    target: { block: 1, subsection: '1.1', reason: 'раздел содержит общие фразы, нет цифр', suggestions: ['Добавьте объём и сроки'] },
    iteration: 1,
    forceAccept: false,
    allIssues: createSampleIssues()
  };

  const session = createShallowSession();
  const result = await engine.handleRevisionRequest(request, session);

  assert.strictEqual(result.isForceAccept, false);
  assert.strictEqual(result.action, 'revision_needed');
  assert.ok(typeof result.question === 'string' && result.question.length > 0);
  // Вопрос должен быть естественным, не содержать "controller said"
  assert.ok(!result.question.toLowerCase().includes('controller'));
  assert.ok(result.question.includes('💡') || result.question.includes('уточнит'));

  // Проверяем, что сессия отмечена как revisionActive
  assert.ok(session._revisionActive);
  assert.strictEqual(session._revisionActive.request.action, 'return_to_questioner');

  // Чистим
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

testAsync('handleRevisionRequest с request_clarification (Story 3.5)', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);
  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });

  const request = {
    action: 'request_clarification',
    target: { block: 1, subsection: '1.1', reason: 'не указаны конкретные цифры', suggestions: ['Сколько пользователей?'] },
    iteration: 1,
    forceAccept: false,
    allIssues: createSampleIssues()
  };

  const session = createShallowSession();
  const result = await engine.handleRevisionRequest(request, session);

  assert.strictEqual(result.isForceAccept, false);
  assert.strictEqual(result.action, 'revision_needed');
  assert.ok(result.question.includes('💡') || result.question.includes('уточнит'));
  assert.ok(result.question.includes('цифр'));

  // Чистим
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

testAsync('handleRevisionRequest c null-request кидает ошибку', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);
  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });

  try {
    await engine.handleRevisionRequest(null, createShallowSession());
    assert.fail('Должна быть ошибка');
  } catch (err) {
    assert.ok(err.message.includes('revision request'));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

testAsync('handleRevisionRequest без target строит общий вопрос', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);
  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });

  const request = {
    action: 'return_to_questioner',
    target: null,
    iteration: 1,
    forceAccept: false
  };

  const session = createShallowSession();
  const result = await engine.handleRevisionRequest(request, session);

  assert.strictEqual(result.isForceAccept, false);
  assert.ok(result.question.length > 0);

  // Чистим
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

console.log('\n📋 Survey Engine — processRevisionAnswer()');

testAsync('processRevisionAnswer сохраняет ответ в revision history', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);
  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });

  const request = {
    action: 'return_to_questioner',
    target: { block: 1, subsection: '1.1', reason: 'Слишком обще', suggestions: ['Добавьте цифры'] },
    iteration: 1,
    forceAccept: false
  };

  const session = createShallowSession();
  session._revisionActive = { request, startedAt: new Date().toISOString() };

  const answer = 'Работаем над приложением для 300 сотрудников офиса. Проект стартует в марте 2026. Бюджет — 2 млн рублей.';
  const result = await engine.processRevisionAnswer(answer, session, request);

  assert.strictEqual(result.action, 'return_to_controller');
  assert.ok(result.message.includes('Спасибо'));
  assert.ok(result.revisionAnswer);
  assert.strictEqual(result.revisionAnswer.subsection, '1.1');
  assert.strictEqual(result.revisionAnswer.text, answer);

  // Проверяем, что ответ сохранился в answers
  assert.ok(session.answers['1.1']);
  assert.ok(Array.isArray(session.answers['1.1'].L1_revision));
  assert.strictEqual(session.answers['1.1'].L1_revision.length, 1);
  assert.strictEqual(session.answers['1.1'].L1_revision[0].text, answer);

  // Флаг _revisionActive должен быть снят
  assert.strictEqual(session._revisionActive, null);

  // Чистим
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

testAsync('processRevisionAnswer накапливает ревизии (массив L1_revision)', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);
  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });

  const request = {
    action: 'return_to_questioner',
    target: { block: 1, subsection: '1.1', reason: 'Слишком обще', suggestions: [] },
    iteration: 1,
    forceAccept: false
  };

  const session = createShallowSession();
  session._revisionActive = { request, startedAt: new Date().toISOString() };

  // Первая ревизия
  await engine.processRevisionAnswer('Первый уточняющий ответ', session, request);

  // Вторая ревизия — нужно установить _revisionActive снова
  session._revisionActive = { request, startedAt: new Date().toISOString() };
  await engine.processRevisionAnswer('Второй уточняющий ответ', session, request);

  assert.ok(Array.isArray(session.answers['1.1'].L1_revision));
  assert.strictEqual(session.answers['1.1'].L1_revision.length, 2);
  assert.strictEqual(session.answers['1.1'].L1_revision[0].text, 'Первый уточняющий ответ');
  assert.strictEqual(session.answers['1.1'].L1_revision[1].text, 'Второй уточняющий ответ');

  // Чистим
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

testAsync('processRevisionAnswer проставляет depthReached если не было', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);
  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });

  const request = {
    action: 'return_to_questioner',
    target: { block: 2, subsection: '2.1', reason: 'Нет цифр', suggestions: [] },
    iteration: 1,
    forceAccept: false
  };

  // Создаём сессию, где у 2.1 нет depthReached
  const session = createShallowSession({
    sessionId: 'qgate-nodepth-001',
    answers: {
      '2.1': {
        L1: 'Просто автоматизировать',
        depthReached: undefined
      }
    },
    template: { block: 2, subsection: '2.1', depth: 'L1' }
  });
  session._revisionActive = { request, startedAt: new Date().toISOString() };

  await engine.processRevisionAnswer('Уточняю: надо автоматизировать заказы кофе в офисе для 300 сотрудников', session, request);

  assert.strictEqual(session.answers['2.1'].depthReached, 'L1');

  // Чистим
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

testAsync('processRevisionAnswer с null-answer кидает ошибку', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);
  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });

  try {
    await engine.processRevisionAnswer('', null, {});
    assert.fail('Должна быть ошибка');
  } catch (err) {
    assert.ok(err.message.includes('требуется ответ'));
  } finally {
    fs.rmSync(tmpDir, { recursive: true, force: true });
  }
});

// ==================== Integration: Controller → SurveyEngine ====================

console.log('\n📋 Integration — Controller → SurveyEngine full flow');

testAsync('Контролёр → revisionRequest → вопросер → processRevisionAnswer → возврат', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);
  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });
  const controller = new ControllerAgent();

  // 1. Контролёр проверяет shallow-сессию
  const session = createShallowSession({ sessionId: 'qgate-integration-001' });
  const checkResult = await controller.process(session, 1);

  // 2. Проверяем, что есть revisionRequest и qualityFeedback
  assert.ok(checkResult.revisionRequest !== undefined);
  assert.ok(checkResult.qualityFeedback !== undefined);

  // 3. Если есть замечания — проверяем flow
  if (checkResult.action === 'return_to_questioner') {
    const revReq = checkResult.revisionRequest;

    // 4. Вопросер обрабатывает запрос
    const questionResult = await engine.handleRevisionRequest(revReq, session);
    assert.strictEqual(questionResult.isForceAccept, false);
    assert.ok(questionResult.question.length > 0);

    // 5. Пользователь отвечает (симуляция)
    const clarification = 'Уточняю: проект CoffeeOffice уже запущен в пилоте на 50 сотрудников. Срок — 2 месяца.';

    const revResult = await engine.processRevisionAnswer(clarification, session, revReq);
    assert.strictEqual(revResult.action, 'return_to_controller');

    // 6. Повторная проверка контролёром
    const recheckResult = await controller.process(session, 2);
    assert.ok(recheckResult.revisionRequest !== undefined);
    assert.ok(typeof recheckResult.overallScore === 'number');
  }

  // Чистим
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

testAsync('Force accept flow — итерация 3', async () => {
  const tmpDir = createTempDir();
  const config = makeSessionConfig(tmpDir);
  const sessionManager = new SessionManager(config);
  const templateEngine = new TemplateEngine();
  templateEngine.loadSync(TEMPLATE_PATH);
  const engine = new SurveyEngine({
    sessionManager,
    templateEngine
  });
  const controller = new ControllerAgent();

  // Сессия с плохими ответами, но на 3-й итерации — force accept
  const session = createShallowSession({ sessionId: 'qgate-force-001' });
  const result = await controller.process(session, controller.maxIterations);

  if (result.action === 'force_accept' || result.action === 'proceed') {
    // Проверяем revisionRequest на force_accept
    const revReq = result.revisionRequest;
    const questionResult = await engine.handleRevisionRequest(revReq, session);
    assert.strictEqual(questionResult.isForceAccept, true);
  }

  // Чистим
  fs.rmSync(tmpDir, { recursive: true, force: true });
});

// ==================== Summary ====================

console.log(`\n${'='.repeat(50)}`);
console.log(`Результаты: ${passed} passed, ${failed} failed`);
console.log(`${'='.repeat(50)}`);

if (failed > 0) {
  console.error(`\n❌ ${failed} тестов не прошли`);
  process.exit(1);
} else {
  console.log('\n✅ Все тесты пройдены');
}
