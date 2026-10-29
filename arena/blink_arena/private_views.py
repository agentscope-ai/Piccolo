"""Display-only fixed-seat views. Decision observations remain actor-specific."""
import jev_agent_games as agent
import jev_selected_games as selected


def fixed_view(world, seat):
    if world['kind'] == 'uno':
        native, _, _ = selected._load(world)
        concealed = bool(world.get('handoff') and selected.actor(world) == seat)
        own = native.get_state(seat)['raw_obs']
        return {'seat': seat, 'concealed': concealed,
                'hand': [] if concealed else list(own['hand']),
                'hand_counts': [len(p.hand) for p in native.game.players],
                'target': native.game.round.target.get_str()}
    if world['kind'] == 'liars_dice':
        native = agent.restore(world)
        concealed = bool(world.get('handoff') and agent.actor(world, native) == seat)
        return {'seat': seat, 'concealed': concealed,
                'dice': [] if concealed else [int(n) for n in native.information_state_string(seat).split()[0]]}
    return None
