/**
 * Retry — exponential backoff для повторных попыток
 *
 * Реализует retry-логику с экспоненциальной задержкой
 * для операций с внешними API (DeepSeek, GitHub, файловая система).
 */

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

/**
 * Выполняет функцию с повторными попытками
 * @param {Function} fn - Асинхронная функция для выполнения
 * @param {object} options - Настройки
 * @param {number} options.maxAttempts - Максимум попыток (по умолч. 3)
 * @param {number} options.initialDelayMs - Начальная задержка (по умолч. 1000)
 * @param {number} options.maxDelayMs - Максимальная задержка (по умолч. 10000)
 * @returns {Promise<any>} Результат выполнения fn
 * @throws {Error} Если все попытки исчерпаны
 */
async function withRetry(fn, options = {}) {
  const maxAttempts = options.maxAttempts || 3;
  const initialDelayMs = options.initialDelayMs || 1000;
  const maxDelayMs = options.maxDelayMs || 10000;

  let lastError;

  for (let attempt = 1; attempt <= maxAttempts; attempt++) {
    try {
      return await fn();
    } catch (error) {
      lastError = error;
      if (attempt < maxAttempts) {
        const delay = Math.min(initialDelayMs * Math.pow(2, attempt - 1), maxDelayMs);
        console.warn(`Retry attempt ${attempt}/${maxAttempts} failed. Retrying in ${delay}ms...`);
        await sleep(delay);
      }
    }
  }

  throw new Error(`All ${maxAttempts} attempts failed: ${lastError.message}`);
}

module.exports = { withRetry, sleep };
