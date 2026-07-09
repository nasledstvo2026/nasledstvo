#!/usr/bin/env node
/**
 * Скрипт для форсированного завершения опроса:
 * находит самую свежую активную сессию, вызывает signalCompletion,
 * запускает compiler → draft-generator → generator → публикацию
 */

const path = require('path');
const dotenv = require('dotenv');
dotenv.config({ path: path.join(__dirname, '.env') });

const SurveyEngine = require('./lib/survey-engine');
const SessionManager = require('./lib/session-manager');
const TemplateEngine = require('./lib/template-engine');
const Compiler = require('./lib/compiler');
const DraftGenerator = require('./lib/draft-generator');
const GeneratorAgent = require('./agents/generator/index');
const SessionContext = require('./lib/session-context');
const { createLogger } = require('./lib/logger');

const logger = createLogger('fix-completion');

async function main() {
  logger.info('Starting fix-completion script...');

  // 1. Init template engine
  const templateEngine = new TemplateEngine({
    templatePath: path.join(__dirname, 'data', 'template.json'),
  });
  await templateEngine.load();

  // 2. Init session manager
  const sessionManager = new SessionManager({
    storagePath: process.env.SESSION_STORAGE_PATH || path.join(__dirname, 'session-storage'),
  });
  await sessionManager.load();

  // 3. Init survey engine
  const surveyEngine = new SurveyEngine({ templateEngine });

  // 4. Find the most recent active session (yours)
  const activeSessions = await sessionManager.listActiveSessions();
  logger.info(`Found ${activeSessions.length} active sessions`);

  // Sort by updatedAt, take the newest
  activeSessions.sort((a, b) => new Date(b.updatedAt || 0) - new Date(a.updatedAt || 0));
  const session = activeSessions[0];

  if (!session) {
    logger.error('No active sessions found');
    process.exit(1);
  }

  logger.info(`Processing session ${session.sessionId}`, {
    updatedAt: session.updatedAt,
    answersCount: Object.keys(session.answers || {}).length,
    risksCount: (session.risks || []).length,
    status: session.status,
  });

  // 5. Check if all sections are complete
  const allComplete = surveyEngine.allSectionsComplete(session);
  logger.info(`All sections complete: ${allComplete}`);

  if (!allComplete) {
    logger.warn('Not all sections are complete. Forcing completion anyway...');
  }

  // 6. Call signalCompletion (this generates the completion message)
  logger.info('Calling signalCompletion...');
  const result = await surveyEngine.signalCompletion(session);
  logger.info('signalCompletion returned', { messageLength: result.message.length });

  // 7. Build SessionContext
  const sessionCtx = surveyEngine.getSessionContext(session);
  logger.info('SessionContext built', {
    answersCount: Object.keys(sessionCtx.answers || {}).length,
    risksCount: (sessionCtx.risks || []).length,
    status: sessionCtx.status,
  });

  // 8. Run compiler
  logger.info('Running compiler...');
  const compiler = new Compiler({ templateEngine });
  const draft = compiler.compileDraft(sessionCtx);
  logger.info('Draft compiled', {
    totalBlocks: draft.totalBlocks,
    completedSubsections: draft.completedSubsections,
    fullTextLength: draft.fullText.length,
    risksTotal: draft.risks.total,
  });

  // 9. Run draft generator
  logger.info('Running draft generator...');
  const draftGenerator = new DraftGenerator({ templateEngine, compiler });
  const finalDraft = draftGenerator.generate(session, sessionCtx, draft);
  logger.info('Final draft ready', {
    status: session.status,
    hasDraft: !!session.draft,
  });

  // 10. Run generator agent (DOCX + HTML + GitHub Pages)
  logger.info('Running generator agent...');
  const generator = new GeneratorAgent({
    outputDir: '/tmp/mamkin-analitik-output',
    githubRepo: process.env.GITHUB_PAGES_REPO,
    githubToken: process.env.GITHUB_TOKEN,
    githubBranch: 'gh-pages',
    dryRun: !process.env.GITHUB_PAGES_REPO,
  });

  const genResult = await generator.process(session);
  logger.info('Generator result', {
    docxPath: genResult.docxPath,
    htmlPath: genResult.htmlPath,
    docxUrl: genResult.docxUrl,
    htmlUrl: genResult.htmlUrl,
    published: genResult.published,
  });

  // 11. Save the completed session
  await sessionManager.completeSession(session.sessionId);
  logger.info(`Session ${session.sessionId} moved to completed`);

  // 12. Print results
  console.log('\n=== RESULTS ===');
  console.log(`Status: ${genResult.published ? '✅ PUBLISHED' : '⚠️ GENERATED LOCALLY'}`);
  console.log(`DOCX: ${genResult.docxUrl || genResult.docxPath}`);
  console.log(`HTML: ${genResult.htmlUrl || genResult.htmlPath}`);
  console.log(`Session: ${session.sessionId}`);

  // 13. If published, also notify via signalCompletion with links
  if (genResult.published) {
    const final = await surveyEngine.signalCompletion(session, {
      docxUrl: genResult.docxUrl,
      htmlUrl: genResult.htmlUrl,
    });
    console.log(`\nMessage for user:\n${final.message}`);
  } else {
    // Send the legacy completion message
    console.log(`\nMessage for user:\n${result.message}`);
  }

  logger.info('Done!');
}

main().catch(err => {
  logger.error('Fatal error', { error: err.message, stack: err.stack });
  process.exit(1);
});
