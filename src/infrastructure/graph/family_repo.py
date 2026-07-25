"""Family relationship graph repository - Neo4j operations for household structure."""

from uuid import UUID

from neo4j import AsyncDriver, AsyncTransaction
from neo4j._async.work.result import AsyncResult

from src.infrastructure.graph.models import ApplicantNode, FamilyMemberNode, HasDependentRel, HasSpouseRel


class FamilyGraphRepository:
    """Manage family relationships in Neo4j."""

    def __init__(self, driver: AsyncDriver):
        self.driver = driver

    async def create_applicant(self, applicant: ApplicantNode) -> None:
        """Create an :Applicant node."""
        async with self.driver.session() as session:
            await session.execute_write(
                self._create_applicant_tx, applicant
            )

    @staticmethod
    async def _create_applicant_tx(tx: AsyncTransaction, applicant: ApplicantNode) -> None:
        await tx.run(
            """
            MERGE (a:Applicant {id: $id})
            SET a += $props
            """,
            id=str(applicant.id),
            props=applicant.model_dump(exclude={"id"}),
        )

    async def add_dependent(
        self, applicant_id: UUID, member: FamilyMemberNode, rel: HasDependentRel | None = None
    ) -> None:
        """Add a :FamilyMember as a dependent of an :Applicant."""
        async with self.driver.session() as session:
            await session.execute_write(
                self._add_dependent_tx, applicant_id, member, rel
            )

    @staticmethod
    async def _add_dependent_tx(
        tx: AsyncTransaction,
        applicant_id: UUID,
        member: FamilyMemberNode,
        rel: HasDependentRel | None,
    ) -> None:
        member_id = member.id
        await tx.run(
            """
            MATCH (a:Applicant {id: $applicant_id})
            MERGE (m:FamilyMember {id: $member_id})
            SET m += $member_props
            MERGE (a)-[r:HAS_DEPENDENT]->(m)
            SET r += $rel_props
            """,
            applicant_id=str(applicant_id),
            member_id=str(member_id),
            member_props=member.model_dump(exclude={"id"}),
            rel_props=rel.model_dump() if rel else {},
        )

    async def add_spouse(
        self, applicant_id: UUID, spouse: FamilyMemberNode, rel: HasSpouseRel | None = None
    ) -> None:
        """Add a :FamilyMember as a spouse of an :Applicant."""
        async with self.driver.session() as session:
            await session.execute_write(
                self._add_spouse_tx, applicant_id, spouse, rel
            )

    @staticmethod
    async def _add_spouse_tx(
        tx: AsyncTransaction,
        applicant_id: UUID,
        spouse: FamilyMemberNode,
        rel: HasSpouseRel | None,
    ) -> None:
        spouse_id = spouse.id
        await tx.run(
            """
            MATCH (a:Applicant {id: $applicant_id})
            MERGE (s:FamilyMember {id: $spouse_id})
            SET s += $spouse_props
            MERGE (a)-[r:HAS_SPOUSE]->(s)
            SET r += $rel_props
            """,
            applicant_id=str(applicant_id),
            spouse_id=str(spouse_id),
            spouse_props=spouse.model_dump(exclude={"id"}),
            rel_props=rel.model_dump() if rel else {},
        )

    async def get_household(self, applicant_id: UUID) -> dict:
        """Return the full household structure for an applicant."""
        async with self.driver.session() as session:
            result = await session.execute_read(
                self._get_household_tx, applicant_id
            )
            return result

    @staticmethod
    async def _get_household_tx(
        tx: AsyncTransaction, applicant_id: UUID
    ) -> dict:
        cursor: AsyncResult = await tx.run(
            """
            MATCH (a:Applicant {id: $applicant_id})
            OPTIONAL MATCH (a)-[r:HAS_DEPENDENT|HAS_SPOUSE]->(m:FamilyMember)
            RETURN a AS applicant, collect(DISTINCT {
                member: properties(m),
                relationship: type(r),
                rel_props: properties(r)
            }) AS household
            """,
            applicant_id=str(applicant_id),
        )
        record = await cursor.single()
        if record is None:
            return {"applicant": None, "household": []}
        return {
            "applicant": dict(record["applicant"]),
            "household": record["household"],
        }

    async def get_dependents(self, applicant_id: UUID) -> list[dict]:
        """Return all dependents of an applicant."""
        async with self.driver.session() as session:
            result = await session.execute_read(
                self._get_dependents_tx, applicant_id
            )
            return result

    @staticmethod
    async def _get_dependents_tx(
        tx: AsyncTransaction, applicant_id: UUID
    ) -> list[dict]:
        cursor: AsyncResult = await tx.run(
            """
            MATCH (a:Applicant {id: $applicant_id})-[:HAS_DEPENDENT]->(m:FamilyMember)
            RETURN m AS member
            """,
            applicant_id=str(applicant_id),
        )
        return [dict(record) async for record in cursor]
