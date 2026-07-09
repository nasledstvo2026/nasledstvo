#!/usr/bin/env node
const path = require('path');
const fs = require('fs');

// 1. PATCH telegram-connector.js - add survey_complete handling
const tcPath = path.join(__dirname, 'lib', 'telegram-connector.js');
let tc = fs.readFileSync(tcPath, 'utf-8');

// Find the onMessage function end and add survey_complete handling
// Strategy: find where result.action is checked and add our case
if (!tc.includes("survey_complete")) {
  // Last return before the function ends - add handler before it
  const lines = tc.split('\n');
  const out = [];
  let patched = false;
  for (let i = 0; i < lines.length; i++) {
    out.push(lines[i]);
    // After "if (result.action === 'reflection_needed')" pattern or similar
    if (!patched && lines[i].includes("action === 'next_question'")) {
      // Find the closing brace of this if block and add our handling
      // We'll insert before the catch/finally of processAnswer or after the action handlers
    }
  }

  // Simpler approach: add handler right after the processAnswer try block
  // Find the last place where survey results are processed
  const marker = "action === 'next_question'";
  const idx = tc.lastIndexOf(marker);
  if (idx >= 0) {
    // Find the closing brace of this block by counting
    const searchStart = idx + marker.length;
    const insertPoint = tc.indexOf('\n', searchStart);
    
    const handler = `
      // FIX: Handle survey completion
      if (result.action === 'survey_complete' || (result.question === null && result.action === 'next_question')) {
        try {
          logger.info('Survey complete detected, calling signalCompletion');
          const compResult = await surveyEngine.signalCompletion(session);
          await bot.sendMessage(chatId, compResult.message, { parse_mode: 'Markdown' });
          logger.info('Survey completion message sent');
          return;
        } catch (sigErr) {
          logger.error('signalCompletion failed', { error: sigErr.message });
        }
      }
`;
    const insertAfter = tc.indexOf('};', idx);
    if (insertAfter > 0) {
      const insertPos = insertAfter + 2; // after };
      tc = tc.slice(0, insertPos) + handler + tc.slice(insertPos);
      fs.writeFileSync(tcPath, tc);
      console.log('PATCHED telegram-connector.js successfully');
      patched = true;
    }
  }
  
  if (!patched) {
    console.log('Could not patch automatically, trying alternative method');
    // Last resort: add handler at the very end of onMessage before its closing
    // Find onMessage function end
    const funcEnd = tc.lastIndexOf('}');
    if (funcEnd > 0) {
      const handler2 = `
  // SURVEY COMPLETE FALLBACK: handle null question
  if (result && (result.action === 'survey_complete' || (result.question === null && !result.error))) {
    try {
      logger.info('Survey complete fallback');
      const compResult = await surveyEngine.signalCompletion(session);
      await bot.sendMessage(chatId, compResult.message, { parse_mode: 'Markdown' });
    } catch (e) {
      logger.error('Fallback completion error', { error: e.message });
    }
  }
`;
      // Insert before the very last } of the file (module.exports etc may follow)
      tc = tc.slice(0, funcEnd) + handler2 + tc.slice(funcEnd);
      fs.writeFileSync(tcPath, tc);
      console.log('PATCHED telegram-connector.js (fallback method)');
    }
  }
} else {
  console.log('Already patched');
}

// 2. FORCE COMPLETE the existing session
const dotenv = require('dotenv');
dotenv.config({ path: path.join(__dirname, '.env') });
const SurveyEngine = require('./lib/survey-engine');
const SessionManager = require('./lib/session-manager');
const TemplateEngine = require('./lib/template-engine');
const Compiler = require('./lib/compiler');
const DraftGenerator = require('./lib/draft-generator');

async function forceComplete() {
  const te = new TemplateEngine({ templatePath: path.join(__dirname, 'data', 'template.json') });
  await te.load();
  const sm = new SessionManager({
    storagePath: process.env.SESSION_STORAGE_PATH || path.join(__dirname, 'session-storage'),
  });
  await sm.load();
  const se = new SurveyEngine({ templateEngine: te });

  const active = await sm.listActiveSessions();
  active.sort((a, b) => new Date(b.updatedAt||0) - new Date(a.updatedAt||0));
  const s = active[0];
  if (!s) { console.log('No active sessions'); return; }
  
  console.log('Session:', s.sessionId);
  console.log('All complete:', se.allSectionsComplete(s));
  
  const r = await se.signalCompletion(s);
  console.log('signalCompletion OK, msg length:', r.message.length);
  
  const ctx = se.getSessionContext(s);
  const compiler = new Compiler({ templateEngine: te });
  const draft = compiler.compileDraft(ctx);
  console.log('Draft compiled:', draft.completedSubsections + '/' + draft.totalSubsections);
  
  const dg = new DraftGenerator({ templateEngine: te, compiler: compiler });
  dg.generate(s);
  console.log('Draft generated, status:', s.status);
  
  await sm.completeSession(s.sessionId);
  console.log('Session COMPLETED!');
  
  // Write output
  const outDir = path.join('/tmp', 'mamkin-fixed-' + s.sessionId);
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'user_message.txt'), r.message);
  console.log('Output:', outDir);
}

forceComplete().catch(e => {
  console.log('ERR:', e.message);
  console.log('STACK:', e.stack);
});
