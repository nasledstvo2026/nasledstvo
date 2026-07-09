/**
 * Section Formatter — форматирование разделов БТ
 *
 * Story 3.1 — Делегирует lib/compiler.js
 *
 * Форматирует ответы пользователя в структурированный текст
 * для каждого из 7 блоков шаблона. Является тонкой обёрткой
 * над основным Compiler-движком из lib/compiler.js.
 */

const path = require('path');

class SectionFormatter {
  /**
   * @param {object} deps
   * @param {object} deps.compiler — экземпляр Compiler из lib/compiler.js
   * @param {object} deps.templateEngine — экземпляр TemplateEngine
   */
  constructor(deps = {}) {
    this.compiler = deps.compiler || null;
    this.templateEngine = deps.templateEngine || null;
  }

  /**
   * Форматирует один блок БТ.
   * Делегирует Compiler.formatBlock().
   *
   * @param {number} blockId — номер блока (1-7)
   * @param {object} answers — ответы пользователя на подразделы блока
   * @returns {string} отформатированный текст блока
   */
  formatBlock(blockId, answers) {
    if (!this.compiler) {
      throw new Error('SectionFormatter: Compiler не подключён');
    }
    const block = this.compiler.formatBlock(blockId, answers);
    return block ? block.content : `\n## Блок ${blockId}\n\n*Не найдено.*`;
  }

  /**
   * Форматирует один подраздел.
   * Делегирует Compiler.formatSubsection().
   *
   * @param {string} subId — '1.1', '2.3'
   * @param {object|null} answers — ответы { L1, L2, L3, depthReached }
   * @returns {string} отформатированный текст
   */
  formatSubsection(subId, answers) {
    if (!this.compiler) {
      throw new Error('SectionFormatter: Compiler не подключён');
    }
    return this.compiler.formatSubsection(subId, answers);
  }

  /**
   * Собирает все 7 блоков в полный документ.
   * Делегирует Compiler.buildDraftDocument().
   *
   * @param {object} allAnswers — ответы на все блоки
   * @param {Array} risks — собранные риски
   * @returns {string} полный текст БТ
   */
  compileDocument(allAnswers, risks) {
    if (!this.compiler) {
      throw new Error('SectionFormatter: Compiler не подключён');
    }

    // Строим минимальный псевдо-контекст для сборки документа
    const pseudoContext = {
      sessionId: 'manual',
      telegramUserId: 0,
      answers: allAnswers,
      risks: risks || []
    };

    const draft = this.compiler.buildDraftDocument(pseudoContext);
    return draft ? draft.fullText : '';
  }
}

module.exports = SectionFormatter;
