#!/usr/bin/env node
const path = require('path');
const fs = require('fs');
const dotenv = require('dotenv');
dotenv.config({ path: path.join(__dirname, '.env') });

const SurveyEngine = require('./lib/survey-engine');
const SessionManager = require('./lib/session-manager');
const TemplateEngine = require('./lib/template-engine');

const TELEGRAM_USER_ID = 346428630;

async function main() {
  const te = new TemplateEngine({ templatePath: path.join(__dirname, 'data', 'template.json') });
  await te.load();
  
  const sm = new SessionManager({
    storagePath: process.env.SESSION_STORAGE_PATH || path.join(__dirname, 'session-storage'),
  });
  
  const se = new SurveyEngine({ templateEngine: te });

  // Сначала список файлов в active — чтобы проверить что они расшифровываются
  const activeDir = process.env.SESSION_STORAGE_PATH 
    ? path.join(process.env.SESSION_STORAGE_PATH, 'active')
    : path.join(__dirname, 'session-storage', 'active');
  
  const files = fs.readdirSync(activeDir).filter(f => f.endsWith('.json'));
  const out = { fileCount: files.length, fileSizes: {}, status: [] };
  
  for (const f of files) {
    const fpath = path.join(activeDir, f);
    const stats = fs.statSync(fpath);
    out.fileSizes[f.replace('session_', '').replace('.json', '').substring(0, 8)] = stats.size;
  }

  // Теперь listActiveSessions с фильтром
  const active = await sm.listActiveSessions(TELEGRAM_USER_ID);
  out.filteredCount = active.length;
  
  if (active.length === 0) {
    out.allSessions = await sm.listActiveSessions(); // без фильтра — может вернуть все?
    
    // Попробуем прочитать самую крупную сессию напрямую
    const bigFile = files.sort((a, b) => fs.statSync(path.join(activeDir, b)).size - fs.statSync(path.join(activeDir, a)).size)[0];
    if (bigFile) {
      const CryptoService = require('./lib/crypto');
      const raw = fs.readFileSync(path.join(activeDir, bigFile), 'utf-8');
      const { config } = require('./lib/config');
      
      out.bigFile = bigFile;
      out.bigFileSize = fs.statSync(path.join(activeDir, bigFile)).size;
      
      try {
        const crypt = new CryptoService({ key: process.env.SESSION_ENCRYPTION_KEY, config: {}});
        const decrypted = crypt.decrypt(raw);
        const session = JSON.parse(decrypted);
        out.bigFileUser = session.telegramUserId;
        out.bigFileSessionId = session.sessionId;
        out.bigFileStatus = session.status;
        out.bigFileAnswers = session.answers ? Object.keys(session.answers).length : 0;
        out.bigFileRisks = session.risks ? session.risks.length : 0;
        out.bigFileAllComplete = se.allSectionsComplete(session);
        
        // Force complete this session
        const r = await se.signalCompletion(session);
        out.signalOk = true;
        
        const ctx = se.getSessionContext(session);
        const Compiler = require('./lib/compiler');
        const compiler = new Compiler({ templateEngine: te });
        const draft = compiler.compileDraft(ctx);
        out.draftCompiled = draft.completedSubsections + '/' + draft.totalSubsections;
        
        const dg = new (require('./lib/draft-generator'))({ templateEngine: te, compiler });
        dg.generateDraft(session, ctx, draft);
        out.draftGenerated = true;
        out.sessionStatus = session.status;
        out.hasDraft = !!session.draft;
        
        // Move to completed
        await sm.completeSession(session.sessionId);
        out.completed = true;
      } catch(e) {
        out.readError = e.message;
      }
    }
  } else {
    out.userId = active[0].telegramUserId;
    out.sessionId = active[0].sessionId;
    out.status = active[0].status;
    out.allComplete = se.allSectionsComplete(active[0]);
    out.answers = Object.keys(active[0].answers||{}).length;
    out.risks = (active[0].risks||[]).length;
    
    const r = await se.signalCompletion(active[0]);
    out.signalOk = true;
    
    const ctx = se.getSessionContext(active[0]);
    const Compiler = require('./lib/compiler');
    const compiler = new Compiler({ templateEngine: te });
    const draft = compiler.compileDraft(ctx);
    out.draftCompiled = draft.completedSubsections + '/' + draft.totalSubsections;
    
    const dg = new (require('./lib/draft-generator'))({ templateEngine: te, compiler });
    dg.generateDraft(active[0], ctx, draft);
    out.draftOk = true;
    out.hasDraft = !!active[0].draft;
    
    await sm.completeSession(active[0].sessionId);
    out.completed = true;
  }
  
  fs.writeFileSync('/home/user1/fix-v3-output.json', JSON.stringify(out, null, 2));
  console.log('DONE');
}

main().catch(e => {
  fs.writeFileSync('/home/user1/fix-v3-output.json', JSON.stringify({ fatal: e.message, stack: e.stack.split('\n').slice(0,4).join(';') }, null, 2));
  console.log('FATAL:', e.message);
});
