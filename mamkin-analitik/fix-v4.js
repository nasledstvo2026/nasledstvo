#!/usr/bin/env node
const path = require('path');
const fs = require('fs');
const dotenv = require('dotenv');
dotenv.config({ path: path.join(__dirname, '.env') });

const SurveyEngine = require('./lib/survey-engine');
const SessionManager = require('./lib/session-manager');
const TemplateEngine = require('./lib/template-engine');
const CryptoService = require('./lib/crypto');

async function main() {
  const te = new TemplateEngine({ templatePath: path.join(__dirname, 'data', 'template.json') });
  await te.load();
  
  const sm = new SessionManager({
    storagePath: process.env.SESSION_STORAGE_PATH || path.join(__dirname, 'session-storage'),
  });
  
  const se = new SurveyEngine({ templateEngine: te });

  // Read the biggest session file directly (35KB – that's yours)
  const activeDir = process.env.SESSION_STORAGE_PATH 
    ? path.join(process.env.SESSION_STORAGE_PATH, 'active')
    : path.join(__dirname, 'session-storage', 'active');
  
  const files = fs.readdirSync(activeDir).filter(f => f.endsWith('.json'));
  files.sort((a, b) => fs.statSync(path.join(activeDir, b)).size - fs.statSync(path.join(activeDir, a)).size);
  
  const bigFile = files[0];
  const bigPath = path.join(activeDir, bigFile);
  
  const out = { file: bigFile, size: fs.statSync(bigPath).size };
  
  // Decrypt
  const crypt = new CryptoService({ 
    key: process.env.SESSION_ENCRYPTION_KEY, 
    allowEmptyKey: false  // we have key
  });
  const raw = fs.readFileSync(bigPath, 'utf-8');
  const decrypted = crypt.decrypt(raw);
  const session = JSON.parse(decrypted);
  
  out.telegramUserId = session.telegramUserId;
  out.sessionId = session.sessionId;
  out.status = session.status;
  out.answers = Object.keys(session.answers||{}).length;
  out.risksCount = (session.risks||[]).length;
  out.allComplete = se.allSectionsComplete(session);
  out.updatedAt = session.updatedAt;
  
  console.log('Session:', session.telegramUserId, 'Complete:', out.allComplete, 'Answers:', out.answers);
  
  // signalCompletion
  const r = await se.signalCompletion(session);
  out.signalOk = true;
  out.signalMsgLen = r.message.length;
  console.log('signalCompletion OK');
  
  // Write message to file
  fs.writeFileSync('/home/user1/bt-completion-message.txt', r.message);
  
  // SessionContext + Compiler
  const ctx = se.getSessionContext(session);
  const Compiler = require('./lib/compiler');
  const compiler = new Compiler({ templateEngine: te });
  const draft = compiler.compileDraft(ctx);
  out.draftCompiled = draft.completedSubsections + '/' + draft.totalSubsections;
  out.draftBlocks = draft.blocks.length;
  out.draftRisks = draft.risks.total;
  console.log('Draft compiled:', out.draftCompiled);
  
  // DraftGenerator
  const dg = new (require('./lib/draft-generator'))({ templateEngine: te, compiler });
  dg.generateDraft(session, ctx, draft);
  out.draftOk = true;
  out.hasDraft = !!session.draft;
  out.sessionStatus = session.status;
  console.log('Draft generated, hasDraft:', out.hasDraft);
  
  // Save output
  const outDir = '/tmp/mamkin-fixed-' + session.sessionId;
  fs.mkdirSync(outDir, { recursive: true });
  fs.writeFileSync(path.join(outDir, 'draft.json'), JSON.stringify(draft, null, 2));
  fs.writeFileSync(path.join(outDir, 'session.json'), JSON.stringify(session, null, 2));
  
  // Move to completed
  await sm.completeSession(session.sessionId);
  out.completed = true;
  console.log('Session moved to completed');
  console.log('Output:', outDir);
  
  fs.writeFileSync('/home/user1/fix-v4-output.json', JSON.stringify(out, null, 2));
}

main().catch(e => {
  fs.writeFileSync('/home/user1/fix-v4-output.json', JSON.stringify({ fatal: e.message, stack: e.stack }, null, 2));
  console.log('FATAL:', e.message);
});
