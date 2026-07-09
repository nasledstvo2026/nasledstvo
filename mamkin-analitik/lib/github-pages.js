/**
 * GitHub Pages Publisher — публикация документов на GitHub Pages
 *
 * Story 4.3 — GitHub Pages publication (FR19, NFR3)
 *
 * Выполняет git push DOCX и HTML-версий БТ в репозиторий GitHub Pages.
 * DOCX и HTML копируются в {pagesDir}/sessions/{sessionId}/,
 * коммитятся с сообщением "Add BRD session {sessionId} - {projectName}",
 * пушатся в ветку gh-pages, и возвращаются постоянные ссылки.
 *
 * Переменные окружения:
 *   GITHUB_PAGES_REPO  — репозиторий в формате "org/repo" (обязательно для прода)
 *   GITHUB_TOKEN       — Personal Access Token с правами на push (обязательно для прода)
 *   GITHUB_PAGES_DIR   — локальная рабочая копия (опционально, по умолч. /tmp/gh-pages-worktree)
 *   GITHUB_PAGES_BRANCH — название ветки (опционально, по умолч. gh-pages)
 *   GITHUB_PAGES_URL   — базовый URL, если отличается от https://{org}.github.io/{repo}
 *
 * Время публикации: ≤ 60 секунд (NFR3)
 *
 * Retry: при ошибке — 1 повторная попытка. При повторной неудаче — ошибка логируется,
 * вызывающий код решает, показывать ли "DOCX готов, но публикация временно недоступна".
 */

const path = require('path');
const fs = require('fs');
const { execSync, exec } = require('child_process');
const { withRetry } = require('./retry');

// ==================== Утилиты ====================

/**
 * Обёртка для execSync с логированием.
 * @param {string} cmd
 * @param {object} [opts]
 * @returns {string} stdout
 */
function run(cmd, opts = {}) {
  const defaults = { stdio: ['pipe', 'pipe', 'pipe'], encoding: 'utf-8', timeout: 30000 };
  const merged = { ...defaults, ...opts };
  try {
    const stdout = execSync(cmd, merged);
    return (stdout || '').toString().trim();
  } catch (err) {
    const stderr = (err.stderr || '').toString().trim();
    const stdout = (err.stdout || '').toString().trim();
    const msg = stderr || stdout || err.message;
    throw new Error(`Command failed: ${cmd.slice(0, 200)}\n${msg}`);
  }
}

/**
 * Асинхронная обёртка exec.
 * @param {string} cmd
 * @param {object} [opts]
 * @returns {Promise<{stdout: string, stderr: string}>}
 */
function runAsync(cmd, opts = {}) {
  return new Promise((resolve, reject) => {
    exec(cmd, { ...opts, maxBuffer: 10 * 1024 * 1024 }, (err, stdout, stderr) => {
      if (err) {
        reject(Object.assign(err, { stdout, stderr }));
      } else {
        resolve({ stdout: (stdout || '').toString().trim(), stderr: (stderr || '').toString().trim() });
      }
    });
  });
}

/**
 * Копирует файл, создавая директорию назначения.
 * @param {string} src
 * @param {string} dest
 */
function copyFile(src, dest) {
  const destDir = path.dirname(dest);
  fs.mkdirSync(destDir, { recursive: true });
  fs.copyFileSync(src, dest);
}

// ==================== GitHubPagesPublisher ====================

class GitHubPagesPublisher {
  /**
   * @param {object} [config]
   * @param {string} [config.repo]          — репозиторий "org/repo"
   * @param {string} [config.token]         — GitHub Personal Access Token
   * @param {string} [config.branch]        — ветка (по умолч. "gh-pages")
   * @param {string} [config.baseUrl]       — базовый URL для ссылок
   * @param {string} [config.pagesDir]      — локальная директория рабочей копии
   * @param {boolean} [config.dryRun]       — если true, не выполняет push
   * @param {object} [config.logger]        — опциональный логгер
   */
  constructor(config = {}) {
    this.repo = config.repo || process.env.GITHUB_PAGES_REPO || '';
    this.token = config.token || process.env.GITHUB_TOKEN || '';
    this.branch = config.branch || process.env.GITHUB_PAGES_BRANCH || 'gh-pages';
    this.pagesDir = config.pagesDir || process.env.GITHUB_PAGES_DIR || '/tmp/gh-pages-worktree';
    this.baseUrl = config.baseUrl || process.env.GITHUB_PAGES_URL || '';
    this.dryRun = config.dryRun === true || process.env.GITHUB_PAGES_DRY_RUN === 'true';
    this.logger = config.logger || { info: console.log, warn: console.warn, error: console.error, debug: () => {} };

    // Вычисляем базовый URL из репозитория, если не указан явно
    if (!this.baseUrl && this.repo) {
      const parts = this.repo.split('/');
      if (parts.length === 2) {
        this.baseUrl = `https://${parts[0]}.github.io/${parts[1]}`;
      }
    }
  }

  /**
   * Проверяет, настроена ли публикация (repo и token).
   * @returns {boolean}
   */
  get isConfigured() {
    return !!(this.repo && this.token);
  }

  // ==================== PUBLIC API ====================

  /**
   * Основной метод: публикует DOCX и HTML на GitHub Pages.
   *
   * @param {string} sessionId   — ID сессии (используется в пути и коммит-сообщении)
   * @param {string} docxPath    — путь к DOCX-файлу на диске
   * @param {string} htmlPath    — путь к HTML-файлу на диске
   * @param {string} [projectName] — название проекта (для коммит-сообщения)
   * @returns {Promise<{ docxUrl: string, htmlUrl: string, sessionDir: string }>}
   *
   * @throws {Error} если не настроен репозиторий или токен
   * @throws {Error} если DOCX или HTML файлы не существуют
   * @throws {Error} если git push не удался (после retry)
   */
  async publishDraft(sessionId, docxPath, htmlPath, projectName) {
    if (!this.isConfigured) {
      throw new Error(
        'GitHubPagesPublisher: не настроен репозиторий. ' +
        'Укажите GITHUB_PAGES_REPO и GITHUB_TOKEN в переменных окружения или config.'
      );
    }

    this.logger.info('GitHubPagesPublisher.publishDraft started', {
      sessionId,
      docxPath,
      htmlPath,
      projectName: projectName || '—',
      repo: this.repo,
      branch: this.branch,
      dryRun: this.dryRun
    });

    // 1. Валидация входных файлов
    this._assertFilesExist(docxPath, htmlPath);

    // 2. Клонируем / обновляем рабочую копию
    await this._ensureWorktree();

    // 3. Копируем файлы в директорию GitHub Pages
    const destPaths = await this._copyToPagesDir(docxPath, htmlPath, sessionId);

    // 4. Коммитим и пушим
    await this._commitAndPush(sessionId, projectName);

    // 5. Генерируем и возвращаем ссылки
    const urls = this._generateUrls(sessionId, destPaths);

    this.logger.info('GitHubPagesPublisher.publishDraft completed', {
      sessionId,
      docxUrl: urls.docxUrl,
      htmlUrl: urls.htmlUrl,
      dryRun: this.dryRun
    });

    return urls;
  }

  /**
   * Устаревший метод publish для обратной совместимости.
   * @deprecated Используйте publishDraft(sessionId, docxPath, htmlPath, projectName)
   */
  async publish(docxPath, htmlContent, sessionId) {
    this.logger.warn('GitHubPagesPublisher.publish() is deprecated — use publishDraft()');
    return this.publishDraft(sessionId, docxPath, htmlContent, sessionId);
  }

  // ==================== PRIVATE: File Operations ====================

  /**
   * Проверяет, что DOCX и HTML файлы существуют.
   * @private
   */
  _assertFilesExist(docxPath, htmlPath) {
    const errors = [];
    if (!docxPath || !fs.existsSync(docxPath)) {
      errors.push(`DOCX файл не найден: ${docxPath || 'не указан'}`);
    }
    if (!htmlPath || !fs.existsSync(htmlPath)) {
      errors.push(`HTML файл не найден: ${htmlPath || 'не указан'}`);
    }
    if (errors.length > 0) {
      throw new Error(`GitHubPagesPublisher: ошибки валидации:\n  ${errors.join('\n  ')}`);
    }
  }

  /**
   * Копирует DOCX и HTML в директорию GitHub Pages.
   *
   * @param {string} docxPath
   * @param {string} htmlPath
   * @param {string} sessionId
   * @returns {Promise<{ docxDest: string, htmlDest: string }>}
   * @private
   */
  async _copyToPagesDir(docxPath, htmlPath, sessionId) {
    const sessionDir = path.join(this.pagesDir, 'sessions', sessionId);
    const docxDest = path.join(sessionDir, path.basename(docxPath));
    const htmlDest = path.join(sessionDir, 'index.html');

    this.logger.debug('Copying files to pages directory', {
      fromDocx: docxPath,
      toDocx: docxDest,
      fromHtml: htmlPath,
      toHtml: htmlDest
    });

    // Создаём директорию сессии
    fs.mkdirSync(sessionDir, { recursive: true });

    // Копируем DOCX
    fs.copyFileSync(docxPath, docxDest);
    this.logger.debug(`DOCX copied: ${docxPath} → ${docxDest}`);

    // Копируем HTML
    fs.copyFileSync(htmlPath, htmlDest);
    this.logger.debug(`HTML copied: ${htmlPath} → ${htmlDest}`);

    // Убеждаемся, что файлы действительно скопировались
    if (!fs.existsSync(docxDest)) {
      throw new Error(`Не удалось скопировать DOCX: ${docxDest}`);
    }
    if (!fs.existsSync(htmlDest)) {
      throw new Error(`Не удалось скопировать HTML: ${htmlDest}`);
    }

    this.logger.info('Files copied to pages directory', {
      sessionDir,
      docxName: path.basename(docxPath),
      htmlName: 'index.html'
    });

    return { docxDest, htmlDest };
  }

  // ==================== PRIVATE: Git Operations ====================

  /**
   * Проверяет, является ли pagesDir валидным git-репозиторием.
   * @returns {Promise<boolean>}
   * @private
   */
  async _isGitRepo() {
    try {
      const { stdout } = await runAsync(
        `git -C "${this.pagesDir}" rev-parse --git-dir 2>/dev/null`,
        { timeout: 5000 }
      );
      return !!(stdout && stdout.trim());
    } catch {
      return false;
    }
  }

  /**
   * Проверяет, настроен ли remote в git-репозитории.
   * @param {string} name — имя remote (по умолч. 'origin')
   * @returns {Promise<boolean>}
   * @private
   */
  async _hasRemote(name = 'origin') {
    try {
      const { stdout } = await runAsync(
        `git -C "${this.pagesDir}" remote get-url ${name} 2>/dev/null`,
        { timeout: 5000 }
      );
      return !!(stdout && stdout.trim());
    } catch {
      return false;
    }
  }

  /**
   * Обеспечивает наличие рабочей копии репозитория.
   * Если pagesDir существует и является git-репозиторием — пуллит.
   * Если нет — клонирует.
   * @private
   */
  async _ensureWorktree() {
    const isRepo = await this._isGitRepo();

    if (isRepo) {
      this.logger.debug('Worktree exists, checking remote...');
      // Проверяем, есть ли remote origin
      const hasRemote = await this._hasRemote('origin');
      if (hasRemote) {
        this.logger.debug('Remote origin found, pulling...');
        await this._runGitCmd(`git -C "${this.pagesDir}" fetch origin ${this.branch}`, 'Git fetch');
        await this._runGitCmd(`git -C "${this.pagesDir}" reset --hard origin/${this.branch}`, 'Git reset');
      } else {
        this.logger.debug('No remote origin — skipping pull');
      }
    } else {
      this.logger.debug('Cloning worktree...');
      const authRepo = this._getAuthRepoUrl();
      fs.mkdirSync(this.pagesDir, { recursive: true });
      await this._runGitCmd(
        `git clone --branch ${this.branch} --single-branch "${authRepo}" "${this.pagesDir}"`,
        'Git clone',
        { timeout: 60000 }  // 60s for clone
      );
    }

    this.logger.debug('Worktree ready', { pagesDir: this.pagesDir });
  }

  /**
   * Коммитит и пушит изменения в GitHub Pages.
   *
   * @param {string} sessionId
   * @param {string} [projectName]
   * @returns {Promise<void>}
   * @private
   */
  async _commitAndPush(sessionId, projectName) {
    const message = this._formatCommitMessage(sessionId, projectName);
    const gitDir = this.pagesDir;

    this.logger.info(`Committing: ${message}`);

    // Проверяем, есть ли изменения
    const status = await this._runGitCmd(`git -C "${gitDir}" status --porcelain`, 'Git status');
    if (!status.stdout) {
      this.logger.warn(`Нет изменений для коммита (sessionId=${sessionId}). Возможно, файлы уже были добавлены.`);
      // Если нет изменений — всё равно возвращаем URL (документы уже опубликованы)
      return;
    }

    // git add
    await this._runGitCmd(`git -C "${gitDir}" add -A`, 'Git add');

    // git commit
    await this._runGitCmd(
      `git -C "${gitDir}" commit -m "${message}"`,
      'Git commit'
    );

    // git push (с retry)
    if (this.dryRun) {
      this.logger.info(`[DRY RUN] git push origin ${this.branch} (пропущен)`);
    } else {
      await this._runGitCmd(
        `git -C "${gitDir}" push origin ${this.branch}`,
        'Git push',
        { timeout: 60000 }
      );
      this.logger.info(`Push completed to ${this.repo}/${this.branch}`);
    }
  }

  /**
   * Форматирует коммит-сообщение.
   * Формат: "Add BRD session {sessionId} - {projectName}"
   *
   * @param {string} sessionId
   * @param {string} [projectName]
   * @returns {string}
   * @private
   */
  _formatCommitMessage(sessionId, projectName) {
    let msg = `Add BRD session ${sessionId}`;
    if (projectName && projectName.trim()) {
      msg += ` - ${projectName.trim()}`;
    }
    return msg.replace(/"/g, '\\"');
  }

  /**
   * Выполняет git-команду с retry-логикой.
   *
   * @param {string} cmd — команда
   * @param {string} label — человекочитаемая метка (для логов)
   * @param {object} [opts] — доп. опции exec
   * @returns {Promise<{stdout: string, stderr: string}>}
   * @private
   */
  async _runGitCmd(cmd, label, opts = {}) {
    const maxAttempts = label === 'Git push' ? 2 : 1;

    return withRetry(async () => {
      this.logger.debug(`Exec: ${label} — ${cmd.slice(0, 150)}`);
      try {
        const result = await runAsync(cmd, { timeout: opts.timeout || 30000 });
        this.logger.debug(`${label}: OK`);
        return result;
      } catch (err) {
        const stderr = (err.stderr || '').toString().trim();
        const stdout = (err.stdout || '').toString().trim();
        const detail = stderr || stdout || err.message;
        throw new Error(`${label} failed: ${detail.slice(0, 500)}`);
      }
    }, {
      maxAttempts,
      initialDelayMs: 2000,
      maxDelayMs: 10000
    });
  }

  /**
   * Возвращает URL репозитория с токеном для аутентификации.
   * @returns {string}
   * @private
   */
  _getAuthRepoUrl() {
    return `https://x-access-token:${this.token}@github.com/${this.repo}.git`;
  }

  // ==================== PRIVATE: URL Generation ====================

  /**
   * Генерирует постоянные ссылки на опубликованные документы.
   *
   * @param {string} sessionId
   * @param {{ docxDest: string, htmlDest: string }} destPaths — пути назначения
   * @returns {{ docxUrl: string, htmlUrl: string, sessionDir: string }}
   * @private
   */
  _generateUrls(sessionId, destPaths) {
    const baseUrl = this.baseUrl.replace(/\/+$/, '');
    const docxName = path.basename(destPaths.docxDest);

    return {
      docxUrl: `${baseUrl}/sessions/${sessionId}/${docxName}`,
      htmlUrl: `${baseUrl}/sessions/${sessionId}/index.html`,
      sessionDir: path.join(this.pagesDir, 'sessions', sessionId)
    };
  }
}

module.exports = GitHubPagesPublisher;
