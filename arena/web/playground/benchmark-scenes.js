/* Small illustrative scenes explain each benchmark's decision setting. */
(() => {
  'use strict';
  const tr = (en, zh) => window.JevI18n?.t(en, zh) ?? en;
  const label = (key, x, y, extra = '') => `<text class="benchmark-scene-label ${extra}" x="${x}" y="${y}" data-benchmark-label="${key}"></text>`;
  const scenes = [
    {
      kind: 'harness',
      labels: {intent: ['Intent', '意图'], search: ['Search', '检索'], code: ['Code', '代码'], browse: ['Browse', '浏览'], action: ['Action', '行动']},
      caption: ['Tool selection · illustrative scenario', '工具选择 · 场景示意'],
      art: `
        <path class="benchmark-scene-route" d="M78 76H98V35H128M98 76H128M98 76V117H128M210 35H240V76H264M210 76H264M210 117H240V76"/>
        <path class="benchmark-scene-route benchmark-scene-route-active benchmark-scene-draw" pathLength="1" d="M78 76H98V35H210H240V76H264"/>
        <rect class="benchmark-scene-node" x="12" y="54" width="66" height="44" rx="7"/>
        <path class="benchmark-scene-icon" d="M27 67h15m-15 5h24m-24 5h18"/>
        ${label('intent', 45, 90, 'benchmark-scene-centered')}
        <rect class="benchmark-scene-node benchmark-scene-node-active" x="128" y="21" width="82" height="28" rx="6"/>
        <circle class="benchmark-scene-icon benchmark-scene-icon-copper" cx="143" cy="33" r="4"/>
        <path class="benchmark-scene-icon benchmark-scene-icon-copper" d="m146 36 3 3"/>
        ${label('search', 157, 38)}
        <rect class="benchmark-scene-node" x="128" y="62" width="82" height="28" rx="6"/>
        <path class="benchmark-scene-icon" d="m145 72-4 4 4 4m9-8 4 4-4 4"/>
        ${label('code', 166, 79)}
        <rect class="benchmark-scene-node" x="128" y="103" width="82" height="28" rx="6"/>
        <rect class="benchmark-scene-icon" x="139" y="111" width="12" height="10" rx="2"/>
        <path class="benchmark-scene-icon" d="M139 114h12"/>
        ${label('browse', 159, 120)}
        <circle class="benchmark-scene-ring" cx="284" cy="76" r="20"/>
        <path class="benchmark-scene-icon benchmark-scene-icon-copper" d="m278 76 4 4 9-10"/>
        ${label('action', 284, 111, 'benchmark-scene-centered')}
        <circle class="benchmark-scene-signal" cx="98" cy="35" r="3"/>
        <circle class="benchmark-scene-signal" cx="240" cy="76" r="3"/>
      `,
    },
    {
      kind: 'data',
      labels: {input: ['Records', '数据'], quality: ['Assess', '判断'], keep: ['Keep', '保留'], review: ['Review', '复核']},
      caption: ['Data quality · illustrative scenario', '数据质量 · 场景示意'],
      art: `
        <rect class="benchmark-scene-paper benchmark-scene-paper-back" x="18" y="30" width="56" height="65" rx="5" transform="rotate(-8 46 62)"/>
        <rect class="benchmark-scene-paper" x="29" y="37" width="56" height="65" rx="5" transform="rotate(5 57 70)"/>
        <rect class="benchmark-scene-node" x="37" y="45" width="56" height="65" rx="5"/>
        <path class="benchmark-scene-icon" d="M48 60h32M48 67h23M48 74h28M48 81h20"/>
        <rect class="benchmark-scene-mark" x="48" y="91" width="11" height="5" rx="2"/>
        <rect class="benchmark-scene-mark benchmark-scene-mark-muted" x="63" y="91" width="17" height="5" rx="2"/>
        ${label('input', 65, 129, 'benchmark-scene-centered')}
        <path class="benchmark-scene-route" d="M94 77H125M177 77H194V46H219M194 77V106H219"/>
        <path class="benchmark-scene-route benchmark-scene-route-active benchmark-scene-draw" pathLength="1" d="M94 77H125M177 77H194V46H219"/>
        <circle class="benchmark-scene-ring" cx="151" cy="77" r="26"/>
        <path class="benchmark-scene-icon benchmark-scene-icon-copper" d="M139 67h24l-9 11v9l-6 3V78z"/>
        ${label('quality', 151, 124, 'benchmark-scene-centered')}
        <rect class="benchmark-scene-node benchmark-scene-node-active" x="219" y="30" width="91" height="32" rx="6"/>
        <path class="benchmark-scene-icon benchmark-scene-icon-copper" d="m231 46 4 4 7-8"/>
        ${label('keep', 251, 49)}
        <rect class="benchmark-scene-node" x="219" y="90" width="91" height="32" rx="6"/>
        <circle class="benchmark-scene-icon" cx="236" cy="106" r="6"/>
        <path class="benchmark-scene-icon" d="M236 102v4l3 2"/>
        ${label('review', 251, 109)}
        <circle class="benchmark-scene-signal" cx="194" cy="46" r="3"/>
      `,
    },
    {
      kind: 'game',
      labels: {observe: ['Observe', '观察'], choose: ['Choose', '选择'], move: ['Move', '行动']},
      caption: ['Action planning · illustrative scenario', '行动规划 · 场景示意'],
      art: `
        <rect class="benchmark-scene-node" x="77" y="12" width="164" height="126" rx="8"/>
        <path class="benchmark-scene-board-grid" d="M89 22h140v104H89zM124 22v104M159 22v104M194 22v104M89 48h140M89 74h140M89 100h140"/>
        <rect class="benchmark-scene-board-wall" x="126" y="50" width="31" height="22" rx="3"/>
        <rect class="benchmark-scene-board-wall" x="196" y="76" width="31" height="22" rx="3"/>
        <rect class="benchmark-scene-board-wall" x="91" y="102" width="31" height="22" rx="3"/>
        <path class="benchmark-scene-route benchmark-scene-route-option" d="M106 87V61M106 87V113M106 87h35"/>
        <path class="benchmark-scene-route benchmark-scene-route-active benchmark-scene-draw" pathLength="1" d="M106 87h70V35h35"/>
        <path class="benchmark-scene-icon benchmark-scene-icon-copper" d="m205 30 6 5-6 5"/>
        <circle class="benchmark-scene-token" cx="106" cy="87" r="7"/>
        <circle class="benchmark-scene-goal" cx="211" cy="35" r="7"/>
        <circle class="benchmark-scene-goal-center" cx="211" cy="35" r="2"/>
        <path class="benchmark-scene-callout" d="M34 51h30l13 10M241 90h20l13 14"/>
        <circle class="benchmark-scene-dot" cx="34" cy="51" r="2"/>
        <circle class="benchmark-scene-dot" cx="274" cy="104" r="2"/>
        ${label('observe', 30, 39)}
        ${label('choose', 266, 123)}
        ${label('move', 159, 151, 'benchmark-scene-centered')}
      `,
    },
  ];
  const cards = document.querySelectorAll('#homeBenchmarks .home-usecase');
  scenes.forEach((scene, index) => {
    const card = cards[index];
    if (!card || card.querySelector('.benchmark-scene')) return;
    const figure = document.createElement('figure');
    figure.className = `benchmark-scene benchmark-scene-${scene.kind}`;
    figure.dataset.i18nRaw = '';
    figure.innerHTML = `<svg class="benchmark-scene-art" viewBox="0 0 330 158" aria-hidden="true" focusable="false">${scene.art}</svg><figcaption class="benchmark-scene-caption"></figcaption>`;
    card.querySelector('h3')?.before(figure);
    const translate = () => {
      figure.querySelectorAll('[data-benchmark-label]').forEach(node => {
        node.textContent = tr(...scene.labels[node.dataset.benchmarkLabel]);
      });
      figure.querySelector('figcaption').textContent = tr(...scene.caption);
    };
    translate();
    window.JevI18n?.onChange(translate);
  });
})();
