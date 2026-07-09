/**
 * Draft Generator — финальное формирование черновика бизнес-требований
 *
 * Story 3.6 — Final Draft Formation (FR14)
 *
 * Принимает:
 *   - session (объект сессии с answers, risks, compiler.draft, qualityGate)
 *   - templateEngine (для валидации 7-блочной структуры)
 *
 * Возвращает:
 *   - session.draft — финальный черновик, готовый для агента-генератора
 *
 * Алгоритм:
 *   1. Валидация: контролёр одобрил (approved=true)
 *   2. Сборка draft из 7 блоков template.json (immutable)
 *   3. Каждый подраздел: 1-3 параграфа + depthReached
 *   4. Консолидация рисков из session.risks
 *   5. Маркировка depthReached для каждого подраздела
 *   6. Статус сессии → 'draft_ready'
 */

const path = require('path');
const { createLogger } = require('./logger');

/** @typedef {import('./template-engine')} TemplateEngine */

class DraftGenerator {
  /**
   * @param {object} deps
   * @param {TemplateEngine} deps.templateEngine — экземпляр TemplateEngine
   * @param {object} [deps.logger] — опциональный логгер
   */
  constructor(deps = {}) {
    /** @type {TemplateEngine} */
    this.templateEngine = deps.templateEngine || null;
    this.logger = deps.logger || createLogger('draft-generator');
  }

  // ==================== PUBLIC API ====================

  /**
   * Основной метод: формирует финальный черновик документа.
   *
   * @param {object} session — объект сессии
   * @param {object} [context] — опциональный Session Context
   * @returns {{ draft: object, session: object }} — черновик + обновлённая сессия
   * @throws {Error} если контролёр не одобрил, нет templateEngine, нет ответов
   */
  generateDraft(session, context) {
    if (!this.templateEngine) {
      throw new Error('DraftGenerator: TemplateEngine не подключён');
    }

    const sessionObj = context && context.sessionId ? context : session;

    // 1. Валидация контролёра
    this._assertControllerApproved(sessionObj);

    // 2. Валидация answers
    this._assertAnswersExist(sessionObj);

    this.logger.info('DraftGenerator.generateDraft started', {
      sessionId: sessionObj.sessionId,
      answersCount: Object.keys(sessionObj.answers || {}).length,
      risksCount: (sessionObj.risks || []).length
    });

    // 3. Строим 7 блоков согласно template.json
    const blocks = this._buildBlocks(sessionObj);

    // 4. Консолидируем риски
    const risks = this.consolidateRisks(sessionObj);

    // 5. Собираем финальную структуру draft
    const draft = this._assembleDraftDocument(sessionObj, blocks, risks);

    // 6. Добавляем depth labels к каждому подразделу
    this.addDepthLabels(draft);

    // 7. Отмечаем статус ready
    this.markAsDraft(sessionObj, draft);

    // Записываем draft в session
    sessionObj.draft = draft;

    this.logger.info('DraftGenerator.generateDraft completed', {
      sessionId: sessionObj.sessionId,
      totalBlocks: draft.totalBlocks,
      completedSubsections: draft.completedSubsections,
      totalSubsections: draft.totalSubsections,
      fullTextLength: draft.fullText.length,
      risksConsolidated: draft.risks.total
    });

    return { draft, session: sessionObj };
  }

  /**
   * Консолидирует все риски из диалога в единый структурированный блок.
   *
   * @param {object} session — объект сессии
   * @returns {{ total: number, byCategory: object, items: Array<object> }}
   */
  consolidateRisks(session) {
    const risks = session.risks || [];

    // Группируем по категориям
    const byCategory = {};
    for (const risk of risks) {
      const cat = risk.category || 'uncategorized';
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push({
        text: risk.text,
        category: cat,
        collectedAt: risk.collectedAt || null,
        probability: risk.probability || null,
        impact: risk.impact || null,
        mitigation: risk.mitigation || null,
        timestamp: risk.timestamp || null
      });
    }

    // Сортируем категории: сначала критические
    const categoryOrder = ['technical', 'business', 'org', 'organizational', 'adoption', 'uncategorized'];
    const sorted = {};
    for (const cat of categoryOrder) {
      if (byCategory[cat]) {
        sorted[cat] = byCategory[cat];
      }
    }
    // Добавляем оставшиеся категории
    for (const cat of Object.keys(byCategory)) {
      if (!sorted[cat]) {
        sorted[cat] = byCategory[cat];
      }
    }

    this.logger.debug('Risks consolidated', {
      total: risks.length,
      categories: Object.keys(sorted).join(', ')
    });

    return {
      total: risks.length,
      byCategory: sorted,
      items: risks.map(r => ({
        text: r.text,
        category: r.category || 'uncategorized',
        probability: r.probability,
        impact: r.impact,
        mitigation: r.mitigation,
        collectedAt: r.collectedAt
      }))
    };
  }

  /**
   * Добавляет depth labels к каждому подразделу в draft.
   * Модифицирует draft in-place.
   *
   * @param {object} draft — объект черновика
   * @returns {object} draft (для чейнинга)
   */
  addDepthLabels(draft) {
    if (!draft || !draft.blocks) return draft;

    const LABELS = {
      'L1': 'Поверхностная проработка (L1) — общее описание',
      'L2': 'Детальная проработка (L2) — с примерами и контекстом',
      'L3': 'Глубокая проработка с анализом коренных причин (L3)',
      'none': 'Не заполнено'
    };

    for (const block of draft.blocks) {
      for (const sub of block.subsections) {
        const label = LABELS[sub.depthReached] || `Уровень проработки: ${sub.depthReached}`;
        sub.depthLabel = label;
      }
    }

    return draft;
  }

  /**
   * Отмечает сессию как draft_ready.
   *
   * @param {object} session — объект сессии (модифицируется in-place)
   * @param {object} draft — объект черновика
   * @returns {object} session
   */
  markAsDraft(session, draft) {
    session.status = 'draft_ready';
    session.draftReadyAt = new Date().toISOString();
    session.updatedAt = new Date().toISOString();
    session.documentReady = true;

    if (draft) {
      draft.status = 'draft_ready';
      draft.readyAt = session.draftReadyAt;
    }

    this.logger.info('Session marked as draft_ready', {
      sessionId: session.sessionId,
      timestamp: session.draftReadyAt
    });

    return session;
  }

  // ==================== PRIVATE METHODS ====================

  /**
   * Проверяет, что контролёр одобрил черновик.
   * Допускает force_accept (достигнут maxIterations).
   *
   * @param {object} session
   * @throws {Error} если не одобрено
   * @private
   */
  _assertControllerApproved(session) {
    const qg = session.qualityGate;
    if (!qg) {
      throw new Error(
        'DraftGenerator: qualityGate отсутствует. ' +
        'Черновик должен пройти проверку контролёром перед формированием финального draft.'
      );
    }

    if (!qg.approved) {
      throw new Error(
        `DraftGenerator: контролёр не одобрил черновик (итерация ${qg.iteration || 1}). ` +
        'Требуется доработка и повторная проверка.'
      );
    }

    this.logger.debug('Controller approval verified', {
      approved: true,
      iteration: qg.iteration,
      overallScore: qg.overallScore,
      issuesCount: (qg.issues || []).length
    });
  }

  /**
   * Проверяет наличие ответов в сессии.
   *
   * @param {object} session
   * @throws {Error} если нет ответов
   * @private
   */
  _assertAnswersExist(session) {
    if (!session.answers || Object.keys(session.answers).length === 0) {
      throw new Error(
        'DraftGenerator: нет ответов для формирования черновика. ' +
        'Сессия должна содержать answers с хотя бы одним ответом.'
      );
    }
  }

  /**
   * Строит массив блоков согласно template.json, заполняя каждый подраздел
   * из ответов пользователя.
   *
   * @param {object} session
   * @returns {Array<object>} блоки
   * @private
   */
  _buildBlocks(session) {
    const totalBlocks = this.templateEngine.getBlockCount();
    const blocks = [];

    for (let b = 1; b <= totalBlocks; b++) {
      const blockTemplate = this.templateEngine.getBlock(b);
      const block = this._buildBlock(blockTemplate, session);
      blocks.push(block);
    }

    return blocks;
  }

  /**
   * Строит один блок с заполненными подразделами.
   *
   * @param {object} blockTemplate — шаблон блока из template.json
   * @param {object} session
   * @returns {object} заполненный блок
   * @private
   */
  _buildBlock(blockTemplate, session) {
    const subsections = [];

    for (const subTemplate of blockTemplate.subsections) {
      const subKey = subTemplate.id;
      const answer = session.answers[subKey];

      const subsection = this._buildSubsection(subTemplate, answer);
      subsections.push(subsection);
    }

    return {
      blockId: blockTemplate.id,
      blockName: blockTemplate.name,
      blockDescription: blockTemplate.description,
      content: this._formatBlockContent(blockTemplate, subsections),
      subsections
    };
  }

  /**
   * Строит один подраздел: 1-3 параграфа + depthReached.
   *
   * @param {object} subTemplate — шаблон подраздела
   * @param {object|null} answer — ответ пользователя { L1, L2, L3, depthReached }
   * @returns {object} подраздел
   * @private
   */
  _buildSubsection(subTemplate, answer) {
    const subsection = {
      subsectionId: subTemplate.id,
      subsectionName: subTemplate.name,
      depthReached: 'none',
      depthLabel: 'Не заполнено',
      text: '',
      paragraphs: []
    };

    if (!answer) {
      subsection.text = '— *Не заполнено.* Ответ на данный подраздел не предоставлен.';
      subsection.paragraphs = [subsection.text];
      return subsection;
    }

    const depthReached = answer.depthReached || 'L1';
    subsection.depthReached = depthReached;

    // Собираем текст: приоритет L3 > L2 > L1
    const texts = [];
    const depthNames = ['L3', 'L2', 'L1'];
    const usedDepths = [];

    for (const depth of depthNames) {
      if (answer[depth] && answer[depth].trim().length > 0) {
        texts.push(answer[depth]);
        usedDepths.push(depth);
      }
    }

    if (texts.length === 0) {
      subsection.text = '— *Не заполнено.* Ответ на данный подраздел не предоставлен.';
      subsection.paragraphs = [subsection.text];
      return subsection;
    }

    // Форматируем: 1-3 параграфа (объединяем L1+L2 и L3 отдельно)
    const paragraphs = this._buildParagraphs(texts, usedDepths, depthReached);
    subsection.paragraphs = paragraphs;
    subsection.text = paragraphs.join('\n\n');

    return subsection;
  }

  /**
   * Строит 1-3 параграфа из ответов пользователя.
   *
   * Правила:
   *   - L1 + L2 → 1-2 параграфа (общее описание + контекст)
   *   - L3 → 1 отдельный параграф (глубокий анализ)
   *   - Максимум 3 параграфа
   *
   * @param {string[]} texts — массив текстов [L3, L2, L1] (приоритет: L3 первый)
   * @param {string[]} usedDepths — [L3, L2, L1] какие глубины использованы
   * @param {string} depthReached — максимальная глубина
   * @returns {string[]} 1-3 параграфа
   * @private
   */
  _buildParagraphs(texts, usedDepths, depthReached) {
    if (texts.length === 0) return [''];

    // Если только L1
    if (texts.length === 1 && usedDepths[0] === 'L1') {
      return [this._cleanTextForParagraph(texts[0])];
    }

    // Если L1 + L2 (2 текста)
    if (texts.length === 2) {
      return [
        this._cleanTextForParagraph(texts[1]), // L1 → общее описание
        this._cleanTextForParagraph(texts[0])  // L2 → контекст / примеры
      ];
    }

    // Если L1 + L2 + L3 (3 текста)
    if (texts.length >= 3) {
      return [
        this._cleanTextForParagraph(texts[2]), // L1 → общее описание
        this._cleanTextForParagraph(texts[1]), // L2 → контекст
        this._cleanTextForParagraph(texts[0])  // L3 → глубокий анализ
      ];
    }

    // Fallback: один параграф
    return [this._cleanTextForParagraph(texts[0])];
  }

  /**
   * Очищает текст для параграфа: убирает разговорные частицы,
   * капитализирует, нормализует.
   *
   * @param {string} text
   * @returns {string}
   * @private
   */
  _cleanTextForParagraph(text) {
    if (!text) return '';

    let cleaned = text.trim();

    // Убираем разговорные частицы в начале
    const particles = [
      'ну ', 'типа ', 'как бы ', 'в общем,', 'в общем ',
      'короче,', 'короче ', 'значит,', 'значит ',
      'так вот,', 'так вот ', 'вообще,', 'вообще ',
      'слушай,', 'слушай ', 'понимаешь,', 'понимаешь ',
      'видишь,', 'видишь '
    ];
    for (const p of particles) {
      if (cleaned.toLowerCase().startsWith(p)) {
        cleaned = cleaned.slice(p.length);
        break;
      }
    }

    // Убираем заполнители в середине
    const fillers = [
      /\bкак бы\b/gi, /\bтипа\b/gi, /\bну вот\b/gi,
      /\bну типа\b/gi, /\bвроде как\b/gi
    ];
    for (const re of fillers) {
      cleaned = cleaned.replace(re, '');
    }

    // Нормализуем пробелы
    cleaned = cleaned.replace(/\s{2,}/g, ' ').trim();

    // Капитализируем первую букву
    if (cleaned.length > 0) {
      cleaned = cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
    }

    // Добавляем точку в конце
    if (cleaned.length > 0 && !/[.!?…]/.test(cleaned[cleaned.length - 1])) {
      cleaned += '.';
    }

    return cleaned;
  }

  /**
   * Форматирует полный текст блока (заголовок + подразделы).
   *
   * @param {object} blockTemplate
   * @param {Array} subsections
   * @returns {string}
   * @private
   */
  _formatBlockContent(blockTemplate, subsections) {
    const lines = [
      `## Блок ${blockTemplate.id}. ${blockTemplate.name}`,
      '',
      `*${blockTemplate.description}*`,
      ''
    ];

    for (const sub of subsections) {
      lines.push(`### ${sub.subsectionId}. ${sub.subsectionName}`);
      lines.push('');
      lines.push(sub.text);
      lines.push('');

      // Добавляем информацию о глубине
      if (sub.depthReached !== 'none' && sub.depthReached !== 'L1') {
        lines.push(`*Уровень проработки:* ${sub.depthLabel}`);
        lines.push('');
      }
    }

    // Убираем лишний перенос в конце
    while (lines.length > 0 && lines[lines.length - 1] === '') {
      lines.pop();
    }

    return lines.join('\n');
  }

  /**
   * Форматирует риски в текстовый раздел.
   *
   * @param {object} risks — консолидированные риски
   * @returns {string|null}
   * @private
   */
  _formatRiskText(risks) {
    if (!risks || risks.total === 0) {
      return '— *Риски не идентифицированы.*';
    }

    const lines = [
      '## Риски и митигации',
      '',
      '*Идентифицированные на протяжении диалога риски и меры по их снижению.*',
      ''
    ];

    const categoryNames = {
      'technical': 'Технические риски',
      'business': 'Бизнес-риски',
      'org': 'Организационные риски',
      'organizational': 'Организационные риски',
      'adoption': 'Риски внедрения',
      'uncategorized': 'Прочие риски'
    };

    for (const [cat, catRisks] of Object.entries(risks.byCategory)) {
      const label = categoryNames[cat] || cat;
      lines.push(`### ${label}`);
      lines.push('');

      catRisks.forEach((risk, i) => {
        lines.push(`**Риск ${i + 1}.** ${risk.text}`);

        const details = [];
        if (risk.probability !== null && risk.probability !== undefined) {
          details.push(`Вероятность: ${this._formatLevel(risk.probability)}`);
        }
        if (risk.impact !== null && risk.impact !== undefined) {
          details.push(`Влияние: ${this._formatLevel(risk.impact)}`);
        }
        if (risk.collectedAt) {
          details.push(`Область сбора: ${risk.collectedAt}`);
        }
        if (risk.mitigation) {
          details.push(`Митигация: ${risk.mitigation}`);
        }

        if (details.length > 0) {
          lines.push(`  _${details.join(' · ')}_`);
        }
        lines.push('');
      });
    }

    // Убираем последний перенос
    while (lines.length > 0 && lines[lines.length - 1] === '') {
      lines.pop();
    }

    return lines.join('\n');
  }

  /**
   * Форматирует числовой уровень в текстовый.
   *
   * @param {number} level — от 0 до 1
   * @returns {string}
   * @private
   */
  _formatLevel(level) {
    if (level >= 0.7) return 'Высокая';
    if (level >= 0.4) return 'Средняя';
    if (level >= 0.1) return 'Низкая';
    return 'Не определена';
  }

  /**
   * Собирает финальный документ draft.
   *
   * @param {object} session
   * @param {Array} blocks
   * @param {object} risks
   * @returns {object} полный draft
   * @private
   */
  _assembleDraftDocument(session, blocks, risks) {
    const documentParts = [];

    // 1. Титул
    documentParts.push('# Документ бизнес-требований');
    documentParts.push('');
    documentParts.push(`*Сформирован:* ${new Date().toLocaleDateString('ru-RU')}`);
    documentParts.push(`*Сессия:* ${session.sessionId}`);
    documentParts.push(`*Пользователь:* ${session.telegramUserId || '—'}`);
    if (session.username) {
      documentParts.push(`*Автор:* ${session.username}`);
    }
    documentParts.push(`*Статус:* draft_ready (финальный черновик)`);
    documentParts.push('');

    // 2. Метрики качества
    if (session.qualityGate) {
      documentParts.push(`*Проверка качества:* ✅ Пройдена (балл: ${session.qualityGate.overallScore || '—'}/10, итераций: ${session.qualityGate.iteration || 1})`);
      documentParts.push('');
    }

    documentParts.push('---');
    documentParts.push('');

    // 3. Блоки
    for (const block of blocks) {
      documentParts.push(block.content);
      documentParts.push('');
    }

    // 4. Риски
    documentParts.push('---');
    documentParts.push('');
    const riskText = this._formatRiskText(risks);
    documentParts.push(riskText);

    // Убираем лишние переносы
    while (documentParts.length > 0 && documentParts[documentParts.length - 1] === '') {
      documentParts.pop();
    }

    const fullText = documentParts.join('\n');

    // Считаем статистику
    let totalSubsections = 0;
    let completedSubsections = 0;

    for (const block of blocks) {
      totalSubsections += block.subsections.length;
      completedSubsections += block.subsections.filter(
        s => s.depthReached !== 'none'
      ).length;
    }

    return {
      title: 'Документ бизнес-требований',
      createdAt: new Date().toISOString(),
      sessionId: session.sessionId,
      telegramUserId: session.telegramUserId,
      username: session.username || null,

      // Структура (следует template.json — 7 блоков, immutable)
      totalBlocks: blocks.length,
      blocks,

      // Риски
      risks,

      // Статистика
      completedSubsections,
      totalSubsections,
      completionPercent: totalSubsections > 0
        ? Math.round((completedSubsections / totalSubsections) * 100)
        : 0,

      // Полный текст
      fullText,

      // Мета
      status: 'draft_building',
      iteration: session.qualityGate ? session.qualityGate.iteration : 1,
      qualityScore: session.qualityGate ? session.qualityGate.overallScore : null
    };
  }
}

module.exports = DraftGenerator;
