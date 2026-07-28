#!/usr/bin/env node
/**
 * generate-agent-status.js
 * 
 * Генерирует agent-status.html с Mermaid-схемой мультиагентной системы.
 * 
 * Использование: node generate-agent-status.js
 * 
 * Результат: ../agent-status.html
 * 
 * Запуск по cron: 0 * * * * cd /home/user1/nasledstvo && node scripts/generate-agent-status.js
 */

const fs = require('fs');
const path = require('path');

const REGISTRY_PATH = path.join(__dirname, '..', 'agents-registry.json');
const OUTPUT_PATH = path.join(__dirname, '..', 'agent-status.html');

// === Загрузка реестра ===
let registry;
try {
  registry = JSON.parse(fs.readFileSync(REGISTRY_PATH, 'utf-8'));
} catch (e) {
  console.error('Ошибка загрузки agents-registry.json:', e.message);
  process.exit(1);
}

// === Построение Mermaid-кода ===
const PROD_COLORS = {
  'fz425': '#58a6ff',
  'inheritance': '#f778ba',
  'pharm': '#bc8cff',
  'family': '#7ee787',
  'social': '#ff9000',
  'brd': '#56d4dd'
};

function buildMermaid() {
  const lines = ['flowchart TB'];
  
  // Стилизация
  lines.push('  classDef gateway fill:#1e3a5f,stroke:#58a6ff,stroke-width:2px,color:#fff');
  lines.push('  classDef skill fill:#2d1b3e,stroke:#bc8cff,stroke-width:2px,color:#e0d0f0');
  lines.push('  classDef user fill:#1a3a1a,stroke:#7ee787,stroke-width:2px,color:#a0e0a0');
  lines.push('  classDef cron fill:#3a2a1a,stroke:#ff9000,stroke-width:2px,color:#f0d0a0');
  lines.push('  classDef product fill:#1a1a2e,stroke:#555,stroke-dasharray:5 5,color:#888');
  lines.push('');
  
  // Ссылки для кликов (агенты → SKILL.md или страница продукта)
  // mermaid click не поддерживается в GitHub Pages с CDN, пропускаем
  
  // === Подграфы по продуктам ===
  for (const product of registry.products) {
    const prodColor = PROD_COLORS[product.id] || '#666';
    lines.push(`  subgraph ${product.id}["${product.emoji || '📦'} ${product.name}"]`);
    
    for (const agentId of product.agents) {
      const agent = registry.agents.find(a => a.id === agentId);
      if (!agent) continue;
      const label = `${agent.emoji} ${agent.name}\\n${agent.role}`;
      lines.push(`    ${agent.id}["${label}"]`);
      // Класс в зависимости от типа
      if (agent.type === 'gateway') lines.push(`    class ${agent.id} gateway;`);
      else if (agent.type === 'skill') lines.push(`    class ${agent.id} skill;`);
    }
    
    lines.push('  end');
    lines.push('');
  }
  
  // === Пользователи ===
  lines.push('  subgraph users["👤 Пользователи"]');
  for (const user of registry.users) {
    const label = `${user.name}${user.username ? ' (@' + user.username + ')' : ''}`;
    const nodeId = 'user_' + (user.username || user.name);
    lines.push(`    ${nodeId}["${label}"]`);
    lines.push(`    class ${nodeId} user;`);
  }
  lines.push('  end');
  lines.push('');
  
  // === Cron ===
  lines.push('  subgraph cron_group["⏰ Cron (VPS)"]');
  lines.push('    cron_trigger["🔄 Раз в час\\nГенерация статуса"]');
  lines.push('    class cron_trigger cron;');
  lines.push('    cron_news["📰 Дайджест новостей\\n02:00-02:20 ежедневно"]');
  lines.push('    class cron_news cron;');
  lines.push('    cron_rzd["📈 РЖД 1Р-37R\\n23:50-23:58 будни"]');
  lines.push('    class cron_rzd cron;');
  lines.push('  end');
  lines.push('');
  
  // === Связи (маршрутизация) ===
  lines.push('  %% --- Связи пользователей ---');
  // Оля → main → fz425-agent
  lines.push('  user_Kirill_syst -->|"Telegram"| main');
  lines.push('  user_Оля -->|"Telegram"| main');
  lines.push('  user_Катя -->|"Telegram"| main');
  lines.push('  user_Su_Ri_Mi -->|"Telegram"| main');
  
  // main → маршрутизация к агентам
  lines.push('  main -->|"sessions_send"| fz425-agent');
  lines.push('  main -->|"sessions_send"| katrin-tender-expert');
  lines.push('  main -->|"«Адвокат»"| kirill-family-advocate');
  lines.push('  main -->|"sessions_send"| inheritance-bank-complaint-analyst');
  lines.push('  main -->|"sessions_send"| danil-vklady-expert');
  lines.push('  main -->|"sessions_send"| social-category-matcher');
  lines.push('  main -->|"создать BRD"| ba-controller');
  
  // Внутренние связи агентов
  lines.push('  fz425-agent -->|"верификация"| fz425-verifier');
  lines.push('  katrin-tender-expert -->|"аудит"| katrin-agent-document-verdict');
  lines.push('  social-category-matcher -->|"проверка"| social-verifier');
  
  // BRD конвейер
  lines.push('  ba-controller -->|"опрос"| ba-questioner');
  lines.push('  ba-controller -->|"генерация"| ba-compiler');
  lines.push('  ba-controller -->|"аудит"| ba-verifier');
  lines.push('  ba-controller -.->|"результат"| main');
  
  // Cron связи
  lines.push('  cron_news -->|"результат"| lena-news-expert');
  lines.push('  cron_rzd -->|"результат"| lena-news-expert');
  
  return lines.join('\n');
}

// === Генерация HTML ===
function generateHtml() {
  const mermaidCode = buildMermaid();
  const now = new Date().toLocaleString('ru-RU', { timeZone: 'Europe/Moscow' });
  
  // Статусы агентов (из реестра, при запуске скрипта можно обновлять)
  const agentCards = registry.agents.map(a => {
    const statusClass = a.status === 'online' ? 'online' : 'offline';
    const statusText = a.status === 'online' ? '🟢 online' : '🔴 offline';
    const modelText = a.model ? a.model.replace('deepseek/', '') : '—';
    const fallbackText = a.fallback ? a.fallback.replace('deepseek/', '') : '—';
    const product = registry.products.find(p => p.agents.includes(a.id));
    const productText = product ? product.name : (a.product || '—');
    
    return `    <div class="agent-card ${statusClass}">
      <div class="agent-card-header">
        <div class="agent-card-icon ${a.type}">${a.emoji}</div>
        <div class="agent-card-info">
          <div class="agent-card-name">
            ${a.name}
            <span class="status-dot ${statusClass}">${statusText}</span>
          </div>
          <p class="agent-card-role">${a.role}</p>
        </div>
      </div>
      <div class="agent-metrics">
        <div class="metric-item">
          <div class="metric-label">Продукт</div>
          <div class="metric-value small">${productText}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">Модель</div>
          <div class="metric-value small">${modelText}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">Фоллбэк</div>
          <div class="metric-value small">${fallbackText}</div>
        </div>
        <div class="metric-item">
          <div class="metric-label">Тип</div>
          <div class="metric-value small">${a.type === 'gateway' ? '🔷 gateway' : a.type === 'skill' ? '📘 skill' : a.type === 'composite' ? '📦 composite' : a.type}</div>
        </div>
      </div>
    </div>`;
  }).join('\n\n');

  return `<!DOCTYPE html>
<html lang="ru">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Статус агентов — nasledstvo2026.github.io</title>
  <link rel="stylesheet" href="theme.css">
  <link rel="stylesheet" href="style.css">
  <script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
  <script>mermaid.initialize({
    startOnLoad: true,
    theme: 'dark',
    themeVariables: {
      fontFamily: 'system-ui, sans-serif',
      fontSize: '13px',
      primaryColor: '#1e3a5f',
      primaryTextColor: '#fff',
      primaryBorderColor: '#58a6ff',
      lineColor: '#58a6ff',
      secondaryColor: '#2d1b3e',
      tertiaryColor: '#1a1a2e',
      clusterBkg: '#111827',
      clusterBorder: '#374151'
    }
  });</script>
  <style>
    body { background: #0a0e17; color: #e0e0e0; }
    .container { max-width: 1200px; margin: 0 auto; padding: 0 20px; }
    .back { color: #58a6ff; text-decoration: none; display: inline-block; margin: 20px 0; font-size: 14px; }
    .back:hover { text-decoration: underline; }
    .hero { text-align: center; padding: 40px 0 20px; }
    .hero h1 { font-size: 32px; margin: 0; }
    .hero .subtitle { color: #888; font-size: 14px; margin-top: 8px; }

    .status-grid {
      display: grid;
      grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
      gap: 16px;
      margin-bottom: 40px;
    }
    .agent-card {
      background: #111827;
      border: 1.5px solid #1f2937;
      border-radius: 14px;
      padding: 18px;
      transition: border-color .3s;
    }
    .agent-card.online { border-color: rgba(126,231,135,0.4); }
    .agent-card-header {
      display: flex;
      align-items: center;
      gap: 12px;
      margin-bottom: 10px;
    }
    .agent-card-icon {
      width: 40px; height: 40px;
      border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      font-size: 20px;
      flex-shrink: 0;
    }
    .agent-card-icon.gateway { background: rgba(88,166,255,.15); }
    .agent-card-icon.skill { background: rgba(188,140,255,.15); }
    .agent-card-info { flex: 1; min-width: 0; }
    .agent-card-name {
      font-size: 14px; font-weight: 700;
      display: flex; align-items: center; gap: 6px; flex-wrap: wrap;
    }
    .agent-card-role { font-size: 11px; opacity: .55; margin: 2px 0 0; }
    .status-dot {
      display: inline-flex; align-items: center; gap: 4px;
      font-size: 10px; font-weight: 600;
      padding: 2px 8px; border-radius: 12px;
    }
    .status-dot.online { background: rgba(126,231,135,.1); color: #7ee787; }
    .agent-metrics {
      display: grid;
      grid-template-columns: 1fr 1fr;
      gap: 6px;
    }
    .metric-item {
      background: rgba(255,255,255,.03);
      border-radius: 8px; padding: 8px 10px;
    }
    .metric-label { font-size: 9px; text-transform: uppercase; letter-spacing: .5px; opacity: .4; margin-bottom: 1px; }
    .metric-value { font-size: 12px; font-weight: 600; }
    .metric-value.small { font-size: 11px; }

    .mermaid-wrapper {
      background: #111827;
      border: 1.5px solid #1f2937;
      border-radius: 14px;
      padding: 28px 20px;
      margin-bottom: 24px;
      overflow-x: auto;
    }
    .mermaid-wrapper h3 {
      margin: 0 0 16px; font-size: 14px;
      text-transform: uppercase; letter-spacing: 1px; opacity: .6;
    }

    .legend {
      display: flex; flex-wrap: wrap; gap: 14px;
      padding: 14px 18px; margin-bottom: 40px;
      background: #111827; border: 1.5px solid #1f2937; border-radius: 12px;
    }
    .legend-item { display: flex; align-items: center; gap: 6px; font-size: 11px; opacity: .6; }
    .legend-item .swatch {
      width: 12px; height: 12px; border-radius: 3px; flex-shrink: 0;
    }

    .last-updated {
      text-align: center; font-size: 11px; opacity: .35;
      margin: 20px 0; padding-bottom: 40px;
    }
    .footer { text-align: center; padding: 20px 0 40px; border-top: 1px solid #1f2937; color: #555; font-size: 12px; }

    @media (max-width: 600px) {
      .status-grid { grid-template-columns: 1fr; }
      .agent-metrics { grid-template-columns: 1fr; }
    }
  </style>
</head>
<body>
<div class="container">
  <a href="service.html" class="back">← Сервисы</a>
  <div class="hero">
    <h1>🤖 Статус агентов</h1>
    <p class="subtitle">Мультиагентная система — ${registry.agents.length} агентов · ${registry.products.length} продуктов</p>
  </div>

  <!-- Карточки агентов -->
  <div class="status-grid">
    ${agentCards}
  </div>

  <!-- Mermaid-схема -->
  <div class="mermaid-wrapper">
    <h3>🗺️ Карта мультиагентной системы</h3>
    <div class="mermaid">
${mermaidCode}
    </div>
  </div>

  <!-- Сводка по продуктам -->
  <div class="mermaid-wrapper" style="padding:20px;">
    <h3>📦 Продукты и сервисы</h3>
    <div style="display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:14px;margin-top:12px;">
      ${registry.products.map(p => {
        const color = PROD_COLORS[p.id] || '#666';
        const agentNames = p.agents.map(aid => {
          const a = registry.agents.find(x => x.id === aid);
          return a ? a.emoji + ' ' + a.name : aid;
        }).join(' · ');
        return `<div style="background:rgba(255,255,255,.03);border-radius:10px;padding:14px;border-left:4px solid ${color};">
          <div style="font-weight:700;font-size:13px;margin-bottom:4px;">${p.name}</div>
          <div style="font-size:11px;opacity:.55;margin-bottom:8px;">${p.description}</div>
          <div style="font-size:11px;opacity:.7;">${agentNames}</div>
        </div>`;
      }).join('\n      ')}
    </div>
  </div>

  <!-- Легенда -->
  <div class="legend">
    <span class="legend-item"><span class="swatch" style="background:#58a6ff"></span> Gateway-агент (отдельный agentId)</span>
    <span class="legend-item"><span class="swatch" style="background:#bc8cff"></span> Skill-агент (навык)</span>
    <span class="legend-item"><span class="swatch" style="background:#7ee787"></span> Пользователь</span>
    <span class="legend-item"><span class="swatch" style="background:#ff9000"></span> Cron / автоматизация</span>
    <span class="legend-item">→ sessions_send / маршрутизация</span>
    <span class="legend-item">- - → обратная связь</span>
  </div>

  <div class="last-updated">
    Последнее обновление: ${now} · 🔄 скрипт generate-agent-status.js · cron: раз в час
  </div>

  <div class="footer">
    <strong>☽ ЛУНТ</strong> · OpenClaw 2026 · DeepSeek V4 Flash
  </div>
</div>
</body>
</html>`;
}

// === Запись файла ===
const html = generateHtml();
fs.writeFileSync(OUTPUT_PATH, html, 'utf-8');
console.log('✅ agent-status.html создан');
console.log('📄 ' + OUTPUT_PATH);
console.log('📊 Агентов:', registry.agents.length);
console.log('📦 Продуктов:', registry.products.length);
console.log('👤 Пользователей:', registry.users.length);
