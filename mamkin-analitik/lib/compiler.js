/**
 * Compiler — движок агента-составителя
 *
 * Story 3.1 — Формирование текста БТ по шаблону (FR12, FR13)
 *
 * Принимает Session Context (все ответы на 7 блоков, риски)
 * и формирует структурированный черновик документа бизнес-требований
 * по утверждённому шаблону (7 блоков).
 *
 * API:
 *   compileDraft(sessionContext)    — основная точка входа
 *   formatBlock(blockId, answers)   — форматирование одного блока
 *   formatSubsection(subId, answers) — форматирование подраздела
 *   buildDraftDocument(sessionContext) — полная сборка документа
 *   getCurrentDraft()               — текущее состояние черновика
 */

const path = require('path');
const { createLogger } = require('./logger');

/**
 * @typedef {Object} DraftBlock
 * @property {number} blockId
 * @property {string} blockName
 * @property {string} content — отформатированный текст блока
 * @property {Array<{subsectionId: string, subsectionName: string, text: string, depthReached: string}>} subsections
 */

/**
 * @typedef {Object} DraftDocument
 * @property {string} title — название документа
 * @property {string} createdAt — дата создания
 * @property {string} sessionId — ID сессии
 * @property {number} telegramUserId — ID пользователя
 * @property {number} totalBlocks — количество блоков (7)
 * @property {Array<DraftBlock>} blocks — массив блоков
 * @property {object} risks — структурированные риски
 * @property {number} completedSubsections — количество заполненных подразделов
 * @property {number} totalSubsections — общее количество подразделов
 * @property {string} fullText — полный текст документа
 */

class Compiler {
  constructor(deps = {}) {
    this.templateEngine = deps.templateEngine || null;
    this.logger = createLogger('compiler');

    /** @type {DraftDocument|null} */
    this._currentDraft = null;

    // Список фраз, указывающих на "не применимо"
    this.NOT_APPLICABLE_PHRASES = [
      'не применимо', 'н/п', 'n/a', 'не знаю', 'затрудняюсь ответить',
      'нет ответа', 'пропустить', 'не относ', 'не актуально',
      'применить нельзя', 'не имеет отношения'
    ];

    // Список "мусорных" однословных ответов
    this.TRIVIAL_ANSWERS = [
      'да', 'нет', 'не знаю', 'возможно', 'наверное',
      'ok', 'ок', 'хорошо', 'понятно', 'норм', 'ага'
    ];
  }

  // ==================== Main Entry Point ====================

  /**
   * Основная точка входа: принимает Session Context и формирует
   * структурированный черновик документа.
   *
   * @param {object} sessionContext — Session Context (из survey-engine)
   * @returns {DraftDocument} структурированный черновик
   * @throws {Error} если контекст невалиден или нет templateEngine
   */
  compileDraft(sessionContext) {
    if (!sessionContext) {
      throw new Error('Compiler: Session Context обязателен для compileDraft');
    }
    if (!this.templateEngine) {
      throw new Error('Compiler: TemplateEngine не подключён');
    }
    if (!sessionContext.answers || Object.keys(sessionContext.answers).length === 0) {
      throw new Error('Compiler: нет ответов для формирования документа');
    }

    this.logger.info('Starting draft compilation', {
      sessionId: sessionContext.sessionId,
      answersCount: Object.keys(sessionContext.answers).length,
      risksCount: (sessionContext.risks || []).length
    });

    // Формируем документ
    const draft = this.buildDraftDocument(sessionContext);

    // Сохраняем как текущий черновик
    this._currentDraft = draft;

    this.logger.info('Draft compilation complete', {
      sessionId: sessionContext.sessionId,
      totalBlocks: draft.totalBlocks,
      completedSubsections: draft.completedSubsections,
      totalSubsections: draft.totalSubsections,
      fullTextLength: draft.fullText.length
    });

    return draft;
  }

  // ==================== Block Formatting ====================

  /**
   * Форматирует один блок шаблона: заголовок + заполненные подразделы.
   *
   * @param {number} blockId — номер блока (1-7)
   * @param {object} answers — ответы пользователя для этого блока
   *   { '1.1': { L1: '...', L2: null, L3: null, depthReached: 'L1' }, ... }
   * @returns {DraftBlock|null} отформатированный блок или null, если блок не найден
   */
  formatBlock(blockId, answers) {
    if (!this.templateEngine) {
      throw new Error('Compiler: TemplateEngine не подключён');
    }

    let block;
    try {
      block = this.templateEngine.getBlock(blockId);
    } catch (err) {
      this.logger.warn('Block not found', { blockId, error: err.message });
      return null;
    }

    const subsections = [];

    // Форматируем каждый подраздел блока
    for (const sub of block.subsections) {
      const subKey = sub.id;
      const sectionAnswers = (answers && answers[subKey]) ? answers[subKey] : null;

      const formatted = this.formatSubsection(subKey, sectionAnswers);
      subsections.push({
        subsectionId: subKey,
        subsectionName: sub.name,
        text: formatted,
        depthReached: sectionAnswers ? (sectionAnswers.depthReached || 'none') : 'none'
      });
    }

    // Собираем полный текст блока
    const contentLines = [
      `## Блок ${blockId}. ${block.name}`,
      '',
      `*${block.description}*`,
      ''
    ];

    for (const sub of subsections) {
      contentLines.push(`### ${sub.subsectionId}. ${sub.subsectionName}`);
      contentLines.push('');
      contentLines.push(sub.text);
      contentLines.push('');
    }

    // Удаляем лишний перенос в конце
    if (contentLines[contentLines.length - 1] === '') {
      contentLines.pop();
    }

    return {
      blockId,
      blockName: block.name,
      content: contentLines.join('\n'),
      subsections
    };
  }

  /**
   * Форматирует один подраздел: L1/L2/L3 ответы → формальный стиль БТ.
   * Принципы:
   *   - Чёткие формулировки, без художественных оборотов (FR13)
   *   - Ответы переформулированы в формальный стиль
   *   - Если ответ отсутствует или "не применимо" → отметка
   *
   * @param {string} subId — идентификатор подраздела ('1.1')
   * @param {object|null} answers — ответы на подраздел { L1, L2, L3, depthReached }
   * @returns {string} отформатированный текст подраздела
   */
  formatSubsection(subId, answers) {
    // Если ответа нет — отметка
    if (!answers) {
      return '— *Не заполнено.* Ответ на данный подраздел не предоставлен.';
    }

    // Определяем максимальную глубину ответа — приоритет L3 > L2 > L1
    const bestAnswer = answers.L3 || answers.L2 || answers.L1;
    const depthReached = answers.depthReached || 'L1';

    // Если нет текста ответа
    if (!bestAnswer || bestAnswer.trim().length === 0) {
      return '— *Не заполнено.* Ответ на данный подраздел не предоставлен.';
    }

    // Проверка на "не применимо"
    const lowerAnswer = bestAnswer.trim().toLowerCase();
    const isNotApplicable = this.NOT_APPLICABLE_PHRASES.some(
      phrase => lowerAnswer.startsWith(phrase) || lowerAnswer === phrase
    );
    if (isNotApplicable) {
      return '— *Не применимо* (указано пользователем).';
    }

    // Проверка на тривиальный ответ
    const isTrivial = this.TRIVIAL_ANSWERS.includes(lowerAnswer.trim());
    if (isTrivial) {
      return '— *Поверхностный ответ.* Требуется уточнение.';
    }

    // Форматируем ответ в формальный стиль БТ
    let formatted = this._formatToFormalStyle(bestAnswer, depthReached);

    // Добавляем информацию о глубине проработки
    const depthLabels = {
      'L1': 'Поверхностная проработка (L1)',
      'L2': 'Детальная проработка (L2)',
      'L3': 'Глубокая проработка с анализом коренных причин (L3)'
    };
    const depthLabel = depthLabels[depthReached] || `Уровень проработки: ${depthReached}`;

    formatted += `\n  *Уровень проработки:* ${depthLabel}.`;

    return formatted;
  }

  // ==================== Full Document Assembly ====================

  /**
   * Собирает полный документ: заголовок, метаданные, 7 блоков, риски.
   *
   * @param {object} sessionContext — Session Context
   * @returns {DraftDocument} полный структурированный документ
   */
  buildDraftDocument(sessionContext) {
    if (!this.templateEngine) {
      throw new Error('Compiler: TemplateEngine не подключён');
    }

    const totalBlocks = this.templateEngine.getBlockCount();
    const answers = sessionContext.answers;
    const risks = sessionContext.risks || [];

    // Группируем ответы по блокам
    const answersByBlock = {};
    for (const [key, value] of Object.entries(answers)) {
      const blockId = key.split('.')[0];
      if (!answersByBlock[blockId]) {
        answersByBlock[blockId] = {};
      }
      answersByBlock[blockId][key] = value;
    }

    // Форматируем каждый блок
    const blocks = [];
    let completedSubsections = 0;
    let totalSubsections = 0;

    for (let b = 1; b <= totalBlocks; b++) {
      const blockAnswers = answersByBlock[String(b)] || {};

      const block = this.formatBlock(b, blockAnswers);
      if (block) {
        blocks.push(block);

        // Считаем статистику
        totalSubsections += block.subsections.length;
        completedSubsections += block.subsections.filter(
          s => s.depthReached !== 'none'
        ).length;
      }
    }

    // Структурируем риски
    const riskSection = this._formatRisks(risks);

    // Собираем полный текст документа
    const documentParts = [];

    // 1. Титул
    documentParts.push('# Документ бизнес-требований');
    documentParts.push('');
    documentParts.push(`*Сформирован:* ${new Date().toLocaleDateString('ru-RU')}`);
    documentParts.push(`*Сессия:* ${sessionContext.sessionId}`);
    documentParts.push(`*Пользователь:* ${sessionContext.telegramUserId}`);
    documentParts.push('');

    // 2. Блоки
    for (const block of blocks) {
      documentParts.push(block.content);
      documentParts.push('');
    }

    // 3. Риски (если есть)
    if (riskSection) {
      documentParts.push('---');
      documentParts.push('');
      documentParts.push(riskSection);
    }

    // Удаляем последний перенос
    while (documentParts.length > 0 && documentParts[documentParts.length - 1] === '') {
      documentParts.pop();
    }

    const fullText = documentParts.join('\n');

    return {
      title: 'Документ бизнес-требований',
      createdAt: new Date().toISOString(),
      sessionId: sessionContext.sessionId,
      telegramUserId: sessionContext.telegramUserId,
      totalBlocks,
      blocks,
      risks: {
        total: risks.length,
        byCategory: this._groupRisksByCategory(risks),
        items: risks.map(r => ({
          text: r.text,
          category: r.category || 'uncategorized',
          probability: r.probability,
          impact: r.impact,
          mitigation: r.mitigation
        }))
      },
      completedSubsections,
      totalSubsections,
      fullText
    };
  }

  /**
   * Возвращает текущее состояние черновика.
   * @returns {DraftDocument|null}
   */
  getCurrentDraft() {
    return this._currentDraft;
  }

  /**
   * Сбрасывает текущий черновик.
   */
  resetDraft() {
    this._currentDraft = null;
  }

  // ==================== Private Methods ====================

  /**
   * Переформулирует ответ пользователя в формальный стиль БТ.
   * Правила:
   *   - Убираются разговорные фразы ("ну", "типа", "как бы")
   *   - Сохраняется смысл и факты
   *   - Формулировка чёткая, без художественных оборотов
   *   - Добавляются термины бизнес-требований где уместно
   *
   * @param {string} answer — оригинальный ответ пользователя
   * @param {string} depthReached — достигнутая глубина
   * @returns {string} форматированный текст
   * @private
   */
  _formatToFormalStyle(answer, depthReached) {
    if (!answer || answer.trim().length === 0) {
      return '— *Нет данных.*';
    }

    let text = answer.trim();

    // Удаляем разговорные частицы в начале
    // Кириллица не поддерживается \b в JS, используем явное начало строки
    const leadingParticles = ['ну', 'типа', 'как бы', 'в общем', 'короче', 'значит', 'так вот', 'вообще', 'слушай', 'понимаешь', 'видишь'];
    for (const particle of leadingParticles) {
      const re = new RegExp(`^${particle.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}\\s*,?\\s*`, 'i');
      text = text.replace(re, '');
    }

    // Удаляем лишние заполнители в середине
    // Примечание: \b не работает с кириллицей в JS, используем ручной обход
    const fillers = ['как бы', 'типа', 'ну вот', 'ну типа', 'вроде как', 'как бэ'];
    for (const filler of fillers) {
      // Ищем заполнитель как отдельное слово (окружённое пробелами, запятыми или началом/концом)
      const re = new RegExp(`(^|[\\s,;-])${filler.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}(?=[\\s,;.!?]|$)`, 'gi');
      text = text.replace(re, '$1');
    }

    // Заменяем многоточия и повторяющиеся знаки препинания
    text = text.replace(/\.{3,}/g, '...');
    text = text.replace(/!{2,}/g, '!');
    text = text.replace(/\?{2,}/g, '?');
    text = text.replace(/,,+/g, ',');

    // Удаляем лишние пробелы
    text = text.replace(/\s{2,}/g, ' ');

    // Капитализируем первую букву
    text = text.charAt(0).toUpperCase() + text.slice(1);

    // Добавляем точку в конце, если её нет
    if (text.length > 0 && !/[.!?…]/.test(text[text.length - 1])) {
      text += '.';
    }

    // Форматируем с новой строки (единый стиль БТ)
    return this._indentParagraph(text);
  }

  /**
   * Форматирует параграф с отступом и стилем БТ.
   * @param {string} text
   * @returns {string}
   * @private
   */
  _indentParagraph(text) {
    const sentences = text.split(/(?<=[.!?])\s+/);
    if (sentences.length <= 1) {
      return `— ${text}`;
    }

    const formatted = sentences.map((s, i) => {
      const trimmed = s.trim();
      if (trimmed.length === 0) return '';
      return (i === 0) ? `— ${trimmed}` : `  ${trimmed}`;
    }).filter(s => s.length > 0).join('\n');

    return formatted;
  }

  /**
   * Форматирует риски в структурированный раздел.
   * @param {Array} risks — массив рисков
   * @returns {string|null} отформатированный текст или null
   * @private
   */
  _formatRisks(risks) {
    if (!risks || risks.length === 0) {
      return null;
    }

    const lines = [
      '## Блок 7. Риски и митигации',
      '',
      '*Идентифицированные риски и меры по их снижению.*',
      ''
    ];

    // Группируем по категориям
    const byCategory = this._groupRisksByCategory(risks);

    for (const [category, catRisks] of Object.entries(byCategory)) {
      const categoryLabel = this._getCategoryLabel(category);
      lines.push(`### ${categoryLabel}`);
      lines.push('');

      for (let i = 0; i < catRisks.length; i++) {
        const risk = catRisks[i];
        lines.push(`**Риск ${i + 1}.** ${risk.text}`);

        if (risk.probability !== null && risk.probability !== undefined) {
          lines.push(`  *Вероятность:* ${this._formatRiskLevel(risk.probability)}`);
        }
        if (risk.impact !== null && risk.impact !== undefined) {
          lines.push(`  *Влияние:* ${this._formatRiskLevel(risk.impact)}`);
        }
        if (risk.mitigation) {
          lines.push(`  *Митигация:* ${risk.mitigation}`);
        }
        lines.push('');
      }
    }

    // Удаляем последний перенос
    if (lines[lines.length - 1] === '') {
      lines.pop();
    }

    return lines.join('\n');
  }

  /**
   * Группирует риски по категориям.
   * @param {Array} risks
   * @returns {object} { category: [risks] }
   * @private
   */
  _groupRisksByCategory(risks) {
    const byCategory = {};
    for (const risk of risks) {
      const cat = risk.category || 'uncategorized';
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(risk);
    }
    return byCategory;
  }

  /**
   * Возвращает русскоязычную метку категории риска.
   * @param {string} category
   * @returns {string}
   * @private
   */
  _getCategoryLabel(category) {
    const labels = {
      'technical': 'Технические риски',
      'org': 'Организационные риски',
      'organizational': 'Организационные риски',
      'business': 'Бизнес-риски',
      'adoption': 'Риски внедрения',
      'uncategorized': 'Прочие риски'
    };
    return labels[category] || category;
  }

  /**
   * Форматирует числовой уровень риска в текстовый.
   * @param {number} level — от 0 до 1
   * @returns {string}
   * @private
   */
  _formatRiskLevel(level) {
    if (level >= 0.7) return 'Высокая';
    if (level >= 0.4) return 'Средняя';
    if (level >= 0.1) return 'Низкая';
    return 'Не определена';
  }
}

module.exports = Compiler;
