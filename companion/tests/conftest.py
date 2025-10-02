"""
Pytest configuration file for the AI Companion System.
Includes fixtures for isolated database testing, mock API clients, and sample user data.
"""
import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import os
from typing import Generator, Dict, Any
from datetime import datetime

# Import application modules
from companion.gateway.database import DatabaseManager
from companion.gateway.config import Settings
from companion.gateway.services.groq_client import GroqClient
from companion.gateway.services.chutes_client import ChutesClient
from companion.gateway.services.personality_engine import PersonalityEngine
from companion.gateway.services.memory_manager import MemoryManager
from companion.gateway.services.user_service import UserService
from companion.gateway.services.letta_service import LettaService
from companion.gateway.models.personality import PersonalitySnapshot, PADState, BigFiveTraits
from companion.gateway.models.user import UserProfile


# Override settings for testing
@pytest.fixture(scope="session")
def test_settings():
    """Override settings for testing."""
    os.environ["ENVIRONMENT"] = "test"
    os.environ["DATABASE_URL"] = os.getenv("TEST_DATABASE_URL", "postgresql://test:test@localhost:5432/test_db")
    os.environ["GROQ_API_KEY"] = "test_groq_key"
    os.environ["CHUTES_API_KEY"] = "test_chutes_key"
    os.environ["GEMINI_API_KEY"] = "test_gemini_key"
    os.environ["LETTA_SERVER_URL"] = "http://test-letta:8283"
    return Settings()



@pytest.fixture
async def test_db(test_settings) -> Generator[DatabaseManager, None, None]:
    """Create an isolated database for testing."""
    db = DatabaseManager(test_settings.database_url)
    await db.initialize()

    # Create all tables (in a real app, you'd run migrations)
    # For this test setup, we'll create a simple table for testing
    async with db.pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS test_users (
                id SERIAL PRIMARY KEY,
                user_id VARCHAR(100) NOT NULL UNIQUE,
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
        """)

    yield db

    # Cleanup
    async with db.pool.acquire() as conn:
        await conn.execute("DROP TABLE IF EXISTS test_users CASCADE")
    await db.close()


@pytest.fixture
async def mock_groq_client():
    """Mock Groq client for testing."""
    mock_client = AsyncMock(spec=GroqClient)
    mock_client.score_importance = AsyncMock(return_value=0.7)
    mock_client.detect_threat = AsyncMock(return_value={"threat_detected": False, "confidence": 0.1})
    mock_client.health_check = AsyncMock(return_value=True)
    return mock_client


@pytest.fixture
async def mock_chutes_client():
    """Mock Chutes client for testing."""
    mock_client = AsyncMock(spec=ChutesClient)
    mock_client.chat_completion = AsyncMock(return_value={"choices": [{"message": {"content": "Test response"}}]})
    mock_client.health_check = AsyncMock(return_value=True)
    return mock_client


@pytest.fixture
async def mock_letta_service():
    """Mock Letta service for testing."""
    mock_service = AsyncMock(spec=LettaService)
    mock_service.send_message = AsyncMock(return_value="Mock response from Letta")
    mock_service.create_agent = AsyncMock(return_value="test_agent_id")
    mock_service.get_agent = AsyncMock(return_value={"id": "test_agent_id"})
    return mock_service


@pytest.fixture
async def sample_user_profile():
    """Create a sample user profile for testing."""
    return UserProfile(
        user_id="test_user_123",
        discord_username="test_user",
        status="active",
        initialization_completed=True,
        personality_initialized=True,
        total_interactions=5,
        last_active=datetime.utcnow()
    )


@pytest.fixture
async def sample_personality_snapshot():
    """Create a sample personality snapshot for testing."""
    return PersonalitySnapshot(
        user_id="test_user_123",
        big_five=BigFiveTraits(
            openness=0.6,
            conscientiousness=0.7,
            extraversion=0.5,
            agreeableness=0.8,
            neuroticism=0.3
        ),
        current_pad=PADState(
            pleasure=0.2,
            arousal=0.1,
            dominance=0.3,
            emotion_label="content"
        ),
        pad_baseline=PADState(
            pleasure=0.0,
            arousal=0.0,
            dominance=0.0,
            emotion_label="neutral"
        ),
        active_quirks=[],
        psychological_needs=[]
    )


@pytest.fixture
async def mock_memory_manager():
    """Mock memory manager for testing."""
    mock_manager = AsyncMock(spec=MemoryManager)
    mock_manager.store_memory = AsyncMock(return_value="test_memory_id")
    mock_manager.search_memories = AsyncMock(return_value=[])
    mock_manager.search_with_mmr = AsyncMock(return_value=[])
    mock_manager.get_memory_by_id = AsyncMock(return_value=None)
    mock_manager.delete_memory = AsyncMock(return_value=True)
    mock_manager.health_check = AsyncMock(return_value=True)
    return mock_manager


@pytest.fixture
async def mock_personality_engine(mock_memory_manager):
    """Mock personality engine for testing."""
    mock_engine = AsyncMock(spec=PersonalityEngine)
    mock_engine.get_personality_snapshot = AsyncMock(return_value=None)
    mock_engine.update_pad_state = AsyncMock(return_value=PADState(pleasure=0.0, arousal=0.0, dominance=0.0))
    mock_engine.get_current_pad_state = AsyncMock(return_value=PADState(pleasure=0.0, arousal=0.0, dominance=0.0))
    mock_engine.health_check = AsyncMock(return_value=True)
    return mock_engine


@pytest.fixture
async def clean_test_user(test_db):
    """Create a clean test user with proper isolation."""
    test_user_id = "test_user_isolated_12345"
    
    # Clean any existing test data
    await test_db.execute("DELETE FROM personality_state WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM interactions WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM quirks WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM needs WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM user_profiles WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM memory_conflicts WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM security_incidents WHERE user_id = $1;", test_user_id)
    
    yield test_user_id
    
    # Cleanup after test
    await test_db.execute("DELETE FROM personality_state WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM interactions WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM quirks WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM needs WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM user_profiles WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM memory_conflicts WHERE user_id = $1;", test_user_id)
    await test_db.execute("DELETE FROM security_incidents WHERE user_id = $1;", test_user_id)


@pytest.fixture
def mock_discord_interaction():
    """Mock Discord interaction object for command testing."""
    interaction = AsyncMock()
    interaction.user = MagicMock()
    interaction.user.id = 123456789
    interaction.user.name = "test_user"
    interaction.response = AsyncMock()
    interaction.response.send_message = AsyncMock()
    interaction.response.defer = AsyncMock()
    return interaction


@pytest.fixture
def mock_discord_bot():
    """Mock Discord bot for testing."""
    bot = MagicMock()
    bot.user = MagicMock()
    bot.user.id = 987654321
    return bot


@pytest.fixture
async def test_services_container(test_db, mock_groq_client, mock_chutes_client,
                                 mock_letta_service, mock_memory_manager, mock_personality_engine):
    """Create a test service container with mocked services."""
    from companion.gateway.main import ServiceContainer

    container = ServiceContainer()
    container.db = test_db
    container.groq = mock_groq_client
    container.chutes = mock_chutes_client
    container.letta = mock_letta_service
    container.memory = mock_memory_manager
    container.personality = mock_personality_engine

    # Mock services are injected via the container above
    # No need for set_instance calls - services are managed by DI

    yield container

    # Cleanup is handled by pytest fixture teardown
    # No static instances to reset - services are scoped to the container


# Configuration for pytest
def pytest_configure(config):
    """Pytest configuration hook."""
    config.addinivalue_line(
        "markers", "integration: mark test as integration test"
    )
    config.addinivalue_line(
        "markers", "unit: mark test as unit test"
    )
    config.addinivalue_line(
        "markers", "slow: mark test as slow running"
    )


def pytest_runtest_setup(item):
    """Called for each test method."""
    # Apply custom markers or setup logic here if needed
    pass


# Custom pytest hooks if needed
@pytest.hookimpl(hookwrapper=True)
def pytest_runtest_protocol(item, nextitem):
    """Implement custom test protocol if needed."""
    # This is a hook wrapper, allowing you to run code before and after tests
    # For example, to time tests or to collect additional metrics
    outcome = yield
    return outcome