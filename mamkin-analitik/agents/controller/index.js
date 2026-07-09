/**
 * Агент-контролёр (Controller Agent)
 *
 * Двухэтапная проверка качества черновика БТ:
 *   Story 3.2 — Проверка полноты (Completeness Check)
 *     1. Все 7 блоков проверяются на наличие содержимого
 *     2. Каждый подраздел: есть осмысленный текст (не "да", "нет", "не знаю")
 *     3. Пустые/формальные ответы → { block, subsection, issue: "empty", severity: "error" }
 *     4. Все заполнены → Completeness PASS
 *
 *   Story 3.3 — Проверка глубины (Depth Check)
 *     Оценка по критериям из quality-rules.md
 *
 *   Story 3.4 — Возврат на доработку (FR15)
 *   Story 3.5 — Запрос уточнений через опросчика (FR16)
 *
 * Вход: Session Context (черновик БТ + ответы пользователя)
 * Выход: результат проверки { completeness, depth, overallScore, approved, issues[] }
 */

const { createLogger } = require('../../lib/logger');

/** Фразы, считающиеся пустыми/формальными ответами */
const EMPTY_PHRASES = [
  'да', 'нет', 'не знаю', 'не применимо', 'н/п', '-', '—',
  'всё ок', 'нормально', 'всё нормально', 'ок', 'ok',
  'затрудняюсь ответить', 'ничего',
  'возможно', 'наверное', 'пока не знаю',
  '', ' ', '  '
];

class ControllerAgent {
  /**
   * @param {object} config
   * @param {object} [config.templateEngine] — экземпляр TemplateEngine (опционально)
   * @param {number} [config.maxIterations=3] — максимальное количество итераций проверки
   */
  constructor(config = {}) {
    this.config = config;
    this.templateEngine = config.templateEngine || null;
    this.maxIterations = config.maxIterations || 3;
    this.logger = createLogger('controller-agent');
  }

  /**
   * Основной метод проверки.
   * Выполняет completeness check (Story 3.2), depth check (Story 3.3)
   * и возвращает результаты.
   *
   * @param {object} session — Session Context
   * @returns {Promise<object>} результат проверки
   */
  async process(session) {
    if (!session) {
      throw new Error('ControllerAgent: требуется Session Context');
    }

    const currentIteration = (session.qualityGate && session.qualityGate.iteration) || 1;

    this.logger.info('Controller: starting quality check', {
      sessionId: session.sessionId,
      iteration: currentIteration,
      maxIterations: this.maxIterations
    });

    // === Step 1: Completeness Check (Story 3.2) ===
    const completenessResult = this._checkCompleteness(session);

    // Если полнота не пройдена — возвращаем результат без depth check
    if (completenessResult.status !== 'PASS') {
      this.logger.warn('Controller: completeness check FAILED', {
        sessionId: session.sessionId,
        issuesCount: completenessResult.issues.length,
        iteration: currentIteration
      });

      // Story 3.4: Создаём Revision Request
      const revReq = this.revisionRequest(completenessResult.issues, currentIteration);
      const qFeedback = this.buildQualityFeedback(completenessResult.issues, session);

      const result = {
        completeness: completenessResult.status,
        depth: null,
        overallScore: completenessResult.averageScore,
        scores: completenessResult.scores,
        issues: completenessResult.issues,
        approved: false,
        iteration: currentIteration,
        action: currentIteration >= this.maxIterations
          ? 'force_accept'
          : 'return_to_questioner',
        revisionRequest: revReq,
        qualityFeedback: qFeedback
      };

      // Сохраняем результат в qualityGate
      session.qualityGate = {
        approved: result.approved,
        issues: result.issues,
        iteration: currentIteration,
        lastCheckAt: new Date().toISOString(),
        revisionRequest: revReq
      };

      return result;
    }

    // === Step 2: Depth Check (Story 3.3) ===
    const depthResult = this._checkDepth(session);

    // === Step 3: Итоговая оценка ===
    const approved = depthResult.status === 'PASS';
    // Общий балл — среднее по всем блокам
    const allScores = { ...completenessResult.scores };
    for (const [block, depthScore] of Object.entries(depthResult.scores || {})) {
      // Если есть depth score — используем его (уточняет completeness score)
      if (depthScore !== undefined && depthScore !== null) {
        allScores[block] = Math.round((allScores[block] + depthScore) / 2);
      }
    }
    const scoreValues = Object.values(allScores);
    const overallScore = scoreValues.length > 0
      ? Math.round(scoreValues.reduce((a, b) => a + b, 0) / scoreValues.length)
      : 0;

    const allIssues = [
      ...completenessResult.issues,
      ...depthResult.issues
    ];

    const needsReturn = allIssues.length > 0;

    this.logger.info('Controller: check complete', {
      sessionId: session.sessionId,
      completeness: completenessResult.status,
      depth: depthResult.status,
      overallScore,
      issuesCount: allIssues.length,
      approved: approved || currentIteration >= this.maxIterations,
      iteration: currentIteration
    });

    // Создаём Revision Request (Story 3.4)
    const revisionReq = this.revisionRequest(allIssues, currentIteration);

    // Создаём Quality Feedback для пользователя (Story 3.4, 3.5)
    const qualityFeedback = this.buildQualityFeedback(allIssues, session);

    const result = {
      completeness: completenessResult.status,
      depth: depthResult.status,
      overallScore,
      scores: allScores,
      issues: allIssues,
      approved: approved || currentIteration >= this.maxIterations,
      iteration: currentIteration,
      action: needsReturn && currentIteration < this.maxIterations
        ? 'return_to_questioner'
        : currentIteration >= this.maxIterations
          ? 'force_accept'
          : 'proceed',
      // Story 3.4: Structured revision request for questioner agent
      revisionRequest: revisionReq,
      // Story 3.4, 3.5: User-facing quality feedback message
      qualityFeedback: qualityFeedback
    };

    // Сохраняем результат в qualityGate
    session.qualityGate = {
      approved: result.approved,
      issues: result.issues,
      iteration: currentIteration,
      lastCheckAt: new Date().toISOString(),
      overallScore,
      revisionRequest: revisionReq
    };

    return result;
  }

  /**
   * Проверка полноты (Story 3.2).
   *
   * Для каждого подраздела проверяет наличие осмысленного текста.
   * Пустые ответы и формальные фразы ("да", "нет", "не знаю") считаются незаполненными.
   *
   * @param {object} session — Session Context
   * @returns {{ status: 'PASS'|'FAIL', issues: Array, scores: object, averageScore: number }}
   */
  _checkCompleteness(session) {
    const answers = session.answers || {};
    const issues = [];
    const scores = {};

    // Получаем список всех блоков и подразделов из template или по умолчанию
    const blocks = this._getBlockStructure();

    let totalScoreSum = 0;
    let totalSubsections = 0;

    for (const block of blocks) {
      let blockScoreSum = 0;
      let blockSubCount = 0;

      for (const sub of block.subsections) {
        const answer = answers[sub.id];
        const text = this._getBestAnswerText(answer);
        const isEmpty = this._isEmptyAnswer(text);
        const score = this._scoreCompleteness(text);

        if (isEmpty) {
          issues.push({
            block: block.id,
            subsection: sub.id,
            issue: 'empty',
            severity: 'error',
            detail: `Подраздел «${sub.name}» не заполнен${text ? ': ответ «' + text + '»' : ''}`
          });
        } else if (score < 4) {
          issues.push({
            block: block.id,
            subsection: sub.id,
            issue: 'too_short',
            severity: 'warning',
            detail: `Подраздел «${sub.name}» заполнен поверхностно (оценка: ${score}/10)`,
            suggestions: this._getCompletenessSuggestions(sub.id, block.id)
          });
        }

        blockScoreSum += score;
        blockSubCount++;
        totalScoreSum += score;
        totalSubsections++;
      }

      // Средний балл по блоку
      scores[String(block.id)] = blockSubCount > 0
        ? Math.round(blockScoreSum / blockSubCount)
        : 0;
    }

    const averageScore = totalSubsections > 0
      ? Math.round(totalScoreSum / totalSubsections)
      : 0;

    return {
      status: issues.length === 0 ? 'PASS' : 'FAIL',
      issues,
      scores,
      averageScore
    };
  }

  /**
   * Проверка глубины (Story 3.3).
   *
   * Оценивает:
   *   - Наличие конкретных фактов/цифр (не общие фразы)
   *   - Анализ причин (для проблемного блока)
   *   - Измеримые показатели (для цели)
   *   - Конкретные стороны (для стейкхолдеров)
   *   - Конкретные функциональные требования (для решения)
   *
   * @param {object} session — Session Context
   * @returns {{ status: 'PASS'|'NEEDS_IMPROVEMENT'|'FAIL', issues: Array, scores: object }}
   */
  _checkDepth(session) {
    const answers = session.answers || {};
    const issues = [];
    const scores = {};

    // Block-specific depth checks (из quality-rules.md)
    const depthChecks = {
      // Block 1: Context & Problem
      checkBlock1: (answer) => {
        const checks = [];
        if (!answer || answer.length < 30) {
          checks.push('контекст инициативы не описан подробно');
        }
        if (answer && !/\d+/.test(answer)) {
          checks.push('нет конкретных цифр или показателей');
        }
        if (answer && !/потому|из-за|причин|следователь|в результат/.test(answer.toLowerCase())) {
          checks.push('не указаны причинно-следственные связи');
        }
        return checks;
      },
      // Block 2: Goal & Measurement
      checkBlock2: (answer) => {
        const checks = [];
        if (!answer || answer.length < 30) {
          checks.push('цель не описана подробно');
        }
        if (answer && !/\d+/.test(answer)) {
          checks.push('нет измеримых KPI или целевых значений');
        }
        if (answer && !/процент|количеств|увеличи|сократи|снизи|повыси/.test(answer.toLowerCase())) {
          checks.push('нет метрик улучшения');
        }
        return checks;
      },
      // Block 3: Stakeholders
      checkBlock3: (answer) => {
        const checks = [];
        if (!answer || answer.length < 30) {
          checks.push('стейкхолдеры не описаны подробно');
        }
        if (answer && !/коман|отдел|департамент|заказчик|пользовател|клиент/.test(answer.toLowerCase())) {
          checks.push('не идентифицированы конкретные группы стейкхолдеров');
        }
        if (answer && !/интерес|влиян|ответствен|роль|задач/.test(answer.toLowerCase())) {
          checks.push('не описаны интересы каждой группы');
        }
        return checks;
      },
      // Block 4: Solution
      checkBlock4: (answer) => {
        const checks = [];
        if (!answer || answer.length < 50) {
          checks.push('функциональные требования не описаны подробно');
        }
        if (answer && !/функци|возможност|модул|систем|интеграци/.test(answer.toLowerCase())) {
          checks.push('нет конкретных функций или возможностей');
        }
        if (answer && !/приоритет|критич|важн|базов/.test(answer.toLowerCase())) {
          checks.push('не указаны приоритеты функций');
        }
        return checks;
      },
      // Block 5: Quality & Constraints
      checkBlock5: (answer) => {
        const checks = [];
        if (!answer || answer.length < 30) {
          checks.push('требования к качеству не описаны');
        }
        if (answer && !/производительн|безопас|масштаб|доступн|скорост/.test(answer.toLowerCase())) {
          checks.push('нет качественных характеристик');
        }
        if (answer && !/бюджет|срок|ограничени|технологи|платформ/.test(answer.toLowerCase())) {
          checks.push('нет ограничений проекта');
        }
        return checks;
      },
      // Block 6: Acceptance
      checkBlock6: (answer) => {
        const checks = [];
        if (!answer || answer.length < 30) {
          checks.push('критерии приёмки не описаны');
        }
        if (answer && !/если|когда|при|после|тогда|затем/.test(answer.toLowerCase())) {
          checks.push('нет формата сценариев приёмки');
        }
        return checks;
      },
      // Block 7: Risks
      checkBlock7: (answer) => {
        const checks = [];
        if (!answer || answer.length < 30) {
          checks.push('риски не описаны');
        }
        if (answer && !/вероятност|влияни|митигаци|предотвра|минимизир/.test(answer.toLowerCase())) {
          checks.push('нет оценки вероятности, влияния или митигации');
        }
        return checks;
      }
    };

    const blocks = this._getBlockStructure();
    let depthFailures = 0;

    for (const block of blocks) {
      let blockIssues = [];
      let blockSubCount = 0;

      for (const sub of block.subsections) {
        const answer = answers[sub.id];
        const text = this._getBestAnswerText(answer);

        if (!text || text.length < 5) {
          continue; // пропускаем — уже поймано completeness check
        }

        // Вызываем специфичную проверку для блока
        const checkFn = depthChecks[`checkBlock${block.id}`];
        if (checkFn) {
          const checkIssues = checkFn(text);
          for (const issue of checkIssues) {
            blockIssues.push({
              block: block.id,
              subsection: sub.id,
              issue: 'shallow',
              severity: 'warning',
              detail: issue,
              suggestions: this._getDepthSuggestions(sub.id, block.id)
            });
          }
        }

        blockSubCount++;
      }

      // Оценка глубины для блока: 0-10
      // Снижаем на 2 за каждое замечание
      let blockScore = 8; // базовая оценка при наличии ответа
      blockScore = Math.max(0, blockScore - blockIssues.length * 2);
      scores[String(block.id)] = blockScore;

      issues.push(...blockIssues);

      if (blockIssues.length > 0) {
        depthFailures++;
      }
    }

    // Определяем статус глубины
    let status;
    if (depthFailures === 0) {
      status = 'PASS';
    } else if (depthFailures <= 2) {
      status = 'NEEDS_IMPROVEMENT';
    } else {
      status = 'FAIL';
    }

    return { status, issues, scores };
  }

  /**
   * Получает лучший текст ответа (приоритет L3 > L2 > L1).
   * @param {object|null} answer
   * @returns {string|null}
   */
  _getBestAnswerText(answer) {
    if (!answer) return null;
    return answer.L3 || answer.L2 || answer.L1 || null;
  }

  /**
   * Проверяет, является ли ответ пустым/формальным.
   * @param {string|null} text
   * @returns {boolean}
   */
  _isEmptyAnswer(text) {
    if (!text) return true;

    const trimmed = text.trim().toLowerCase();

    // Точное совпадение с пустыми фразами
    if (EMPTY_PHRASES.includes(trimmed)) return true;

    // Слишком короткий ответ (< 3 слов)
    const words = trimmed.split(/\s+/).filter(w => w.length > 0);
    if (words.length < 3) return true;

    // Только знаки препинания и пробелы
    if (/^[\s.,!?;:\-—]+$/.test(text)) return true;

    return false;
  }

  /**
   * Оценивает полноту ответа по шкале 0-10.
   * @param {string|null} text
   * @returns {number}
   */
  _scoreCompleteness(text) {
    if (!text) return 0;
    if (this._isEmptyAnswer(text)) return 0;

    const trimmed = text.trim();
    const words = trimmed.split(/\s+/).filter(w => w.length > 0);
    const wordCount = words.length;
    const sentenceCount = trimmed.split(/[.!?]+/).filter(s => s.trim().length > 0).length;
    const hasNumbers = /\d+/.test(trimmed);
    const hasFacts = /пример|конкретн|такой|факт|данн/.test(trimmed.toLowerCase());

    // Оценка на основе характеристик
    let score = 3; // базовая
    if (wordCount >= 10) score += 2;
    if (wordCount >= 20) score += 1;
    if (sentenceCount >= 3) score += 1;
    if (hasNumbers) score += 2;
    if (hasFacts) score += 1;

    return Math.min(10, Math.max(0, score));
  }

  /**
   * Возвращает структуру блоков и подразделов.
   * Использует template engine если доступен, иначе — жёстко заданную структуру.
   * @returns {Array<{id: number, name: string, subsections: Array<{id: string, name: string}>}>}
   */
  _getBlockStructure() {
    // Если TemplateEngine подключён — используем его
    if (this.templateEngine) {
      try {
        const blockCount = this.templateEngine.getBlockCount();
        const blocks = [];
        for (let b = 1; b <= blockCount; b++) {
          const block = this.templateEngine.getBlock(b);
          if (block) {
            blocks.push({
              id: b,
              name: block.name || `Блок ${b}`,
              subsections: (block.subsections || []).map(sub => ({
                id: sub.id,
                name: sub.name || sub.id
              }))
            });
          }
        }
        if (blocks.length > 0) return blocks;
      } catch (err) {
        this.logger.warn('TemplateEngine unavailable, using fallback structure', {
          error: err.message
        });
      }
    }

    // Fallback: жёстко заданная структура 7 блоков
    return [
      {
        id: 1,
        name: 'Контекст и проблема',
        subsections: [
          { id: '1.1', name: 'Контекст инициативы' },
          { id: '1.2', name: 'Проблема' },
          { id: '1.3', name: 'Последствия бездействия' }
        ]
      },
      {
        id: 2,
        name: 'Цель и измерение',
        subsections: [
          { id: '2.1', name: 'Бизнес-цель' },
          { id: '2.2', name: 'Критерии успеха' }
        ]
      },
      {
        id: 3,
        name: 'Стейкхолдеры и влияние',
        subsections: [
          { id: '3.1', name: 'Группы стейкхолдеров' },
          { id: '3.2', name: 'Интересы и влияние' }
        ]
      },
      {
        id: 4,
        name: 'Решение',
        subsections: [
          { id: '4.1', name: 'Ключевые функции' },
          { id: '4.2', name: 'Пользовательские сценарии' },
          { id: '4.3', name: 'Граничные случаи' }
        ]
      },
      {
        id: 5,
        name: 'Требования к качеству и ограничения',
        subsections: [
          { id: '5.1', name: 'Качественные характеристики' },
          { id: '5.2', name: 'Ограничения' }
        ]
      },
      {
        id: 6,
        name: 'Приёмка',
        subsections: [
          { id: '6.1', name: 'Критерии приёмки' },
          { id: '6.2', name: 'Сценарии тестирования' }
        ]
      },
      {
        id: 7,
        name: 'Риски и митигации',
        subsections: [
          { id: '7.1', name: 'Идентифицированные риски' },
          { id: '7.2', name: 'Митигации' }
        ]
      }
    ];
  }

  /**
   * Возвращает рекомендации по улучшению полноты для подраздела.
   * @param {string} subId
   * @param {number} blockId
   * @returns {string[]}
   */
  _getCompletenessSuggestions(subId, blockId) {
    const suggestions = {
      '1.1': ['Опишите, над чем работает проект', 'Укажите область деятельности'],
      '1.2': ['Опишите проблему конкретно', 'Приведите примеры'],
      '1.3': ['Укажите, что произойдёт, если ничего не делать', 'Приведите цифры потерь'],
      '2.1': ['Сформулируйте бизнес-цель', 'Укажите KPI и целевые значения'],
      '2.2': ['Перечислите критерии успеха', 'Каждый критерий должен быть измеримым'],
      '3.1': ['Перечислите все группы: команда, заказчики, пользователи'],
      '3.2': ['Для каждой группы опишите интересы'],
      '4.1': ['Опишите 3+ ключевые функции', 'Укажите приоритеты'],
      '4.2': ['Опишите happy path и обработку ошибок'],
      '4.3': ['Укажите 2+ граничных случая'],
      '5.1': ['Опишите требования: производительность, безопасность, масштабирование'],
      '5.2': ['Укажите бюджет, сроки, технологические ограничения'],
      '6.1': ['Для каждой функции опишите критерий приёмки'],
      '6.2': ['Опишите сценарии тестирования для критичных функций'],
      '7.1': ['Перечислите 3+ риска', 'Оцените вероятность и влияние'],
      '7.2': ['Для каждого риска предложите митигацию']
    };
    return suggestions[subId] || ['Добавьте конкретные детали и примеры'];
  }

  /**
   * Возвращает рекомендации по углублению для подраздела.
   * @param {string} subId
   * @param {number} blockId
   * @returns {string[]}
   */
  /**
   * Создаёт структурированный запрос на доработку (Revision Request).
   *
   * Story 3.4: Формирует объект для передачи агенту-опросчику
   * с конкретными замечаниями по блоку/подразделу.
   *
   * Формат:
   *   {
   *     action: 'return_to_questioner',
   *     target: { block, subsection, reason, suggestions },
   *     iteration: 1..3,
   *     forceAccept: false
   *   }
   *
   * @param {Array<{block: number, subsection: string, issue: string, severity: string, detail: string, suggestions: string[]}>} issues
   * @param {number} currentIteration — номер текущей итерации (1, 2, 3)
   * @returns {object} revision request
   */
  revisionRequest(issues, currentIteration) {
    if (!issues || issues.length === 0) {
      return { action: 'proceed', reason: 'нет замечаний' };
    }

    // Группируем замечания по подразделам
    const groupedBySub = {};
    for (const issue of issues) {
      const key = `${issue.block}.${issue.subsection}`;
      if (!groupedBySub[key]) {
        groupedBySub[key] = {
          block: issue.block,
          subsection: issue.subsection,
          reasons: [],
          suggestions: []
        };
      }
      groupedBySub[key].reasons.push(issue.detail);
      if (issue.suggestions) {
        groupedBySub[key].suggestions.push(...issue.suggestions);
      }
    }

    // Берём первое (или самое важное) замечание
    const firstKey = Object.keys(groupedBySub)[0];
    const group = groupedBySub[firstKey];

    const isLastIteration = currentIteration >= this.maxIterations;

    const request = {
      action: isLastIteration ? 'force_accept' : 'return_to_questioner',
      target: {
        block: group.block,
        subsection: group.subsection,
        reason: group.reasons.join('; '),
        suggestions: [...new Set(group.suggestions)] // уникальные
      },
      iteration: currentIteration,
      forceAccept: isLastIteration,
      allIssues: issues // полный список для логирования
    };

    return request;
  }

  /**
   * Строит сообщение Quality Feedback для пользователя.
   *
   * Story 3.4, 3.5: Формирует понятное пользователю сообщение
   * с объяснением, чего не хватает и как улучшить.
   *
   * @param {Array} issues — массив замечаний от проверки
   * @param {object} session — сессия (для контекста)
   * @returns {string} сообщение для пользователя
   */
  buildQualityFeedback(issues, session) {
    if (!issues || issues.length === 0) {
      return '✅ Раздел прошёл проверку. Замечаний нет.';
    }

    const blocks = this._getBlockStructure();
    const lines = [];
    const iteration = (session.qualityGate && session.qualityGate.iteration) || 1;

    // Заголовок
    if (iteration >= this.maxIterations) {
      lines.push('📋 *Форсированное принятие*');
      lines.push('Достигнут лимит итераций (макс. ' + this.maxIterations + '). Принимаем как есть.');
      lines.push('');
    } else {
      lines.push('📋 *Проверка качества: требуется доработка*');
      lines.push(`Итерация ${iteration} из ${this.maxIterations}`);
      lines.push('');
    }

    // По каждому замечанию
    for (const issue of issues) {
      // Название блока
      const block = blocks.find(b => b.id === issue.block);
      const blockName = block ? block.name : `Блок ${issue.block}`;

      lines.push(`🔹 *${blockName}* (${issue.subsection})`);
      lines.push(`   ${issue.detail}`);

      if (issue.suggestions && issue.suggestions.length > 0) {
        lines.push('   *Рекомендации:*');
        for (const s of issue.suggestions) {
          lines.push(`   • ${s}`);
        }
      }
      lines.push('');
    }

    if (iteration < this.maxIterations) {
      lines.push('💡 *Уточните раздел выше в естественном диалоге.*');
    }

    return lines.join('\n');
  }

  /**
   * Возвращает рекомендации по улучшению для указанного подраздела.
   *
   * @param {string} subId
   * @param {number} blockId
   * @returns {string[]}
   */
  _getCompletenessSuggestions(subId, blockId) {
    const suggestions = {
      '1.1': ['Опишите, над чем работает проект', 'Укажите область деятельности'],
      '1.2': ['Опишите причины с примерами', 'Укажите конкретные последствия'],
      '1.3': ['Укажите финансовые потери', 'Опишите влияние на команду/бизнес'],
      '2.1': ['Укажите целевые значения KPI'],
      '2.2': ['Каждый критерий успеха сделайте измеримым'],
      '3.1': ['Укажите должности и роли', 'Кто принимает решения?'],
      '3.2': ['Для каждой группы опишите влияние', 'Есть ли конфликты интересов?'],
      '4.1': ['Укажите функциональные приоритеты', 'Какие функции MVP?'],
      '4.2': ['Опишите сценарий ошибки', 'Что если система недоступна?'],
      '4.3': ['Укажите граничные условия: нагрузка, объём данных'],
      '5.1': ['Укажите конкретные SLA: время отклика, uptime'],
      '5.2': ['Уточните бюджет и временные рамки'],
      '6.1': ['Используйте формат Given-When-Then'],
      '6.2': ['Опишите тестовые сценарии для edge cases'],
      '7.1': ['Оцените вероятность и влияние каждого риска'],
      '7.2': ['Для каждого риска — конкретные шаги митигации']
    };
    return suggestions[subId] || ['Добавьте конкретные цифры и примеры'];
  }
}

module.exports = ControllerAgent;
