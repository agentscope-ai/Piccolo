"""Expose the existing native opponent callbacks as interactive player turns.

No new card, chance or settlement rules: a partially answered outer turn is
replayed from its saved state with the same seed and already supplied choices.
"""
import copy
import random
from types import SimpleNamespace

from fastapi import HTTPException
import jev_social_games as social
import jev_eval_social_opponents as opponents
import jev_probability_games as probability
from jev_game_seat_control import doudizhu_record, rule_actor0
from jev_engine_registry import get_engine

KINDS = {'doudizhu', 'texas_holdem', 'property_tycoon', 'zha_jin_hua'}


class AwaitOpponent(Exception):
    def __init__(self, record):
        self.record = copy.deepcopy(record)


class SocialDuel:
    def __init__(self, world):
        self.world = copy.deepcopy(world)
        self.engine = get_engine(world['kind'])
        self.outer_action = None
        self.responses = []
        self.pending = None
        self.handoff = False

    @property
    def actor(self):
        return self.world['turn'] if self.world['kind'] == 'doudizhu' else int(self.pending is not None)

    def record(self):
        if self.world.get('outcome'):
            return None
        if self.pending is not None:
            return copy.deepcopy(self.pending)
        if self.world['kind'] == 'doudizhu':
            native = SimpleNamespace(as_record=self.engine.observe, social=social, social_opponents=opponents)
            return doudizhu_record(native, self.world, self.actor)
        return self.engine.observe(self.world)

    def public(self, view_seat=None):
        record = None if self.handoff else self.record()
        # The callback observation is the complete allowed view for that seat.
        # Never attach the outer world's hands, deck or previous seat's input.
        return {'kind': self.world['kind'], 'duel': True, 'current_player': self.actor,
            'steps': self.world['steps'], 'handoff': self.handoff,
            'outcome': self.world.get('outcome'), 'score': self.world.get('score', 0),
            'players': ['地主', '农民一', '农民二'] if self.world['kind'] == 'doudizhu' else ['玩家一', '玩家二'],
            'observation': copy.deepcopy(record['state']) if record else None,
            'event': self.world.get('event', '') if not self.handoff else '',
            'table': self.table(view_seat)}

    def table(self, view_seat=None):
        """Display an explicitly fixed seat without changing the acting record.

        This is deliberately separate from the decision record. Never send the
        full native world: it contains the deck and every player's private hand.
        Pending callbacks describe a newer public board than self.world.
        """
        world, actor = self.world, self.actor
        view = actor if view_seat is None else view_seat
        concealed = self.handoff and (view_seat is None or view == actor)
        kind = world['kind']
        record = self.record()
        obs = record['state']['observation'] if record else {}
        table = {key: copy.deepcopy(world.get(key)) for key in ('kind', 'steps', 'outcome', 'event')}
        table.update(duel=True, view_seat=view, active_seat=actor, handoff=concealed,
                     seat_ids=[view, *[i for i in range(3 if kind == 'doudizhu' else 2) if i != view]])
        if self.pending:
            table['event'] = ''  # The saved outer turn's caption is no longer current.
        if kind == 'doudizhu':
            order = [view, (view + 1) % 3, (view + 2) % 3]
            table['seat_ids'] = order
            public = social.public(world)
            table.update(hand=[] if concealed else list(world['hands'][view]),
                hand_count=len(world['hands'][view]),
                opponent_counts=[len(world['hands'][seat]) for seat in order[1:]],
                seat_labels=[['Landlord', 'Farmer A', 'Farmer B'][seat] for seat in order],
                leader=order.index(world['leader']), last=copy.deepcopy(world['last']),
                last_card_ids=public.get('last_card_ids'),
                history=[{**entry, 'player': order.index(entry['player'])} for entry in public['history']])
            if not concealed and '_hand_card_ids' in world:
                table['hand_card_ids'] = list(world['_hand_card_ids'][view])
        elif kind in ('texas_holdem', 'zha_jin_hua'):
            table.update(pot=obs.get('pot', world['pot']),
                stacks=([obs['player_stack'], obs['own_stack']] if self.pending else list(world['stacks']))[::1 if view == 0 else -1],
                showdown=bool(world.get('showdown')), opponent_last=world.get('opponent_last', ''))
            if kind == 'texas_holdem':
                table.update(board=list(obs.get('board', world['board'])),
                    to_call=world['to_call'] if not self.pending and view == 0 else 0)
                if self.pending:
                    table['opponent_last'] = {'call': '跟注', 'check': '过牌', 'raise': '加注'}.get(obs.get('player_last_action'), '')
            else:
                table.update(round=obs.get('round', world['round']), stake=obs.get('stake', world['stake']),
                    seen=bool(world['seen'] if view == 0 else self.pending or world.get('opponent_seen')))
            visible = not concealed and (kind == 'texas_holdem' or table['seen'] or table['showdown'])
            table['hand'] = list(world['hands'][view]) if visible else ([] if kind == 'texas_holdem' else None)
            # A fold is a terminal result, but does not authorize revealing the opponent.
            if table['showdown']:
                table['opponent_hand'] = list(world['hands'][1 - view])
        else:
            for key in ('names', 'prices', 'owners', 'levels', 'cash', 'positions', 'phase', 'round', 'dice'):
                table[key] = copy.deepcopy(obs.get(key, world[key]))
            if self.pending:
                table['positions'][1] = obs['position']
                options = record['questions']['decision']['criteria']
                table['phase'] = 'buy' if 'buy' in options else 'build'
            if view:
                table['cash'].reverse()
                table['positions'].reverse()
                table['owners'] = {key: 1 - owner for key, owner in table['owners'].items()}
        return table

    def payload(self, view_seat=None):
        r = None if self.handoff else self.record()
        q = r['questions']['decision'] if r else None
        return {'world': self.public(view_seat), 'goal': self.engine.goal,
            'choices': q['criteria'] if q else {},
            'input': {'state': r['state'], 'prompt': q['instructions'], 'option': q['criteria']} if r else None}

    def rule_action(self):
        """Select for this seat using native policies, never another seat's cards."""
        kind = self.world['kind']
        record = self.record()
        options = record['questions']['decision']['criteria']
        if len(options) == 1:
            return next(iter(options))
        if kind == 'doudizhu':
            return social.dzbest(self.world, self.actor)
        if kind == 'property_tycoon':
            return social.propertybest(self.table())
        if self.pending is None:
            native = SimpleNamespace(social=social, probability=probability)
            return rule_actor0(native, record, self.world['seed'], self.world['steps'])
        obs = record['state']['observation']
        rng = random.Random(f"{self.world['seed']}/{self.world['steps'] + 1}")
        if kind == 'texas_holdem':
            # The native opponent samples a fixed betting tier. Restrict it to
            # this callback's legal tiers when either stack is almost empty.
            wager = rng.choice([0, 10, 20, 40])
            legal_bets = [int(a[3:]) for a in options if a.startswith('bet')]
            amount = max((n for n in legal_bets if n <= wager), default=0)
            return f'bet{amount}' if amount else 'check'
        rank = probability.rank3(tuple(obs['own_hand']))
        weak = rank[0] == 0 and rank[1] <= 10
        return 'fold' if obs['round'] >= 2 and weak and rng.random() < .28 else 'call'

    async def step(self, action, card_ids=None):
        if self.handoff:
            raise HTTPException(422, 'Reveal the current seat first')
        r = self.record()
        if not r or action not in r['questions']['decision']['criteria']:
            raise HTTPException(422, 'Illegal game action')
        actor = self.actor
        if self.world['kind'] == 'doudizhu':
            game = copy.deepcopy(self.world)
            if actor == 0:
                game['steps'] += 1
            social.dzplay(game, actor, action, card_ids=card_ids)
            game['history'] = game['history'][-12:]
            if not game['outcome'] and game['steps'] >= self.engine.limit and game['turn'] == 0:
                game['outcome'] = 'budget_exhausted'
            self.world = game
        else:
            outer = self.outer_action if self.pending is not None else action
            answers = [*self.responses, action] if self.pending is not None else []
            index = 0

            async def choose(record, ordinal):
                nonlocal index
                if index >= len(answers):
                    raise AwaitOpponent(record)
                chosen = answers[index]
                index += 1
                if chosen not in record['questions']['decision']['criteria']:
                    raise ValueError('Native callback replay changed')
                return chosen

            try:
                game, _ = await opponents.step(self.world, outer, choose)
            except AwaitOpponent as pause:
                self.outer_action, self.responses, self.pending = outer, answers, pause.record
            else:
                self.world = game
                self.outer_action, self.responses, self.pending = None, [], None
                if not game['outcome'] and game['steps'] >= self.engine.limit:
                    game['outcome'] = 'budget_exhausted'
        self.handoff = self.actor != actor and not self.world.get('outcome') and self.world['kind'] != 'property_tycoon'
