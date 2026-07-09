/**
 * Session Manager — управление сессиями пользователей
 *
 * Файловое JSON-хранилище сессий с AES-256-GCM шифрованием.
 * Хранение: session-storage/active/ (черновики) и session-storage/completed/ (завершённые)
 * Шифрование: AES-256 через crypto.js
 * Locking: сериализация конкурентных записей через per-session promise chain
 * Транзакционность: write to temp → rename
 *
 * Внешние зависимости: lib/crypto.js, lib/logger.js, path, fs
 */

const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const CryptoService = require('./crypto');
const { createLogger } = require('./logger');

const SESSION_ID_LENGTH = 16; // bytes для UUID сессии

class SessionManager {
  /**
   * @param {object} config
   * @param {string} config.storagePath - Базовый путь к session-storage
   * @param {boolean} [config.allowEmptyKey=false] - Разрешить пустой ключ (тесты)
   * @param {number} [config.lockTimeout=5000] - Таймаут блокировки (мс)
   */
  constructor(config = {}) {
    const cfg = config.session || config;

    this.storagePath = cfg.storagePath || path.join(
      __dirname, '..', 'session-storage'
    );
    this.activeDir = path.join(this.storagePath, 'active');
    this.completedDir = path.join(this.storagePath, 'completed');
    this.allowEmptyKey = cfg.allowEmptyKey === true;
    this.lockTimeout = cfg.lockTimeout || 5000;

    this.logger = createLogger('session-manager');

    // Крипто-сервис для шифрования
    this.crypto = new CryptoService({
      key: cfg.encryptionKey,
      allowEmptyKey: this.allowEmptyKey
    });

    // Per-session locks: { sessionId: PromiseChain }
    this._locks = {};

    // Убедиться, что директории существуют
    this._ensureDirectories();

    this.logger.info('SessionManager initialized', {
      storagePath: this.storagePath,
      encryptionEnabled: !!process.env.SESSION_ENCRYPTION_KEY || !!cfg.encryptionKey
    });
  }

  // ==================== Public API ====================

  /**
   * Создаёт новую сессию
   * @param {number} telegramUserId - Telegram ID пользователя
   * @param {object} [options]
   * @param {string} [options.username] - Имя пользователя (опционально)
   * @returns {Promise<object>} Объект сессии
   */
  async createSession(telegramUserId, options = {}) {
    const sessionId = this._generateSessionId();
    const now = new Date().toISOString();

    const session = {
      sessionId,
      telegramUserId,
      username: options.username || null,
      status: 'in_progress',
      createdAt: now,
      updatedAt: now,
      template: {
        block: 1,
        subsection: '1.1',
        depth: 'L1'
      },
      answers: {},
      risks: [],
      documentReady: false,
      qualityGate: {
        approved: false,
        issues: []
      }
    };

    await this._writeSessionFile(session);
    this.logger.info('Session created', { sessionId, telegramUserId });

    return session;
  }

  /**
   * Загружает сессию по ID
   * @param {string} sessionId - ID сессии
   * @returns {Promise<object|null>} Объект сессии или null
   */
  async getSession(sessionId) {
    return this.loadSession(sessionId);
  }

  /**
   * Загружает сессию по ID
   * @param {string} sessionId - ID сессии
   * @returns {Promise<object|null>} Объект сессии или null
   */
  async loadSession(sessionId) {
    // Проверяем active/
    const activePath = this._sessionFilePath(sessionId, 'active');
    if (fs.existsSync(activePath)) {
      return this._readSessionFile(activePath);
    }

    // Проверяем completed/
    const completedPath = this._sessionFilePath(sessionId, 'completed');
    if (fs.existsSync(completedPath)) {
      return this._readSessionFile(completedPath);
    }

    this.logger.warn('Session not found', { sessionId });
    return null;
  }

  /**
   * Загружает активную сессию по Telegram ID пользователя
   * Если у пользователя только одна активная сессия — возвращает её.
   * Если несколько — возвращает последнюю по updatedAt.
   * @param {number} telegramUserId
   * @returns {Promise<object|null>} Объект сессии или null
   */
  async getActiveSessionByUser(telegramUserId) {
    const sessions = await this.listActiveSessions(telegramUserId);

    if (sessions.length === 0) return null;

    // Сортируем по updatedAt (последняя активная)
    sessions.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
    return sessions[0];
  }

  /**
   * Сохраняет (обновляет) сессию
   * @param {object} session - Объект сессии с sessionId
   * @returns {Promise<object>} Обновлённая сессия
   */
  async saveSession(session) {
    return this.updateSession(session.sessionId, session);
  }

  /**
   * Обновляет данные сессии
   * @param {string} sessionId - ID сессии
   * @param {object} updates - Поля для обновления (частичный merge)
   * @returns {Promise<object>} Обновлённая сессия
   */
  async updateSession(sessionId, updates) {
    return this._withLock(sessionId, async () => {
      const session = await this.loadSession(sessionId);
      if (!session) {
        throw new Error(`Session not found: ${sessionId}`);
      }

      // Глубокий мерж обновлений
      const updated = this._deepMerge(session, updates);

      // Всегда обновляем timestamp
      updated.updatedAt = new Date().toISOString();

      await this._writeSessionFile(updated);
      this.logger.debug('Session updated', { sessionId, status: updated.status });

      return updated;
    });
  }

  /**
   * Завершает сессию: перемещает из active/ в completed/
   * @param {string} sessionId - ID сессии
   * @returns {Promise<object>} Завершённая сессия
   */
  async completeSession(sessionId) {
    return this._withLock(sessionId, async () => {
      const session = await this.loadSession(sessionId);
      if (!session) {
        throw new Error(`Session not found: ${sessionId}`);
      }

      if (session.status === 'completed') {
        this.logger.warn('Session already completed', { sessionId });
        return session;
      }

      session.status = 'completed';
      session.updatedAt = new Date().toISOString();

      // Записываем в completed/
      const activePath = this._sessionFilePath(sessionId, 'active');
      const completedPath = this._sessionFilePath(sessionId, 'completed');

      // Сначала пишем новую версию в completed/
      const encrypted = this._serializeSession(session);
      const tempPath = completedPath + '.tmp';

      try {
        fs.writeFileSync(tempPath, encrypted, 'utf8');
        fs.renameSync(tempPath, completedPath);

        // Удаляем из active/
        if (fs.existsSync(activePath)) {
          fs.unlinkSync(activePath);
        }
      } catch (err) {
        // Если что-то пошло не так — чистим temp
        if (fs.existsSync(tempPath)) {
          fs.unlinkSync(tempPath);
        }
        throw new Error(`Failed to complete session: ${err.message}`);
      }

      this.logger.info('Session completed', { sessionId });
      return session;
    });
  }

  /**
   * Список активных сессий для пользователя
   * @param {number} telegramUserId
   * @returns {Promise<object[]>} Массив сессий
   */
  async listActiveSessions(telegramUserId) {
    const sessions = [];
    const files = this._listSessionFiles('active');

    for (const file of files) {
      try {
        const session = this._readSessionFileSync(file);
        if (session && session.telegramUserId === telegramUserId) {
          sessions.push(session);
        }
      } catch (err) {
        this.logger.warn('Error reading session file', {
          file,
          error: err.message
        });
      }
    }

    return sessions;
  }

  /**
   * Список завершённых сессий для пользователя
   * @param {number} telegramUserId
   * @returns {Promise<object[]>} Массив сессий
   */
  async listCompletedSessions(telegramUserId) {
    const sessions = [];
    const files = this._listSessionFiles('completed');

    for (const file of files) {
      try {
        const session = this._readSessionFileSync(file);
        if (session && session.telegramUserId === telegramUserId) {
          sessions.push(session);
        }
      } catch (err) {
        this.logger.warn('Error reading completed session file', {
          file,
          error: err.message
        });
      }
    }

    // Сортируем по updatedAt (сначала новые)
    sessions.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
    return sessions;
  }

  /**
   * Получает все сессии пользователя (активные + завершённые)
   * @param {number} telegramUserId
   * @returns {Promise<object[]>}
   */
  async getUserSessions(telegramUserId) {
    const [active, completed] = await Promise.all([
      this.listActiveSessions(telegramUserId),
      this.listCompletedSessions(telegramUserId)
    ]);

    return [...active, ...completed];
  }

  /**
   * Список ВСЕХ активных сессий (без фильтрации по userId).
   * Используется администратором для просмотра любых сессий.
   * @returns {Promise<object[]>}
   */
  async listAllActiveSessions() {
    const sessions = [];
    const files = this._listSessionFiles('active');

    for (const file of files) {
      try {
        const session = this._readSessionFileSync(file);
        if (session) {
          sessions.push(session);
        }
      } catch (err) {
        this.logger.warn('Error reading session file', {
          file,
          error: err.message
        });
      }
    }

    return sessions;
  }

  /**
   * Список ВСЕХ завершённых сессий (без фильтрации по userId).
   * Используется администратором для просмотра любых сессий.
   * @returns {Promise<object[]>}
   */
  async listAllCompletedSessions() {
    const sessions = [];
    const files = this._listSessionFiles('completed');

    for (const file of files) {
      try {
        const session = this._readSessionFileSync(file);
        if (session) {
          sessions.push(session);
        }
      } catch (err) {
        this.logger.warn('Error reading completed session file', {
          file,
          error: err.message
        });
      }
    }

    sessions.sort((a, b) => new Date(b.updatedAt) - new Date(a.updatedAt));
    return sessions;
  }

  /**
   * Загружает сессию по ID без проверки владельца.
   * Используется администратором для просмотра любой сессии.
   * @param {string} sessionId
   * @param {number} adminUserId - ID администратора (для логирования)
   * @returns {Promise<object|null>}
   */
  async getSessionForAdmin(sessionId, adminUserId) {
    const session = await this.loadSession(sessionId);

    if (session) {
      this.logger.info('Admin accessed session', {
        adminUserId,
        targetSessionId: sessionId,
        targetUser: session.telegramUserId
      });
    }

    return session;
  }

  /**
   * Восстанавливает сессии после перезапуска — все in_progress → recovered
   * @returns {Promise<number>} Количество восстановленных сессий
   */
  async recoverSessions() {
    let count = 0;
    const files = this._listSessionFiles('active');

    for (const file of files) {
      try {
        const session = this._readSessionFileSync(file);
        if (session && session.status === 'in_progress') {
          session.status = 'recovered';
          session.updatedAt = new Date().toISOString();
          await this._writeSessionFile(session);
          count++;
          this.logger.info('Session recovered', { sessionId: session.sessionId });
        }
      } catch (err) {
        this.logger.warn('Error recovering session', {
          file,
          error: err.message
        });
      }
    }

    if (count > 0) {
      this.logger.info('Sessions recovered after restart', { count });
    }

    return count;
  }

  // ==================== Внутренние методы ====================

  /**
   * Генерирует уникальный ID сессии
   * @returns {string}
   */
  _generateSessionId() {
    return crypto.randomBytes(SESSION_ID_LENGTH).toString('hex');
  }

  /**
   * Формирует путь к файлу сессии
   * @param {string} sessionId
   * @param {'active'|'completed'} dir
   * @returns {string}
   */
  _sessionFilePath(sessionId, dir) {
    return path.join(
      dir === 'active' ? this.activeDir : this.completedDir,
      `session_${sessionId}.json`
    );
  }

  /**
   * Убеждается, что директории существуют
   */
  _ensureDirectories() {
    for (const dir of [this.activeDir, this.completedDir]) {
      if (!fs.existsSync(dir)) {
        fs.mkdirSync(dir, { recursive: true });
      }
    }
  }

  /**
   * Список файлов сессий в директории
   * @param {'active'|'completed'} dir
   * @returns {string[]}
   */
  _listSessionFiles(dir) {
    const targetDir = dir === 'active' ? this.activeDir : this.completedDir;

    if (!fs.existsSync(targetDir)) return [];

    try {
      return fs.readdirSync(targetDir)
        .filter(f => f.startsWith('session_') && f.endsWith('.json'))
        .map(f => path.join(targetDir, f));
    } catch (err) {
      this.logger.error('Error listing session files', {
        dir: targetDir,
        error: err.message
      });
      return [];
    }
  }

  /**
   * Сериализует сессию в зашифрованную строку
   * @param {object} session
   * @returns {string}
   */
  _serializeSession(session) {
    const json = JSON.stringify(session, null, 2);
    return this.crypto.encrypt(json);
  }

  /**
   * Десериализует зашифрованную строку в объект сессии
   * @param {string} data
   * @returns {object}
   */
  _deserializeSession(data) {
    if (!data) return null;
    const json = this.crypto.decrypt(data);
    return JSON.parse(json);
  }

  /**
   * Читает и дешифрует файл сессии (async)
   * @param {string} filePath
   * @returns {Promise<object>}
   */
  async _readSessionFile(filePath) {
    const data = await fs.promises.readFile(filePath, 'utf8');
    return this._deserializeSession(data);
  }

  /**
   * Читает и дешифрует файл сессии (sync, для batch-операций)
   * @param {string} filePath
   * @returns {object}
   */
  _readSessionFileSync(filePath) {
    if (!fs.existsSync(filePath)) return null;

    try {
      const data = fs.readFileSync(filePath, 'utf8');
      return this._deserializeSession(data);
    } catch (err) {
      this.logger.error('Error reading session file', {
        filePath,
        error: err.message
      });
      return null;
    }
  }

  /**
   * Записывает сессию в файл с транзакционной записью
   * (write to temp → rename → удаление старого временного файла)
   * @param {object} session
   */
  async _writeSessionFile(session) {
    const filePath = this._sessionFilePath(
      session.sessionId,
      session.status === 'completed' ? 'completed' : 'active'
    );
    const tempPath = filePath + '.tmp.' + process.pid;

    const encrypted = this._serializeSession(session);

    // Транзакционная запись
    try {
      fs.writeFileSync(tempPath, encrypted, 'utf8');
      fs.renameSync(tempPath, filePath);
    } catch (err) {
      // Очищаем временный файл при ошибке
      try {
        if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
      } catch (_) {
        // ignore cleanup errors
      }
      throw new Error(`Failed to write session file: ${err.message}`);
    }
  }

  /**
   * Per-session блокировка для сериализации конкурентных записей
   * @param {string} sessionId
   * @param {Function} fn - Асинхронная функция для выполнения под блокировкой
   * @returns {Promise<any>}
   */
  _withLock(sessionId, fn) {
    if (!this._locks[sessionId]) {
      this._locks[sessionId] = Promise.resolve();
    }

    const acquire = (this._locks[sessionId]).then(async () => {
      // Таймаут блокировки
      const timeout = new Promise((_, reject) => {
        setTimeout(() => reject(
          new Error(`Lock timeout for session: ${sessionId}`)
        ), this.lockTimeout);
      });

      const result = await Promise.race([fn(), timeout]);
      return result;
    });

    this._locks[sessionId] = acquire.catch(err => {
      this.logger.error('Lock operation failed', {
        sessionId,
        error: err.message
      });
      throw err;
    });

    return this._locks[sessionId];
  }

  /**
   * Глубокий мерж: копирует обновления в целевой объект
   * @param {object} target - Целевой объект
   * @param {object} updates - Обновления
   * @returns {object} Новый объект (не мутирует оригинал)
   */
  _deepMerge(target, updates) {
    // Создаём глубокую копию
    const result = JSON.parse(JSON.stringify(target));

    for (const [key, value] of Object.entries(updates)) {
      if (value === null || value === undefined) {
        // Пропускаем null/undefined (не удаляем поля)
        continue;
      }

      if (this._isPlainObject(value) && this._isPlainObject(result[key])) {
        // Рекурсивный мерж для вложенных объектов
        result[key] = this._deepMerge(result[key], value);
      } else {
        result[key] = value;
      }
    }

    return result;
  }

  /**
   * Проверяет, является ли значение простым объектом
   * @param {*} value
   * @returns {boolean}
   */
  _isPlainObject(value) {
    return value !== null &&
      typeof value === 'object' &&
      !Array.isArray(value) &&
      value.constructor === Object;
  }
}

module.exports = SessionManager;
