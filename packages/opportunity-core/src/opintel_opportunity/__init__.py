"""M2 opportunity engine public package."""

from opintel_opportunity.application import OpportunityApplicationService
from opintel_opportunity.workflow import OpportunityWorkflowRunner

__all__ = ["OpportunityApplicationService", "OpportunityWorkflowRunner"]
