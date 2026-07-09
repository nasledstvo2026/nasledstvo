/**
 * Whitelist — управление белым списком пользователей Telegram
 *
 * Story 1.4 — Интеграция Telegram Bot Connector и whitelist
 *
 * Хранение: data/whitelist.json (JSON-массив записей пользователей)
 * Идентификация: по telegramUserId (number)
 * Администратор: определяется переменной окружения TELEGRAM_ADMIN_IDS
 *   (список ID через запятую, например "12345,67890")
 *
 * API:
 *   Whitelist.load(path?)          — загрузка whitelist.json
 *   isWhitelisted(telegramId)      — проверка доступа
 *   addUser(telegramId, addedBy)   — добавление пользователя
 *   removeUser(telegramId)         — удаление пользователя
 *   isAdmin(telegramId)            — проверка прав администратора
 *   getAllUsers()                  — список всех пользователей
 *   getUser(telegramId)            — информация о конкретном пользователе
 *   getAdminIds()                  — список ID администраторов
 *
 * Формат whitelist.json:
 * [
 *   {
 *     "telegramId": 123456789,
 *     "username": "optional_username",
 *     "addedBy": 111111111,
 *     "addedAt": "2026-07-08T12:00:00.000Z"
 *   }
 * ]
 */

const path = require('path');
const fs = require('fs');
const { createLogger } = require('./logger');

const DEFAULT_WHITELIST_PATH = path.resolve(__dirname, '..', 'data', 'whitelist.json');

class Whitelist {
  /**
   * @param {object} [options]
   * @param {string} [options.whitelistPath] — путь к whitelist.json
   * @param {number[]} [options.adminIds] — ID администраторов (override env)
   * @param {boolean} [options.readOnly=false] — читать без сохранения (тесты)
   */
  constructor(options = {}) {
    this.logger = createLogger('whitelist');
    this.whitelistPath = options.whitelistPath || DEFAULT_WHITELIST_PATH;
    this.readOnly = options.readOnly === true;

    // Администраторы: из options, или из TELEGRAM_ADMIN_IDS, или fallback
    if (options.adminIds && Array.isArray(options.adminIds)) {
      this._adminIds = options.adminIds;
    } else {
      const envAdminIds = process.env.TELEGRAM_ADMIN_IDS || '';
      this._adminIds = envAdminIds
        .split(',')
        .map(id => id.trim())
        .filter(id => id.length > 0)
        .map(id => parseInt(id, 10))
        .filter(id => !isNaN(id));
    }

    /** @private */
    this._users = []; // Массив записей пользователей
    /** @private */
    this._loaded = false;
    /** @private */
    this._userIdSet = new Set(); // Быстрая проверка: Set<telegramId>
  }

  /**
   * Загружает whitelist.json.
   * Если файл не существует, создаёт пустой whitelist.
   *
   * @returns {Promise<Whitelist>}
   */
  async load() {
    const filePath = path.resolve(this.whitelistPath);

    if (!fs.existsSync(filePath)) {
      this.logger.info('Whitelist file not found, creating empty', { filePath });
      this._users = [];
      this._rebuildIndex();
      this._loaded = true;
      if (!this.readOnly) {
        await this._save();
      }
      return this;
    }

    try {
      const raw = fs.readFileSync(filePath, 'utf-8');
      const parsed = JSON.parse(raw);

      if (!Array.isArray(parsed)) {
        throw new Error('whitelist.json должен быть массивом объектов');
      }

      // Валидация каждой записи
      this._users = [];
      for (let i = 0; i < parsed.length; i++) {
        const entry = parsed[i];
        if (!entry || typeof entry !== 'object') {
          this.logger.warn(`Запись whitelist[${i}] не является объектом, пропущена`);
          continue;
        }
        if (typeof entry.telegramId !== 'number') {
          this.logger.warn(
            `Запись whitelist[${i}]: telegramId должен быть числом, пропущена`
          );
          continue;
        }
        // Нормализуем запись
        this._users.push({
          telegramId: entry.telegramId,
          username: entry.username || null,
          addedBy: entry.addedBy || null,
          addedAt: entry.addedAt || new Date().toISOString()
        });
      }

      this._rebuildIndex();
      this._loaded = true;
      this.logger.info('Whitelist loaded', { count: this._users.length });
    } catch (err) {
      this.logger.error('Failed to load whitelist', {
        filePath,
        error: err.message
      });
      throw new Error(`Whitelist: ошибка загрузки: ${err.message}`);
    }

    return this;
  }

  // ==================== Public API ====================

  /**
   * Проверяет, есть ли пользователь в белом списке.
   * @param {number} telegramId — Telegram ID пользователя
   * @returns {boolean}
   */
  isWhitelisted(telegramId) {
    this._ensureLoaded();
    return this._userIdSet.has(telegramId);
  }

  /**
   * Добавляет пользователя в белый список.
   *
   * @param {number} telegramId — Telegram ID
   * @param {number} addedBy — Telegram ID администратора, добавившего пользователя
   * @param {string} [username] — Имя пользователя (опционально)
   * @returns {Promise<object>} Добавленная запись
   * @throws {Error} если пользователь уже в списке или telegramId невалидный
   */
  async addUser(telegramId, addedBy, username) {
    this._ensureLoaded();

    // Валидация
    if (typeof telegramId !== 'number' || !Number.isInteger(telegramId) || telegramId <= 0) {
      throw new Error(`Whitelist: невалидный telegramId: ${telegramId}`);
    }

    if (this._userIdSet.has(telegramId)) {
      throw new Error(`Whitelist: пользователь ${telegramId} уже в белом списке`);
    }

    const entry = {
      telegramId,
      username: username || null,
      addedBy: addedBy || null,
      addedAt: new Date().toISOString()
    };

    this._users.push(entry);
    this._userIdSet.add(telegramId);

    if (!this.readOnly) {
      await this._save();
    }

    this.logger.info('User added to whitelist', {
      telegramId,
      addedBy,
      username: username || '(no name)'
    });

    return { ...entry };
  }

  /**
   * Удаляет пользователя из белого списка.
   * Активные сессии пользователя не прерываются (AC Story 1.4).
   *
   * @param {number} telegramId — Telegram ID
   * @returns {Promise<boolean>} true если пользователь был удалён, false если не найден
   */
  async removeUser(telegramId) {
    this._ensureLoaded();

    const index = this._users.findIndex(u => u.telegramId === telegramId);
    if (index === -1) {
      this.logger.warn('User not found in whitelist', { telegramId });
      return false;
    }

    this._users.splice(index, 1);
    this._userIdSet.delete(telegramId);

    if (!this.readOnly) {
      await this._save();
    }

    this.logger.info('User removed from whitelist', {
      telegramId
    });

    return true;
  }

  /**
   * Проверяет, является ли пользователь администратором.
   *
   * @param {number} telegramId — Telegram ID
   * @returns {boolean}
   */
  isAdmin(telegramId) {
    return this._adminIds.includes(telegramId);
  }

  /**
   * Возвращает копию массива всех пользователей белого списка.
   * @returns {object[]}
   */
  getAllUsers() {
    this._ensureLoaded();
    return this._users.map(u => ({ ...u }));
  }

  /**
   * Возвращает информацию о конкретном пользователе.
   * @param {number} telegramId
   * @returns {object|null}
   */
  getUser(telegramId) {
    this._ensureLoaded();
    const user = this._users.find(u => u.telegramId === telegramId);
    return user ? { ...user } : null;
  }

  /**
   * Возвращает массив ID администраторов.
   * @returns {number[]}
   */
  getAdminIds() {
    return [...this._adminIds];
  }

  /**
   * Возвращает общее количество пользователей в whitelist.
   * @returns {number}
   */
  getCount() {
    this._ensureLoaded();
    return this._users.length;
  }

  // ==================== Private Methods ====================

  /**
   * @private
   * Сохраняет whitelist.json на диск.
   */
  async _save() {
    const filePath = path.resolve(this.whitelistPath);
    const tempPath = filePath + '.tmp.' + process.pid;

    try {
      const data = JSON.stringify(this._users, null, 2);
      fs.writeFileSync(tempPath, data, 'utf-8');
      fs.renameSync(tempPath, filePath);
    } catch (err) {
      // Очищаем temp при ошибке
      try {
        if (fs.existsSync(tempPath)) fs.unlinkSync(tempPath);
      } catch (_) {
        // ignore cleanup errors
      }
      throw new Error(`Whitelist: ошибка сохранения: ${err.message}`);
    }
  }

  /**
   * @private
   * Перестраивает Set для быстрой проверки.
   */
  _rebuildIndex() {
    this._userIdSet = new Set(this._users.map(u => u.telegramId));
  }

  /**
   * @private
   * Проверяет, что whitelist загружен.
   */
  _ensureLoaded() {
    if (!this._loaded) {
      throw new Error(
        'Whitelist: не загружен. Вызовите load() перед использованием.'
      );
    }
  }
}

module.exports = Whitelist;
