from unittest.mock import patch

from experiments.no_values.model.agents import (
    NoValuesEvolutorAgent,
    NoValuesProfilerAgent,
    NoValuesSelectorAgent,
)
from model.agents.evolutor_agent import EvolutorAgent
from model.agents.profiler_agent import ProfilerAgent
from model.agents.selector_agent import CandidateSelectorAgent


def test_profiler_redacts_incoming_values() -> None:
    agent = NoValuesProfilerAgent(llm_client=None)
    schema = {"tables": {"incoming": {"columns": {}}}}

    with patch.object(ProfilerAgent, "__call__", return_value={}) as call:
        agent(incoming_schema=schema, incoming_values=[{"secret": "value"}])

    assert call.call_args.kwargs["incoming_values"] == []


def test_selector_redacts_both_value_collections() -> None:
    agent = NoValuesSelectorAgent()

    with patch.object(CandidateSelectorAgent, "__call__", return_value={}) as call:
        agent(
            incoming_schema={"tables": {}},
            incoming_values=[{"secret": "incoming"}],
            existing_schema={"tables": {}},
            existing_values={"existing": [{"secret": "stored"}]},
        )

    assert call.call_args.kwargs["incoming_values"] == []
    assert call.call_args.kwargs["existing_values"] == {}


def test_evolutor_redacts_values_but_retains_profiles() -> None:
    agent = NoValuesEvolutorAgent(llm_client=None)
    incoming_profile = {"table": {"entity": "Incoming"}}
    existing_profiles = {"tables": {"existing": {}}}

    with patch.object(EvolutorAgent, "__call__", return_value={}) as call:
        agent(
            incoming_schema={"tables": {}},
            incoming_values=[{"secret": "incoming"}],
            incoming_profile=incoming_profile,
            existing_schema={"tables": {}},
            existing_values={"existing": [{"secret": "stored"}]},
            existing_profiles=existing_profiles,
            existing_constraints={"constraints": {}},
            selection_result={},
        )

    assert call.call_args.kwargs["incoming_values"] == []
    assert call.call_args.kwargs["existing_values"] == {}
    assert call.call_args.kwargs["incoming_profile"] is incoming_profile
    assert call.call_args.kwargs["existing_profiles"] is existing_profiles
