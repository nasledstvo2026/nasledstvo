/**
 * Template Engine — immutable шаблон БТ (7 блоков, L1/L2/L3)
 *
 * Загружает data/template.json и предоставляет read-only API
 * для всех агентов пайплайна. Единый источник истины.
 *
 * Story 1.3 — Реализация
 *
 * API:
 *   load(path?)     — загрузка и валидация template.json
 *   getBlockCount() — количество блоков (7)
 *   getBlock(id)    — блок по номеру (1-7) или ключу ('block.1')
 *   getSubsection(blockId, subId)     — L1/L2/L3 вопросы подраздела
 *   getNextSubsection(blockId, subId) — следующий подраздел
 *   getFirstQuestion()                — первый L1-вопрос (Блок 1, 1.1)
 *   getQuestion(subsectionKey, depth) — вопрос по ключу и глубине
 *   getAllBlocks()  — массив всех блоков
 *   getTemplate()   — полный объект шаблона (read-only копия)
 *
 * Read-only: вызов write() → Error
 */

const path = require('path');
const fs = require('fs');

const EXPECTED_BLOCK_COUNT = 7;
const EXPECTED_BLOCK_IDS = [1, 2, 3, 4, 5, 6, 7];
const REQUIRED_DEPTHS = ['L1', 'L2', 'L3'];
const STORAGE_PATHS = [
  '/var/mamkin-analitik/sessions/template.json',
  '/var/mamkin-analitik/template.json'
];

class TemplateEngine {
  constructor() {
    /** @private */
    this.template = null;
    /** @private */
    this.blocks = [];
    /** @private */
    this._loaded = false;
    /** @private */
    this._blockMap = new Map();   // 'block.1' → block, 1 → block
    /** @private */
    this._subsectionMap = new Map(); // '1.1' → { block, subsection }
  }

  /**
   * Загружает template.json из указанного пути.
   *
   * @param {string} [filePath] — путь к template.json.
   *   Если не указан, ищет в data/template.json (workspace),
   *   затем в /var/mamkin-analitik/.
   * @returns {Promise<Object>} загруженный шаблон
   * @throws {Error} если файл не найден, невалиден или не immutable
   */
  async load(filePath) {
    if (filePath) {
      this.template = this._readAndParse(filePath);
    } else {
      this.template = this._findAndLoad();
    }

    this._validate(this.template);

    // Индексируем блоки и подразделы для быстрого доступа
    this.blocks = this.template.blocks;
    this._buildIndexes();

    this._loaded = true;
    return this.template;
  }

  /**
   * Загружает шаблон синхронно (без async, для обратной совместимости).
   * @param {string} [filePath]
   * @returns {Object}
   */
  loadSync(filePath) {
    if (filePath) {
      this.template = JSON.parse(fs.readFileSync(filePath, 'utf-8'));
    } else {
      this.template = this._findAndLoad();
    }

    this._validate(this.template);
    this.blocks = this.template.blocks;
    this._buildIndexes();
    this._loaded = true;
    return this.template;
  }

  // ========== Public API ==========

  /**
   * Возвращает количество блоков в шаблоне.
   * @returns {number} всегда 7 для валидного шаблона
   */
  getBlockCount() {
    this._ensureLoaded();
    return this.blocks.length;
  }

  /**
   * Возвращает блок по номеру (1-7) или ключу ('block.1').
   *
   * @param {number|string} id — номер блока (1..7) или ключ ('block.1')
   * @returns {Object} блок с полями: id, key, name, description, subsections, completenessCriteria
   * @throws {Error} если блок не найден или шаблон не загружен
   */
  getBlock(id) {
    this._ensureLoaded();

    const block = this._blockMap.get(id);
    if (!block) {
      throw new Error(`TemplateEngine: блок "${id}" не найден`);
    }
    return this._deepFreeze(block);
  }

  /**
   * Возвращает вопросы L1/L2/L3 для указанного подраздела.
   *
   * @param {number|string} blockId — номер блока (1..7) или ключ ('block.1')
   * @param {string} subId — идентификатор подраздела ('1.1', '1.2', ...)
   * @returns {Object} { id, name, questions: { L1, L2, L3 } }
   * @throws {Error} если блок или подраздел не найдены
   */
  getSubsection(blockId, subId) {
    this._ensureLoaded();

    // Определяем полный ключ подраздела
    const fullKey = subId.includes('.') ? subId : `${blockId}.${subId}`;

    // Ищем по карте подразделов
    const entry = this._subsectionMap.get(fullKey);
    if (entry) {
      return this._deepFreeze(entry.subsection);
    }

    // Fallback: ищем вручную
    const block = this._resolveBlock(blockId);
    const subsection = block.subsections.find(s => s.id === fullKey);
    if (!subsection) {
      throw new Error(
        `TemplateEngine: подраздел "${fullKey}" не найден в блоке ${blockId}`
      );
    }
    return this._deepFreeze(subsection);
  }

  /**
   * Возвращает следующий подраздел после указанного.
   *
   * @param {number|string} blockId — номер блока (1..7) или ключ ('block.1')
   * @param {string} subId — текущий подраздел ('1.1')
   * @returns {Object|null} следующий подраздел { id, name, questions } или null, если это конец
   */
  getNextSubsection(blockId, subId) {
    this._ensureLoaded();

    const fullKey = subId.includes('.') ? subId : `${blockId}.${subId}`;

    // Нормализуем blockId: 'block.3' → 3, '3' → 3
    let currentBlockNum;
    if (typeof blockId === 'number') {
      currentBlockNum = blockId;
    } else if (blockId.startsWith('block.')) {
      currentBlockNum = parseInt(blockId.slice(6), 10);
    } else {
      currentBlockNum = parseInt(blockId, 10);
    }

    // Ищем текущий подраздел в текущем блоке
    const currentBlock = this._resolveBlock(currentBlockNum);
    const currentIdx = currentBlock.subsections.findIndex(s => s.id === fullKey);

    if (currentIdx === -1) {
      throw new Error(
        `TemplateEngine: подраздел "${fullKey}" не найден в блоке ${currentBlockNum}`
      );
    }

    // Следующий подраздел в том же блоке
    if (currentIdx + 1 < currentBlock.subsections.length) {
      return this._deepFreeze(currentBlock.subsections[currentIdx + 1]);
    }

    // Переход к следующему блоку
    const nextBlockNum = currentBlockNum + 1;
    if (nextBlockNum <= this.blocks.length) {
      const nextBlock = this._resolveBlock(nextBlockNum);
      if (nextBlock.subsections.length > 0) {
        return this._deepFreeze(nextBlock.subsections[0]);
      }
    }

    // Конец шаблона
    return null;
  }

  /**
   * Возвращает L1-вопрос первого подраздела первого блока.
   * Удобно для старта опроса.
   *
   * @returns {Object} { blockId, subsectionId, question, depth }
   */
  getFirstQuestion() {
    this._ensureLoaded();

    const firstBlock = this.blocks[0];
    const firstSub = firstBlock.subsections[0];
    return this._deepFreeze({
      blockId: firstBlock.id,
      blockName: firstBlock.name,
      subsectionId: firstSub.id,
      subsectionName: firstSub.name,
      question: firstSub.questions.L1,
      depth: 'L1'
    });
  }

  /**
   * Возвращает вопрос для указанного подраздела и глубины (L1/L2/L3).
   *
   * @param {string} subsectionKey — ключ подраздела ('1.1')
   * @param {string} depth — уровень глубины ('L1'|'L2'|'L3')
   * @returns {string} текст вопроса
   * @throws {Error} если подраздел или уровень не найдены
   */
  getQuestion(subsectionKey, depth) {
    this._ensureLoaded();

    const entry = this._subsectionMap.get(subsectionKey);
    if (!entry) {
      throw new Error(
        `TemplateEngine: подраздел "${subsectionKey}" не найден`
      );
    }

    const question = entry.subsection.questions[depth];
    if (!question) {
      throw new Error(
        `TemplateEngine: вопрос уровня "${depth}" не найден для подраздела "${subsectionKey}"`
      );
    }
    return question;
  }

  /**
   * Возвращает массив всех блоков.
   * @returns {Object[]}
   */
  getAllBlocks() {
    this._ensureLoaded();
    return this._deepFreeze([...this.blocks]);
  }

  /**
   * Возвращает полный объект загруженного шаблона (read-only копия).
   * @returns {Object}
   */
  getTemplate() {
    this._ensureLoaded();
    return this._deepFreeze({ ...this.template });
  }

  /**
   * Read-only режим: любые попытки записи игнорируются.
   * @throws {Error} всегда
   */
  write() {
    throw new Error(
      'TemplateEngine: шаблон работает в read-only режиме. ' +
      'Изменения template.json запрещены — это immutable источник истины.'
    );
  }

  /**
   * Алиас для write().
   * @throws {Error} всегда
   */
  save() {
    return this.write();
  }

  /**
   * Алиас для write().
   * @throws {Error} всегда
   */
  update() {
    return this.write();
  }

  // ========== Private Methods ==========

  /**
   * @private
   * Читает и парсит JSON-файл.
   */
  _readAndParse(filePath) {
    const absolutePath = path.resolve(filePath);
    if (!fs.existsSync(absolutePath)) {
      throw new Error(
        `TemplateEngine: файл шаблона не найден: ${absolutePath}`
      );
    }
    const raw = fs.readFileSync(absolutePath, 'utf-8');
    return JSON.parse(raw);
  }

  /**
   * @private
   * Ищет template.json: сначала data/template.json (workspace),
   * затем /var/mamkin-analitik/.
   */
  _findAndLoad() {
    const workspacePath = path.resolve(__dirname, '..', 'data', 'template.json');

    for (const p of [workspacePath, ...STORAGE_PATHS]) {
      if (fs.existsSync(p)) {
        const raw = fs.readFileSync(p, 'utf-8');
        return JSON.parse(raw);
      }
    }

    throw new Error(
      'TemplateEngine: template.json не найден. ' +
      'Проверьте data/template.json или /var/mamkin-analitik/sessions/template.json'
    );
  }

  /**
   * @private
   * Валидирует целостность template.json.
   */
  _validate(template) {
    const errors = [];

    // 1. Проверка meta
    if (!template || typeof template !== 'object') {
      throw new Error('TemplateEngine: template.json должен быть объектом');
    }
    if (!template.meta) {
      errors.push('Отсутствует meta');
    } else {
      if (template.meta.immutable !== true) {
        errors.push('meta.immutable должен быть true');
      }
      if (!template.meta.version) {
        errors.push('Отсутствует meta.version');
      }
      if (!template.meta.name) {
        errors.push('Отсутствует meta.name');
      }
    }

    // 2. Проверка blocks
    if (!Array.isArray(template.blocks)) {
      throw new Error('TemplateEngine: template.blocks должен быть массивом');
    }

    if (template.blocks.length !== EXPECTED_BLOCK_COUNT) {
      errors.push(
        `Шаблон должен содержать ${EXPECTED_BLOCK_COUNT} блоков, ` +
        `найдено ${template.blocks.length}`
      );
    }

    // 3. Проверка каждого блока
    const seenKeys = new Set();
    const seenIds = new Set();

    for (let i = 0; i < template.blocks.length; i++) {
      const block = template.blocks[i];
      const idx = i + 1;

      if (!block.id) {
        errors.push(`Блок #${idx}: отсутствует id`);
      } else if (seenIds.has(block.id)) {
        errors.push(`Блок #${idx}: дублирующийся id "${block.id}"`);
      } else if (typeof block.id === 'number' && !EXPECTED_BLOCK_IDS.includes(block.id)) {
        errors.push(`Блок #${idx}: невалидный id "${block.id}" (допустимы 1-7)`);
      }
      seenIds.add(block.id);

      if (!block.key) {
        errors.push(`Блок #${idx}: отсутствует key`);
      } else if (seenKeys.has(block.key)) {
        errors.push(`Блок #${idx}: дублирующийся key "${block.key}"`);
      } else {
        const expectedKey = `block.${block.id || idx}`;
        if (block.key !== expectedKey) {
          errors.push(
            `Блок #${idx}: key "${block.key}" не соответствует ожидаемому "${expectedKey}"`
          );
        }
      }
      seenKeys.add(block.key);

      if (!block.name) {
        errors.push(`Блок #${idx}: отсутствует name`);
      }

      // 4. Проверка подразделов
      if (!Array.isArray(block.subsections) || block.subsections.length === 0) {
        errors.push(`Блок "${block.key || idx}": нет подразделов`);
      } else {
        for (let j = 0; j < block.subsections.length; j++) {
          const sub = block.subsections[j];

          if (!sub.id) {
            errors.push(`Блок "${block.key}" подраздел #${j + 1}: отсутствует id`);
          }

          if (!sub.name) {
            errors.push(`Блок "${block.key}" подраздел "${sub.id}": отсутствует name`);
          }

          if (!sub.questions || typeof sub.questions !== 'object') {
            errors.push(
              `Блок "${block.key}" подраздел "${sub.id}": отсутствуют questions`
            );
          } else {
            for (const depth of REQUIRED_DEPTHS) {
              if (!sub.questions[depth]) {
                errors.push(
                  `Блок "${block.key}" подраздел "${sub.id}": отсутствует вопрос ${depth}`
                );
              }
            }
          }
        }
      }
    }

    if (errors.length > 0) {
      throw new Error(
        `TemplateEngine: ошибки валидации template.json:\n  - ${errors.join('\n  - ')}`
      );
    }
  }

  /**
   * @private
   * Строит индексы для быстрого доступа по ключам.
   */
  _buildIndexes() {
    this._blockMap.clear();
    this._subsectionMap.clear();

    for (const block of this.blocks) {
      // Индекс по числовому id
      this._blockMap.set(block.id, block);
      // Индекс по строковому key
      this._blockMap.set(block.key, block);

      for (const sub of block.subsections) {
        this._subsectionMap.set(sub.id, { block, subsection: sub });
      }
    }
  }

  /**
   * @private
   * Гарантирует, что шаблон загружен.
   */
  _ensureLoaded() {
    if (!this._loaded || !this.template) {
      throw new Error(
        'TemplateEngine: шаблон не загружен. Вызовите load() перед использованием.'
      );
    }
  }

  /**
   * @private
   * Разрешает блок по числу или ключу.
   */
  _resolveBlock(id) {
    const block = this._blockMap.get(id);
    if (!block) {
      // Попытка привести к числу
      const numericId = typeof id === 'string' && !id.startsWith('block.')
        ? parseInt(id, 10)
        : id;
      const resolved = this._blockMap.get(numericId);
      if (!resolved) {
        throw new Error(`TemplateEngine: блок "${id}" не найден`);
      }
      return resolved;
    }
    return block;
  }

  /**
   * @private
   * Замораживает объект (и вложенные) для read-only доступа.
   */
  _deepFreeze(obj) {
    if (obj && typeof obj === 'object' && !Object.isFrozen(obj)) {
      const props = Object.getOwnPropertyNames(obj);
      for (const prop of props) {
        const val = obj[prop];
        if (val && typeof val === 'object') {
          this._deepFreeze(val);
        }
      }
      return Object.freeze(obj);
    }
    return obj;
  }
}

module.exports = TemplateEngine;
