/**
 * Logger — структурированное логирование
 *
 * Обеспечивает единый формат логов для всех компонентов сервиса.
 */

class Logger {
  constructor(module) {
    this.module = module;
    this.level = process.env.OPENCLAW_LOG_LEVEL || 'info';
  }

  info(message, data = {}) {
    this._log('INFO', message, data);
  }

  warn(message, data = {}) {
    this._log('WARN', message, data);
  }

  error(message, data = {}) {
    this._log('ERROR', message, data);
  }

  debug(message, data = {}) {
    if (this.level === 'debug') {
      this._log('DEBUG', message, data);
    }
  }

  _log(level, message, data) {
    const entry = {
      timestamp: new Date().toISOString(),
      level,
      module: this.module,
      message,
      ...data
    };
    console.log(JSON.stringify(entry));
  }
}

function createLogger(module) {
  return new Logger(module);
}

module.exports = { Logger, createLogger };
