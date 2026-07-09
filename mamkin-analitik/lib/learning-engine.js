/**
 * Learning Engine — анализ паттернов и контекстная персонализация опроса
 *
 * Stories:
 *   5.2 — Pattern analysis (FR23): avgDepthPerBlock, frequentL3Topics, commonGaps
 *   5.3 — Context reuse from previous BRDs (FR24, FR25): getContextForUser,
 *         getPersonalizedGreeting, getGapAwareQuestion
 *
 * Анализирует history.json и предоставляет:
 *   5.2: среднюю глубину по блокам, L3-темы, слепые зоны
 *   5.3: контекст пользователя, персонализированные приветствия,
 *        вопросы с учётом предыдущих пробелов
 *
 * API (5.2):
 *   analyzeHistory(userId)              — полный анализ паттернов
 *   getFrequentL3Topics(userId)          → [{block, subsection, count}]
 *   getCommonGaps(userId)                → [{block, subsection, frequency}]
 *   getAvgDepthPerBlock(userId)          → [{blockId, avgDepth}]
 *
 * API (5.3):
 *   getContextForUser(userId)           — контекст пользователя (async)
 *   getPersonalizedGreeting(userId)     — персонализированное приветствие (async)
 *   getGapAwareQuestion(subKey, ctx, q) — вопрос с учётом пробелов
 */

const path = require('path');
const fs = require('fs');
const { createLogger } = require('./logger');

const HISTORY_FILE = path.resolve(__dirname, '..', 'history.json');

class LearningEngine {
  /**
   * @param {object} [options]
   * @param {string} [options.historyPath] — путь к history.json (для тестов)
   * @param {object} [options.template]    — загруженный template (для разрешения имён блоков)
   */
  constructor(options = {}) {
    this.historyPath = options.historyPath || HISTORY_FILE;
    this.template = options.template || null;
    this.logger = createLogger('learning-engine');
  }

  // ==================== Story 5.2 Public API ====================

  /**
   * Полный анализ паттернов пользователя на основе истории.
   *
   * @param {number|string} userId — Telegram user ID
   * @returns {object} паттерны пользователя
   */
  analyzeHistory(userId) {
    const userSessions = this._getUserSessions(userId);

    if (userSessions.length === 0) {
      return this._emptyAnalysis(userId);
    }

    return {
      userId,
      totalSessions: userSessions.length,
      avgDepthPerBlock: this.getAvgDepthPerBlock(userId),
      frequentL3Topics: this.getFrequentL3Topics(userId),
      commonGaps: this.getCommonGaps(userId),
      lastSessionDate: userSessions[userSessions.length - 1].completedAt || null,
      overallAvgDepth: this._calculateOverallAvgDepth(userSessions)
    };
  }

  /**
   * Возвращает темы (подразделы), по которым чаще всего требовались L3-уточнения.
   *
   * @param {number|string} userId — Telegram user ID
   * @returns {Array<{block: number, subsection: string, count: number}>}
   */
  getFrequentL3Topics(userId) {
    const userSessions = this._getUserSessions(userId);
    return this._computeFrequentL3Topics(userSessions);
  }

  /**
   * Возвращает типичные «слепые зоны» — подразделы, которые пользователь
   * часто оставляет на глубине L1 (поверхностно).
   *
   * @param {number|string} userId — Telegram user ID
   * @returns {Array<{block: number, subsection: string, frequency: number}>}
   */
  getCommonGaps(userId) {
    const userSessions = this._getUserSessions(userId);
    return this._computeCommonGaps(userSessions);
  }

  /**
   * Возвращает среднюю глубину проработки по каждому блоку.
   *
   * @param {number|string} userId — Telegram user ID
   * @returns {Array<{blockId: number, avgDepth: number}>}
   */
  getAvgDepthPerBlock(userId) {
    const userSessions = this._getUserSessions(userId);
    return this._computeAvgDepthPerBlock(userSessions);
  }

  // ==================== Story 5.3 Public API (async) ====================

  /**
   * Возвращает контекст пользователя на основе его предыдущих сессий.
   *
   * Анализирует:
   *   — Список проектов (по ключевым словам из сессий)
   *   — Подразделы, где пользователь часто останавливался на L1 (пробелы/gaps)
   *   — Среднюю глубину проработки по каждому блоку
   *   — Общее количество сессий и последнюю активность
   *
   * @param {number|string} userId — Telegram user ID
   * @returns {Promise<object>} контекст пользователя
   *   @property {boolean} hasHistory — есть ли завершённые сессии
   *   @property {number} sessionCount — количество сессий
   *   @property {object|null} lastSession — последняя сессия
   *   @property {string[]} pastProjectThemes — темы прошлых проектов
   *   @property {string[]} frequentGaps — подразделы с частыми L1-остановками
   *   @property {object} avgDepthPerBlock — средняя глубина по блокам
   *   @property {object} depthDistributionByBlock — распределение глубины по блокам
   *   @property {string[]} commonL3Topics — темы, где пользователь углублялся до L3
   *   @property {object|null} lastSessionSummary — краткая сводка последней сессии
   */
  async getContextForUser(userId) {
    if (!userId) {
      this.logger.debug('userId не указан — контекст недоступен');
      return this._emptyContext();
    }

    try {
      const userSessions = this._getUserSessions(userId);

      if (userSessions.length === 0) {
        return this._emptyContext();
      }

      // Сортируем по completedAt (сначала новые)
      userSessions.sort(
        (a, b) => new Date(b.completedAt || 0) - new Date(a.completedAt || 0)
      );

      // Последняя сессия
      const lastSession = userSessions[0];

      // Анализируем прошлые темы проектов (из ключевых слов)
      const pastProjectThemes = this._extractProjectThemes(userSessions);

      // Пробелы — подразделы, где пользователь часто останавливался на L1
      const frequentGaps = this._findFrequentGaps(userSessions);

      // Средняя глубина по блокам
      const avgDepthPerBlock = {};
      const depthData = this._computeAvgDepthPerBlock(userSessions);
      for (const entry of depthData) {
        avgDepthPerBlock[String(entry.blockId)] = entry.avgDepth;
      }

      // Распределение глубины по блокам
      const depthDistributionByBlock = this._calcDepthDistributionByBlock(userSessions);

      // Темы, где пользователь углублялся до L3
      const commonL3Topics = this._findCommonL3Topics(userSessions);

      // Сводка последней сессии
      const lastSessionSummary = this._buildSessionSummary(lastSession);

      this.logger.info('User context loaded', {
        userId,
        sessionCount: userSessions.length,
        gapCount: frequentGaps.length,
        themeCount: pastProjectThemes.length
      });

      return {
        hasHistory: true,
        sessionCount: userSessions.length,
        lastSession,
        pastProjectThemes,
        frequentGaps,
        avgDepthPerBlock,
        depthDistributionByBlock,
        commonL3Topics,
        lastSessionSummary,
        patterns: {}
      };
    } catch (err) {
      this.logger.error('Failed to load user context', {
        userId,
        error: err.message
      });
      return this._emptyContext();
    }
  }

  /**
   * Возвращает персонализированное приветствие для возвращающегося пользователя.
   *
   * Формат:
   *   С историей: "🔄 С возвращением! В прошлый раз вы работали над [тема проекта]"
   *   Без истории: null (используется стандартное приветствие)
   *
   * @param {number|string} userId — Telegram user ID
   * @returns {Promise<string|null>} приветствие или null (если нет истории)
   */
  async getPersonalizedGreeting(userId) {
    const context = await this.getContextForUser(userId);

    if (!context.hasHistory) {
      return null;
    }

    // Определяем тему последнего проекта
    let projectTheme = 'проектом';

    if (context.pastProjectThemes.length > 0) {
      // Берём первую (самую частотную) тему
      projectTheme = context.pastProjectThemes[0];
    } else if (context.lastSessionSummary) {
      // Пробуем извлечь тему из ключевых слов последней сессии
      const keywords = context.lastSessionSummary.topKeywords || [];
      if (keywords.length > 0) {
        projectTheme = keywords.slice(0, 3).join(', ');
      }
    }

    // Строим приветствие
    const greeting = `🔄 *С возвращением!* В прошлый раз вы работали над *${projectTheme}*.`;

    // Добавляем информацию о количестве сессий
    let detailLine = '';
    if (context.sessionCount === 1) {
      detailLine = 'У вас уже есть одна завершённая сессия — я учту её опыт в новом опросе.';
    } else if (context.sessionCount > 1) {
      detailLine = `У вас уже ${context.sessionCount} завершённых сессий — я учту накопленный опыт в новом опросе.`;
    }

    // Добавляем намёк на пробелы, если есть
    let gapHint = '';
    if (context.frequentGaps.length > 0) {
      const gapCount = context.frequentGaps.length;
      if (gapCount <= 3) {
        gapHint = `\n\n🔍 В прошлый раз мы подробно разобрали не все разделы — я задам более точные вопросы по ${gapCount} темам, чтобы ничего не упустить.`;
      } else {
        gapHint = `\n\n🔍 Вижу, в прошлый раз мы могли углубиться не во все разделы. Я подготовил уточняющие вопросы, чтобы проработать детали.`;
      }
    }

    const fullGreeting = [greeting, detailLine, gapHint].filter(Boolean).join('\n\n');

    return fullGreeting;
  }

  /**
   * Возвращает персонализированный вопрос для подраздела, учитывая
   * предыдущие пробелы пользователя.
   *
   * Если подраздел был проблемным (часто L1), возвращает более конкретную
   * формулировку с дополнительным контекстом.
   *
   * @param {string} subsectionKey — ID подраздела (например, '1.1')
   * @param {object} userContext — контекст пользователя из getContextForUser()
   * @param {string} originalQuestion — исходный вопрос из шаблона
   * @returns {string} персонализированный вопрос
   */
  getGapAwareQuestion(subsectionKey, userContext, originalQuestion) {
    if (!userContext || !userContext.hasHistory) {
      return originalQuestion;
    }

    // Проверяем, был ли этот подраздел проблемным
    const isGap = userContext.frequentGaps && userContext.frequentGaps.includes(subsectionKey);

    if (!isGap) {
      // Подраздел без пробелов — можно добавить лёгкую персонализацию
      const depthInfo = this._getSubsectionDepthInfo(subsectionKey, userContext);
      if (depthInfo && depthInfo.avgDepth >= 2.5) {
        // Пользователь в прошлый раз глубоко проработал этот раздел
        return `В прошлый раз вы уже хорошо проработали этот раздел. Расскажите, что изменилось или добавилось с тех пор?\n\n${originalQuestion}`;
      }

      return originalQuestion;
    }

    // Пробел — формулируем более конкретный вопрос
    const gapHint = this._buildGapHint(subsectionKey, userContext);
    const targetedQuestion = this._buildTargetedQuestion(subsectionKey, originalQuestion);

    if (gapHint) {
      return `${gapHint}\n\n${targetedQuestion}`;
    }

    return targetedQuestion;
  }

  // ==================== Story 5.3 Private Methods ====================

  /**
   * Извлекает темы проектов из сессий пользователя.
   * Анализирует ключевые слова из draft и выбирает самые частотные.
   *
   * @param {object[]} sessions — массив сессий пользователя
   * @returns {string[]} — темы проектов (от наиболее частотных)
   * @private
   */
  _extractProjectThemes(sessions) {
    const keywordFrequency = {};

    for (const session of sessions) {
      const keywords = session.keywords || [];
      for (const kw of keywords) {
        keywordFrequency[kw] = (keywordFrequency[kw] || 0) + 1;
      }
    }

    // Сортируем по частоте, возвращаем топ-5
    return Object.entries(keywordFrequency)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5)
      .map(([word]) => word);
  }

  /**
   * Находит подразделы, где пользователь часто останавливался на L1.
   *
   * @param {object[]} sessions — массив сессий пользователя
   * @returns {string[]} — ID подразделов (до 10)
   * @private
   */
  _findFrequentGaps(sessions) {
    const gapFrequency = {};

    for (const session of sessions) {
      const answers = session.answers || {};
      for (const [subKey, answer] of Object.entries(answers)) {
        if (answer.depthReached === 'L1') {
          gapFrequency[subKey] = (gapFrequency[subKey] || 0) + 1;
        }
      }
    }

    // Сортируем по убыванию частоты
    return Object.entries(gapFrequency)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([subKey]) => subKey);
  }

  /**
   * Вычисляет распределение глубины по блокам.
   *
   * @param {object[]} sessions — массив сессий пользователя
   * @returns {object} — { blockId: { L1: N, L2: N, L3: N, total: N } }
   * @private
   */
  _calcDepthDistributionByBlock(sessions) {
    const result = {};

    for (const session of sessions) {
      const answers = session.answers || {};
      for (const [subKey, answer] of Object.entries(answers)) {
        const blockId = subKey.split('.')[0];
        if (!result[blockId]) {
          result[blockId] = { L1: 0, L2: 0, L3: 0, total: 0 };
        }
        if (result[blockId][answer.depthReached] !== undefined) {
          result[blockId][answer.depthReached]++;
          result[blockId].total++;
        }
      }
    }

    return result;
  }

  /**
   * Находит темы (ключевые слова), где пользователь углублялся до L3.
   *
   * @param {object[]} sessions — массив сессий пользователя
   * @returns {string[]} — ключевые слова из L3-ответов
   * @private
   */
  _findCommonL3Topics(sessions) {
    const l3Words = {};

    for (const session of sessions) {
      const answers = session.answers || {};
      for (const [subKey, answer] of Object.entries(answers)) {
        if (answer.depthReached === 'L3' && answer.L3) {
          const words = (answer.L3 || '')
            .toLowerCase()
            .replace(/[^а-яёa-z0-9\s-]/gi, ' ')
            .split(/\s+/)
            .filter(w => w.length > 4);

          for (const word of words) {
            l3Words[word] = (l3Words[word] || 0) + 1;
          }
        }
      }
    }

    return Object.entries(l3Words)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 10)
      .map(([word]) => word);
  }

  /**
   * Строит краткую сводку последней сессии пользователя.
   *
   * @param {object} session — объект сессии
   * @returns {object|null} — сводка
   * @private
   */
  _buildSessionSummary(session) {
    if (!session) return null;

    const answers = session.answers || {};
    const answeredCount = Object.keys(answers).length;
    const keywords = session.keywords || [];

    const depthCounts = { L1: 0, L2: 0, L3: 0 };
    for (const answer of Object.values(answers)) {
      if (depthCounts[answer.depthReached] !== undefined) {
        depthCounts[answer.depthReached]++;
      }
    }

    return {
      completedAt: session.completedAt,
      answeredSubsections: answeredCount,
      depthBreakdown: depthCounts,
      avgDepth: session.avgDepth,
      risksCount: session.risksCount || 0,
      topKeywords: keywords.slice(0, 5),
      draftLength: session.draftLength || 0
    };
  }

  /**
   * Получает информацию о глубине для конкретного подраздела.
   *
   * @param {string} subsectionKey
   * @param {object} userContext
   * @returns {object|null} — { avgDepth: number, depthCount: number } или null
   * @private
   */
  _getSubsectionDepthInfo(subsectionKey, userContext) {
    const blockId = subsectionKey.split('.')[0];
    const blockDepth = userContext.depthDistributionByBlock;
    if (!blockDepth || !blockDepth[blockId]) return null;

    const stats = blockDepth[blockId];
    if (!stats || stats.total === 0) return null;

    const avgDepth = (
      stats.L1 * 1 + stats.L2 * 2 + stats.L3 * 3
    ) / stats.total;

    return { avgDepth, depthCount: stats.total };
  }

  /**
   * Строит подсказку о пробеле для конкретного подраздела.
   *
   * @param {string} subsectionKey
   * @param {object} userContext
   * @returns {string|null}
   * @private
   */
  _buildGapHint(subsectionKey, userContext) {
    const lastSession = userContext.lastSession;
    if (!lastSession) return null;

    const answers = lastSession.answers || {};
    const lastAnswer = answers[subsectionKey];

    if (!lastAnswer) return null;

    const previousText = lastAnswer.L1 || null;

    if (!previousText) {
      return '💡 В прошлый раз мы не успели детально проработать этот раздел. Давайте уделим ему особое внимание сейчас.';
    }

    const snippet = previousText.length > 100
      ? previousText.slice(0, 97) + '…'
      : previousText;

    return `💡 *Ранее вы ответили:* _${snippet}_\n\nДавайте теперь разберём этот раздел подробнее.`;
  }

  /**
   * Строит более конкретный вопрос для проблемного подраздела.
   *
   * @param {string} subsectionKey
   * @param {string} originalQuestion
   * @returns {string}
   * @private
   */
  _buildTargetedQuestion(subsectionKey, originalQuestion) {
    return `🔍 *Уточним:* ${originalQuestion}\n\n💡 Постарайтесь описать конкретные факты, цифры или примеры — это очень поможет для полноты документа.`;
  }

  /**
   * Возвращает пустой контекст (нет истории / ошибка).
   *
   * @returns {object}
   * @private
   */
  _emptyContext() {
    return {
      hasHistory: false,
      sessionCount: 0,
      lastSession: null,
      pastProjectThemes: [],
      frequentGaps: [],
      avgDepthPerBlock: {},
      depthDistributionByBlock: {},
      commonL3Topics: [],
      lastSessionSummary: null,
      patterns: {}
    };
  }

  // ==================== Story 5.2 Private Methods ====================

  /**
   * Загружает историю из history.json.
   *
   * @returns {{ sessions: object[], patterns: object }}
   * @private
   */
  _loadHistory() {
    try {
      if (!fs.existsSync(this.historyPath)) {
        return { sessions: [], patterns: {} };
      }

      const data = fs.readFileSync(this.historyPath, 'utf8');
      if (!data || data.trim().length === 0) {
        return { sessions: [], patterns: {} };
      }

      const parsed = JSON.parse(data);

      if (parsed && Array.isArray(parsed.sessions)) {
        return parsed;
      }

      return {
        sessions: Array.isArray(parsed) ? parsed : [],
        patterns: parsed.patterns || {}
      };
    } catch (err) {
      this.logger.error('Failed to load history.json', {
        path: this.historyPath,
        error: err.message
      });
      return { sessions: [], patterns: {} };
    }
  }

  /**
   * Отбирает сессии, принадлежащие указанному пользователю.
   *
   * @param {number|string} userId
   * @returns {object[]}
   * @private
   */
  _getUserSessions(userId) {
    if (userId === undefined || userId === null) {
      return [];
    }
    const history = this._loadHistory();
    const allSessions = history.sessions || [];

    if (userId === '*') {
      return allSessions;
    }

    const userIdStr = String(userId);
    return allSessions.filter(s => String(s.telegramUserId) === userIdStr);
  }

  /**
   * Вычисляет L3-частотность по подразделам.
   *
   * @param {object[]} sessions
   * @returns {Array<{block: number, subsection: string, count: number}>}
   * @private
   */
  _computeFrequentL3Topics(sessions) {
    const l3Counts = {};

    for (const session of sessions) {
      const answers = session.answers || {};
      const depthDist = session.depthDistribution || {};

      for (const [subKey, answer] of Object.entries(answers)) {
        const depthReached = answer.depthReached;
        if (depthReached === 'L3') {
          l3Counts[subKey] = (l3Counts[subKey] || 0) + 1;
          continue;
        }

        if (depthDist[subKey] === 'L3') {
          l3Counts[subKey] = (l3Counts[subKey] || 0) + 1;
        }
      }
    }

    return Object.entries(l3Counts)
      .map(([subKey, count]) => ({
        block: this._extractBlockNumber(subKey),
        subsection: subKey,
        count
      }))
      .sort((a, b) => b.count - a.count);
  }

  /**
   * Вычисляет общие «слепые зоны» — подразделы, оставшиеся на L1.
   *
   * @param {object[]} sessions
   * @returns {Array<{block: number, subsection: string, frequency: number}>}
   * @private
   */
  _computeCommonGaps(sessions) {
    const gapCounts = {};
    let totalSessions = sessions.length;

    for (const session of sessions) {
      const answers = session.answers || {};
      const depthDist = session.depthDistribution || {};

      const allSubsections = new Set([
        ...Object.keys(answers),
        ...Object.keys(depthDist)
      ]);

      for (const subKey of allSubsections) {
        const answer = answers[subKey];
        const depthReached = answer ? answer.depthReached : depthDist[subKey];

        if (depthReached === 'L1') {
          gapCounts[subKey] = (gapCounts[subKey] || 0) + 1;
        }
      }
    }

    return Object.entries(gapCounts)
      .map(([subKey, count]) => ({
        block: this._extractBlockNumber(subKey),
        subsection: subKey,
        frequency: totalSessions > 0
          ? parseFloat((count / totalSessions).toFixed(2))
          : 0
      }))
      .sort((a, b) => b.frequency - a.frequency);
  }

  /**
   * Вычисляет среднюю глубину проработки для каждого блока.
   *
   * @param {object[]} sessions
   * @returns {Array<{blockId: number, avgDepth: number}>}
   * @private
   */
  _computeAvgDepthPerBlock(sessions) {
    const depthTotals = {};

    for (const session of sessions) {
      const blockStats = session.blockStats || {};

      for (const [blockId, stats] of Object.entries(blockStats)) {
        const numericId = parseInt(blockId, 10);

        if (!depthTotals[numericId]) {
          depthTotals[numericId] = { totalDepth: 0, count: 0 };
        }

        const avg = parseFloat(stats.avgDepth) || 0;
        depthTotals[numericId].totalDepth += avg;
        depthTotals[numericId].count++;
      }

      if (Object.keys(blockStats).length === 0) {
        const answers = session.answers || {};
        const depthRank = { L1: 1, L2: 2, L3: 3 };

        for (const [subKey, answer] of Object.entries(answers)) {
          const blockId = this._extractBlockNumber(subKey);
          const rank = depthRank[answer.depthReached] || 1;

          if (!depthTotals[blockId]) {
            depthTotals[blockId] = { totalDepth: 0, count: 0 };
          }
          depthTotals[blockId].totalDepth += rank;
          depthTotals[blockId].count++;
        }
      }
    }

    return Object.entries(depthTotals)
      .map(([blockIdStr, data]) => ({
        blockId: parseInt(blockIdStr, 10),
        avgDepth: data.count > 0
          ? parseFloat((data.totalDepth / data.count).toFixed(2))
          : 1.0
      }))
      .sort((a, b) => a.blockId - b.blockId);
  }

  /**
   * Вычисляет общую среднюю глубину по всем подразделам пользователя.
   *
   * @param {object[]} sessions
   * @returns {number}
   * @private
   */
  _calculateOverallAvgDepth(sessions) {
    const depthRank = { L1: 1, L2: 2, L3: 3 };
    let totalDepth = 0;
    let totalCount = 0;

    for (const session of sessions) {
      const blockStats = session.blockStats || {};

      if (Object.keys(blockStats).length > 0) {
        for (const stats of Object.values(blockStats)) {
          totalDepth += parseFloat(stats.avgDepth) || 0;
          totalCount++;
        }
      } else {
        const answers = session.answers || {};
        for (const answer of Object.values(answers)) {
          totalDepth += depthRank[answer.depthReached] || 1;
          totalCount++;
        }
      }
    }

    return totalCount > 0
      ? parseFloat((totalDepth / totalCount).toFixed(2))
      : 0;
  }

  /**
   * Извлекает номер блока из ключа подраздела.
   *
   * @param {string} subKey
   * @returns {number}
   * @private
   */
  _extractBlockNumber(subKey) {
    if (!subKey) return 0;
    const parts = subKey.split('.');
    return parseInt(parts[0], 10) || 0;
  }

  /**
   * Возвращает пустой результат анализа для пользователя без истории.
   *
   * @param {number|string} userId
   * @returns {object}
   * @private
   */
  _emptyAnalysis(userId) {
    return {
      userId,
      totalSessions: 0,
      avgDepthPerBlock: [],
      frequentL3Topics: [],
      commonGaps: [],
      lastSessionDate: null,
      overallAvgDepth: 0
    };
  }
}

module.exports = LearningEngine;
