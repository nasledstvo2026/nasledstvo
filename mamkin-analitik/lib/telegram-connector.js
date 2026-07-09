/**
 * Telegram Bot Connector — интеграция с Telegram Bot API
 *
 * Story 1.4 — Интеграция Telegram Bot Connector и Whitelist
 *
 * Компонент для получения и обработки обновлений от Telegram Bot API.
 * Использует webhook-режим (порт 8080, /webhook), так как бот работает
 * через OpenClaw на VPS с Cloudflare Tunnel.
 *
 * API:
 *   TelegramConnector.initialize(options) — инициализация: загрузка whitelist,
 *     получение информации о боте, установка webhook
 *   processUpdate(update) — обработка входящего обновления (сообщения, команды)
 *   handleStartCommand(msg) — команда /start: whitelist → онбординг
 *   handleAddUser(msg, args) — команда /adduser: добавление в whitelist
 *   handleRemoveUser(msg, args) — команда /removeuser: удаление из whitelist
 *   sendMessage(chatId, text, options) — отправка сообщения
 *   getWebhookInfo() — проверка статуса webhook
 *
 * Формат команд:
 *   /start — запуск бота
 *   /adduser <telegram_id> [username] — добавить пользователя (только админ)
 *   /removeuser <telegram_id> — удалить пользователя (только админ)
 */

const { createLogger } = require('./logger');
const Whitelist = require('./whitelist');
const SessionManager = require('./session-manager');
const SessionCommands = require('./session-commands');
const SurveyEngine = require('./survey-engine');

const TELEGRAM_API_BASE = 'https://api.telegram.org/bot';

class TelegramConnector {
  /**
   * @param {object} [options]
   * @param {string} [options.botToken] — токен Telegram Bot (override env)
   * @param {object} [options.sessionManager] — экземпляр SessionManager
   * @param {object} [options.whitelist] — экземпляр Whitelist
   * @param {string} [options.whitelistPath] — путь к whitelist.json
   * @param {number[]} [options.adminIds] — ID администраторов
   * @param {number} [options.pollIntervalMs=10000] — интервал polling (fallback)
   * @param {boolean} [options.skipInit=false] — пропустить инициализацию (тесты)
   */
  constructor(options = {}) {
    this.logger = createLogger('telegram-connector');

    // Bot token
    this.botToken = options.botToken || process.env.TELEGRAM_BOT_TOKEN || '';

    // API base URL
    this.apiBase = `${TELEGRAM_API_BASE}${this.botToken}`;

    // Session Manager
    this.sessionManager = options.sessionManager || null;

    // Template Engine (для навигации по шаблону)
    this.templateEngine = options.templateEngine || null;

    // Whitelist
    this.whitelist = options.whitelist || new Whitelist({
      whitelistPath: options.whitelistPath,
      adminIds: options.adminIds
    });

    // Survey Engine (Story 1.6 — обработка ответов во время опроса)
    this.surveyEngine = options.surveyEngine || null;
    if (!this.surveyEngine && this.sessionManager && this.templateEngine) {
      this.surveyEngine = new SurveyEngine({
        sessionManager: this.sessionManager,
        templateEngine: this.templateEngine
      });
    }

    // Session Commands
    this.sessionCommands = new SessionCommands({
      sessionManager: this.sessionManager,
      templateEngine: this.templateEngine,
      surveyEngine: this.surveyEngine,
      whitelist: this.whitelist
    });

    // Состояние
    this._initialized = false;
    this._botInfo = null;
    this._lastUpdateId = 0;

    // Polling (fallback если webhook не работает)
    this.pollIntervalMs = options.pollIntervalMs || 10000;
    this._pollTimer = null;

    // Пропустить автоматическую инициализацию (для тестов)
    this.skipInit = options.skipInit === true;
  }

  /**
   * Инициализирует коннектор: загружает whitelist, получает информацию о боте,
   * устанавливает webhook.
   *
   * @returns {Promise<TelegramConnector>}
   */
  async initialize() {
    if (this.skipInit) {
      this._initialized = true;
      return this;
    }

    // 1. Загрузка whitelist
    await this.whitelist.load();
    this.logger.info('Whitelist loaded', {
      count: this.whitelist.getCount(),
      admins: this.whitelist.getAdminIds()
    });

    // 2. Получение информации о боте
    try {
      this._botInfo = await this._apiCall('getMe');
      this.logger.info('Bot info retrieved', {
        username: this._botInfo.username,
        id: this._botInfo.id
      });
    } catch (err) {
      this.logger.error('Failed to get bot info', { error: err.message });
      throw new Error(`Telegram: не удалось подключиться к Bot API: ${err.message}`);
    }

    this._initialized = true;
    return this;
  }

  /**
   * Обрабатывает входящее обновление от Telegram.
   * Может быть вызвана из webhook-обработчика или из polling-цикла.
   *
   * @param {object} update — объект обновления от Telegram Bot API
   * @returns {Promise<object|null>} Результат обработки
   */
  async processUpdate(update) {
    if (!update) return null;

    // Запоминаем последний ID для polling
    if (update.update_id && update.update_id > this._lastUpdateId) {
      this._lastUpdateId = update.update_id;
    }

    // Сообщение
    if (update.message) {
      return this._handleMessage(update.message);
    }

    // Callback query (inline keyboard)
    if (update.callback_query) {
      return this._handleCallbackQuery(update.callback_query);
    }

    // Неподдерживаемый тип обновления
    this.logger.debug('Unhandled update type', {
      update_id: update.update_id,
      keys: Object.keys(update)
    });

    return null;
  }

  // ==================== Команды ====================

  /**
   * Обрабатывает команду /start.
   *
   * Flow:
   *   1. Проверка whitelist
   *   2. Если не авторизован → "Извините, у вас нет доступа"
   *   3. Если авторизован → идентификация → онбординг / восстановление сессии
   *
   * @param {object} msg — объект сообщения Telegram
   * @returns {Promise<object>} Результат отправки сообщения
   */
  async handleStartCommand(msg) {
    const chatId = msg.chat.id;
    const fromId = msg.from.id;
    const username = msg.from.username || msg.from.first_name || null;

    // Шаг 1: Проверка whitelist
    if (!this.whitelist.isWhitelisted(fromId)) {
      const reply = await this.sendMessage(
        chatId,
        'Извините, у вас нет доступа к этому боту.\n\n' +
        'Это приватный сервис для авторизованных пользователей. ' +
        'Если вы считаете, что доступ должен быть — обратитесь к администратору.'
      );
      this.logger.info('Unauthorized access attempt', {
        telegramId: fromId,
        username: username || '(no name)',
        chatId
      });
      return reply;
    }

    // Шаг 2: Делегируем в SessionCommands для resume-диалога / онбординга
    const result = await this.sessionCommands.handleStartCommand({ msg, connector: this });
    return result.reply;
  }

  /**
   * Обрабатывает команду /adduser <telegram_id> [username]
   * Только для администраторов.
   *
   * @param {object} msg — объект сообщения Telegram
   * @param {string[]} args — аргументы команды
   * @returns {Promise<object>} Результат отправки сообщения
   */
  async handleAddUser(msg, args) {
    const chatId = msg.chat.id;
    const fromId = msg.from.id;
    const fromName = msg.from.username || msg.from.first_name || 'Unknown';

    // Проверка прав администратора
    if (!this.whitelist.isAdmin(fromId)) {
      return this.sendMessage(
        chatId,
        '⛔ У вас нет прав для выполнения этой команды.'
      );
    }

    // Валидация аргументов
    if (!args || args.length < 1) {
      return this.sendMessage(
        chatId,
        '❌ Использование: `/adduser <telegram_id> [имя]`\n\n' +
        'Пример: `/adduser 123456789 Иван Иванов`',
        { parse_mode: 'HTML' }
      );
    }

    const targetId = parseInt(args[0], 10);
    if (isNaN(targetId) || targetId <= 0) {
      return this.sendMessage(
        chatId,
        `❌ Невалидный Telegram ID: \`${args[0]}\`. ID должен быть числом.`,
        { parse_mode: 'HTML' }
      );
    }

    const targetUsername = args.slice(1).join(' ') || null;

    try {
      const entry = await this.whitelist.addUser(targetId, fromId, targetUsername);
      return this.sendMessage(
        chatId,
        `✅ Пользователь добавлен в белый список.\n\n` +
        `🆔 ID: \`${entry.telegramId}\`\n` +
        `👤 Имя: ${entry.username || '(не указано)'}\n` +
        `📅 Добавлен: ${new Date(entry.addedAt).toLocaleString('ru-RU')}`,
        { parse_mode: 'HTML' }
      );
    } catch (err) {
      return this.sendMessage(
        chatId,
        `❌ Ошибка: ${err.message}`
      );
    }
  }

  /**
   * Обрабатывает команду /removeuser <telegram_id>
   * Только для администраторов.
   *
   * Важно: активные сессии удалённого пользователя НЕ прерываются
   * (согласно AC Story 1.4).
   *
   * @param {object} msg — объект сообщения Telegram
   * @param {string[]} args — аргументы команды
   * @returns {Promise<object>} Результат отправки сообщения
   */
  async handleRemoveUser(msg, args) {
    const chatId = msg.chat.id;
    const fromId = msg.from.id;

    // Проверка прав администратора
    if (!this.whitelist.isAdmin(fromId)) {
      return this.sendMessage(
        chatId,
        '⛔ У вас нет прав для выполнения этой команды.'
      );
    }

    // Валидация аргументов
    if (!args || args.length < 1) {
      return this.sendMessage(
        chatId,
        '❌ Использование: `/removeuser <telegram_id>`\n\n' +
        'Пример: `/removeuser 123456789`',
        { parse_mode: 'HTML' }
      );
    }

    const targetId = parseInt(args[0], 10);
    if (isNaN(targetId) || targetId <= 0) {
      return this.sendMessage(
        chatId,
        `❌ Невалидный Telegram ID: \`${args[0]}\``,
        { parse_mode: 'HTML' }
      );
    }

    // Проверка: нельзя удалить администратора через /removeuser
    if (this.whitelist.isAdmin(targetId)) {
      return this.sendMessage(
        chatId,
        '⛔ Нельзя удалить администратора из белого списка через эту команду.'
      );
    }

    // Получаем информацию до удаления
    const userInfo = this.whitelist.getUser(targetId);

    const removed = await this.whitelist.removeUser(targetId);
    if (removed) {
      this.logger.info('User removed from whitelist by admin', {
        targetId,
        removedBy: fromId
      });

      return this.sendMessage(
        chatId,
        `✅ Пользователь удалён из белого списка.\n\n` +
        `🆔 ID: \`${targetId}\`\n` +
        `👤 Имя: ${(userInfo && userInfo.username) || '(не указано)'}\n\n` +
        `📌 *Активные сессии пользователя не прерваны.* ` +
        `Пользователь сможет завершить начатые сессии, но новые начать не сможет.`,
        { parse_mode: 'HTML' }
      );
    } else {
      return this.sendMessage(
        chatId,
        `❌ Пользователь \`${targetId}\` не найден в белом списке.`,
        { parse_mode: 'HTML' }
      );
    }
  }

  /**
   * Отправляет сообщение в Telegram чат.
   *
   * @param {number|string} chatId — ID чата
   * @param {string} text — Текст сообщения
   * @param {object} [options] — Дополнительные параметры (parse_mode и т.д.)
   * @returns {Promise<object>} Ответ от Telegram API
   */
  async sendMessage(chatId, text, options = {}) {
    const body = {
      chat_id: chatId,
      text: text,
      parse_mode: options.parse_mode || 'HTML',
      disable_web_page_preview: options.disable_web_page_preview !== false,
      ...options
    };

    // Если Markdown, убираем потенциально проблемные символы
    if (body.parse_mode === 'HTML') {
      body.text = this._sanitizeMarkdown(body.text);
    }

    return this._apiCall('sendMessage', body);
  }

  /**
   * Получение информации о текущем пользователе по его сообщению.
   *
   * @param {object} msg — объект сообщения Telegram
   * @returns {object} { telegramId, username, firstName, lastName, isAdmin, isWhitelisted }
   */
  extractUserInfo(msg) {
    if (!msg || !msg.from) return null;

    const from = msg.from;
    const telegramId = from.id;

    return {
      telegramId,
      username: from.username || null,
      firstName: from.first_name || null,
      lastName: from.last_name || null,
      isAdmin: this.whitelist.isAdmin(telegramId),
      isWhitelisted: this.whitelist.isWhitelisted(telegramId),
      languageCode: from.language_code || null
    };
  }

  /**
   * Проверяет статус webhook.
   * @returns {Promise<object>}
   */
  async getWebhookInfo() {
    return this._apiCall('getWebhookInfo');
  }

  /**
   * Устанавливает webhook URL.
   * @param {string} url — URL для webhook
   * @param {object} [options] — опции (secret_token и т.д.)
   * @returns {Promise<object>}
   */
  async setWebhook(url, options = {}) {
    const body = {
      url: url,
      ...options
    };
    return this._apiCall('setWebhook', body);
  }

  /**
   * Удаляет webhook (переход на polling).
   * @returns {Promise<object>}
   */
  async deleteWebhook() {
    return this._apiCall('deleteWebhook');
  }

  // ==================== Polling (fallback) ====================

  /**
   * Запускает polling-цикл для получения обновлений.
   * Используется как fallback, если webhook не настроен.
   *
   * @param {number} [intervalMs] — интервал опроса (override конструктора)
   */
  startPolling(intervalMs) {
    if (this._pollTimer) {
      clearTimeout(this._pollTimer);
    }

    const interval = intervalMs || this.pollIntervalMs;
    this.logger.info('Starting polling', { intervalMs: interval });

    const poll = async () => {
      try {
        const updates = await this._apiCall('getUpdates', {
          offset: this._lastUpdateId + 1,
          timeout: 30
        });

        if (Array.isArray(updates)) {
          for (const update of updates) {
            await this.processUpdate(update);
          }
        }
      } catch (err) {
        this.logger.error('Polling error', { error: err.message });
      }

      // Планируем следующий polling
      this._pollTimer = setTimeout(poll, interval);
    };

    // Первый запуск
    this._pollTimer = setTimeout(poll, 1000);
  }

  /**
   * Останавливает polling.
   */
  stopPolling() {
    if (this._pollTimer) {
      clearTimeout(this._pollTimer);
      this._pollTimer = null;
    }
    this.logger.info('Polling stopped');
  }

  // ==================== Private Methods ====================

  /**
   * @private
   * Обрабатывает входящее сообщение.
   */
  async _handleMessage(msg) {
    const chatId = msg.chat.id;
    const text = (msg.text || '').trim();
    const fromId = msg.from ? msg.from.id : null;

    if (!text) {
      this.logger.debug('Empty message received', { chatId });
      return null;
    }

    // Распознаём команды
    if (text.startsWith('/')) {
      return this._handleCommand(msg, text);
    }

    // Обычное текстовое сообщение — проверяем whitelist
    if (!fromId || !this.whitelist.isWhitelisted(fromId)) {
      return this.sendMessage(
        chatId,
        'Извините, у вас нет доступа к этому боту.'
      );
    }

    // Если есть активная сессия — обрабатываем через SurveyEngine
    if (this.surveyEngine && this.sessionManager) {
      try {
        const session = await this.sessionManager.getActiveSessionByUser(fromId);
        if (session && (session.status === 'in_progress' || session.status === 'recovered')) {
          // Проверка: нужна ли Session Resume Card (пауза >30 минут)
          if (this.surveyEngine.needsResumeCard(session)) {
            const resumeCard = this.surveyEngine.buildSessionResumeCard(session);
            await this.sendMessage(chatId, resumeCard.text);
          }

          // Обрабатываем ответ через SurveyEngine
          const result = await this.surveyEngine.processAnswer(session, text);
          const updatedSession = result.session;

          // Если была ошибка ФС при сохранении — уведомляем пользователя
          if (result.action === 'error') {
            return this.sendMessage(chatId, result.question);
          }

          // Прогресс-бар
          const progress = result.progress;
          const progressBar = this.surveyEngine ? this.surveyEngine.buildProgressMessage(progress) : this._formatProgressBar(progress);

          if (result.action === 'survey_complete') {
            // Опрос завершён
            const finalText =
              `${progressBar}\n\n` +
              '🎉 *Опрос завершён!* Все разделы пройдены.\n\n' +
              'Я передаю данные составителю для формирования черновика документа. ' +
              'Это займёт несколько секунд.\n\n' +
              'Спасибо за ваши ответы! 🙌';

            return this.sendMessage(chatId, finalText);
          }

          // Получаем текущий вопрос
          const currentQ = this.surveyEngine.getCurrentQuestion(updatedSession);
          const depthIndicator = this._getDepthIndicator(currentQ.depth);

          // Формируем сообщение по UX-структуре:
          // Progress → Depth Indicator → Reflection → Question → Action
          let responseText = progressBar + '\n\n';

          // Depth Indicator для L2/L3
          if (currentQ.depth === 'L2') {
            responseText += '🔍 *Уточним детали.* Чтобы получить более полную картину:\n\n';
          } else if (currentQ.depth === 'L3') {
            responseText += '🔍 *Давайте разберёмся глубже.* Попробуем добраться до сути:\n\n';
          }

          // Reflection (короткая рефлексия последнего ответа)
          const reflection = this._buildReflection(text, currentQ.depth);
          if (reflection) {
            responseText += reflection + '\n\n';
          }

          // Вопрос
          responseText += `❓ ${currentQ.question}`;

          return this.sendMessage(chatId, responseText);
        }
      } catch (err) {
        this.logger.error('Error processing survey answer', {
          chatId,
          fromId,
          error: err.message
        });
        return this.sendMessage(
          chatId,
          '⚠️ Произошла ошибка при обработке ответа. Пожалуйста, попробуйте ещё раз.'
        );
      }
    }

    // Fallback: если нет SurveyEngine или активной сессии
    return this.sendMessage(
      chatId,
      '✅ Сообщение получено.'
    );
  }

  /**
   * @private
   * Обрабатывает команду.
   */
  async _handleCommand(msg, text) {
    const parts = text.split(/\s+/);
    const command = parts[0].toLowerCase();
    const args = parts.slice(1);

    switch (command) {
      case '/start':
      case '/создатьбт':
        return this.handleStartCommand(msg);

      case '/history':
        return this.sessionCommands.handleHistoryCommand({ msg, connector: this });

      case '/back':
        return this.sessionCommands.handleBackCommand({ msg, connector: this }, args);

      case '/adduser':
        return this.handleAddUser(msg, args);

      case '/removeuser':
        return this.handleRemoveUser(msg, args);

      case '/help':
        return this._handleHelpCommand(msg);

      case '/cancel':
        return this.sessionCommands.handleCancelCommand({ msg, connector: this });

      case '/admin':
        return this._handleAdminCommand(msg);

      default:
        return this.sendMessage(
          msg.chat.id,
          `❌ Неизвестная команда: \`${command}\`. Напишите /help для списка команд.`,
          { parse_mode: 'HTML' }
        );
    }
  }

  /**
   * @private
   * Команда /help.
   */
  async _handleHelpCommand(msg) {
    const chatId = msg.chat.id;
    const fromId = msg.from ? msg.from.id : null;

    if (!fromId || !this.whitelist.isWhitelisted(fromId)) {
      return this.sendMessage(chatId, 'Извините, у вас нет доступа к этому боту.');
    }

    const isAdmin = this.whitelist.isAdmin(fromId);

    let helpText =
      '📚 *Доступные команды*\n\n' +
      '👤 *Основные*\n' +
      '• `/создатьбт` — Начать или продолжить сессию (БТ)\n' +
      '• `/history` — История завершённых сессий\n' +
      '• `/back` — Вернуться к предыдущему вопросу\n' +
      '• `/cancel` — Отменить текущую сессию\n' +
      '• `/help` — Эта справка\n\n' +
      '📖 *Что я делаю:*\n' +
      'Я помогаю составить бизнес-требования высокого уровня зрелости. ' +
      'Просто отвечайте на мои вопросы, и я сформирую готовый документ.';

    if (isAdmin) {
      helpText += '\n\n' +
        '🔐 *Административные*\n' +
        '• `/adduser <id> [имя]` — Добавить пользователя в белый список\n' +
        '• `/removeuser <id>` — Удалить пользователя из белого списка\n' +
        '• `/admin` — Информация о белом списке';
    }

    return this.sendMessage(chatId, helpText, { parse_mode: 'HTML' });
  }

  /**
   * @private
   * Команда /cancel — удалена, реализация в SessionCommands.
   * Сохранена для обратной совместимости (если кто-то вызывает напрямую).
   */
  async _handleCancelCommand(msg) {
    const result = await this.sessionCommands.handleCancelCommand({ msg, connector: this });
    return result.reply;
  }

  /**
   * @private
   * Команда /admin — информация о whitelist (только для админов).
   */
  async _handleAdminCommand(msg) {
    const chatId = msg.chat.id;
    const fromId = msg.from ? msg.from.id : null;

    if (!fromId || !this.whitelist.isAdmin(fromId)) {
      return this.sendMessage(chatId, '⛔ У вас нет прав для этой команды.');
    }

    const users = this.whitelist.getAllUsers();
    const admins = this.whitelist.getAdminIds();

    let text =
      `🔐 *Whitelist:* ${users.length} пользователей\n` +
      `👑 *Администраторы:* ${admins.length}\n\n`;

    if (users.length > 0) {
      text += '*Пользователи:*\n';
      for (const user of users.slice(0, 20)) { // Показываем первые 20
        const name = user.username || '(без имени)';
        const added = user.addedAt
          ? new Date(user.addedAt).toLocaleDateString('ru-RU')
          : 'неизвестно';
        text += `• \`${user.telegramId}\` — ${name} (добавлен: ${added})\n`;
      }
      if (users.length > 20) {
        text += `\n*...и ещё ${users.length - 20} пользователей*`;
      }
    } else {
      text += '_Белый список пуст._';
    }

    return this.sendMessage(chatId, text, { parse_mode: 'HTML' });
  }

  /**
   * @private
   * Обрабатывает callback query (inline keyboard).
   * Перенаправляет в SessionCommands для команд управления сессией.
   */
  async _handleCallbackQuery(callbackQuery) {
    if (!callbackQuery) {
      this.logger.warn('Callback query is empty');
      return null;
    }

    const data = callbackQuery.data;
    const msg = callbackQuery.message;
    const fromId = callbackQuery.from ? callbackQuery.from.id : null;

    if (!fromId) {
      this.logger.warn('Callback query without from', { data });
      return null;
    }

    this.logger.info('Callback query received', {
      from: fromId,
      data
    });

    // Ответ на callback (убираем "часики" на кнопке)
    try {
      await this._apiCall('answerCallbackQuery', {
        callback_query_id: callbackQuery.id
      });
    } catch (err) {
      this.logger.warn('Failed to answer callback query', { error: err.message });
    }

    // Перенаправляем callback в SessionCommands
    if (data && (data.startsWith('cancel:') || data.startsWith('back:') ||
        data.startsWith('resume:') || data.startsWith('history:') ||
        data === 'continue' || data === 'new' || data === 'resume_session')) {
      // Важно: передаём callbackQuery.message, не сам callbackQuery — у message есть chat.id
      const cqMsg = callbackQuery.message || callbackQuery;
      const result = await this.sessionCommands.handleCallback({
        msg: cqMsg,
        connector: this,
        callbackData: data,
        callbackQuery // передаём оригинальный callbackQuery для fromId
      });

      // Если обработка вернула reply — отправляем в чат
      if (result && result.reply) {
        return result.reply;
      }

      // Если нет reply, но есть action — отправляем текстовый ответ
      if (result && result.action && !result.reply) {
        const actionMessages = {
          'resume_continued': '▶️ Продолжаем опрос. Напишите ваш ответ на текущий вопрос.',
          'session_created': '✅ Новая сессия создана! Напишите ответ на первый вопрос.',
          'unknown_callback': '❌ Неизвестная команда.',
          'unauthorized': '❌ У вас нет доступа к этой команде.',
          'no_session': '❌ Активная сессия не найдена.',
        };
        if (actionMessages[result.action]) {
          const chatId = cqMsg.chat ? cqMsg.chat.id : (cqMsg.from ? cqMsg.from.id : null);
          if (chatId) {
            return await this.sendMessage(chatId, actionMessages[result.action]);
          }
        }
      }

      return result;
    }

    return null;
  }

  /**
   * @private
   * Возвращает приветственное сообщение для нового пользователя.
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

  /**
   * @private
   * Вызов Telegram Bot API.
   *
   * @param {string} method — метод API (sendMessage, getMe, ...)
   * @param {object} [body] — тело запроса
   * @returns {Promise<object>} Поле result из ответа Telegram
   */
  async _apiCall(method, body) {
    const url = `${this.apiBase}/${method}`;

    // Для простых GET-запросов без тела
    const options = {
      method: body ? 'POST' : 'GET',
      headers: {
        'Content-Type': 'application/json'
      }
    };

    if (body) {
      options.body = JSON.stringify(body);
    }

    try {
      const response = await fetch(url, options);

      if (!response.ok) {
        const errorText = await response.text();
        throw new Error(`HTTP ${response.status}: ${errorText}`);
      }

      const data = await response.json();

      if (!data.ok) {
        throw new Error(`Telegram API error: ${data.description || 'unknown error'}`);
      }

      return data.result;
    } catch (err) {
      if (err.message.includes('Telegram API error') || err.message.includes('HTTP')) {
        throw err;
      }
      throw new Error(`Network error: ${err.message}`);
    }
  }

  /**
   * @private
   * Санитизирует Markdown-строку для Telegram — экранирует спецсимволы
   * внутри обычного текста, чтобы не сломать разметку.
   */
  _sanitizeMarkdown(text) {
    // Экранируем символы, которые Telegram использует для Markdown разметки
    // _, *, [, ], (, ), ~, `, >, #, +, -, =, |, {, }, ., !
    // Но не трогаем уже корректную разметку (парные символы)

    // Пока ничего не делаем — Markdown корректный, Telegram парсит сам.
    // При необходимости можно добавить экранирование.
    return text;
  }

  // ==================== Survey Engine Helpers (Story 1.6) ====================

  /**
   * Форматирует прогресс-бар для отображения в сообщении.
   * @private
   * @param {object} progress
   * @returns {string}
   */
  _formatProgressBar(progress) {
    if (!progress) return '';

    const filled = Math.round((progress.completedSubsections / Math.max(progress.totalSubsections, 1)) * 10);
    const empty = 10 - filled;
    const bar = '█'.repeat(filled) + '░'.repeat(empty);

    return `${bar} ${progress.percent}% | Блок ${progress.block}/${progress.totalBlocks}`;
  }

  /**
   * Возвращает эмодзи-индикатор уровня глубины.
   * @private
   * @param {string} depth — 'L1', 'L2' или 'L3'
   * @returns {string}
   */
  _getDepthIndicator(depth) {
    switch (depth) {
      case 'L2': return '🔍';
      case 'L3': return '🔍🔍';
      default: return '💬';
    }
  }

  /**
   * Строит короткую рефлексию ответа пользователя.
   * Не более 1-2 предложений, ≤ 400 символов весь ответ.
   * @private
   * @param {string} answer — ответ пользователя
   * @param {string} depth — уровень глубины
   * @returns {string|null}
   */
  _buildReflection(answer, depth) {
    if (!answer || answer.trim().length < 10) return null;

    // Берём первую осмысленную фразу (до 120 символов)
    const cleaned = answer.trim().replace(/\s+/g, ' ');
    let snippet = cleaned.slice(0, 100);
    if (cleaned.length > 100) {
      // Обрезаем по последнему пробелу до 100 символов
      const lastSpace = snippet.lastIndexOf(' ');
      if (lastSpace > 20) {
        snippet = snippet.slice(0, lastSpace);
      }
      snippet += '…';
    }

    return `💡 *Вы сказали:* _${snippet}_`;
  }
}

module.exports = TelegramConnector;
