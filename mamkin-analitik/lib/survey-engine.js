/**
 * Survey Engine — движок адаптивного опроса
 *
 * Stories:
 *   1.6 — Автоматическое сохранение черновиков сессии
 *   2.1 — Базовая логика последовательного опроса
 *   2.2 — Глубина L1 (открывающие вопросы, Reflection Message)
 *   2.3 — Глубина L2 (уточняющие вопросы, контекстная адаптация)
 *   5.1 — Session history for self-learning (signalCompletion вызывает historyRecorder)
 *   5.3 — Context reuse from previous BRDs (startSurvey вызывает LearningEngine)
 *   5.4 — Async self-learning update (signalCompletion вызывает learningEngine.triggerAsyncUpdate)
 *
 * Управляет процессом опроса: загружает template, задаёт вопросы L1→L2→L3,
 * оценивает глубину ответов, переходит между подразделами и блоками,
 * автоматически сохраняет черновики через session-manager.
 *
 * Depth evaluation (из data/depth-config.json):
 *   0.0-0.3 → L2 (уточняющий)
 *   0.3-0.6 → L3 (корневой)
 *   0.6-1.0 → фиксация с достигнутой глубиной, переход к следующему подразделу
 *
 * L2 question format (Story 2.3):
 *   Префикс причины: "Чтобы лучше понять ситуацию, уточню..."
 *   Вопрос: "🔍 Давайте уточним: [контекстно-адаптированный вопрос]"
 *   Контекстная привязка к предыдущему ответу пользователя
 *
 * Сообщение при паузе >30 минут:
 *   Session Resume Card — показывает последний сохранённый ответ и текущую позицию.
 *
 * Ошибки ФС:
 *   При ошибке сохранения — пользователь получает уведомление и ответ сохраняется
 *   в memory-кеше для повторной попытки.
 */

const path = require('path');
const fs = require('fs');
const { createLogger } = require('./logger');

// Путь к depth-config.json
const DEPTH_CONFIG_PATH = path.resolve(__dirname, '..', 'data', 'depth-config.json');

/**
 * @typedef {Object} DepthConfig
 * @property {Object} levels — { L1, L2, L3 } с порогами
 * @property {Object} scoring — настройки оценки глубины
 * @property {number} scoring.minFactsForL2
 * @property {number} scoring.minSentencesForL2
 * @property {number} scoring.minFactsForL3
 * @property {number} scoring.minSentencesForL3
 * @property {string[]} scoring.vaguePhrases
 * @property {string[]} scoring.depthIndicators
 * @property {string[]} scoring.causalIndicators
 */

class SurveyEngine {
  /**
   * @param {object} deps
   * @param {object} deps.sessionManager — экземпляр SessionManager
   * @param {object} deps.templateEngine — экземпляр TemplateEngine
   * @param {object} [deps.historyRecorder] — экземпляр HistoryRecorder (Story 5.1)
   * @param {object} [deps.learningEngine] — экземпляр LearningEngine (Story 5.4)
   * @param {string} [deps.depthConfigPath] — путь к depth-config.json (опционально)
   */
  constructor(deps = {}) {
    this.sessionManager = deps.sessionManager;
    this.templateEngine = deps.templateEngine;
    /** @type {import('./history-recorder')|null} */
    this.historyRecorder = deps.historyRecorder || null;
    /** @type {import('./learning-engine')|null} */
    this.learningEngine = deps.learningEngine || null;
    this.logger = createLogger('survey-engine');

    /** @type {DepthConfig|null} */
    this.depthConfig = null;

    // Загружаем depth-config
    const configPath = deps.depthConfigPath || DEPTH_CONFIG_PATH;
    this._loadDepthConfig(configPath);

    // Портоговые значения по умолчанию (из depth-config.json или hardcoded)
    this.L2_THRESHOLD = this.depthConfig?.levels?.L1?.nextLevelThreshold ?? 0.3;
    this.L3_THRESHOLD = this.depthConfig?.levels?.L2?.nextLevelThreshold ?? 0.6;

    // Scoring defaults
    const scoring = this.depthConfig?.scoring || {};
    this.MIN_FACTS_L2 = scoring.minFactsForL2 ?? 2;
    this.MIN_SENTENCES_L2 = scoring.minSentencesForL2 ?? 3;
    this.MIN_FACTS_L3 = scoring.minFactsForL3 ?? 4;
    this.MIN_SENTENCES_L3 = scoring.minSentencesForL3 ?? 6;
    this.vaguePhrases = scoring.vaguePhrases ?? [
      'всё плохо', 'надо автоматизировать', 'нужно улучшить',
      'сделать удобно', 'как-то не так'
    ];
    this.depthIndicators = scoring.depthIndicators ?? [
      'цифры', 'количество', 'процентов', 'дней', 'часов',
      'рублей', 'пример', 'конкретно'
    ];
    this.causalIndicators = scoring.causalIndicators ?? [
      'потому что', 'из-за', 'причина', 'следовательно', 'в результате'
    ];

    // Кэш ошибок ФС для повторной попытки
    /** @type {Map<string, { session: object, lastError: string, retries: number }>} */
    this._fsErrorCache = new Map();

    // Максимальное количество повторов при ошибке ФС
    this.MAX_FS_RETRIES = 3;
  }

  // ==================== Session Context Integration (Story 2.1) ====================

  /**
   * Создаёт SessionContext из текущего состояния сессии.
   * Используется для передачи данных следующему агенту пайплайна (compiler).
   *
   * @param {object} session — объект сессии
   * @returns {object} SessionContext
   * @throws {Error} если сессия не валидна
   */
  getSessionContext(session) {
    const SessionContext = require('./session-context');

    if (!session || !session.sessionId) {
      throw new Error('SurveyEngine: требуется валидная сессия для создания SessionContext');
    }

    const ctx = SessionContext.fromSession(session);

    // Устанавливаем прогресс
    const progress = this.getProgress(session);
    ctx.setProgress(progress.percent);
    ctx.currentBlock = progress.block;
    ctx.currentSubsection = progress.subsection;
    ctx.depth = progress.depth;

    // Обновляем мета-время
    ctx.meta.updatedAt = new Date().toISOString();

    this.logger.debug('SessionContext created', {
      sessionId: session.sessionId,
      progress: progress.percent,
      answersCount: ctx.getAnsweredCount(),
      risksCount: ctx.risks.length
    });

    return ctx;
  }

  /**
   * Проверяет, пройдены ли все 7 блоков опроса.
   * Каждый подраздел считается пройденным, если у него есть depthReached.
   *
   * @param {object} session — объект сессии
   * @returns {boolean}
   */
  allSectionsComplete(session) {
    if (!this.templateEngine || !session) return false;

    try {
      const totalBlocks = this.templateEngine.getBlockCount();

      for (let b = 1; b <= totalBlocks; b++) {
        const block = this.templateEngine.getBlock(b);
        if (!block || !block.subsections) continue;

        for (const sub of block.subsections) {
          const answer = session.answers && session.answers[sub.id];
          if (!answer || !answer.depthReached) {
            return false;
          }
        }
      }

      return true;
    } catch (err) {
      this.logger.warn('allSectionsComplete check failed', {
        error: err.message
      });
      return false;
    }
  }

  /**
   * Сигнализирует о завершении опроса / публикации.
   *
   * Story 2.1: Возвращает финальное сообщение и SessionContext для передачи составителю
   *   при завершении опроса (без links).
   * Story 4.4: Принимает опциональные links (docxUrl, htmlUrl) от агента-генератора
   *   и возвращает финальное сообщение со ссылками на готовый документ.
   *
   * @param {object} session — объект сессии
   * @param {object} [links] — опциональные ссылки на готовый документ
   * @param {string} [links.docxUrl] — URL для скачивания DOCX
   * @param {string} [links.htmlUrl] — URL веб-версии
   * @returns {Promise<{ message: string, context: object }>}
   */
  async signalCompletion(session, links) {
    if (!session) {
      throw new Error('SurveyEngine: требуется сессия для signalCompletion');
    }

    if (!this.allSectionsComplete(session)) {
      this.logger.warn('signalCompletion called but not all sections complete', {
        sessionId: session.sessionId
      });
    }

    // Отмечаем сессию как завершённую (только в памяти, не на диске —
    // SessionManager.completeSession() с перемещением в completed/ будет
    // вызван на финальном этапе пайплайна)
    session.status = 'completed';
    session.completedAt = new Date().toISOString();
    session.updatedAt = new Date().toISOString();

    // Сохраняем через Session Manager (в active/ — не меняем директорию)
    // Явно сохраняем статус 'completed' только в памяти, файл остаётся в active/
    // чтобы loadSession не потерял сессию при повторной загрузке
    let savedSession = session;
    try {
      // Сохраняем с временной заменой статуса, чтобы файл остался в active/
      const originalStatus = session.status;
      session.status = 'in_progress';
      savedSession = await this._saveSessionSafe(session);
      savedSession.status = originalStatus;
      savedSession.completedAt = session.completedAt;
      session.status = originalStatus;
    } catch (err) {
      this.logger.error('Failed to save session during signalCompletion', {
        sessionId: session.sessionId,
        error: err.message
      });
    }

    const context = this.getSessionContext(savedSession);
    context.status = 'completed';
    context.meta.completedAt = session.completedAt;
    context.meta.updatedAt = session.updatedAt;

    // ===== Story 5.1 — Record session to history (self-learning) =====
    // Fire-and-forget: не блокируем ответ пользователю из-за ошибки записи истории
    if (this.historyRecorder) {
      this._recordToHistory(context).catch(err => {
        this.logger.error('Failed to record session to history', {
          sessionId: session.sessionId,
          error: err.message
        });
      });
    }

    // ===== Story 5.4 — Async self-learning update =====
    // Non-blocking: ответ уже отправлен пользователю, обновление в фоне.
    // Не дожидаемся выполнения — fire-and-forget через setImmediate внутри triggerAsyncUpdate.
    if (this.learningEngine) {
      this._triggerLearningUpdate(session.sessionId).catch(err => {
        this.logger.error('Failed to trigger learning update', {
          sessionId: session.sessionId,
          error: err.message
        });
      });
    }

    // ===== Story 4.4 — Link sharing =====
    // Если переданы links от агента-генератора — строим финальное сообщение с ссылками
    if (links && (links.docxUrl || links.htmlUrl)) {
      const hasDocx = !!links.docxUrl;
      const hasHtml = !!links.htmlUrl;

      this.logger.info('signalCompletion with publication links', {
        sessionId: session.sessionId,
        hasDocx,
        hasHtml
      });

      const messageParts = ['📄 *Ваш документ готов!*'];

      if (hasDocx) {
        messageParts.push(`📎 DOCX: ${links.docxUrl}`);
      }

      if (hasHtml) {
        messageParts.push(`🌐 Web: ${links.htmlUrl}`);
      }

      // Если один из форматов недоступен — уведомляем
      if (hasDocx && !hasHtml) {
        messageParts.push('');
        messageParts.push('🌐 Веб-версия временно недоступна.');
      }

      if (!hasDocx && hasHtml) {
        messageParts.push('');
        messageParts.push('📎 DOCX временно недоступен.');
      }

      const message = messageParts.join('\n');

      return { message, context };
    }

    // ===== Fallback: опрос завершён, но публикация не удалась =====
    if (links && !links.docxUrl && !links.htmlUrl) {
      this.logger.warn('signalCompletion called with empty links — publication failed', {
        sessionId: session.sessionId
      });

      const message =
        '📄 *Ваш документ сформирован.*\n\n' +
        'Опубликовать не удалось. Пожалуйста, попробуйте повторить публикацию позже или обратитесь к администратору.';

      return { message, context };
    }

    // ===== Legacy: опрос завершён (без links) — сообщение для передаче составителю =====
    // Строим сводку по категориям рисков
    const rc = context.riskContext;
    const catCountStr = Object.entries(rc.byCategory)
      .map(([cat, risks]) => `  • ${cat}: ${risks.length}`)
      .join('\n');

    const message =
      '✅ *Опрос завершён!*\n\n' +
      'Спасибо за подробные ответы! Я собрал всю информацию по всем 7 блокам бизнес-требований.\n\n' +
      '📋 *Сводка:*\n' +
      `📊 Прогресс: 100% (все подразделы заполнены)\n` +
      `⚠️ Собрано рисков: ${rc.count}\n` +
      (rc.count > 0 ? `📂 По категориям:\n${catCountStr}\n\n` : '\n') +
      '🔄 *Передаю данные составителю для формирования документа.*\n' +
      'Пожалуйста, подождите — сейчас будет сформирован черновик бизнес-требований.';

    return { message, context };
  }

  // ==================== Основной API ====================

  /**
   * Начинает опрос: загружает template, инициализирует сессию,
   * задаёт первый L1-вопрос из блока 1, подраздела 1.1.
   *
   * Story 5.3 — при наличии LearningEngine проверяет историю пользователя
   * и возвращает персонализированное приветствие для возвращающихся пользователей,
   * а также адаптирует первый вопрос с учётом предыдущих пробелов.
   *
   * @param {object} session — объект сессии (уже создан через sessionManager.createSession)
   * @returns {Promise<{ question: string, progress: object, session: object }>}
   * @throws {Error} если template не загружен
   */
  async startSurvey(session) {
    if (!this.templateEngine) {
      throw new Error('SurveyEngine: TemplateEngine не подключён');
    }

    // Проверяем, что template загружен
    try {
      this.templateEngine.getBlockCount();
    } catch {
      throw new Error('SurveyEngine: TemplateEngine не загружен. Вызовите templateEngine.load()');
    }

    // Сбрасываем позицию в сессии на первый блок/подраздел
    const firstQuestion = this.templateEngine.getFirstQuestion();

    session.template = {
      block: 1,
      subsection: '1.1',
      depth: 'L1'
    };

    // ===== Story 5.3: Personalized greeting + gap-aware first question =====
    let personalizedGreeting = null;
    let userContext = null;

    if (this.learningEngine && session.telegramUserId) {
      try {
        userContext = await this.learningEngine.getContextForUser(session.telegramUserId);

        if (userContext && userContext.hasHistory) {
          personalizedGreeting = await this.learningEngine.getPersonalizedGreeting(session.telegramUserId);

          // Сохраняем контекст в сессии для использования при последующих вопросах
          session._userContext = {
            hasHistory: true,
            frequentGaps: userContext.frequentGaps || [],
            pastProjectThemes: (userContext.pastProjectThemes || []).slice(0, 3),
            depthDistributionByBlock: userContext.depthDistributionByBlock || {}
          };

          this.logger.info('Personalized survey start', {
            sessionId: session.sessionId,
            userId: session.telegramUserId,
            hasHistory: true,
            gapCount: (userContext.frequentGaps || []).length
          });
        }
      } catch (err) {
        this.logger.warn('Failed to load user context for personalization', {
          sessionId: session.sessionId,
          userId: session.telegramUserId,
          error: err.message
        });
        // Не блокируем старт из-за ошибки персонализации
      }
    }

    // Строим финальный вопрос
    let question;

    if (personalizedGreeting) {
      // Персонализированное приветствие + вопрос
      // Для возвращающегося пользователя с известными пробелами — используем gap-aware
      let firstSubQuestion;
      if (userContext && userContext.frequentGaps && userContext.frequentGaps.includes('1.1')) {
        // Первый подраздел был проблемным — персонализируем
        firstSubQuestion = this.learningEngine
          ? this.learningEngine.getGapAwareQuestion('1.1', userContext, firstQuestion.question)
          : firstQuestion.question;
      } else {
        firstSubQuestion = firstQuestion.question;
      }

      question = `${personalizedGreeting}

💬 ${firstSubQuestion}`;
    } else {
      question = firstQuestion.question;
    }

    // Сохраняем через Session Manager (транзакционно)
    try {
      session = await this._saveSessionSafe(session);
    } catch (err) {
      this.logger.error('Failed to save session on startSurvey', {
        sessionId: session.sessionId,
        error: err.message
      });
      // Не блокируем старт из-за ошибки сохранения
    }

    this.logger.info('Survey started', {
      sessionId: session.sessionId,
      block: 1,
      subsection: '1.1',
      depth: 'L1',
      personalized: !!personalizedGreeting
    });

    return {
      question,
      progress: this.getProgress(session),
      session
    };
  }

  /**
   * Обрабатывает ответ пользователя:
   * 1. Оценивает глубину ответа
   * 2. Сохраняет ответ в сессию (транзакционно)
   * 3. Решает: L2, L3 или переход к следующему подразделу
   * 4. Возвращает следующий вопрос (или финальное сообщение)
   *
   * @param {object} session — объект сессии
   * @param {string} answer — текст ответа пользователя
   * @returns {Promise<{ question: string|null, progress: object, session: object, action: string }>}
   *   action: 'next_question' | 'survey_complete' | 'error'
   */
  async processAnswer(session, answer) {
    if (!session || !session.sessionId) {
      throw new Error('SurveyEngine: сессия не валидна');
    }

    const currentSub = session.template.subsection;
    const currentDepth = session.template.depth;
    const currentBlock = session.template.block;
    const subsectionKey = currentSub;

    // ===== Story 2.6: Handle return-to-section flow =====
    // Если пользователь вернулся к разделу (returnToSection был вызван ранее)
    // и теперь отвечает — обновляем ответ и продолжаем с origin-позиции
    if (session._returnActive && session._returnActive.subsection === currentSub) {
      return await this._handleReturnAnswer(session, answer, currentSub);
    }

    // ===== Story 2.2: Handle reflection pending (confirmation/correction) =====
    if (session.reflectionPending) {
      return await this._handleReflectionConfirm(session, answer);
    }

    // 1. Оцениваем глубину ответа
    const depthScore = this._evaluateDepth(answer);

    // 2. Сохраняем ответ в сессию
    if (!session.answers) {
      session.answers = {};
    }

    if (!session.answers[subsectionKey]) {
      session.answers[subsectionKey] = {};
    }

    // Сохраняем ответ на текущем уровне глубины
    session.answers[subsectionKey][currentDepth] = answer;

    // 3. Определяем, какой уровень глубины достигнут
    let reachedDepth;
    let nextDepth;

    // ===== NEW Story 2.2: L1-specific deep-enough check (≥3 sentences OR ≥2 facts) =====
    if (currentDepth === 'L1' && this._isL1DeepEnough(answer)) {
      // Развёрнутый ответ на L1 → фиксация на L1 + Reflection Message
      reachedDepth = 'L1';
      nextDepth = null;

      session.answers[subsectionKey].depthReached = 'L1';
      session.reflectionPending = true;
      session.reflectionAnswer = answer;
      session.reflectionSubsection = subsectionKey;

      // Собираем риски
      const detectedRisks = this._collectRisks(answer, session, subsectionKey, 'L1');
      if (detectedRisks.length > 0) {
        if (!session.risks) session.risks = [];
        session.risks.push(...detectedRisks);
      }

      session.updatedAt = new Date().toISOString();

      // Сохраняем сессию
      try {
        session = await this._saveSessionSafe(session);
      } catch (err) {
        this.logger.error('Failed to save session on reflection_needed', {
          sessionId: session.sessionId, error: err.message
        });
        this._fsErrorCache.set(session.sessionId, {
          session, lastError: err.message, retries: 1
        });
        return {
          question: '⚠️ Не удалось сохранить ответ. Попробуйте позже.',
          progress: this.getProgress(session),
          session,
          action: 'error'
        };
      }

      const reflection = this.buildReflection(answer);

      this.logger.debug('L1 deep answer → reflection needed', {
        sessionId: session.sessionId,
        subsection: subsectionKey,
        reflectionSentenceCount: answer.split(/[.!?]+/).filter(s => s.trim()).length
      });

      return {
        question: reflection,
        progress: this.getProgress(session),
        session,
        action: 'reflection_needed'
      };
    }

    // ===== Existing depth decision logic (for L2/L3 or shallow L1) =====
    if (depthScore >= this.L3_THRESHOLD) {
      // Ответ достаточно глубокий — фиксируем L3 (максимум)
      reachedDepth = currentDepth; // L1, L2 или L3
      nextDepth = null; // переход к следующему подразделу
    } else if (depthScore >= this.L2_THRESHOLD && currentDepth === 'L1') {
      // Средняя глубина на L1 — переходим на L2
      reachedDepth = 'L1';
      nextDepth = 'L2';
    } else if (depthScore >= this.L2_THRESHOLD && currentDepth === 'L2') {
      // Средняя глубина на L2 — переходим на L3
      reachedDepth = 'L2';
      nextDepth = 'L3';
    } else if (depthScore < this.L2_THRESHOLD && currentDepth === 'L1') {
      // Поверхностный ответ на L1 — переходим на L2
      reachedDepth = 'L1';
      nextDepth = 'L2';
    } else if (depthScore < this.L2_THRESHOLD && currentDepth === 'L2') {
      // Поверхностный ответ на L2 — переходим на L3
      reachedDepth = 'L2';
      nextDepth = 'L3';
    } else if (depthScore >= this.L3_THRESHOLD && currentDepth === 'L2') {
      // Глубокий ответ на L2 — фиксируем как L2, переходим
      reachedDepth = 'L2';
      nextDepth = null;
    } else if (currentDepth === 'L3') {
      // Story 2.4: L3 — фиксируем максимальную глубину, без повторных вопросов
      // Даже при поверхностном L3-ответе — сохраняем depthReached: 'L3' и переходим
      reachedDepth = 'L3';
      nextDepth = null;
    } else {
      // Fallback — фиксируем текущий уровень
      reachedDepth = currentDepth;
      nextDepth = null;
    }

    // Обновляем depthReached в ответе
    session.answers[subsectionKey].depthReached = reachedDepth;

    // Story 2.4: maxDepthReached — всегда максимальная достигнутая глубина
    // (только возрастает, никогда не убывает)
    const prevMax = session.answers[subsectionKey].maxDepthReached;
    const depthRank = { 'L0': 0, 'L1': 1, 'L2': 2, 'L3': 3 };
    if (!prevMax || (depthRank[reachedDepth] || 0) > (depthRank[prevMax] || 0)) {
      session.answers[subsectionKey].maxDepthReached = reachedDepth;
    }

    // Собираем риски из ответа (с указанием уровня глубины)
    // Story 2.5: используем _collectRisks для расширенного сбора
    const detectedRisks = this._collectRisks(answer, session, subsectionKey, currentDepth);
    if (detectedRisks.length > 0) {
      if (!session.risks) session.risks = [];
      session.risks.push(...detectedRisks);
    }

    // 4. Определяем следующие шаги
    let question = null;
    let action = 'next_question';

    if (nextDepth) {
      // Переход на следующий уровень глубины
      session.template.depth = nextDepth;

      if (nextDepth === 'L2') {
        // Story 2.3: L2 question formatting with context adaptation
        question = this._formatL2Question(subsectionKey, answer);
      } else if (nextDepth === 'L3') {
        // Story 2.4: L3 question formatting with full dialogue context
        // Передаём полный контекст диалога (L1 + L2 ответы) для контекстной привязки
        const fullContext = session.answers && session.answers[subsectionKey]
          ? { L1: session.answers[subsectionKey].L1, L2: session.answers[subsectionKey].L2 }
          : { L1: answer, L2: undefined };
        question = this._formatL3Question(subsectionKey, fullContext);
      } else {
        // Получаем вопрос для следующего уровня
        try {
          question = this.templateEngine.getQuestion(subsectionKey, nextDepth);
        } catch (err) {
          this.logger.warn('Failed to get question for next depth', {
            subsection: subsectionKey,
            depth: nextDepth,
            error: err.message
          });
          // Fallback: переходим к следующему подразделу
          nextDepth = null;
        }
      }
    }

    if (!nextDepth) {
      // Переход к следующему подразделу
      const nextSub = this.templateEngine.getNextSubsection(currentBlock, subsectionKey);

      if (nextSub) {
        // Определяем номер блока из ID подраздела (напр. '2.1' → 2)
        const nextBlockNum = parseInt(nextSub.id.split('.')[0], 10);

        // Story 2.5: При входе в Блок 7 показываем сводку собранных рисков
        const enteringBlock7 = nextBlockNum === 7 && currentBlock !== 7;
        let riskSummary = null;
        if (enteringBlock7) {
          riskSummary = this._buildBlock7RiskSummary(session);
          this.logger.info('Entering Block 7 — risk summary shown', {
            sessionId: session.sessionId,
            risksCollected: (session.risks || []).length
          });
        }

        // Есть следующий подраздел
        session.template.subsection = nextSub.id;
        session.template.block = nextBlockNum;
        session.template.depth = 'L1';

        try {
          let templateQuestion = this.templateEngine.getQuestion(nextSub.id, 'L1');

          // ===== Story 5.3: Gap-aware questioning for known gaps =====
          if (session._userContext && session._userContext.hasHistory) {
            const isGap = session._userContext.frequentGaps.includes(nextSub.id);
            if (isGap && this.learningEngine) {
              const gapContext = {
                hasHistory: true,
                frequentGaps: session._userContext.frequentGaps || [],
                pastProjectThemes: session._userContext.pastProjectThemes || [],
                depthDistributionByBlock: session._userContext.depthDistributionByBlock || {}
              };
              templateQuestion = this.learningEngine.getGapAwareQuestion(
                nextSub.id,
                gapContext,
                templateQuestion
              );
              this.logger.debug('Gap-aware question applied', {
                sessionId: session.sessionId,
                subsection: nextSub.id
              });
            }
          }

          // Story 2.5: Если входим в Блок 7 — предваряем вопрос сводкой рисков
          if (riskSummary) {
            question = riskSummary + '\n\n' + templateQuestion;
          } else {
            question = templateQuestion;
          }
        } catch (err) {
          this.logger.error('Failed to get L1 question for next subsection', {
            subsection: nextSub.id,
            error: err.message
          });
          if (riskSummary) {
            question = riskSummary + '\n\nРасскажите подробнее о данном разделе.';
          } else {
            question = 'Расскажите подробнее о данном разделе.';
          }
        }
      } else {
        // Все подразделы завершены — опрос окончен
        action = 'survey_complete';
        session.template.block = currentBlock;
        session.template.depth = 'L1';
        question = null;
      }
    }

    // Обновляем timestamp
    session.updatedAt = new Date().toISOString();

    // 5. Сохраняем сессию транзакционно
    try {
      session = await this._saveSessionSafe(session);
    } catch (err) {
      this.logger.error('Failed to save session on processAnswer', {
        sessionId: session.sessionId,
        error: err.message,
        answerLength: answer.length
      });

      // Кэшируем ошибку для повторной попытки
      this._fsErrorCache.set(session.sessionId, {
        session,
        lastError: err.message,
        retries: 1
      });

      action = 'error';
      question = '⚠️ Не удалось сохранить ответ. Попробуйте позже.';
    }

    const progress = this.getProgress(session);

    this.logger.debug('Answer processed', {
      sessionId: session.sessionId,
      subsection: subsectionKey,
      depth: currentDepth,
      score: depthScore,
      nextDepth,
      action
    });

    return {
      question,
      progress,
      session,
      action
    };
  }

  /**
   * Возвращает текущий вопрос для пользователя с полной структурой UX-компонентов.
   *
   * Story 2.7 — Conversational UX components:
   *   - Progress Badge: "📋 Прогресс: Блок 1/7 · Раздел 1.2 · 15%"
   *   - Depth Indicator: "🔍 Уровень: L1 → L2"
   *   - Reflection Message: "💡 Вы сказали: [цитата]. Я правильно понял?"
   *   - Risk Warning: "⚠️ Замечено рисков: 2"
   *   - Action Buttons: ["✅ Подтвердить", "🔄 Уточнить", "↩️ Назад"]
   *   - assembledMessage: предассемблированная строка
   *
   * @param {object} session
   * @param {object} [options]
   * @param {string} [options.nextDepth] — следующий уровень глубины (для Depth Indicator)
   * @param {boolean} [options.showReflection] — показать Reflection вместо question
   * @param {boolean} [options.canBack] — доступна кнопка "Назад"
   * @param {boolean} [options.canConfirm] — доступна кнопка "Подтвердить"
   * @param {boolean} [options.canCorrect] — доступна кнопка "Уточнить"
   * @returns {{ question: string, depth: string, subsectionId: string,
   *            subsectionName: string, blockId: number, components: object,
   *            assembledMessage: string }}
   */
  getCurrentQuestion(session, options = {}) {
    if (!this.templateEngine || !session || !session.template) {
      return null;
    }

    const subKey = session.template.subsection;
    const depth = session.template.depth || 'L1';

    try {
      const question = this.templateEngine.getQuestion(subKey, depth);
      const sub = this.templateEngine.getSubsection(
        session.template.block,
        subKey
      );

      const subsectionName = sub ? sub.name : '';
      const blockId = session.template.block;

      // === Build UX Components ===

      // 1. Progress Badge
      const progressBadge = this.buildProgressBadge(session);

      // 2. Depth Indicator (if transitioning to next depth level)
      const depthIndicator = options.nextDepth
        ? this.buildDepthIndicator(depth, options.nextDepth)
        : null;

      // 3. Reflection Message (after deep L1 answer)
      let reflection = null;
      if (options.showReflection && session.reflectionAnswer) {
        const text = this.buildReflection(session.reflectionAnswer);
        reflection = {
          text,
          type: 'pending'
        };
      }

      // 4. Risk Warning (if risks collected)
      const riskWarning = this.buildRiskWarning(session);

      // 5. Action Buttons
      const actionButtons = this.buildActionButtons({
        canBack: options.canBack || false,
        canConfirm: options.canConfirm || false,
        canCorrect: options.canCorrect || false
      });

      const components = {
        progressBadge,
        depthIndicator,
        reflection,
        question,
        riskWarning,
        actionButtons
      };

      // 6. Assemble full message text
      const assembledMessage = this.assembleMessage(components);

      return {
        // Legacy fields (backward compatible)
        question,
        depth,
        subsectionId: subKey,
        subsectionName,
        blockId,

        // === NEW: UX Component Structure (Story 2.7) ===
        components,
        assembledMessage
      };
    } catch (err) {
      this.logger.warn('Failed to get current question', {
        subsection: subKey,
        depth,
        error: err.message
      });
      const fallback = 'Расскажите подробнее по текущему разделу.';
      return {
        question: fallback,
        depth,
        subsectionId: subKey,
        subsectionName: '',
        blockId: session.template.block,
        components: null,
        assembledMessage: fallback
      };
    }
  }

  // ==================== UX Component Builders (Story 2.7) ====================

  /**
   * Строит Progress Badge — индикатор прогресса опроса.
   *
   * Story 2.7: "📋 Прогресс: Блок 1/7 · Раздел 1.2 · 15%"
   *
   * Формат:
   *   "📋 Прогресс: Блок X/7 · Название блока · YY%"
   *   если название подраздела доступно:
   *   "📋 Прогресс: Блок X/7 · Подраздел X.Y · 15%"
   *
   * @param {object} session — объект сессии
   * @returns {string} строка Progress Badge
   */
  buildProgressBadge(session) {
    const progress = this.getProgress(session);

    let blockName = '';
    try {
      const block = this.templateEngine.getBlock(progress.block);
      if (block && block.name) {
        blockName = block.name;
      }
    } catch { /* ignore */ }

    // Показываем и название блока, и процент
    const blockStr = blockName
      ? `Блок ${progress.block}/${progress.totalBlocks} · ${blockName}`
      : `Блок ${progress.block}/${progress.totalBlocks}`;

    return `📋 Прогресс: ${blockStr} · ${progress.percent}%`;
  }

  /**
   * Строит Depth Indicator — индикатор перехода на следующий уровень глубины.
   *
   * Story 2.7: "🔍 Уровень: L1 → L2"
   *
   * Показывается только при переходе между уровнями глубины (L1→L2, L2→L3),
   * не показывается при стационарном уровне.
   *
   * @param {string} currentDepth — текущий уровень ('L1', 'L2', 'L3')
   * @param {string} nextDepth — следующий уровень ('L2', 'L3')
   * @returns {string|null} строка Depth Indicator или null
   */
  buildDepthIndicator(currentDepth, nextDepth) {
    if (!currentDepth || !nextDepth) {
      return null;
    }

    // Не показываем индикатор на стационарном уровне
    if (currentDepth === nextDepth) {
      return null;
    }

    return `🔍 Уровень: ${currentDepth} → ${nextDepth}`;
  }

  /**
   * Строит массив Action Buttons — кнопки для inline keyboard.
   *
   * Story 2.7: "✅ Подтвердить / 🔄 Уточнить / ↩️ Назад"
   *
   * @param {object} flags
   * @param {boolean} flags.canBack — показать кнопку "↩️ Назад"
   * @param {boolean} flags.canConfirm — показать кнопку "✅ Подтвердить"
   * @param {boolean} flags.canCorrect — показать кнопку "🔄 Уточнить"
   * @returns {string[]} массив строк-кнопок
   */
  buildActionButtons({ canBack, canConfirm, canCorrect } = {}) {
    const buttons = [];

    if (canConfirm) {
      buttons.push('✅ Подтвердить');
    }
    if (canCorrect) {
      buttons.push('🔄 Уточнить');
    }
    if (canBack) {
      buttons.push('↩️ Назад');
    }

    // Всегда показываем хотя бы "Назад"
    return buttons.length > 0 ? buttons : ['↩️ Назад'];
  }

  /**
   * Строит Risk Warning — предупреждение о количестве собранных рисков.
   *
   * Story 2.7: "⚠️ Замечено рисков: 2"
   *
   * Показывается только если есть собранные риски (session.risks.length > 0).
   *
   * @param {object} session — объект сессии
   * @returns {string|null} строка Risk Warning или null
   */
  buildRiskWarning(session) {
    if (!session || !session.risks || session.risks.length === 0) {
      return null;
    }

    const count = session.risks.length;
    const word = count === 1 ? 'риск' : 'рисков';
    return `⚠️ Замечено ${word}: ${count}`;
  }

  /**
   * Собирает все UX-компоненты в единое отформатированное сообщение.
   *
   * Story 2.7 — финальная ассемблированная строка:
   *
   *   📋 Прогресс: Блок X/7 · Название · XX%
   *   ⚠️ Замечено рисков: N          (если есть)
   *   🔍 Уровень: L1 → L2            (если переход)
   *
   *   [Осмысленный текст/вопрос]
   *
   *   ✅ Подтвердить    🔄 Уточнить    ↩️ Назад
   *
   * Каждое сообщение ≤ 3 предложений, ≤ 400 символов.
   * Эмодзи — не более 1 на строку, не ключевой для смысла.
   *
   * @param {object} components
   * @param {string} components.progressBadge — строка Progress Badge
   * @param {string|null} components.depthIndicator — строка Depth Indicator или null
   * @param {object|null} components.reflection — объект рефлексии { text, type } или null
   * @param {string} components.question — текст вопроса
   * @param {string|null} components.riskWarning — строка Risk Warning или null
   * @param {string[]} components.actionButtons — массив кнопок
   * @returns {string} финальное сообщение для отправки пользователю
   */
  assembleMessage(components) {
    if (!components) {
      return '';
    }

    const lines = [];

    // 1. Progress Badge — всегда первая строка
    if (components.progressBadge) {
      lines.push(components.progressBadge);
    }

    // 2. Risk Warning — сразу после прогресса (если есть)
    if (components.riskWarning) {
      lines.push(components.riskWarning);
    }

    // 3. Depth Indicator — при переходе
    if (components.depthIndicator) {
      lines.push(components.depthIndicator);
    }

    // Пустая строка перед основным контентом
    lines.push('');

    // 4. Основной контент: Reflection или Question
    if (components.reflection && components.reflection.text) {
      // Reflection Message — "💡 Вы сказали: ... Я правильно понял?"
      lines.push(components.reflection.text);
    } else if (components.question) {
      lines.push(components.question);
    }

    // Пустая строка перед кнопками
    lines.push('');

    // 5. Action Buttons — в виде текстовой строки (для отладки/логов)
    // В реальном Telegram-сообщении они будут переданы как inline_keyboard,
    // но для ассемблированной строки показываем через разделитель
    if (components.actionButtons && components.actionButtons.length > 0) {
      lines.push(components.actionButtons.join('  '));
    }

    // Собираем строку
    const message = lines.join('\n');

    // Ограничение длины: ≤ 400 символов (из UX Spec)
    if (message.length > 400) {
      this.logger.debug('assembledMessage truncated to 400 chars', {
        originalLength: message.length
      });
      return message.slice(0, 397) + '…';
    }

    return message;
  }

  /**
   * Возвращает прогресс опроса.
   *
   * @param {object} session
   * @returns {{ block: number, totalBlocks: number, subsection: string,
   *            depth: string, completedSubsections: number,
   *            totalSubsections: number, percent: number }}
   */
  getProgress(session) {
    if (!this.templateEngine) {
      return {
        block: 1,
        totalBlocks: 7,
        subsection: '1.1',
        depth: 'L1',
        completedSubsections: 0,
        totalSubsections: 1,
        percent: 0
      };
    }

    const totalBlocks = this.templateEngine.getBlockCount();
    const currentBlock = session.template ? session.template.block : 1;
    const currentSub = session.template ? session.template.subsection : '1.1';
    const currentDepth = session.template ? session.template.depth : 'L1';

    // Считаем общее количество подразделов и завершённых
    let totalSubsections = 0;
    let completedSubsections = 0;

    try {
      for (let b = 1; b <= totalBlocks; b++) {
        const block = this.templateEngine.getBlock(b);
        if (block && block.subsections) {
          for (const sub of block.subsections) {
            totalSubsections++;
            // Подраздел считается завершённым, если есть ответ с depthReached
            if (session.answers && session.answers[sub.id] && session.answers[sub.id].depthReached) {
              completedSubsections++;
            }
          }
        }
      }
    } catch (err) {
      this.logger.warn('Failed to calculate progress', { error: err.message });
    }

    const percent = totalSubsections > 0
      ? Math.round((completedSubsections / totalSubsections) * 100)
      : 0;

    // Собираем статистику по рискам (Story 2.5)
    const risks = session.risks || [];
    const risksByCategory = {};
    for (const risk of risks) {
      const cat = risk.category || 'uncategorized';
      if (!risksByCategory[cat]) risksByCategory[cat] = 0;
      risksByCategory[cat]++;
    }

    return {
      block: currentBlock,
      totalBlocks,
      subsection: currentSub,
      depth: currentDepth,
      completedSubsections,
      totalSubsections,
      percent,
      risksCollected: risks.length,
      risksByCategory
    };
  }

  /**
   * Формирует Session Resume Card для пользователя после паузы >30 минут.
   *
   * @param {object} session
   * @returns {{ text: string, lastAnswer: string|null, blockInfo: string }}
   */
  buildResumeCard(session) {
    if (!session) return null;

    const progress = this.getProgress(session);

    // Определяем название блока
    let blockName = `Блок ${progress.block}`;
    try {
      if (this.templateEngine) {
        const block = this.templateEngine.getBlock(progress.block);
        if (block && block.name) {
          blockName = block.name;
        }
      }
    } catch { /* ignore */ }

    // Последний ответ пользователя
    const lastAnswer = this._getLastAnswerText(session);

    // Определяем последний подраздел с ответом
    const answeredSubsections = session.answers
      ? Object.keys(session.answers).filter(k => session.answers[k].depthReached)
      : [];

    const lastAnsweredKey = answeredSubsections.length > 0
      ? answeredSubsections[answeredSubsections.length - 1]
      : null;

    let lastAnswerText = null;
    if (lastAnsweredKey && session.answers[lastAnsweredKey]) {
      const depths = ['L3', 'L2', 'L1'];
      for (const d of depths) {
        if (session.answers[lastAnsweredKey][d]) {
          lastAnswerText = session.answers[lastAnsweredKey][d];
          break;
        }
      }
    }

    // Обрезаем до 150 символов
    if (lastAnswerText && lastAnswerText.length > 150) {
      lastAnswerText = lastAnswerText.slice(0, 150) + '…';
    }

    const text =
      '🔄 *С возвращением!*\n\n' +
      `📋 Вы остановились на разделе *«${blockName}»* (подраздел ${progress.subsection})\n` +
      `📊 Прогресс: ${progress.percent}% (${progress.completedSubsections} из ${progress.totalSubsections} подразделов)\n\n` +
      (lastAnswerText
        ? `📝 *Ваш последний ответ:*\n_${lastAnswerText}_\n\n`
        : '') +
      '▶️ *Продолжим с того же места?* Просто напишите ответ на текущий вопрос.';

    return {
      text,
      lastAnswer: lastAnswerText,
      blockInfo: `Блок ${progress.block}: ${blockName} (подраздел ${progress.subsection})`
    };
  }

  /**
   * Проверяет, требуется ли Session Resume Card.
   * Если с момента последнего обновления сессии прошло >30 минут.
   *
   * @param {object} session
   * @returns {boolean}
   */
  needsResumeCard(session) {
    if (!session || !session.updatedAt) return false;

    const updatedAt = new Date(session.updatedAt);
    const now = new Date();
    const diffMs = now.getTime() - updatedAt.getTime();
    const diffMinutes = diffMs / (1000 * 60);

    return diffMinutes > 30;
  }

  /**
   * Повторяет сохранение сессий, которые не удалось сохранить из-за ошибки ФС.
   * Вызывается периодически или при следующем ответе пользователя.
   *
   * @param {string} sessionId
   * @returns {Promise<object|null>} — сохранённая сессия или null
   */
  async retryFailedSave(sessionId) {
    if (!this._fsErrorCache.has(sessionId)) return null;

    const entry = this._fsErrorCache.get(sessionId);
    if (entry.retries >= this.MAX_FS_RETRIES) {
      this.logger.error('Max FS retries exhausted', { sessionId });
      this._fsErrorCache.delete(sessionId);
      return null;
    }

    try {
      const saved = await this._saveSessionSafe(entry.session);
      this._fsErrorCache.delete(sessionId);
      this.logger.info('FS retry successful', { sessionId, retries: entry.retries });
      return saved;
    } catch (err) {
      entry.retries++;
      entry.lastError = err.message;
      this.logger.warn('FS retry failed', {
        sessionId,
        retry: entry.retries,
        error: err.message
      });
      return null;
    }
  }

  // ==================== Story 2.6: Return to Earlier Blocks ====================

  /**
   * Возвращает к указанному блоку для уточнения.
   * Все существующие ответы сохраняются — пользователь может дополнить/исправить.
   * Устанавливает позицию на первый подраздел указанного блока.
   *
   * Story 2.6: FR11 — возврат к ранее пройденным блокам.
   *
   * @param {object} session — объект сессии
   * @param {number} blockNum — номер блока (1-7)
   * @returns {Promise<{ question: string, progress: object, session: object,
   *    previousAnswers: object|null, blockName: string, confirmationText: string }>}
   * @throws {Error} если блок не существует
   */
  async returnToBlock(session, blockNum) {
    if (!session || !session.sessionId) {
      throw new Error('SurveyEngine: требуется валидная сессия для returnToBlock');
    }

    if (!this.templateEngine) {
      throw new Error('SurveyEngine: TemplateEngine не подключён');
    }

    const totalBlocks = this.templateEngine.getBlockCount();
    if (blockNum < 1 || blockNum > totalBlocks) {
      throw new Error(
        `SurveyEngine: блок ${blockNum} не найден. Допустимы 1-${totalBlocks}.`
      );
    }

    // Валидируем, что блок существует
    const block = this.templateEngine.getBlock(blockNum);
    if (!block || !block.subsections || block.subsections.length === 0) {
      throw new Error(`SurveyEngine: блок ${blockNum} не содержит подразделов`);
    }

    // Получаем первый подраздел блока
    const firstSub = block.subsections[0];
    const subId = firstSub.id;

    // Собираем все существующие ответы по этому блоку
    const previousAnswers = {};
    let previousAnswerText = null;
    for (const sub of block.subsections) {
      const ans = session.answers && session.answers[sub.id];
      if (ans) {
        const text = ans.L3 || ans.L2 || ans.L1 || null;
        if (text) {
          previousAnswers[sub.id] = {
            text,
            depthReached: ans.depthReached || null,
            subsectionName: sub.name
          };
          if (!previousAnswerText) {
            previousAnswerText = text;
          }
        }
      }
    }

    // Строим контекстное подтверждение (Story 2.6 AC)
    const confirmationText = this._buildReturnToBlockConfirmation(
      blockNum,
      block.name,
      previousAnswers
    );

    // Устанавливаем позицию на первый подраздел блока
    session.template.block = blockNum;
    session.template.subsection = subId;
    session.template.depth = 'L1';
    session.updatedAt = new Date().toISOString();

    // Сбрасываем reflection pending
    session.reflectionPending = false;
    session.reflectionSubsection = null;
    session.reflectionAnswer = null;

    // Сохраняем сессию
    try {
      session = await this._saveSessionSafe(session);
    } catch (err) {
      this.logger.error('Failed to save session on returnToBlock', {
        sessionId: session.sessionId,
        blockNum,
        error: err.message
      });
    }

    // Получаем L1-вопрос первого подраздела
    let question;
    try {
      question = this.templateEngine.getQuestion(subId, 'L1');
    } catch (err) {
      question = `Расскажите подробнее о разделе «${block.name}».`;
    }

    this.logger.info('Navigation: return to block', {
      sessionId: session.sessionId,
      blockNum,
      subsection: subId,
      previousAnswersCount: Object.keys(previousAnswers).length
    });

    return {
      question,
      progress: this.getProgress(session),
      session,
      previousAnswers: Object.keys(previousAnswers).length > 0 ? previousAnswers : null,
      blockName: block.name,
      confirmationText
    };
  }

  /**
   * Строит контекстное сообщение для подтверждения возврата к блоку.
   * Формат: "Вернуться к блоку N? Вы там говорили про..."
   *
   * @param {number} blockNum
   * @param {string} blockName
   * @param {object} previousAnswers — { subId: { text, depthReached, subsectionName } }
   * @returns {string}
   * @private
   */
  _buildReturnToBlockConfirmation(blockNum, blockName, previousAnswers) {
    let text = `⬅️ *Вернуться к блоку ${blockNum}* — _${blockName}_?\n\n`;

    const entries = Object.entries(previousAnswers);
    if (entries.length > 0) {
      // Берём первый ответ для контекстной привязки
      const firstEntry = entries[0];
      const snippet = firstEntry[1].text;
      const truncated = snippet.length > 120
        ? snippet.slice(0, 117) + '…'
        : snippet;
      text += `💭 *Вы говорили:* _${truncated}_\n\n`;

      if (entries.length > 1) {
        text += `📋 Заполнено подразделов в этом блоке: ${entries.length}\n`;
      }
    } else {
      text += 'Вы ещё не заполняли этот блок.\n';
    }

    text += '\nХотите что-то уточнить или дополнить?';

    return text;
  }

  /**
   * Возврат к предыдущему подразделу (/back).
   * Анализирует историю ответов и возвращается к предыдущему
   * подразделу с сохранением контекста.
   *
   * Story 2.6: FR11 — возврат к предыдущему подразделу.
   *
   * @param {object} session — объект сессии
   * @returns {Promise<{ question: string, progress: object, session: object,
   *    previousAnswer: string|null, previousSubsection: object|null,
   *    confirmationText: string }>}
   */
  async returnToPrevious(session) {
    if (!session || !session.sessionId) {
      throw new Error('SurveyEngine: требуется валидная сессия для returnToPrevious');
    }

    if (!this.templateEngine) {
      throw new Error('SurveyEngine: TemplateEngine не подключён');
    }

    const currentBlock = session.template.block;
    const currentSub = session.template.subsection;

    // Строим полный список всех подразделов в порядке обхода
    const allSubsections = [];
    try {
      const blockCount = this.templateEngine.getBlockCount();
      for (let b = 1; b <= blockCount; b++) {
        const block = this.templateEngine.getBlock(b);
        if (block && block.subsections) {
          for (const sub of block.subsections) {
            allSubsections.push({
              blockId: b,
              blockName: block.name,
              fullKey: sub.id,
              name: sub.name
            });
          }
        }
      }
    } catch {
      throw new Error('SurveyEngine: не удалось загрузить структуру шаблона');
    }

    if (allSubsections.length === 0) {
      throw new Error('SurveyEngine: шаблон не содержит подразделов');
    }

    // Находим индекс текущего подраздела
    const currentIdx = allSubsections.findIndex(s => s.fullKey === currentSub);
    if (currentIdx <= 0) {
      // Уже в начале опроса
      return {
        question: null,
        progress: this.getProgress(session),
        session,
        previousAnswer: null,
        previousSubsection: null,
        confirmationText: '⬅️ Вы уже в начале опроса. Нет предыдущих подразделов для возврата.'
      };
    }

    const prev = allSubsections[currentIdx - 1];

    // Получаем последний ответ по предыдущему подразделу
    let previousAnswer = null;
    if (session.answers && session.answers[prev.fullKey]) {
      const ans = session.answers[prev.fullKey];
      previousAnswer = ans.L3 || ans.L2 || ans.L1 || null;
    }

    // Строим контекстное подтверждение
    let confirmationText = `⬅️ *Вернуться к подразделу ${prev.fullKey}* — _${prev.name}_?`;
    if (previousAnswer) {
      const truncated = previousAnswer.length > 100
        ? previousAnswer.slice(0, 97) + '…'
        : previousAnswer;
      confirmationText += `\n\n💭 *Вы говорили:* _${truncated}_`;
    }
    confirmationText += '\n\nВы уверены?';

    this.logger.info('Navigation: return to previous subsection', {
      sessionId: session.sessionId,
      from: currentSub,
      to: prev.fullKey,
      hasPreviousAnswer: !!previousAnswer
    });

    return {
      question: null, // Устанавливается после подтверждения
      progress: this.getProgress(session),
      session,
      previousAnswer,
      previousSubsection: prev,
      confirmationText
    };
  }

  /**
   * Выполняет фактический возврат к указанному подразделу после подтверждения.
   *
   * @param {object} session
   * @param {object} subsection — { blockId, fullKey, name, blockName }
   * @returns {Promise<{ question: string, progress: object, session: object, previousAnswer: string|null }>}
   */
  async executeReturnToSubsection(session, subsection) {
    if (!session || !subsection) {
      throw new Error('SurveyEngine: требуется сессия и целевой подраздел');
    }

    const subId = subsection.fullKey;
    const blockId = subsection.blockId;

    // Сохраняем предыдущий ответ
    const previousAnswer = session.answers && session.answers[subId]
      ? (session.answers[subId].L3 || session.answers[subId].L2 || session.answers[subId].L1 || null)
      : null;

    // Устанавливаем позицию
    session.template.block = blockId;
    session.template.subsection = subId;
    session.template.depth = 'L1';
    session.updatedAt = new Date().toISOString();
    session.reflectionPending = false;
    session.reflectionSubsection = null;
    session.reflectionAnswer = null;

    // Сохраняем
    try {
      session = await this._saveSessionSafe(session);
    } catch (err) {
      this.logger.error('Failed to save session on executeReturnToSubsection', {
        sessionId: session.sessionId,
        subId,
        error: err.message
      });
    }

    // Форматируем возвратный вопрос
    const question = this._formatReturnQuestion(blockId, subId, previousAnswer);

    return {
      question,
      progress: this.getProgress(session),
      session,
      previousAnswer
    };
  }

  // ==================== Story 2.7: Conversational UX Components ====================

  /**
   * Строит сообщение прогресса с эмодзи и именем блока.
   * Формат: "📋 Прогресс: Блок 2/7 · Раздел 2.3"
   * Если progressMessage содержит больше деталей, дополняет.
   *
   * @param {object} progress — объект прогресса из getProgress()
   * @returns {string} — отформатированное сообщение прогресса
   */
  buildProgressMessage(progress) {
    if (!progress) return '';

    let blockName = `Блок ${progress.block}`;
    try {
      if (this.templateEngine) {
        const block = this.templateEngine.getBlock(progress.block);
        if (block && block.name) {
          blockName = block.name;
        }
      }
    } catch { /* ignore */ }

    const filled = Math.round((progress.completedSubsections / Math.max(progress.totalSubsections, 1)) * 10);
    const empty = 10 - filled;
    const bar = '█'.repeat(filled) + '░'.repeat(empty);

    let text = `📋 *Прогресс:* ${bar} ${progress.percent}%`;
    text += ` · *${blockName}* (Раздел ${progress.subsection})`;

    if (progress.risksCollected > 0) {
      text += ` · ⚠️ ${progress.risksCollected}`;
    }

    return text;
  }

  /**
   * Строит сообщение-рефлексию с контекстной привязкой.
   * Формат: "💭 Вы упомянули [topic]..."
   * Извлекает ключевую тему из ответа пользователя и строит
   * рефлексивное сообщение с перекрёстной ссылкой на предыдущие темы.
   *
   * @param {string} answer — текст ответа пользователя
   * @param {object} [allAnswers] — все ответы сессии (для перекрёстной рефлексии)
   * @param {object} [options]
   * @param {boolean} [options.short=false] — короткая форма (без цитаты)
   * @returns {string|null} — отформатированное сообщение рефлексии или null
   */
  buildReflection(answer, allAnswers, options = {}) {
    if (!answer || answer.trim().length < 5) return null;

    const keyPhrase = this._extractKeyPhrase(answer);

    // Перекрёстная рефлексия: ищем связанные темы в предыдущих ответах
    let crossReference = null;
    if (allAnswers && typeof allAnswers === 'object' && keyPhrase) {
      const keyWords = keyPhrase.toLowerCase().split(/\s+/).filter(w => w.length > 3);
      if (keyWords.length > 0) {
        const answeredKeys = Object.keys(allAnswers);
        for (const subKey of answeredKeys) {
          const ans = allAnswers[subKey];
          if (!ans) continue;
          for (const depth of ['L3', 'L2', 'L1']) {
            const text = ans[depth];
            if (!text || text === answer) continue; // пропускаем текущий ответ
            const hasMatch = keyWords.some(w => text.toLowerCase().includes(w));
            if (hasMatch) {
              const snippet = text.length > 60
                ? text.slice(0, 57) + '…'
                : text;
              crossReference = `Вы уже упоминали похожую тему в разделе ${subKey}: _${snippet}_`;
              break;
            }
          }
          if (crossReference) break;
        }
      }
    }

    // Строим сообщение рефлексии
    let message;
    if (keyPhrase) {
      if (options.short) {
        message = `💭 Упомянуто: ${keyPhrase}`;
      } else {
        message = `💭 Вы упомянули *«${keyPhrase}»*.`;
      }
    } else {
      // Берём первую фразу ответа
      const sentences = answer.split(/[.!?]+/).filter(s => s.trim().length > 0);
      const firstSentence = sentences[0] ? sentences[0].trim() : '';
      if (firstSentence.length > 0) {
        const snippet = firstSentence.length > 80
          ? firstSentence.slice(0, 77) + '…'
          : firstSentence;
        message = `💭 Вы сказали: _${snippet}_`;
      } else {
        return null;
      }
    }

    // Добавляем перекрёстную ссылку, если есть
    if (crossReference) {
      message += `\n\n🔗 ${crossReference}`;
    }

    return message;
  }

  /**
   * Форматирует вопрос с учётом глубины, контекста и прогресса.
   * Строит полное сообщение с прогрессом, индикатором глубины и вопросом.
   *
   * Story 2.7: Question formatting — консистентный формат для всех уровней.
   *
   * @param {string} question — текст вопроса из шаблона
   * @param {string} depth — уровень глубины ('L1', 'L2', 'L3')
   * @param {object} [context] — дополнительный контекст
   * @param {object} [context.progress] — объект прогресса для включения в сообщение
   * @param {string} [context.previousAnswer] — предыдущий ответ (для L2/L3 привязки)
   * @returns {string} — полное отформатированное сообщение
   */
  buildQuestion(question, depth, context = {}) {
    if (!question) return '';

    const parts = [];

    // 1. Индикатор глубины для L2 и L3
    if (depth === 'L2') {
      parts.push('🔍 *Давайте уточним:*');
    } else if (depth === 'L3') {
      parts.push('🔍 *Попробуем добраться до сути:*');
    } else {
      parts.push('💬');
    }

    // 2. Контекстная привязка для L2/L3
    if ((depth === 'L2' || depth === 'L3') && context.previousAnswer) {
      const keyPhrase = this._extractKeyPhrase(context.previousAnswer);
      if (keyPhrase) {
        parts.push(`Вы упомянули *«${keyPhrase}»*:`);
      }
    }

    // 3. Сам вопрос
    parts.push(question);

    return parts.join('\n\n');
  }

  /**
   * Строит сообщение обратной связи о качестве ответа.
   * Формат: "💡 Качество: хороший ответ" с рекомендациями по улучшению.
   *
   * Story 2.7: Quality Feedback — ненавязчивая обратная связь без оценок.
   *
   * @param {string} answer — текст ответа пользователя
   * @param {number} score — оценка глубины от 0 до 1
   * @returns {string|null} — сообщение обратной связи или null
   */
  buildQualityFeedback(answer, score) {
    if (!answer || score === undefined || score === null) return null;

    // Без оценок — только рекомендации (UX Spec: «терапевт», без оценочных суждений)
    const sentences = answer.split(/[.!?]+/).filter(s => s.trim().length > 0).length;
    const hasNumbers = /\d+/.test(answer);

    if (score >= 0.6) {
      // Отличный ответ — нейтральное подтверждение
      return '💡 Спасибо, отличный развёрнутый ответ. Зафиксировал.';
    }

    if (score >= 0.3) {
      // Хороший ответ, но можно глубже
      const suggestions = [];
      if (!hasNumbers) {
        suggestions.push('добавить цифры или метрики');
      }
      if (sentences < 4) {
        suggestions.push('описать подробнее');
      }

      if (suggestions.length > 0) {
        return `💡 Хороший ответ. Для полноты картины можно ${suggestions.join(' и ')}.`;
      }
      return '💡 Спасибо, зафиксировал ответ.';
    }

    // Поверхностный ответ — мягкий намёк на уточнение
    return '💡 Зафиксировал. Если захотите что-то добавить — просто напишите.';
  }

  /**
   * Строит Session Resume Card для восстановления сессии.
   * Улучшенная версия с детализацией последних активностей,
   * поддержкой нескольких блоков и короткой рефлексией.
   *
   * Story 2.7: Session Resume Card — бесшовное восстановление.
   *
   * @param {object} session — объект сессии
   * @returns {{ text: string, lastAnswer: string|null, blockInfo: string, progressMessage: string }}
   */
  buildSessionResumeCard(session) {
    if (!session) {
      return {
        text: '',
        lastAnswer: null,
        blockInfo: '',
        progressMessage: ''
      };
    }

    const progress = this.getProgress(session);
    const progressMsg = this.buildProgressMessage(progress);

    // Определяем название блока
    let blockName = `Блок ${progress.block}`;
    try {
      if (this.templateEngine) {
        const block = this.templateEngine.getBlock(progress.block);
        if (block && block.name) {
          blockName = block.name;
        }
      }
    } catch { /* ignore */ }

    // Последний ответ пользователя
    const lastAnswerText = this._getLastAnswerText(session);
    let lastAnswerSnippet = null;
    if (lastAnswerText) {
      lastAnswerSnippet = lastAnswerText.length > 150
        ? lastAnswerText.slice(0, 147) + '…'
        : lastAnswerText;
    }

    // Определяем последний завершённый подраздел
    const answeredSubsections = session.answers
      ? Object.keys(session.answers).filter(k => session.answers[k].depthReached)
      : [];
    const lastAnsweredKey = answeredSubsections.length > 0
      ? answeredSubsections[answeredSubsections.length - 1]
      : null;

    let lastSubName = '';
    if (lastAnsweredKey && this.templateEngine) {
      try {
        const part = lastAnsweredKey.split('.');
        const blockObj = this.templateEngine.getBlock(parseInt(part[0], 10));
        if (blockObj) {
          for (const sub of blockObj.subsections) {
            if (sub.id === lastAnsweredKey) {
              lastSubName = sub.name;
              break;
            }
          }
        }
      } catch { /* ignore */ }
    }

    // Строим текстовое сообщение
    const parts = [];
    parts.push(`🔄 *С возвращением!*`);
    parts.push('');

    // Прогресс
    parts.push(progressMsg);
    parts.push('');

    // Детальная информация о блоке
    parts.push(`📍 Вы работали над разделом *«${blockName}»* (${progress.subsection})`);

    if (lastAnsweredKey && lastSubName) {
      parts.push(`✅ Последний завершённый: _${lastSubName}_ (${lastAnsweredKey})`);
    }

    parts.push(`📊 Заполнено: ${progress.completedSubsections} из ${progress.totalSubsections} подразделов`);
    parts.push('');

    // Последний ответ
    if (lastAnswerSnippet) {
      parts.push(`📝 *Ваш последний ответ:*`);
      parts.push(`_${lastAnswerSnippet}_`);
      parts.push('');
    }

    // Призыв к действию
    parts.push('▶️ *Продолжим с того же места?* Просто напишите ответ на текущий вопрос.');

    const text = parts.join('\n');

    return {
      text,
      lastAnswer: lastAnswerSnippet,
      blockInfo: `Блок ${progress.block}: ${blockName} (${progress.subsection})`,
      progressMessage: progressMsg
    };
  }

  // ==================== Navigation & Depth Formatting (Story 2.3, Story 2.6) ====================

  /**
   * Возвращает к указанному разделу для уточнения.
   * Story 2.3 / Story 2.6: returnToSection — навигация назад по блокам/подразделам (FR11).
   *
   * Используется:
   *   - При команде пользователя /back
   *   - При возврате контролёра к недоработанному разделу
   *
   * Метод устанавливает текущую позицию опроса на указанный подраздел,
   * не удаляя существующие ответы. Возвращает L1-вопрос для этого подраздела
   * с контекстом "ранее вы ответили: ...".
   *
   * Story 2.6 enhancements:
   *   - Сохраняет origin-позицию (откуда вернулись) для последующего продолжения
   *   - Показывает предыдущий ответ с пометкой "ранее вы ответили"
   *   - Восстанавливает полное состояние сессии через Session Context
   *   - Не удаляет уже собранные ответы (только перезаписывает при уточнении)
   *
   * @param {object} session — объект сессии
   * @param {number} blockId — номер блока (1-7)
   * @param {string} subId — идентификатор подраздела ('1.1', '2.3')
   * @param {object} [options]
   * @param {boolean} [options.isUserBack=false] — true если вызов из команды /back
   * @param {string} [options.reason] — причина возврата (для контролёра)
   * @returns {Promise<{ question: string, progress: object, session: object, previousAnswer: string|null }>}
   * @throws {Error} если блок или подраздел не существует
   */
  async returnToSection(session, blockId, subId, options = {}) {
    if (!session || !session.sessionId) {
      throw new Error('SurveyEngine: требуется валидная сессия для returnToSection');
    }

    if (!this.templateEngine) {
      throw new Error('SurveyEngine: TemplateEngine не подключён');
    }

    const { isUserBack = false, reason = null } = options;

    // Валидируем, что секция существует
    const block = this.templateEngine.getBlock(blockId);
    if (!block) {
      throw new Error(`SurveyEngine: блок ${blockId} не найден`);
    }

    const subsection = this.templateEngine.getSubsection(blockId, subId);
    if (!subsection) {
      throw new Error(`SurveyEngine: подраздел ${subId} не найден в блоке ${blockId}`);
    }

    // Сохраняем origin-позицию (откуда возвращаемся) для последующего продолжения
    const originBlock = session.template.block;
    const originSub = session.template.subsection;
    const originDepth = session.template.depth;

    // Story 2.6: Сохраняем origin в сессии, чтобы после уточнения продолжить с того же места
    if (!session._returnOrigin) {
      session._returnOrigin = {};
    }
    session._returnOrigin[subId] = {
      block: originBlock,
      subsection: originSub,
      depth: originDepth,
      returnedAt: new Date().toISOString()
    };

    // Сохраняем предыдущий ответ, если был (не удаляем!)
    const previousAnswer = session.answers && session.answers[subId]
      ? (session.answers[subId].L3 || session.answers[subId].L2 || session.answers[subId].L1 || null)
      : null;

    // Устанавливаем позицию на указанный подраздел
    session.template.block = parseInt(blockId.toString().replace('block.', ''), 10);
    session.template.subsection = subId;
    session.template.depth = 'L1';
    session.updatedAt = new Date().toISOString();

    // Сбрасываем reflection pending, если был
    session.reflectionPending = false;
    session.reflectionSubsection = null;
    session.reflectionAnswer = null;

    // Story 2.6: Отмечаем, что это возврат (чтобы processAnswer знал, как обработать уточнение)
    session._returnActive = {
      subsection: subId,
      hadPreviousAnswer: !!previousAnswer
    };

    // Сохраняем сессию
    try {
      session = await this._saveSessionSafe(session);
    } catch (err) {
      this.logger.error('Failed to save session on returnToSection', {
        sessionId: session.sessionId,
        blockId,
        subId,
        error: err.message
      });
    }

    // Получаем L1-вопрос для возврата
    const question = this._formatReturnQuestion(blockId, subId, previousAnswer, { isUserBack, reason });

    this.logger.info('Navigation: return to section', {
      sessionId: session.sessionId,
      blockId,
      subId,
      hadPreviousAnswer: !!previousAnswer,
      isUserBack,
      originBlock,
      originSub,
      hasReason: !!reason
    });

    return {
      question,
      progress: this.getProgress(session),
      session,
      previousAnswer
    };
  }

  // ==================== Story 2.6: /back Command Handler ====================

  /**
   * Обрабатывает команду /back — возврат к предыдущему подразделу.
   *
   * Story 2.6: Использует returnToSection для навигации на предыдущий подраздел
   * с сохранением контекста и показом последнего ответа с пометкой "ранее вы ответили".
   *
   * Flow:
   *   1. Определяет предыдущий подраздел через TemplateEngine
   *   2. Вызывает returnToSection с isUserBack=true
   *   3. Возвращает отформатированное сообщение и обновлённую сессию
   *
   * @param {object} session — объект сессии
   * @returns {Promise<{ question: string, progress: object, session: object, previousAnswer: string|null }>}
   */
  async handleBackNavigation(session) {
    if (!session || !session.sessionId) {
      throw new Error('SurveyEngine: требуется валидная сессия для handleBackNavigation');
    }

    if (!this.templateEngine) {
      throw new Error('SurveyEngine: TemplateEngine не подключён');
    }

    // Определяем предыдущий подраздел
    const prevSub = this._getPreviousSubsection(session);
    if (!prevSub) {
      this.logger.info('Back navigation: already at start', {
        sessionId: session.sessionId
      });
      return {
        question: null,
        progress: this.getProgress(session),
        session,
        previousAnswer: null,
        atStart: true
      };
    }

    this.logger.debug('Back navigation triggered', {
      sessionId: session.sessionId,
      currentSub: session.template.subsection,
      prevBlockId: prevSub.blockId,
      prevSubId: prevSub.fullKey
    });

    // Используем returnToSection для единой логики навигации
    return await this.returnToSection(session, prevSub.blockId, prevSub.fullKey, {
      isUserBack: true
    });
  }

  // ==================== Story 2.6: Continue After Return ====================

  /**
   * Продолжает опрос после возврата к разделу.
   * Вызывается processAnswer при обнаружении _returnActive в сессии.
   *
   * Story 2.6: После уточнения (возврата к разделу) — переходит к origin-позиции,
   * т.е. к тому подразделу, где остановились до возврата.
   *
   * @param {object} session — объект сессии
   * @param {string} subId — подраздел, к которому был возврат
   * @returns {Promise<{ question: string|null, progress: object, session: object, action: string }>}
   */
  async continueFromReturn(session, subId) {
    if (!session || !session.sessionId) {
      throw new Error('SurveyEngine: требуется валидная сессия для continueFromReturn');
    }

    const origin = session._returnOrigin && session._returnOrigin[subId];

    // Сбрасываем флаги возврата
    session._returnActive = null;
    session.updatedAt = new Date().toISOString();

    // Если origin не найден — просто переходим к следующему подразделу
    if (!origin) {
      this.logger.warn('continueFromReturn: no origin found, going to next subsection', {
        sessionId: session.sessionId,
        returnSub: subId
      });
      const nextSub = this.templateEngine.getNextSubsection(
        session.template.block,
        session.template.subsection
      );
      if (nextSub) {
        session.template.subsection = nextSub.id;
        session.template.block = parseInt(nextSub.id.split('.')[0], 10);
        session.template.depth = 'L1';
      }

      let question = null;
      try {
        question = this.templateEngine.getQuestion(session.template.subsection, 'L1');
      } catch {
        question = 'Расскажите подробнее по текущему разделу.';
      }

      try {
        session = await this._saveSessionSafe(session);
      } catch (err) {
        this.logger.error('Failed to save after continueFromReturn (no origin)', {
          sessionId: session.sessionId, error: err.message
        });
      }

      return {
        question,
        progress: this.getProgress(session),
        session,
        action: 'next_question'
      };
    }

    // Восстанавливаем origin-позицию (откуда вернулись)
    this.logger.info('Continuing from return origin', {
      sessionId: session.sessionId,
      returnSub: subId,
      originBlock: origin.block,
      originSub: origin.subsection,
      originDepth: origin.depth
    });

    // Удаляем origin после использования
    delete session._returnOrigin[subId];

    // Восстанавливаем позицию
    session.template.block = origin.block;
    session.template.subsection = origin.subsection;
    session.template.depth = origin.depth || 'L1';

    // Получаем вопрос для текущей позиции
    let question = null;
    try {
      question = this.templateEngine.getQuestion(origin.subsection, origin.depth || 'L1');
    } catch (err) {
      this.logger.warn('Failed to get question for origin after return', {
        subsection: origin.subsection,
        depth: origin.depth,
        error: err.message
      });
      // Fallback: L1 вопрос
      try {
        question = this.templateEngine.getQuestion(origin.subsection, 'L1');
      } catch {
        question = 'Продолжаем опрос. Расскажите подробнее по текущему разделу.';
      }
    }

    // Информируем пользователя о продолжении
    const continueMessage = `✅ Уточнение по разделу ${subId} завершено. Продолжаем с того же места.`;

    try {
      session = await this._saveSessionSafe(session);
    } catch (err) {
      this.logger.error('Failed to save after continueFromReturn', {
        sessionId: session.sessionId, error: err.message
      });
    }

    return {
      question: `${continueMessage}

❓ ${question}`,
      progress: this.getProgress(session),
      session,
      action: 'next_question'
    };
  }

  // ==================== Story 2.6: Resume Origin (для контролёра) ====================

  /**
   * Возвращает список подразделов, доступных для возврата (уже отвеченных).
   * Используется контролёром для навигации к недоработанным разделам.
   *
   * @param {object} session — объект сессии
   * @returns {Array<{ subId: string, blockId: number, blockName: string, subName: string, depthReached: string }>}
   */
  getAvailableReturnTargets(session) {
    if (!session || !session.answers || !this.templateEngine) return [];

    const targets = [];
    try {
      const blockCount = this.templateEngine.getBlockCount();
      for (let b = 1; b <= blockCount; b++) {
        const block = this.templateEngine.getBlock(b);
        if (!block || !block.subsections) continue;

        for (const sub of block.subsections) {
          const answer = session.answers[sub.id];
          if (answer && answer.depthReached) {
            targets.push({
              subId: sub.id,
              blockId: block.id,
              blockName: block.name || `Блок ${block.id}`,
              subName: sub.name || sub.id,
              depthReached: answer.depthReached,
              maxDepthReached: answer.maxDepthReached || answer.depthReached
            });
          }
        }
      }
    } catch (err) {
      this.logger.warn('Failed to get available return targets', { error: err.message });
    }

    return targets;
  }

  /**
   * Форматирует вопрос при возврате к разделу.
   *
   * Story 2.6: Использует фразу "ранее вы ответили: ..." для показа предыдущего ответа.
   * Поддерживает различные сценарии:
   *   - /back (isUserBack=true): краткое сообщение, показ предыдущего ответа
   *   - Контролёр (reason задан): объяснение причины возврата + показ предыдущего ответа
   *
   * @param {number|string} blockId
   * @param {string} subId
   * @param {string|null} previousAnswer
   * @param {object} [options]
   * @param {boolean} [options.isUserBack=false]
   * @param {string} [options.reason]
   * @returns {string}
   * @private
   */
  _formatReturnQuestion(blockId, subId, previousAnswer, options = {}) {
    const { isUserBack = false, reason = null } = options;

    let question;
    try {
      question = this.templateEngine.getQuestion(subId, 'L1');
    } catch (err) {
      this.logger.warn('Failed to get L1 question for return', {
        subsection: subId,
        error: err.message
      });
      question = 'Расскажите подробнее по данному разделу.';
    }

    let blockName = `Блок ${blockId}`;
    let subName = '';
    try {
      const block = this.templateEngine.getBlock(blockId);
      if (block && block.name) {
        blockName = block.name;
      }
      const sub = this.templateEngine.getSubsection(blockId, subId);
      if (sub && sub.name) {
        subName = sub.name;
      }
    } catch { /* ignore */ }

    const sectionLabel = subName ? `*«${subName}»* (${subId})` : `*«${blockName}»* (${subId})`;

    let header;
    if (isUserBack) {
      // Story 2.6: /back — краткий заголовок с возвратом к предыдущему подразделу
      header = `⬅️ Возврат к разделу ${sectionLabel}.`;
    } else if (reason) {
      // Story 2.6: Контролёр — объяснение причины возврата
      header = `🔄 Давайте уточним раздел ${sectionLabel}.\n\n📋 *Причина:* ${reason}`;
    } else {
      header = `🔄 Возвращаемся к разделу ${sectionLabel}.`;
    }

    // Story 2.6: Показываем предыдущий ответ с фразой "ранее вы ответили"
    let answerRef = '';
    if (previousAnswer) {
      const truncated = previousAnswer.length > 150
        ? previousAnswer.slice(0, 147) + '…'
        : previousAnswer;
      // Используем фразу "ранее вы ответили" как указано в Story 2.6 AC
      answerRef = `\n\n📝 *Ранее вы ответили:*\n_“${truncated}”_\n\nХотите что-то уточнить или дополнить?`;
    } else {
      answerRef = '\n\nВ этом разделе у вас пока нет записанных ответов. Расскажите, что хотите уточнить.';
    }

    return `${header}${answerRef}\n\n${question}`;
  }

  // ==================== L2 Formatting (Story 2.3) ====================

  /**
   * Форматирует L2-вопрос с контекстной адаптацией и префиксом причины.
   *
   * Схема (из UX Spec):
   *   Чтобы лучше понять ситуацию, уточню...
   *
   *   🔍 Давайте уточним: [контекстно-адаптированный вопрос]
   *
   * @param {string} subsectionKey — ключ подраздела ('1.1', '1.2')
   * @param {string} [previousAnswer] — предыдущий ответ пользователя (для контекстной привязки)
   * @returns {string} отформатированный L2-вопрос
   * @private
   */
  _formatL2Question(subsectionKey, previousAnswer) {
    let question;
    try {
      question = this.templateEngine.getQuestion(subsectionKey, 'L2');
    } catch (err) {
      this.logger.warn('Failed to get L2 question for formatting', {
        subsection: subsectionKey,
        error: err.message
      });
      question = 'расскажите подробнее о данном разделе.';
    }

    // Контекстная адаптация: привязываемся к предыдущему ответу пользователя
    let contextPart = '';
    if (previousAnswer && previousAnswer.trim().length > 0) {
      const keyPhrase = this._extractKeyPhrase(previousAnswer);
      if (keyPhrase) {
        // Делаем первую букву вопроса строчной, т.к. он идёт после вводной фразы
        const qStart = question.charAt(0).toLowerCase();
        const qRest = question.slice(1);
        contextPart = `вы упомянули ${keyPhrase}. `;
        question = `${qStart}${qRest}`;
      }
    }

    // Форматируем вопрос с 🔍 (единственное эмодзи на сообщение)
    const formattedQuestion = `🔍 Давайте уточним: ${contextPart}${question}`;

    // Полный текст: префикс причины + пустая строка + отформатированный вопрос
    const fullMessage = `Чтобы лучше понять ситуацию, уточню...\n\n${formattedQuestion}`;

    this.logger.debug('L2 question formatted', {
      subsection: subsectionKey,
      hasContext: !!contextPart,
      messageLength: fullMessage.length
    });

    return fullMessage;
  }

  /**
   * Форматирует L3-вопрос с корневым индикатором глубины и контекстной
   * адаптацией ко всему диалогу (L1 + L2 ответы).
   *
   * Story 2.4: L3 — корневые вопросы, контекстно-релевантные всему диалогу.
   *
   * Формат:
   *   Чтобы понять коренную причину, спрошу глубже...
   *
   *   🔍 Попробуем добраться до сути: [корневой вопрос, контекстно-адаптированный]
   *
   * Контекстная адаптация:
   *   - Если в подразделе есть L1+L2 ответы, извлекается ключевая фраза
   *     и встраивается в вопрос: «вы ранее упомянули [фраза]. [вопрос из шаблона]»
   *   - Если контекст короткий — вопрос задаётся без привязки
   *   - Тональность: без раздражения, с объяснением «Чтобы понять коренную причину...»
   *
   * @param {string} subsectionKey — ключ подраздела ('1.1', '1.2')
   * @param {object} [fullContext] — полный контекст диалога для подраздела
   *   { L1: string, L2: string } — ответы пользователя
   * @returns {string} отформатированный L3-вопрос
   * @private
   */
  _formatL3Question(subsectionKey, fullContext) {
    let question;
    try {
      question = this.templateEngine.getQuestion(subsectionKey, 'L3');
    } catch (err) {
      this.logger.warn('Failed to get L3 question for formatting', {
        subsection: subsectionKey,
        error: err.message
      });
      question = 'расскажите о коренной причине в этом разделе.';
    }

    // Делаем первую букву вопроса строчной, т.к. он идёт после вводной фразы
    const qStart = question.charAt(0).toLowerCase();
    const qRest = question.slice(1);

    // Контекстная адаптация: привязка ко всему диалогу (L1 + L2)
    let contextPart = '';
    if (fullContext && typeof fullContext === 'object') {
      // Собираем весь диалог для извлечения контекста
      const dialogueParts = [];
      if (fullContext.L1 && fullContext.L1.trim().length > 0) {
        dialogueParts.push(fullContext.L1);
      }
      if (fullContext.L2 && fullContext.L2.trim().length > 0) {
        dialogueParts.push(fullContext.L2);
      }

      if (dialogueParts.length > 0) {
        const fullDialogue = dialogueParts.join(' ');
        const keyPhrase = this._extractKeyPhrase(fullDialogue);
        if (keyPhrase) {
          contextPart = `вы говорили про ${keyPhrase}. `;
        }
      }
    }

    // Форматируем вопрос с 🔍 (единственное эмодзи на сообщение)
    // Контекстная фраза встраивается между вводной частью и вопросом из шаблона
    const contextPrefix = contextPart
      ? `🔍 Попробуем добраться до сути: ${contextPart}${qStart}${qRest}`
      : `🔍 Попробуем добраться до сути: ${qStart}${qRest}`;

    // Полный текст: объяснение + пустая строка + контекстно-адаптированный вопрос
    const fullMessage = `Чтобы понять коренную причину, спрошу глубже...\n\n${contextPrefix}`;

    this.logger.debug('L3 question formatted', {
      subsection: subsectionKey,
      hasContext: !!contextPart,
      messageLength: fullMessage.length
    });

    return fullMessage;
  }

  /**
   * Извлекает ключевую фразу из ответа пользователя для контекстной адаптации L2-вопроса.
   *
   * Правила:
   *   - Берёт первое осмысленное предложение (≥3 слов, не слово-подтверждение)
   *   - Извлекает до 5 первых слов
   *   - Игнорирует односложные ответы
   *
   * @param {string} answer — текст ответа пользователя
   * @returns {string|null} ключевая фраза (с заглавной буквы) или null
   * @private
   */
  _extractKeyPhrase(answer) {
    if (!answer || answer.trim().length === 0) return null;

    const text = answer.trim();
    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);

    // Слова-подтверждения, которые не несут контекста
    const fillerWords = new Set([
      'да', 'нет', 'верно', 'правильно', 'точно', 'именно', 'ага', 'угу',
      'yes', 'no', 'yeah', 'yep', 'nope', 'ok', 'okay', 'не', 'ну'
    ]);

    for (const sentence of sentences) {
      const trimmed = sentence.trim();
      const words = trimmed.split(/\s+/).filter(w => w.length > 0);

      // Пропускаем слишком короткие предложения (≤2 слов)
      if (words.length <= 2) {
        // Проверяем, может быть это одно слово-подтверждение
        if (words.length === 1 && fillerWords.has(words[0].toLowerCase().replace(/[!?.]+/g, ''))) {
          continue;
        }
        if (words.length === 1) {
          // Одиночное слово — всё равно проверяем длину
          if (trimmed.length < 4) continue;
        }
        if (words.length === 2) {
          // Два слова — проверяем, не короткий ли это ответ
          if (fillerWords.has(words[0].toLowerCase().replace(/[!?.]+/g, ''))) continue;
        }
      }

      // Берём до 5 слов из первого осмысленного предложения
      const keyWords = words.slice(0, 5).join(' ');

      // Очищаем от знаков препинания в конце
      const cleanKey = keyWords.replace(/[!?.,;:]+$/g, '').trim();

      if (cleanKey.length >= 4) {
        // Капитализируем первую букву
        return cleanKey.charAt(0).toUpperCase() + cleanKey.slice(1);
      }
    }

    return null;
  }

  // ==================== Внутренние методы ====================

  /**
   * Загружает depth-config.json.
   * @private
   */
  _loadDepthConfig(configPath) {
    try {
      if (fs.existsSync(configPath)) {
        const raw = fs.readFileSync(configPath, 'utf-8');
        this.depthConfig = JSON.parse(raw);
        this.logger.info('Depth config loaded', { path: configPath });
      } else {
        this.logger.warn('Depth config not found, using defaults', { path: configPath });
        this.depthConfig = null;
      }
    } catch (err) {
      this.logger.warn('Failed to load depth config, using defaults', {
        path: configPath,
        error: err.message
      });
      this.depthConfig = null;
    }
  }

  /**
   * Оценивает глубину ответа пользователя.
   * Возвращает число от 0 до 1:
   *   0.0-0.3 → поверхностный (L1)
   *   0.3-0.6 → средний (L2)
   *   0.6-1.0 → глубокий (L3)
   *
   * @param {string} answer — текст ответа
   * @returns {number} score 0..1
   * @private
   */
  /**
   * Проверяет, достаточно ли глубок ответ для фиксации на L1.
   * Критерии из Story 2.2: ≥3 предложений ИЛИ ≥2 фактов.
   *
   * @param {string} answer — текст ответа
   * @returns {boolean}
   * @private
   */
  _isL1DeepEnough(answer) {
    if (!answer || answer.trim().length === 0) return false;

    const text = answer.trim();
    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);

    // ≥3 предложений → достаточно глубоко
    if (sentences.length >= 3) return true;

    // ≥2 фактов → достаточно глубоко
    const factCount = this._countFacts(text);
    if (factCount >= 2) return true;

    return false;
  }

  /**
   * Считает количество фактов в тексте (цифры, индикаторы, причинно-следственные связи).
   * @param {string} text
   * @returns {number}
   * @private
   */
  _countFacts(text) {
    if (!text) return 0;
    const lowerText = text.toLowerCase();
    let facts = 0;

    // Цифры — факт
    if (/\d+/.test(text)) facts++;

    // Индикаторы глубины — факт (конкретные примеры)
    const hasDepthIndicators = this.depthIndicators.some(
      ind => lowerText.includes(ind.toLowerCase())
    );
    if (hasDepthIndicators) facts++;

    // Причинно-следственные связи — факт анализа
    const hasCausalLinks = this.causalIndicators.some(
      ind => lowerText.includes(ind.toLowerCase())
    );
    if (hasCausalLinks) facts++;

    // Перечисления (списки) — структурные факты
    if (/^[-*]\s/m.test(text) || /^\d+\.\s/m.test(text)) facts++;

    return facts;
  }

  /**
   * Enhanced buildReflection is defined in the Story 2.7 UX Components section.
   * This spot is intentionally left blank to avoid method duplication.
   */

  _evaluateDepth(answer) {
    if (!answer || answer.trim().length === 0) return 0;

    const text = answer.trim();
    const sentences = text.split(/[.!?]+/).filter(s => s.trim().length > 0);
    const words = text.split(/\s+/).filter(w => w.length > 0);
    const lowerText = text.toLowerCase();

    let score = 0;
    const signals = [];

    // 1. Длина ответа (базовый сигнал)
    const sentenceCount = sentences.length;
    const wordCount = words.length;

    if (sentenceCount >= 8) {
      score += 0.25;
      signals.push('long_text');
    } else if (sentenceCount >= 5) {
      score += 0.2;
      signals.push('medium_text');
    } else if (sentenceCount >= 3) {
      score += 0.1;
      signals.push('short_text');
    } else {
      score += 0.05;
      signals.push('very_short');
    }

    // 2. Конкретные факты (цифры, количество)
    const hasNumbers = /\d+/.test(text);
    if (hasNumbers) {
      score += 0.15;
      signals.push('has_numbers');
    }

    // 3. Глубинные индикаторы из depth-config
    const hasDepthIndicators = this.depthIndicators.some(
      indicator => lowerText.includes(indicator.toLowerCase())
    );
    if (hasDepthIndicators) {
      score += 0.15;
      signals.push('has_depth_indicators');
    }

    // 4. Причинно-следственные связи
    const hasCausalLinks = this.causalIndicators.some(
      indicator => lowerText.includes(indicator.toLowerCase())
    );
    if (hasCausalLinks) {
      score += 0.2;
      signals.push('has_causal_links');
    }

    // 5. Штраф за размытые фразы
    const vagueCount = this.vaguePhrases.filter(
      phrase => lowerText.includes(phrase.toLowerCase())
    ).length;
    if (vagueCount > 0) {
      score -= vagueCount * 0.1;
      signals.push('vague_penalty');
    }

    // 6. Структурированность (маркированные списки, перечисления)
    const hasList = /^[-*]\s/m.test(text) || /^\d+\.\s/m.test(text);
    if (hasList) {
      score += 0.1;
      signals.push('structured');
    }

    // 7. Длина как доля от max (кап 0.1)
    const lengthRatio = Math.min(wordCount / 100, 1) * 0.1;
    score += lengthRatio;

    // Нормализуем в [0, 1]
    score = Math.max(0, Math.min(1, score));

    this.logger.debug('Depth evaluation', {
      score,
      signals,
      sentenceCount,
      wordCount,
      hasNumbers,
      hasCausalLinks,
      vaguePhrases: vagueCount
    });

    return score;
  }

  /**
   * Извлекает риски из ответа пользователя.
   * Эвристика: ищет ключевые слова и контекстные паттерны, указывающие на риски.
   * Story 2.3: улучшенное детектирование во время L2-диалога (контекстные паттерны,
   * составные триггеры, отслеживание глубины сбора).
   *
   * @param {string} answer — текст ответа
   * @param {object} session — сессия (для определения текущего блока)
   * @param {string} subsectionKey — ключ подраздела
   * @param {string} [currentDepth] — текущий уровень глубины ('L1'|'L2'|'L3')
   * @returns {Array<{ text: string, collectedAt: string, category: string, depth: string|null }>}
   * @private
   */
  /**
   * Собирает риски из ответа пользователя с расширенным анализом.
   * Story 2.5: обёртка над _extractRisks() с добавлением timestamp,
   * дедупликацией, категоризацией и автоматическим логгированием.
   *
   * @param {string} answer — текст ответа
   * @param {object} session — сессия
   * @param {string} subsectionKey — ключ подраздела
   * @param {string} [currentDepth] — текущий уровень глубины
   * @returns {Array<{ text: string, collectedAt: string, category: string, depth: string|null, timestamp: string }>}
   * @private
   */
  _collectRisks(answer, session, subsectionKey, currentDepth) {
    const detected = this._extractRisks(answer, session, subsectionKey, currentDepth);

    if (detected.length > 0) {
      this.logger.info('Risks collected from answer', {
        sessionId: session.sessionId,
        count: detected.length,
        categories: detected.reduce((acc, r) => {
          acc[r.category] = (acc[r.category] || 0) + 1;
          return acc;
        }, {}),
        subsection: subsectionKey,
        depth: currentDepth
      });
    }

    return detected;
  }

  /**
   * Строит сводку рисков для входа в Блок 7.
   * Story 2.5: "По ходу разговора я заметил несколько рисков. Давайте их систематизируем."
   *
   * @param {object} session — сессия
   * @returns {string|null} — сообщение со сводкой рисков или null, если рисков нет
   * @private
   */
  _buildBlock7RiskSummary(session) {
    const risks = session.risks || [];
    if (risks.length === 0) return null;

    const byCategory = {};
    const categoryLabels = {
      technical: '🛠 Технические',
      org: '👥 Организационные',
      business: '💼 Бизнес-риски',
      adoption: '👤 Внедрение'
    };

    for (const risk of risks) {
      const cat = risk.category || 'uncategorized';
      if (!byCategory[cat]) byCategory[cat] = [];
      byCategory[cat].push(risk);
    }

    const lines = [];
    for (const [cat, catRisks] of Object.entries(byCategory)) {
      const label = categoryLabels[cat] || `📋 ${cat}`;
      lines.push(`${label}: ${catRisks.length}`);
    }

    const text =
      `⚠️ *По ходу разговора я заметил несколько рисков.* Давайте их систематизируем.\n\n` +
      `Всего замечено: *${risks.length} ${risks.length === 1 ? 'риск' : 'рисков'}*\n` +
      lines.join('\n') +
      `\n\n📝 Пожалуйста, для каждого риска уточните:\n` +
      `1. Вероятность (низкая/средняя/высокая)\n` +
      `2. Влияние (низкое/среднее/высокое)\n` +
      `3. Какие меры митигации предлагаете?`;

    return text;
  }

  _extractRisks(answer, session, subsectionKey, currentDepth) {
    const risks = [];
    const lowerAnswer = answer.toLowerCase();
    const now = new Date().toISOString();

    // === Story 2.5: Расширенные триггеры ===
    const riskTriggers = [
      // Технические риски
      { words: ['техн', 'разработк', 'сервер', 'хостинг', 'баз данных', 'бд', 'инфраструктур'], category: 'technical' },
      { words: ['безопасность', 'доступ', 'конфиденциально', 'утечка', 'шифрован', 'авторизаци'], category: 'technical' },
      { words: ['интеграция', 'API', 'совместимость', 'стыковка', 'протокол', 'интерфейс'], category: 'technical' },
      { words: ['производительность', 'скорость', 'масштабирова', 'нагрузка', 'бутылочно'], category: 'technical' },
      { words: ['проблема', 'сложность', 'трудно', 'тяжело', 'не работает', 'ошибка', 'баг'], category: 'technical' },
      // Организационные риски
      { words: ['команд', 'люди', 'некому', 'ресурс', 'персонал', 'сотрудник', 'вакансия'], category: 'org' },
      { words: ['срок', 'дедлайн', 'задержк', 'опозда', 'не успеем', 'просроч'], category: 'org' },
      { words: ['процесс', 'регламент', 'согласова', 'бюрократи', 'контроль', 'отчёт'], category: 'org' },
      { words: ['менеджмент', 'управление', 'руководств', 'начальник', 'директор'], category: 'org' },
      // Бизнес-риски
      { words: ['бизнес', 'рынок', 'клиент', 'конкурент', 'рентабельность', 'прибыль'], category: 'business' },
      { words: ['бюджет', 'денег нет', 'дорого', 'финансы', 'стоимость', 'затрат', 'окупаемость'], category: 'business' },
      { words: ['риск', 'опасность', 'угроза', 'потер', 'убытк', 'неопределённость'], category: 'business' },
      // Риски внедрения
      { words: ['пользователь', 'adoption', 'примут', 'отторжение', 'юзер', 'сотрудник'], category: 'adoption' },
      { words: ['сопротивление', 'страх', 'боя', 'не готов', 'не хот', 'культур'], category: 'adoption' }
    ];

    // === Story 2.5: Расширенные контекстные паттерны ===
    const contextualPatterns = [
      // Технические риски
      { patterns: [
        /не хватает? (данных|информации|мощностей|времени|ресурсов)/i,
        /нет (возможности|инструмента|доступа|опыта|знаний)/i,
        /сложно (собрать|получить|настроить|интегрировать|реализовать)/i,
        /техническ(ая|ое|ий) (долг|ограничени|проблем)/i,
        /устаревш(ая|ее|ий) (систем|технологи|платформ)/i
      ], category: 'technical' },
      // Организационные риски
      { patterns: [
        /никто не (знает|понимает|занимается|отвечает)/i,
        /нет (ответственного|владельца|куратора|лидера|координатор)/i,
        /между (отделами|командами|департаментами|подразделениями)/i,
        /непонятн[ао] (кто|что|когда|как|почему)/i
      ], category: 'org' },
      // Бизнес-риски
      { patterns: [
        /зависит от (другого|внешнего|третьей|поставщик|партнёр)/i,
        /неопределённ/i,
        /непонятно/i,
        /не ясно/i,
        /под вопрос/i,
        /нет (уверен|гарант|ясн)/i
      ], category: 'business' },
      // Риски внедрения
      { patterns: [
        /сопротивление/i,
        /не (готов|готовы|примут|пойм)/i,
        /страх/i,
        /боя/i,
        /боим/i,
        /опаса/i,
        /привык/i
      ], category: 'adoption' }
    ];

    const collectedBlock = `block_${subsectionKey.split('.')[0]}`;
    const existingTexts = new Set(
      (session.risks || []).map(r => r.text.toLowerCase())
    );
    const sentences = answer.split(/[.!?]+/).filter(s => s.trim().length > 0);

    // === Фаза 1: Базовый keyword-поиск ===
    for (const trigger of riskTriggers) {
      const found = trigger.words.some(word => lowerAnswer.includes(word));
      if (found) {
        for (const sentence of sentences) {
          const lowerSentence = sentence.toLowerCase();
          if (trigger.words.some(w => lowerSentence.includes(w))) {
            const trimmed = sentence.trim();
            const lowerTrimmed = trimmed.toLowerCase();
            if (!existingTexts.has(lowerTrimmed)) {
              risks.push({
                text: trimmed,
                collectedAt: collectedBlock,
                category: trigger.category,
                probability: null,
                impact: null,
                mitigation: null,
                depth: currentDepth || null,
                timestamp: now
              });
              existingTexts.add(lowerTrimmed);
              break;
            }
          }
        }
      }
    }

    // === Фаза 2: Контекстные паттерны (только для развёрнутых ответов ≥3 предложений) ===
    if (sentences.length >= 3) {
      for (const ctx of contextualPatterns) {
        for (const pattern of ctx.patterns) {
          const match = pattern.exec(answer);
          if (match) {
            // Находим предложение, содержащее паттерн
            for (const sentence of sentences) {
              if (pattern.test(sentence)) {
                const trimmed = sentence.trim();
                const lowerTrimmed = trimmed.toLowerCase();
                if (!existingTexts.has(lowerTrimmed)) {
                  risks.push({
                    text: trimmed,
                    collectedAt: collectedBlock,
                    category: ctx.category,
                    probability: null,
                    impact: null,
                    mitigation: null,
                    depth: currentDepth || 'L2',
                    timestamp: now
                  });
                  existingTexts.add(lowerTrimmed);
                  break;
                }
              }
            }
          }
        }
      }
    }

    // === Фаза 3: Анализ «если…то» (условные риски в L2-ответах) ===
    if (sentences.length >= 2) {
      const conditionalPattern = /если\s+(.+?)\s*,\s*то\s+(.+?)[.?!;]/gi;
      let condMatch;
      while ((condMatch = conditionalPattern.exec(answer)) !== null) {
        const fullMatch = condMatch[0].trim();
        const lowerMatch = fullMatch.toLowerCase();
        if (!existingTexts.has(lowerMatch)) {
          risks.push({
            text: fullMatch,
            collectedAt: collectedBlock,
            category: 'business',
            probability: null,
            impact: null,
            mitigation: null,
            depth: currentDepth || 'L2',
            timestamp: now
          });
          existingTexts.add(lowerMatch);
        }
      }
    }

    return risks;
  }

  // ==================== Story 2.6: Handle answer during return flow ====================

  /**
   * Обрабатывает ответ пользователя при возврате к разделу (через /back или контролёр).
   *
   * Story 2.6:
   *   1. Сохраняет/обновляет ответ для подраздела, к которому вернулись
   *   2. Отмечает depthReached (сохраняя предыдущий достигнутый уровень)
   *   3. Собирает риски из уточнения
   *   4. Вызывает continueFromReturn для возврата к origin-позиции
   *
   * @param {object} session — объект сессии
   * @param {string} answer — ответ пользователя
   * @param {string} subId — подраздел, к которому был возврат
   * @returns {Promise<{ question: string|null, progress: object, session: object, action: string }>}
   * @private
   */
  async _handleReturnAnswer(session, answer, subId) {
    this.logger.info('Processing answer during return flow', {
      sessionId: session.sessionId,
      subsection: subId
    });

    // 1. Обновляем/сохраняем ответ для этого подраздела
    if (!session.answers) {
      session.answers = {};
    }
    if (!session.answers[subId]) {
      session.answers[subId] = {};
    }

    // Сохраняем уточнение как L1 (новый ответ поверх старого)
    // Сохраняем предыдущие L2/L3 если были (они остаются)
    const prevMaxDepth = session.answers[subId].maxDepthReached || session.answers[subId].depthReached;
    session.answers[subId].L1 = answer;
    // Обновляем depthReached — сохраняем максимум
    session.answers[subId].depthReached = prevMaxDepth || 'L1';
    // Отмечаем, что был возврат для этого подраздела
    session.answers[subId].returnedTo = true;
    session.answers[subId].returnedAt = new Date().toISOString();
    session.answers[subId].returnedAnswers = session.answers[subId].returnedAnswers || [];
    session.answers[subId].returnedAnswers.push({
      answer,
      timestamp: new Date().toISOString()
    });

    // 2. Собираем риски из уточнения
    const detectedRisks = this._collectRisks(answer, session, subId, 'L1');
    if (detectedRisks.length > 0) {
      if (!session.risks) session.risks = [];
      session.risks.push(...detectedRisks);
    }

    session.updatedAt = new Date().toISOString();

    // 3. Сохраняем сессию
    try {
      session = await this._saveSessionSafe(session);
    } catch (err) {
      this.logger.error('Failed to save during return flow', {
        sessionId: session.sessionId, error: err.message
      });
    }

    // 4. Продолжаем с origin-позиции
    this.logger.info('Return flow: continuing from origin', {
      sessionId: session.sessionId,
      returnSub: subId
    });

    return await this.continueFromReturn(session, subId);
  }

  /**
   * Безопасное сохранение сессии через Session Manager с обработкой ошибок.
   *
   * @param {object} session
   * @returns {Promise<object>}
   * @private
   */
  async _saveSessionSafe(session) {
    if (!this.sessionManager) {
      this.logger.warn('SessionManager не подключён, сохранение пропущено');
      return session;
    }

    try {
      const saved = await this.sessionManager.updateSession(
        session.sessionId,
        session
      );
      return saved;
    } catch (err) {
      this.logger.error('Session save failed', {
        sessionId: session.sessionId,
        error: err.message
      });
      throw new Error(`Ошибка сохранения сессии: ${err.message}`);
    }
  }

  /**
   * Обрабатывает ответ пользователя на Reflection Message.
   * Story 2.2: подтверждение → переход к следующему подразделу;
   * исправление → обновление ответа.
   *
   * @param {object} session
   * @param {string} answer — ответ пользователя
   * @returns {Promise<{ question: string|null, progress: object, session: object, action: string }>}
   * @private
   */
  async _handleReflectionConfirm(session, answer) {
    this.logger.debug('Handling reflection confirmation', {
      sessionId: session.sessionId,
      subsection: session.reflectionSubsection
    });

    const subKey = session.reflectionSubsection;
    const currentBlock = session.template.block;

    // Определяем, подтверждение или исправление
    const confirmWords = [
      'да', 'верно', 'правильно', 'точно', 'именно', 'да-да',
      'yes', 'yeah', 'yep', 'ok', 'okay', 'ага', 'угу', 'так точно',
      'всё верно', 'все верно', 'да, всё верно', 'согласен',
      'подтверждаю', 'так и есть', 'именно так'
    ];

    const trimmed = answer.trim().toLowerCase().replace(/[!?.]+/g, '').trim();
    const isConfirmation = confirmWords.includes(trimmed) ||
      confirmWords.some(w => trimmed === w || trimmed === w + '.');

    // Сбрасываем reflection state
    session.reflectionPending = false;
    session.reflectionSubsection = null;

    if (isConfirmation) {
      // Подтверждение: depthReached уже 'L1', переходим к следующему подразделу
      this.logger.info('Reflection confirmed, advancing to next subsection', {
        sessionId: session.sessionId,
        subsection: subKey
      });

      const nextSub = this.templateEngine.getNextSubsection(currentBlock, subKey);

      let question = null;
      let action = 'next_question';

      if (nextSub) {
        const nextBlockNum = parseInt(nextSub.id.split('.')[0], 10);
        session.template.subsection = nextSub.id;
        session.template.block = nextBlockNum;
        session.template.depth = 'L1';

        try {
          question = this.templateEngine.getQuestion(nextSub.id, 'L1');
        } catch (err) {
          this.logger.error('Failed to get next question after reflection', {
            subsection: nextSub.id, error: err.message
          });
          question = 'Расскажите подробнее о данном разделе.';
        }
      } else {
        action = 'survey_complete';
      }

      session.updatedAt = new Date().toISOString();

      try {
        session = await this._saveSessionSafe(session);
      } catch (err) {
        this.logger.error('Failed to save after reflection confirm', {
          sessionId: session.sessionId, error: err.message
        });
        this._fsErrorCache.set(session.sessionId, {
          session, lastError: err.message, retries: 1
        });
        action = 'error';
        question = '⚠️ Не удалось сохранить. Попробуйте ещё раз.';
      }

      return {
        question,
        progress: this.getProgress(session),
        session,
        action
      };
    }

    // Исправление: обновляем ответ и заново оцениваем
    this.logger.info('Reflection corrected, re-evaluating answer', {
      sessionId: session.sessionId
    });

    session.answers[subKey].L1 = answer;
    delete session.answers[subKey].depthReached;

    // Повторная оценка исправленного ответа
    if (this._isL1DeepEnough(answer)) {
      // Теперь достаточно глубоко — фиксируем
      session.answers[subKey].depthReached = 'L1';

      const nextSub = this.templateEngine.getNextSubsection(currentBlock, subKey);
      let question = null;

      if (nextSub) {
        const nextBlockNum = parseInt(nextSub.id.split('.')[0], 10);
        session.template.subsection = nextSub.id;
        session.template.block = nextBlockNum;
        session.template.depth = 'L1';
        try {
          question = this.templateEngine.getQuestion(nextSub.id, 'L1');
        } catch (err) {
          question = 'Расскажите подробнее о данном разделе.';
        }
      }

      // Собираем риски из исправленного ответа
      const detectedRisks = this._collectRisks(answer, session, subKey, 'L1');
      if (detectedRisks.length > 0) {
        if (!session.risks) session.risks = [];
        session.risks.push(...detectedRisks);
      }

      session.updatedAt = new Date().toISOString();

      try {
        session = await this._saveSessionSafe(session);
      } catch (err) {
        this.logger.error('Failed to save after reflection correction', {
          sessionId: session.sessionId, error: err.message
        });
      }

      return {
        question: question || null,
        progress: this.getProgress(session),
        session,
        action: question ? 'next_question' : 'survey_complete'
      };
    }

    // Исправление всё ещё поверхностное → переходим на L2
    session.answers[subKey].depthReached = 'L1';
    session.template.depth = 'L2';

    // Story 2.3: Форматируем L2-вопрос с контекстной адаптацией
    // Используем исправленный ответ как контекст для вопроса
    const question = this._formatL2Question(subKey, answer);

    session.updatedAt = new Date().toISOString();

    try {
      session = await this._saveSessionSafe(session);
    } catch (err) {
      this.logger.error('Failed to save after reflection → L2', {
        sessionId: session.sessionId, error: err.message
      });
    }

    return {
      question,
      progress: this.getProgress(session),
      session,
      action: 'next_question'
    };
  }

  /**
   * Извлекает последний ответ пользователя из сессии.
   *
   * @param {object} session
   * @returns {string|null}
   * @private
   */
  _getLastAnswerText(session) {
    if (!session || !session.answers) return null;

    const answeredKeys = Object.keys(session.answers);
    if (answeredKeys.length === 0) return null;

    const lastKey = answeredKeys[answeredKeys.length - 1];
    const lastEntry = session.answers[lastKey];

    if (!lastEntry) return null;

    // Ищем ответ: L3 → L2 → L1 (приоритет более глубоким)
    for (const depth of ['L3', 'L2', 'L1']) {
      if (lastEntry[depth]) return lastEntry[depth];
    }

    return null;
  }

  // ==================== Story 2.6: Previous subsection navigation ====================

  /**
   * Определяет предыдущий подраздел относительно текущей позиции в сессии.
   *
   * Story 2.6: Используется для /back навигации.
   *
   * @param {object} session - текущая сессия
   * @returns {object|null} { blockId, fullKey, name } или null, если мы в начале
   * @private
   */
  _getPreviousSubsection(session) {
    if (!session || !session.template) return null;
    if (!this.templateEngine) return null;

    const currentSub = session.template.subsection || '1.1';

    // Собираем все подразделы в порядке обхода
    const allSubsections = [];
    try {
      const blockCount = this.templateEngine.getBlockCount();
      for (let b = 1; b <= blockCount; b++) {
        const block = this.templateEngine.getBlock(b);
        if (block && block.subsections) {
          for (const sub of block.subsections) {
            allSubsections.push({
              blockId: block.id,
              fullKey: sub.id,
              name: sub.name
            });
          }
        }
      }
    } catch {
      return null;
    }

    if (allSubsections.length === 0) return null;

    // Находим индекс текущего подраздела
    const currentIdx = allSubsections.findIndex(s => s.fullKey === currentSub);
    if (currentIdx <= 0) return null; // мы в начале или не нашли

    return allSubsections[currentIdx - 1];
  }

  // ==================== Story 3.4: Return for Revision ====================

  /**
   * Обрабатывает запрос на доработку от контролёра.
   *
   * Story 3.4: Получает revision request с замечаниями,
   * реформулирует их в естественные вопросы для пользователя.
   * Story 3.5: Запрос уточнений через агента-опросчика.
   *
   * Пользователь НЕ ДОЛЖЕН видеть прямых сообщений контролёра.
   * Все вопросы формулируются в тональности Quality Feedback:
   *   "💡 Я заметил, что этот раздел можно проработать глубже.
   *    Конкретно: [причина]. Давайте уточним: [вопрос]"
   *
   * @param {object} request — revision request от контролёра
   *   { action: 'return_to_questioner'|'request_clarification'|'force_accept',
   *     target: { block, subsection, reason, suggestions },
   *     iteration: number, forceAccept: boolean, allIssues: Array }
   * @param {object} session — текущая сессия
   * @returns {Promise<{ question: string, isForceAccept: boolean,
   *    session: object, action: string, progress: object }>}
   */
  async handleRevisionRequest(request, session) {
    if (!request || !session) {
      throw new Error('SurveyEngine: требуется revision request и сессия');
    }

    this.logger.info('SurveyEngine: handling revision request', {
      sessionId: session.sessionId,
      action: request.action,
      target: request.target ? `${request.target.block}.${request.target.subsection}` : 'none',
      iteration: request.iteration
    });

    // Если force_accept — не задаём вопрос, просто уведомляем
    if (request.action === 'force_accept' || request.forceAccept) {
      const msg = this._buildForceAcceptMessage(request);
      return {
        question: msg,
        isForceAccept: true,
        session,
        action: 'force_accept',
        progress: this.getProgress(session)
      };
    }

    // Отмечаем сессию, что идёт доработка
    session._revisionActive = {
      request: request,
      startedAt: new Date().toISOString()
    };

    // Строим естественный вопрос пользователю
    const question = this._buildRevisionQuestion(request, session);

    this.logger.debug('Revision question built', {
      questionLength: question.length,
      targetSub: request.target ? request.target.subsection : null
    });

    return {
      question,
      isForceAccept: false,
      session,
      action: 'revision_needed',
      progress: this.getProgress(session)
    };
  }

  /**
   * Обрабатывает ответ пользователя на запрос доработки.
   *
   * Story 3.4, 3.5:
   *   - Сохраняет уточнённый ответ в сессию (перезаписывает или дополняет)
   *   - Снимает флаг _revisionActive
   *   - Возвращает обновлённую сессию для повторной передачи контролёру
   *
   * @param {string} answer — ответ пользователя на уточняющий вопрос
   * @param {object} session — текущая сессия
   * @param {object} request — оригинальный revision request
   * @returns {Promise<{ session: object, action: string,
   *    message: string, progress: object, revisionAnswer: object }>}
   */
  async processRevisionAnswer(answer, session, request) {
    if (!answer || !session) {
      throw new Error('SurveyEngine: требуется ответ и сессия для processRevisionAnswer');
    }

    const target = request && request.target;
    const subId = target ? target.subsection : null;
    const blockId = target ? target.block : null;

    if (subId) {
      // Сохраняем уточнённый ответ в сессию
      if (!session.answers) {
        session.answers = {};
      }
      if (!session.answers[subId]) {
        session.answers[subId] = {};
      }

      // Сохраняем как L1-ответ revision (не затирает глубину, если была)
      if (!session.answers[subId].L1_revision) {
        session.answers[subId].L1_revision = [];
      } else if (!Array.isArray(session.answers[subId].L1_revision)) {
        session.answers[subId].L1_revision = [session.answers[subId].L1_revision];
      }
      session.answers[subId].L1_revision.push({
        text: answer,
        revisedAt: new Date().toISOString(),
        iteration: session._revisionActive
          ? (session.qualityGate ? session.qualityGate.iteration : 1)
          : 1
      });

      // Если не было depthReached — проставляем
      if (!session.answers[subId].depthReached) {
        session.answers[subId].depthReached = 'L1';
      }

      this.logger.info('Revision answer saved', {
        sessionId: session.sessionId,
        subsection: subId,
        answerLength: answer.length
      });
    }

    // Снимаем флаг активной доработки
    session._revisionActive = null;
    session.updatedAt = new Date().toISOString();

    // Сохраняем сессию
    try {
      session = await this._saveSessionSafe(session);
    } catch (err) {
      this.logger.error('Failed to save session during processRevisionAnswer', {
        sessionId: session.sessionId,
        error: err.message
      });
    }

    const message = '✅ Спасибо за уточнение! Передаю данные на повторную проверку.';

    return {
      session,
      action: 'return_to_controller',
      message,
      progress: this.getProgress(session),
      revisionAnswer: {
        subsection: subId,
        text: answer,
        answeredAt: new Date().toISOString()
      }
    };
  }

  // ==================== Story 3.4/3.5: Private Helpers ====================

  /**
   * Строит естественный вопрос для пользователя на основе revision request.
   *
   * Формат (из prompt.md Story 3.4 AC):
   *   "💡 Я заметил, что этот раздел можно проработать глубже.
   *    Конкретно: [причина]. Давайте уточним: [вопрос]"
   *
   * Формат для request_clarification (Story 3.5):
   *   "💡 Давайте уточним детали: [контекст]\n\n[вопрос]"
   *
   * @param {object} request — revision request
   * @param {object} session — сессия
   * @returns {string} естественный вопрос
   * @private
   */
  _buildRevisionQuestion(request, session) {
    if (!request || !request.target) {
      return '💡 Давайте уточним этот раздел. Что именно вы имели в виду?';
    }

    const { block, subsection, reason, suggestions } = request.target;

    // Определяем название подраздела
    let subName = subsection;
    try {
      if (this.templateEngine) {
        const blockObj = this.templateEngine.getBlock(block);
        if (blockObj && blockObj.subsections) {
          const sub = blockObj.subsections.find(s => s.id === subsection);
          if (sub && sub.name) {
            subName = sub.name;
          }
        }
      }
    } catch { /* ignore */ }

    // Проверяем action для выбора тональности
    if (request.action === 'request_clarification') {
      // Story 3.5: Запрос уточнений — более мягкая формулировка
      let question = `💡 *Давайте уточним детали по разделу «${subName}»*\n\n`;

      if (reason) {
        question += `Я заметил: ${reason}\n\n`;
      }

      if (suggestions && suggestions.length > 0) {
        question += `*Уточните:*\n`;
        for (const s of suggestions) {
          question += `• ${s}\n`;
        }
        question += '\n';
      }

      question += 'Напишите подробнее, пожалуйста.';
      return question;
    }

    // Story 3.4: Return for revision — тональность Quality Feedback
    let question = `💡 *Давайте проработаем раздел «${subName}» глубже.*\n\n`;

    if (reason) {
      question += `Конкретно: ${reason}\n\n`;
    }

    if (suggestions && suggestions.length > 0) {
      question += '*Рекомендации:*\n';
      for (const s of suggestions) {
        question += `• ${s}\n`;
      }
      question += '\n';
    }

    question += 'Пожалуйста, уточните ваш ответ.';
    return question;
  }

  /**
   * Строит сообщение при форсированном принятии (лимит итераций).
   *
   * @param {object} request — revision request
   * @returns {string} сообщение пользователю
   * @private
   */
  _buildForceAcceptMessage(request) {
    const target = request.target || {};
    const issues = request.allIssues || [];

    let msg = '📋 *Раздел принят как есть.*\n\n';

    if (target.reason) {
      msg += `Достигнут лимит итераций (макс. 3). Исходные замечания: ${target.reason}\n\n`;
    }

    if (issues.length > 0) {
      msg += '*Зафиксированные замечания:*\n';
      for (const issue of issues) {
        msg += `• ${issue.detail || issue.reason || 'не указано'}\n`;
      }
      msg += '\n';
    }

    msg += 'Продолжаем заполнение следующих разделов.';
    return msg;
  }

  // ==================== Story 5.1: History Recording ====================

  /**
   * Записывает завершённую сессию в history.json через HistoryRecorder.
   *
   * Вызывается из signalCompletion() для каждой завершённой сессии.
   * Использует SessionContext для извлечения данных об ответах, рисках и draft.
   *
   * @param {object} context — SessionContext
   * @returns {Promise<object>} — записанная запись истории
   * @private
   */
  async _recordToHistory(context) {
    if (!this.historyRecorder) {
      this.logger.debug('HistoryRecorder не подключён — запись истории пропущена', {
        sessionId: context.sessionId
      });
      return null;
    }

    this.logger.info('Recording session to history (self-learning)', {
      sessionId: context.sessionId,
      user: context.telegramUserId
    });

    try {
      // Передаём SessionContext целиком — HistoryRecorder сам извлечёт нужные поля
      const entry = await this.historyRecorder.recordSession(context);

      this.logger.info('Session history recorded successfully', {
        sessionId: context.sessionId,
        answersCount: Object.keys(context.answers || {}).length,
        risksCount: (context.risks || []).length,
        keywordsCount: (entry.keywords || []).length
      });

      return entry;
    } catch (err) {
      this.logger.error('Failed to record session to history', {
        sessionId: context.sessionId,
        error: err.message
      });
      // Не перевыбрасываем — ошибка записи истории не должна блокировать ответ пользователю
      return null;
    }
  }

  // ==================== Story 5.4: Async Self-Learning Update ====================

  /**
   * Запускает асинхронное обновление self-learning через LearningEngine.
   *
   * Story 5.4: Non-blocking — LearningEngine.triggerAsyncUpdate() использует
   * setImmediate для выполнения в следующем тике цикла событий.
   * Ответ пользователю уже отправлен — обновление не влияет на UX.
   *
   * @param {string} sessionId — идентификатор завершённой сессии
   * @returns {Promise<boolean>} — true если обновление запланировано
   * @private
   */
  async _triggerLearningUpdate(sessionId) {
    if (!this.learningEngine) {
      this.logger.debug('LearningEngine не подключён — self-learning update пропущен', {
        sessionId
      });
      return false;
    }

    if (!sessionId) {
      this.logger.warn('_triggerLearningUpdate: sessionId не указан');
      return false;
    }

    this.logger.info('Triggering async self-learning update (Story 5.4)', {
      sessionId
    });

    try {
      // ===== Story 5.4: Fire-and-forget =====
      // triggerAsyncUpdate возвращает Promise, но мы не ждём его выполнения.
      // Внутри LearningEngine использует setImmediate для неблокирующего планирования.
      const scheduled = await this.learningEngine.triggerAsyncUpdate(sessionId);

      if (scheduled) {
        this.logger.info('Async self-learning update scheduled successfully', {
          sessionId,
          nonBlocking: true
        });
      } else {
        this.logger.warn('Async self-learning update not scheduled (trigger returned false)', {
          sessionId
        });
      }

      return scheduled;
    } catch (err) {
      this.logger.error('Failed to trigger async self-learning update', {
        sessionId,
        error: err.message
      });
      // Не перевыбрасываем — ошибка self-learning не должна блокировать ответ пользователю
      return false;
    }
  }
}

module.exports = SurveyEngine;
