/**
 * Агент-опросчик (questioner)
 *
 * Задаёт вопросы по 7 блокам шаблона БТ с динамической глубиной (L1→L2→L3).
 * Оценивает полноту ответов, при поверхностном ответе задаёт уточняющие вопросы.
 * Собирает риски на протяжении всего диалога.
 *
 * Вход: Session Context (текущий блок, подраздел, предыдущие ответы)
 * Выход: обновлённый Session Context (ответы, глубина, риски)
 */

const depthControl = require('./depth-control.js');

class QuestionerAgent {
  constructor(config) {
    this.config = config;
    this.depthControl = depthControl;
  }

  async process(session) {
    // TODO: реализовать в Story 2.1-2.4
    // 1. Определить текущий блок и подраздел из session.template
    // 2. Выбрать вопрос соответствующего уровня глубины (L1/L2/L3)
    // 3. Отправить вопрос пользователю через Telegram
    // 4. Получить ответ и оценить глубину
    // 5. При поверхностном ответе — перейти на следующий уровень
    // 6. При глубоком ответе — зафиксировать и перейти дальше
    // 7. Собрать риски в session.risks
    throw new Error('Not implemented — Story 2.x');
  }
}

module.exports = QuestionerAgent;
