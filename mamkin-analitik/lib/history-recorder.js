/**
 * History Recorder — запись истории завершённых сессий для самообучения
 *
 * Story 5.1 — Session history for self-learning (FR22)
 *
 * Каждая завершённая сессия сохраняет ключевые данные в history.json
 * (append-only файл). Исторические данные доступны для анализа паттернов
 * и используются для улучшения опроса в последующих сессиях.
 *
 * Сохраняемые данные:
 *   — ID сессии, пользователь, временные метки
 *   — Ответы пользователя по подразделам (L1/L2/L3)
 *   — Достигнутые глубины (depthReached)
 *   — Собранные риски
 *   — Ключевые слова из финального draft
 *   — Статистика по глубине проработки
 *
 * API:
 *   recordSession(sessionContext)   — сохранить сессию в history.json
 *   getHistory()                    — загрузить всю историю
 *   getStats()                      — агрегированная статистика
 */

const path = require('path');
const fs = require('fs');
const { createLogger } = require('./logger');

const HISTORY_FILE = path.resolve(__dirname, '..', 'history.json');

class HistoryRecorder {
  /**
   * @param {object} [options]
   * @param {string} [options.historyPath] — путь к history.json (для тестов)
   */
  constructor(options = {}) {
    this.historyPath = options.historyPath || HISTORY_FILE;
    this.logger = createLogger('history-recorder');
  }

  // ==================== Public API ====================

  /**
   * Сохраняет сессию в history.json (append-only).
   *
   * Извлекает из SessionContext:
   *   — sessionId, telegramUserId, username
   *   — createdAt, completedAt
   *   — answers (L1/L2/L3) с depthReached
   *   — risks
   *   — draft keywords (из draft.fullText)
   *   — статистику глубины
   *
   * @param {object} sessionContext — SessionContext (или объект с полями сессии)
   * @returns {Promise<object>} — записанная запись истории
   */
  async recordSession(sessionContext) {
    if (!sessionContext || !sessionContext.sessionId) {
      throw new Error('HistoryRecorder: требуется валидный SessionContext с sessionId');
    }

    this.logger.info('Recording session to history', {
      sessionId: sessionContext.sessionId,
      user: sessionContext.telegramUserId
    });

    // Строим запись истории
    const historyEntry = this._buildHistoryEntry(sessionContext);

    // Читаем существующую историю
    let history = this._readHistory();

    // Append-only: добавляем новую запись
    if (!Array.isArray(history.sessions)) {
      history.sessions = [];
    }
    history.sessions.push(historyEntry);

    // Обновляем агрегированные паттерны
    history.patterns = this._updatePatterns(history.patterns || {}, historyEntry);

    // Записываем обратно
    this._writeHistory(history);

    // Обновляем индекс сессий
    this._updateSessionIndex(historyEntry);

    this.logger.info('Session recorded to history', {
      sessionId: sessionContext.sessionId,
      totalSessions: history.sessions.length,
      answersCount: Object.keys(sessionContext.answers || {}).length,
      risksCount: (sessionContext.risks || []).length
    });

    return historyEntry;
  }

  /**
   * Загружает всю историю.
   *
   * @param {object} [options]
   * @param {number} [options.limit] — ограничение количества записей
   * @param {boolean} [options.includePatterns=true] — включать паттерны
   * @returns {{ sessions: object[], patterns: object, sessionIndex: object }}
   */
  getHistory(options = {}) {
    const { limit, includePatterns = true } = options;
    const history = this._readHistory();

    let sessions = history.sessions || [];

    // Сортируем по completedAt (сначала новые)
    sessions = [...sessions].sort(
      (a, b) => new Date(b.completedAt || 0) - new Date(a.completedAt || 0)
    );

    // Ограничение
    if (limit && limit > 0) {
      sessions = sessions.slice(0, limit);
    }

    return {
      sessions,
      patterns: includePatterns ? (history.patterns || {}) : {},
      sessionIndex: history.sessionIndex || {}
    };
  }

  /**
   * Возвращает агрегированную статистику по завершённым сессиям.
   *
   * @returns {object} статистика
   */
  getStats() {
    const history = this._readHistory();
    const sessions = history.sessions || [];

    if (sessions.length === 0) {
      return this._emptyStats();
    }

    // Общая статистика
    const totalSessions = sessions.length;
    const uniqueUsers = new Set(sessions.map(s => s.telegramUserId)).size;

    // Статистика по глубине
    const depthCounts = { L1: 0, L2: 0, L3: 0 };
    let totalSubsections = 0;

    for (const session of sessions) {
      const depthStats = session.depthStats || {};
      for (const [depth, count] of Object.entries(depthStats)) {
        if (depthCounts[depth] !== undefined) {
          depthCounts[depth] += count;
        }
        totalSubsections += count;
      }
    }

    // Распределение глубины
    const depthDistribution = {};
    for (const [depth, count] of Object.entries(depthCounts)) {
      depthDistribution[depth] = totalSubsections > 0
        ? Math.round((count / totalSubsections) * 100)
        : 0;
    }

    // Средняя глубина (L1=1, L2=2, L3=3)
    const avgDepth = totalSubsections > 0
      ? (
          (depthCounts.L1 * 1 + depthCounts.L2 * 2 + depthCounts.L3 * 3) /
          (depthCounts.L1 + depthCounts.L2 + depthCounts.L3)
        ).toFixed(2)
      : 0;

    // Статистика по рискам
    const totalRisks = sessions.reduce((sum, s) => sum + (s.risksCount || 0), 0);
    const avgRisksPerSession = totalSessions > 0
      ? (totalRisks / totalSessions).toFixed(1)
      : 0;

    // Категории рисков
    const riskCategories = {};
    for (const session of sessions) {
      if (session.risksByCategory) {
        for (const [cat, count] of Object.entries(session.risksByCategory)) {
          riskCategories[cat] = (riskCategories[cat] || 0) + count;
        }
      }
    }

    // Распределение по блокам (сколько сессий заполнили каждый блок)
    const blockUsage = {};
    for (const session of sessions) {
      if (session.blockStats) {
        for (const [blockId, stats] of Object.entries(session.blockStats)) {
          if (!blockUsage[blockId]) {
            blockUsage[blockId] = { sessions: 0, avgDepth: 0, totalDepth: 0 };
          }
          blockUsage[blockId].sessions++;
          blockUsage[blockId].totalDepth += stats.avgDepth || 0;
        }
      }
    }
    for (const blockId of Object.keys(blockUsage)) {
      blockUsage[blockId].avgDepth = blockUsage[blockId].sessions > 0
        ? (blockUsage[blockId].totalDepth / blockUsage[blockId].sessions).toFixed(2)
        : 0;
      delete blockUsage[blockId].totalDepth;
    }

    // Тренды: по дням
    const sessionsByDay = {};
    for (const session of sessions) {
      const day = session.completedAt
        ? session.completedAt.slice(0, 10)
        : 'unknown';
      if (!sessionsByDay[day]) sessionsByDay[day] = 0;
      sessionsByDay[day]++;
    }

    // Частотные ключевые слова из draft
    const keywordFrequency = {};
    for (const session of sessions) {
      const keywords = session.keywords || [];
      for (const kw of keywords) {
        keywordFrequency[kw] = (keywordFrequency[kw] || 0) + 1;
      }
    }
    const topKeywords = Object.entries(keywordFrequency)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 20)
      .map(([word, count]) => ({ word, count }));

    return {
      totalSessions,
      uniqueUsers,
      totalSubsections,
      depthStats: depthCounts,
      depthDistribution,
      avgDepth: parseFloat(avgDepth),
      totalRisks,
      avgRisksPerSession: parseFloat(avgRisksPerSession),
      riskCategories,
      blockUsage,
      sessionsByDay,
      topKeywords,
      patterns: history.patterns || {}
    };
  }

  /**
   * Экспорт истории в упрощённом формате для анализа.
   *
   * @returns {Array<object>} — массив записей для анализа
   */
  exportForAnalysis() {
    const history = this._readHistory();
    const sessions = history.sessions || [];

    return sessions.map(entry => ({
      sessionId: entry.sessionId,
      telegramUserId: entry.telegramUserId,
      completedAt: entry.completedAt,
      totalSubsections: entry.totalSubsections,
      depthDistribution: entry.depthDistribution,
      avgDepth: entry.avgDepth,
      risksCount: entry.risksCount,
      keywords: entry.keywords || [],
      topDepthPerBlock: entry.topDepthPerBlock
    }));
  }

  // ==================== Private Methods ====================

  /**
   * Строит запись истории из SessionContext.
   *
   * @param {object} ctx — SessionContext
   * @returns {object} запись для history.json
   * @private
   */
  _buildHistoryEntry(ctx) {
    const answers = ctx.answers || {};
    const risks = ctx.risks || [];
    const draft = ctx.draft || null;

    // Извлекаем вопросы из answers (по ключам подразделов)
    const questions = this._extractQuestions(answers);

    // Статистика по глубине
    const depthStats = { L1: 0, L2: 0, L3: 0 };
    const depthDistribution = {};

    for (const [subKey, answer] of Object.entries(answers)) {
      const depth = answer.depthReached || 'L1';
      if (depthStats[depth] !== undefined) {
        depthStats[depth]++;
      }
      depthDistribution[subKey] = depth;
    }

    // Средняя глубина
    const totalAnswered = Object.keys(answers).length;
    const avgDepth = totalAnswered > 0
      ? (
          (depthStats.L1 * 1 + depthStats.L2 * 2 + depthStats.L3 * 3) /
          (depthStats.L1 + depthStats.L2 + depthStats.L3 || 1)
        ).toFixed(2)
      : 0;

    // Группировка рисков по категориям
    const risksByCategory = {};
    for (const risk of risks) {
      const cat = risk.category || 'uncategorized';
      if (!risksByCategory[cat]) risksByCategory[cat] = 0;
      risksByCategory[cat]++;
    }

    // Ключевые слова из draft
    const keywords = draft && draft.fullText
      ? this._extractKeywords(draft.fullText)
      : [];

    // Статистика по блокам
    const blockStats = {};
    for (const [subKey, answer] of Object.entries(answers)) {
      const blockId = subKey.split('.')[0];
      if (!blockStats[blockId]) {
        blockStats[blockId] = { subsections: 0, totalDepth: 0 };
      }
      blockStats[blockId].subsections++;
      const rank = { L1: 1, L2: 2, L3: 3 };
      blockStats[blockId].totalDepth += rank[answer.depthReached] || 1;
    }
    for (const blockId of Object.keys(blockStats)) {
      blockStats[blockId].avgDepth = blockStats[blockId].subsections > 0
        ? (blockStats[blockId].totalDepth / blockStats[blockId].subsections).toFixed(2)
        : 0;
      delete blockStats[blockId].totalDepth;
    }

    // Максимальная глубина на блок
    const topDepthPerBlock = {};
    for (const [subKey, answer] of Object.entries(answers)) {
      const blockId = subKey.split('.')[0];
      const rank = { L1: 1, L2: 2, L3: 3 };
      const currentRank = rank[answer.depthReached] || 1;
      if (!topDepthPerBlock[blockId] || currentRank > rank[topDepthPerBlock[blockId]]) {
        topDepthPerBlock[blockId] = answer.depthReached || 'L1';
      }
    }

    return {
      sessionId: ctx.sessionId,
      telegramUserId: ctx.telegramUserId,
      username: ctx.meta ? ctx.meta.username : null,
      createdAt: ctx.meta ? ctx.meta.createdAt : null,
      completedAt: ctx.meta ? ctx.meta.completedAt : new Date().toISOString(),
      recordedAt: new Date().toISOString(),

      // Вопросы и ответы
      totalSubsections: totalAnswered,
      questions,
      answers,
      depthStats,
      depthDistribution,
      avgDepth: parseFloat(avgDepth),
      topDepthPerBlock,

      // Риски
      risksCount: risks.length,
      risksByCategory,
      risks: risks.map(r => ({
        text: r.text,
        category: r.category || 'uncategorized',
        collectedAt: r.collectedAt || null
      })),

      // Draft
      keywords,
      draftLength: draft && draft.fullText ? draft.fullText.length : 0,
      draftSnippet: draft && draft.fullText
        ? draft.fullText.slice(0, 200)
        : null,

      // Блоковая статистика
      blockStats
    };
  }

  /**
   * Извлекает вопросы из ответов (по ключам подразделов).
   *
   * @param {object} answers — { subKey: { L1, L2, L3, depthReached } }
   * @returns {object} — { subKey: { questionId, depthReached, levels: [L1, L2, L3] } }
   * @private
   */
  _extractQuestions(answers) {
    const questions = {};
    for (const [subKey, answer] of Object.entries(answers)) {
      if (!answer) continue;
      questions[subKey] = {
        subsectionId: subKey,
        depthReached: answer.depthReached || 'none',
        levels: {
          L1: answer.L1 ? true : false,
          L2: answer.L2 ? true : false,
          L3: answer.L3 ? true : false
        }
      };
    }
    return questions;
  }

  /**
   * Извлекает ключевые слова из текста draft.
   *
   * Алгоритм:
   *   1. Убирает стоп-слова (предлоги, союзы, частицы)
   *   2. Оставляет слова длиннее 4 символов
   *   3. Нормализует в нижний регистр
   *   4. Возвращает топ-15 по частоте
   *
   * @param {string} text — полный текст draft
   * @returns {string[]} — массив ключевых слов
   * @private
   */
  _extractKeywords(text) {
    if (!text || text.length < 20) return [];

    // Стоп-слова (русские и английские)
    const stopWords = new Set([
      'это', 'что', 'для', 'все', 'или', 'как', 'его', 'она', 'они',
      'нас', 'вас', 'них', 'без', 'над', 'под', 'при', 'там', 'тут',
      'эти', 'быть', 'был', 'была', 'были', 'было', 'если', 'чтобы',
      'потом', 'когда', 'даже', 'уже', 'ещё', 'тоже', 'вот', 'здесь',
      'можно', 'нужно', 'должен', 'должна', 'должны', 'будет', 'будут',
      'this', 'that', 'with', 'from', 'have', 'been', 'were', 'they',
      'them', 'their', 'will', 'would', 'could', 'should', 'about',
      'which', 'there', 'what', 'when', 'where', 'also', 'than', 'then',
      'very', 'just', 'more', 'some', 'such', 'only', 'other', 'over',
      'into', 'after', 'before', 'those'
    ]);

    // Разбиваем на слова
    const words = text
      .toLowerCase()
      .replace(/[^а-яёa-z0-9\s-]/gi, ' ')
      .split(/\s+/)
      .filter(w => w.length > 4 && !stopWords.has(w));

    // Считаем частоту
    const freq = {};
    for (const word of words) {
      // Нормализация: убираем окончания (простая стемминг-заглушка)
      const stem = word.replace(/[аяеёийоуыэю]ми?$/i, '').replace(/[аяеёийоуыэю]в?$/i, '');
      const key = stem.length > 3 ? stem : word;
      freq[key] = (freq[key] || 0) + 1;
    }

    // Топ-15
    return Object.entries(freq)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 15)
      .map(([word]) => word);
  }

  /**
   * Читает history.json.
   *
   * @returns {{ sessions: object[], patterns: object, sessionIndex: object }}
   * @private
   */
  _readHistory() {
    try {
      if (!fs.existsSync(this.historyPath)) {
        return { sessions: [], patterns: {}, sessionIndex: {} };
      }

      const data = fs.readFileSync(this.historyPath, 'utf8');

      // Обработка пустого файла
      if (!data || data.trim().length === 0) {
        return { sessions: [], patterns: {}, sessionIndex: {} };
      }

      // Обработка случая, когда файл содержит пустой объект {}
      const parsed = JSON.parse(data);

      // Проверяем структуру
      if (parsed && Array.isArray(parsed.sessions)) {
        return parsed;
      }

      // Если файл был пустым объектом {} или другой формат — мигрируем
      return {
        sessions: Array.isArray(parsed) ? parsed : [],
        patterns: parsed.patterns || {},
        sessionIndex: parsed.sessionIndex || {}
      };
    } catch (err) {
      this.logger.error('Failed to read history.json', {
        path: this.historyPath,
        error: err.message
      });
      return { sessions: [], patterns: {}, sessionIndex: {} };
    }
  }

  /**
   * Записывает историю в history.json (транзакционная запись).
   *
   * @param {object} history — { sessions, patterns, sessionIndex }
   * @private
   */
  _writeHistory(history) {
    const tempPath = this.historyPath + '.tmp.' + process.pid;
    const json = JSON.stringify(history, null, 2);

    try {
      fs.writeFileSync(tempPath, json, 'utf8');
      fs.renameSync(tempPath, this.historyPath);
    } catch (err) {
      // Очистка временного файла
      try {
        if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
      } catch (_) { /* ignore */ }
      throw new Error(`Failed to write history.json: ${err.message}`);
    }
  }

  /**
   * Обновляет агрегированные паттерны на основе новой записи.
   *
   * @param {object} patterns — существующие паттерны
   * @param {object} entry — новая запись
   * @returns {object} обновлённые паттерны
   * @private
   */
  _updatePatterns(patterns, entry) {
    const updated = { ...patterns };

    // Частотные L3-темы — ключевые слова из сессий с L3-глубиной
    const l3Keywords = [];
    const answers = entry.answers || {};
    for (const [subKey, answer] of Object.entries(answers)) {
      if (answer.depthReached === 'L3' && answer.L3) {
        l3Keywords.push(...this._extractKeywords(answer.L3));
      }
    }
    const existingL3 = updated.frequentL3Topics || [];
    updated.frequentL3Topics = [...new Set([...existingL3, ...l3Keywords])].slice(0, 30);

    // Средняя глубина по блокам (экспоненциальное скользящее среднее)
    const existingAvgDepth = updated.avgDepthPerBlock || {};
    const blockStats = entry.blockStats || {};
    for (const [blockId, stats] of Object.entries(blockStats)) {
      const existing = existingAvgDepth[blockId] || 1.0;
      // Скользящее среднее с α=0.3
      existingAvgDepth[blockId] = parseFloat(
        (existing * 0.7 + parseFloat(stats.avgDepth) * 0.3).toFixed(2)
      );
    }
    updated.avgDepthPerBlock = existingAvgDepth;

    // Распределение глубины по блокам
    const existingDepthByBlock = updated.depthDistributionByBlock || {};
    for (const [subKey, depth] of Object.entries(entry.depthDistribution || {})) {
      const blockId = subKey.split('.')[0];
      if (!existingDepthByBlock[blockId]) {
        existingDepthByBlock[blockId] = { L1: 0, L2: 0, L3: 0, total: 0 };
      }
      if (existingDepthByBlock[blockId][depth] !== undefined) {
        existingDepthByBlock[blockId][depth]++;
        existingDepthByBlock[blockId].total++;
      }
    }
    updated.depthDistributionByBlock = existingDepthByBlock;

    // Общие "узкие места" — подразделы, где часто не достигают L2
    const existingGaps = updated.commonGaps || [];
    for (const [subKey, answer] of Object.entries(answers)) {
      if (answer.depthReached === 'L1') {
        if (!existingGaps.includes(subKey)) {
          existingGaps.push(subKey);
        }
      }
    }
    updated.commonGaps = existingGaps.slice(0, 20);

    // Популярные темы (ключевые слова из всех сессий)
    const existingTopics = updated.frequentTopics || [];
    const newKeywords = entry.keywords || [];
    for (const kw of newKeywords) {
      if (!existingTopics.includes(kw)) {
        existingTopics.push(kw);
      }
    }
    updated.frequentTopics = existingTopics.slice(0, 30);

    // Тренд завершений по месяцам
    const month = entry.completedAt ? entry.completedAt.slice(0, 7) : 'unknown';
    const existingTrend = updated.completionTrend || {};
    existingTrend[month] = (existingTrend[month] || 0) + 1;
    updated.completionTrend = existingTrend;

    // Общее количество сессий
    const allSessions = this._readHistory().sessions || [];
    updated.totalSessions = allSessions.length + 1;

    // Среднее количество рисков
    const totalRisks = allSessions.reduce((sum, s) => sum + (s.risksCount || 0), 0);
    updated.avgRisksPerSession = parseFloat(
      ((totalRisks + (entry.risksCount || 0)) / (allSessions.length + 1)).toFixed(1)
    );

    return updated;
  }

  /**
   * Обновляет индекс сессий по пользователям.
   *
   * @param {object} entry — запись истории
   * @private
   */
  _updateSessionIndex(entry) {
    // Индекс хранится как часть history.json
    // Обновляется при записи через _writeHistory
    // Здесь просто логируем
    this.logger.debug('Session index updated', {
      userId: entry.telegramUserId,
      sessionId: entry.sessionId
    });
  }

  /**
   * Возвращает пустую статистику.
   *
   * @returns {object}
   * @private
   */
  _emptyStats() {
    return {
      totalSessions: 0,
      uniqueUsers: 0,
      totalSubsections: 0,
      depthStats: { L1: 0, L2: 0, L3: 0 },
      depthDistribution: {},
      avgDepth: 0,
      totalRisks: 0,
      avgRisksPerSession: 0,
      riskCategories: {},
      blockUsage: {},
      sessionsByDay: {},
      topKeywords: [],
      patterns: {}
    };
  }
}

module.exports = HistoryRecorder;
