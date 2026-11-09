"""Service-wide text input profiles; model execution and readout are unchanged."""
from dataclasses import dataclass
import os

from .flex_prompt import FlexPromptCompiler


@dataclass(frozen=True)
class InputProfile:
    name: str
    read_twice: bool
    single_question_budget: int
    multiple_question_budget: int
    revision: str = "1"


PROFILES = {
    "flexdm": InputProfile("flexdm", True, 3000, 3000),
    "u03": InputProfile("u03", True, 12000, 3000),
    "single-pass": InputProfile("single-pass", False, 3000, 3000),
}


class ProfilePromptCompiler:
    """Choose a budget using the complete request, before splitting model rows."""

    def __init__(self, tokenizer, profile="flexdm", *, max_row_tokens=65535):
        if profile not in PROFILES:
            raise ValueError(f"Unknown input profile {profile!r}; choose {', '.join(PROFILES)}")
        self.profile = PROFILES[profile]
        self.compilers = {
            budget: FlexPromptCompiler(
                tokenizer, layout="header", read_twice=self.profile.read_twice,
                twice_max_tokens=budget, max_row_tokens=max_row_tokens,
            )
            for budget in {self.profile.single_question_budget, self.profile.multiple_question_budget}
        }
        self.limit = max_row_tokens

    def compile(self, state, questions, *, training_extension=False):
        if not isinstance(questions, dict) or not questions:
            raise ValueError("Pass the complete nonempty question map before splitting rows")
        profile = self.profile
        budget = (profile.single_question_budget if len(questions) == 1
                  else profile.multiple_question_budget)
        rows, identity = self.compilers[budget].compile(
            state, questions, training_extension=training_extension,
        )
        return rows, dict(identity, input_profile=profile.name,
                         input_profile_revision=profile.revision, layout="header",
                         read_twice_enabled=profile.read_twice,
                         repeat_budget=budget if profile.read_twice else None,
                         budget_basis="whole original request before per-question splitting",
                         configured_max_row_tokens=self.limit)


def compiler_from_env(tokenizer):
    return ProfilePromptCompiler(tokenizer, os.environ.get("PICCOLO_INPUT_PROFILE", "flexdm"))
