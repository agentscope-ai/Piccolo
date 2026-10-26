"""Small live prompt overrides; deterministic facts never choose an action."""
import copy
import json
import os
from pathlib import Path

from blink_arena.paths import REPO
CONFIG=REPO / "config/game-prompts.json"
_cached_signature=None
_cached_config={}


def config_path():
    """Same effective file for record construction and RL source binding."""
    return Path(os.environ.get('JEV_GAME_PROMPTS_PATH', str(CONFIG)))


def snake_facts(record):
    import jev_snake_realtime as snake
    state=record['state']
    if not snake.is_realtime(state):
        raise ValueError('snake prompt facts require the current realtime observation')
    actions=record['questions']['decision']['criteria']
    result={}
    for old_moves in (0,1):
        arrival=copy.deepcopy(state)
        if old_moves:
            direction=arrival.get('pending_direction',arrival['direction'])
            head,body,eating,collision=snake.next_cell(arrival,direction)
            if collision or eating:
                result[str(old_moves)]={'old_input_collision':collision,
                    'old_input_eats_visible_food':eating,
                    'candidate_projection_unavailable':'collision or next food is not observable'}
                continue
            arrival.update(body=body,direction=direction)
        candidates={}
        for action in actions:
            direction=arrival['direction'] if action==snake.REVERSE[arrival['direction']] else action
            head,body,eating,collision=snake.next_cell(arrival,direction)
            fact={'next_head':head,'collision':collision,'eats_visible_food':eating,
                  'input_would_reverse_and_be_ignored':direction!=action}
            if not collision:
                blocked={tuple(p) for p in body[1:]+arrival['obstacles']}
                distances=snake._reachable(head,blocked,arrival['n'])
                fact.update(static_distance_to_visible_food=distances.get(tuple(arrival['food'])),
                            reachable_free_cells=len(distances))
                projected=copy.deepcopy(arrival)
                projected.update(body=body,direction=direction)
                runway=1
                if not eating:
                    for _ in range(3):
                        h,b,ate,hit=snake.next_cell(projected,direction)
                        if hit:break
                        runway+=1
                        if ate:break
                        projected['body']=b
                fact['straight_safe_moves_up_to_4']=runway
            candidates[action]=fact
        result[str(old_moves)]={'arrival_head':arrival['body'][0],'candidates':candidates}
    return result


def transform(record,override):
    if not override:
        return record
    result=copy.deepcopy(record)
    question=result['questions']['decision']
    if isinstance(override,str):
        question['instructions']=override
    else:
        if override.get('instructions'):
            question['instructions']=override['instructions']
        extra=override.get('append')
        if extra and not question['instructions'].endswith(extra):
            question['instructions']+='\n'+extra
        if override.get('snake_geometry_footer'):
            marker='\n公开几何条件核对（不选择动作；假设旧输入再移动0格/1格，不是实际网络延迟保证）：\n'
            question['instructions']=question['instructions'].split(marker)[0]+marker+json.dumps(
                snake_facts(result),ensure_ascii=False,separators=(',',':'))
        if override.get('snake_option_facts'):
            facts=snake_facts(result)
            question['instructions']+=('\nCurrent head='+str(result['state']['body'][0])+
                '; visible food='+str(result['state']['food'])+
                '; old pending heading='+result['state']['pending_direction']+
                '; seconds until old input moves='+str(result['state']['seconds_to_next_move'])+'.')
            for action,label in list(question['criteria'].items()):
                parts=[]
                for count,title in [('0','NOW'),('1','AFTER_ONE_OLD_MOVE')]:
                    value=facts[count].get('candidates',{}).get(action)
                    if value is None:
                        parts.append(title+': '+str({k:v for k,v in facts[count].items() if k!='candidates'}))
                    else:
                        parts.append(title+': '+json.dumps(value,ensure_ascii=False,separators=(',',':')))
                question['criteria'][action]=label.split(' | NOW:')[0]+' | '+' | '.join(parts)
    return result


def apply(record):
    global _cached_signature,_cached_config
    path = config_path()
    if not path.exists():
        return record
    stat=path.stat()
    signature=(str(path),stat.st_mtime_ns,stat.st_size)
    if signature!=_cached_signature:
        config=json.loads(path.read_text())
        if config.get('schema')!='jev.live-prompt-calibration.v1':
            raise ValueError('unknown live prompt calibration schema')
        _cached_config=config
        _cached_signature=signature
    metadata=record.get('metadata',{})
    source=record.get('provenance',{}).get('data_source')
    if source not in {'jev.demo.live','cues_social_games_v1','cues_live_opponent_eval',
                      'jev_live_agent_games','cues_live_rally_engine','cues_showcase_synthetic_v1',
                      'openspiel','textarena','rlcard','cues_probability_games_v1'}:
        return record
    kind=metadata.get('sub_domain') or record.get('state',{}).get('kind')
    if kind in ('mario_platformer','terramai_directional','terraria_survival'):
        return record
    override=_cached_config.get('games',{}).get(kind)
    return transform(record,override) if override else record
