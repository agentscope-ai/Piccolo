"""Shared lazy engine registry for frontend, sampling and evaluation.

Importing this module requires only Python's standard library. It does not
load FastAPI, model clients, training packages, OpenSpiel, browser automation
or a machine-specific path. Register a standard Environment to add a native
game; browser physics additionally require an explicit real bridge/replay.
"""
from __future__ import annotations

import copy
import os
from dataclasses import dataclass, field, replace as dataclass_replace
from importlib import import_module
from typing import Any, Mapping

from jev_engine_environment import (
    INTERFACE_REVISION, BoardEnvironment, BrowserEnvironment, Environment,
    LazyEnvironment, ModuleEnvironment, RobotGraspEnvironment, WorkerEnvironment,
)

REVISION = 'jev.engine.registry.v1'


@dataclass(frozen=True)
class EngineSpec:
    kind: str
    name: str
    environment: Environment
    family: str = 'showcase'
    backend: str = 'native'
    clock: str = 'turn'
    scene: Mapping[str, Any] = field(default_factory=dict)
    goal: str = ''
    limit: int = 100
    opponent_modes: tuple[str, ...] = ('environment',)
    seat_count: int = 1
    internal: bool = False
    sft_export_prohibited: bool = False
    runtime_module: str | None = None
    rl_runner: str | None = None
    rl_verify: str | None = None
    browser_page: str | None = None
    browser_bridge: str | None = None
    browser_assets: tuple[str, ...] = ()
    browser_replay_hook: str | None = None
    browser_terminal_getter: str | None = None
    core_module: str | None = None
    core_viewport: tuple[int, int] = (896, 448)
    capabilities: tuple[str, ...] = ('seeded_reset', 'choice', 'public_observation')
    source_modules: tuple[str, ...] = ()
    scene_source: str | None = None
    renderer: str = 'generic'
    archived: bool = False
    interface_revision: str = INTERFACE_REVISION

    def reset(self, seed, options=None):
        return self.environment.reset(seed, options)

    def legal_actions(self, state):
        return self.environment.legal_actions(state)

    def observe(self, state):
        return self.environment.observe(state)

    as_record = observe

    def step(self, state, action, **kwargs):
        return self.environment.step(state, action, **kwargs)

    def raw_step(self, state, action, **kwargs):
        return getattr(self.environment, 'raw_step', self.environment.step)(state, action, **kwargs)

    def public(self, state, **kwargs):
        return self.environment.public(state, **kwargs)

    def outcome(self, state, side=None):
        return self.environment.outcome(state, side)

    @property
    def runtime(self):
        return import_module(self.runtime_module) if self.runtime_module else None

    def bind(self, driver):
        binder = getattr(self.environment, 'bind', None)
        if binder is None:
            raise TypeError(f'{self.kind} does not use an external execution driver')
        return dataclass_replace(self, environment=binder(driver))

    def descriptor(self):
        """JSON-safe discovery metadata; no callables or private engine state."""
        names = ('kind', 'name', 'family', 'backend', 'clock', 'goal', 'limit',
                 'seat_count', 'internal', 'sft_export_prohibited', 'archived',
                 'browser_page', 'browser_bridge', 'interface_revision', 'renderer',
                 'runtime_module', 'rl_runner', 'rl_verify', 'browser_replay_hook',
                 'browser_terminal_getter', 'core_module', 'core_viewport')
        value = {name: getattr(self, name) for name in names}
        value['core_viewport'] = list(self.core_viewport)
        value.update(scene=self.scene_descriptor(),
                     opponent_modes=list(self.opponent_modes),
                     browser_assets=list(self.browser_assets),
                     source_modules=list(self.source_modules),
                     capabilities=list(self.capabilities),
                     replay_available=bool(self.rl_verify))
        return value

    manifest = descriptor

    def scene_descriptor(self):
        """Preserve existing display/opponent metadata while supplying defaults.

        Optional engines are loaded only when their own metadata is requested,
        never at registry import. New plugins need no pre-existing catalog row.
        """
        scene = {'name': self.name, 'mode': 'world' if self.family == 'world' or self.backend == 'browser' else
                 'board' if self.family == 'board' else 'game', 'note': self.goal}
        if self.scene_source:
            module, attribute = self.scene_source.split(':', 1)
            source = getattr(import_module(module), attribute)
            scene.update(copy.deepcopy(source.get(self.kind, {})) if attribute == 'SCENES'
                         else copy.deepcopy(source))
        scene.update(copy.deepcopy(dict(self.scene)))
        return scene


_ENGINES: dict[str, EngineSpec] = {}
_BUILTINS: set[str] = set()
_ARCHIVED: dict[str, EngineSpec] = {}
_LOADED_PLUGINS: list[str] = []
_PLUGIN_CONTEXT: list[str] = []
from jev_control_scope import policy as _scope_policy
_RETIRED = frozenset(_scope_policy().get('retired_games', ()))


def register_engine(spec: EngineSpec, *, replace=False):
    if not isinstance(spec, EngineSpec):
        raise TypeError('register_engine requires EngineSpec')
    if not spec.kind or any(c not in 'abcdefghijklmnopqrstuvwxyz_0123456789' for c in spec.kind):
        raise ValueError('engine kind must be a lowercase identifier')
    if _PLUGIN_CONTEXT and spec.kind in _RETIRED:
        raise ValueError('game_removed_from_active_scope: ' + spec.kind)
    if spec.kind in _ENGINES and (not replace or _PLUGIN_CONTEXT):
        raise ValueError(f'engine already registered: {spec.kind}')
    if spec.backend not in ('native', 'browser', 'worker') or spec.clock not in ('turn', 'realtime'):
        raise ValueError('unknown backend or clock contract')
    if type(spec.limit) is not int or spec.limit <= 0 or not spec.opponent_modes:
        raise ValueError('positive decision limit and opponent modes are required')
    if type(spec.seat_count) is not int or spec.seat_count <= 0:
        raise ValueError('seat_count must be a positive integer')
    if len(set(spec.opponent_modes)) != len(spec.opponent_modes):
        raise ValueError('opponent_modes must contain unique modes')
    if any(not isinstance(mode, str) or not mode.strip() for mode in spec.opponent_modes):
        raise ValueError('opponent_modes must contain nonempty strings')
    if bool(spec.rl_runner) != bool(spec.rl_verify):
        raise ValueError('custom RL runner and verifier must be registered together')
    if spec.backend == 'browser' and (not spec.browser_page or not spec.browser_bridge):
        raise ValueError('browser engines require page and bridge metadata')
    if spec.clock == 'realtime' and spec.backend == 'native' and not all(
            (spec.runtime_module, spec.rl_runner, spec.rl_verify)):
        raise ValueError('native realtime engines require clock runtime, RL runner and exact replay verifier')
    if spec.backend == 'browser' and not all((spec.browser_assets, spec.rl_runner, spec.rl_verify)):
        raise ValueError('browser engines require packaged assets, RL runner and replay verifier')
    if spec.core_module is not None and (
            spec.backend != 'worker' or spec.core_module not in spec.browser_assets or
            not spec.rl_runner or not spec.rl_verify or
            len(spec.core_viewport) != 2 or any(type(x) is not int or x <= 0 for x in spec.core_viewport)):
        raise ValueError('shared core workers require packaged module, positive viewport and runner/verifier')
    for path in (*spec.browser_assets, *((spec.browser_page,) if spec.browser_page else ())):
        if not isinstance(path, str) or path.startswith('/') or '..' in path.split('/') or '\\' in path:
            raise ValueError('browser assets must be relative package paths')
    if not isinstance(spec.environment, Environment):
        raise TypeError('environment must implement reset/legal_actions/observe/step/public/outcome')
    if _PLUGIN_CONTEXT:
        spec = dataclass_replace(spec, source_modules=tuple(dict.fromkeys(
            (*spec.source_modules, _PLUGIN_CONTEXT[-1]))))
    if spec.kind in _RETIRED:
        # Kept solely for explicit historical replay, never live engine lookup.
        _ARCHIVED[spec.kind] = dataclass_replace(spec, archived=True)
    else:
        _ENGINES[spec.kind] = spec
    return spec


def unregister_engine(kind):
    """Remove a dynamic plugin, never a built-in historical capability."""
    if kind in _BUILTINS:
        raise ValueError('built-in engines cannot be unregistered; use release scope filtering')
    return _ENGINES.pop(kind)


def list_engines(*, backend=None, family=None, include_internal=True):
    return tuple(spec for spec in _ENGINES.values()
                 if (include_internal or not spec.internal)
                 and (backend is None or spec.backend == backend)
                 and (family is None or spec.family == family))


def get_engine(kind, state=None):
    try:
        spec = _ENGINES[kind]
    except KeyError as exc:
        raise ValueError(f'unknown engine: {kind}') from exc
    if state is not None:
        state_kind = state.get('kind') or state.get('game')
        if state_kind is not None and state_kind != kind:
            raise ValueError(f'engine/state kind mismatch: {kind} vs {state_kind}')
    if state is not None and kind in _ARCHIVED:
        if kind in ('snake_navigation', 'tetris_placement'):
            if not import_module(spec.environment.module_name).is_realtime(state):
                # Explicit old turn-state layout, not an unrecognized future
                # realtime revision. Never silently reinterpret newer physics.
                if state.get('engine_revision'):
                    raise ValueError(f'unsupported {kind} engine revision: {state["engine_revision"]}')
                return _ARCHIVED[kind]
        elif kind == 'terraria_survival' and 'player' not in state and 'hp' in state:
            return _ARCHIVED[kind]
        elif kind == 'chess' and '_moves' in state and not state.get('engine_revision'):
            return _ARCHIVED[kind]
    return spec


def get_archived_engine(kind):
    """Explicit compatibility entry for original offline simulator fixtures.

    Live callers must use get_engine(); archived reset must never be selected
    merely because a browser driver is missing.
    """
    try:
        return _ARCHIVED[kind]
    except KeyError as exc:
        raise ValueError(f'no archived engine for {kind}') from exc


def engine_manifest():
    return {'revision': REVISION, 'interface_revision': INTERFACE_REVISION,
            'engines': [spec.descriptor() for spec in list_engines()],
            'archived': [spec.descriptor() for spec in _ARCHIVED.values()],
            'plugins': list(_LOADED_PLUGINS)}


def engine_source_modules():
    """Modules to bind in provenance without importing optional runtimes."""
    names = {'jev_engine_registry', 'jev_engine_environment'}
    for spec in (*_ENGINES.values(), *_ARCHIVED.values()):
        names.update(spec.source_modules)
        for value in (spec.runtime_module, spec.rl_runner, spec.rl_verify, spec.scene_source,
                      getattr(spec.environment, 'module_name', None),
                      getattr(spec.environment, 'record_module', None)):
            if value:
                names.add(value.split(':', 1)[0])
        module = type(spec.environment).__module__
        if module not in ('builtins', '__main__'):
            names.add(module)
    return tuple(sorted(names))


def load_engine_plugins(modules=None):
    """Import explicitly configured plugins, once per process.

    ``JEV_ENGINE_PLUGINS=package.first,package.second`` is the common startup
    hook for frontend/RL. A module registers EngineSpec objects at import, or
    exposes ``register_engines(register_engine)``. There is no directory scan
    or implicit execution of arbitrary files. Registration failures roll back
    that module's registry mutations and remain visible to the caller.
    """
    if modules is None:
        modules = os.environ.get('JEV_ENGINE_PLUGINS', '')
    if isinstance(modules, str):
        modules = [name.strip() for name in modules.split(',') if name.strip()]
    for name in modules:
        if not isinstance(name, str) or not name or not all(part.isidentifier() for part in name.split('.')):
            raise ValueError('plugin must be an importable dotted module name')
        if name in _LOADED_PLUGINS:
            continue
        before = dict(_ENGINES)
        _PLUGIN_CONTEXT.append(name)
        try:
            module = import_module(name)
            registrar = getattr(module, 'register_engines', None)
            # A plugin uses one registration style. Do not call its optional
            # hook again after it already registered at import time.
            if registrar is not None and _ENGINES == before:
                registrar(register_engine)
        except BaseException:
            _ENGINES.clear()
            _ENGINES.update(before)
            raise
        finally:
            _PLUGIN_CONTEXT.pop()
        _LOADED_PLUGINS.append(name)
    return tuple(_LOADED_PLUGINS)


def _add(kind, name, module, goal, limit, *, family='showcase', **kwargs):
    env = ModuleEnvironment(kind, module, family=family,
                            fresh_with_kind=family not in ('realtime', 'robot'),
                            adapt=family != 'realtime', remember_effects=family != 'realtime',
                            record_without_reference=module == 'jev_showcase_games')
    scene = kwargs.pop('scene', {})
    scene_source = {
        'jev_showcase_games': 'jev_showcase_common:SCENES',
        'jev_social_games': 'jev_social_games:SCENES',
        'jev_probability_games': 'jev_probability_games:SCENES',
        'jev_agent_games': 'jev_agent_games:SCENES',
        'jev_snake_realtime': 'jev_showcase_common:SCENES',
        'jev_tetris_realtime': 'jev_showcase_common:SCENES',
        'jev_racing_game': 'jev_racing_game:SCENE',
    }.get(module)
    if family == 'realtime' and module != 'jev_racing_game':
        scene = {'note': goal, **scene}
    return register_engine(EngineSpec(kind, name, env, family=family, scene=scene, renderer='legacy',
                                     scene_source=scene_source, goal=goal, limit=limit, **kwargs))


def _builtins():
    opponents = ('qwen3.8-max', 'rule_engine')
    # Stable historical order is part of seeded roster identity. Internal
    # adapters are appended after the live catalog, never inserted before it.
    boards = (
        ('tic_tac_toe', '井字棋', 9, '连成三个棋子'),
        ('connect_four', '四子棋', 42, '连成四个棋子'),
        ('othello_6x6', '黑白棋 · 6×6', 38, '终局时拥有更多棋子'),
        ('othello_8x8', '黑白棋 · 8×8', 66, '终局时拥有更多棋子'),
        ('gomoku_19x19', '五子棋 · 19×19', 120, '连成五个棋子'),
        ('hex_7x7', 'Hex · 7×7', 49, '连接己方两侧边界'),
        ('dots_and_boxes_3x3', '点格棋 · 3×3', 24, '取得更多盒子'),
    )
    for kind, name, limit, goal in boards:
        register_engine(EngineSpec(kind, name, BoardEnvironment(kind), family='board',
                        scene={'name': name, 'mode': 'board', 'note': goal}, goal=goal,
                        limit=limit, opponent_modes=opponents, seat_count=2, renderer='legacy'))
    worlds = {
        'terraria_survival': ('泰拉瑞亚 · Terramai', 'terraria', 'JevTerramai',
                             'jev_terraria_contract', 300, '采矿与小怪战斗升级装备，击败守门 Boss 后进入胜利之门'),
        'mario_platformer': ('马里奥 · 像素闯关', 'mario', 'JevMario',
                             'jev_mario_contract', 160, '活着抵达右侧终点旗杆'),
    }
    def world(kind):
        name, page, bridge, contract, limit, goal = worlds[kind]
        scene = ({'name': name, 'mode': 'world', 'note': '探索、采矿和战斗成长；玩家参与击败指定守门 Boss 后，活着进入地图右侧胜利之门。',
                  'source_label': '交互仿真 · Xinji-Mai / Terramai',
                  'url': 'https://github.com/Xinji-Mai/Xinji-Mai.github.io/blob/master/assets/js/tasty-world.js'}
                 if kind == 'terraria_survival' else
                 {'name': name, 'mode': 'world', 'note': '网页像素闯关：顶问号方块弹出金币或蘑菇，避开管道食人花、深坑和敌人，抵达终点旗杆。',
                  'source_label': '交互仿真 · CuES 网页关卡', 'url': None})
        return register_engine(EngineSpec(kind, name, WorkerEnvironment(kind, contract),
                        family='world', backend='worker', clock='realtime', renderer='legacy',
                        scene=scene, goal=goal, limit=limit,
                        browser_page=page, browser_bridge=bridge,
                        core_module=page+'-core.js',
                        core_viewport=(896, 448) if kind == 'mario_platformer' else (888, 480),
                        browser_assets=(page+'.html', page+'.js', page+'-core.js',
                            'world-arrival.js', 'world-seed.js', 'world-core-worker.cjs'),
                        rl_runner='jev_world_core_rl:play', rl_verify='jev_world_core_rl:verify',
                        capabilities=('seeded_reset', 'choice', 'public_observation', 'realtime', 'shared_js_core', 'exact_replay')))
    world('terraria_survival')
    _add('jump_jump', '跳一跳 · 落点控制', 'jev_showcase_games', '连续跳上 8 个平台', 12)
    realtime = (
        ('tetris_placement', '俄罗斯方块', 'tetris', 'jev_tetris_realtime', 320,
         '实时下落，在 240 秒和 40 块内消除 4 行，避免堆顶'),
        ('snake_navigation', '贪吃蛇', 'snake', 'jev_snake_realtime', 240,
         '实时前进，避开墙、石块和身体，吃到 6 个苹果'),
    )
    for kind, name, short, module, limit, goal in realtime:
        _add(kind, name, module, goal, limit, family='realtime', clock='realtime',
             source_modules=('jev_tetris_projection',) if short == 'tetris' else (),
             runtime_module=f'jev_{short}_runtime', rl_runner=f'jev_{short}_rl:play',
             rl_verify=f'jev_{short}_rl:verify', capabilities=('seeded_reset', 'choice', 'public_observation',
                         'realtime', 'capture_commit_tick', 'exact_replay'))
    _add('merge_2048', '2048 · 合并挑战', 'jev_showcase_games', '120 步内合成 128 方块', 120)
    _add('sokoban_puzzle', '推箱子 · 仓库谜题', 'jev_showcase_games', '80 步内把两只箱子推到目标格', 80)
    world('mario_platformer')
    _add('racing_sprint', '赛车 · Rally Sprint', 'jev_racing_game',
         '首次踩油门后300秒内自主驾驶900米抵达终点，车辆耐久大于0；允许停车和低速恢复', 320,
         family='realtime', clock='realtime', runtime_module='jev_racing_runtime',
         rl_runner='jev_racing_rl:play', rl_verify='jev_racing_rl:verify', sft_export_prohibited=True,
         capabilities=('seeded_reset', 'choice', 'public_observation', 'realtime', 'capture_commit_tick', 'exact_replay'))
    for kind, name, goal, limit in (
        ('doudizhu', '斗地主', '以地主身份先出完手牌', 100),
        ('texas_holdem', '德州扑克', '用虚拟筹码完成一手牌并赢下底池', 30),
        ('property_tycoon', '大富翁', '20回合经营地产，资产超过对手', 100),
    ):
        _add(kind, name, 'jev_social_games', goal, limit, family='social', opponent_modes=opponents,
             seat_count=3 if kind == 'doudizhu' else 2)
    for kind, name, goal, limit in (
        ('chess', '国际象棋', '将死对方的王', 200),
        ('breakthrough', '兵卒突围', '让一枚兵突破对方底线', 100),
        ('mancala', '播棋 · Mancala', '收集比对手更多的种子', 100),
        ('liars_dice', '吹牛骰子', '识破虚报，或让对手质疑失败', 50),
        ('goofspiel', '竞价夺牌', '用七张手牌赢得更多奖分', 20),
        ('blackjack', '21 点', '不超过 21 点，并胜过庄家', 20),
    ):
        _add(kind, name, 'jev_agent_games', goal, limit, family='agent',
             opponent_modes=('rule_engine',) if kind == 'blackjack' else opponents,
             seat_count=1 if kind == 'blackjack' else 2,
             internal=kind in ('chess', 'breakthrough', 'mancala'))
    # Preserve explicit historical states while enabling the shared orthodox
    # chess environment for every new frontend/RL session.
    _ARCHIVED['chess'] = dataclass_replace(_ENGINES['chess'], archived=True)
    register_engine(EngineSpec('chess', '国际象棋', LazyEnvironment('jev_chess', 'ChessEnvironment'),
        family='strategy', renderer='chess', limit=256, seat_count=2,
        goal='按标准国际象棋规则将死对方的王', opponent_modes=opponents,
        scene={'name': '国际象棋', 'mode': 'game', 'supports_opponent': True,
               'note': '完整合法着法、棋谱与一步公开后果；种子 0 为标准开局，其余种子为可复现合法开局。',
               'source_label': '规则 · python-chess / 决策接口参考 · StartLux',
               'url': 'https://github.com/StartLuxLabs/Startlux-Decision'},
        rl_runner='jev_chess_rl:play', rl_verify='jev_chess_rl:verify',
        source_modules=('jev_chess',),
        capabilities=('seeded_reset', 'choice', 'public_observation', 'exact_replay',
                      'reference_action', 'controller_provenance')), replace=True)
    for kind, name, goal, limit in (
        ('zha_jin_hua', '炸金花', '赢下这手三张牌的底池', 8),
        ('pig_dice', '掷骰猪', '先于对手达到 50 分', 90),
    ):
        _add(kind, name, 'jev_probability_games', goal, limit, family='probability',
             opponent_modes=opponents, seat_count=2)
    _add('robot_pick_cola', '机械臂 · 拿起可乐', 'jev_demo_robot_pick',
         '移动、对准并夹起红色可乐，最后抬升到安全高度', 40, family='robot', internal=True)
    _add('robot_grasp', '机械臂 · 抓取放置', 'jev_showcase_games',
         '安全抓取、抬升、搬运并放置物体', 20, family='embodied', internal=True)
    _ENGINES['robot_grasp'] = dataclass_replace(_ENGINES['robot_grasp'],
        environment=RobotGraspEnvironment('robot_grasp', 'jev_showcase_games',
                                         family='embodied', record_without_reference=True),
        source_modules=('jev_showcase_robot',))
    for kind in ('snake_navigation', 'tetris_placement', 'terraria_survival'):
        current = _ENGINES[kind]
        env = ModuleEnvironment(kind, 'jev_showcase_games', archived=True, record_without_reference=True)
        _ARCHIVED[kind] = dataclass_replace(current, environment=env, family='showcase', backend='native', clock='turn',
             runtime_module=None, rl_runner=None, rl_verify=None, browser_page=None, browser_bridge=None,
             browser_assets=(), archived=True, capabilities=('choice', 'public_observation', 'archived_replay'),
             limit={'snake_navigation': 80, 'tetris_placement': 40, 'terraria_survival': 12}[kind],
             goal={'snake_navigation': '80 步内吃到 3 个食物', 'tetris_placement': '40 块内累计消除 4 行',
                   'terraria_survival': '按归档简化生存规则结算'}[kind])
    from jev_selected_games import register_games
    register_games(register_engine, EngineSpec)
    _BUILTINS.update(_ENGINES)


_builtins()
load_engine_plugins()
