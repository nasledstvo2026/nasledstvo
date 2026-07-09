/**
 * Тесты Draft Generator (Story 3.6 — Final Draft Formation)
 *
 * Проверяет:
 *   1. lib/draft-generator.js — основные методы
 *      - generateDraft() — финальная сборка черновика
 *      - consolidateRisks() — консолидация рисков
 *      - addDepthLabels() — маркировка глубины
 *      - markAsDraft() — статус draft_ready
 *   2. Структура draft
 *      - 7 блоков (immutable, следует template.json)
 *      - Каждый подраздел: 1-3 параграфа + depthReached
 *      - Консолидированные риски
 *   3. Валидация
 *      - Контролёр должен быть approved
 *      - Ошибка при отсутствии qualityGate
 *      - Ошибка при отсутствии answers
 *   4. Интеграция с существующими компонентами
 *      - TemplateEngine (валидация 7 блоков)
 *      - Session Context
 *      - Quality Gate
 */

const path = require('path');
const assert = require('assert');
const TemplateEngine = require('../lib/template-engine');
const DraftGenerator = require('../lib/draft-generator');

// ==================== Test Data ====================

/**
 * Создаёт полный Session Context с ответами на все 7 блоков
 * и одобренным qualityGate.
 */
function createApprovedSession(overrides = {}) {
  return {
    sessionId: overrides.sessionId || 'test-draft-session-001',
    telegramUserId: overrides.telegramUserId || 123456789,
    username: overrides.username !== undefined ? overrides.username : 'test_user',
    status: overrides.status || 'completed',
    createdAt: '2026-07-08T12:00:00.000Z',
    updatedAt: '2026-07-08T12:35:00.000Z',
    completedAt: '2026-07-08T12:30:00.000Z',
    answers: overrides.answers || {
      // Блок 1: Контекст и проблема
      '1.1': {
        L1: 'Работаем над мобильным приложением для заказа кофе в офис. Название проекта — CoffeeOffice.',
        L2: 'Суть инициативы: создать единое приложение, через которое сотрудники офиса смогут заказывать кофе из корпоративной кофейни и оплачивать через корпоративный счёт.',
        L3: null,
        depthReached: 'L2'
      },
      '1.2': {
        L1: 'Сейчас заказ кофе хаотичный — сотрудники звонят в кофейню, отвлекают бариста, очереди в коридоре.',
        L2: 'Конкретный пример: на прошлой неделе сотрудники ждали кофе до 15 минут, потому что бариста физически не успевал.',
        L3: 'Коренная причина в том, что нет централизованной системы приёма заказов. Это длится уже полгода.',
        depthReached: 'L3'
      },
      '1.3': {
        L1: 'Если ничего не менять, недовольство сотрудников будет расти.',
        L2: 'Конкретные потери: примерно 40 человеко-часов в месяц тратится на ожидание кофе, это около 200 тысяч рублей в месяц.',
        L3: 'Через полгода ситуация ухудшится — компания планирует нанять ещё 100 человек.',
        depthReached: 'L3'
      },
      // Блок 2: Цель и измерение
      '2.1': {
        L1: 'Автоматизировать процесс заказа кофе в офисе.',
        L2: 'Снизить среднее время ожидания кофе с 10-15 минут до 3-5 минут.',
        L3: 'KPI: время ожидания не более 5 минут, до 40 заказов в час, NPS не ниже 8.',
        depthReached: 'L3'
      },
      '2.2': {
        L1: 'Когда 90% сотрудников будут получать кофе в течение 5 минут.',
        L2: '1) Среднее время заказа < 5 минут, 2) 95% заказов без ошибок, 3) NPS не ниже 8.',
        L3: 'Критерии проверяются через аналитику приложения. Автоматический сбор метрик.',
        depthReached: 'L3'
      },
      // Блок 3: Стейкхолдеры и влияние
      '3.1': {
        L1: 'Сотрудники офиса, бариста, руководители отделов, финансовая служба.',
        L2: 'Пользователи — ~300 человек. Бариста — внедряет. Платит — финансовый отдел.',
        L3: 'Может заблокировать — IT-безопасность.',
        depthReached: 'L3'
      },
      '3.2': {
        L1: 'Каждая сторона хочет получить удобный и быстрый сервис.',
        L2: 'Мнение IT-безопасности критично — может заблокировать проект.',
        L3: 'Конфликт: бариста хотят простой интерфейс, IT хотят сложную аутентификацию.',
        depthReached: 'L3'
      },
      // Блок 4: Решение
      '4.1': {
        L1: 'Приложение должно позволять заказывать кофе, оплачивать и отслеживать статус.',
        L2: 'Must have: каталог напитков, заказ, оплата. Should have: история заказов.',
        L3: 'Функция заказа: выбор напитка, размера, добавок, комментарий, подтверждение.',
        depthReached: 'L3'
      },
      '4.2': {
        L1: 'Пользователь открывает приложение, выбирает кофе, оплачивает, получает уведомление.',
        L2: 'Сценарий: вход → каталог → выбор → корзина → оплата → статус готовности.',
        L3: 'Сценарий misuse: пользователь заказывает, но не забирает — через 15 мин отмена.',
        depthReached: 'L3'
      },
      '4.3': {
        L1: 'Если оплата не прошла — заказ не создаётся. Если кофейня не работает — показывать статус.',
        L2: 'Успех: заказ оплачен, кофе готов. Ошибка: платёж не прошёл — показать сообщение.',
        L3: 'Экстремум: 50+ одновременных заказов, очередь бариста — ограничение в системе.',
        depthReached: 'L3'
      },
      // Блок 5: Требования к качеству
      '5.1': {
        L1: 'Приложение должно работать быстро и быть безопасным.',
        L2: 'Время отклика < 1 секунды. Аутентификация через корпоративный SSO.',
        L3: 'Доступность 99.9%, время восстановления до 1 часа, ежедневные бэкапы.',
        depthReached: 'L3'
      },
      '5.2': {
        L1: 'Бюджет ограничен, нужен MVP за 3 месяца.',
        L2: 'Бюджет: до 2 млн рублей. Срок MVP: 3 месяца. Технологии: React Native + Node.js.',
        L3: 'Ограничения по регуляторике: ФЗ-152 (персональные данные).',
        depthReached: 'L3'
      },
      // Блок 6: Приёмка
      '6.1': {
        L1: 'Функция заказа: заказ создаётся, оплачивается, кофе готов.',
        L2: 'Given: пользователь авторизован, на странице каталога. When: выбирает напиток и нажимает «Заказать». Then: заказ отправлен, списана оплата.',
        L3: 'Принимает: руководитель отдела. Blocker: незавершённая оплата.',
        depthReached: 'L3'
      },
      // Блок 7: Риски
      '7.1': {
        L1: 'Пользователи могут не принять новое приложение, технические сбои, превышение бюджета.',
        L2: 'Технические: сбои интеграции с платёжной системой. Организационные: сопротивление персонала.',
        L3: 'Вероятность сбоя платежей — средняя, влияние — критическое. Приоритет — высокий.',
        depthReached: 'L3'
      },
      '7.2': {
        L1: 'Провести обучение персонала, сделать запасной план оплаты.',
        L2: 'Для критических рисков: резервный платёжный шлюз, план отката.',
        L3: 'Риск непринятия можно устранить через обучение. С риском сбоев придётся жить.',
        depthReached: 'L3'
      }
    },
    risks: overrides.risks || [
      {
        text: 'Пользователи могут не принять новое приложение из-за привычки к старому процессу',
        category: 'adoption',
        collectedAt: 'block_1',
        probability: 0.5,
        impact: 0.6,
        mitigation: 'Провести обучение и пилотный запуск на одном отделе'
      },
      {
        text: 'Технические сбои интеграции с корпоративной платёжной системой',
        category: 'technical',
        collectedAt: 'block_4',
        probability: 0.4,
        impact: 0.8,
        mitigation: 'Резервный платёжный шлюз, тестирование интеграции'
      },
      {
        text: 'Превышение бюджета из-за дополнительных требований',
        category: 'business',
        collectedAt: 'block_5',
        probability: 0.6,
        impact: 0.7,
        mitigation: 'Чёткое определение MVP, control change management'
      }
    ],
    qualityGate: overrides.qualityGate || {
      approved: true,
      issues: [],
      iteration: 1,
      lastCheckAt: '2026-07-08T12:34:00.000Z',
      overallScore: 8
    }
  };
}

// ==================== Test Suite ====================

async function runTests() {
  let passed = 0;
  let failed = 0;
  const failures = [];

  function test(name, fn) {
    try {
      fn();
      passed++;
      console.log(`  ✅ ${name}`);
    } catch (err) {
      failed++;
      failures.push({ name, error: err.message, stack: err.stack });
      console.log(`  ❌ ${name}: ${err.message}`);
    }
  }

  function assertIncludes(actual, expected, msg) {
    if (!actual.includes(expected)) {
      throw new Error(
        `${msg || 'String includes check failed'}: expected "${expected}" to be in "${actual.slice(0, 200)}"`
      );
    }
  }

  // ==================== Setup ====================
  console.log('\n🔧 Setting up test environment...');
  const templateEngine = new TemplateEngine();
  await templateEngine.load();
  console.log('  ✅ TemplateEngine loaded');

  const generator = new DraftGenerator({ templateEngine });
  console.log('  ✅ DraftGenerator initialized');

  // ==================== Basic API Tests ====================
  console.log('\n📋 Test Suite 1: Basic API Tests');

  test('DraftGenerator constructor sets templateEngine', () => {
    assert.strictEqual(generator.templateEngine, templateEngine);
  });

  test('DraftGenerator has all public methods', () => {
    assert.strictEqual(typeof generator.generateDraft, 'function');
    assert.strictEqual(typeof generator.consolidateRisks, 'function');
    assert.strictEqual(typeof generator.addDepthLabels, 'function');
    assert.strictEqual(typeof generator.markAsDraft, 'function');
  });

  // ==================== Generation Tests ====================
  console.log('\n📋 Test Suite 2: generateDraft()');

  test('generateDraft returns draft and session', () => {
    const session = createApprovedSession();
    const result = generator.generateDraft(session, null);
    assert.ok(result.draft);
    assert.ok(result.session);
    assert.strictEqual(result.session, session);
  });

  test('generateDraft draft has 7 blocks (follows template.json)', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    assert.strictEqual(draft.totalBlocks, 7);
    assert.strictEqual(draft.blocks.length, 7);
  });

  test('generateDraft each block has blockId, blockName, content, subsections', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    for (const block of draft.blocks) {
      assert.ok(block.blockId, `block ${block.blockId} missing blockId`);
      assert.ok(block.blockName, `block ${block.blockId} missing blockName`);
      assert.ok(block.content, `block ${block.blockId} missing content`);
      assert.ok(Array.isArray(block.subsections), `block ${block.blockId} missing subsections array`);
    }
  });

  test('generateDraft each subsection has subsectionId, subsectionName, text, depthReached, paragraphs', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    for (const block of draft.blocks) {
      for (const sub of block.subsections) {
        assert.ok(sub.subsectionId, `subsection missing id in block ${block.blockId}`);
        assert.ok(sub.subsectionName, `subsection missing name: ${sub.subsectionId}`);
        assert.ok(sub.text !== undefined, `subsection missing text: ${sub.subsectionId}`);
        assert.ok(sub.depthReached, `subsection missing depthReached: ${sub.subsectionId}`);
        assert.ok(Array.isArray(sub.paragraphs), `subsection missing paragraphs: ${sub.subsectionId}`);
      }
    }
  });

  test('generateDraft each subsection has 1-3 paragraphs', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    for (const block of draft.blocks) {
      for (const sub of block.subsections) {
        assert.ok(sub.paragraphs.length >= 1, `subsection ${sub.subsectionId} has < 1 paragraph`);
        assert.ok(sub.paragraphs.length <= 3, `subsection ${sub.subsectionId} has > 3 paragraphs (${sub.paragraphs.length})`);
      }
    }
  });

  test('generateDraft each subsection has depthLabel after addDepthLabels', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    generator.addDepthLabels(draft);
    for (const block of draft.blocks) {
      for (const sub of block.subsections) {
        assert.ok(sub.depthLabel, `subsection ${sub.subsectionId} missing depthLabel`);
      }
    }
  });

  test('generateDraft fullText is long enough for complete session', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    assert.ok(draft.fullText.length > 2000, `fullText too short: ${draft.fullText.length} chars`);
  });

  test('generateDraft fullText contains all block titles', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    const blockNames = [
      'Контекст и проблема',
      'Цель и измерение',
      'Стейкхолдеры',
      'Решение',
      'Требования к качеству',
      'Приёмка',
      'Риски'
    ];
    for (const name of blockNames) {
      assert.ok(draft.fullText.includes(name), `fullText missing block name: ${name}`);
    }
  });

  test('generateDraft draft has title, sessionId, telegramUserId, createdAt', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    assert.strictEqual(draft.title, 'Документ бизнес-требований');
    assert.strictEqual(draft.sessionId, session.sessionId);
    assert.strictEqual(draft.telegramUserId, session.telegramUserId);
    assert.ok(draft.createdAt);
  });

  test('generateDraft draft has completedSubsections and totalSubsections', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    assert.ok(draft.totalSubsections > 0);
    assert.ok(draft.completedSubsections > 0);
    assert.ok(draft.completionPercent >= 0);
  });

  test('generateDraft sets status to draft_ready after full generation', () => {
    const session = createApprovedSession();
    session.status = 'completed';
    const { draft } = generator.generateDraft(session, null);
    assert.strictEqual(session.status, 'draft_ready');
    assert.strictEqual(draft.status, 'draft_ready');
    assert.ok(session.draftReadyAt);
    assert.ok(draft.readyAt);
    assert.strictEqual(session.documentReady, true);
  });

  test('generateDraft fullText contains "Документ бизнес-требований" title', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    assert.ok(draft.fullText.includes('# Документ бизнес-требований'));
  });

  // ==================== Risk Consolidation Tests ====================
  console.log('\n📋 Test Suite 3: consolidateRisks()');

  test('consolidateRisks returns all risks from session', () => {
    const session = createApprovedSession();
    const risks = generator.consolidateRisks(session);
    assert.strictEqual(risks.total, 3);
    assert.strictEqual(risks.items.length, 3);
  });

  test('consolidateRisks groups by category', () => {
    const session = createApprovedSession();
    const risks = generator.consolidateRisks(session);
    assert.ok(risks.byCategory.adoption);
    assert.ok(risks.byCategory.technical);
    assert.ok(risks.byCategory.business);
    assert.strictEqual(risks.byCategory.adoption.length, 1);
    assert.strictEqual(risks.byCategory.technical.length, 1);
    assert.strictEqual(risks.byCategory.business.length, 1);
  });

  test('consolidateRisks preserves risk fields', () => {
    const session = createApprovedSession();
    const risks = generator.consolidateRisks(session);
    const first = risks.items[0];
    assert.ok(first.text);
    assert.ok(first.category);
    assert.ok(first.collectedAt);
  });

  test('consolidateRisks returns empty stats for no risks', () => {
    const session = createApprovedSession({ risks: [] });
    const risks = generator.consolidateRisks(session);
    assert.strictEqual(risks.total, 0);
    assert.strictEqual(risks.items.length, 0);
    assert.deepStrictEqual(risks.byCategory, {});
  });

  test('consolidateRisks handles uncategorized risks', () => {
    const session = createApprovedSession({
      risks: [{ text: 'Test risk' }]
    });
    const risks = generator.consolidateRisks(session);
    assert.strictEqual(risks.total, 1);
    assert.ok(risks.byCategory.uncategorized);
  });

  // ==================== Depth Label Tests ====================
  console.log('\n📋 Test Suite 4: addDepthLabels()');

  test('addDepthLabels sets proper label for L1 depth', () => {
    const draft = {
      blocks: [{
        subsections: [{ depthReached: 'L1' }]
      }]
    };
    generator.addDepthLabels(draft);
    assert.ok(draft.blocks[0].subsections[0].depthLabel.includes('L1'));
  });

  test('addDepthLabels sets proper label for L2 depth', () => {
    const draft = {
      blocks: [{
        subsections: [{ depthReached: 'L2' }]
      }]
    };
    generator.addDepthLabels(draft);
    assert.ok(draft.blocks[0].subsections[0].depthLabel.includes('L2'));
  });

  test('addDepthLabels sets proper label for L3 depth', () => {
    const draft = {
      blocks: [{
        subsections: [{ depthReached: 'L3' }]
      }]
    };
    generator.addDepthLabels(draft);
    assert.ok(draft.blocks[0].subsections[0].depthLabel.includes('L3'));
  });

  test('addDepthLabels sets label for none depth', () => {
    const draft = {
      blocks: [{
        subsections: [{ depthReached: 'none' }]
      }]
    };
    generator.addDepthLabels(draft);
    assert.strictEqual(draft.blocks[0].subsections[0].depthLabel, 'Не заполнено');
  });

  test('addDepthLabels sets labels for all subsections', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    generator.addDepthLabels(draft);
    for (const block of draft.blocks) {
      for (const sub of block.subsections) {
        assert.ok(sub.depthLabel, `subsection ${sub.subsectionId} missing depthLabel`);
      }
    }
  });

  // ==================== Mark as Draft Tests ====================
  console.log('\n📋 Test Suite 5: markAsDraft()');

  test('markAsDraft sets session status to draft_ready', () => {
    const session = createApprovedSession();
    session.status = 'completed';
    const draft = { status: 'draft_building' };
    generator.markAsDraft(session, draft);
    assert.strictEqual(session.status, 'draft_ready');
    assert.strictEqual(draft.status, 'draft_ready');
    assert.strictEqual(session.documentReady, true);
  });

  test('markAsDraft sets draftReadyAt timestamp', () => {
    const session = createApprovedSession();
    generator.markAsDraft(session, {});
    assert.ok(session.draftReadyAt);
    assert.ok(Date.parse(session.draftReadyAt));
  });

  test('markAsDraft updates updatedAt', () => {
    const session = createApprovedSession();
    const old = session.updatedAt;
    generator.markAsDraft(session, {});
    assert.ok(session.updatedAt >= old);
  });

  // ==================== Validation Tests ====================
  console.log('\n📋 Test Suite 6: Validation');

  test('generateDraft throws without qualityGate', () => {
    const session = createApprovedSession();
    delete session.qualityGate;
    assert.throws(() => {
      generator.generateDraft(session, null);
    }, /qualityGate отсутствует/);
  });

  test('generateDraft throws when controller not approved', () => {
    const session = createApprovedSession({
      qualityGate: { approved: false, issues: [{ issue: 'test' }], iteration: 1 }
    });
    assert.throws(() => {
      generator.generateDraft(session, null);
    }, /контролёр не одобрил/);
  });

  test('generateDraft throws without templateEngine', () => {
    const badGenerator = new DraftGenerator({ templateEngine: null });
    const session = createApprovedSession();
    assert.throws(() => {
      badGenerator.generateDraft(session, null);
    }, /TemplateEngine не подключён/);
  });

  test('generateDraft throws without answers', () => {
    const session = createApprovedSession({ answers: {} });
    assert.throws(() => {
      generator.generateDraft(session, null);
    }, /нет ответов/);
  });

  // ==================== Edge Case Tests ====================
  console.log('\n📋 Test Suite 7: Edge Cases');

  test('generateDraft handles session with context object (second param)', () => {
    const session = createApprovedSession();
    const result = generator.generateDraft(session, session);
    assert.ok(result.draft);
    assert.ok(result.session);
  });

  test('generateDraft handles session with only L1 answers', () => {
    const minimalAnswers = {
      '1.1': { L1: 'Минимальный ответ на контекст.', depthReached: 'L1' }
    };
    // Need all sections — create full but shallow
    const answers = {};
    const subKeys = ['1.1','1.2','1.3','2.1','2.2','3.1','3.2','4.1','4.2','4.3','5.1','5.2','6.1','7.1','7.2'];
    for (const key of subKeys) {
      answers[key] = { L1: `Тестовый ответ для подраздела ${key}.`, depthReached: 'L1' };
    }
    const session = createApprovedSession({ answers });
    const { draft } = generator.generateDraft(session, null);
    assert.strictEqual(draft.blocks.length, 7);
    // All L1 — check paragraphs = 1 each
    for (const block of draft.blocks) {
      for (const sub of block.subsections) {
        assert.strictEqual(sub.paragraphs.length, 1,
          `${sub.subsectionId} expected 1 paragraph for L1-only, got ${sub.paragraphs.length}`);
      }
    }
  });

  test('generateDraft handles session without risks', () => {
    const session = createApprovedSession({ risks: [] });
    const { draft } = generator.generateDraft(session, null);
    assert.strictEqual(draft.risks.total, 0);
  });

  test('generateDraft handles session with username', () => {
    const session = createApprovedSession({ username: 'Иван Петров' });
    const { draft } = generator.generateDraft(session, null);
    assert.ok(draft.fullText.includes('Иван Петров'));
    assert.strictEqual(draft.username, 'Иван Петров');
  });

  test('generateDraft handles session without username', () => {
    const session = createApprovedSession({ username: null });
    const { draft } = generator.generateDraft(session, null);
    assert.strictEqual(draft.username, null);
  });

  test('generateDraft handles session with multiple L3 answers on all blocks', () => {
    // Already using deep session — verify depth labels
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    generator.addDepthLabels(draft);
    for (const block of draft.blocks) {
      for (const sub of block.subsections) {
        assert.ok(sub.depthLabel, `subsection ${sub.subsectionId} missing depthLabel`);
        if (sub.depthReached !== 'none') {
          assert.ok(sub.depthLabel.includes('L'), `subsection ${sub.subsectionId} label doesn't include L-level`);
        }
      }
    }
  });

  test('generateDraft fullText is non-empty string', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    assert.strictEqual(typeof draft.fullText, 'string');
    assert.ok(draft.fullText.length > 0);
  });

  // ==================== Integration Tests ====================
  console.log('\n📋 Test Suite 8: Integration');

  test('generateDraft integrates with full pipeline: compiler → controller → generator', () => {
    // Simulate pipeline: session with all answers, approved qualityGate
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);

    // Verify draft structure matches template
    const template = templateEngine.getTemplate();
    assert.strictEqual(draft.totalBlocks, template.blocks.length);

    // Verify block structure
    for (let i = 0; i < template.blocks.length; i++) {
      const templateBlock = template.blocks[i];
      const draftBlock = draft.blocks[i];

      assert.strictEqual(draftBlock.blockId, templateBlock.id,
        `Block ${i + 1} id mismatch`);
      assert.strictEqual(draftBlock.blockName, templateBlock.name,
        `Block ${i + 1} name mismatch`);

      // Verify subsections match template
      assert.strictEqual(draftBlock.subsections.length, templateBlock.subsections.length,
        `Block ${i + 1} subsection count mismatch`);
    }
  });

  test('generateDraft produces draft_ready status after full cycle', () => {
    // Full cycle: session → generator → markAsDraft
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);
    generator.markAsDraft(session, draft);

    assert.strictEqual(session.status, 'draft_ready');
    assert.strictEqual(draft.status, 'draft_ready');
    assert.strictEqual(session.documentReady, true);

    // Verify draft can be serialized to JSON (for generator agent)
    const json = JSON.stringify(draft);
    assert.ok(json.length > 0);
    const parsed = JSON.parse(json);
    assert.strictEqual(parsed.title, 'Документ бизнес-требований');
    assert.strictEqual(parsed.totalBlocks, 7);
    assert.strictEqual(parsed.status, 'draft_ready');
  });

  test('generateDraft blocks follow immutable template order', () => {
    const session = createApprovedSession();
    const { draft } = generator.generateDraft(session, null);

    const expectedOrder = [
      { id: 1, name: 'Контекст и проблема' },
      { id: 2, name: 'Цель и измерение' },
      { id: 3, name: 'Стейкхолдеры и влияние' },
      { id: 4, name: 'Решение' },
      { id: 5, name: 'Требования к качеству и ограничения' },
      { id: 6, name: 'Приёмка' },
      { id: 7, name: 'Риски и митигации' }
    ];

    for (let i = 0; i < expectedOrder.length; i++) {
      assert.strictEqual(draft.blocks[i].blockId, expectedOrder[i].id,
        `Block ${i + 1}: expected id ${expectedOrder[i].id}`);
      assert.strictEqual(draft.blocks[i].blockName, expectedOrder[i].name,
        `Block ${i + 1}: expected name "${expectedOrder[i].name}"`);
    }
  });

  // ==================== Summary ====================
  const total = passed + failed;
  console.log(`\n🏁 Test Suite Complete: ${total} tests`);
  console.log(`  ✅ Passed: ${passed}`);
  console.log(`  ❌ Failed: ${failed}`);

  if (failed > 0) {
    console.log('\n📝 Failure details:');
    for (const f of failures) {
      console.log(`  - ${f.name}: ${f.error}`);
    }
    process.exit(1);
  }
}

runTests().catch(err => {
  console.error('💥 Test runner error:', err.message);
  process.exit(1);
});
