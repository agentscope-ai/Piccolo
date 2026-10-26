"""Shared browser wall clock, stopped at the first observed native terminal.

A readonly getter is injected into the existing engine closure. It never calls
snapshot(), whose visibility bookkeeping has side effects in the RL worlds.
The observer checks once per animation frame; elapsed time is performance.now,
not frame / FPS. Terminal detection precision is one animation frame.
"""

CLOCK_REVISION = 'browser-first-terminal-wall-clock-v1'

STOPWATCH_JS = r'''
(() => {
  let started=null,terminal=null,stopped=null,initialWins=0,generation=0;
  const native=()=>{
    if(typeof window.__JevEpisodeTerminal!=='function')throw Error('native_terminal_clock_unavailable');
    return window.__JevEpisodeTerminal();
  };
  function observe(){
    if(started===null||terminal!==null||stopped!==null)return;
    const state=native();
    if(state.outcome||(state.wins||0)>initialWins)terminal=performance.now();
  }
  function watch(own){
    if(own!==generation||stopped!==null||terminal!==null)return;
    observe();
    if(terminal===null)requestAnimationFrame(()=>watch(own));
  }
  const elapsed=()=>{
    if(started===null)throw Error('episode_clock_not_started');
    observe();return ((terminal??stopped??performance.now())-started)/1000;
  };
  window.__JevEpisodeClock={
    start(){initialWins=native().wins||0;started=performance.now();terminal=null;stopped=null;
      const own=++generation;requestAnimationFrame(()=>watch(own));return started;},
    elapsedSeconds:elapsed,
    wallSeconds(){if(started===null)throw Error('episode_clock_not_started');return (performance.now()-started)/1000;},
    finish(){observe();stopped=performance.now();return this.report();},
    report(){return {revision:'browser-first-terminal-wall-clock-v1',elapsed_seconds:elapsed(),
      observed_wall_seconds:this.wallSeconds(),terminal_observed:terminal!==null,
      terminal_detection_precision:'one_animation_frame',clock_source:'performance.now'};}
  };
})();
'''


async def install_episode_clock(page, kind):
    """Install before goto; no file edits, model calls, or physics changes."""
    if kind not in ('mario_platformer', 'terraria_survival'):
        raise ValueError('unsupported_browser_episode_clock')
    filename = 'mario' if kind == 'mario_platformer' else 'terraria'
    getter = ('window.__JevEpisodeTerminal=()=>({outcome,wins:0});'
              if kind == 'mario_platformer' else
              'window.__JevEpisodeTerminal=()=>({outcome:null,wins});')
    await page.add_init_script(STOPWATCH_JS)

    async def script(route):
        response = await route.fetch()
        source = await response.text()
        marker = source.rfind('})();')
        if marker < 0:
            raise ValueError('unknown_world_script_shape_for_clock')
        await route.fulfill(response=response, body=source[:marker]+getter+'\n'+source[marker:])

    await page.route(f'**/{filename}.js*', script)
