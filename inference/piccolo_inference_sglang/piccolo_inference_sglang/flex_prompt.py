"""FlexDM v1.0 prompt compiler, using upstream Layout without modifying it.

The complete request must reach this compiler BEFORE splitting model rows.
The explicit training extension accepts score questions; upstream does not.
"""
from copy import deepcopy
from dataclasses import dataclass
from ._vendor.reader import Layout, render_question
from ._vendor.base import Unsupported


@dataclass(frozen=True)
class PromptRow:
    question_id: str
    kind: str
    option_keys: tuple
    candidate_token_ids: tuple
    input_ids: tuple
    repeated: bool


def training_questions(questions):
    """Explicit adapter for Jev training score/option_order; leaves input intact."""
    result = deepcopy(questions)
    for q in result.values():
        if q['type'] == 'noul' and isinstance(q.get('criteria'), dict) and set(q['criteria']) == {'yes', 'no'}:
            # Jev training also permits yes/no criteria keys. Upstream Flex
            # expects false/true; retain both supplied descriptions explicitly.
            q['criteria'] = {'false': q['criteria']['no'], 'true': q['criteria']['yes']}
        if q['type'] == 'score':
            criteria = q['criteria']
            q['criteria'] = ({str(i): v for i, v in enumerate(criteria)}
                             if isinstance(criteria, list) else criteria)
            q['type'] = 'choice'
        order = q.get('option_order')
        if order is not None and q['type'] == 'choice':
            if len(order) != len(set(order)) or set(order) != set(q['criteria']):
                raise ValueError('option_order does not match candidate keys')
            q['criteria'] = {k: q['criteria'][k] for k in order}
    return result


class FlexPromptCompiler:
    def __init__(self, tokenizer, *, layout='header', read_twice=True,
                 twice_max_tokens=3000, max_row_tokens=131071):
        if layout not in {'header', 'decider'}:
            raise ValueError('Expected header or decider layout')
        if twice_max_tokens < 0 or max_row_tokens <= 0:
            raise ValueError('Invalid token limits')
        self.layout = Layout(tokenizer)
        # Upstream checks contextual token boundaries for A..J. Check all labels
        # as well: Qwen and Gemma need not share tokenization above ten options.
        for label, token_id in zip(self.layout.labels, self.layout.label_ids):
            if self.layout._enc('Answer: (' + label) != self.layout.answer + [token_id]:
                raise ValueError(f'Label boundary mismatch: {label}')
        self.header = layout == 'header'
        self.read_twice = read_twice
        self.cutoff = twice_max_tokens
        self.limit = max_row_tokens

    def compile(self, state, questions, *, training_extension=False):
        if not questions:
            raise ValueError('Request contains no questions')
        kinds = {k: q['type'] for k, q in questions.items()}
        adapted = training_questions(questions) if training_extension else questions
        rendered = [(key, *render_question(q)) for key, q in adapted.items()]
        texts = [text for _, text, _, _ in rendered] if self.header else None
        ctx = self.layout.context(state, texts)
        again = self.layout.again(state, texts) if self.read_twice else None
        pieces = [(key, keys, self.layout.question(text, options),
                   self.layout.question(text, options, again) if again else None)
                  for key, text, options, keys in rendered]
        once_tokens = len(ctx) + sum(len(once) for _, _, once, _ in pieces)
        fits = [twice is not None and len(ctx)+len(twice) <= self.limit
                for _, _, _, twice in pieces]
        whole = self.read_twice and all(fits) and (self.cutoff == 0 or once_tokens <= self.cutoff)
        rows = []
        for key, keys, once, twice in pieces:
            ids = ctx + (twice if whole else once)
            if len(ids) > self.limit:
                raise Unsupported(f'Untruncated prompt has {len(ids)} tokens; limit {self.limit}')
            rows.append(PromptRow(key, kinds[key], tuple(keys),
                                  tuple(self.layout.label_ids[:len(keys)]), tuple(ids), whole))
        return rows, dict(once_request_tokens=once_tokens, repeated=whole,
                          final_model_tokens=sum(len(row.input_ids) for row in rows),
                          max_row_tokens=max(len(row.input_ids) for row in rows),
                          question_count=len(rows), training_extension=training_extension)
