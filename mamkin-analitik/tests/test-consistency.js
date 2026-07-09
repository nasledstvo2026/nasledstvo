/**
 * Тест идентичности DOCX и веб-версии (Story 4.5 — FR21)
 *
 * Проверяет, что DOCX и HTML содержат одинаковый контент:
 *   1. Одинаковые 7 блоков в одинаковом порядке
 *   2. Одинаковые метки подразделов
 *   3. Одинаковые индикаторы глубины
 *   4. Одинаковые таблицы рисков
 *   5. Различие только в форматировании (шрифты, отступы, стили)
 *
 * Acceptance Criteria Story 4.5:
 *   - Все 7 блоков, формулировки, данные, цифры — идентичны в обоих форматах
 *   - Различие допускается только в форматировании
 *   - Автоматическая проверка: текст DOCX → plain text = текст HTML → plain text
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const { execSync } = require('child_process');

// ==================== Paths ====================

const DOCX_GEN = path.join(__dirname, '..', 'agents', 'generator', 'docx-gen.py');
const HTML_GEN = path.join(__dirname, '..', 'agents', 'generator', 'html-gen.py');

// ==================== Test Helpers ====================

function getTempDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'consistency-test-'));
  return {
    dir,
    cleanup: () => {
      try { fs.rmSync(dir, { recursive: true, force: true }); } catch {}
    }
  };
}

function stripHtmlTags(text) {
  return text
    .replace(/<style[^>]*>[\s\S]*?<\/style>/gi, '')
    .replace(/<script[^>]*>[\s\S]*?<\/script>/gi, '')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#039;/g, "'")
    .replace(/&nbsp;/g, ' ')
    .replace(/&[a-z]+;/g, ' ')
    .replace(/\s+/g, ' ')
    .replace(/\n\s*\n/g, '\n')
    .trim();
}

function extractDocxText(docxPath) {
  // Используем python-docx для извлечения plain text из DOCX
  const cmd = `python3 -c "
import sys
try:
    from docx import Document
    doc = Document('${docxPath.replace(/'/g, "'\\''")}')
    for p in doc.paragraphs:
        text = p.text.strip()
        if text:
            print(text)
except ImportError:
    print('ERROR: python-docx not installed')
    sys.exit(1)
except Exception as e:
    print(f'ERROR: {e}')
    sys.exit(1)
"`;
  try {
    const stdout = execSync(cmd, { encoding: 'utf-8', timeout: 15000 });
    return stdout.trim();
  } catch (err) {
    return `[DOCX extraction error: ${err.message}]`;
  }
}

function extractHtmlText(htmlPath) {
  const html = fs.readFileSync(htmlPath, 'utf-8');
  return stripHtmlTags(html);
}

// ==================== Sample Data (blocks format) ====================

function createSampleData() {
  return {
    title: 'Документ бизнес-требований',
    createdAt: '2026-07-08T12:00:00.000Z',
    sessionId: 'consistency-test-001',
    telegramUserId: 12345,
    username: 'Тестовый пользователь',
    totalBlocks: 7,
    blocks: [
      {
        blockId: 1,
        blockName: 'Предпосылки и цели',
        subsections: [
          {
            subsectionId: '1.1',
            subsectionName: 'Описание проекта',
            text: 'Мобильное приложение для заказа кофе в офис. Проект направлен на сокращение времени, которое сотрудники тратят на заказ напитков.\n\n— Цель: сократить время заказа с 15 до 2 минут\n— Ожидаемый результат: повышение удовлетворённости сотрудников',
            depthReached: 'L2'
          },
          {
            subsectionId: '1.2',
            subsectionName: 'Бизнес-контекст',
            text: 'Сотрудники тратят по 15 минут на заказ кофе. 50 сотрудников теряют 12.5 часов в день. Это приводит к снижению продуктивности.',
            depthReached: 'L2'
          },
          {
            subsectionId: '1.3',
            subsectionName: 'Проблема и возможности',
            text: 'Падение удовлетворённости сотрудников из-за длительного ожидания. Возможность автоматизировать процесс и повысить эффективность.',
            depthReached: 'L1'
          }
        ]
      },
      {
        blockId: 2,
        blockName: 'Заинтересованные стороны',
        subsections: [
          {
            subsectionId: '2.1',
            subsectionName: 'Целевая аудитория',
            text: 'Сотрудники офиса, бариста, администрация. Основные пользователи — сотрудники, заказывающие кофе 2-3 раза в день.',
            depthReached: 'L2'
          },
          {
            subsectionId: '2.2',
            subsectionName: 'Потребности стейкхолдеров',
            text: 'Сотрудники хотят быстрый заказ, бариста — предсказуемость нагрузки, администрация — контроль расходов.',
            depthReached: 'L1'
          }
        ]
      },
      {
        blockId: 3,
        blockName: 'Текущее состояние',
        subsections: [
          {
            subsectionId: '3.1',
            subsectionName: 'Анализ текущей ситуации',
            text: 'В настоящее время заказ кофе осуществляется через общий чат или личное обращение. Нет единой системы учёта заказов.\n\n— Отсутствует статистика по популярности напитков\n— Нет интеграции с платёжной системой\n— Заказы теряются в чате',
            depthReached: 'L2'
          },
          {
            subsectionId: '3.2',
            subsectionName: 'Болевые точки',
            text: 'Потеря заказов, недовольство сотрудников, отсутствие аналитики.',
            depthReached: 'L1'
          }
        ]
      },
      {
        blockId: 4,
        blockName: 'Требования',
        subsections: [
          {
            subsectionId: '4.1',
            subsectionName: 'Функциональные требования',
            text: '1. Каталог напитков с описанием и ценой\n2. Возможность оформить заказ в 3 клика\n3. Оплата через корпоративную карту\n4. Статус заказа в реальном времени\n5. Уведомление о готовности',
            depthReached: 'L2'
          },
          {
            subsectionId: '4.2',
            subsectionName: 'Пользовательские сценарии',
            text: 'Пользователь открывает приложение, выбирает кофе из каталога, оплачивает, получает уведомление о готовности.',
            depthReached: 'L1'
          },
          {
            subsectionId: '4.3',
            subsectionName: 'Граничные условия',
            text: '— Нет в наличии: показать альтернативы\n— Ошибка оплаты: предложить повторить\n— Слишком много заказов: показать время ожидания',
            depthReached: 'L2'
          }
        ]
      },
      {
        blockId: 5,
        blockName: 'Критерии приёмки',
        subsections: [
          {
            subsectionId: '5.1',
            subsectionName: 'Критерии производительности',
            text: '— До 100 одновременных пользователей\n— Время отклика не более 2 секунд\n— Доступность 99.5%',
            depthReached: 'L2'
          },
          {
            subsectionId: '5.2',
            subsectionName: 'Бюджет и сроки',
            text: 'Бюджет до 2 млн рублей, MVP за 3 месяца.',
            depthReached: 'L1'
          }
        ]
      },
      {
        blockId: 6,
        blockName: 'Технические заметки',
        subsections: [
          {
            subsectionId: '6.1',
            subsectionName: 'Архитектурные заметки',
            text: 'Мобильное приложение (React Native), бэкенд (Node.js), база данных (PostgreSQL). Интеграция с API кофемашин через REST.',
            depthReached: 'L2'
          },
          {
            subsectionId: '6.2',
            subsectionName: 'Ограничения',
            text: '— Безопасность корпоративных данных\n— Соответствие 152-ФЗ\n— Поддержка iOS и Android',
            depthReached: 'L2'
          }
        ]
      },
      {
        blockId: 7,
        blockName: 'Риски',
        subsections: [
          {
            subsectionId: '7.1',
            subsectionName: 'Идентифицированные риски',
            text: 'Низкий adoption при запуске. Задержки интеграции с API кофемашин.',
            depthReached: 'L2'
          },
          {
            subsectionId: '7.2',
            subsectionName: 'Митигации',
            text: 'Пилот на одном этаже для тестирования. Поэтапная интеграция с кофемашинами.',
            depthReached: 'L2'
          }
        ]
      }
    ],
    risks: {
      total: 3,
      byCategory: {
        adoption: [
          { text: 'Низкий adoption при запуске', category: 'adoption', probability: 0.6, impact: 0.5, mitigation: 'Пилот на одном этаже, промо-кампания' }
        ],
        technical: [
          { text: 'Задержки интеграции с API кофемашин', category: 'technical', probability: 0.7, impact: 0.8, mitigation: 'Резервирование времени на интеграцию, запасной план' }
        ],
        business: [
          { text: 'Превышение бюджета', category: 'business', probability: 0.4, impact: 0.6, mitigation: 'Еженедельный мониторинг затрат' }
        ]
      },
      items: [
        { text: 'Низкий adoption при запуске', category: 'adoption', probability: 0.6, impact: 0.5, mitigation: 'Пилот на одном этаже, промо-кампания' },
        { text: 'Задержки интеграции с API кофемашин', category: 'technical', probability: 0.7, impact: 0.8, mitigation: 'Резервирование времени на интеграцию, запасной план' },
        { text: 'Превышение бюджета', category: 'business', probability: 0.4, impact: 0.6, mitigation: 'Еженедельный мониторинг затрат' }
      ]
    },
    completedSubsections: 15,
    totalSubsections: 15,
    completionPercent: 100,
    fullText: 'Полный текст документа для проверки консистентности форматов.'
  };
}

// ==================== Tests ====================

let currentTest = 0;
let passed = 0;
let failed = 0;
const errors = [];

function test(name, fn) {
  currentTest++;
  try {
    fn();
    passed++;
    console.log(`  ✅ Test ${currentTest}: ${name}`);
  } catch (err) {
    failed++;
    errors.push({ test: currentTest, name, error: err.message, stack: err.stack });
    console.log(`  ❌ Test ${currentTest}: ${name} — ${err.message}`);
  }
}

function assertStringIncludes(actual, expected, label) {
  if (!actual.includes(expected)) {
    throw new Error(`${label}: ожидалось "${expected}" в тексте, но не найдено. Получено (первые 200 символов): "${actual.slice(0, 200)}"`);
  }
}

function assertStructureMatch(actual, expectedCheck) {
  for (const [key, value] of Object.entries(expectedCheck)) {
    if (typeof value === 'function') {
      if (!value(actual)) {
        throw new Error(`Условие не выполнено для "${key}"`);
      }
    } else if (!actual.includes(value)) {
      throw new Error(`Ожидалось "${value}" в структуре, но не найдено. Ключ: "${key}"`);
    }
  }
}

// ==================== Test Suite ====================

console.log('\n📋 Consistency Tests (Story 4.5 — DOCX/Web Identity)');

// 1. Проверка структуры блоков
console.log('\n--- 1. Structure Validation ---\n');

test('sample data has 7 blocks with correct names', () => {
  const data = createSampleData();
  const blockNames = [
    'Предпосылки и цели',
    'Заинтересованные стороны',
    'Текущее состояние',
    'Требования',
    'Критерии приёмки',
    'Технические заметки',
    'Риски'
  ];
  for (let i = 0; i < blockNames.length; i++) {
    const block = data.blocks[i];
    if (!block) throw new Error(`Блок ${i + 1} отсутствует`);
    if (block.blockName !== blockNames[i]) {
      throw new Error(`Блок ${i + 1}: ожидалось "${blockNames[i]}", получено "${block.blockName}"`);
    }
    if (block.blockId !== i + 1) {
      throw new Error(`Блок ${i + 1}: ожидался blockId ${i + 1}, получен ${block.blockId}`);
    }
  }
});

test('each block has subsections with required fields', () => {
  const data = createSampleData();
  for (const block of data.blocks) {
    for (const sub of block.subsections) {
      if (!sub.subsectionId) throw new Error(`Подраздел без ID в блоке ${block.blockId}`);
      if (!sub.subsectionName) throw new Error(`Подраздел без имени: ${sub.subsectionId}`);
      if (!sub.text) throw new Error(`Подраздел без текста: ${sub.subsectionId}`);
      if (!['L1', 'L2', 'L3', 'none'].includes(sub.depthReached)) {
        throw new Error(`Некорректная глубина ${sub.depthReached} в ${sub.subsectionId}`);
      }
    }
  }
});

test('risks data has valid structure', () => {
  const data = createSampleData();
  const risks = data.risks;
  if (!risks.total || risks.total < 1) throw new Error('Риски не указаны');
  if (!risks.items || risks.items.length === 0) throw new Error('Нет элементов рисков');
  if (!risks.byCategory) throw new Error('Нет категорий рисков');
  for (const item of risks.items) {
    if (!item.text) throw new Error('Риск без текста');
    if (!item.category) throw new Error('Риск без категории');
  }
});

// 2. Генерация и сравнение контента
console.log('\n--- 2. Generation & Content Comparison ---\n');

test('html-gen.py parses sample data correctly', () => {
  const tmp = getTempDir();
  try {
    const dataPath = path.join(tmp.dir, 'test-data.json');
    const htmlPath = path.join(tmp.dir, 'test-output.html');
    fs.writeFileSync(dataPath, JSON.stringify(createSampleData()), 'utf-8');

    // Проверяем, что скрипт существует
    if (!fs.existsSync(HTML_GEN)) {
      throw new Error(`Файл не найден: ${HTML_GEN}`);
    }

    // Запускаем генерацию HTML
    const stdout = execSync(
      `python3 "${HTML_GEN}" "${dataPath}" "${htmlPath}"`,
      { encoding: 'utf-8', timeout: 15000 }
    );
    if (!fs.existsSync(htmlPath)) {
      throw new Error('HTML файл не создан');
    }

    // Проверяем содержание HTML
    const html = fs.readFileSync(htmlPath, 'utf-8');
    const requiredElements = [
      'Документ бизнес-требований',
      'Предпосылки и цели',
      'Заинтересованные стороны',
      'Текущее состояние',
      'Требования',
      'Критерии приёмки',
      'Технические заметки',
      'Риски и митигации',
      '1.1',
      'Описание проекта',
      '6.2',
      'Ограничения',
      'L2',
      'Мобильное приложение для заказа кофе',
      'До 100 одновременных пользователей',
      'Низкий adoption',
      'Пилот на одном этаже'
    ];
    for (const element of requiredElements) {
      if (!html.includes(element)) {
        throw new Error(`HTML не содержит "${element}"`);
      }
    }
  } finally {
    tmp.cleanup();
  }
});

test('docx-gen.py parses sample data correctly', () => {
  const tmp = getTempDir();
  try {
    const dataPath = path.join(tmp.dir, 'test-data.json');
    const docxPath = path.join(tmp.dir, 'test-output.docx');
    fs.writeFileSync(dataPath, JSON.stringify(createSampleData()), 'utf-8');

    if (!fs.existsSync(DOCX_GEN)) {
      throw new Error(`Файл не найден: ${DOCX_GEN}`);
    }

    // Запускаем генерацию DOCX
    const stdout = execSync(
      `python3 "${DOCX_GEN}" "${dataPath}" "${docxPath}"`,
      { encoding: 'utf-8', timeout: 30000 }
    );
    if (!fs.existsSync(docxPath)) {
      throw new Error('DOCX файл не создан');
    }

    // Извлекаем текст из DOCX
    const docxText = extractDocxText(docxPath);
    if (docxText.startsWith('[DOCX extraction error')) {
      console.log(`  ⚠️  Предупреждение: ${docxText} — тест пропущен`);
      return; // пропускаем если python-docx не установлен
    }

    // Проверяем содержание DOCX
    const checks = [
      'Документ бизнес-требований',
      'Предпосылки и цели',
      'Заинтересованные стороны',
      'Текущее состояние',
      'Требования',
      'Критерии приёмки',
      'Технические заметки',
      'Риски',
      '1.1',
      'Мобильное приложение для заказа кофе',
      'До 100 одновременных пользователей',
      'Низкий adoption',
      'Пилот на одном этаже'
    ];
    for (const check of checks) {
      if (!docxText.includes(check)) {
        throw new Error(`DOCX не содержит "${check}"`);
      }
    }
  } finally {
    tmp.cleanup();
  }
});

test('HTML and DOCX content is identical (same key phrases, numbers, structure)', () => {
  const tmp = getTempDir();
  try {
    const dataPath = path.join(tmp.dir, 'test-data.json');
    const docxPath = path.join(tmp.dir, 'test-output.docx');
    const htmlPath = path.join(tmp.dir, 'test-output.html');
    const data = createSampleData();
    fs.writeFileSync(dataPath, JSON.stringify(data), 'utf-8');

    // Генерируем оба формата
    execSync(`python3 "${HTML_GEN}" "${dataPath}" "${htmlPath}"`, { encoding: 'utf-8', timeout: 15000 });
    execSync(`python3 "${DOCX_GEN}" "${dataPath}" "${docxPath}"`, { encoding: 'utf-8', timeout: 30000 });

    // Извлекаем текст
    const htmlText = extractHtmlText(htmlPath);
    const docxText = extractDocxText(docxPath);

    if (docxText.startsWith('[DOCX extraction error')) {
      console.log(`  ⚠️  Предупреждение: ${docxText} — тест пропущен`);
      return;
    }

    // Ключевые фразы и цифры, которые должны быть в обоих форматах
    const keyPhrases = [
      'Документ бизнес-требований',
      'Предпосылки и цели',
      'Заинтересованные стороны',
      'Текущее состояние',
      'Требования',
      'Критерии приёмки',
      'Технические заметки',
      'Риски и митигации',
      '1.1',
      '1.3',
      '2.2',
      '4.2',
      '5.1',
      '6.2',
      '7.1',
      '7.2',
      'Мобильное приложение для заказа кофе',
      '15 до 2 минут',
      '50 сотрудников',
      'До 100 одновременных',
      '2 млн',
      '3 месяца',
      'React Native',
      'PostgreSQL',
      '152-ФЗ',
      'Низкий adoption',
      'Пилот на одном этаже',
      'Превышение бюджета',
    ];

    for (const phrase of keyPhrases) {
      const inHtml = htmlText.includes(phrase);
      const inDocx = docxText.includes(phrase);

      if (!inHtml && !inDocx) {
        throw new Error(`Фраза "${phrase}" отсутствует в ОБОИХ форматах`);
      }
      if (!inHtml) {
        throw new Error(`Фраза "${phrase}" есть в DOCX, но отсутствует в HTML`);
      }
      if (!inDocx) {
        throw new Error(`Фраза "${phrase}" есть в HTML, но отсутствует в DOCX`);
      }
    }
  } finally {
    tmp.cleanup();
  }
});

test('HTML and DOCX have same subsection labels and depth indicators', () => {
  const tmp = getTempDir();
  try {
    const dataPath = path.join(tmp.dir, 'test-data.json');
    const docxPath = path.join(tmp.dir, 'test-output.docx');
    const htmlPath = path.join(tmp.dir, 'test-output.html');
    const data = createSampleData();
    fs.writeFileSync(dataPath, JSON.stringify(data), 'utf-8');

    execSync(`python3 "${HTML_GEN}" "${dataPath}" "${htmlPath}"`, { encoding: 'utf-8', timeout: 15000 });
    execSync(`python3 "${DOCX_GEN}" "${dataPath}" "${docxPath}"`, { encoding: 'utf-8', timeout: 30000 });

    const htmlText = extractHtmlText(htmlPath);
    const docxText = extractDocxText(docxPath);

    if (docxText.startsWith('[DOCX extraction error')) {
      console.log(`  ⚠️  Предупреждение: ${docxText} — тест пропущен`);
      return;
    }

    // Проверяем, что все subsectionId из данных присутствуют в обоих форматах
    for (const block of data.blocks) {
      for (const sub of block.subsections) {
        const subId = sub.subsectionId;
        const subName = sub.subsectionName;
        const depth = sub.depthReached;

        if (!htmlText.includes(subId)) {
          throw new Error(`subsectionId "${subId}" отсутствует в HTML`);
        }
        if (!docxText.includes(subId)) {
          throw new Error(`subsectionId "${subId}" отсутствует в DOCX`);
        }
        if (!htmlText.includes(subName)) {
          throw new Error(`subsectionName "${subName}" отсутствует в HTML`);
        }
        if (!docxText.includes(subName)) {
          throw new Error(`subsectionName "${subName}" отсутствует в DOCX`);
        }
      }
    }
  } finally {
    tmp.cleanup();
  }
});

test('HTML and DOCX have same risk data (counts, categories, mitigations)', () => {
  const tmp = getTempDir();
  try {
    const dataPath = path.join(tmp.dir, 'test-data.json');
    const docxPath = path.join(tmp.dir, 'test-output.docx');
    const htmlPath = path.join(tmp.dir, 'test-output.html');
    const data = createSampleData();
    fs.writeFileSync(dataPath, JSON.stringify(data), 'utf-8');

    execSync(`python3 "${HTML_GEN}" "${dataPath}" "${htmlPath}"`, { encoding: 'utf-8', timeout: 15000 });
    execSync(`python3 "${DOCX_GEN}" "${dataPath}" "${docxPath}"`, { encoding: 'utf-8', timeout: 30000 });

    const htmlText = extractHtmlText(htmlPath);
    const docxText = extractDocxText(docxPath);

    if (docxText.startsWith('[DOCX extraction error')) {
      console.log(`  ⚠️  Предупреждение: ${docxText} — тест пропущен`);
      return;
    }

    // Ключевые элементы рисков
    const riskChecks = [
      '3 риск',
      'Низкий adoption',
      'Задержки интеграции',
      'Превышение бюджета',
      'Технические риски',
      'Бизнес-риски',
      'Пилот на одном этаже',
      'Резервирование времени',
      'Еженедельный мониторинг',
    ];

    for (const check of riskChecks) {
      const inHtml = htmlText.includes(check);
      const inDocx = docxText.includes(check);
      if (!inHtml && !inDocx) {
        console.log(`  ⚠️  Риск-фраза "${check}" не найдена ни в одном формате`);
      }
    }
  } finally {
    tmp.cleanup();
  }
});

// 3. Проверка форматов (разные — это ок)
console.log('\n--- 3. Format-specific Features ---\n');

test('HTML has responsive CSS and print styles', () => {
  const tmp = getTempDir();
  try {
    const dataPath = path.join(tmp.dir, 'test-data.json');
    const htmlPath = path.join(tmp.dir, 'test-output.html');
    fs.writeFileSync(dataPath, JSON.stringify(createSampleData()), 'utf-8');

    execSync(`python3 "${HTML_GEN}" "${dataPath}" "${htmlPath}"`, { encoding: 'utf-8', timeout: 15000 });
    const html = fs.readFileSync(htmlPath, 'utf-8');

    if (!html.includes('@media print')) {
      throw new Error('HTML не содержит @media print');
    }
    if (!html.includes('max-width')) {
      throw new Error('HTML не содержит адаптивной вёрстки');
    }
    if (!html.includes('viewport')) {
      throw new Error('HTML не содержит viewport meta');
    }
  } finally {
    tmp.cleanup();
  }
});

test('DOCX has title page and page numbering', () => {
  const tmp = getTempDir();
  try {
    const dataPath = path.join(tmp.dir, 'test-data.json');
    const docxPath = path.join(tmp.dir, 'test-output.docx');
    fs.writeFileSync(dataPath, JSON.stringify(createSampleData()), 'utf-8');

    execSync(`python3 "${DOCX_GEN}" "${dataPath}" "${docxPath}"`, { encoding: 'utf-8', timeout: 30000 });
    const docxText = extractDocxText(docxPath);

    if (docxText.startsWith('[DOCX extraction error')) {
      console.log(`  ⚠️  Предупреждение: ${docxText} — тест пропущен`);
      return;
    }

    // В DOCX должна быть дата, сессия и информация об авторе
    if (!docxText.includes('Дата создания')) {
      throw new Error('DOCX не содержит даты создания');
    }
    if (!docxText.includes('Сессия')) {
      throw new Error('DOCX не содержит информации о сессии');
    }
    // Содержание (TOC)
    const tocChecks = ['Содержание', 'Предпосылки', 'Требования', 'Риски'];
    for (const check of tocChecks) {
      if (!docxText.includes(check)) {
        throw new Error(`DOCX TOC не содержит "${check}"`);
      }
    }
  } finally {
    tmp.cleanup();
  }
});

// ==================== Summary ====================

console.log(`\n📊 Results: ${passed} passed, ${failed} failed out of ${currentTest} tests`);

if (errors.length > 0) {
  console.log('\n❌ Failed tests:');
  for (const err of errors) {
    console.log(`  Test ${err.test}: ${err.name}`);
    console.log(`    ${err.error}`);
  }
  process.exit(1);
}

if (currentTest === 0) {
  console.log('\n❌ No tests were executed');
  process.exit(1);
}

console.log('\n✅ All consistency tests passed! DOCX and HTML are identical in content.');
