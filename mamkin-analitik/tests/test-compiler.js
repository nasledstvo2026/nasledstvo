/**
 * Тесты Compiler Agent (Story 3.1)
 *
 * Проверяет:
 *   1. lib/compiler.js — основные методы
 *      - compileDraft() с полным контекстом
 *      - formatBlock() — форматирование блока
 *      - formatSubsection() — форматирование подраздела (L1/L2/L3)
 *      - buildDraftDocument() — полная сборка документа
 *      - getCurrentDraft() — текущее состояние
 *   2. Стилевые требования (FR13)
 *      - Отсутствие художественных оборотов
 *      - Чёткие формулировки
 *      - Формальный стиль БТ
 *   3. agents/compiler/index.js — интеграция
 *      - process() — основной метод
 *      - canProcess() — проверка готовности
 *   4. agents/compiler/section-formatter.js — обёртка
 *      - Делегирование в lib/compiler.js
 *   5. Граничные случаи
 *      - Пустые ответы
 *      - "Не применимо"
 *      - Отсутствие рисков
 *      - Неполные данные
 *      - Минимальный контекст
 */

const path = require('path');
const assert = require('assert');
const TemplateEngine = require('../lib/template-engine');
const Compiler = require('../lib/compiler');
const CompilerAgent = require('../agents/compiler/index.js');
const SectionFormatter = require('../agents/compiler/section-formatter');

// ==================== Test Data ====================

/**
 * Создаёт полный Session Context с ответами на все 7 блоков.
 */
function createFullSessionContext(overrides = {}) {
  return {
    sessionId: overrides.sessionId || 'test-session-compiler-001',
    telegramUserId: overrides.telegramUserId || 123456789,
    answers: overrides.answers || {
      // Блок 1: Контекст и проблема
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
        L3: 'Через полгода ситуация ухудшится — компания планирует нанять ещё 100 человек. Без системы заказов хаос только усилится.',
        depthReached: 'L3'
      },
      // Блок 2: Цель и измерение
      '2.1': {
        L1: 'Автоматизировать процесс заказа кофе в офисе.',
        L2: 'Снизить среднее время ожидания кофе с текущих 10-15 минут до 3-5 минут. Обеспечить прозрачный учёт расходов на кофе по отделам.',
        L3: 'Конкретные KPI: среднее время ожидания — не более 5 минут; количество обработанных заказов в час — до 40; удовлетворённость сотрудников (NPS) — не ниже 8 из 10.',
        depthReached: 'L3'
      },
      '2.2': {
        L1: 'Когда 90% сотрудников будут получать кофе в течение 5 минут.',
        L2: 'Критерии успеха: 1) Среднее время заказа < 5 минут через 2 недели после запуска; 2) 95% заказов без ошибок; 3) NPS по опросу через месяц — не ниже 8.',
        L3: 'Критерии проверяются через аналитику приложения (время от начала заказа до получения). Автоматический сбор метрик. Срок — 2 недели после MVP.',
        depthReached: 'L3'
      },
      // Блок 3: Стейкхолдеры и влияние
      '3.1': {
        L1: 'Сотрудники офиса, бариста, руководители отделов, финансовая служба.',
        L2: 'Пользователи — сотрудники офиса (~300 человек). Бариста — внедряет и работает с системой. Платит — финансовый отдел (корпоративный бюджет). Может заблокировать — руководитель IT, если сочтёт систему небезопасной.',
        L3: 'Забыли: юридический отдел (нужно согласие на обработку данных), служба безопасности (интеграция с корпоративной сетью).',
        depthReached: 'L3'
      },
      '3.2': {
        L1: 'Сотрудники хотят удобно и быстро заказывать кофе. Бариста хотят упростить приём заказов. Финансовый отдел — контролировать расходы.',
        L2: 'Критично мнение финансового отдела — они утверждают бюджет. Без их одобрения проект не запустится.',
        L3: 'Конфликт интересов: бариста хотят меньше работы, но отдел продаж может захотеть больше кофе для встреч с клиентами за счёт бюджета.',
        depthReached: 'L3'
      },
      // Блок 4: Решение
      '4.1': {
        L1: 'Каталог напитков с ценами, оформление заказа, оплата через корпоративный счёт, уведомление бариста.',
        L2: 'Must Have: каталог, оформление заказа, уведомление бариста, учёт расходов. Should Have: отложенный заказ (на конкретное время). Nice to Have: интеграция с календарём.',
        L3: 'Функция оформления заказа: пользователь выбирает напиток, размер, добавки; указывает корпоративный e-mail; система проверяет бюджет отдела; отправляет заказ бариста с указанием времени приготовления.',
        depthReached: 'L3'
      },
      '4.2': {
        L1: 'Пользователь заходит в приложение, видит каталог напитков, выбирает, оплачивает, получает уведомление, когда заказ готов.',
        L2: 'При входе пользователь видит приветствие и каталог. Выбирает напиток (латте, капучино, американо), размер, добавки. Система показывает стоимость списания с корпоративного счёта. После подтверждения — заказ отправлен, система показывает ожидаемое время приготовления. Бариста видит заказ на экране, готовит, нажимает "Готово". Пользователь получает push-уведомление.',
        L3: 'Нетипичный сценарий: пользователь заказывает 15 чашек к встрече — система проверяет лимит бюджета отдела и может отклонить превышение.',
        depthReached: 'L3'
      },
      '4.3': {
        L1: 'Если сеть упала — ошибка отправки заказа. Если неверные данные пользователя — отклонение заказа. Если кофе закончился — уведомление об отсутствии.',
        L2: 'Успех: заказ отправлен, бариста получил, время приготовления рассчитано. Ошибка: сеть недоступна — показать "Повторить позже" с автоматической попыткой через 10 секунд.',
        L3: 'Экстремальные случаи: 300 сотрудников заказывают одновременно (например, утром) — система должна выдержать пиковую нагрузку до 50 заказов в минуту. Большие данные: история заказов за год — до 50 000 записей, аналитика должна подгружаться не более 3 секунд.',
        depthReached: 'L3'
      },
      // Блок 5: Требования к качеству и ограничения
      '5.1': {
        L1: 'Производительность (быстрый отклик), безопасность (корпоративные данные), доступность (24/7).',
        L2: 'Производительность: до 300 пользователей, время отклика не более 2 секунд. Безопасность: аутентификация через корпоративный LDAP, данные шифруются. Доступность: 24/7, допускаются окна обслуживания ночью. Совместимость: интеграция с Active Directory.',
        L3: 'Требования по надёжности: uptime 99.5% (рабочее время), время восстановления до 2 часов, ежедневный бэкап базы данных.',
        depthReached: 'L3'
      },
      '5.2': {
        L1: 'Бюджет до 1 млн рублей, срок MVP — 2 месяца, технологии — React Native + Node.js.',
        L2: 'Бюджет: утверждён в 800 тыс. - 1 млн рублей. Сроки: MVP через 2 месяца. Технологии: React Native (мобильное) или просто PWA, backend Node.js. Регуляторика: согласие на обработку персональных данных.',
        L3: 'Манёвр: бюджет можем нарушить до +20% (одобрение финдиректора), сроки — критичны, нарушать нельзя из-за контракта с кофейней.',
        depthReached: 'L3'
      },
      // Блок 6: Приёмка
      '6.1': {
        L1: 'Проверяем каждую функцию: заказ, оплата, уведомления.',
        L2: 'Given пользователь авторизован. When он выбирает латте, нажимает "Заказать". Then заказ отправляется бариста, пользователь видит время ожидания 3 минуты.',
        L3: 'Принимает руководитель продукта. Blocker: если не работает интеграция с LDAP — приёмка невозможна. Нужно автоматическое тестирование: юнит-тесты + интеграционные тесты API.',
        depthReached: 'L3'
      },
      // Блок 7: Риски и митигации
      '7.1': {
        L1: 'Риск: пользователи не примут новое приложение из-за привычки звонить.',
        L2: 'Технические: сбой интеграции с LDAP. Организационные: задержка согласования бюджета. Бизнес-риски: низкая adoption. Риски внедрения: бариста не научатся пользоваться.',
        L3: 'Вероятность низкой adoption — средняя, влияние — высокое. Вероятность срыва сроков — низкая. Приоритет: adoption — критический риск.',
        depthReached: 'L3'
      },
      '7.2': {
        L1: 'Провести обучение, сделать простой интерфейс, информировать заранее.',
        L2: 'Для adoption: пилот на одном этаже, сбор отзывов, итеративное улучшение. Для срыва сроков: MVP с сокращённым функционалом (только базовый заказ).',
        L3: 'Риск adoption можно полностью устранить, сделав обязательным использование приложения для всех сотрудников (административное решение). С низкой adoption придётся жить, если не будет поддержки руководства.',
        depthReached: 'L3'
      }
    },
    risks: [
      {
        text: 'Пользователи могут не принять новое приложение из-за привычки звонить',
        category: 'adoption',
        collectedAt: 'block_1',
        probability: 0.5,
        impact: 0.8,
        mitigation: 'Пилотный запуск на одном этаже, сбор отзывов, итеративное улучшение интерфейса'
      },
      {
        text: 'Сбой интеграции с корпоративным LDAP может заблокировать запуск',
        category: 'technical',
        collectedAt: 'block_3',
        probability: 0.3,
        impact: 0.9,
        mitigation: 'Заранее протестировать интеграцию, подготовить fallback-аутентификацию'
      },
      {
        text: 'Задержка согласования бюджета финансовым отделом',
        category: 'organizational',
        collectedAt: 'block_5',
        probability: 0.4,
        impact: 0.6,
        mitigation: 'Заранее согласовать бюджет до старта разработки'
      }
    ],
    status: overrides.status || 'completed',
    currentBlock: 7,
    currentSubsection: '7.2',
    depth: 'L1',
    progress: 100,
    meta: {
      createdAt: '2026-07-08T12:00:00.000Z',
      updatedAt: '2026-07-08T12:45:00.000Z',
      completedAt: '2026-07-08T12:45:00.000Z',
      username: 'test_user'
    },
    ...overrides
  };
}

/**
 * Создаёт минимальный Session Context (только некоторые ответы).
 */
function createMinimalSessionContext(overrides = {}) {
  return {
    sessionId: overrides.sessionId || 'test-session-minimal-001',
    telegramUserId: overrides.telegramUserId || 987654321,
    answers: {
      '1.1': { L1: 'Проект по автоматизации отчётности.', depthReached: 'L1' },
      '1.2': { L1: 'Сейчас отчёты делают вручную в Excel, это долго.', depthReached: 'L1' },
      '2.1': { L1: 'Автоматизировать создание еженедельных отчётов.', depthReached: 'L1' }
    },
    risks: [],
    status: 'completed',
    meta: {
      createdAt: '2026-07-08T14:00:00.000Z',
      updatedAt: '2026-07-08T14:30:00.000Z'
    },
    ...overrides
  };
}

/**
 * Создаёт session с отсутствующими ответами.
 */
function createEmptySessionContext(overrides = {}) {
  return {
    sessionId: overrides.sessionId || 'test-session-empty-001',
    telegramUserId: overrides.telegramUserId || 555555555,
    answers: {},
    risks: [],
    status: 'completed',
    meta: {
      createdAt: '2026-07-08T15:00:00.000Z',
      updatedAt: '2026-07-08T15:00:00.000Z'
    },
    ...overrides
  };
}

// ==================== Setup ====================

let compiler;
let compilerAgent;
let templateEngine;

before(async function () {
  this.timeout(10000);

  // Инициализируем TemplateEngine
  templateEngine = new TemplateEngine();
  await templateEngine.load();

  // Создаём Compiler
  compiler = new Compiler({ templateEngine });

  // Создаём CompilerAgent
  compilerAgent = new CompilerAgent({ templateEngine });
});

// ==================== Test: lib/compiler.js ====================

describe('lib/compiler.js', () => {
  describe('Конструктор', () => {
    it('должен создать экземпляр без templateEngine', () => {
      const c = new Compiler();
      assert.ok(c);
      assert.strictEqual(c._currentDraft, null);
    });

    it('должен создать экземпляр с templateEngine', () => {
      const c = new Compiler({ templateEngine });
      assert.ok(c);
      assert.strictEqual(c._currentDraft, null);
    });

    it('должен иметь пустой _currentDraft после инициализации', () => {
      assert.strictEqual(compiler.getCurrentDraft(), null);
    });
  });

  describe('formatSubsection()', () => {
    it('должен вернуть "Не заполнено" для null-ответа', () => {
      const result = compiler.formatSubsection('1.1', null);
      assert.ok(result.includes('Не заполнено'));
    });

    it('должен вернуть "Не заполнено" для ответа без текста', () => {
      const result = compiler.formatSubsection('1.1', { depthReached: 'L1' });
      assert.ok(result.includes('Не заполнено'));
    });

    it('должен вернуть "Не применимо" для "не применимо"', () => {
      const result = compiler.formatSubsection('1.1', {
        L1: 'Не применимо',
        depthReached: 'L1'
      });
      assert.ok(result.includes('Не применимо'));
    });

    it('должен вернуть "Не применимо" для "н/п"', () => {
      const result = compiler.formatSubsection('1.1', {
        L1: 'н/п',
        depthReached: 'L1'
      });
      assert.ok(result.includes('Не применимо'));
    });

    it('должен использовать L3 при наличии (наибольшая глубина)', () => {
      const result = compiler.formatSubsection('1.1', {
        L1: 'Поверхностный ответ',
        L2: 'Средний ответ с деталями',
        L3: 'Глубокий анализ коренной причины',
        depthReached: 'L3'
      });
      assert.ok(result.includes('Глубокий анализ коренной причины'));
      assert.ok(result.includes('Глубокая проработка'));
    });

    it('должен использовать L2 если L3 отсутствует', () => {
      const result = compiler.formatSubsection('1.1', {
        L1: 'Поверхностный ответ',
        L2: 'Детальный ответ',
        L3: null,
        depthReached: 'L2'
      });
      assert.ok(result.includes('Детальный ответ'));
      assert.ok(result.includes('Детальная проработка'));
    });

    it('должен использовать L1 если L2 и L3 отсутствуют', () => {
      const result = compiler.formatSubsection('1.1', {
        L1: 'Базовый ответ',
        L2: null,
        L3: null,
        depthReached: 'L1'
      });
      assert.ok(result.includes('Базовый ответ'));
      assert.ok(result.includes('Поверхностная проработка'));
    });

    it('должен вернуть "Поверхностный ответ" для тривиальных ответов', () => {
      const result = compiler.formatSubsection('1.1', {
        L1: 'да',
        depthReached: 'L1'
      });
      assert.ok(result.includes('Поверхностный ответ'));
    });
  });

  describe('formatBlock()', () => {
    it('должен выбросить ошибку без templateEngine', () => {
      const c = new Compiler();
      assert.throws(() => c.formatBlock(1, {}), /TemplateEngine/);
    });

    it('должен вернуть null для несуществующего блока', () => {
      const result = compiler.formatBlock(99, {});
      assert.strictEqual(result, null);
    });

    it('должен отформатировать блок 1 с ответами', () => {
      const ctx = createFullSessionContext();
      const block = compiler.formatBlock(1, ctx.answers);

      assert.ok(block);
      assert.strictEqual(block.blockId, 1);
      assert.ok(block.blockName);
      assert.ok(Array.isArray(block.subsections));
      assert.ok(block.subsections.length > 0);
      assert.ok(block.content.includes('Блок 1'));
      assert.ok(block.content.includes('1.1'));
      assert.ok(block.content.includes('1.2'));
    });

    it('должен включить все подразделы блока', () => {
      // Блок 1 имеет 3 подраздела (1.1, 1.2, 1.3)
      const ctx = createFullSessionContext();
      const block = compiler.formatBlock(1, ctx.answers);

      assert.strictEqual(block.subsections.length, 3);

      const subIds = block.subsections.map(s => s.subsectionId);
      assert.ok(subIds.includes('1.1'));
      assert.ok(subIds.includes('1.2'));
      assert.ok(subIds.includes('1.3'));
    });

    it('должен пометить отсутствующие подразделы как "Не заполнено"', () => {
      const block = compiler.formatBlock(2, {});
      // Блок 2, но ответов нет — подразделы должны быть "Не заполнено"
      assert.ok(block);
      assert.ok(block.subsections.every(s => s.text.includes('Не заполнено')));
    });
  });

  describe('compileDraft()', () => {
    it('должен выбросить ошибку без TemplateEngine', () => {
      const c = new Compiler();
      const ctx = createFullSessionContext();
      assert.throws(() => c.compileDraft(ctx), /TemplateEngine/);
    });

    it('должен выбросить ошибку с пустыми ответами', () => {
      const ctx = createEmptySessionContext();
      assert.throws(() => compiler.compileDraft(ctx), /нет ответов/);
    });

    it('должен создать черновик из полного контекста', () => {
      const ctx = createFullSessionContext();
      const draft = compiler.compileDraft(ctx);

      assert.ok(draft);
      assert.strictEqual(draft.sessionId, 'test-session-compiler-001');
      assert.strictEqual(draft.totalBlocks, 7);
      assert.strictEqual(draft.blocks.length, 7);
      assert.ok(draft.fullText);
      assert.ok(draft.fullText.length > 500);
    });

    it('должен включить все 7 блоков в документ', () => {
      const ctx = createFullSessionContext();
      const draft = compiler.compileDraft(ctx);

      assert.strictEqual(draft.blocks.length, 7);
      for (let i = 0; i < 7; i++) {
        assert.strictEqual(draft.blocks[i].blockId, i + 1);
      }
    });

    it('должен включить титульную часть (заголовок, дата, сессия)', () => {
      const ctx = createFullSessionContext();
      const draft = compiler.compileDraft(ctx);

      assert.ok(draft.fullText.includes('Документ бизнес-требований'));
      assert.ok(draft.fullText.includes(draft.sessionId));
    });

    it('должен структурировать риски в блоке 7', () => {
      const ctx = createFullSessionContext();
      const draft = compiler.compileDraft(ctx);

      assert.ok(draft.risks);
      assert.strictEqual(draft.risks.total, 3);
      assert.ok(draft.risks.byCategory.adoption);
      assert.ok(draft.risks.byCategory.technical);
      assert.ok(draft.risks.byCategory.organizational);
      assert.ok(draft.fullText.includes('adoption'));
      assert.ok(draft.fullText.includes('Риски'));
    });

    it('должен корректно сосчитать completedSubsections', () => {
      const ctx = createFullSessionContext();
      const draft = compiler.compileDraft(ctx);

      // Ответы есть на все подразделы с depthReached !== 'none'
      assert.ok(draft.completedSubsections > 0);
      assert.strictEqual(
        draft.completedSubsections,
        draft.totalSubsections  // В полном контексте всё заполнено
      );
    });
  });

  describe('getCurrentDraft()', () => {
    it('должен вернуть null если черновик не сформирован', () => {
      const c = new Compiler({ templateEngine });
      assert.strictEqual(c.getCurrentDraft(), null);
    });

    it('должен вернуть черновик после compileDraft', () => {
      const ctx = createFullSessionContext();
      const draft = compiler.compileDraft(ctx);

      const current = compiler.getCurrentDraft();
      assert.ok(current);
      assert.strictEqual(current.sessionId, draft.sessionId);
    });

    it('должен вернуть null после resetDraft()', () => {
      const c = new Compiler({ templateEngine });
      const ctx = createFullSessionContext();
      c.compileDraft(ctx);
      assert.ok(c.getCurrentDraft());

      c.resetDraft();
      assert.strictEqual(c.getCurrentDraft(), null);
    });
  });

  describe('buildDraftDocument() — минимальные данные', () => {
    it('должен создать документ из минимального контекста', () => {
      const ctx = createMinimalSessionContext();
      const draft = compiler.buildDraftDocument(ctx);

      assert.ok(draft);
      assert.strictEqual(draft.sessionId, 'test-session-minimal-001');
      assert.strictEqual(draft.totalBlocks, 7);
      assert.strictEqual(draft.blocks.length, 7);
      assert.ok(draft.fullText);
      assert.ok(draft.fullText.includes('test-session-minimal-001'));
    });

    it('должен корректно обработать отсутствие рисков', () => {
      const ctx = createMinimalSessionContext();
      const draft = compiler.buildDraftDocument(ctx);

      assert.strictEqual(draft.risks.total, 0);
      assert.deepStrictEqual(draft.risks.items, []);
    });

    it('должен пометить незаполненные подразделы', () => {
      const ctx = createMinimalSessionContext();
      const draft = compiler.buildDraftDocument(ctx);

      // В минимальных данных заполнены только 1.1, 1.2, 2.1
      // Остальные должны быть "Не заполнено"
      const block2 = draft.blocks[1]; // Блок 2
      const unsubs = block2.subsections.filter(s => s.text.includes('Не заполнено'));
      assert.ok(unsubs.length > 0);
    });
  });
});

// ==================== Test: Стилевые требования FR13 ====================

describe('FR13 — Стилевые требования', () => {
  it('должен удалять разговорные частицы ("ну", "типа", "как бы")', () => {
    const result = compiler.formatSubsection('1.1', {
      L1: 'Ну типа проект по автоматизации, как бы, всякие отчёты.',
      depthReached: 'L1'
    });
    // Разговорные частицы должны быть убраны
    assert.ok(!result.includes('ну типа'));
    assert.ok(!result.includes('как бы'));
    // Смысл должен сохраниться
    assert.ok(result.includes('автоматизации'));
  });

  it('не должен содержать художественных оборотов', () => {
    const ctx = createFullSessionContext();
    const draft = compiler.compileDraft(ctx);

    const artisticPhrases = [
      'прекрасный', 'чудесный', 'восхитительный', 'потрясающий',
      'великолепный', 'сказочный', 'невероятный', 'божественный'
    ];

    for (const phrase of artisticPhrases) {
      assert.ok(
        !draft.fullText.toLowerCase().includes(phrase),
        `Найдена художественная фраза: "${phrase}"`
      );
    }
  });

  it('должен сохранять деловой стиль (формальные формулировки)', () => {
    const ctx = createFullSessionContext();
    const draft = compiler.compileDraft(ctx);

    // Документ должен содержать формальные бизнес-термины
    const formalTerms = [
      'Система', 'Пользователь', 'Требование', 'Функция',
      'Ограничение', 'Риск', 'Митигация', 'KPI'
    ];

    const foundTerms = formalTerms.filter(t => draft.fullText.includes(t));
    assert.ok(foundTerms.length >= 3, `Найдено формальных терминов: ${foundTerms.length}`);
  });

  it('должен форматировать ответы в маркированный список с тире', () => {
    const result = compiler.formatSubsection('1.1', {
      L1: 'Проект по автоматизации отчётности.',
      depthReached: 'L1'
    });
    assert.ok(result.startsWith('—'));
  });
});

// ==================== Test: Граничные случаи ====================

describe('Граничные случаи', () => {
  it('должен обработать sessionContext без meta', () => {
    const ctx = {
      sessionId: 'no-meta-001',
      telegramUserId: 1,
      answers: { '1.1': { L1: 'Тест', depthReached: 'L1' } },
      risks: []
    };
    const draft = compiler.buildDraftDocument(ctx);
    assert.ok(draft);
    assert.strictEqual(draft.sessionId, 'no-meta-001');
  });

  it('должен обработать sessionContext без answers', () => {
    const ctx = {
      sessionId: 'no-answers-001',
      telegramUserId: 1,
      answers: {},
      risks: []
    };
    const draft = compiler.buildDraftDocument(ctx);
    assert.ok(draft);
    assert.strictEqual(draft.totalSubsections, draft.blocks.reduce(
      (sum, b) => sum + b.subsections.length, 0
    ));
  });

  it('должен обработать сессию с рисками без митигаций', () => {
    const ctx = createFullSessionContext({
      risks: [
        { text: 'Простой риск', category: 'technical', probability: null, impact: null, mitigation: null }
      ]
    });
    const draft = compiler.compileDraft(ctx);
    assert.ok(draft.fullText.includes('Простой риск'));
    assert.ok(draft.fullText.includes('Технические'));
  });

  it('должен корректно обработать L1-ответ с цифрами', () => {
    const result = compiler.formatSubsection('1.2', {
      L1: 'Теряем около 200 тысяч рублей в месяц из-за простоев.',
      depthReached: 'L1'
    });
    assert.ok(result.includes('200'));
    assert.ok(result.includes('рублей'));
  });

  it('должен добавить точку в конце, если её нет', () => {
    const result = compiler.formatSubsection('1.1', {
      L1: 'Проект по автоматизации',
      depthReached: 'L1'
    });
    assert.ok(result.includes('автоматизации.'));
  });

  it('должен капитализировать первую букву', () => {
    const result = compiler.formatSubsection('1.1', {
      L1: 'проект по автоматизации',
      depthReached: 'L1'
    });
    assert.ok(result.includes('Проект'));
  });
});

// ==================== Test: agents/compiler/index.js ====================

describe('agents/compiler/index.js', () => {
  describe('process()', () => {
    it('должен выбросить ошибку без sessionId', async () => {
      try {
        await compilerAgent.process({});
        assert.fail('Должна быть ошибка');
      } catch (err) {
        assert.ok(err.message.includes('невалидный'));
      }
    });

    it('должен выбросить ошибку с пустыми answers', async () => {
      try {
        await compilerAgent.process({
          sessionId: 'test-001',
          answers: {}
        });
        assert.fail('Должна быть ошибка');
      } catch (err) {
        assert.ok(err.message.includes('нет ответов'));
      }
    });

    it('должен создать черновик из полного Session Context', async () => {
      const ctx = createFullSessionContext();
      const result = await compilerAgent.process(ctx);

      assert.ok(result);
      assert.ok(result.draft);
      assert.strictEqual(result.draft.totalBlocks, 7);
      assert.strictEqual(result.draft.blocks.length, 7);
    });

    it('должен установить documentReady = false после компиляции', async () => {
      const ctx = createFullSessionContext();
      const result = await compilerAgent.process(ctx);

      assert.strictEqual(result.documentReady, false);
    });

    it('должен сохранить статистику последней компиляции', async () => {
      const ctx = createFullSessionContext();
      await compilerAgent.process(ctx);

      const stats = compilerAgent.getLastProcessStats();
      assert.ok(stats);
      assert.strictEqual(stats.draftCreated, true);
      assert.ok(stats.draftBlocks);
    });
  });

  describe('canProcess()', () => {
    it('должен вернуть false для null', () => {
      const result = compilerAgent.canProcess(null);
      assert.strictEqual(result.ready, false);
    });

    it('должен вернуть false для пустого контекста', () => {
      const result = compilerAgent.canProcess({});
      assert.strictEqual(result.ready, false);
    });

    it('должен вернуть false при отсутствии answers', () => {
      const result = compilerAgent.canProcess({
        sessionId: 'test-001',
        answers: {}
      });
      assert.strictEqual(result.ready, false);
    });

    it('должен вернуть true для валидного контекста', () => {
      const result = compilerAgent.canProcess({
        sessionId: 'test-001',
        answers: { '1.1': { L1: 'Ответ' } }
      });
      assert.strictEqual(result.ready, true);
    });
  });

  describe('getCurrentDraft()', () => {
    it('должен вернуть null до первого process()', () => {
      const agent = new CompilerAgent({ templateEngine });
      assert.strictEqual(agent.getCurrentDraft(), null);
    });

    it('должен вернуть черновик после process()', async () => {
      const ctx = createFullSessionContext();
      await compilerAgent.process(ctx);

      const draft = compilerAgent.getCurrentDraft();
      assert.ok(draft);
      assert.strictEqual(draft.sessionId, 'test-session-compiler-001');
    });
  });
});

// ==================== Test: agents/compiler/section-formatter.js ====================

describe('agents/compiler/section-formatter.js', () => {
  let formatter;

  before(() => {
    formatter = new SectionFormatter({ compiler, templateEngine });
  });

  describe('formatBlock()', () => {
    it('должен отформатировать блок 1', () => {
      const ctx = createFullSessionContext();
      const result = formatter.formatBlock(1, ctx.answers);

      assert.ok(result);
      assert.ok(typeof result === 'string');
      assert.ok(result.includes('Блок 1'));
      assert.ok(result.includes('Контекст'));
    });

    it('должен выбросить ошибку без compiler', () => {
      const f = new SectionFormatter();
      assert.throws(() => f.formatBlock(1, {}), /Compiler/);
    });
  });

  describe('formatSubsection()', () => {
    it('должен отформатировать подраздел', () => {
      const result = formatter.formatSubsection('1.1', {
        L1: 'Тестовый ответ',
        depthReached: 'L1'
      });
      assert.ok(result.includes('Тестовый ответ'));
    });
  });

  describe('compileDocument()', () => {
    it('должен собрать весь документ', () => {
      const ctx = createFullSessionContext();
      const text = formatter.compileDocument(ctx.answers, ctx.risks);

      assert.ok(text);
      assert.ok(text.length > 500);
      assert.ok(text.includes('Блок 1'));
      assert.ok(text.includes('Блок 7'));
    });

    it('должен работать без рисков', () => {
      const ctx = createMinimalSessionContext();
      const text = formatter.compileDocument(ctx.answers, []);

      assert.ok(text);
      assert.ok(text.length > 100);
    });
  });
});

// ==================== Test: Сквозной тест ====================

describe('Сквозной тест: от Session Context до сформированного документа', () => {
  it('должен пройти полный цикл: session → compile → draft', async () => {
    const ctx = createFullSessionContext();

    // 1. Проверка готовности
    const readyCheck = compilerAgent.canProcess(ctx);
    assert.strictEqual(readyCheck.ready, true);

    // 2. Компиляция
    const result = await compilerAgent.process(ctx);
    assert.ok(result.draft);

    // 3. Проверка структуры черновика
    const draft = result.draft;
    assert.strictEqual(draft.totalBlocks, 7);
    assert.strictEqual(draft.blocks.length, 7);
    assert.ok(draft.fullText);

    // 4. Проверка, что каждый блок имеет заголовок и подразделы
    for (const block of draft.blocks) {
      assert.ok(block.blockId >= 1 && block.blockId <= 7);
      assert.ok(block.blockName);
      assert.ok(block.subsections.length > 0);
      assert.ok(block.content);
    }

    // 5. Проверка блока рисков
    assert.ok(draft.risks);
    assert.strictEqual(draft.risks.total, 3);

    // 6. Проверка, что текст документа содержит все ключевые разделы
    const text = draft.fullText;
    assert.ok(text.includes('Документ бизнес-требований'));
    assert.ok(text.includes('Блок 1'));
    assert.ok(text.includes('Блок 2'));
    assert.ok(text.includes('Блок 3'));
    assert.ok(text.includes('Блок 4'));
    assert.ok(text.includes('Блок 5'));
    assert.ok(text.includes('Блок 6'));
    assert.ok(text.includes('Блок 7'));
    assert.ok(text.includes('Риски и митигации'));
  });
});
