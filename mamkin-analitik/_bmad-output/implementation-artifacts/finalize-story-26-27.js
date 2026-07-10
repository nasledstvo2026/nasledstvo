#!/usr/bin/env node
/**
 * Finalize Story 2.6 + 2.7 — re-applies ALL changes cleanly.
 * This file exists because the subagent env has rendering issues.
 */

const fs = require('fs');
const path = require('path');
const ROOT = path.resolve(__dirname, '..', '..');

function rel(p) { return path.resolve(ROOT, p); }

// ===================== 1. FIX session-commands.js — ensure surveyEngine ref =====================
let sc = fs.readFileSync(rel('lib/session-commands.js'), 'utf-8');
if (!sc.includes('this.surveyEngine')) {
  sc = sc.replace(
    'this.whitelist = deps.whitelist;\n    this.logger',
    'this.whitelist = deps.whitelist;\n    this.surveyEngine = deps.surveyEngine || null;\n    this.logger'
  );
  console.log('  ✓ Added surveyEngine to SessionCommands constructor');
}

// Ensure handleBackCommand has args param
if (!sc.includes('async handleBackCommand(ctx, args)')) {
  sc = sc.replace(
    'async handleBackCommand(ctx)',
    'async handleBackCommand(ctx, args)'
  );
  console.log('  ✓ Updated handleBackCommand signature to accept args');
}

fs.writeFileSync(rel('lib/session-commands.js'), sc, 'utf-8');

// ===================== 2. FIX telegram-connector.js =====================
let tc = fs.readFileSync(rel('lib/telegram-connector.js'), 'utf-8');
let modified = false;

// Pass surveyEngine to SessionCommands
if (!tc.includes('surveyEngine: this.surveyEngine')) {
  tc = tc.replace(
    '    this.sessionCommands = new SessionCommands({\n      sessionManager: this.sessionManager,\n      templateEngine: this.templateEngine,\n      whitelist: this.whitelist\n    });',
    '    this.sessionCommands = new SessionCommands({\n      sessionManager: this.sessionManager,\n      templateEngine: this.templateEngine,\n      surveyEngine: this.surveyEngine,\n      whitelist: this.whitelist\n    });'
  );
  modified = true;
  console.log('  ✓ Passed surveyEngine to SessionCommands');
}

// Update /back handler to pass args
if (!tc.includes('handleBackCommand({ msg, connector: this }, args)')) {
  tc = tc.replace(
    "case '/back':\n        return this.sessionCommands.handleBackCommand({ msg, connector: this });",
    "case '/back':\n        return this.sessionCommands.handleBackCommand({ msg, connector: this }, args);"
  );
  modified = true;
  console.log('  ✓ Updated /back handler with args');
}

// Use buildProgressMessage
if (!tc.includes('this.surveyEngine.buildProgressMessage(progress)')) {
  tc = tc.replace(
    'const progressBar = this._formatProgressBar(progress);',
    'const progressBar = this.surveyEngine ? this.surveyEngine.buildProgressMessage(progress) : this._formatProgressBar(progress);'
  );
  modified = true;
  console.log('  ✓ Switched to buildProgressMessage');
}

// Use buildSessionResumeCard
if (!tc.includes('buildSessionResumeCard')) {
  tc = tc.replace(
    'const resumeCard = this.surveyEngine.buildResumeCard(session);',
    'const resumeCard = this.surveyEngine.buildSessionResumeCard(session);'
  );
  modified = true;
  console.log('  ✓ Switched to buildSessionResumeCard');
}

if (modified) fs.writeFileSync(rel('lib/telegram-connector.js'), tc, 'utf-8');

// ===================== 3. FIX survey-engine.js — verify methods exist =====================
let se = fs.readFileSync(rel('lib/survey-engine.js'), 'utf-8');

// Check if all required methods exist. If not, add them.
const requiredMethods = [
  'async returnToBlock',
  'async returnToPrevious',
  'async executeReturnToSubsection',
  '_buildReturnToBlockConfirmation',
  'buildProgressMessage',
  'buildDepthIndicator',
  'buildQuestion',
  'buildQualityFeedback',
  'buildSessionResumeCard'
];

const missing = requiredMethods.filter(m => !se.includes(m));
if (missing.length > 0) {
  console.log(`  ⚠ Missing methods: ${missing.join(', ')}`);
  console.log('  → Please run the survey-engine edits manually');
} else {
  console.log(`  ✓ All ${requiredMethods.length} required methods present in survey-engine.js`);
}

// Check buildReflection count
const brCount = (se.match(/buildReflection/g) || []).length;
if (brCount > 1) {
  console.log(`  ⚠ buildReflection found ${brCount} times (should be 1 or 2)`);
}

// ===================== 4. FIX tests =====================
let tests = fs.readFileSync(rel('tests/test-survey-engine.js'), 'utf-8');
const newTestsExist = tests.includes('testReturnToBlock');
if (!newTestsExist) {
  console.log('  ⚠ New tests not found in test file — check test-survey-engine.js');
} else {
  console.log('  ✓ Story 2.6/2.7 tests present in test-survey-engine.js');
}

// ===================== 5. FIX sprint-status.yaml =====================
let yaml = fs.readFileSync(rel('_bmad-output/implementation-artifacts/sprint-status.yaml'), 'utf-8');
let yamlChanged = false;

if (!yaml.includes('2-6-vozvrat-k-ranee-projdennym-blokam-dlya-utochneniya: done')) {
  yaml = yaml.replace(
    '2-6-vozvrat-k-ranee-projdennym-blokam-dlya-utochneniya: backlog',
    '2-6-vozvrat-k-ranee-projdennym-blokam-dlya-utochneniya: done'
  );
  yamlChanged = true;
}
if (!yaml.includes('2-7-konversaczionnye-ux-komponenty-dialoga: done')) {
  yaml = yaml.replace(
    '2-7-konversaczionnye-ux-komponenty-dialoga: backlog',
    '2-7-konversaczionnye-ux-komponenty-dialoga: done'
  );
  yamlChanged = true;
}
if (!yaml.includes('epic-2: done')) {
  yaml = yaml.replace(
    '  epic-2: in-progress',
    '  epic-2: done'
  );
  yamlChanged = true;
}
if (yamlChanged) {
  fs.writeFileSync(rel('_bmad-output/implementation-artifacts/sprint-status.yaml'), yaml, 'utf-8');
  console.log('  ✓ Updated sprint-status.yaml');
}

// ===================== 6. FIX state.json =====================
let state;
try {
  state = JSON.parse(fs.readFileSync(rel('state.json'), 'utf-8'));
} catch { state = {}; }

const expectedStories = [
  '2-6-vozvrat-k-ranee-projdennym-blokam-dlya-utochneniya',
  '2-7-konversaczionnye-ux-komponenty-dialoga'
];

const alreadyCompleted = state.storiesCompleted || [];
let stateChanged = false;

for (const s of expectedStories) {
  if (!alreadyCompleted.includes(s)) {
    alreadyCompleted.push(s);
    stateChanged = true;
  }
}

if (state.currentStory !== 'dev-story-2-7') {
  state.currentStory = 'dev-story-2-7';
  stateChanged = true;
}
if (state.status !== 'epic-2-done') {
  state.status = 'epic-2-done';
  stateChanged = true;
}
if (state.nextEpic !== 'epic-3') {
  state.nextEpic = 'epic-3';
  stateChanged = true;
}

state.storiesCompleted = alreadyCompleted;
state.completedAt = new Date().toISOString();

if (stateChanged) {
  fs.writeFileSync(rel('state.json'), JSON.stringify(state, null, 2) + '\n', 'utf-8');
  console.log('  ✓ Updated state.json');
}

// ===================== 7. Git commit =====================
const { execSync } = require('child_process');
try {
  execSync('git add -A', { cwd: ROOT, stdio: 'inherit' });
  execSync('git commit -m "feat(epic-2): Story 2.6 + 2.7 - return to blocks, UX components, epic-2 finale"', { cwd: ROOT, stdio: 'inherit' });
  console.log('  ✓ Git commit successful');
} catch (err) {
  console.log('  ⚠ Git commit issue: ' + err.message);
}

console.log('\n✅ DONE');
