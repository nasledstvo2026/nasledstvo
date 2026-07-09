#!/usr/bin/env node
/**
 * Патч: добавляет вызов signalCompletion при survey_complete
 */

const fs = require('fs');
const path = require('path');

const filePath = path.join(__dirname, 'lib', 'telegram-connector.js');
let content = fs.readFileSync(filePath, 'utf-8');

// Ищем место с обработкой survey_complete
// По коду survey-engine.js: processAnswer возвращает { action: 'survey_complete', question: null }
// В telegram-connector должно быть что-то вроде:
//   if (result.action === 'survey_complete') ...
// Если нет — добавим

const needle = "case 'survey_complete'";
if (content.includes(needle)) {
  console.log('survey_complete handler already exists');
} else {
  // Ищем switch/case pattern для action
  // Добавляем после блока с question или в конец функции обработки
  // Найдём: если есть "action" + "next_question" — место рядом
  const patterns = [
    "const { question, progress, session: updatedSession, action } = result;",
    "case 'reflection_needed'",
    "case 'next_question'",
    "if (result.action === 'next_question')",
    "if (result.action === 'reflection_needed')"
  ];

  let found = false;
  for (const pat of patterns) {
    const idx = content.indexOf(pat);
    if (idx >= 0) {
      // Ищем ближайший случай/условие, куда воткнуть survey_complete
      console.log(`Found pattern "${pat}" at index ${idx}`);
      found = true;
      break;
    }
  }

  if (!found) {
    // Попробуем найти любой ref на result.action
    const rx = /result\.action\s*[=!]==?\s*'/g;
    let match;
    while ((match = rx.exec(content)) !== null) {
      console.log(`Found result.action usage at ${match.index}: "${content.substr(match.index, 50)}"`);
    }

    // Также ищем return result; или return { question, ... }
    const rx2 = /return\s+(result|{)/g;
    let m2;
    while ((m2 = rx2.exec(content)) !== null) {
      console.log(`Found return at ${m2.index}: "${content.substr(m2.index, 60)}"`);
    }
  }
}

// Alternative: найти место, где survey_complete должен быть обработан
// Ищем вызов processAnswer
const pAIdx = content.indexOf('processAnswer(');
const sCIdx = content.indexOf('signalCompletion');
const gCIdx = content.indexOf('survey_complete');
console.log('\nKey locations:');
console.log('processAnswer():', pAIdx >= 0 ? pAIdx : 'NOT FOUND');
console.log('signalCompletion:', sCIdx >= 0 ? sCIdx : 'NOT FOUND');
console.log('survey_complete:', gCIdx >= 0 ? content.substr(gCIdx - 30, 80) : 'NOT FOUND');
