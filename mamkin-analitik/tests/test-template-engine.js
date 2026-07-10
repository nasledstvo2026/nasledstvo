/**
 * Тесты Template Engine (Story 1.3)
 *
 * Тестирует: загрузку, валидацию, навигацию по блокам/подразделам,
 *            read-only режим, getFirstQuestion, edge cases.
 *
 * Использует реальный data/template.json из проекта.
 */

const path = require('path');
const fs = require('fs');
const assert = require('assert');
const TemplateEngine = require('../lib/template-engine');

const TEMPLATE_PATH = path.resolve(__dirname, '..', 'data', 'template.json');

// ==================== Test Helpers ====================

/**
 * Создаёт временный файл с содержимым для тестирования валидации.
 */
function createTempJson(data) {
  const tmpDir = fs.mkdtempSync('/tmp/template-test-');
  const tmpPath = path.join(tmpDir, 'template.json');
  fs.writeFileSync(tmpPath, JSON.stringify(data, null, 2), 'utf-8');
  return { tmpDir, tmpPath };
}

// ==================== Tests ====================

/**
 * 1. Загрузка и базовая целостность
 */
async function testLoadAndIntegrity() {
  const engine = new TemplateEngine();
  const template = await engine.load(TEMPLATE_PATH);

  assert(template, 'Шаблон должен загрузиться');
  assert(template.meta, 'Должна быть meta');
  assert.strictEqual(template.meta.immutable, true, 'meta.immutable должен быть true');
  assert.strictEqual(template.meta.version, '1.0', 'meta.version должен быть 1.0');
  assert.strictEqual(template.meta.language, 'ru', 'meta.language должен быть ru');

  // Проверка 7 блоков
  assert(Array.isArray(template.blocks), 'template.blocks должен быть массивом');
  assert.strictEqual(template.blocks.length, 7, 'Должно быть 7 блоков');

  // Каждый блок имеет id, key, name, subsections
  for (let i = 0; i < template.blocks.length; i++) {
    const block = template.blocks[i];
    const idx = i + 1;
    assert(block.id, `Блок ${idx}: должен иметь id`);
    assert.strictEqual(typeof block.id, 'number', `Блок ${idx}: id должен быть числом`);
    assert.strictEqual(block.id, idx, `Блок ${idx}: id должен быть ${idx}`);
    assert(block.key, `Блок ${idx}: должен иметь key`);
    assert.strictEqual(block.key, `block.${idx}`, `Блок ${idx}: key должен быть block.${idx}`);
    assert(block.name, `Блок ${idx}: должен иметь name`);
    assert(Array.isArray(block.subsections), `Блок ${idx}: subsections должен быть массивом`);
    assert(block.subsections.length >= 1, `Блок ${idx}: должен иметь хотя бы 1 подраздел`);
    assert(Array.isArray(block.completenessCriteria), `Блок ${idx}: должен иметь completenessCriteria`);
  }

  console.log('✓ testLoadAndIntegrity');
}

/**
 * 2. getBlockCount()
 */
async function testGetBlockCount() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  const count = engine.getBlockCount();
  assert.strictEqual(count, 7, 'getBlockCount() должен вернуть 7');

  console.log('✓ testGetBlockCount');
}

/**
 * 3. getBlock() — по номеру и по ключу
 */
async function testGetBlock() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  // По номеру
  const block1 = engine.getBlock(1);
  assert.strictEqual(block1.id, 1, 'Блок 1: id должен быть 1');
  assert.strictEqual(block1.key, 'block.1', 'Блок 1: key должен быть block.1');
  assert.strictEqual(block1.name, 'Контекст и проблема', 'Блок 1: name');
  assert(Array.isArray(block1.subsections), 'Блок 1: subsections должен быть массивом');
  assert.strictEqual(block1.subsections.length, 3, 'Блок 1: должно быть 3 подраздела');

  // По ключу
  const block7 = engine.getBlock('block.7');
  assert.strictEqual(block7.id, 7, 'Блок 7: id должен быть 7');
  assert.strictEqual(block7.key, 'block.7', 'Блок 7: key');
  assert.strictEqual(block7.name, 'Риски и митигации', 'Блок 7: name');

  // Граничные случаи
  const blockMid = engine.getBlock(4);
  assert.strictEqual(blockMid.id, 4, 'Блок 4: id');
  assert.strictEqual(blockMid.name, 'Решение', 'Блок 4: name');

  // Ошибка: несуществующий блок
  assert.throws(() => engine.getBlock(999), /не найден/, 'Несуществующий блок должен кидать ошибку');
  assert.throws(() => engine.getBlock('block.99'), /не найден/, 'Несуществующий ключ должен кидать ошибку');

  console.log('✓ testGetBlock');
}

/**
 * 4. getSubsection() — L1/L2/L3 вопросы
 */
async function testGetSubsection() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  // Подраздел 1.1 — Контекст инициативы
  const sub11 = engine.getSubsection(1, '1.1');
  assert.strictEqual(sub11.id, '1.1', 'sub 1.1: id');
  assert.strictEqual(sub11.name, 'Контекст инициативы', 'sub 1.1: name');

  // Вопросы L1/L2/L3
  assert(sub11.questions.L1, 'sub 1.1: должен быть L1');
  assert(sub11.questions.L2, 'sub 1.1: должен быть L2');
  assert(sub11.questions.L3, 'sub 1.1: должен быть L3');

  assert(
    sub11.questions.L1.includes('над чем работаете'),
    'L1 вопрос 1.1: контекст'
  );

  // По ключу блока
  const sub32 = engine.getSubsection('block.3', '3.2');
  assert.strictEqual(sub32.id, '3.2', 'sub 3.2: id');
  assert.strictEqual(sub32.name, 'Их интересы и влияние', 'sub 3.2: name');
  assert(sub32.questions.L1.includes('Что каждая'), 'L1 вопрос 3.2');

  // Все 7 блоков имеют L1/L2/L3 для всех подразделов
  for (const block of engine.getAllBlocks()) {
    for (const sub of block.subsections) {
      const loaded = engine.getSubsection(block.id, sub.id);
      assert(loaded.questions.L1, `Блок ${block.id} ${sub.id}: L1`);
      assert(loaded.questions.L2, `Блок ${block.id} ${sub.id}: L2`);
      assert(loaded.questions.L3, `Блок ${block.id} ${sub.id}: L3`);
    }
  }

  // Ошибка: несуществующий подраздел
  assert.throws(
    () => engine.getSubsection(1, '99.99'),
    /не найден/,
    'Несуществующий подраздел должен кидать ошибку'
  );

  console.log('✓ testGetSubsection');
}

/**
 * 5. getNextSubsection() — навигация
 */
async function testGetNextSubsection() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  // Внутри блока: 1.1 → 1.2
  const next12 = engine.getNextSubsection(1, '1.1');
  assert(next12, 'После 1.1 должен быть подраздел');
  assert.strictEqual(next12.id, '1.2', 'После 1.1 следует 1.2');

  // 1.2 → 1.3
  const next13 = engine.getNextSubsection(1, '1.2');
  assert.strictEqual(next13.id, '1.3', 'После 1.2 следует 1.3');

  // Переход между блоками: 1.3 → 2.1
  const next21 = engine.getNextSubsection(1, '1.3');
  assert.strictEqual(next21.id, '2.1', 'После блока 1 следует 2.1');

  // По ключу блока
  const next31 = engine.getNextSubsection('block.3', '3.1');
  assert.strictEqual(next31.id, '3.2', 'После 3.1 следует 3.2');

  // Сквозная навигация: проходим все до конца
  let sub = engine.getNextSubsection(6, '6.1');
  assert.strictEqual(sub.id, '7.1', 'После 6.1 следует 7.1');

  sub = engine.getNextSubsection(7, '7.1');
  assert.strictEqual(sub.id, '7.2', 'После 7.1 следует 7.2');

  // Конец шаблона
  const end = engine.getNextSubsection(7, '7.2');
  assert.strictEqual(end, null, 'После 7.2 должен быть null (конец)');

  // Ошибка: несуществующий подраздел
  assert.throws(
    () => engine.getNextSubsection(1, '99.99'),
    /не найден/,
    'Несуществующий подраздел должен кидать ошибку'
  );

  console.log('✓ testGetNextSubsection');
}

/**
 * 6. getFirstQuestion()
 */
async function testGetFirstQuestion() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  const first = engine.getFirstQuestion();
  assert(first, 'getFirstQuestion() должен вернуть объект');
  assert.strictEqual(first.blockId, 1, 'Первый блок: id 1');
  assert.strictEqual(first.blockName, 'Контекст и проблема', 'Первый блок: name');
  assert.strictEqual(first.subsectionId, '1.1', 'Первый подраздел: 1.1');
  assert.strictEqual(first.subsectionName, 'Контекст инициативы', 'Первый подраздел: name');
  assert.strictEqual(first.depth, 'L1', 'Глубина: L1');
  assert(
    first.question.includes('над чем работаете'),
    'Первый вопрос: контекст'
  );

  console.log('✓ testGetFirstQuestion');
}

/**
 * 7. getQuestion() — обратная совместимость
 */
async function testGetQuestion() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  // L1
  const q1 = engine.getQuestion('1.1', 'L1');
  assert(typeof q1 === 'string', 'Вопрос должен быть строкой');
  assert(q1.includes('над чем'), 'L1 вопрос 1.1');

  // L2
  const q2 = engine.getQuestion('2.1', 'L2');
  assert(q2.includes('измеримый'), 'L2 вопрос 2.1');

  // L3
  const q3 = engine.getQuestion('7.2', 'L3');
  assert(q3.includes('полностью устранить'), 'L3 вопрос 7.2');

  // Ошибка: несуществующий уровень
  assert.throws(
    () => engine.getQuestion('1.1', 'L4'),
    /не найден/,
    'L4 должен кидать ошибку'
  );

  console.log('✓ testGetQuestion');
}

/**
 * 8. getAllBlocks()
 */
async function testGetAllBlocks() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  const all = engine.getAllBlocks();
  assert(Array.isArray(all), 'getAllBlocks() должен возвращать массив');
  assert.strictEqual(all.length, 7, 'Должно быть 7 блоков');

  // Проверка названий всех блоков
  const expectedNames = [
    'Контекст и проблема',
    'Цель и измерение',
    'Стейкхолдеры и влияние',
    'Решение',
    'Требования к качеству и ограничения',
    'Приёмка',
    'Риски и митигации'
  ];

  for (let i = 0; i < expectedNames.length; i++) {
    assert.strictEqual(all[i].name, expectedNames[i], `Блок ${i + 1}: name`);
  }

  console.log('✓ testGetAllBlocks');
}

/**
 * 9. Read-only режим
 */
async function testReadOnly() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  // write() должен кидать ошибку
  assert.throws(
    () => engine.write(),
    /read-only/,
    'write() должен кидать Error'
  );

  // save() — алиас
  assert.throws(
    () => engine.save(),
    /read-only/,
    'save() должен кидать Error'
  );

  // update() — алиас
  assert.throws(
    () => engine.update(),
    /read-only/,
    'update() должен кидать Error'
  );

  // Данные остаются доступными после попытки записи
  const count = engine.getBlockCount();
  assert.strictEqual(count, 7, 'После write() данные должны оставаться доступными');

  console.log('✓ testReadOnly');
}

/**
 * 10. Read-only — возвращаемые объекты заморожены
 */
async function testFrozenObjects() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  const block = engine.getBlock(1);
  assert(Object.isFrozen(block), 'Блок должен быть frozen');

  // Попытка изменить frozen объект (должна молча игнорироваться в strict mode)
  // Просто проверяем, что блок остался целым
  assert.strictEqual(block.id, 1, 'Блок 1: id не изменился');

  const sub = engine.getSubsection(1, '1.1');
  assert(Object.isFrozen(sub), 'Подраздел должен быть frozen');

  console.log('✓ testFrozenObjects');
}

/**
 * 11. Валидация — отсутствующий файл
 */
async function testValidationMissingFile() {
  const engine = new TemplateEngine();

  try {
    await engine.load('/nonexistent/path/template.json');
    assert(false, 'Должна быть ошибка при отсутствии файла');
  } catch (e) {
    assert(e.message.includes('не найден'), 'Ошибка: файл не найден');
  }

  console.log('✓ testValidationMissingFile');
}

/**
 * 12. Валидация — невалидный шаблон (не 7 блоков)
 */
async function testValidationWrongBlockCount() {
  const badTemplate = {
    meta: { version: '1.0', name: 'Bad', immutable: true },
    blocks: [{ id: 1, key: 'block.1', name: 'Only one', subsections: [], completenessCriteria: [] }]
  };
  const { tmpDir, tmpPath } = createTempJson(badTemplate);

  const engine = new TemplateEngine();
  try {
    await engine.load(tmpPath);
    assert(false, 'Должна быть ошибка: не 7 блоков');
  } catch (e) {
    assert(e.message.includes('7 блоков'), `Ошибка: ${e.message}`);
  }

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testValidationWrongBlockCount');
}

/**
 * 13. Валидация — не immutable
 */
async function testValidationNotImmutable() {
  const badTemplate = {
    meta: { version: '1.0', name: 'Mutable', immutable: false },
    blocks: [
      { id: 1, key: 'block.1', name: 'B1', subsections: [{ id: '1.1', name: 'S1', questions: { L1: 'q1', L2: 'q2', L3: 'q3' } }], completenessCriteria: [] },
      { id: 2, key: 'block.2', name: 'B2', subsections: [{ id: '2.1', name: 'S2', questions: { L1: 'q1', L2: 'q2', L3: 'q3' } }], completenessCriteria: [] },
      { id: 3, key: 'block.3', name: 'B3', subsections: [{ id: '3.1', name: 'S3', questions: { L1: 'q1', L2: 'q2', L3: 'q3' } }], completenessCriteria: [] },
      { id: 4, key: 'block.4', name: 'B4', subsections: [{ id: '4.1', name: 'S4', questions: { L1: 'q1', L2: 'q2', L3: 'q3' } }], completenessCriteria: [] },
      { id: 5, key: 'block.5', name: 'B5', subsections: [{ id: '5.1', name: 'S5', questions: { L1: 'q1', L2: 'q2', L3: 'q3' } }], completenessCriteria: [] },
      { id: 6, key: 'block.6', name: 'B6', subsections: [{ id: '6.1', name: 'S6', questions: { L1: 'q1', L2: 'q2', L3: 'q3' } }], completenessCriteria: [] },
      { id: 7, key: 'block.7', name: 'B7', subsections: [{ id: '7.1', name: 'S7', questions: { L1: 'q1', L2: 'q2', L3: 'q3' } }], completenessCriteria: [] }
    ]
  };
  const { tmpDir, tmpPath } = createTempJson(badTemplate);

  const engine = new TemplateEngine();
  try {
    await engine.load(tmpPath);
    assert(false, 'Должна быть ошибка: не immutable');
  } catch (e) {
    assert(e.message.includes('immutable'), `Ошибка: ${e.message}`);
  }

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testValidationNotImmutable');
}

/**
 * 14. Валидация — отсутствует L3 вопрос
 */
async function testValidationMissingDepth() {
  const badSubs = [
    { id: '1.1', name: 'S1', questions: { L1: 'q1', L2: 'q2' } } // нет L3
  ];
  const badTemplate = {
    meta: { version: '1.0', name: 'Bad', immutable: true },
    blocks: []
  };
  for (let i = 1; i <= 7; i++) {
    badTemplate.blocks.push({
      id: i, key: `block.${i}`, name: `B${i}`,
      subsections: i === 1 ? badSubs : [{ id: `${i}.1`, name: `S${i}`, questions: { L1: 'q1', L2: 'q2', L3: 'q3' } }],
      completenessCriteria: []
    });
  }
  const { tmpDir, tmpPath } = createTempJson(badTemplate);

  const engine = new TemplateEngine();
  try {
    await engine.load(tmpPath);
    assert(false, 'Должна быть ошибка: отсутствует L3');
  } catch (e) {
    assert(e.message.includes('L3'), `Ошибка: ${e.message}`);
  }

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testValidationMissingDepth');
}

/**
 * 15. Загрузка без вызова load() — ошибка
 */
async function testNotLoadedError() {
  const engine = new TemplateEngine();

  assert.throws(
    () => engine.getBlockCount(),
    /не загружен/,
    'getBlockCount() без load() должен кидать ошибку'
  );
  assert.throws(
    () => engine.getBlock(1),
    /не загружен/,
    'getBlock() без load() должен кидать ошибку'
  );

  console.log('✓ testNotLoadedError');
}

/**
 * 16. getTemplate() — полный объект шаблона
 */
async function testGetTemplate() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  const tpl = engine.getTemplate();
  assert(tpl, 'getTemplate() должен вернуть объект');
  assert.strictEqual(tpl.meta.version, '1.0', 'meta.version');
  assert(Array.isArray(tpl.blocks), 'tpl.blocks');
  assert.strictEqual(tpl.blocks.length, 7, '7 blocks');
  assert(tpl.depthControl, 'Наличие depthControl');

  // Объект заморожен
  assert(Object.isFrozen(tpl), 'getTemplate() должен возвращать frozen объект');

  console.log('✓ testGetTemplate');
}

/**
 * 17. loadSync() — синхронная загрузка
 */
async function testLoadSync() {
  const engine = new TemplateEngine();
  const template = engine.loadSync(TEMPLATE_PATH);

  assert(template, 'loadSync() должен загрузить шаблон');
  assert.strictEqual(engine.getBlockCount(), 7, 'После loadSync: 7 блоков');

  const firstQ = engine.getFirstQuestion();
  assert.strictEqual(firstQ.blockId, 1, 'loadSync: первый блок 1');

  console.log('✓ testLoadSync');
}

/**
 * 18. Сквозной сценарий: пройти все подразделы от начала до конца
 */
async function testEndToEndNavigation() {
  const engine = new TemplateEngine();
  await engine.load(TEMPLATE_PATH);

  const first = engine.getFirstQuestion();
  assert(first.question, 'Есть первый вопрос');

  // Проходим все подразделы через getNextSubsection
  let subId = first.subsectionId;
  let blockId = first.blockId;
  let steps = 1;

  let next = engine.getNextSubsection(blockId, subId);
  while (next !== null) {
    steps++;
    subId = next.id;
    // Определяем блок из id подраздела
    blockId = parseInt(subId.split('.')[0], 10);
    next = engine.getNextSubsection(blockId, subId);
  }

  // Всего подразделов: 3 + 2 + 2 + 3 + 2 + 1 + 2 = 15
  assert.strictEqual(steps, 15, `Должно быть 15 подразделов, пройдено ${steps}`);

  console.log('✓ testEndToEndNavigation');
}

// ==================== Run All Tests ====================

async function runAll() {
  const tests = [
    testLoadAndIntegrity,
    testGetBlockCount,
    testGetBlock,
    testGetSubsection,
    testGetNextSubsection,
    testGetFirstQuestion,
    testGetQuestion,
    testGetAllBlocks,
    testReadOnly,
    testFrozenObjects,
    testValidationMissingFile,
    testValidationWrongBlockCount,
    testValidationNotImmutable,
    testValidationMissingDepth,
    testNotLoadedError,
    testGetTemplate,
    testLoadSync,
    testEndToEndNavigation
  ];

  let passed = 0;
  let failed = 0;

  console.log('\n🧪 Template Engine Tests (Story 1.3)\n');

  for (const test of tests) {
    try {
      await test();
      passed++;
    } catch (e) {
      failed++;
      console.error(`✗ ${test.name}: FAIL`);
      console.error(`  ${e.message}`);
      if (e.stack) {
        console.error(`  ${e.stack.split('\n').slice(1, 3).join('\n  ')}`);
      }
    }
  }

  const total = passed + failed;
  console.log(`\n📊 Результат: ${passed}/${total} тестов пройдено`);
  if (failed > 0) {
    console.error(`❌ Провалено: ${failed}`);
    process.exit(1);
  } else {
    console.log('✅ Все тесты пройдены!');
  }
}

runAll();
