"""E2E 测试脚本 - 测试完整的申请流程"""
import requests
import json
from src.utils.emirates_id import luhn_check_digit

# 生成新的 Emirates ID
body = '78419959876543'
check = luhn_check_digit(body)
emirates_id = f'784-1995-9876543-{check}'
print(f"Generated Emirates ID: {emirates_id}")

# 1. 认证
print("\n=== Step 1: Authentication ===")
auth_response = requests.post(
    'http://localhost:8000/api/v1/auth/login',
    json={'emirates_id': emirates_id}
)
print(f"Status: {auth_response.status_code}")
auth_data = auth_response.json()
print(json.dumps(auth_data, indent=2))

applicant_id = auth_data['applicant_id']
application_id = auth_data['application_id']

# 2. Intake - 提供申请人信息
print("\n=== Step 2: Intake ===")
intake_response = requests.post(
    f'http://localhost:8000/api/v1/applications/{application_id}/chat',
    data={
        'text': 'I am divorced with 2 children. I work as an administrative assistant at Al Noor Trading earning 15000 AED monthly. I rent in Ajman.'
    }
)
print(f"Status: {intake_response.status_code}")
intake_data = intake_response.json()
print(f"Phase: {intake_data['phase']}")
print(f"Message: {intake_data['message'][:200]}...")

# 3. 检查数据库状态
print("\n=== Step 3: Check Database ===")
import asyncio
from sqlalchemy import select
from src.infrastructure.db.session import get_session_factory
from src.infrastructure.db.models.application import Application
from src.config import settings

async def check_db():
    factory = get_session_factory(settings)
    async with factory() as session:
        result = await session.execute(
            select(Application).where(Application.id == application_id)
        )
        app = result.scalar_one_or_none()
        if app:
            print(f"DB Phase: {app.current_phase}")
            print(f"DB Status: {app.status}")
            print(f"DB Decision: {app.decision}")
            print(f"DB State Snapshot: {app.state_snapshot is not None}")
        else:
            print("Application not found in DB")

asyncio.run(check_db())

print("\n=== Test Complete ===")
