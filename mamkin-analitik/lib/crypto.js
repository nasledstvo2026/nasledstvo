/**
 * Crypto — шифрование данных сессий (AES-256)
 *
 * Обеспечивает шифрование/дешифрование файлов сессий
 * с использованием AES-256-GCM.
 *
 * Ключ шифрования: из переменной окружения SESSION_ENCRYPTION_KEY
 * Соль: из переменной окружения SESSION_ENCRYPTION_SALT
 *
 * Формат зашифрованных данных: IV (hex) : TAG (hex) : CIPHERTEXT (hex)
 */

const crypto = require('crypto');

const ALGORITHM = 'aes-256-gcm';
const IV_LENGTH = 16;     // 16 bytes for GCM
const TAG_LENGTH = 16;    // 16 bytes auth tag
const KEY_LENGTH = 32;    // 256 bits

class CryptoService {
  /**
   * @param {object} [options]
   * @param {string} [options.key] - 32-byte hex key (optional, overrides env)
   * @param {boolean} [options.allowEmptyKey=false] - allow empty key for tests
   */
  constructor(options = {}) {
    const secret = options.key || process.env.SESSION_ENCRYPTION_KEY || '';
    this.allowEmptyKey = options.allowEmptyKey === true;

    if (!secret && !this.allowEmptyKey) {
      throw new Error(
        'SESSION_ENCRYPTION_KEY must be set in production. ' +
        'For tests, pass allowEmptyKey: true or set SESSION_ENCRYPTION_KEY.'
      );
    }

    this.key = this._deriveKey(secret);
  }

  /**
   * Шифрует данные AES-256-GCM
   * @param {string} plaintext - Текст для шифрования (JSON-строка)
   * @returns {string} Зашифрованная строка в формате iv:tag:ciphertext (hex)
   */
  encrypt(plaintext) {
    if (!plaintext) return '';

    // Если ключ пустой (dev/test mode), возвращаем plaintext с маркером
    if (this.allowEmptyKey && !this.key) {
      return `plain:${plaintext}`;
    }

    const iv = crypto.randomBytes(IV_LENGTH);
    const cipher = crypto.createCipheriv(ALGORITHM, this.key, iv);

    let encrypted = cipher.update(plaintext, 'utf8', 'hex');
    encrypted += cipher.final('hex');

    const authTag = cipher.getAuthTag();

    return `${iv.toString('hex')}:${authTag.toString('hex')}:${encrypted}`;
  }

  /**
   * Дешифрует данные AES-256-GCM
   * @param {string} ciphertext - Зашифрованная строка (iv:tag:ciphertext hex)
   * @returns {string} Расшифрованный текст
   */
  decrypt(ciphertext) {
    if (!ciphertext) return '';

    // Dev/test mode: если это plaintext, возвращаем как есть
    if (ciphertext.startsWith('plain:')) {
      return ciphertext.slice(6);
    }

    if (!this.key) {
      throw new Error('Encryption key not configured');
    }

    const parts = ciphertext.split(':');
    if (parts.length !== 3) {
      throw new Error('Invalid encrypted data format. Expected iv:tag:ciphertext');
    }

    const [ivHex, tagHex, encryptedHex] = parts;

    const iv = Buffer.from(ivHex, 'hex');
    const authTag = Buffer.from(tagHex, 'hex');
    const encrypted = Buffer.from(encryptedHex, 'hex');

    const decipher = crypto.createDecipheriv(ALGORITHM, this.key, iv);
    decipher.setAuthTag(authTag);

    let decrypted = decipher.update(encrypted, 'hex', 'utf8');
    decrypted += decipher.final('utf8');

    return decrypted;
  }

  /**
   * Проверяет, зашифрованы ли данные
   * @param {string} data
   * @returns {boolean}
   */
  isEncrypted(data) {
    if (!data) return false;
    // Формат iv:tag:ciphertext — 3 части разделённые ":"
    // Каждая часть — hex-строка
    if (data.startsWith('plain:')) return false;
    const parts = data.split(':');
    return parts.length === 3;
  }

  /**
   * Производная ключа через scrypt
   * @param {string} secret - Секретная строка
   * @returns {Buffer} 32-байтовый ключ
   */
  _deriveKey(secret) {
    if (!secret && this.allowEmptyKey) {
      return null;
    }

    const salt = process.env.SESSION_ENCRYPTION_SALT || '';
    if (!salt && !this.allowEmptyKey) {
      throw new Error('SESSION_ENCRYPTION_SALT must be set in production');
    }
    if (!salt && this.allowEmptyKey) {
      // В тестовом режиме без соли используем хеш секрета
      return crypto.createHash('sha256').update(secret).digest();
    }

    return crypto.scryptSync(secret, salt, KEY_LENGTH);
  }
}

module.exports = CryptoService;
