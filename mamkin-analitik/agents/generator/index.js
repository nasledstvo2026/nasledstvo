/**
 * Агент-генератор (generator)
 *
 * Создаёт DOCX-файл и веб-версию документа БТ.
 * Публикует результаты на GitHub Pages.
 *
 * Вход: Session Context (финальный черновик БТ)
 * Выход: ссылки на DOCX и веб-версию
 *
 * Story 4.1 — DOCX generation (python-docx)
 * Story 4.2 — HTML web version generation
 * Story 4.3 — GitHub Pages publication
 * Story 4.4 — Send links to user in Telegram
 * Story 4.5 — Content identity DOCX ↔ HTML
 */

const { execSync } = require('child_process');
const path = require('path');
const fs = require('fs');
const { createLogger } = require('../../lib/logger');
const GitHubPagesPublisher = require('../../lib/github-pages');

class GeneratorAgent {
  constructor(config) {
    this.config = config;
    this.logger = createLogger('generator-agent');

    // Paths to Python scripts
    this.docxScript = path.join(__dirname, 'docx-gen.py');
    this.htmlScript = path.join(__dirname, 'html-gen.py');

    // Output directories
    this.outputDir = config?.outputDir || '/tmp/mamkin-analitik-output';
    this.publishDir = config?.publishDir || null; // GitHub Pages directory

    // GitHub Pages publisher (Story 4.3)
    this.publisher = config?.publisher || new GitHubPagesPublisher({
      repo: config?.githubRepo || process.env.GITHUB_PAGES_REPO,
      token: config?.githubToken || process.env.GITHUB_TOKEN,
      branch: config?.githubBranch || 'gh-pages',
      baseUrl: config?.githubBaseUrl || process.env.GITHUB_PAGES_URL,
      pagesDir: this.publishDir,
      dryRun: config?.dryRun || false,
      logger: this.logger
    });
  }

  /**
   * Основной метод: запускает генерацию и публикацию.
   *
   * @param {object} session — объект сессии с финальным черновиком
   * @returns {Promise<{ docxPath: string, htmlPath: string, docxUrl: string, htmlUrl: string }>}
   */
  async process(session) {
    this.logger.info('GeneratorAgent.process started', {
      sessionId: session?.sessionId,
      documentReady: session?.documentReady
    });

    // 1. Экспортируем данные сессии в JSON для Python-скриптов
    const data = this._prepareSessionData(session);
    const sessionDir = path.join(this.outputDir, session.sessionId);
    fs.mkdirSync(sessionDir, { recursive: true });

    const dataPath = path.join(sessionDir, 'session-data.json');
    fs.writeFileSync(dataPath, JSON.stringify(data, null, 2), 'utf-8');

    // 2. Генерируем DOCX (Story 4.1)
    const docxPath = path.join(sessionDir, 'business-requirements.docx');
    this._generateDocx(dataPath, docxPath);

    // 3. Генерируем HTML (Story 4.2)
    const htmlPath = path.join(sessionDir, 'index.html');
    this._generateHtml(dataPath, htmlPath);

    // 4. Публикуем на GitHub Pages (Story 4.3)
    let docxUrl = null;
    let htmlUrl = null;
    let published = false;

    if (this.publisher.isConfigured) {
      try {
        const urls = await this.publisher.publishDraft(
          session.sessionId,
          docxPath,
          htmlPath,
          session.draft?.title || session.title || 'Документ бизнес-требований'
        );
        docxUrl = urls.docxUrl;
        htmlUrl = urls.htmlUrl;
        published = true;
        this.logger.info('Publication successful', { docxUrl, htmlUrl });
      } catch (publishErr) {
        this.logger.error('Publication failed (continuing with local files)', {
          error: publishErr.message
        });
        // Не прерываем процесс — файлы локально сгенерированы (Story 4.3 fallback)
      }
    } else {
      this.logger.warn('GitHub Pages not configured — skipping publication. ' +
        'Set GITHUB_PAGES_REPO and GITHUB_TOKEN to enable auto-publish.');
    }

    // 5. Формируем результат
    const result = {
      sessionId: session.sessionId,
      docxPath,
      htmlPath,
      dataPath,
      docxUrl,
      htmlUrl,
      published
    };

    this.logger.info('GeneratorAgent.process completed', result);
    return result;
  }

  /**
   * Подготавливает данные сессии для Python-скриптов.
   *
   * @param {object} session
   * @returns {object}
   * @private
   */
  _prepareSessionData(session) {
    const draft = session.draft || session.finalDraft || {};

    return {
      title: draft.title || 'Документ бизнес-требований',
      createdAt: draft.createdAt || session.createdAt || new Date().toISOString(),
      sessionId: session.sessionId,
      telegramUserId: session.telegramUserId,
      username: session.username || null,
      totalBlocks: draft.totalBlocks || 7,
      blocks: draft.blocks || [],
      risks: draft.risks || { total: 0, byCategory: {}, items: [] },
      completedSubsections: draft.completedSubsections || 0,
      totalSubsections: draft.totalSubsections || 0,
      completionPercent: draft.completionPercent || 0,
      fullText: draft.fullText || ''
    };
  }

  /**
   * Запускает генерацию DOCX через docx-gen.py.
   *
   * @param {string} dataPath — путь к JSON с данными
   * @param {string} outputPath — путь для DOCX
   * @private
   */
  _generateDocx(dataPath, outputPath) {
    this.logger.info(`Generating DOCX: ${outputPath}`);
    try {
      const stdout = execSync(
        `python3 "${this.docxScript}" "${dataPath}" "${outputPath}"`,
        { timeout: 30000, encoding: 'utf-8' }
      );
      this.logger.info(`DOCX generated: ${stdout.trim()}`);
    } catch (err) {
      this.logger.error(`DOCX generation failed: ${err.message}`);
      throw new Error(`DOCX generation failed: ${err.message}`);
    }
  }

  /**
   * Запускает генерацию HTML через html-gen.py.
   *
   * @param {string} dataPath — путь к JSON с данными
   * @param {string} outputPath — путь для HTML
   * @private
   */
  _generateHtml(dataPath, outputPath) {
    this.logger.info(`Generating HTML: ${outputPath}`);
    try {
      const stdout = execSync(
        `python3 "${this.htmlScript}" "${dataPath}" "${outputPath}"`,
        { timeout: 30000, encoding: 'utf-8' }
      );
      this.logger.info(`HTML generated: ${stdout.trim()}`);
    } catch (err) {
      this.logger.error(`HTML generation failed: ${err.message}`);
      throw new Error(`HTML generation failed: ${err.message}`);
    }
  }
  /**
   * Публикует уже сгенерированные файлы на GitHub Pages без повторной генерации.
   *
   * @param {string} sessionId — ID сессии
   * @param {string} docxPath — путь к DOCX-файлу
   * @param {string} htmlPath — путь к HTML-файлу
   * @param {string} [projectName] — название проекта для коммит-сообщения
   * @returns {Promise<{ docxUrl: string, htmlUrl: string, sessionDir: string }>}
   */
  async publishFromResult(sessionId, docxPath, htmlPath, projectName) {
    if (!this.publisher.isConfigured) {
      this.logger.warn('GitHub Pages not configured — cannot publish');
      return { docxUrl: null, htmlUrl: null, sessionDir: null };
    }

    this.logger.info('publishFromResult: publishing existing files', {
      sessionId, docxPath, htmlPath, projectName
    });

    return this.publisher.publishDraft(sessionId, docxPath, htmlPath, projectName);
  }
}

module.exports = GeneratorAgent;
