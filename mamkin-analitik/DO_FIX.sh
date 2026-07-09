#!/bin/bash
set -e
cd /home/user1/.openclaw/workspace/mamkin-analitik

# Step 1: Create a simple node script that forces completion
cat > /tmp/force-fix.mjs << 'SCRIPT'
import { createRequire } from 'module';
const require = createRequire(import.meta.url);
import path from 'path';
import fs from 'fs';
import dotenv from 'dotenv';

const __dirname = '/home/user1/.openclaw/workspace/mamkin-analitik';
dotenv.config({ path: path.join(__dirname, '.env') });

const SurveyEngine = require('./lib/survey-engine');
const SessionManager = require('./lib/session-manager');
const TemplateEngine = require('./lib/template-engine');
const Compiler = require('./lib/compiler');
const DraftGenerator = require('./lib/draft-generator');

async function main() {
  const te = new TemplateEngine({ templatePath: path.join(__dirname, 'data', 'template.json') });
  await te.load();
  const sm = new SessionManager({
    storagePath: process.env.SESSION_STORAGE_PATH || path.join(__dirname, 'session-storage'),
  });
  await sm.load();
  const se = new SurveyEngine({ templateEngine: te });

  const active = await sm.listActiveSessions();
  active.sort((a, b) => new Date(b.updatedAt || 0) - new Date(a.updatedAt || 0));
  const s = active[0];
  
  const outPath = '/home/user1/fix-output.json';
  const result = { sessionId: s?.sessionId, activeCount: active.length };
  
  if (!s) {
    result.error = 'No active sessions';
    fs.writeFileSync(outPath, JSON.stringify(result, null, 2));
    return;
  }
  
  result.allComplete = se.allSectionsComplete(s);
  
  try {
    const r = await se.signalCompletion(s);
    result.signalMsgLength = r.message.length;
    result.signalMsg = r.message;
  } catch (e) {
    result.signalError = e.message;
  }
  
  try {
    const ctx = se.getSessionContext(s);
    const compiler = new Compiler({ templateEngine: te });
    const draft = compiler.compileDraft(ctx);
    result.compiled = true;
    result.completedSubsections = draft.completedSubsections;
    result.totalSubsections = draft.totalSubsections;
    result.risksTotal = draft.risks.total;
    result.blocksCount = draft.blocks.length;
  } catch (e) {
    result.compilerError = e.message;
  }
  
  try {
    const dg = new DraftGenerator({ templateEngine: te, compiler: new Compiler({ templateEngine: te }) });
    dg.generate(s);
    result.draftGenerated = true;
    result.status = s.status;
    result.hasDraft = !!s.draft;
  } catch (e) {
    result.draftError = e.message;
  }
  
  try {
    await sm.completeSession(s.sessionId);
    result.sessionCompleted = true;
  } catch (e) {
    result.completeError = e.message;
  }
  
  fs.writeFileSync(outPath, JSON.stringify(result, null, 2));
}

main().catch(e => {
  fs.writeFileSync('/home/user1/fix-output.json', JSON.stringify({ fatal: e.message, stack: e.stack }, null, 2));
});
SCRIPT

cd /home/user1/.openclaw/workspace/mamkin-analitik && node --experimental-modules /tmp/force-fix.mjs 2>/dev/null || node -e "
const path = require('path');
const fs = require('fs');
const dotenv = require('dotenv');
const __dirname = '/home/user1/.openclaw/workspace/mamkin-analitik';
dotenv.config({ path: path.join(__dirname, '.env') });
const SurveyEngine = require(path.join(__dirname, 'lib/survey-engine'));
const SessionManager = require(path.join(__dirname, 'lib/session-manager'));
const TemplateEngine = require(path.join(__dirname, 'lib/template-engine'));
const Compiler = require(path.join(__dirname, 'lib/compiler'));
const DraftGenerator = require(path.join(__dirname, 'lib/draft-generator'));

async function main() {
  const te = new TemplateEngine({ templatePath: path.join(__dirname, 'data', 'template.json') });
  await te.load();
  const sm = new SessionManager({ storagePath: process.env.SESSION_STORAGE_PATH || path.join(__dirname, 'session-storage') });
  await sm.load();
  const se = new SurveyEngine({ templateEngine: te });
  const active = await sm.listActiveSessions();
  active.sort((a,b)=>new Date(b.updatedAt||0)-new Date(a.updatedAt||0));
  const s = active[0];
  const r = { sessionId: s?.sessionId, activeCount: active.length };
  if (!s) { r.error='no sessions'; fs.writeFileSync('/home/user1/fix-output.json',JSON.stringify(r)); return; }
  r.allComplete = se.allSectionsComplete(s);
  try {
    const sig = await se.signalCompletion(s);
    r.signalMsgLength = sig.message.length;
  } catch(e) { r.signalError = e.message; }
  try {
    const ctx = se.getSessionContext(s);
    const comp = new Compiler({templateEngine:te});
    const draft = comp.compileDraft(ctx);
    r.compiled={subs:draft.completedSubsections+'/'+draft.totalSubsections,risks:draft.risks.total,blocks:draft.blocks.length};
  } catch(e) { r.compilerError = e.message; }
  try {
    const dg = new DraftGenerator({templateEngine:te,compiler:new Compiler({templateEngine:te})});
    dg.generate(s);
    r.draftGenerated=true;
    r.status=s.status;
    r.hasDraft=!!s.draft;
  } catch(e) { r.draftError=e.message; }
  try {
    await sm.completeSession(s.sessionId);
    r.completed=true;
  } catch(e) { r.completeError=e.message; }
  fs.writeFileSync('/home/user1/fix-output.json',JSON.stringify(r,null,2));
}
main().catch(e=>{fs.writeFileSync('/home/user1/fix-output.json',JSON.stringify({fatal:e.message,stack:e.stack.split('\\n').slice(0,5).join('|')},null,2));});
" 2>&1

echo "EXIT_CODE: $?"
echo "---"
cat /home/user1/fix-output.json 2>/dev/null || echo "NO_OUTPUT"
echo "==="
ls -la /home/user1/fix-output.json 2>/dev/null || echo "NO_FILE"
