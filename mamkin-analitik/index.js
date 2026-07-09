#!/usr/bin/env node
/**
 * «Мамкин аналитик» — Telegram-бот для сбора бизнес-требований
 * Точка входа: запускает polling-цикл Telegram Bot API
 */

const path = require('path');
const dotenv = require('dotenv');
const TelegramConnector = require('./lib/telegram-connector');
const SessionManager = require('./lib/session-manager');
const Whitelist = require('./lib/whitelist');
const SurveyEngine = require('./lib/survey-engine');
const TemplateEngine = require('./lib/template-engine');
const SessionContext = require('./lib/session-context');
const { createLogger } = require('./lib/logger');

// Load .env
dotenv.config({ path: path.join(__dirname, '.env') });

const logger = createLogger('index');

async function main() {
  logger.info('Starting Mamkin Analitik Bot...');

  const botToken = process.env.TELEGRAM_BOT_TOKEN || '';

  if (!botToken) {
    logger.error('TELEGRAM_BOT_TOKEN not set in environment or .env');
    process.exit(1);
  }

  // Init whitelist
  const whitelist = new Whitelist({
    whitelistPath: path.join(__dirname, 'data', 'whitelist.json'),
    adminIds: (process.env.TELEGRAM_ADMIN_IDS || '346428630').split(',').map(Number).filter(Boolean),
  });
  await whitelist.load();

  // Init template engine
  const templateEngine = new TemplateEngine({
    templatePath: path.join(__dirname, 'data', 'template.json'),
  });
  await templateEngine.load();

  // Init session manager
  const sessionManager = new SessionManager({
    storagePath: process.env.SESSION_STORAGE_PATH || path.join(__dirname, 'sessions'),
  });

  // Init survey engine (без sessionContext — создаётся на лету)
  const surveyEngine = new SurveyEngine({
    templateEngine,
  });

  // Init Telegram connector with polling
  const connector = new TelegramConnector({
    botToken,
    sessionManager,
    whitelist,
    templateEngine,
    skipInit: true,
  });

  // Start polling
  await connector.startPolling(5000);

  logger.info('Bot is running in polling mode. Press Ctrl+C to stop.');
}

main().catch(err => {
  logger.error('Fatal error', { error: err.message, stack: err.stack });
  process.exit(1);
});
