// Shared model display names; registered identities remain unchanged.
(function (root) {
  'use strict';
  const aliases={
    'oneshot-hosted':'Piccolo',
    'oneshot-w22m05r02-v5best-avg50':'Piccolo-27B',
    'ours-w22m05r02-v5best-avg50':'Piccolo-27B',
    'oneshot-rl-r6-iter0000019':'Piccolo-27B',
    'oneshot27b-control-reviewed-sft-iter310':'Piccolo 27B SFT',
    'oneshot27b-gameplay-terminal-rl4':'Piccolo 27B RL',
    'oneshot27b-game-rl-native-iter17':'Piccolo 27B RL'
  };
  function arenaModelName(id,label) {
    if(aliases[id])return aliases[id];
    let value=String(label||id||'Model').trim();
    if(/^(?:OneShot|QwenJev|Blink)(?:$|\s+\(?27B\)?(?:$|[\s·-]))/i.test(value))value=value.replace(/^(?:OneShot|QwenJev|Blink)\b/i,'Piccolo');
    const release=value.match(/^Piccolo\s+27B\s+(RL|SFT)(?=$|[\s·-])/i);
    if(release)return 'Piccolo 27B '+release[1].toUpperCase();
    if(/^Piccolo\s*\(27B\)$/i.test(value))return 'Piccolo-27B';
    return value.replace(/(?:\s*[·|—–-]\s*|\s+\(?\s*)DashScope\s*\)?$/i,'').trim();
  }
  const api={model:arenaModelName};
  if(typeof module!=='undefined'&&module.exports)module.exports=api;
  if(root)root.JevArenaDisplay=api;
})(typeof window==='undefined'?null:window);
