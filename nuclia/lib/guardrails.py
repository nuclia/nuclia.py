from datetime import datetime
from enum import Enum
from typing import Annotated, Optional
from uuid import UUID

from pydantic import (
    AfterValidator,
    BaseModel,
    ConfigDict,
    Field,
    model_validator,
)
from typing_extensions import Self

MAX_GUARDRAIL_POLICY_NAME_LENGTH = 200
MAX_GUARDRAIL_POLICY_DESCRIPTION_LENGTH = 2_000
MAX_GUARDRAIL_POLICY_INSTRUCTION_LENGTH = 20_000
MAX_GUARDRAIL_POLICY_QUERY_LENGTH = 1_000
MAX_GUARDRAIL_CONTENT_LENGTH = 20_000


def validate_not_blank(value: str) -> str:
    if not value.strip():
        raise ValueError("must not be blank")
    return value


NonBlankString = Annotated[str, AfterValidator(validate_not_blank)]


class GuardrailTarget(str, Enum):
    QUERY = "QUERY"


class GuardrailPolicyFields(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: NonBlankString = Field(
        min_length=1,
        max_length=MAX_GUARDRAIL_POLICY_NAME_LENGTH,
    )
    description: Optional[str] = Field(
        default=None,
        max_length=MAX_GUARDRAIL_POLICY_DESCRIPTION_LENGTH,
    )
    instruction: NonBlankString = Field(
        min_length=1,
        max_length=MAX_GUARDRAIL_POLICY_INSTRUCTION_LENGTH,
    )
    query: NonBlankString = Field(
        min_length=1,
        max_length=MAX_GUARDRAIL_POLICY_QUERY_LENGTH,
    )
    target: GuardrailTarget = GuardrailTarget.QUERY
    enabled: bool = False
    blocking: bool = Field(
        default=True,
        description=(
            "Whether evaluation failures block generation. Policy violations always "
            "block when the policy is enabled."
        ),
    )


class CreateGuardrailPolicy(GuardrailPolicyFields):
    pass


class PatchGuardrailPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Optional[NonBlankString] = Field(
        default=None,
        min_length=1,
        max_length=MAX_GUARDRAIL_POLICY_NAME_LENGTH,
    )
    description: Optional[str] = Field(
        default=None,
        max_length=MAX_GUARDRAIL_POLICY_DESCRIPTION_LENGTH,
    )
    instruction: Optional[NonBlankString] = Field(
        default=None,
        min_length=1,
        max_length=MAX_GUARDRAIL_POLICY_INSTRUCTION_LENGTH,
    )
    query: Optional[NonBlankString] = Field(
        default=None,
        min_length=1,
        max_length=MAX_GUARDRAIL_POLICY_QUERY_LENGTH,
    )
    target: Optional[GuardrailTarget] = None
    enabled: Optional[bool] = None
    blocking: Optional[bool] = Field(
        default=None,
        description=(
            "Whether evaluation failures block generation. Policy violations always "
            "block when the policy is enabled."
        ),
    )

    @model_validator(mode="after")
    def validate_non_nullable_fields(self) -> Self:
        for field_name in (
            "name",
            "instruction",
            "query",
            "target",
            "enabled",
            "blocking",
        ):
            if (
                field_name in self.model_fields_set
                and getattr(self, field_name) is None
            ):
                raise ValueError(f"{field_name} cannot be null")
        return self


class GuardrailPolicy(GuardrailPolicyFields):
    id: UUID
    account_id: str
    created_at: datetime
    updated_at: datetime


class InlineGuardrailPolicy(BaseModel):
    model_config = ConfigDict(extra="forbid")

    instruction: NonBlankString = Field(
        min_length=1,
        max_length=MAX_GUARDRAIL_POLICY_INSTRUCTION_LENGTH,
    )
    query: NonBlankString = Field(
        min_length=1,
        max_length=MAX_GUARDRAIL_POLICY_QUERY_LENGTH,
    )
    target: GuardrailTarget = GuardrailTarget.QUERY


class GuardrailRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: NonBlankString = Field(
        min_length=1,
        max_length=MAX_GUARDRAIL_CONTENT_LENGTH,
    )
    policy_id: Optional[str] = None
    policy: Optional[InlineGuardrailPolicy] = None

    @model_validator(mode="after")
    def validate_policy_source(self) -> Self:
        if (self.policy_id is None) == (self.policy is None):
            raise ValueError("Exactly one of policy_id and policy must be provided")
        return self


class GuardrailResponse(BaseModel):
    flagged: bool
    score: float
    threshold: float
    policy_id: Optional[str] = None
