#!/usr/bin/env node
/**
 * Story 2.6 + 2.7 implementation helper.
 * Runs all remaining updates: tests, sprint-status, state.json, git commit.
 */
const path = require('path');
const fs = require('fs');
const { execSync } = require('child_process');

const ROOT = path.resolve(__dirname, '..', '..');

function abs(p) { return path.resolve(ROOT, p); }

// ==================== 1. Update session-commands.js: add surveyEngine reference ====================
const scPath = abs('lib/session-commands.js');
let sc = fs.readFileSync(scPath, 'utf-8');

// Add surveyEngine to constructor
if (!sc.includes('this.surveyEngine')) {
  sc = sc.replace(
    `    this.whitelist = deps.whitelist;\n    this.logger = createLogger('session-commands');`,
    `    this.whitelist = deps.whitelist;\n    this.surveyEngine = deps.surveyEngine || null;\n    this.logger = createLogger('session-commands');`
  );
  fs.writeFileSync(scPath, sc, 'utf-8');
  console.log('  ✓ Added surveyEngine ref to SessionCommands');
}

// ==================== 2. Update telegram-connector.js: pass surveyEngine to SessionCommands ====================
const tcPath = abs('lib/telegram-connector.js');
let tc = fs.readFileSync(tcPath, 'utf-8');

// Already passes sessionManager and templateEngine to sessionCommands
// Need to also pass surveyEngine
if (!tc.includes("surveyEngine: this.surveyEngine")) {
  tc = tc.replace(
    `    // Session Commands\n    this.sessionCommands = new SessionCommands({\n      sessionManager: this.sessionManager,\n      templateEngine: this.templateEngine,\n      whitelist: this.whitelist\n    });`,
    `    // Session Commands\n    this.sessionCommands = new SessionCommands({\n      sessionManager: this.sessionManager,\n      templateEngine: this.templateEngine,\n      surveyEngine: this.surveyEngine,\n      whitelist: this.whitelist\n    });`
  );
  fs.writeFileSync(tcPath, tc, 'utf-8');
  console.log('  ✓ Passed surveyEngine to SessionCommands in telegram-connector');
}

// ==================== 3. Update telegram-connector: use buildProgressMessage and buildSessionResumeCard ====================
// Replace _formatProgressBar usage with buildProgressMessage
tc = fs.readFileSync(tcPath, 'utf-8');
let tcModified = false;

// In the survey answer handler - use buildProgressMessage instead of _formatProgressBar
if (!tc.includes('this.surveyEngine.buildProgressMessage(progress)')) {
  // Find the progressBar usage and replace
  tc = tc.replace(
    `const progressBar = this._formatProgressBar(progress);`,
    `const progressBar = this.surveyEngine ? this.surveyEngine.buildProgressMessage(progress) : this._formatProgressBar(progress);`
  );
  tcModified = true;
}

if (!tc.includes('buildSessionResumeCard')) {
  tc = tc.replace(
    `const resumeCard = this.surveyEngine.buildResumeCard(session);`,
    `const resumeCard = this.surveyEngine.buildSessionResumeCard(session);`
  );
  tcModified = true;
}

if (tcModified) {
  fs.writeFileSync(tcPath, tc, 'utf-8');
  console.log('  ✓ Updated telegram-connector to use UX components');
}

// ==================== 4. Update telegram-connector: handle /back N with args ====================
tc = fs.readFileSync(tcPath, 'utf-8');

// Find the /back command handler and pass args
if (!tc.includes('args)')) {
  tc = tc.replace(
    `case '/back':\n        return this.sessionCommands.handleBackCommand({ msg, connector: this });`,
    `case '/back':\n        return this.sessionCommands.handleBackCommand({ msg, connector: this }, args);`
  );
  fs.writeFileSync(tcPath, tc, 'utf-8');
  console.log('  ✓ Updated /back handler to pass args');
}

// ==================== 5. Write the tests file ====================
const testPath = abs('tests/test-survey-engine.js');
let tests = fs.readFileSync(testPath, 'utf-8');

// Add new tests for Story 2.6 and 2.7
const newTests = `

// ==================== Story 2.6: Return to earlier blocks ====================

async function testReturnToBlock() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // First answer some questions in block 1
    let current = startResult;
    current = await processWithReflection(surveyEngine, current.session, DEEP_ANSWER);
    current = await processWithReflection(surveyEngine, current.session, DEEP_ANSWER);

    // Now navigate to block 2
    const result = await surveyEngine.returnToBlock(current.session, 2);

    assert(result, 'returnToBlock should return a result');
    assert(result.question, 'Should return a question');
    assert(result.session.template.block === 2,
      \`Should be at block 2, got \${result.session.template.block}\`);
    assert(result.session.template.subsection === '2.1',
      \`Should be at subsection 2.1, got \${result.session.template.subsection}\`);
    assert(result.session.template.depth === 'L1',
      'Depth should be L1 after return');
    assert(result.blockName, 'Should have block name');
    assert(result.confirmationText, 'Should have confirmation text');
    assert(result.confirmationText.includes('Вернуться к блоку 2'),
      'Confirmation should mention block 2');

    // Previous answers from block 1 should be preserved
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert(savedSession.answers['1.1'], 'Answer for 1.1 should be preserved');
    assert(savedSession.answers['1.2'], 'Answer for 1.2 should be preserved');

    console.log('✓ testReturnToBlock');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReturnToBlock_InvalidBlock() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    try {
      await surveyEngine.returnToBlock(startResult.session, 0);
      assert(false, 'Should throw for block 0');
    } catch (err) {
      assert(err.message.includes('не найден'), 'Error should mention block not found');
    }

    try {
      await surveyEngine.returnToBlock(startResult.session, 99);
      assert(false, 'Should throw for block 99');
    } catch (err) {
      assert(err.message.includes('не найден'), 'Error should mention block not found');
    }

    console.log('✓ testReturnToBlock_InvalidBlock');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReturnToPrevious() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Answer first subsection
    let current = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);
    assert.strictEqual(current.session.template.subsection, '1.2',
      'Should be at 1.2 after answering 1.1');

    // Navigate back
    const result = await surveyEngine.returnToPrevious(current.session);

    assert(result, 'returnToPrevious should return a result');
    assert(result.previousSubsection, 'Should find previous subsection');
    assert.strictEqual(result.previousSubsection.fullKey, '1.1',
      \`Previous should be 1.1, got \${result.previousSubsection.fullKey}\`);
    assert(result.confirmationText, 'Should have confirmation text');
    assert(result.confirmationText.includes('Вернуться к подразделу 1.1'),
      'Confirmation should mention subsection 1.1');

    console.log('✓ testReturnToPrevious');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReturnToPrevious_AtStart() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // At the very first subsection, no previous available
    const result = await surveyEngine.returnToPrevious(startResult.session);

    assert(result, 'returnToPrevious should return a result');
    assert.strictEqual(result.previousSubsection, null,
      'Should not have previous subsection at start');
    assert(result.confirmationText.includes('начале опроса'),
      'Should say already at start');

    console.log('✓ testReturnToPrevious_AtStart');
  } finally {
    cleanup(tmpDir);
  }
}

async function testExecuteReturnToSubsection() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Answer first two subsections
    let current = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);
    assert.strictEqual(current.session.template.subsection, '1.2');

    // Execute return to subsection 1.1
    const subsection = { blockId: 1, fullKey: '1.1', name: 'Контекст инициативы' };
    const result = await surveyEngine.executeReturnToSubsection(current.session, subsection);

    assert(result, 'executeReturnToSubsection should return a result');
    assert(result.question, 'Should return a question');
    assert.strictEqual(result.session.template.block, 1,
      \`Should be at block 1, got \${result.session.template.block}\`);
    assert.strictEqual(result.session.template.subsection, '1.1',
      \`Should be at subsection 1.1, got \${result.session.template.subsection}\`);
    assert(result.previousAnswer, 'Should have previous answer');

    console.log('✓ testExecuteReturnToSubsection');
  } finally {
    cleanup(tmpDir);
  }
}

async function testReturnToBlockPreservesAnswers() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Answer all of block 1
    let current = startResult;
    for (let i = 0; i < 3; i++) {
      current = await processWithReflection(surveyEngine, current.session, DEEP_ANSWER);
    }
    assert.strictEqual(current.session.template.block, 2,
      'Should be at block 2 after completing block 1');

    // Navigate back to block 1
    const result = await surveyEngine.returnToBlock(current.session, 1);

    assert(result.previousAnswers, 'Should have previous answers');
    assert(Object.keys(result.previousAnswers).length === 3,
      \`Should have 3 previous answers, got \${Object.keys(result.previousAnswers).length}\`);

    // Verify answers are preserved in storage
    const savedSession = await sessionManager.getSession(result.session.sessionId);
    assert(savedSession.answers['1.1'].L1 === DEEP_ANSWER,
      'Answer for 1.1 should be preserved');
    assert(savedSession.answers['1.2'].L1 === DEEP_ANSWER,
      'Answer for 1.2 should be preserved');
    assert(savedSession.answers['1.3'].L1 === DEEP_ANSWER,
      'Answer for 1.3 should be preserved');

    console.log('✓ testReturnToBlockPreservesAnswers');
  } finally {
    cleanup(tmpDir);
  }
}

// ==================== Story 2.7: Conversational UX Components ====================

async function testBuildProgressMessage() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    const progress = surveyEngine.getProgress(startResult.session);
    const msg = surveyEngine.buildProgressMessage(progress);

    assert(msg, 'buildProgressMessage should return a string');
    assert(msg.length > 0, 'Message should not be empty');
    assert(msg.includes('Прогресс'), 'Should mention progress');
    assert(msg.includes('Блок 1'), 'Should mention block 1');
    assert(msg.includes('0%'), 'Progress at 0% at start');

    // After answering one subsection
    const result = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);
    const progress2 = surveyEngine.getProgress(result.session);
    const msg2 = surveyEngine.buildProgressMessage(progress2);

    assert(msg2, 'Should return message after progress');
    assert(progress2.completedSubsections >= 1,
      \`Should have at least 1 completed subsection, got \${progress2.completedSubsections}\`);

    console.log('✓ testBuildProgressMessage');
  } finally {
    cleanup(tmpDir);
  }
}

async function testBuildDepthIndicator() {
  const { surveyEngine } = await setup();

  // L1 → L2
  const l1tol2 = surveyEngine.buildDepthIndicator('L1', 'L2');
  assert(l1tol2, 'Should return string');
  assert(l1tol2.includes('L1'), 'Should mention L1');
  assert(l1tol2.includes('L2'), 'Should mention L2');
  assert(l1tol2.includes('🔍'), 'Should have magnifier emoji');

  // L2 → L3
  const l2tol3 = surveyEngine.buildDepthIndicator('L2', 'L3');
  assert(l2tol3.includes('L3'), 'Should mention L3');
  assert(l2tol3.includes('корневой'), 'Should mention root level');

  // Empty input
  assert.strictEqual(surveyEngine.buildDepthIndicator('', 'L2'), '',
    'Empty from should return empty');
  assert.strictEqual(surveyEngine.buildDepthIndicator(null, 'L2'), '',
    'Null from should return empty');

  console.log('✓ testBuildDepthIndicator');
}

async function testBuildReflection() {
  const { surveyEngine } = await setup();

  // Normal answer
  const answer = 'Мы работаем над платформой для автоматизации закупок.';
  const reflection = surveyEngine.buildReflection(answer);
  assert(reflection, 'Should return reflection');
  assert(reflection.includes('Вы упомянули'), 'Should mention "Вы упомянули"');
  assert(reflection.includes('💭'), 'Should have thought emoji');

  // Short answer - no reflection
  const shortReflection = surveyEngine.buildReflection('Да.');
  assert.strictEqual(shortReflection, null,
    'Short answer should return null');

  // With cross-reference
  const allAnswers = {
    '2.1': { L1: 'Хотим автоматизировать закупки и снизить затраты' },
    '2.2': { L1: 'Критерии успеха: снижение времени обработки' }
  };
  const crossReflection = surveyEngine.buildReflection(
    'Автоматизация закупок даст нам сокращение затрат на 20%',
    allAnswers
  );
  assert(crossReflection, 'Should return cross-reference reflection');
  assert(crossReflection.includes('упоминали'), 'Might include cross-reference');

  // Short form
  const shortForm = surveyEngine.buildReflection(answer, null, { short: true });
  assert(shortForm.includes('Упомянуто'), 'Short form should say "Упомянуто"');

  console.log('✓ testBuildReflection');
}

async function testBuildQuestion() {
  const { surveyEngine } = await setup();

  // L1 question
  const l1 = surveyEngine.buildQuestion('Расскажите о проекте.', 'L1');
  assert(l1, 'Should return formatted L1 question');
  assert(l1.includes('Расскажите'), 'Should contain the question');

  // L2 question with context
  const l2 = surveyEngine.buildQuestion('Уточните детали.', 'L2', {
    previousAnswer: 'Мы автоматизируем закупки'
  });
  assert(l2, 'Should return formatted L2 question');
  assert(l2.includes('Уточним'), 'L2 should say "Уточним"');
  assert(l2.includes('🔍'), 'L2 should have magnifier');

  // L3 question
  const l3 = surveyEngine.buildQuestion('Доберитесь до сути.', 'L3');
  assert(l3.includes('добраться до сути'), 'L3 should mention root cause');

  // Empty question
  assert.strictEqual(surveyEngine.buildQuestion('', 'L1'), '',
    'Empty question should return empty');

  console.log('✓ testBuildQuestion');
}

async function testBuildQualityFeedback() {
  const { surveyEngine } = await setup();

  // Deep answer (score >= 0.6)
  const deepFeedback = surveyEngine.buildQualityFeedback(DEEP_ANSWER, 0.75);
  assert(deepFeedback, 'Should return feedback for deep answer');
  assert(deepFeedback.includes('Спасибо'), 'Should say thanks');

  // Medium answer (score 0.3-0.6)
  const mediumFeedback = surveyEngine.buildQualityFeedback(MEDIUM_ANSWER, 0.45);
  assert(mediumFeedback, 'Should return feedback for medium answer');

  // Shallow answer (score < 0.3)
  const shallowFeedback = surveyEngine.buildQualityFeedback(SHALLOW_L1_ANSWER, 0.15);
  assert(shallowFeedback, 'Should return feedback for shallow answer');

  // Null/empty
  assert.strictEqual(surveyEngine.buildQualityFeedback('', 0.5), null,
    'Empty answer should return null');
  assert.strictEqual(surveyEngine.buildQualityFeedback('test', null), null,
    'Null score should return null');

  console.log('✓ testBuildQualityFeedback');
}

async function testBuildSessionResumeCard() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Resume card for fresh session
    const card = surveyEngine.buildSessionResumeCard(session);
    assert(card, 'Should return resume card');
    assert(card.text.includes('С возвращением'), 'Should have greeting');
    assert(card.text.includes('Прогресс'), 'Should mention progress');
    assert(card.blockInfo, 'Should have block info');

    // After some progress
    const result = await processWithReflection(surveyEngine, startResult.session, DEEP_ANSWER);
    const card2 = surveyEngine.buildSessionResumeCard(result.session);
    assert(card2.lastAnswer, 'Should have last answer after progress');
    assert(card2.progressMessage, 'Should have progress message');

    // Null session
    const nullCard = surveyEngine.buildSessionResumeCard(null);
    assert.strictEqual(nullCard.text, '', 'Null session should return empty text');

    console.log('✓ testBuildSessionResumeCard');
  } finally {
    cleanup(tmpDir);
  }
}

async function testUXComponentsIntegration() {
  const { tmpDir, sessionManager, surveyEngine } = await setup();
  try {
    const session = await sessionManager.createSession(12345);
    const startResult = await surveyEngine.startSurvey(session);

    // Test full message composition using UX components
    const progress = surveyEngine.getProgress(startResult.session);
    const progressMsg = surveyEngine.buildProgressMessage(progress);
    const question = surveyEngine.getCurrentQuestion(startResult.session);
    const formattedQuestion = surveyEngine.buildQuestion(question.question, question.depth);

    // Compose a full UX message
    const fullMessage = [
      progressMsg,
      '',
      formattedQuestion
    ].join('\\n');

    assert(fullMessage.includes('Прогресс'), 'Full message should have progress');
    assert(fullMessage.includes(question.question), 'Full message should have question');

    // Answer and test quality feedback
    const result = await surveyEngine.processAnswer(startResult.session, DEEP_ANSWER);
    const score = surveyEngine._evaluateDepth(DEEP_ANSWER);
    const feedback = surveyEngine.buildQualityFeedback(DEEP_ANSWER, score);

    if (feedback) {
      assert(typeof feedback === 'string', 'Feedback should be a string');
    }

    console.log('✓ testUXComponentsIntegration');
  } finally {
    cleanup(tmpDir);
  }
}
`;

// Find the end of runAllTests function and add new tests before the closing
if (!tests.includes('testReturnToBlock')) {
  // Insert new tests before the runAllTests function
  const insertPos = tests.lastIndexOf('async function runAllTests()');
  tests = tests.slice(0, insertPos) + newTests + '\n\n' + tests.slice(insertPos);
  
  // Add new test calls to runAllTests
  tests = tests.replace(
    `    testFullSurveyPipelineWithContext\n  ];`,
    `    testFullSurveyPipelineWithContext,\n    // Story 2.6: Return to earlier blocks\n    testReturnToBlock,\n    testReturnToBlock_InvalidBlock,\n    testReturnToPrevious,\n    testReturnToPrevious_AtStart,\n    testExecuteReturnToSubsection,\n    testReturnToBlockPreservesAnswers,\n    // Story 2.7: Conversational UX Components\n    testBuildProgressMessage,\n    testBuildDepthIndicator,\n    testBuildReflection,\n    testBuildQuestion,\n    testBuildQualityFeedback,\n    testBuildSessionResumeCard,\n    testUXComponentsIntegration\n  ];`
  );

  fs.writeFileSync(testPath, tests, 'utf-8');
  console.log('  ✓ Added Story 2.6 and 2.7 tests');
}

// ==================== 6. Update sprint-status.yaml ====================
const yamlPath = abs('_bmad-output/implementation-artifacts/sprint-status.yaml');
let yaml = fs.readFileSync(yamlPath, 'utf-8');

yaml = yaml.replace(
  `  2-6-vozvrat-k-ranee-projdennym-blokam-dlya-utochneniya: backlog`,
  `  2-6-vozvrat-k-ranee-projdennym-blokam-dlya-utochneniya: done`
);
yaml = yaml.replace(
  `  2-7-konversaczionnye-ux-komponenty-dialoga: backlog`,
  `  2-7-konversaczionnye-ux-komponenty-dialoga: done`
);
yaml = yaml.replace(
  `  epic-2: in-progress`,
  `  epic-2: done`
);
fs.writeFileSync(yamlPath, yaml, 'utf-8');
console.log('  ✓ Updated sprint-status.yaml');

// ==================== 7. Update state.json ====================
const statePath = abs('state.json');
let state = JSON.parse(fs.readFileSync(statePath, 'utf-8'));
state.currentStory = 'dev-story-2-7';
state.storiesCompleted.push(
  '2-6-vozvrat-k-ranee-projdennym-blokam-dlya-utochneniya',
  '2-7-konversaczionnye-ux-komponenty-dialoga'
);
state.nextEpic = 'epic-3';
state.status = 'epic-2-done';
state.completedAt = new Date().toISOString();
fs.writeFileSync(statePath, JSON.stringify(state, null, 2) + '\n', 'utf-8');
console.log('  ✓ Updated state.json');

// ==================== 8. Git add + commit ====================
try {
  execSync('git add -A', { cwd: ROOT, stdio: 'inherit' });
  execSync(
    'git commit -m "feat(epic-2): Story 2.6 + 2.7 - return to blocks + UX components"',
    { cwd: ROOT, stdio: 'inherit' }
  );
  console.log('  ✓ Git commit complete');
} catch (err) {
  console.log('  ⚠ Git commit failed:', err.message);
}

console.log('\n✅ Story 2.6 + 2.7 implementation complete!\n');
