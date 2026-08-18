"""Approved M6.6A task inventory. Subject-line generation is intentionally absent."""

from opintel_qualification.tournament2_domain import (
    CORE_TASKS,
    AuthorityClass,
    TaskDefinition,
    TournamentTask,
)


def _definition(task: TournamentTask) -> TaskDefinition:
    wording = {
        TournamentTask.AUDIT_WORDING,
        TournamentTask.AUDIT_SUMMARIZATION,
        TournamentTask.DEMO_CONVERSATIONAL_WORDING,
        TournamentTask.DEMO_NARRATION_WORDING,
        TournamentTask.OUTREACH_WORDING,
        TournamentTask.VALIDATION_QUESTION_WORDING,
        TournamentTask.CALL_OPENING_WORDING,
    }
    return TaskDefinition(
        task=task,
        authority=AuthorityClass.WORDING_ONLY if task in wording else AuthorityClass.ADVISORY_ONLY,
        core_execution=task in CORE_TASKS,
        contract_version=f"m6.6a.{task.value}@1",
        input_schema_version=f"m6.6a.{task.value}.input@1",
        output_schema_version=f"m6.6a.{task.value}.output@1",
    )


TASK_DEFINITIONS = tuple(_definition(task) for task in TournamentTask)
TASK_DEFINITION_BY_CLASS = {item.task: item for item in TASK_DEFINITIONS}
