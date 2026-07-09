/**
 * Агент-составитель (compiler)
 *
 * Story 3.1 — Формирование текста БТ по шаблону (FR12, FR13)
 *
 * Формирует текст БТ по утверждённому шаблону (7 блоков)
 * на основе ответов пользователя, собранных агентом-опросчиком.
 *
 * Pipeline:
 *   1. Questioner завершает опрос → session.status = 'completed'
 *   2. Session manager триггерирует CompilerAgent.process(sessionContext)
 *   3. Compiler формирует session.draft (7 блоков, структурированный текст)
 *   4. Draft передаётся контролёру (ControllerAgent) для проверки
 *
 * Вход: Session Context (все ответы на 7 блоков, риски)
 * Выход: session.draft — структурированный черновик документа БТ
 *
 * Acceptance Criteria (Story 3.1):
 *   - Принимает session.answers
 *   - Формирует 7 блоков с заполненными подразделами
 *   - Чёткие формулировки, без художественных оборотов (FR13)
 *   - Output: session.draft в структурированном формате
 *   - Пустые/неприменимые подразделы помечаются
 */

const path = require('path');
const Compiler = require('../../lib/compiler');
const SectionFormatter = require('./section-formatter');
const { createLogger } = require('../../lib/logger');

class CompilerAgent {
  /**
   * @param {object} config
   * @param {object} config.templateEngine — экземпляр TemplateEngine
   * @param {object} [config.logger] — опциональный логгер
   */
  constructor(config = {}) {
    this.config = config;
    this.templateEngine = config.templateEngine || null;
    this.logger = config.logger || createLogger('compiler-agent');

    // Инициализируем движок компиляции
    this.compiler = new Compiler({
      templateEngine: this.templateEngine
    });

    // Инициализируем SectionFormatter (обёртка)
    this.formatter = new SectionFormatter({
      compiler: this.compiler,
      templateEngine: this.templateEngine
    });

    /** @type {object|null} */
    this._lastProcessedSession = null;
  }

  /**
   * Основной метод — обрабатывает Session Context и формирует черновик.
   *
   * @param {object} session — Session Context (или объект сессии)
   * @returns {Promise<object>} обновлённый Session Context с полем .draft
   * @throws {Error} если данные невалидны
   */
  async process(session) {
    // Принимаем как SessionContext (из survey-engine), так и plain object
    const sessionContext = this._normalizeSession(session);

    if (!sessionContext || !sessionContext.sessionId) {
      throw new Error('CompilerAgent: невалидный Session Context');
    }

    this.logger.info('CompilerAgent.process started', {
      sessionId: sessionContext.sessionId,
      answersCount: Object.keys(sessionContext.answers || {}).length,
      risksCount: (sessionContext.risks || []).length
    });

    // Проверяем, что есть ответы
    if (!sessionContext.answers || Object.keys(sessionContext.answers).length === 0) {
      throw new Error('CompilerAgent: нет ответов для компиляции');
    }

    // Формируем черновик
    const draft = this.compiler.compileDraft(sessionContext);

    // Устанавливаем черновик в Session Context
    sessionContext.draft = draft;

    // Обновляем статус — документ готов к проверке контролёром
    sessionContext.documentReady = false;

    // Запоминаем последний обработанный контекст
    this._lastProcessedSession = {
      sessionId: sessionContext.sessionId,
      draftCreated: true,
      draftBlocks: draft.totalBlocks,
      completedSubsections: draft.completedSubsections,
      totalSubsections: draft.totalSubsections,
      timestamp: new Date().toISOString()
    };

    this.logger.info('CompilerAgent.process completed', {
      sessionId: sessionContext.sessionId,
      blocksFormed: draft.totalBlocks,
      completedSubsections: draft.completedSubsections,
      totalSubsections: draft.totalSubsections,
      fullTextLength: draft.fullText.length,
      risksCount: draft.risks.total
    });

    // Возвращаем обновлённый Session Context
    return sessionContext;
  }

  /**
   * Проверяет, готовы ли данные для компиляции.
   *
   * @param {object} session — Session Context
   * @returns {{ ready: boolean, reason: string }}
   */
  canProcess(session) {
    const ctx = this._normalizeSession(session);

    if (!ctx) {
      return { ready: false, reason: 'Нет Session Context' };
    }

    if (!ctx.answers || Object.keys(ctx.answers).length === 0) {
      return { ready: false, reason: 'Нет ответов (answers пуст)' };
    }

    if (!this.templateEngine) {
      return { ready: false, reason: 'TemplateEngine не подключён' };
    }

    return { ready: true, reason: 'Готов к компиляции' };
  }

  /**
   * Возвращает статистику последней компиляции.
   *
   * @returns {object|null}
   */
  getLastProcessStats() {
    return this._lastProcessedSession;
  }

  /**
   * Возвращает текущий черновик (если есть).
   *
   * @returns {object|null}
   */
  getCurrentDraft() {
    return this.compiler.getCurrentDraft();
  }

  /**
   * Нормализует входной объект сессии.
   * Принимает как SessionContext, так и plain-объект.
   *
   * @param {object} session
   * @returns {object}
   * @private
   */
  _normalizeSession(session) {
    if (!session) return null;

    // Если это SessionContext — у него есть toJSON()
    if (typeof session.toJSON === 'function') {
      return session.toJSON();
    }

    // Если это session.answers есть — возвращаем как есть
    if (session.answers) {
      return session;
    }

    // Если у сессии есть answers на каком-то уровне
    if (session.draft !== undefined && session.answers) {
      return session;
    }

    return session;
  }
}

module.exports = CompilerAgent;
