#!/usr/bin/env node
const path = require('path');
const fs = require('fs');
const dotenv = require('dotenv');
dotenv.config({ path: path.join(__dirname, '.env') });

const SurveyEngine = require('./lib/survey-engine');
const SessionManager = require('./lib/session-manager');
const TemplateEngine = require('./lib/template-engine');

async function main() {
  // Init — without load() because SessionManager doesn't have it
  const te = new TemplateEngine({ templatePath: path.join(__dirname, 'data', 'template.json') });
  await te.load();
  
  const sm = new SessionManager({
    storagePath: process.env.SESSION_STORAGE_PATH || path.join(__dirname, 'session-storage'),
  });
  
  const se = new SurveyEngine({ templateEngine: te });

  // Find active sessions
  const active = await sm.listActiveSessions();
  active.sort((a, b) => new Date(b.updatedAt || 0) - new Date(a.updatedAt || 0));
  const s = active[0];
  
  const out = { sessionId: s?.sessionId, activeCount: active.length };
  
  if (!s) {
    out.error = 'No active sessions';
    fs.writeFileSync('/home/user1/fix-v2-output.json', JSON.stringify(out, null, 2));
    console.log('No active sessions');
    return;
  }
  
  out.allComplete = se.allSectionsComplete(s);
  console.log('Session:', s.sessionId, 'Complete:', out.allComplete, 'Answers:', Object.keys(s.answers||{}).length);
  
  // Step 1: signalCompletion
  try {
    const r = await se.signalCompletion(s);
    out.signalOk = true;
    out.signalMsgLength = r.message.length;
    // Write message
    fs.writeFileSync('/home/user1/msg-for-user.txt', r.message);
    console.log('signalCompletion OK, msg:', r.message.length);
  } catch(e) {
    out.signalError = e.message;
    console.log('signalCompletion FAIL:', e.message);
  }
  
  // Step 2: SessionContext + compile
  const ctx = se.getSessionContext(s);
  const Compiler = require('./lib/compiler');
  const compiler = new Compiler({ templateEngine: te });
  const draft = compiler.compileDraft(ctx);
  out.compiled = draft.completedSubsections + '/' + draft.totalSubsections;
  out.blocks = draft.blocks.length;
  out.risks = draft.risks.total;
  console.log('Draft compiled:', out.compiled, 'blocks:', out.blocks, 'risks:', out.risks);
  
  // Step 3: DraftGenerator
  try {
    const dg = new (require('./lib/draft-generator'))({ templateEngine: te, compiler: compiler });
    dg.generateDraft(s, ctx, draft);
    out.draftOk = true;
    out.status = s.status;
    out.hasDraft = !!s.draft;
    console.log('DraftGenerator OK, status:', s.status);
  } catch(e) {
    out.draftError = e.message;
    console.log('DraftGenerator FAIL:', e.message);
    // Try without extra args
    try {
      const dg2 = new (require('./lib/draft-generator'))({ templateEngine: te, compiler: compiler });
      dg2.generateDraft(s);
      out.draftOk = true;
      out.status = s.status;
      out.hasDraft = !!s.draft;
      console.log('DraftGenerator (retry) OK');
    } catch(e2) {
      out.draftError2 = e2.message;
      console.log('DraftGenerator (retry) FAIL:', e2.message);
    }
  }
  
  // Step 4: completeSession
  try {
    await sm.completeSession(s.sessionId);
    out.completed = true;
    console.log('Session completed');
  } catch(e) {
    out.completeError = e.message;
    console.log('completeSession FAIL:', e.message);
  }
  
  // Write full output
  fs.writeFileSync('/home/user1/fix-v2-output.json', JSON.stringify(out, null, 2));
  console.log('DONE');
}

main().catch(e => {
  const err = { fatal: e.message, stack: e.stack };
  fs.writeFileSync('/home/user1/fix-v2-output.json', JSON.stringify(err, null, 2));
  console.log('FATAL:', e.message);
});
