/**
 * Depth Control — управление глубиной опроса (L1/L2/L3)
 *
 * Определяет, на какой уровень глубины перейти в зависимости от полноты ответа.
 *
 * Критерии глубины:
 * - L1 (поверхностный): < 2 фактов или < 3 предложений, общие фразы
 * - L2 (средний): 2+ факта или 3+ предложения, есть конкретика
 * - L3 (глубокий): примеры, цифры, причинно-следственные связи
 * - MAX: даже после L3 недостаточно — фиксировать как есть
 */

const DEPTH_LEVELS = {
  L1: 'L1',     // Открывающий вопрос
  L2: 'L2',     // Углубляющий вопрос
  L3: 'L3',     // Корневой вопрос
  MAX: 'MAX'    // Предельная глубина
};

/**
 * Оценивает глубину ответа пользователя
 * @param {string} answer - Текст ответа пользователя
 * @returns {object} { depth: 'L1'|'L2'|'L3', score: number }
 */
function assessDepth(answer) {
  // TODO: реализовать в Story 2.2-2.4
  // - Анализ длины ответа (кол-во предложений, символов)
  // - Наличие конкретных фактов, цифр, примеров
  // - Наличие причинно-следственных связей
  // - Отсутствие общих фраз ("всё плохо", "надо автоматизировать")
  return { depth: DEPTH_LEVELS.L1, score: 0 };
}

/**
 * Определяет следующий уровень глубины
 * @param {object} assessment - Результат assessDepth()
 * @param {string} currentLevel - Текущий уровень
 * @returns {string} Следующий уровень или null, если достаточно
 */
function nextLevel(assessment, currentLevel) {
  if (assessment.depth === DEPTH_LEVELS.L3) return null;
  if (currentLevel === DEPTH_LEVELS.L1) return DEPTH_LEVELS.L2;
  if (currentLevel === DEPTH_LEVELS.L2) return DEPTH_LEVELS.L3;
  if (currentLevel === DEPTH_LEVELS.L3) return DEPTH_LEVELS.MAX;
  return null;
}

module.exports = { assessDepth, nextLevel, DEPTH_LEVELS };
