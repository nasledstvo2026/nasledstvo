/**
 * Session Commands — команды управления сессией
 *
 * Story 1.5 — Команды управления сессией (resume, history, cancel, back)
 *
 * Набор обработчиков для команд управления сессией пользователя:
 *   /start — проверить активную сессию, предложить продолжить или начать новую
 *   /history — список завершённых сессий (дата, статус)
 *   /cancel — подтверждение → сохранение черновика → завершение сессии
 *   /back — возврат к предыдущему подразделу/блоку, показ последнего ответа
 *
 * Каждый метод принимает { msg, connector, sessionManager, templateEngine, whitelist }
 * и возвращает { action, reply } или выкидывает ошибку.
 *
 * Зависимости:
 *   - TelegramConnector (для sendMessage)
 *   - SessionManager (для операций с сессиями)
 *   - TemplateEngine (для навигации по шаблону)
 *   - Whitelist (для проверки доступа)
 */

const { createLogger } = require('./logger');

// ==================== Клавиатуры (inline keyboard) ====================

/**
 * Клавиатура подтверждения отмены сессии
 */
function cancelConfirmKeyboard() {
  return {
    reply_markup: {
      inline_keyboard: [
        [
          { text: '✅ Да, завершить сессию', callback_data: 'cancel:confirm' },
          { text: '❌ Нет, продолжить', callback_data: 'cancel:abort' }
        ]
      ]
    }
  };
}

/**
 * Клавиатура для resume-диалога
 */
function resumeKeyboard() {
  return {
    reply_markup: {
      inline_keyboard: [
        [
          { text: '▶️ Продолжить', callback_data: 'resume:continue' },
          { text: '🆕 Новая сессия', callback_data: 'resume:new' }
        ]
      ]
    }
  };
}

/**
 * Клавиатура для просмотра завершённых сессий
 * @param {Array<{sessionId: string, index: number}>} sessions
 * @returns {object}
 */
function historyKeyboard(sessions) {
  const keyboard = [];

  // До 6 сессий по 2 в ряд
  let row = [];
  for (const s of sessions.slice(0, 6)) {
    const label = s.label || `Сессия #${s.index}`;
    row.push({ text: label, callback_data: `history:view:${s.sessionId}` });
    if (row.length === 2) {
      keyboard.push(row);
      row = [];
    }
  }
  if (row.length > 0) {
    keyboard.push(row);
  }

  // Кнопка закрытия
  keyboard.push([
    { text: '✖️ Закрыть', callback_data: 'history:close' }
  ]);

  return { reply_markup: { inline_keyboard: keyboard } };
}

/**
 * Клавиатура для /back — подтверждение возврата
 */
function backKeyboard() {
  return {
    reply_markup: {
      inline_keyboard: [
        [
          { text: '⬅️ Вернуться', callback_data: 'back:confirm' },
          { text: '↩️ Остаться', callback_data: 'back:abort' }
        ]
      ]
    }
  };
}

// ==================== Основные обработчики ====================

class SessionCommands {
  /**
   * @param {object} deps
   * @param {object} deps.sessionManager - экземпляр SessionManager
   * @param {object} deps.templateEngine - экземпляр TemplateEngine
   * @param {object} deps.whitelist - экземпляр Whitelist
   * @param {object} deps.surveyEngine - экземпляр SurveyEngine (Story 2.6)
   */
  constructor(deps = {}) {
    this.sessionManager = deps.sessionManager;
    this.templateEngine = deps.templateEngine;
    this.whitelist = deps.whitelist;
    this.surveyEngine = deps.surveyEngine;  // Story 2.6: для /back навигации
    this.logger = createLogger('session-commands');
  }

  /**
   * Проверяет, авторизован ли пользователь.
   * @param {number} telegramId
   * @returns {boolean}
   */
  _isAuthorized(telegramId) {
    if (!this.whitelist) return true;
    return this.whitelist.isWhitelisted(telegramId);
  }

  /**
   * Форматирует дату для отображения пользователю (ru-RU, коротко).
   * @param {string} isoDate
   * @returns {string}
   */
  _formatDate(isoDate) {
    if (!isoDate) return 'неизвестно';
    try {
      return new Date(isoDate).toLocaleDateString('ru-RU', {
        day: 'numeric',
        month: 'long',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
      });
    } catch {
      return isoDate;
    }
  }

  // ==================== /start ====================

  /**
   * Команда /start — проверка активной сессии, resume-диалог или онбординг.
   *
   * Flow:
   *   1. Проверка whitelist
   *   2. Поиск активной сессии
   *   3. Если активная сессия есть → handleResumeDialog
   *   4. Если нет → приветствие + создание новой сессии
   *
   * @param {object} ctx - { msg, connector }
   * @returns {Promise<object>} { action: 'started'|'resumed'|'unauthorized', reply }
   */
  async handleStartCommand(ctx) {
    const { msg, connector } = ctx;
    const chatId = msg.chat.id;
    const fromId = msg.from.id;
    const username = msg.from.username || msg.from.first_name || 'Пользователь';

    // 1. Проверка доступа
    if (!this._isAuthorized(fromId)) {
      const reply = await connector.sendMessage(
        chatId,
        'Извините, у вас нет доступа к этому боту.\n\n' +
        'Это приватный сервис для авторизованных пользователей. ' +
        'Если вы считаете, что доступ должен быть — обратитесь к администратору.'
      );
      return { action: 'unauthorized', reply };
    }

    // 2. Поиск активной сессии
    let activeSession = null;
    if (this.sessionManager) {
      activeSession = await this.sessionManager.getActiveSessionByUser(fromId);
    }

    // 3. Resume-диалог если есть активная сессия
    if (activeSession) {
      return this.handleResumeDialog(ctx, activeSession);
    }

    // 4. Онбординг + новая сессия
    // Создаём сессию сначала — чтобы знать block/subsection
    let session = null;
    if (this.sessionManager) {
      session = await this.sessionManager.createSession(fromId, { username });
      this.logger.info('Session created via /start', {
        telegramId: fromId,
        sessionId: session.sessionId
      });
    }

    // Берём первый вопрос из шаблона
    let firstQuestion = '';
    if (session && this.templateEngine) {
      try {
        const subsection = session.template.subsection || '1.1';
        const sub = this.templateEngine.getSubsection(1, subsection);
        if (sub && sub.questions && sub.questions.L1) {
          firstQuestion = '\n\n❓ *' + sub.questions.L1 + '*';
        }
      } catch (e) {
        this.logger.warn('Could not get first question from template', { error: e.message });
      }
    }

    const greeting = this._getOnboardingMessage(username) + firstQuestion;
    const reply = await connector.sendMessage(chatId, greeting);

    return { action: 'started', reply, session };
  }

  /**
   * Приветственное сообщение для нового пользователя.
   * @param {string} username
   * @returns {string}
   */
  _getOnboardingMessage(username) {
    const greeting = username
      ? `Привет, ${username}! 👋\n\n`
      : 'Привет! 👋\n\n';

    return (
      greeting +
      'Я — *Мамкин аналитик* 🤖\n\n' +
      'Я помогу вам составить *бизнес-требования* высокого уровня зрелости. ' +
      'Это займёт примерно 15–30 минут.\n\n' +
      '📋 *Как это работает:*\n' +
      '1️⃣ Я задам вопросы по 7 разделам\n' +
      '2️⃣ Вы отвечаете своими словами\n' +
      '3️⃣ Если нужно уточнить — я задам дополнительные вопросы\n' +
      '4️⃣ В конце вы получите готовый документ\n\n' +
      '📝 Просто отвечайте на вопросы текстом. Начнём!\n\n' +
      '— *Первый вопрос:*'
    );
  }

  // ==================== Resume Dialog ====================

  /**
   * Диалог восстановления сессии.
   * Показывает пользователю информацию о незавершённой сессии
   * и предлагает продолжить или начать новую.
   *
   * @param {object} ctx - { msg, connector }
   * @param {object} session - активная сессия
   * @returns {Promise<object>} { action, reply }
   */
  async handleResumeDialog(ctx, session) {
    const { msg, connector } = ctx;
    const chatId = msg.chat.id;
    const username = msg.from.username || msg.from.first_name || 'Пользователь';

    const blockNum = session.template ? session.template.block : '?';
    const subsectionId = session.template ? session.template.subsection : '?';
    const lastAnswer = this._getLastAnswer(session);

    // Определяем название блока из шаблона
    let blockName = `Блок ${blockNum}`;
    if (this.templateEngine) {
      try {
        const block = this.templateEngine.getBlock(blockNum);
        if (block && block.name) {
          blockName = block.name;
        }
      } catch {
        // Если шаблон не загружен — используем базовое название
      }
    }

    // Формируем текст карточки восстановления
    let text =
      `👋 С возвращением, ${username}!\n\n` +
      `📋 *${blockName}* (Подраздел ${subsectionId})\n` +
      `У вас есть незавершённая сессия.\n\n` +
      `➡️ *Продолжить* — вернуться к опросу\n` +
      `🆕 *Новая сессия* — начать заново (текущий прогресс будет сохранён)`;

    // Показываем последний ответ, если он есть
    if (lastAnswer) {
      text += `\n\n📝 *Последний ответ:*\n_${lastAnswer}_`;
    }

    const reply = await connector.sendMessage(chatId, text, resumeKeyboard());
    return { action: 'resumed', reply, session };
  }

  /**
   * Извлекает последний ответ пользователя из сессии.
   * @param {object} session
   * @returns {string|null}
   */
  _getLastAnswer(session) {
    if (!session || !session.answers) return null;

    const answerKeys = Object.keys(session.answers);
    if (answerKeys.length === 0) return null;

    // Берём последний по ключу (подразделу) ответ
    const lastKey = answerKeys[answerKeys.length - 1];
    const lastAnswer = session.answers[lastKey];

    if (!lastAnswer) return null;

    // Если ответ — объект, берём text или content
    if (typeof lastAnswer === 'object') {
      return lastAnswer.text || lastAnswer.content || null;
    }

    // Если ответ — строка, обрезаем до 120 символов
    const answerStr = String(lastAnswer);
    return answerStr.length > 120
      ? answerStr.slice(0, 120) + '…'
      : answerStr;
  }

  // ==================== /history ====================

  /**
   * Команда /history — список завершённых сессий пользователя.
   *
   * Flow:
   *   1. Проверка доступа
   *   2. Получение списка завершённых сессий через SessionManager
   *   3. Если сессий нет — информационное сообщение
   *   4. Если есть — список с датами, статусами и кнопками для просмотра
   *
   * @param {object} ctx - { msg, connector }
   * @returns {Promise<object>} { action, reply, sessions }
   */
  async handleHistoryCommand(ctx) {
    const { msg, connector } = ctx;
    const chatId = msg.chat.id;
    const fromId = msg.from.id;

    // 1. Проверка доступа
    if (!this._isAuthorized(fromId)) {
      const reply = await connector.sendMessage(
        chatId,
        'Извините, у вас нет доступа к этому боту.'
      );
      return { action: 'unauthorized', reply };
    }

    // 2. Получение завершённых сессий
    let sessions = [];
    if (this.sessionManager) {
      sessions = await this.sessionManager.listCompletedSessions(fromId);
    }

    // 3. Нет завершённых сессий
    if (!sessions || sessions.length === 0) {
      const reply = await connector.sendMessage(
        chatId,
        '📭 У вас пока нет завершённых сессий.\n\n' +
        'Напишите /start, чтобы начать новый опрос.'
      );
      return { action: 'empty', reply, sessions: [] };
    }

    // 4. Формируем список
    const lines = [
      '📋 *История сессий*\n',
      `У вас *${sessions.length}* завершённ${sessions.length === 1 ? 'ая' : 'ых'} сесси${sessions.length === 1 ? 'я' : 'и'}:\n`
    ];

    const sessionButtons = sessions.map((s, i) => {
      const date = this._formatDate(s.updatedAt);
      const status = s.documentReady ? '✅ Документ готов' : '📝 Черновик';
      const shortId = s.sessionId ? s.sessionId.slice(0, 8) : `#${i + 1}`;
      const label = `#${i + 1}`;

      lines.push(
        `\n*${label}* — от ${date}`,
        `   Статус: ${status}`,
        `   ID: \`${shortId}\``
      );

      return { sessionId: s.sessionId, index: i + 1, label: `#${i + 1}` };
    });

    const text = lines.join('\n');
    const keyboard = historyKeyboard(sessionButtons);
    const reply = await connector.sendMessage(chatId, text, keyboard);

    return { action: 'list', reply, sessions };
  }

  // ==================== /cancel ====================

  /**
   * Команда /cancel — завершение сессии с подтверждением.
   *
   * Flow:
   *   1. Проверка доступа
   *   2. Поиск активной сессии
   *   3. Если нет активной — сообщение
   *   4. Если есть — запрос подтверждения с inline keyboard
   *   5. Подтверждение через callback → save draft → complete session
   *
   * @param {object} ctx - { msg, connector }
   * @returns {Promise<object>} { action, reply, session }
   */
  async handleCancelCommand(ctx) {
    const { msg, connector } = ctx;
    const chatId = msg.chat.id;
    const fromId = msg.from.id;

    // 1. Проверка доступа
    if (!this._isAuthorized(fromId)) {
      const reply = await connector.sendMessage(
        chatId,
        'Извините, у вас нет доступа к этому боту.'
      );
      return { action: 'unauthorized', reply };
    }

    // 2. Поиск активной сессии
    let session = null;
    if (this.sessionManager) {
      session = await this.sessionManager.getActiveSessionByUser(fromId);
    }

    // 3. Нет активной сессии
    if (!session) {
      const reply = await connector.sendMessage(
        chatId,
        '📭 У вас нет активных сессий.\n\n' +
        'Напишите /start, чтобы начать новый опрос.'
      );
      return { action: 'no_session', reply };
    }

    // 4. Запрос подтверждения
    const blockNum = session.template ? session.template.block : '?';
    const subsectionId = session.template ? session.template.subsection : '?';
    const answerCount = session.answers
      ? Object.keys(session.answers).length
      : 0;

    let blockName = `Блок ${blockNum}`;
    if (this.templateEngine) {
      try {
        const block = this.templateEngine.getBlock(blockNum);
        if (block && block.name) blockName = block.name;
      } catch { /* ignore */ }
    }

    const text =
      '⚠️ *Вы уверены, что хотите завершить сессию?*\n\n' +
      `📋 Текущий прогресс: ${blockName} (Подраздел ${subsectionId})\n` +
      `📝 Сохранено ответов: ${answerCount}\n\n` +
      '✅ Черновик будет сохранён, и вы сможете начать новую сессию.\n' +
      '❌ Если хотите продолжить опрос — нажмите «Нет, продолжить».';

    const reply = await connector.sendMessage(chatId, text, cancelConfirmKeyboard());
    return { action: 'pending_confirmation', reply, session };
  }

  /**
   * Обрабатывает подтверждение отмены сессии (callback).
   *
   * @param {object} ctx - { msg, connector, callbackData }
   * @returns {Promise<object>} { action, reply }
   */
  async handleCancelConfirm(ctx) {
    const { msg, connector, callbackData } = ctx;
    const chatId = msg.chat.id || (msg.message && msg.message.chat.id);
    const fromId = msg.from.id;

    if (!this._isAuthorized(fromId)) {
      return { action: 'unauthorized' };
    }

    // Если пользователь отменил отмену
    if (callbackData === 'cancel:abort') {
      const reply = await connector.sendMessage(
        chatId,
        '✅ Продолжаем опрос. Напишите ваш ответ на текущий вопрос.'
      );
      return { action: 'cancellation_aborted', reply };
    }

    // Подтверждение отмены
    if (callbackData === 'cancel:confirm') {
      let session = null;
      if (this.sessionManager) {
        session = await this.sessionManager.getActiveSessionByUser(fromId);
      }

      if (!session) {
        const reply = await connector.sendMessage(
          chatId,
          '📭 Активная сессия не найдена. Возможно, она уже была завершена.'
        );
        return { action: 'no_session', reply };
      }

      // Сохраняем как черновик и завершаем
      await this.sessionManager.completeSession(session.sessionId);

      this.logger.info('Session cancelled by user', {
        telegramId: fromId,
        sessionId: session.sessionId,
        answersCount: session.answers ? Object.keys(session.answers).length : 0
      });

      const reply = await connector.sendMessage(
        chatId,
        '✅ *Сессия завершена.*\n\n' +
        'Ваши ответы сохранены как черновик.\n\n' +
        'Если захотите начать заново — нажмите /start.'
      );
      return { action: 'cancelled', reply, session };
    }

    return { action: 'unknown_callback', callbackData };
  }

  // ==================== /back ====================

  /**
   * Команда /back — возврат к предыдущему подразделу/блоку.
   *
   * Flow:
   *   1. Проверка доступа
   *   2. Поиск активной сессии
   *   3. Если нет активной — сообщение
   *   4. Навигация назад через TemplateEngine
   *   5. Показ последнего сохранённого ответа
   *
   * @param {object} ctx - { msg, connector }
   * @returns {Promise<object>} { action, reply, previousSubsection, previousAnswer }
   */
  async handleBackCommand(ctx, args) {
    const { msg, connector } = ctx;
    const chatId = msg.chat.id;
    const fromId = msg.from.id;

    // 1. Проверка доступа
    if (!this._isAuthorized(fromId)) {
      const reply = await connector.sendMessage(
        chatId,
        'Извините, у вас нет доступа к этому боту.'
      );
      return { action: 'unauthorized', reply };
    }

    // 2. Поиск активной сессии
    let session = null;
    if (this.sessionManager) {
      session = await this.sessionManager.getActiveSessionByUser(fromId);
    }

    // 3. Нет активной сессии
    if (!session) {
      const reply = await connector.sendMessage(
        chatId,
        '📭 У вас нет активной сессии.\n\n' +
        'Напишите /start, чтобы начать новый опрос.'
      );
      return { action: 'no_session', reply };
    }

    // 4. Навигация назад
    const prevSubsection = this._getPreviousSubsection(session);
    if (!prevSubsection) {
      const reply = await connector.sendMessage(
        chatId,
        '⬅️ Вы уже в начале опроса. Нет предыдущих подразделов для возврата.'
      );
      return { action: 'at_start', reply };
    }

    // 5. Получаем последний ответ по предыдущему подразделу
    const prevAnswer = this._getAnswerForSubsection(session, prevSubsection.fullKey);

    // 6. Запрашиваем подтверждение
    let text = `⬅️ *Вернуться к подразделу ${prevSubsection.fullKey}*`;

    if (prevSubsection.name) {
      text += ` — ${prevSubsection.name}`;
    }

    // Story 2.6: Используем фразу "ранее вы ответили" для отображения предыдущего ответа
    if (prevAnswer) {
      text += `\n\n📝 *Ранее вы ответили:*\n_${this._truncateAnswer(prevAnswer)}_`;
    }

    text += '\n\nВы уверены, что хотите вернуться?';

    const reply = await connector.sendMessage(chatId, text, backKeyboard());
    return { action: 'pending_back', reply, previousSubsection: prevSubsection, previousAnswer: prevAnswer };
  }

  /**
   * Обрабатывает подтверждение возврата (callback).
   *
   * @param {object} ctx - { msg, connector, callbackData }
   * @returns {Promise<object>} { action, reply }
   */
  async handleBackConfirm(ctx) {
    const { msg, connector, callbackData } = ctx;
    const chatId = msg.chat.id || (msg.message && msg.message.chat.id);
    const fromId = msg.from.id;

    if (!this._isAuthorized(fromId)) {
      return { action: 'unauthorized' };
    }

    if (callbackData === 'back:abort') {
      const reply = await connector.sendMessage(
        chatId,
        '✅ Остаёмся на текущем вопросе. Напишите ваш ответ.'
      );
      return { action: 'back_aborted', reply };
    }

    if (callbackData === 'back:confirm') {
      let session = null;
      if (this.sessionManager) {
        session = await this.sessionManager.getActiveSessionByUser(fromId);
      }

      if (!session) {
        const reply = await connector.sendMessage(
          chatId,
          '📭 Активная сессия не найдена.'
        );
        return { action: 'no_session', reply };
      }

      // Story 2.6: Используем SurveyEngine.returnToSection для навигации назад
      // Это обеспечивает единую логику: сохранение origin, показ "ранее вы ответили",
      // обновление Session Context
      if (this.surveyEngine) {
        try {
          const result = await this.surveyEngine.handleBackNavigation(session);

          if (result.atStart) {
            const reply = await connector.sendMessage(
              chatId,
              '⬅️ Вы уже в начале опроса. Нет предыдущих подразделов для возврата.'
            );
            return { action: 'at_start', reply };
          }

          // Получаем отформатированное сообщение от SurveyEngine
          const reply = await connector.sendMessage(chatId, result.question);
          return { action: 'back_completed', reply, session: result.session };
        } catch (err) {
          this.logger.error('SurveyEngine back navigation failed', {
            sessionId: session.sessionId,
            error: err.message
          });
          // Fallback: используем старую логику
        }
      }

      // === Fallback: старая логика (без SurveyEngine) ===
      // Выполняем навигацию назад
      const prevSubsection = this._getPreviousSubsection(session);
      if (!prevSubsection) {
        const reply = await connector.sendMessage(
          chatId,
          '⬅️ Вы уже в начале опроса.'
        );
        return { action: 'at_start', reply };
      }

      // Обновляем позицию в сессии
      session.template.block = prevSubsection.blockId;
      session.template.subsection = prevSubsection.fullKey;

      if (this.sessionManager) {
        await this.sessionManager.updateSession(session.sessionId, {
          template: session.template
        });
      }

      // Получаем вопрос для этого подраздела (L1)
      let question = `Давайте вернёмся к разделу "${prevSubsection.name}". Что вы можете добавить?`;
      if (this.templateEngine) {
        try {
          const sub = this.templateEngine.getSubsection(
            prevSubsection.blockId,
            prevSubsection.fullKey
          );
          if (sub && sub.questions && sub.questions.L1) {
            question = sub.questions.L1;
          }
        } catch { /* use default */ }
      }

      const prevAnswer = this._getAnswerForSubsection(session, prevSubsection.fullKey);
      let text = `⬅️ *Вернулись к подразделу ${prevSubsection.fullKey}*`;

      if (prevSubsection.name) {
        text += ` — ${prevSubsection.name}`;
      }

      if (prevAnswer) {
        text += `\n\n📝 *Ранее вы ответили:*\n_${this._truncateAnswer(prevAnswer)}_`;
      }

      text += `\n\n❓ ${question}`;

      const reply = await connector.sendMessage(chatId, text);
      return { action: 'back_completed', reply };
    }

    return { action: 'unknown_callback', callbackData };
  }

  // ==================== Callback обработчик ====================

  /**
   * Единый обработчик callback-запросов от inline-клавиатур.
   * Перенаправляет на соответствующие обработчики.
   *
   * @param {object} ctx - { msg, connector, callbackData }
   * @returns {Promise<object>} результат обработки
   */
  async handleCallback(ctx) {
    const { callbackData } = ctx;

    if (!callbackData) {
      return { action: 'no_callback_data' };
    }

    // cancel:confirm / cancel:abort
    if (callbackData.startsWith('cancel:')) {
      return this.handleCancelConfirm(ctx);
    }

    // back:confirm / back:abort
    if (callbackData.startsWith('back:')) {
      return this.handleBackConfirm(ctx);
    }

    // resume:continue / resume:new
    if (callbackData.startsWith('resume:')) {
      return this._handleResumeCallback(ctx, callbackData);
    }

    // history:view:<sessionId> / history:close
    if (callbackData.startsWith('history:')) {
      return this._handleHistoryCallback(ctx, callbackData);
    }

    return { action: 'unknown_callback', callbackData };
  }

  /**
   * Обработчик callback для resume-диалога.
   * @private
   */
  async _handleResumeCallback(ctx, callbackData) {
    const { msg, connector, callbackQuery } = ctx;
    const chatId = msg.chat ? msg.chat.id : (msg.message ? msg.message.chat.id : null);
    // fromId должен быть из callbackQuery.from (реальный пользователь), а не из msg.from (бот)
    const fromId = (callbackQuery && callbackQuery.from && callbackQuery.from.id) ||
                   (msg.from && msg.from.id);

    if (!this._isAuthorized(fromId)) {
      return { action: 'unauthorized' };
    }

    if (callbackData === 'resume:continue') {
      // Продолжаем активную сессию
      const session = await this.sessionManager.getActiveSessionByUser(fromId);
      if (!session) {
        const reply = await connector.sendMessage(
          chatId,
          '❌ Активная сессия не найдена. Начните новую с /start.'
        );
        return { action: 'no_session', reply };
      }

      let question = 'Продолжаем опрос. Напишите ваш ответ на текущий вопрос.';
      if (this.templateEngine) {
        try {
          const sub = this.templateEngine.getSubsection(
            session.template.block,
            session.template.subsection
          );
          if (sub && sub.questions && sub.questions.L1) {
            question = sub.questions.L1;
          }
        } catch { /* use default */ }
      }

      const reply = await connector.sendMessage(
        chatId,
        `▶️ *Продолжаем опрос*\n\n❓ ${question}`
      );
      return { action: 'resume_continued', reply, session };
    }

    if (callbackData === 'resume:new') {
      // Начинаем новую сессию (старая остаётся как черновик)
      if (this.sessionManager) {
        // Не завершаем старую, просто создаём новую
        await this.sessionManager.createSession(fromId);
      }

      const text = this._getOnboardingMessage(
        msg.from.username || msg.from.first_name || 'Пользователь'
      );
      const reply = await connector.sendMessage(chatId, text);
      return { action: 'resume_new_session', reply };
    }

    return { action: 'unknown_callback', callbackData };
  }

  /**
   * Обработчик callback для истории сессий.
   * @private
   */
  async _handleHistoryCallback(ctx, callbackData) {
    const { msg, connector } = ctx;
    const chatId = msg.chat.id || (msg.message && msg.message.chat.id);
    const fromId = msg.from.id;

    if (!this._isAuthorized(fromId)) {
      return { action: 'unauthorized' };
    }

    if (callbackData === 'history:close') {
      const reply = await connector.sendMessage(
        chatId,
        '✅ История закрыта. Напишите /start, чтобы начать новый опрос.'
      );
      return { action: 'history_closed', reply };
    }

    // history:view:<sessionId>
    const viewMatch = callbackData.match(/^history:view:(.+)$/);
    if (viewMatch) {
      const sessionId = viewMatch[1];

      // Admin override: администратор может просматривать любую сессию
      const isAdmin = this.whitelist && this.whitelist.isAdmin(fromId);
      const session = isAdmin
        ? await this.sessionManager.getSessionForAdmin(sessionId, fromId)
        : await this.sessionManager.getSession(sessionId);

      if (!session) {
        const reply = await connector.sendMessage(
          chatId,
          '❌ Сессия не найдена. Возможно, она была удалена.'
        );
        return { action: 'session_not_found', reply };
      }

      // Проверка: сессия должна принадлежать пользователю (кроме админа)
      if (!isAdmin && session.telegramUserId !== fromId) {
        const reply = await connector.sendMessage(
          chatId,
          '⛔ У вас нет доступа к этой сессии.'
        );
        return { action: 'forbidden', reply };
      }

      const date = this._formatDate(session.updatedAt);
      const answerCount = session.answers
        ? Object.keys(session.answers).length
        : 0;
      const docStatus = session.documentReady
        ? '✅ Документ готов'
        : '📝 Черновик сохранён';

      let text =
        `📋 *Сессия ${sessionId.slice(0, 8)}*\n\n` +
        `📅 Завершена: ${date}\n` +
        `📝 Статус: ${docStatus}\n` +
        `💬 Ответов: ${answerCount}\n`;

      if (session.documentReady && session.documentUrl) {
        text += `\n🔗 Ссылка на документ: ${session.documentUrl}`;
      }

      const reply = await connector.sendMessage(chatId, text);
      return { action: 'history_viewed', reply, session };
    }

    return { action: 'unknown_callback', callbackData };
  }

  // ==================== Навигация ====================

  /**
   * Определяет предыдущий подраздел относительно текущей позиции в сессии.
   *
   * @param {object} session - текущая сессия
   * @returns {object|null} { blockId, fullKey, name } или null, если мы в начале
   */
  _getPreviousSubsection(session) {
    if (!session || !session.template) return null;
    if (!this.templateEngine) return null;

    const currentBlock = session.template.block || 1;
    const currentSub = session.template.subsection || '1.1';

    // Ищем все подразделы в порядке обхода
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

  /**
   * Извлекает ответ для указанного подраздела из сессии.
   *
   * @param {object} session
   * @param {string} subsectionKey — '1.1', '2.3' и т.д.
   * @returns {string|null}
   */
  _getAnswerForSubsection(session, subsectionKey) {
    if (!session || !session.answers) return null;

    const answer = session.answers[subsectionKey];
    if (!answer) return null;

    if (typeof answer === 'object') {
      return answer.text || answer.content || JSON.stringify(answer);
    }

    return String(answer);
  }

  /**
   * Обрезает ответ для отображения (макс 200 символов).
   * @param {string} answer
   * @returns {string}
   */
  _truncateAnswer(answer) {
    if (!answer) return '';
    return answer.length > 200 ? answer.slice(0, 200) + '…' : answer;
  }
}

// ==================== Экспорт ====================

module.exports = SessionCommands;
module.exports.cancelConfirmKeyboard = cancelConfirmKeyboard;
module.exports.resumeKeyboard = resumeKeyboard;
module.exports.historyKeyboard = historyKeyboard;
module.exports.backKeyboard = backKeyboard;
