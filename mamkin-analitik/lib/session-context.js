/**
 * Session Context — единый контекст для обмена данными между агентами
 *
 * Story 1.7 — Изоляция сессий и безопасность хранения
 *
 * Session Context — это объект, который передаётся между агентами пайплайна
 * (questioner → compiler → controller → generator) без дублирования на диск.
 *
 * Содержит минимальный набор данных, необходимых агентам:
 *   - sessionId — идентификатор сессии
 *   - telegramUserId — владелец сессии
 *   - answers — ответы пользователя по подразделам
 *   - currentBlock — текущий блок опроса
 *   - currentSubsection — текущий подраздел
 *   - risks — собранные риски
 *   - depth — уровень глубины
 *   - progress — прогресс опроса
 *   - status — статус сессии
 *   - draft — черновик документа (заполняется compiler-ом)
 *   - qualityGate — результаты проверки контролёром
 *
 * Контекст создаётся из сессии и обогащается по мере прохождения пайплайна.
 * После завершения — сохраняется обратно в сессию через Session Manager.
 */

class SessionContext {
  /**
   * @param {object} session — объект сессии из SessionManager
   */
  constructor(session) {
    if (!session || !session.sessionId) {
      throw new Error('SessionContext: требуется валидный объект сессии с sessionId');
    }

    /** @type {string} */
    this.sessionId = session.sessionId;

    /** @type {number} */
    this.telegramUserId = session.telegramUserId;

    /** @type {Object<string, Object>} answers[subsectionId][depth] = ответ */
    this.answers = session.answers || {};

    /** @type {number} */
    this.currentBlock = (session.template && session.template.block) || 1;

    /** @type {string} */
    this.currentSubsection = (session.template && session.template.subsection) || '1.1';

    /** @type {Array<{text: string, category: string, collectedAt: string, probability: number|null, impact: number|null, mitigation: string|null, timestamp: string|null}>} */
    this.risks = session.risks || [];

    /** @type {'L1'|'L2'|'L3'} */
    this.depth = (session.template && session.template.depth) || 'L1';

    /** @type {number} Процент завершения опроса (0-100) */
    this.progress = 0;

    /** @type {'in_progress'|'recovered'|'completed'} */
    this.status = session.status || 'in_progress';

    /**
     * Черновик сформированного документа БТ.
     * Заполняется агентом-составителем (compiler).
     * @type {object|null}
     */
    this.draft = session.draft || null;

    /**
     * Результаты проверки контролёром.
     * @type {{ approved: boolean, issues: Array<{block: number, subsection: string, issue: string, severity: string, suggestions: string[]}>, iteration: number }}
     */
    this.qualityGate = session.qualityGate || {
      approved: false,
      issues: [],
      iteration: 0
    };

    /**
     * Документ готов к генерации.
     * @type {boolean}
     */
    this.documentReady = session.documentReady === true;

    /**
     * URL опубликованного документа (заполняется генератором).
     * @type {string|null}
     */
    this.documentUrl = session.documentUrl || null;

    /**
     * Мета-информация о контексте.
     * @type {{ createdAt: string, updatedAt: string, completedAt: string|null, username: string|null }}
     */
    this.meta = {
      createdAt: session.createdAt || new Date().toISOString(),
      updatedAt: session.updatedAt || new Date().toISOString(),
      completedAt: session.completedAt || null,
      username: session.username || null
    };
  }

  // ==================== Фабричные методы ====================

  /**
   * Создаёт SessionContext из объекта сессии.
   * @param {object} session
   * @returns {SessionContext}
   */
  static fromSession(session) {
    return new SessionContext(session);
  }

  /**
   * Создаёт SessionContext из JSON-строки (для десериализации).
   * @param {string} json
   * @returns {SessionContext}
   */
  static fromJSON(json) {
    const data = JSON.parse(json);
    return new SessionContext(data);
  }

  // ==================== Сериализация ====================

  /**
   * Сериализует контекст в JSON.
   * @returns {object}
   */
  toJSON() {
    return {
      sessionId: this.sessionId,
      telegramUserId: this.telegramUserId,
      answers: this.answers,
      currentBlock: this.currentBlock,
      currentSubsection: this.currentSubsection,
      risks: this.risks,
      riskContext: this.riskContext,
      depth: this.depth,
      progress: this.progress,
      status: this.status,
      draft: this.draft,
      qualityGate: this.qualityGate,
      documentReady: this.documentReady,
      documentUrl: this.documentUrl,
      meta: this.meta
    };
  }

  /**
   * Возвращает контекст рисков: grouped by category + count.
   * @returns {{ risks: Array, byCategory: object, count: number }}
   */
  get riskContext() {
    const byCategory = {};
    for (const risk of this.risks) {
      const cat = risk.category || 'uncategorized';
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(risk);
    }
    return {
      risks: this.risks,
      byCategory,
      count: this.risks.length
    };
  }

  /**
   * Возвращает JSON-строку для передачи между агентами.
   * @returns {string}
   */
  serialize() {
    return JSON.stringify(this.toJSON());
  }

  // ==================== Обновление контекста ====================

  /**
   * Обновляет контекст из частичного объекта.
   * Используется для безопасного обогащения контекста агентами.
   *
   * @param {object} updates — частичные обновления
   * @returns {SessionContext} this (чейнинг)
   */
  update(updates) {
    if (!updates) return this;

    const allowedKeys = [
      'answers', 'currentBlock', 'currentSubsection', 'risks', 'depth',
      'progress', 'status', 'draft', 'qualityGate', 'documentReady',
      'documentUrl'
    ];

    for (const key of allowedKeys) {
      if (updates[key] !== undefined) {
        // Для вложенных объектов делаем глубокий мерж
        if (typeof updates[key] === 'object' && !Array.isArray(updates[key]) &&
            updates[key] !== null && typeof this[key] === 'object' &&
            this[key] !== null && !Array.isArray(this[key])) {
          this[key] = { ...this[key], ...updates[key] };
        } else {
          this[key] = updates[key];
        }
      }
    }

    if (updates.meta) {
      this.meta = { ...this.meta, ...updates.meta };
      this.meta.updatedAt = new Date().toISOString();
    } else {
      this.meta.updatedAt = new Date().toISOString();
    }

    return this;
  }

  /**
   * Добавляет риск в контекст.
   * @param {string} text — описание риска
   * @param {string} category — категория (technical/org/business/adoption)
   * @param {string} collectedAt — блок, где собран
   * @returns {SessionContext}
   */
  addRisk(text, category = 'business', collectedAt = null) {
    this.risks.push({
      text,
      category,
      collectedAt: collectedAt || `block_${this.currentBlock}`,
      probability: null,
      impact: null,
      mitigation: null,
      timestamp: new Date().toISOString()
    });
    this.meta.updatedAt = new Date().toISOString();
    return this;
  }

  /**
   * Устанавливает черновик документа.
   * Вызывается агентом-составителем.
   * @param {object} draft — черновик БТ
   * @returns {SessionContext}
   */
  setDraft(draft) {
    this.draft = draft;
    this.meta.updatedAt = new Date().toISOString();
    return this;
  }

  /**
   * Обновляет прогресс опроса.
   * @param {number} percent — 0-100
   * @returns {SessionContext}
   */
  setProgress(percent) {
    this.progress = Math.max(0, Math.min(100, percent));
    return this;
  }

  /**
   * Переводит сессию в статус "documentReady".
   * Вызывается после прохождения всех проверок контролёром.
   * @returns {SessionContext}
   */
  markDocumentReady() {
    this.documentReady = true;
    this.status = 'completed';
    this.meta.completedAt = new Date().toISOString();
    this.meta.updatedAt = new Date().toISOString();
    return this;
  }

  /**
   * Устанавливает URL опубликованного документа.
   * @param {string} url
   * @returns {SessionContext}
   */
  setDocumentUrl(url) {
    this.documentUrl = url;
    this.meta.updatedAt = new Date().toISOString();
    return this;
  }

  // ==================== Запросы данных ====================

  /**
   * Возвращает ответ на указанный подраздел на максимальной достигнутой глубине.
   * @param {string} subsectionKey — '1.1', '2.3' и т.д.
   * @returns {string|null}
   */
  getAnswer(subsectionKey) {
    const answer = this.answers[subsectionKey];
    if (!answer) return null;

    // Приоритет: L3 → L2 → L1
    for (const depth of ['L3', 'L2', 'L1']) {
      if (answer[depth]) return answer[depth];
    }

    return null;
  }

  /**
   * Возвращает достигнутую глубину для подраздела.
   * @param {string} subsectionKey
   * @returns {string|null}
   */
  getDepthReached(subsectionKey) {
    const answer = this.answers[subsectionKey];
    return answer ? (answer.depthReached || null) : null;
  }

  /**
   * Возвращает все ответы, сгруппированные по блокам.
   * @returns {object} { blockId: { subsectionKey: answer } }
   */
  getAnswersByBlock() {
    const byBlock = {};

    for (const [key, answer] of Object.entries(this.answers)) {
      const blockId = key.split('.')[0];

      if (!byBlock[blockId]) {
        byBlock[blockId] = {};
      }

      byBlock[blockId][key] = answer;
    }

    return byBlock;
  }

  /**
   * Возвращает общее количество отвеченных подразделов.
   * @returns {number}
   */
  getAnsweredCount() {
    return Object.keys(this.answers).length;
  }

  /**
   * Проверяет, есть ли непройденные checkpoints (quality issues).
   * @returns {boolean}
   */
  hasQualityIssues() {
    return this.qualityGate && this.qualityGate.issues &&
      this.qualityGate.issues.length > 0;
  }

  /**
   * Возвращает краткую сводку контекста для логирования.
   * @returns {object}
   */
  getSummary() {
    return {
      sessionId: this.sessionId,
      user: this.telegramUserId,
      status: this.status,
      progress: this.progress,
      currentBlock: this.currentBlock,
      currentSubsection: this.currentSubsection,
      depth: this.depth,
      answersCount: this.getAnsweredCount(),
      risksCount: this.risks.length,
      hasDraft: !!this.draft,
      documentReady: this.documentReady,
      qualityApproved: this.qualityGate.approved,
      qualityIssues: this.qualityGate.issues.length
    };
  }

  /**
   * Возвращает текстовую сводку для отображения пользователю.
   * @returns {string}
   */
  getProgressText() {
    const blocks = ['1', '2', '3', '4', '5', '6', '7'];
    const answered = new Set(
      Object.keys(this.answers).map(k => k.split('.')[0])
    );

    const blockNames = {
      '1': 'Предпосылки и цели',
      '2': 'Заинтересованные стороны',
      '3': 'Текущее состояние',
      '4': 'Требования',
      '5': 'Критерии приёмки',
      '6': 'Технические заметки',
      '7': 'Риски'
    };

    const lines = [];
    for (const b of blocks) {
      const name = blockNames[b] || `Блок ${b}`;
      const done = answered.has(b);
      lines.push(`${done ? '✅' : '⬜'} Блок ${b}: ${name}`);
    }

    return lines.join('\n');
  }

  /**
   * Проверяет, следует ли передать управление следующему агенту.
   * @returns {{nextAgent: string|null, reason: string}}
   */
  getNextAgent() {
    // Агент-опросчик (questioner) — пока не завершён опрос
    if (this.status === 'in_progress' || this.status === 'recovered') {
      return { nextAgent: 'questioner', reason: 'опрос не завершён' };
    }

    // Агент-составитель (compiler) — нет черновика
    if (this.status === 'completed' && !this.draft) {
      return { nextAgent: 'compiler', reason: 'черновик не сформирован' };
    }

    // Агент-контролёр (controller) — черновик есть, но не проверен
    if (this.draft && !this.qualityGate.approved) {
      if (this.qualityGate.iteration < 3) {
        return { nextAgent: 'controller', reason: 'проверка качества' };
      }
      // После 3 итераций форсированное принятие
      return { nextAgent: 'generator', reason: 'форсированное принятие (max итераций)' };
    }

    // Агент-генератор (generator) — документ готов к генерации
    if (this.documentReady) {
      return { nextAgent: 'generator', reason: 'документ готов к генерации' };
    }

    return { nextAgent: null, reason: 'неизвестное состояние' };
  }
}

module.exports = SessionContext;
