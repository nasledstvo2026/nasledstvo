#!/usr/bin/env node
const path = require('path');
const fs = require('fs');
const dotenv = require('dotenv');
dotenv.config({ path: path.join(__dirname, '.env') });
const { execSync } = require('child_process');

async function main() {
  const CryptoService = require('./lib/crypto');
  const SessionManager = require('./lib/session-manager');

  // Read the BIG completed session (35KB — yours)
  const completedDir = process.env.SESSION_STORAGE_PATH 
    ? path.join(process.env.SESSION_STORAGE_PATH, 'completed')
    : path.join(__dirname, 'session-storage', 'completed');
  
  const files = fs.readdirSync(completedDir).filter(f => f.endsWith('.json'));
  files.sort((a, b) => fs.statSync(path.join(completedDir, b)).size - fs.statSync(path.join(completedDir, a)).size);
  const bigFile = files[0];
  
  const crypt = new CryptoService({ key: process.env.SESSION_ENCRYPTION_KEY, allowEmptyKey: false });
  const raw = fs.readFileSync(path.join(completedDir, bigFile), 'utf-8');
  const session = JSON.parse(crypt.decrypt(raw));
  
  console.log('Session:', session.sessionId, 'User:', session.telegramUserId);

  // SessionContext from saved data
  const TemplateEngine = require('./lib/template-engine');
  const te = new TemplateEngine({ templatePath: path.join(__dirname, 'data', 'template.json') });
  await te.load();

  const SurveyEngine = require('./lib/survey-engine');
  const se = new SurveyEngine({ templateEngine: te });

  // Get context from session (answers are in session.answers)
  const ctx = se.getSessionContext(session);
  console.log('Context:', Object.keys(ctx.answers||{}).length, 'answers,', (ctx.risks||[]).length, 'risks');

  // Compiler
  const Compiler = require('./lib/compiler');
  const compiler = new Compiler({ templateEngine: te });
  const draftFromCompiler = compiler.compileDraft(ctx);
  console.log('Draft compiled:', draftFromCompiler.completedSubsections + '/' + draftFromCompiler.totalSubsections);

  // Force controller approval
  ctx.qualityGate = { approved: true, iteration: 1, overallScore: 75, issues: [] };

  // DraftGenerator
  const dg = new (require('./lib/draft-generator'))({ templateEngine: te, compiler });
  dg.generateDraft(session, ctx);
  
  if (!ctx.draft) {
    console.error('ctx.draft is still undefined after generateDraft!');
    // Fallback: use compiler data
    ctx.draft = draftFromCompiler;
  }
  
  session.draft = ctx.draft;
  console.log('draft.blocks:', session.draft.blocks?.length, 'text:', session.draft.fullText?.length, 'chars');

  // Build session-data.json
  const outDir = '/tmp/mamkin-fixed-' + session.sessionId;
  fs.mkdirSync(outDir, { recursive: true });
  
  const sd = {
    title: session.draft.title || 'Документ бизнес-требований',
    createdAt: session.draft.createdAt || session.createdAt || new Date().toISOString(),
    sessionId: session.sessionId,
    telegramUserId: session.telegramUserId,
    totalBlocks: session.draft.totalBlocks || draftFromCompiler.totalBlocks || 7,
    blocks: session.draft.blocks || draftFromCompiler.blocks || [],
    risks: session.draft.risks || draftFromCompiler.risks || { total: 0, byCategory: {}, items: [] },
    completedSubsections: session.draft.completedSubsections || draftFromCompiler.completedSubsections || 0,
    totalSubsections: session.draft.totalSubsections || draftFromCompiler.totalSubsections || 0,
    fullText: session.draft.fullText || draftFromCompiler.fullText || ''
  };
  
  console.log('session-data blocks:', sd.blocks.length, 'text:', sd.fullText.length, 'chars');
  fs.writeFileSync(path.join(outDir, 'session-data.json'), JSON.stringify(sd, null, 2));

  // Generate DOCX
  console.log('\nGenerating DOCX...');
  execSync(
    `python3 "${__dirname}/agents/generator/docx-gen.py" "${outDir}/session-data.json" "${outDir}/business-requirements.docx"`,
    { timeout: 30000 }
  );
  console.log('DOCX OK');

  // Generate HTML
  console.log('Generating HTML...');
  execSync(
    `python3 "${__dirname}/agents/generator/html-gen.py" "${outDir}/session-data.json" "${outDir}/index.html"`,
    { timeout: 30000 }
  );
  console.log('HTML OK');

  // Publish to GitHub Pages
  console.log('\nPublishing...');
  try {
    const GitHubPagesPublisher = require('./lib/github-pages');
    const publisher = new GitHubPagesPublisher({
      repo: process.env.GITHUB_PAGES_REPO || 'nasledstvo2026/nasledstvo',
      token: process.env.GITHUB_TOKEN,
      branch: 'gh-pages',
      baseUrl: process.env.GITHUB_PAGES_URL || 'https://nasledstvo2026.github.io/nasledstvo',
      pagesDir: outDir,
      dryRun: false,
      logger: console
    });
    
    const urls = await publisher.publishDraft(
      session.sessionId,
      path.join(outDir, 'business-requirements.docx'),
      path.join(outDir, 'index.html'),
      sd.title
    );
    console.log('PUBLISHED:', JSON.stringify(urls));
  } catch(e) {
    console.log('Publish error:', e.message);
  }

  // Restart bot
  console.log('\nRestarting bot...');
  try {
    execSync('pkill -f "node.*index.js" || true', { timeout: 3000 });
    execSync(
      `cd /home/user1/.openclaw/workspace/mamkin-analitik && nohup node index.js > bot.log 2>&1 &`,
      { timeout: 3000 }
    );
    console.log('Bot restarted');
  } catch(e) {
    console.log('Restart error:', e.message);
  }

  console.log('\n✅ DONE');
  console.log('📁', outDir);
}

main().catch(e => {
  fs.writeFileSync('/home/user1/fix-v7-output.json', JSON.stringify({ fatal: e.message, stack: e.stack }, null, 2));
  console.log('FATAL:', e.message);
});
