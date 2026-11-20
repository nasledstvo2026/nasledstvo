# Анимированные пузырьки (новые glass-страницы)

Применять только при создании новой страницы с нуля в glass-стиле. На существующую главную `index.html` не добавлять — там свой фон (bg-grid/bg-glow/particles).

Добавлять в `<style>` и сразу после `<body>`:

```html
<style>
  .bubbles {
    position: fixed; inset: 0; pointer-events: none; z-index: 0; overflow: hidden;
  }
  .bubble {
    position: absolute; bottom: -120px; border-radius: 50%;
    background: radial-gradient(circle at 30% 30%, rgba(255,255,255,0.08), rgba(88,166,255,0.03) 50%, transparent 70%);
    backdrop-filter: blur(2px); -webkit-backdrop-filter: blur(2px);
    border: 1px solid rgba(255,255,255,0.04);
    animation: bubble-rise linear infinite;
  }
  .bubble:nth-child(1) { left: 10%; width: 60px; height: 60px; animation-duration: 18s; animation-delay: 0s; }
  .bubble:nth-child(2) { left: 25%; width: 40px; height: 40px; animation-duration: 14s; animation-delay: 3s; }
  .bubble:nth-child(3) { left: 40%; width: 80px; height: 80px; animation-duration: 22s; animation-delay: 5s; }
  .bubble:nth-child(4) { left: 55%; width: 50px; height: 50px; animation-duration: 16s; animation-delay: 2s; }
  .bubble:nth-child(5) { left: 70%; width: 35px; height: 35px; animation-duration: 12s; animation-delay: 7s; }
  .bubble:nth-child(6) { left: 85%; width: 70px; height: 70px; animation-duration: 20s; animation-delay: 4s; }
  .bubble:nth-child(7) { left: 15%; width: 45px; height: 45px; animation-duration: 15s; animation-delay: 9s; }
  .bubble:nth-child(8) { left: 60%; width: 90px; height: 90px; animation-duration: 25s; animation-delay: 1s; }
  @keyframes bubble-rise {
    0%   { transform: translateY(0) scale(1); opacity: 0; }
    10%  { opacity: 0.6; }
    80%  { opacity: 0.3; }
    100% { transform: translateY(-110vh) scale(0.6); opacity: 0; }
  }
</style>
```

```html
<div class="bubbles">
  <div class="bubble"></div>  <!-- ×8 -->
</div>
```

Характеристики: 8 пузырьков, 35-90px, 12-25s подъём, `pointer-events: none`, полупрозрачный radial-gradient + blur. Позади контента (z-index: 0).
