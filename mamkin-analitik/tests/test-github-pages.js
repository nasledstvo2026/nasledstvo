/**
 * Тесты GitHub Pages Publisher (Story 4.3 — Publication on GitHub Pages)
 *
 * Проверяет:
 *   1. lib/github-pages.js — GitHubPagesPublisher
 *      - publishDraft(sessionId, docxPath, htmlPath, projectName)
 *      - _copyToPagesDir(src, dest) — file copy
 *      - _commitAndPush(sessionId, projectName) — git add/commit/push
 *      - _generateUrls() — URL generation
 *   2. Конфигурация
 *      - isConfigured / env vars fallback
 *      - dry-run mode
 *   3. Валидация
 *      - Throws если repo/token не настроены
 *      - Throws если DOCX/HTML файлы не существуют
 *   4. Интеграция
 *      - Формат сообщения коммита: "Add BRD session [sessionId] - [project name]"
 *      - URL формат: https://{org}.github.io/{repo}/sessions/{sessionId}/index.html
 */

const path = require('path');
const fs = require('fs');
const assert = require('assert');
const os = require('os');
const { execSync } = require('child_process');

const GitHubPagesPublisher = require('../lib/github-pages');

// ==================== Test Helpers ====================

/**
 * Создаёт временную директорию для тестов.
 * @returns {{ dir: string, cleanup: Function }}
 */
function getTempDir() {
  const dir = fs.mkdtempSync(path.join(os.tmpdir(), 'gh-pages-test-'));
  return {
    dir,
    cleanup: () => {
      try { fs.rmSync(dir, { recursive: true, force: true }); } catch {}
    }
  };
}

/**
 * Создаёт тестовый файл.
 * @param {string} filePath
 * @param {string} [content]
 * @returns {string}
 */
function createTestFile(filePath, content = 'test content') {
  const dir = path.dirname(filePath);
  fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(filePath, content);
  return filePath;
}

/**
 * Инициализирует git-репозиторий в указанной директории.
 * @param {string} dir
 * @param {string} [branch]
 */
function initGitRepo(dir, branch = 'gh-pages') {
  fs.mkdirSync(dir, { recursive: true });
  execSync(`git init -b ${branch} "${dir}"`, { stdio: 'pipe' });
  execSync(`git -C "${dir}" config user.email "test@test.com"`, { stdio: 'pipe' });
  execSync(`git -C "${dir}" config user.name "Test"`, { stdio: 'pipe' });
  // Создаём начальный коммит, чтобы не было ошибок при pull/reset
  fs.writeFileSync(path.join(dir, '.gitkeep'), '');
  execSync(`git -C "${dir}" add -A && git -C "${dir}" commit -m "init"`, { stdio: 'pipe' });
}

// ==================== Test Data ====================

const TEST_REPO = 'test-org/mamkin-analitik';
const TEST_TOKEN = 'ghp_test_token_12345';
const TEST_SESSION_ID = 'sess_test_001';
const TEST_PROJECT = 'Тестовый проект';
const TEST_BASE_URL = 'https://test-org.github.io/mamkin-analitik';

// ==================== Tests ====================

let currentTest = 0;
let passed = 0;
let failed = 0;
const errors = [];

function test(name, fn) {
  currentTest++;
  try {
    fn();
    passed++;
    console.log(`  ✅ Test ${currentTest}: ${name}`);
  } catch (err) {
    failed++;
    errors.push({ test: currentTest, name, error: err.message, stack: err.stack });
    console.log(`  ❌ Test ${currentTest}: ${name} — ${err.message}`);
  }
}

function testAsync(name, fn) {
  currentTest++;
  fn().then(
    () => {
      passed++;
      console.log(`  ✅ Test ${currentTest}: ${name}`);
    },
    (err) => {
      failed++;
      errors.push({ test: currentTest, name, error: err.message, stack: err.stack });
      console.log(`  ❌ Test ${currentTest}: ${name} — ${err.message}`);
    }
  );
}

function assertThrows(fn, expectedMsg) {
  try {
    fn();
    assert.fail(`Expected error with "${expectedMsg}", but no error was thrown`);
  } catch (err) {
    if (err.code === 'ERR_ASSERTION') throw err;
    if (expectedMsg && !err.message.includes(expectedMsg)) {
      assert.fail(`Expected error containing "${expectedMsg}", got: "${err.message}"`);
    }
  }
}

// ==================== Configuration Tests ====================

console.log('\n📋 Configuration Tests');

test('constructor with explicit config', () => {
  const publisher = new GitHubPagesPublisher({
    repo: TEST_REPO,
    token: TEST_TOKEN,
    branch: 'gh-pages',
    baseUrl: TEST_BASE_URL,
    dryRun: true
  });

  assert.strictEqual(publisher.repo, TEST_REPO);
  assert.strictEqual(publisher.token, TEST_TOKEN);
  assert.strictEqual(publisher.branch, 'gh-pages');
  assert.strictEqual(publisher.baseUrl, TEST_BASE_URL);
  assert.strictEqual(publisher.dryRun, true);
  assert.strictEqual(publisher.isConfigured, true);
});

test('constructor falls back to env vars', () => {
  const origRepo = process.env.GITHUB_PAGES_REPO;
  const origToken = process.env.GITHUB_TOKEN;

  process.env.GITHUB_PAGES_REPO = TEST_REPO;
  process.env.GITHUB_TOKEN = TEST_TOKEN;

  try {
    const publisher = new GitHubPagesPublisher();
    assert.strictEqual(publisher.repo, TEST_REPO);
    assert.strictEqual(publisher.token, TEST_TOKEN);
    assert.strictEqual(publisher.isConfigured, true);
  } finally {
    if (origRepo) process.env.GITHUB_PAGES_REPO = origRepo;
    else delete process.env.GITHUB_PAGES_REPO;
    if (origToken) process.env.GITHUB_TOKEN = origToken;
    else delete process.env.GITHUB_TOKEN;
  }
});

test('isConfigured returns false when repo is missing', () => {
  const publisher = new GitHubPagesPublisher({ repo: '', token: TEST_TOKEN });
  assert.strictEqual(publisher.isConfigured, false);
});

test('isConfigured returns false when token is missing', () => {
  const publisher = new GitHubPagesPublisher({ repo: TEST_REPO, token: '' });
  assert.strictEqual(publisher.isConfigured, false);
});

test('isConfigured returns false when both are missing', () => {
  const publisher = new GitHubPagesPublisher({});
  assert.strictEqual(publisher.isConfigured, false);
});

test('baseUrl is computed from repo when not provided', () => {
  const publisher = new GitHubPagesPublisher({
    repo: 'my-org/my-repo',
    token: TEST_TOKEN,
    dryRun: true
  });
  assert.strictEqual(publisher.baseUrl, 'https://my-org.github.io/my-repo');
});

test('baseUrl is empty when repo is not set', () => {
  const publisher = new GitHubPagesPublisher({ repo: '', token: '' });
  assert.strictEqual(publisher.baseUrl, '');
});

test('dryRun from config takes precedence', () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  assert.strictEqual(publisher.dryRun, true);
});

test('default branch is gh-pages', () => {
  const publisher = new GitHubPagesPublisher({});
  assert.strictEqual(publisher.branch, 'gh-pages');
});

// ==================== Validation Tests ====================

console.log('\n📋 Validation Tests');

testAsync('publishDraft throws when repo not configured (empty)', async () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  try {
    await publisher.publishDraft('test', '/fake/docx', '/fake/html', 'Test');
    assert.fail('Expected error was not thrown');
  } catch (err) {
    assert.ok(err.message.includes('не настроен репозиторий'));
  }
});

testAsync('publishDraft throws when files do not exist', async () => {
  const publisher = new GitHubPagesPublisher({
    repo: TEST_REPO,
    token: TEST_TOKEN,
    dryRun: true
  });

  try {
    await publisher.publishDraft('test', '/nonexistent/docx.docx', '/nonexistent/index.html', 'Test');
    assert.fail('Expected error was not thrown');
  } catch (err) {
    assert.ok(err.message.includes('не найден'));
  }
});

test('_assertFilesExist throws when docx missing', () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  const tmp = getTempDir();
  try {
    const htmlPath = path.join(tmp.dir, 'index.html');
    fs.writeFileSync(htmlPath, '<html></html>');
    assertThrows(() => publisher._assertFilesExist('/fake/docx.docx', htmlPath), 'не найден');
  } finally {
    tmp.cleanup();
  }
});

test('_assertFilesExist throws when html missing', () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  const tmp = getTempDir();
  try {
    const docxPath = path.join(tmp.dir, 'test.docx');
    fs.writeFileSync(docxPath, 'fake docx');
    assertThrows(() => publisher._assertFilesExist(docxPath, '/fake/index.html'), 'не найден');
  } finally {
    tmp.cleanup();
  }
});

test('_assertFilesExist passes when both files exist', () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  const tmp = getTempDir();
  try {
    const docxPath = path.join(tmp.dir, 'test.docx');
    const htmlPath = path.join(tmp.dir, 'index.html');
    fs.writeFileSync(docxPath, 'fake docx');
    fs.writeFileSync(htmlPath, '<html></html>');
    publisher._assertFilesExist(docxPath, htmlPath);
  } finally {
    tmp.cleanup();
  }
});

// ==================== Copy Tests ====================

console.log('\n📋 File Copy Tests');

testAsync('_copyToPagesDir copies files to correct session directory', async () => {
  const publisher = new GitHubPagesPublisher({
    repo: TEST_REPO,
    token: TEST_TOKEN,
    dryRun: true
  });

  const tmp = getTempDir();
  try {
    const pagesDir = path.join(tmp.dir, 'pages');
    publisher.pagesDir = pagesDir;

    const docxPath = path.join(tmp.dir, 'brd-test.docx');
    const htmlPath = path.join(tmp.dir, 'output.html');
    createTestFile(docxPath, 'fake docx content');
    createTestFile(htmlPath, '<html>Test BRD</html>');

    const result = await publisher._copyToPagesDir(docxPath, htmlPath, TEST_SESSION_ID);

    const expectedSessionDir = path.join(pagesDir, 'sessions', TEST_SESSION_ID);
    assert.strictEqual(result.docxDest, path.join(expectedSessionDir, 'brd-test.docx'));
    assert.strictEqual(result.htmlDest, path.join(expectedSessionDir, 'index.html'));

    assert.ok(fs.existsSync(result.docxDest), 'DOCX должен существовать');
    assert.ok(fs.existsSync(result.htmlDest), 'HTML должен существовать');
    assert.strictEqual(fs.readFileSync(result.docxDest, 'utf-8'), 'fake docx content');
    assert.strictEqual(fs.readFileSync(result.htmlDest, 'utf-8'), '<html>Test BRD</html>');
  } finally {
    tmp.cleanup();
  }
});

testAsync('_copyToPagesDir creates nested session directories', async () => {
  const publisher = new GitHubPagesPublisher({
    repo: TEST_REPO,
    token: TEST_TOKEN,
    dryRun: true
  });

  const tmp = getTempDir();
  try {
    const pagesDir = path.join(tmp.dir, 'pages');
    publisher.pagesDir = pagesDir;

    const docxPath = path.join(tmp.dir, 'report.docx');
    const htmlPath = path.join(tmp.dir, 'web.html');
    createTestFile(docxPath, 'docx');
    createTestFile(htmlPath, 'html');

    await publisher._copyToPagesDir(docxPath, htmlPath, 'sess_deep/test/with/slashes');

    const expectedDir = path.join(pagesDir, 'sessions', 'sess_deep/test/with/slashes');
    assert.ok(fs.existsSync(expectedDir), 'Nested session directory должен быть создан');
    assert.ok(fs.existsSync(path.join(expectedDir, 'report.docx')));
  } finally {
    tmp.cleanup();
  }
});

// ==================== URL Generation Tests ====================

console.log('\n📋 URL Generation Tests');

test('_generateUrls returns correct docxUrl and htmlUrl', () => {
  const publisher = new GitHubPagesPublisher({
    repo: TEST_REPO,
    token: TEST_TOKEN,
    baseUrl: TEST_BASE_URL,
    pagesDir: '/tmp/pages',
    dryRun: true
  });

  const destPaths = {
    docxDest: `/tmp/pages/sessions/${TEST_SESSION_ID}/brd-final.docx`,
    htmlDest: `/tmp/pages/sessions/${TEST_SESSION_ID}/index.html`
  };

  const urls = publisher._generateUrls(TEST_SESSION_ID, destPaths);

  assert.strictEqual(urls.docxUrl, `${TEST_BASE_URL}/sessions/${TEST_SESSION_ID}/brd-final.docx`);
  assert.strictEqual(urls.htmlUrl, `${TEST_BASE_URL}/sessions/${TEST_SESSION_ID}/index.html`);
  assert.strictEqual(urls.sessionDir, `/tmp/pages/sessions/${TEST_SESSION_ID}`);
});

test('_generateUrls handles base URL with trailing slash', () => {
  const publisher = new GitHubPagesPublisher({
    repo: TEST_REPO,
    token: TEST_TOKEN,
    baseUrl: 'https://my-org.github.io/my-repo/',
    dryRun: true
  });

  const urls = publisher._generateUrls('sess_001', {
    docxDest: '/tmp/pages/sessions/sess_001/brd.docx',
    htmlDest: '/tmp/pages/sessions/sess_001/index.html'
  });

  assert.strictEqual(urls.docxUrl, 'https://my-org.github.io/my-repo/sessions/sess_001/brd.docx');
  assert.strictEqual(urls.htmlUrl, 'https://my-org.github.io/my-repo/sessions/sess_001/index.html');
});

test('_generateUrls handles HTML renamed to index.html', () => {
  const publisher = new GitHubPagesPublisher({
    repo: TEST_REPO,
    token: TEST_TOKEN,
    baseUrl: TEST_BASE_URL,
    dryRun: true
  });

  const urls = publisher._generateUrls('sess_002', {
    docxDest: `/tmp/pages/sessions/sess_002/report.docx`,
    htmlDest: `/tmp/pages/sessions/sess_002/index.html`
  });

  assert.ok(urls.htmlUrl.endsWith('/index.html'));
});

// ==================== Commit Message Tests ====================

console.log('\n📋 Commit Message Tests');

test('_formatCommitMessage formats correctly with sessionId and projectName', () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  const msg = publisher._formatCommitMessage(TEST_SESSION_ID, TEST_PROJECT);
  assert.strictEqual(msg, `Add BRD session ${TEST_SESSION_ID} - ${TEST_PROJECT}`);
});

test('_formatCommitMessage works without projectName', () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  const msg = publisher._formatCommitMessage(TEST_SESSION_ID);
  assert.strictEqual(msg, `Add BRD session ${TEST_SESSION_ID}`);
});

test('_formatCommitMessage handles empty projectName', () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  const msg = publisher._formatCommitMessage(TEST_SESSION_ID, '');
  assert.strictEqual(msg, `Add BRD session ${TEST_SESSION_ID}`);
});

test('_formatCommitMessage escapes double quotes', () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  const msg = publisher._formatCommitMessage('sess_001', 'Проект "Мамкин"');
  assert.ok(!msg.includes('"Мамкин"'));
  assert.ok(msg.includes('\\"Мамкин\\"'));
});

test('_formatCommitMessage accepts sessionId with special characters', () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  const msg = publisher._formatCommitMessage('sess-uuid-1234-5678', 'Test Project');
  assert.strictEqual(msg, 'Add BRD session sess-uuid-1234-5678 - Test Project');
});

test('_formatCommitMessage trims whitespace from projectName', () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  const msg = publisher._formatCommitMessage('sess_001', '  My Project  ');
  assert.strictEqual(msg, 'Add BRD session sess_001 - My Project');
});

// ==================== Integration Tests (with real git init) ====================

console.log('\n📋 Integration Tests (git init)');

testAsync('publishDraft with dryRun and real git repo works end-to-end', async () => {
  const tmp = getTempDir();
  try {
    const pagesDir = path.join(tmp.dir, 'pages-worktree');
    const docxPath = path.join(tmp.dir, 'brd.docx');
    const htmlPath = path.join(tmp.dir, 'output.html');
    createTestFile(docxPath, 'docx content');
    createTestFile(htmlPath, '<html>BRD</html>');

    // Инициализируем настоящий git репозиторий
    initGitRepo(pagesDir);

    const publisher = new GitHubPagesPublisher({
      repo: TEST_REPO,
      token: TEST_TOKEN,
      pagesDir,
      branch: 'gh-pages',
      dryRun: true,
      logger: {
        info: () => {},
        warn: () => {},
        error: () => {},
        debug: () => {}
      }
    });

    const result = await publisher.publishDraft(TEST_SESSION_ID, docxPath, htmlPath, TEST_PROJECT);

    // Проверяем URL
    assert.ok(result.docxUrl.includes(TEST_SESSION_ID));
    assert.ok(result.htmlUrl.includes(TEST_SESSION_ID));
    assert.ok(result.htmlUrl.endsWith('/index.html'));

    // Проверяем, что файлы скопированы
    const sessionDir = path.join(pagesDir, 'sessions', TEST_SESSION_ID);
    assert.ok(fs.existsSync(path.join(sessionDir, 'brd.docx')));
    assert.ok(fs.existsSync(path.join(sessionDir, 'index.html')));
  } finally {
    tmp.cleanup();
  }
});

testAsync('publishDraft with dryRun copies multiple sessions correctly', async () => {
  const tmp = getTempDir();
  try {
    const pagesDir = path.join(tmp.dir, 'gh-pages');
    initGitRepo(pagesDir);

    const publisher = new GitHubPagesPublisher({
      repo: 'my-org/business-requirements',
      token: 'ghp_fake123',
      pagesDir,
      dryRun: true,
      logger: { info: () => {}, warn: () => {}, error: () => {}, debug: () => {} }
    });

    // Публикуем первую сессию
    const docx1 = path.join(tmp.dir, 'session1.docx');
    const html1 = path.join(tmp.dir, 'session1.html');
    createTestFile(docx1, 'DOCX content for BRD');
    createTestFile(html1, '<html><body>BRD content</body></html>');

    const r1 = await publisher.publishDraft('sess_uuid_abc', docx1, html1, 'My Project');

    assert.ok(r1.docxUrl.startsWith('https://my-org.github.io/business-requirements/sessions/sess_uuid_abc/'));
    assert.ok(r1.htmlUrl.startsWith('https://my-org.github.io/business-requirements/sessions/sess_uuid_abc/'));

    const sessDir1 = path.join(pagesDir, 'sessions', 'sess_uuid_abc');
    assert.ok(fs.existsSync(path.join(sessDir1, 'session1.docx')));
    assert.ok(fs.existsSync(path.join(sessDir1, 'index.html')));
    assert.strictEqual(fs.readFileSync(path.join(sessDir1, 'session1.docx'), 'utf-8'), 'DOCX content for BRD');
    assert.strictEqual(fs.readFileSync(path.join(sessDir1, 'index.html'), 'utf-8'), '<html><body>BRD content</body></html>');

    // Публикуем вторую сессию
    const docx2 = path.join(tmp.dir, 'session2.docx');
    const html2 = path.join(tmp.dir, 'session2.html');
    createTestFile(docx2, 'docx 2');
    createTestFile(html2, '<html>2</html>');

    const r2 = await publisher.publishDraft('sess_002', docx2, html2, 'Project Beta');

    assert.ok(fs.existsSync(path.join(pagesDir, 'sessions', 'sess_uuid_abc')));
    assert.ok(fs.existsSync(path.join(pagesDir, 'sessions', 'sess_002')));
    assert.ok(fs.existsSync(path.join(pagesDir, 'sessions', 'sess_uuid_abc', 'session1.docx')));
    assert.ok(fs.existsSync(path.join(pagesDir, 'sessions', 'sess_002', 'session2.docx')));
    assert.strictEqual(fs.readFileSync(path.join(pagesDir, 'sessions', 'sess_uuid_abc', 'index.html'), 'utf-8'), '<html><body>BRD content</body></html>');
    assert.strictEqual(fs.readFileSync(path.join(pagesDir, 'sessions', 'sess_002', 'index.html'), 'utf-8'), '<html>2</html>');

    assert.ok(r1.htmlUrl.includes('sess_uuid_abc'));
    assert.ok(r2.htmlUrl.includes('sess_002'));
  } finally {
    tmp.cleanup();
  }
});

// ==================== Edge Cases ====================

console.log('\n📋 Edge Cases');

test('constructor works with empty config', () => {
  const publisher = new GitHubPagesPublisher();
  assert.strictEqual(publisher.repo, '');
  assert.strictEqual(publisher.token, '');
  assert.strictEqual(publisher.branch, 'gh-pages');
  assert.strictEqual(publisher.dryRun, false);
  assert.strictEqual(publisher.isConfigured, false);
});

test('publisher default pagesDir is /tmp/gh-pages-worktree', () => {
  const publisher = new GitHubPagesPublisher({});
  assert.strictEqual(publisher.pagesDir, '/tmp/gh-pages-worktree');
});

test('publisher accepts custom pagesDir from config', () => {
  const publisher = new GitHubPagesPublisher({ pagesDir: '/custom/pages' });
  assert.strictEqual(publisher.pagesDir, '/custom/pages');
});

testAsync('publishDraft rejects with empty sessionId (file not found)', async () => {
  const publisher = new GitHubPagesPublisher({
    repo: TEST_REPO,
    token: TEST_TOKEN,
    dryRun: true
  });

  try {
    await publisher.publishDraft('', '/fake/docx.docx', '/fake/index.html', 'Test');
    assert.fail('Expected error');
  } catch (err) {
    assert.ok(err.message.includes('не найден'));
  }
});

testAsync('_copyToPagesDir preserves DOCX filename', async () => {
  const publisher = new GitHubPagesPublisher({ dryRun: true });
  const tmp = getTempDir();
  try {
    const pagesDir = path.join(tmp.dir, 'pages');
    publisher.pagesDir = pagesDir;

    const docxPath = path.join(tmp.dir, 'Бизнес-требования-ЗАО-Рога-и-Копыта.docx');
    const htmlPath = path.join(tmp.dir, 'web.html');
    createTestFile(docxPath, 'content');
    createTestFile(htmlPath, 'html');

    const result = await publisher._copyToPagesDir(docxPath, htmlPath, 'sess_123');
    assert.ok(result.docxDest.endsWith('Бизнес-требования-ЗАО-Рога-и-Копыта.docx'));
  } finally {
    tmp.cleanup();
  }
});

testAsync('_ensureWorktree clones when pagesDir is empty', async () => {
  const tmp = getTempDir();
  try {
    const publisher = new GitHubPagesPublisher({
      repo: TEST_REPO,
      token: TEST_TOKEN,
      pagesDir: path.join(tmp.dir, 'empty-pages'),
      dryRun: true
    });

    // Директория не существует — будет попытка клонирования
    try {
      await publisher._ensureWorktree();
      assert.fail('Expected git clone to fail with fake token');
    } catch (err) {
      assert.ok(err.message.includes('clone') || err.message.includes('failed'));
    }
  } finally {
    tmp.cleanup();
  }
});

// ==================== Summary ====================

const totalTests = currentTest;
setTimeout(() => {
  console.log(`\n${'='.repeat(50)}`);
  console.log(`📊 Results: ${passed} passed, ${failed} failed, ${totalTests} total`);
  console.log(`${'='.repeat(50)}`);

  if (failed > 0) {
    console.log('\n❌ Failed tests:');
    errors.forEach(e => {
      console.log(`  ${e.test}. ${e.name}`);
      console.log(`     ${e.error}`);
    });
    process.exit(1);
  } else {
    console.log('\n✅ ALL TESTS PASSED');
  }
}, 500);
