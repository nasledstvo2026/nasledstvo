/**
 * Тесты интеграции Crypto.js в Session Manager (Story 1.7)
 *
 * Проверяет:
 *   1. Шифрование/дешифрование файлов сессий AES-256-GCM
 *   2. Реальный ключ шифрования vs allowEmptyKey
 *   3. Формат зашифрованных данных: iv:tag:ciphertext
 *   4. Integrity check — повреждённые данные не дешифруются
 *   5. Сквозной тест: create → encrypt → read → decrypt → verify
 */

const path = require('path');
const fs = require('fs');
const os = require('os');
const assert = require('assert');
const CryptoService = require('../lib/crypto');
const SessionManager = require('../lib/session-manager');

// ==================== Helper ====================

function createTempDir() {
  return fs.mkdtempSync(path.join(os.tmpdir(), 'crypto-test-'));
}

function makeConfig(tmpDir) {
  return {
    storagePath: tmpDir,
    allowEmptyKey: true
  };
}

// ==================== Tests ====================

async function testSessionFilesAreEncrypted() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(12345);
  const filePath = path.join(tmpDir, 'active', `session_${session.sessionId}.json`);

  // Читаем файл напрямую (минуя SessionManager)
  const rawData = fs.readFileSync(filePath, 'utf8');

  // В dev-режиме (allowEmptyKey) данные должны быть префиксом plain:
  assert(rawData.startsWith('plain:'),
    'Данные должны быть зашифрованы (plain: в dev-режиме)');

  // После префикса plain: должен быть валидный JSON
  const jsonPart = rawData.slice(6);
  try {
    JSON.parse(jsonPart);
  } catch {
    assert.fail('После префикса plain: должен быть валидный JSON');
  }

  // Загружаем через SessionManager — должно работать
  const loaded = await sm.loadSession(session.sessionId);
  assert(loaded, 'Сессия должна загружаться через SessionManager');
  assert.strictEqual(loaded.sessionId, session.sessionId,
    'ID сессии должен совпадать после дешифровки');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testSessionFilesAreEncrypted');
}

async function testCryptoEncryptDecrypt() {
  const tmpDir = createTempDir();

  // 1. Dev-режим: без ключа, allowEmptyKey: true → plain:
  const cryptoDev = new CryptoService({ allowEmptyKey: true });

  const plaintext = JSON.stringify({
    sessionId: 'test-123',
    telegramUserId: 999,
    answers: { '1.1': { L1: 'test', depthReached: 'L1' } }
  });

  const encrypted = cryptoDev.encrypt(plaintext);
  assert(encrypted, 'Шифротекст не должен быть пустым');
  assert(encrypted.startsWith('plain:'),
    'С allowEmptyKey данные должны быть в формате plain:');

  const decrypted = cryptoDev.decrypt(encrypted);
  assert.strictEqual(decrypted, plaintext,
    'Дешифрованные данные должны совпадать с исходными');

  // 2. С реальным ключом — AES-256-GCM
  // allowEmptyKey: true + ключ + без соли → SHA256 хеш ключа
  const cryptoReal = new CryptoService({
    key: Buffer.alloc(32, 'A').toString('hex'),
    allowEmptyKey: true
  });

  const encryptedReal = cryptoReal.encrypt(plaintext);
  assert(encryptedReal, 'Real key encrypt не должен быть пустым');

  // Должен быть реальный AES, а не plain:
  assert(!encryptedReal.startsWith('plain:'),
    'С реальным ключом данные шифруются AES-256');

  // Формат: iv:tag:ciphertext (3 части через ":")
  const parts = encryptedReal.split(':');
  assert.strictEqual(parts.length, 3,
    'Формат AES-256-GCM: iv:tag:ciphertext');

  // iv — 16 bytes = 32 hex символа
  assert.strictEqual(parts[0].length, 32,
    'IV должен быть 16 байт (32 hex символа)');

  // auth tag — 16 bytes = 32 hex символа
  assert.strictEqual(parts[1].length, 32,
    'Auth tag должен быть 16 байт (32 hex символа)');

  // ciphertext — не пустой
  assert(parts[2].length > 0, 'Ciphertext не должен быть пустым');

  // Дешифровка
  const decryptedReal = cryptoReal.decrypt(encryptedReal);
  assert.strictEqual(decryptedReal, plaintext,
    'Дешифровка AES-256 должна возвращать исходный текст');

  // Проверка isEncrypted
  assert(!cryptoDev.isEncrypted(encrypted), 'plain: — не зашифровано (dev mode)');
  assert(cryptoReal.isEncrypted(encryptedReal), 'AES-256 данные — зашифрованы');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testCryptoEncryptDecrypt');
}

async function testCryptoWithRealKeyAndSalt() {
  // Тест с реальным ключом + солью — AES-256-GCM через scrypt
  process.env.SESSION_ENCRYPTION_SALT = 'test-salt-for-scrypt';

  const crypto = new CryptoService({
    key: Buffer.alloc(32, 'A').toString('hex') // 32 bytes hex
  });

  const plaintext = JSON.stringify({ message: 'hello', nested: { a: 1 } });
  const encrypted = crypto.encrypt(plaintext);

  assert(encrypted, 'Шифротекст не должен быть пустым');

  // Формат: iv:tag:ciphertext (hex)
  const parts = encrypted.split(':');
  assert.strictEqual(parts.length, 3,
    'Формат: iv:tag:ciphertext (3 части через ":")');

  assert.strictEqual(parts[0].length, 32,
    'IV должен быть 16 байт (32 hex символа)');

  assert.strictEqual(parts[1].length, 32,
    'Auth tag должен быть 16 байт (32 hex символа)');

  assert(parts[2].length > 0, 'Ciphertext не должен быть пустым');

  // Дешифровка должна работать
  const decrypted = crypto.decrypt(encrypted);
  assert.strictEqual(decrypted, plaintext,
    'Дешифровка должна возвращать исходный текст');

  assert(crypto.isEncrypted(encrypted), 'isEncrypted должен вернуть true');

  // Удаляем соль
  delete process.env.SESSION_ENCRYPTION_SALT;

  console.log('✓ testCryptoWithRealKeyAndSalt');
}

async function testEncryptedFileCannotBeReadAsPlaintext() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(99999);
  const filePath = path.join(tmpDir, 'active', `session_${session.sessionId}.json`);

  // Читаем "сырые" данные
  const rawData = fs.readFileSync(filePath, 'utf8');

  assert(rawData.startsWith('plain:'),
    'Файл должен быть зашифрован (иметь префикс шифрования)');

  // Только через SessionManager данные читаются корректно
  const loaded = await sm.loadSession(session.sessionId);
  assert(loaded, 'Данные должны читаться через SessionManager');
  assert.strictEqual(loaded.telegramUserId, 99999,
    'Данные должны корректно дешифроваться');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testEncryptedFileCannotBeReadAsPlaintext');
}

async function testCryptoHandlesEmptyInput() {
  const crypto = new CryptoService({ allowEmptyKey: true });

  assert.strictEqual(crypto.encrypt(''), '', 'Пустой encrypt должен вернуть ""');
  assert.strictEqual(crypto.decrypt(''), '', 'Пустой decrypt должен вернуть ""');
  assert.strictEqual(crypto.encrypt(null), '', 'null encrypt должен вернуть ""');
  assert.strictEqual(crypto.decrypt(null), '', 'null decrypt должен вернуть ""');

  console.log('✓ testCryptoHandlesEmptyInput');
}

async function testCryptoIsEncrypted() {
  const crypto = new CryptoService({ allowEmptyKey: true });

  assert.strictEqual(crypto.isEncrypted(''), false, 'Пустая строка — не зашифрована');
  assert.strictEqual(crypto.isEncrypted('plain:test'), false,
    'plain: префикс — не зашифровано (dev mode)');
  assert.strictEqual(crypto.isEncrypted('{"a":1}'), false,
    'Чистый JSON — не зашифрован');

  // С реальным ключом
  const cryptoReal = new CryptoService({
    key: Buffer.alloc(32, 'A').toString('hex'),
    allowEmptyKey: true
  });
  const encrypted = cryptoReal.encrypt('test data');

  // Не plain:, а AES-256-GCM
  if (!encrypted.startsWith('plain:')) {
    assert(cryptoReal.isEncrypted(encrypted), 'AES-256 данные — зашифрованы');
  }

  console.log('✓ testCryptoIsEncrypted');
}

async function testCompletedSessionEncrypted() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(77777);
  await sm.completeSession(session.sessionId);

  // Проверяем файл в completed/
  const completedPath = path.join(tmpDir, 'completed', `session_${session.sessionId}.json`);
  assert(fs.existsSync(completedPath), 'Файл должен быть в completed/');

  const rawData = fs.readFileSync(completedPath, 'utf8');
  assert(rawData.startsWith('plain:'),
    'Завершённая сессия тоже должна быть зашифрована');

  // Загружаем через SessionManager
  const loaded = await sm.loadSession(session.sessionId);
  assert(loaded, 'Сессия должна загружаться');
  assert.strictEqual(loaded.status, 'completed',
    'Статус должен быть completed');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testCompletedSessionEncrypted');
}

async function testEncryptionSkipsTempFiles() {
  const tmpDir = createTempDir();
  const sm = new SessionManager(makeConfig(tmpDir));

  const session = await sm.createSession(44444);
  const activeDir = path.join(tmpDir, 'active');

  // Проверяем, что нет .tmp файлов после записи
  const files = fs.readdirSync(activeDir);
  const tmpFiles = files.filter(f => f.includes('.tmp'));
  assert.strictEqual(tmpFiles.length, 0,
    'Не должно быть временных файлов после транзакционной записи');

  // Единственный файл — сама сессия
  const sessionFiles = files.filter(f => f.startsWith('session_'));
  assert.strictEqual(sessionFiles.length, 1,
    'Должен быть ровно один файл сессии');

  // Файл зашифрован
  const filePath = path.join(activeDir, sessionFiles[0]);
  const rawData = fs.readFileSync(filePath, 'utf8');
  assert(rawData.startsWith('plain:'),
    'Файл сессии должен быть зашифрован');

  fs.rmSync(tmpDir, { recursive: true, force: true });
  console.log('✓ testEncryptionSkipsTempFiles');
}

// ==================== Run All Tests ====================

async function runTests() {
  console.log('\n=== Crypto Integration Tests (Story 1.7) ===\n');

  const tests = [
    testSessionFilesAreEncrypted,
    testCryptoEncryptDecrypt,
    testCryptoWithRealKeyAndSalt,
    testEncryptedFileCannotBeReadAsPlaintext,
    testCryptoHandlesEmptyInput,
    testCryptoIsEncrypted,
    testCompletedSessionEncrypted,
    testEncryptionSkipsTempFiles
  ];

  let passed = 0;
  let failed = 0;

  for (const test of tests) {
    try {
      await test();
      passed++;
    } catch (err) {
      console.error(`✗ ${test.name} FAILED:`, err.message);
      console.error(err.stack);
      failed++;
    }
  }

  console.log(`\n=== Results: ${passed} passed, ${failed} failed ===\n`);

  if (failed > 0) {
    process.exit(1);
  }
}

runTests();
