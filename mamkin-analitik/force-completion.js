#!/usr/bin/env node
const path = require('path');
const dotenv = require('dotenv');
const fs = require('fs');
dotenv.config({ path: path.join(__dirname, '.env') });

const SurveyEngine = require('./lib/survey-engine');
const SessionManager = require('./lib/session-manager');
const TemplateEngine = require('./lib/template-engine');
const Compiler = require('./lib/compiler');
const DraftGenerator = require('./lib/draft-generator');
const SessionContext = require('./lib/session-context');

async function main() {
  // Init
  const te = new TemplateEngine({ templatePath: path.join(__dirname, 'data', 'template.json') });
  await te.load();
  const sm = new SessionManager({
    storagePath: process.env.SESSION_STORAGE_PATH || path.join(__dirname, 'session-storage'),
  });
  await sm.load();
  const se = new SurveyEngine({ templateEngine: te });

  // Find newest active session
  const active = await sm.listActiveSessions();
  active.sort((a, b) => new Date(b.updatedAt||0) - new Date(a.updatedAt||0));
  const s = active[0];
  if (!s) { console.error('No active sessions'); process.exit(1); }

  console.log('Session:', s.sessionId, 'Answers:', Object.keys(s.answers||{}).length, 'Risks:', (s.risks||[]).length);

  // Force complete
  const allDone = se.allSectionsComplete(s);
  console.log('All sections complete:', allDone);
  if (!allDone) {
    // Mark any missing sections as skipped
    const total = te.getBlockCount();
    for (let b = 1; b <= total; b++) {
      const block = te.getBlock(b);
      if (!block || !block.subsections) continue;
      for (const sub of block.subsections) {
        if (!s.answers || !s.answers[sub.id] || !s.answers[sub.id].depthReached) {
          if (!s.answers) s.answers = {};
          s.answers[sub.id] = s.answers[sub.id] || {};
          s.answers[sub.id].L1 = 'Пропущено';
          s.answers[sub.id].depthReached = 'L1';
          console.log('  Filled missing:', sub.id);
        }
      }
    }
  }

  // signalCompletion
  const r = await se.signalCompletion(s);
  console.log('signalCompletion done, msg len:', r.message.length);

  // Compile
  const ctx = se.getSessionContext(s);
  const compiler = new Compiler({ templateEngine: te });
  const draft = compiler.compileDraft(ctx);
  console.log('Draft compiled:', draft.completedSubsections, '/', draft.totalSubsections, 'blocks:', draft.blocks.length);

  // DraftGenerator
  const dg = new DraftGenerator({ templateEngine: te, compiler });
  dg.generate(s, ctx, draft);
  console.log('Draft status:', s.status, 'hasDraft:', !!s.draft);

  // Save session
  await sm.completeSession(s.sessionId);
  console.log('Session completed!');

  // Write result JSON for debug
  const outDir = path.join('/tmp', 'mamkin-fix-' + s.sessionId);
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'draft.json'), JSON.stringify(draft, null, 2));
  fs.writeFileSync(path.join(outDir, 'session.json'), JSON.stringify(s, null, 2));
  console.log('Output written to', outDir);

  // Generate message for user
  const msg = r.message + '\n\nДокумент сформирован. Жди ссылки от агента-генератора (следующий шаг).';
  fs.writeFileSync(path.join(outDir, 'user_message.txt'), msg);
  console.log('\n=== MESSAGE FOR USER ===');
  console.log(msg);
}

main().catch(e => { console.error('FATAL:', e.message, e.stack); process.exit(1); });
