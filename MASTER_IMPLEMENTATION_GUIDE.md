Here is the complete, unified technical blueprint, combining the architectural overview of `deployment-plan.md` with the deep implementation details of `MASTER_IMPLEMENTATION_GUIDE.md`. This master document serves as the single source of truth for building the AI Companion system.

---

# 🚀 AI Companion System: Master Implementation Guide & Technical Blueprint

## Executive Summary

**Goal:** Deploy a human-like AI companion with evolving personality, persistent memory, and proactive engagement capabilities, supporting **multiple personalized users** via Discord. Embedding services are migrated to **Gemini** for cost efficiency while maintaining the 1536-dimensional vector space.

**Timeline:** 2-3 days for MVP, 1 week for full system
**Cost:** ~$20-35/month (Hetzner VPS + Chutes.ai API + Groq API)
**Complexity:** Intermediate (Docker experience required)

---

## 🎯 Multi-User Personalized Companions: Frictionless Solution

### Recommended Approach: **User-Scoped Multi-Tenancy**

**Core Concept:** **All infrastructure stays the same**, but data is scoped by `user_id`. Each Discord account gets its own personality, memories, and conversational history while sharing the same services (Postgres, Qdrant, Redis, Gateway).

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    DISCORD (User Interface)                      │
│                  Discord Bot + Slash Commands                    │
└────────────────────┬────────────────────────────────────────────┘
                     │
                     │ Discord.py WebSocket
                     │
┌────────────────────▼────────────────────────────────────────────┐
│               GATEWAY API (FastAPI)                              │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 1. Proactive Conversation Manager (User-Scoped)           │  │
│  │    - Inner Thoughts Generator                            │  │
│  │    - Timing Calculator (when to initiate)                │  │
│  │    - Context Monitor                                     │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 2. Personality Engine (User-Scoped)                      │  │
│  │    - Big Five Traits (FIXED)                             │  │
│  │    - PAD State (DYNAMIC)                                 │  │
│  │    - OCC Appraisal Logic                                 │  │
│  │    - PAD Baseline Drift (Long-term evolution)            │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 3. Letta Integration (Core Agent Logic)                  │  │
│  │    - Agent Routing & Creation (Per User)                 │  │
│  │    - Message Processing & LLM Call Delegation            │  │
│  │    - Semantic Injection Detection (Groq)                 │  │
│  └──────────────────────────────────────────────────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │ 4. Memory Orchestrator (User-Scoped)                     │  │
│  │    - Episodic → Semantic consolidation                   │  │
│  │    - MMR retrieval (Redis cached)                        │  │
│  │    - Importance scoring (via Groq) & recency weighting   │  │
│  └──────────────────────────────────────────────────────────┘  │
└────────────────────┬────────────────────────────────────────────┘
                     │
        ┌────────────┴──────────────┐
        │                           │
┌───────▼──────────┐    ┌───────────▼──────────┐
│  LETTA SERVER    │    │  EMBEDDING SERVICE   │
│   (Multi-Agent)  │    │   (gemini-emb-001)   │
│                  │    │   FastAPI wrapper    │
│ - Agent state    │    └───────────┬──────────┘
│ - Memory blocks  │                │
│ - Tool calls     │                │
└───────┬──────────┘                │
        │                           │
        │         ┌─────────────────┴────────────┐
        │         │                              │
┌───────▼─────────▼────┐         ┌──────────────▼──────┐
│   POSTGRES + PG      │         │      QDRANT         │
│     VECTOR           │         │   (Vector Store)    │
│                      │         │                     │
│ - PAD state (User-ID)│         │ - Episodic memory (User-ID)│
│ - Personality traits │         │ - Semantic memory (User-ID)│
│ - Quirks & needs     │         │ - RAG documents     │
│ - Interactions log   │         │ - Hybrid search     │
│ - Conflict tracker   │         │                     │
│ - User Profiles      │         │                     │
│ - Security Incidents │         │                     │
└──────────────────────┘         └─────────────────────┘
                                          │
┌─────────────────────────────────────────▼─────────────┐
│              REDIS CLUSTER                             │
│  - Hot vector cache (recent conversations)             │
│  - Embedding cache (avoid recomputation)               │
│  - Proactive trigger state                             │
│  - Session management                                  │
│  - Security Offender Tracking                          │
└────────────────────────────────────────────────────────┘

┌────────────────────────────────────────────────────────┐
│                  CADDY REVERSE PROXY                    │
│  - Automatic HTTPS (Let's Encrypt)                     │
│  - Rate limiting                                       │
│  - Load balancing (if needed)                          │
└────────────────────────────────────────────────────────┘
```

---

## 📦 Technology Stack & Justification

### Core Infrastructure

| Component | Technology | Version | Why This Choice |
|-----------|-----------|---------|-----------------|
| **LLM Provider (Chat)** | Chutes.ai | API | Decentralized, cost-effective, good model selection |
| **LLM Provider (Scoring)** | Groq | API | Extremely low latency for real-time importance scoring |
| **Primary LLM** | Qwen3-80B-A3B-Instruct | Available | Best balance of capability, cost, and conversational quality |
| **Scoring LLM** | Llama-4-Maverick | Available | High speed, reliable numerical output for scoring |
| **Embedding Model** | gemini-embedding-001 | Available | Cost-effective, supports 1536 dimensions |
| **Agent Framework** | Letta (MemGPT) | 0.6.8 | Only mature stateful agent framework with built-in memory management |
| **API Gateway** | FastAPI | 0.118.0 | Async-first, excellent performance, easy testing |
| **Interface** | Discord | discord.py 2.6.3 | Native mobile/desktop, free, better UX than web UI |
| **Reverse Proxy** | Caddy | 2.10.2+ | Automatic HTTPS, simpler config than Nginx |
| **Database** | PostgreSQL + pgvector | 16.4 + 0.8.1 | ACID compliance, vector support, mature ecosystem |
| **Vector Store** | Qdrant | 1.12.1 | Best hybrid search, production-ready, excellent Python client |
| **Cache Layer** | Redis | 7.4.7+ | Industry standard, fast, excellent for hot data |
| **Embedding Service** | Custom FastAPI | - | Wrapper around Gemini for consistency |
| **Container Runtime** | Docker + Compose | 27+ | Reproducible deployments, easy management |
| **Hosting** | Hetzner VPS | CX32 | Affordable (€12/mo), reliable, good specs |

### Python Dependencies

```python
# requirements.txt
fastapi==0.118.0
uvicorn[standard]==0.37.0
discord.py==2.6.3
letta-client==0.6.8
asyncpg==0.30.0
redis[hiredis]==5.2.0
qdrant-client==1.12.1
sqlalchemy[asyncio]==2.0.43
pydantic==2.11.9
httpx==0.28.1
numpy==2.3.3
google-generativeai==0.8.3 # NEW: For Gemini Embeddings
apscheduler==3.11.0  # For nightly reflection
python-dotenv==1.1.1
groq==0.11.0
```

---

## 📁 Complete Project Structure

```
companion/
├── docker-compose.yml
├── .env.example
├── Caddyfile
├── migrations/
│   ├── 001_init.sql
│   ├── 002_personhood.sql
│   ├── 003_memory_conflicts.sql
│   ├── 004_user_profiles.sql
│   └── 005_security.sql
│
├── gateway/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── main.py                      # FastAPI app entry (UPDATED for Groq init)
│   ├── config.py                    # Configuration management (UPDATED for Gemini settings)
│   │
│   ├── models/
│   │   ├── personality.py           # BigFive + PAD classes
│   │   ├── memory.py                # Memory data models
│   │   └── interaction.py           # Interaction models
│   │
│   ├── services/
│   │   ├── chutes_client.py         # Chutes.ai API wrapper
│   │   ├── groq_client.py           # Groq API wrapper
│   │   ├── letta_service.py         # Letta Integration
│   │   ├── embedding_client.py      # Embedding service client (UPDATED for Gemini query)
│   │   ├── memory_manager.py        # Memory CRUD operations (UPDATED for query embedding)
│   │   └── personality_engine.py    # Personality state management
│   │
│   ├── agents/
│   │   ├── proactive_manager.py     # Inner thoughts + timing
│   │   ├── reflection.py            # Nightly consolidation
│   │   └── appraisal.py             # OCC emotion logic
│   │
│   ├── routers/
│   │   ├── chat.py                  # Chat endpoints
│   │   ├── memory.py                # Memory management endpoints
│   │   ├── personality.py           # Personality inspection
│   │   └── admin.py                 # Admin tools
│   │
│   └── utils/
│       ├── mmr.py                   # Maximal Marginal Relevance
│       ├── importance_scorer.py     # LLM Importance Scorer
│       └── scheduler.py             # APScheduler jobs
│
├── discord_bot/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── bot.py                       # Main Discord bot
│   ├── commands.py                  # Slash commands
│   └── utils.py                     # Helper functions (DiscordSender)
│
├── embedding_service/
│   ├── Dockerfile
│   ├── requirements.txt             # UPDATED for google-generativeai
│   └── main.py                      # Gemini Embedding Service (REPLACED)
│
├── scripts/
│   ├── bootstrap_letta.py           # (DEPRECATED)
│   ├── init_qdrant.py               # Create Qdrant collections
│   ├── backup.sh                    # Backup script
│   └── monitor.sh                   # Health monitoring
│
└── docs/
    ├── API.md                       # API documentation
    ├── PERSONALITY.md               # Personality configuration guide
    └── RESEARCH.md                  # Research notes
```

---

## 🗄️ Database Schemas

### PostgreSQL Tables

```sql
-- migrations/001_init.sql: Core tables
CREATE EXTENSION IF NOT EXISTS vector;

-- Personality state
CREATE TABLE personality_state (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Multi-User Scoping
    user_id VARCHAR(100) NOT NULL DEFAULT 'default_user',
    
    -- Big Five (OCEAN) traits (0.0 to 1.0)
    openness FLOAT NOT NULL CHECK (openness BETWEEN 0 AND 1),
    conscientiousness FLOAT NOT NULL CHECK (conscientiousness BETWEEN 0 AND 1),
    extraversion FLOAT NOT NULL CHECK (extraversion BETWEEN 0 AND 1),
    agreeableness FLOAT NOT NULL CHECK (agreeableness BETWEEN 0 AND 1),
    neuroticism FLOAT NOT NULL CHECK (neuroticism BETWEEN 0 AND 1),
    
    -- PAD emotional state (-1.0 to 1.0)
    pleasure FLOAT NOT NULL CHECK (pleasure BETWEEN -1 AND 1),
    arousal FLOAT NOT NULL CHECK (arousal BETWEEN -1 AND 1),
    dominance FLOAT NOT NULL CHECK (dominance BETWEEN -1 AND 1),
    
    -- Computed emotion label
    emotion_label VARCHAR(50),
    
    -- Version tracking
    is_current BOOLEAN DEFAULT TRUE,
    
    -- PAD BASELINE (NEW)
    pad_baseline JSONB -- Long-term PAD baseline that drifts over time.
);

COMMENT ON COLUMN personality_state.pad_baseline IS 
'Long-term PAD baseline that drifts over time. Current PAD state fluctuates around this baseline.';

COMMENT ON COLUMN personality_state.openness IS 
'Big Five trait - FIXED at initialization, never changes';
COMMENT ON COLUMN personality_state.conscientiousness IS 
'Big Five trait - FIXED at initialization, never changes';
COMMENT ON COLUMN personality_state.extraversion IS 
'Big Five trait - FIXED at initialization, never changes';
COMMENT ON COLUMN personality_state.agreeableness IS 
'Big Five trait - FIXED at initialization, never changes';
COMMENT ON COLUMN personality_state.neuroticism IS 
'Big Five trait - FIXED at initialization, never changes';

-- UPDATED INDEX FOR USER SCOPING
DROP INDEX IF EXISTS idx_personality_current;
CREATE INDEX idx_personality_current ON personality_state(user_id, is_current) WHERE is_current = TRUE;
CREATE INDEX idx_personality_timestamp ON personality_state(timestamp DESC);

-- Interaction log (for analysis)
CREATE TABLE interactions (
    id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Multi-User Scoping (CRITICAL FIX)
    user_id VARCHAR(100) NOT NULL DEFAULT 'default_user',
    
    -- Message content
    user_message TEXT NOT NULL,
    assistant_response TEXT NOT NULL,
    
    -- Context at time of interaction
    personality_snapshot_id INT REFERENCES personality_state(id),
    pad_before JSONB,  -- {pleasure, arousal, dominance}
    pad_after JSONB,
    
    -- Proactive metadata
    was_proactive BOOLEAN DEFAULT FALSE,
    proactive_score FLOAT,
    proactive_reason TEXT,
    
    -- Memory retrieval
    memories_retrieved INT,
    memory_ids TEXT[],
    
    -- Performance metrics
    response_latency_ms INT,
    tokens_used INT,
    model_used VARCHAR(100)
);

CREATE INDEX idx_interactions_timestamp ON interactions(timestamp DESC);
CREATE INDEX idx_interactions_proactive ON interactions(was_proactive) WHERE was_proactive = TRUE;
-- ADDED INDEX FOR USER SCOPING
CREATE INDEX idx_interactions_user_timestamp ON interactions(user_id, timestamp DESC);

-- migrations/002_personhood.sql: Quirks and needs
CREATE TABLE quirks (
    id SERIAL PRIMARY KEY,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Multi-User Scoping
    user_id VARCHAR(100) NOT NULL DEFAULT 'default_user',
    
    quirk_type VARCHAR(50) NOT NULL,  -- 'speech_pattern', 'behavior', 'preference'
    description TEXT NOT NULL,
    strength FLOAT DEFAULT 0.5 CHECK (strength BETWEEN 0 AND 1),
    
    -- Evolution tracking
    times_expressed INT DEFAULT 0,
    last_expressed TIMESTAMPTZ,
    
    is_active BOOLEAN DEFAULT TRUE
);

CREATE INDEX idx_quirks_active ON quirks(is_active) WHERE is_active = TRUE;
-- ADDED INDEX FOR USER SCOPING
CREATE INDEX idx_quirks_user ON quirks(user_id, is_active) WHERE is_active = TRUE;

CREATE TABLE needs (
    id SERIAL PRIMARY KEY,
    
    -- Multi-User Scoping
    user_id VARCHAR(100) NOT NULL DEFAULT 'default_user',
    
    need_type VARCHAR(50) NOT NULL,  -- 'social', 'intellectual', 'creative', 'rest'
    current_level FLOAT DEFAULT 0.5 CHECK (current_level BETWEEN 0 AND 1),
    baseline FLOAT DEFAULT 0.5,
    decay_rate FLOAT DEFAULT 0.005,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Satisfaction tracking
    last_satisfied TIMESTAMPTZ,
    satisfaction_count INT DEFAULT 0
);

-- ADDED INDEX FOR USER SCOPING
CREATE UNIQUE INDEX idx_needs_user_type ON needs(user_id, need_type);

-- migrations/003_memory_conflicts.sql: Conflict detection
CREATE TABLE memory_conflicts (
    id SERIAL PRIMARY KEY,
    detected_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    memory_id_1 TEXT NOT NULL,  -- Qdrant point ID
    memory_id_2 TEXT NOT NULL,
    
    conflict_type VARCHAR(50),  -- 'contradiction', 'inconsistency', 'outdated'
    description TEXT,
    confidence FLOAT CHECK (confidence BETWEEN 0 AND 1),
    
    resolution_status VARCHAR(20) DEFAULT 'pending',  -- 'pending', 'resolved', 'ignored'
    resolved_at TIMESTAMPTZ,
    resolution_note TEXT
);

CREATE INDEX idx_conflicts_pending ON memory_conflicts(resolution_status) WHERE resolution_status = 'pending';

-- migrations/004_user_profiles.sql: User management
CREATE TABLE user_profiles (
    user_id VARCHAR(100) PRIMARY KEY,
    username VARCHAR(100) NOT NULL,
    letta_agent_id VARCHAR(100) UNIQUE NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_active TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    
    -- Optional: User preferences
    preferred_personality_profile VARCHAR(50) DEFAULT 'curious_companion',
    timezone VARCHAR(50) DEFAULT 'Asia/Karachi',
    
    -- Stats
    total_interactions INT DEFAULT 0,
    total_proactive_initiations INT DEFAULT 0
);

CREATE INDEX idx_user_profiles_last_active ON user_profiles(last_active DESC);

-- migrations/005_security.sql: Security Incidents
CREATE TABLE security_incidents (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(100) NOT NULL,
    message TEXT NOT NULL,
    threat_type VARCHAR(50),
    confidence FLOAT,
    response TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_security_user ON security_incidents(user_id, timestamp DESC);
CREATE INDEX idx_security_threats ON security_incidents(threat_type) WHERE confidence > 0.6;
```

### Qdrant Collections (Payload Scoping)

```python
# Qdrant schema configuration
QDRANT_COLLECTIONS = {
    "episodic_memory": {
        "vectors": {
            "size": 1536,  # Gemini with output_dimensionality=1536
            "distance": "Cosine"
        },
        "payload_schema": {
            "content": "text",
            "timestamp": "datetime",
            "importance": "float",
            "recency_score": "float",
            "emotion_context": "keyword",
            "speaker": "keyword",
            "conversation_id": "keyword",
            "user_id": "keyword",
            "metadata": "json"
        }
    },
    "semantic_memory": {
        "vectors": {
            "size": 1536,
            "distance": "Cosine"
        },
        "payload_schema": {
            "content": "text",
            "memory_type": "keyword",
            "confidence": "float",
            "created_at": "datetime",
            "last_accessed": "datetime",
            "access_count": "integer",
            "user_id": "keyword",
            "source_episodic_ids": "keyword[]"
        }
    },
    "documents": {
        "vectors": {
            "size": 1536,
            "distance": "Cosine"
        },
        "payload_schema": {
            "content": "text",
            "chunk_index": "integer",
            "document_name": "keyword",
            "document_type": "keyword",
            "uploaded_at": "datetime"
        }
    }
}
```

---

## 🎨 Personality Evolution Boundaries

### What Actually Evolves vs What Stays Fixed

**FIXED (Set at initialization, never changes):**
- **Big Five personality traits (OCEAN)**
- These represent stable dispositional tendencies

**DYNAMIC (Changes through interactions):**
- **PAD emotional state** (short-term): Updates after each interaction
- **PAD baseline** (long-term): Drifts slowly (~±0.01/night) based on recent emotional patterns
- **Quirks**: Emerge from behavioral patterns, strengthen with use, fade without
- **Needs**: Decay and get satisfied based on interactions
- **Memories**: Accumulate, consolidate, and shape understanding of user

---

## 📋 Data Models (Pydantic Classes)

### `gateway/models/personality.py`

```python
from pydantic import BaseModel, Field, validator
from typing import Dict, Optional, List
from datetime import datetime
from enum import Enum

class BigFiveTraits(BaseModel):
    """Big Five personality traits (OCEAN) - FIXED at initialization"""
    openness: float = Field(..., ge=0.0, le=1.0, description="Openness to experience")
    conscientiousness: float = Field(..., ge=0.0, le=1.0, description="Conscientiousness")
    extraversion: float = Field(..., ge=0.0, le=1.0, description="Extraversion")
    agreeableness: float = Field(..., ge=0.0, le=1.0, description="Agreeableness")
    neuroticism: float = Field(..., ge=0.0, le=1.0, description="Neuroticism")

class PADState(BaseModel):
    """PAD emotional state - DYNAMIC, changes with interactions"""
    pleasure: float = Field(..., ge=-1.0, le=1.0, description="Pleasure dimension")
    arousal: float = Field(..., ge=-1.0, le=1.0, description="Arousal dimension") 
    dominance: float = Field(..., ge=-1.0, le=1.0, description="Dominance dimension")
    
    def to_dict(self) -> Dict[str, float]:
        return {"pleasure": self.pleasure, "arousal": self.arousal, "dominance": self.dominance}

class PADBaseline(BaseModel):
    """Long-term PAD baseline that drifts slowly over time"""
    pleasure: float = Field(default=0.0, ge=-1.0, le=1.0)
    arousal: float = Field(default=0.0, ge=-1.0, le=1.0)
    dominance: float = Field(default=0.0, ge=-1.0, le=1.0)

class EmotionLabel(str, Enum):
    """Computed emotion labels from PAD state"""
    HAPPY = "happy"
    SAD = "sad"
    ANGRY = "angry"
    FEARFUL = "fearful"
    SURPRISED = "surprised"
    DISGUSTED = "disgusted"
    CALM = "calm"
    EXCITED = "excited"
    CONTENT = "content"
    ANXIOUS = "anxious"

class PersonalitySnapshot(BaseModel):
    """Complete personality state snapshot for a user"""
    id: int
    user_id: str
    timestamp: datetime
    big_five: BigFiveTraits
    pad_state: PADState
    pad_baseline: PADBaseline
    emotion_label: EmotionLabel
    is_current: bool = True
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class QuirkType(str, Enum):
    SPEECH_PATTERN = "speech_pattern"
    BEHAVIOR = "behavior"  
    PREFERENCE = "preference"

class Quirk(BaseModel):
    """Behavioral quirk that emerges and evolves"""
    id: int
    user_id: str
    quirk_type: QuirkType
    description: str
    strength: float = Field(..., ge=0.0, le=1.0)
    times_expressed: int = 0
    last_expressed: Optional[datetime] = None
    is_active: bool = True
    created_at: datetime

class NeedType(str, Enum):
    SOCIAL = "social"
    INTELLECTUAL = "intellectual"
    CREATIVE = "creative"
    REST = "rest"

class Need(BaseModel):
    """Psychological need that decays and gets satisfied"""
    id: int
    user_id: str
    need_type: NeedType
    current_level: float = Field(..., ge=0.0, le=1.0)
    baseline: float = Field(default=0.5, ge=0.0, le=1.0)
    decay_rate: float = Field(default=0.005, ge=0.0, le=0.1)
    last_updated: datetime
    last_satisfied: Optional[datetime] = None
    satisfaction_count: int = 0

class PersonalityProfile(str, Enum):
    """Predefined personality profiles for initialization"""
    CURIOUS_COMPANION = "curious_companion"
    SUPPORTIVE_FRIEND = "supportive_friend"
    INTELLECTUAL_MENTOR = "intellectual_mentor"
    CREATIVE_COLLABORATOR = "creative_collaborator"

class PersonalityUpdate(BaseModel):
    """Request model for personality updates"""
    pleasure_delta: float = Field(..., ge=-2.0, le=2.0)
    arousal_delta: float = Field(..., ge=-2.0, le=2.0)
    dominance_delta: float = Field(..., ge=-2.0, le=2.0)
    reason: str = Field(..., max_length=500)
```

### `gateway/models/memory.py`

```python
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
import uuid

class MemoryType(str, Enum):
    EPISODIC = "episodic"
    SEMANTIC = "semantic"
    FACTUAL = "factual"
    EMOTIONAL = "emotional"

class Speaker(str, Enum):
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"

class Memory(BaseModel):
    """Base memory model"""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str
    content: str
    memory_type: MemoryType
    timestamp: datetime
    importance: float = Field(..., ge=0.0, le=1.0)
    recency_score: float = Field(default=1.0, ge=0.0, le=1.0)
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

class EpisodicMemory(Memory):
    """Specific conversation memories"""
    memory_type: MemoryType = MemoryType.EPISODIC
    speaker: Speaker
    conversation_id: str
    conversation_turn: int = 0
    emotion_context: str
    pad_context: Dict[str, float] = Field(default_factory=dict)
    
    @validator('conversation_turn')
    def validate_turn(cls, v):
        if v < 0:
            raise ValueError('Conversation turn must be non-negative')
        return v

class SemanticMemory(Memory):
    """Consolidated knowledge memories"""
    memory_type: MemoryType = MemoryType.SEMANTIC
    confidence: float = Field(..., ge=0.0, le=1.0)
    source_episodic_ids: List[str] = Field(default_factory=list)
    consolidation_date: datetime
    
    @validator('source_episodic_ids')
    def validate_sources(cls, v):
        if len(v) == 0:
            raise ValueError('Semantic memory must have source episodic memories')
        return v

class MemorySearchResult(BaseModel):
    """Memory search result with relevance scoring"""
    memory: Memory
    relevance_score: float = Field(..., ge=0.0, le=1.0)
    mmr_score: float = Field(..., ge=0.0, le=1.0)
    retrieval_reason: str

class MemorySearchRequest(BaseModel):
    """Request for memory search"""
    query: str = Field(..., min_length=1, max_length=1000)
    k: int = Field(default=10, ge=1, le=50)
    lambda_param: float = Field(default=0.7, ge=0.0, le=1.0, description="MMR lambda parameter")
    memory_types: Optional[List[MemoryType]] = None
    min_importance: float = Field(default=0.0, ge=0.0, le=1.0)

class MemoryConflict(BaseModel):
    """Detected conflict between memories"""
    id: int
    memory_id_1: str
    memory_id_2: str
    conflict_type: str
    description: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    detected_at: datetime
    resolution_status: str = "pending"
    resolved_at: Optional[datetime] = None
    resolution_note: Optional[str] = None

class MemoryImportanceScoreRequest(BaseModel):
    """Request for importance scoring"""
    content: str
    context: Dict[str, Any] = Field(default_factory=dict)
    speaker: Speaker
    conversation_history: List[str] = Field(default_factory=list, max_items=10)

class MemoryConsolidationResult(BaseModel):
    """Result of memory consolidation process"""
    semantic_memories_created: int
    episodic_memories_processed: int
    consolidation_timestamp: datetime
    summary: str
```

### `gateway/models/interaction.py`

```python
from pydantic import BaseModel, Field, validator
from typing import Dict, List, Optional, Any
from datetime import datetime
from enum import Enum
from .personality import PADState, EmotionLabel
from .memory import Memory

class InteractionType(str, Enum):
    REACTIVE = "reactive"
    PROACTIVE = "proactive"
    SYSTEM = "system"

class ProactiveReason(str, Enum):
    SCHEDULED_CHECK_IN = "scheduled_check_in"
    EMOTIONAL_SUPPORT = "emotional_support"
    CURIOSITY_DRIVEN = "curiosity_driven"
    NEED_FULFILLMENT = "need_fulfillment"
    MEMORY_TRIGGERED = "memory_triggered"

class InnerThought(BaseModel):
    """AI's internal thought process before responding"""
    content: str = Field(..., max_length=2000)
    emotional_assessment: str
    user_state_analysis: str
    response_strategy: str
    proactive_impulse: float = Field(..., ge=0.0, le=1.0)
    timestamp: datetime = Field(default_factory=datetime.now)

class ProactiveContext(BaseModel):
    """Context for proactive conversation evaluation"""
    user_id: str
    time_since_last_interaction: float  # hours
    recent_emotional_pattern: List[EmotionLabel]
    unfulfilled_needs: List[str]
    significant_memories: List[str]  # memory IDs
    current_pad_state: PADState
    personality_snapshot_id: int

class ProactiveScore(BaseModel):
    """Calculated proactive conversation score"""
    total_score: float = Field(..., ge=0.0, le=1.0)
    temporal_factor: float = Field(..., ge=0.0, le=1.0)
    personality_factor: float = Field(..., ge=0.0, le=1.0)
    need_factor: float = Field(..., ge=0.0, le=1.0)
    engagement_factor: float = Field(..., ge=0.0, le=1.0)
    threshold: float = Field(default=0.6, ge=0.0, le=1.0)
    should_initiate: bool = False
    reasoning: str

class Interaction(BaseModel):
    """Complete interaction record"""
    id: int
    user_id: str
    timestamp: datetime
    interaction_type: InteractionType
    user_message: str
    assistant_response: str
    
    # Context
    personality_snapshot_id: int
    pad_before: PADState
    pad_after: PADState
    
    # Proactive metadata
    was_proactive: bool = False
    proactive_score: Optional[float] = None
    proactive_reason: Optional[ProactiveReason] = None
    inner_thought: Optional[InnerThought] = None
    
    # Memory context
    memories_retrieved: int = 0
    memory_ids: List[str] = Field(default_factory=list)
    
    # Performance metrics
    response_latency_ms: int
    tokens_used: int
    model_used: str
    
    @validator('tokens_used')
    def validate_tokens(cls, v):
        if v < 0:
            raise ValueError('Tokens used must be non-negative')
        return v
    
    @validator('response_latency_ms')
    def validate_latency(cls, v):
        if v < 0:
            raise ValueError('Response latency must be non-negative')
        return v

class MessageRequest(BaseModel):
    """Incoming message request"""
    message: str = Field(..., min_length=1, max_length=4000)
    user_id: str
    username: str
    conversation_id: Optional[str] = None
    
class MessageResponse(BaseModel):
    """Outgoing message response"""
    response: str
    interaction_id: int
    pad_state_after: PADState
    emotion_label: EmotionLabel
    memories_used: List[str]
    processing_time_ms: int
    was_proactive: bool = False

class SecurityIncident(BaseModel):
    """Security incident detection"""
    id: int
    user_id: str
    message: str
    threat_type: str
    confidence: float = Field(..., ge=0.0, le=1.0)
    response: str
    timestamp: datetime
    
class ChatSession(BaseModel):
    """Active chat session state"""
    user_id: str
    conversation_id: str
    started_at: datetime
    last_activity: datetime
    message_count: int = 0
    personality_evolution_count: int = 0
```

---

## 🔧 Core Service & Agent Specifications

### 1. Personality Engine (`gateway/services/personality_engine.py`)

**Purpose:** Manages the dynamic personality state for each user, including short-term emotional changes (PAD) and long-term baseline drift.

**Core Methods:**
- **`async get_current_state(user_id: str) -> PersonalitySnapshot`**: Fetches the current, complete personality state for a given user.
- **`async update_pad_state(user_id: str, pleasure_delta: float, arousal_delta: float, dominance_delta: float, reason: str) -> PADState`**: Applies an emotional change to the user's current PAD state, clamping values between -1.0 and 1.0.
- **`async apply_stochastic_drift(user_id: str, time_elapsed_hours: float)`**: A nightly job that slowly drifts the user's PAD *baseline* towards their recent average emotional state. This creates long-term personality evolution without altering the core Big Five traits.
- **`async evolve_quirks(user_id: str)`**: A nightly job that analyzes recent conversations to identify, strengthen, or fade behavioral quirks. New quirks emerge from consistent patterns, existing ones strengthen with use, and unused ones fade away.

**`apply_stochastic_drift` Implementation:**
```python
async def apply_stochastic_drift(user_id: str, time_elapsed_hours: float):
    """
    Apply gradual drift to PAD BASELINE (not Big Five traits).
    """
    current = await self.get_current_state(user_id)
    
    # Calculate drift based on recent emotional patterns
    recent_pad_avg = await self._get_recent_pad_average(user_id, days=7)
    
    # Drift baselines toward recent averages (very slowly)
    drift_rate = 0.01  # Max 1% shift per night
    
    new_baselines = {
        'pleasure': current.pad_baseline.pleasure + (recent_pad_avg.pleasure - current.pad_baseline.pleasure) * drift_rate,
        'arousal': current.pad_baseline.arousal + (recent_pad_avg.arousal - current.pad_baseline.arousal) * drift_rate,
        'dominance': current.pad_baseline.dominance + (recent_pad_avg.dominance - current.pad_baseline.dominance) * drift_rate,
    }
    
    # Update personality state with new baselines (Big Five unchanged)
    await db.execute(
        """INSERT INTO personality_state 
           (user_id, openness, conscientiousness, extraversion, agreeableness, neuroticism,
            pleasure, arousal, dominance, emotion_label, pad_baseline, is_current)
           VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, TRUE)""",
        user_id,
        current.big_five.openness,  # UNCHANGED
        current.big_five.conscientiousness,  # UNCHANGED
        current.big_five.extraversion,  # UNCHANGED
        current.big_five.agreeableness,  # UNCHANGED
        current.big_five.neuroticism,  # UNCHANGED
        new_baselines['pleasure'],
        new_baselines['arousal'],
        new_baselines['dominance'],
        self._calculate_emotion_label(new_baselines),
        json.dumps(new_baselines)
    )
```

**`evolve_quirks` Implementation:**
```python
async def evolve_quirks(user_id: str):
    """
    Called during nightly reflection to evolve quirks based on behavior.
    This IS dynamic - quirks emerge, strengthen, and fade.
    """
    # Get recent interactions
    recent = await db.fetch(
        """SELECT assistant_response FROM interactions 
           WHERE user_id = $1 AND timestamp > NOW() - INTERVAL '7 days'""",
        user_id
    )
    
    # Use Groq to detect behavioral patterns
    prompt = f"""Analyze these recent AI responses for consistent behavioral patterns.

RESPONSES (last 7 days):
{chr(10).join(r['assistant_response'][:200] for r in recent[:20])}

Identify 1-3 quirks/patterns like:
- Speech patterns (uses certain phrases, asks lots of questions)
- Behavioral tendencies (always provides examples, uses analogies)
- Interaction style (playful, serious, uses humor)

Format:
QUIRK: description
STRENGTH: 0.0-1.0 (how consistent/frequent)

List only observed patterns:"""

    response = await self.groq.chat_completion(
        messages=[{"role": "user", "content": prompt}],
        temperature=0.3,
        max_tokens=200
    )
    
    # Parse and update quirks
    new_quirks = self._parse_quirks(response)
    
    for quirk in new_quirks:
        # Check if quirk exists
        existing = await db.fetchrow(
            """SELECT id, strength, times_expressed FROM quirks 
               WHERE user_id = $1 AND description ILIKE $2 AND is_active = TRUE""",
            user_id, f"%{quirk['description'][:30]}%"
        )
        
        if existing:
            # Strengthen existing quirk
            await db.execute(
                """UPDATE quirks 
                   SET strength = LEAST(1.0, strength + 0.1),
                       times_expressed = times_expressed + 1,
                       last_expressed = NOW()
                   WHERE id = $1""",
                existing['id']
            )
        else:
            # Add new emergent quirk
            await db.execute(
                """INSERT INTO quirks 
                   (user_id, quirk_type, description, strength, times_expressed, last_expressed)
                   VALUES ($1, 'behavior', $2, $3, 1, NOW())""",
                user_id, quirk['description'], quirk['strength']
            )
    
    # Fade unused quirks
    await db.execute(
        """UPDATE quirks 
           SET strength = GREATEST(0.0, strength - 0.05)
           WHERE user_id = $1 
           AND last_expressed < NOW() - INTERVAL '14 days'
           AND is_active = TRUE""",
        user_id
    )
    
    # Deactivate quirks that faded to zero
    await db.execute(
        """UPDATE quirks SET is_active = FALSE 
           WHERE user_id = $1 AND strength < 0.1""",
        user_id
    )
```

### 2. Memory Manager (`gateway/services/memory_manager.py`)

**Purpose:** Orchestrates all memory operations, including storage, retrieval, consolidation, and conflict detection for each user.

**Core Methods:**
- **`async store_episodic_memory(...)`**: Stores a conversational memory, calculates its importance using Groq, embeds it using Gemini, and saves it to Qdrant.
- **`async retrieve_relevant_memories(...)`**: Performs a hybrid search in Qdrant using Maximal Marginal Relevance (MMR) to retrieve a diverse yet relevant set of memories for a given query. Filters by `user_id`.
- **`async consolidate_memories_with_personality_evolution(user_id: str)`**: A nightly job that clusters recent episodic memories, summarizes them into new semantic memories, and identifies emerging behavioral patterns (quirks).
- **`async detect_personality_memory_conflicts(...)`**: Compares a new memory against existing memories and personality traits to flag contradictions or inconsistencies.

### 3. Proactive Conversation Manager (`gateway/agents/proactive_manager.py`)

**Purpose:** Decides when and why the AI companion should initiate a conversation with a user.

**Core Methods:**
- **`async check_and_initiate_all_users()`**: The main loop, run every 5 minutes. It iterates through all active users, calculates a proactive score for each, and triggers the delivery pipeline if the score exceeds a threshold.
- **`calculate_proactive_score(...)`**: A multi-factor algorithm that computes a score based on the user's psychological needs, the time of day, their personality (e.g., extraverts are more likely to be contacted), and recent engagement patterns.
- **`async deliver_proactive_message(...)`**: The final step that sends the generated message to the user via the Discord bot, with rate limiting and delivery confirmation.

### 4. Letta Integration (`gateway/services/letta_service.py`)

**Purpose:** Manages the lifecycle of stateful Letta agents, one for each user, and handles the core message processing pipeline.

**Core Methods:**
- **`async get_or_create_agent(...)`**: For a given `user_id`, retrieves the corresponding Letta agent ID or creates a new one if it doesn't exist. The new agent is initialized with a system prompt tailored to the user's companion's personality.
- **`async inject_personality_context(...)`**: Before every message, this method updates the Letta agent's context with the companion's current emotional state (PAD), active quirks, and relevant recent memories.
- **`async process_message(...)`**: The main entry point for handling a user's message. It performs a security check, manages the agent lifecycle, sends the message to Letta, and orchestrates post-processing tasks like memory storage and personality updates.

---

## 🔌 Service Clients & Utilities

### `gateway/services/chutes_client.py`
**Purpose:** A robust client for the primary LLM provider (Chutes.ai) with built-in retry logic and automatic fallback to a secondary model in case of API errors or timeouts.

### `gateway/services/groq_client.py`
**Purpose:** A client for the fast LLM provider (Groq), used for low-latency tasks like importance scoring and security checks. Includes exponential backoff for rate limiting.

```python
import httpx
from typing import Dict, List
import asyncio
import logging

logger = logging.getLogger(__name__)

class GroqClient:
    """Client for Groq API using Llama-4-Maverick"""
    
    def __init__(self, api_key: str, base_url: str = "https://api.groq.com/openai/v1"):
        self.api_key = api_key
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)
        self.model = "llama-4-maverick"
    
    async def chat_completion(
        self,
        messages: List[Dict],
        temperature: float = 0.3,
        max_tokens: int = 50,
        retry_count: int = 0
    ) -> str:
        """Call Groq API with retry logic"""
        
        try:
            response = await self.client.post(
                f"{self.base_url}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": messages,
                    "temperature": temperature,
                    "max_tokens": max_tokens
                }
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
            
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429 and retry_count < 2:
                # Rate limited - exponential backoff
                wait_time = 2 ** retry_count
                logger.warning(f"Groq rate limited, waiting {wait_time}s")
                await asyncio.sleep(wait_time)
                return await self.chat_completion(messages, temperature, max_tokens, retry_count + 1)
            
            elif e.response.status_code >= 500 and retry_count < 1:
                # Server error - retry once
                await asyncio.sleep(1)
                return await self.chat_completion(messages, temperature, max_tokens, retry_count + 1)
            
            else:
                logger.error(f"Groq API error: {e.response.status_code} - {e.response.text}")
                raise
                
        except httpx.TimeoutException:
            if retry_count < 1:
                logger.warning("Groq timeout, retrying...")
                return await self.chat_completion(messages, temperature, max_tokens, retry_count + 1)
            raise
    
    async def close(self):
        await self.client.aclose()
```

### `gateway/services/embedding_client.py`
**Purpose:** A client for the custom Gemini embedding service. It distinguishes between embedding documents for storage (`retrieval_document`) and embedding queries for search (`retrieval_query`) to optimize performance.

### `gateway/utils/importance_scorer.py`
**Purpose:** Uses the Groq client to score the importance of a memory on a scale of 0.0 to 1.0. Includes Redis caching to avoid re-scoring identical memories and a fallback heuristic if the API fails.

### `gateway/security/semantic_injection_detector.py`
**Purpose:** Uses the Groq client to analyze user messages for prompt injection, jailbreaking, and other security threats. Tracks repeat offenders in Redis to escalate responses.

### `gateway/utils/mmr.py`
**Purpose:** Implements the Maximal Marginal Relevance (MMR) algorithm. This is used during memory retrieval to ensure the selected memories are not only relevant to the query but also diverse, preventing redundant information from cluttering the context.

---

## 🌐 API Routers

### `gateway/routers/chat.py`
**Endpoints:**
- `POST /message`: Main endpoint for processing a user's message.
- `POST /proactive/{user_id}`: Triggers a proactive conversation for a specific user.
- `GET /session/{user_id}`: Retrieves the current state of a user's chat session.

### `gateway/routers/memory.py`
**Endpoints:**
- `POST /search`: Searches a user's memories with semantic search and MMR.
- `GET /episodic/{user_id}`: Retrieves recent episodic memories.
- `GET /semantic/{user_id}`: Retrieves consolidated semantic memories.
- `POST /consolidate/{user_id}`: Manually triggers memory consolidation.

### `gateway/routers/personality.py`
**Endpoints:**
- `GET /current/{user_id}`: Gets the full personality snapshot for a user.
- `GET /history/{user_id}`: Retrieves the historical evolution of a user's personality.
- `GET /quirks/{user_id}`: Lists the active behavioral quirks for a user.
- `GET /needs/{user_id}`: Shows the current state of a user's psychological needs.

### `gateway/routers/admin.py`
**Endpoints:**
- `GET /users`: Lists all users in the system.
- `GET /stats`: Provides system-wide statistics.
- `GET /security/incidents`: Shows recent security flags.
- `POST /user/{user_id}/reset`: Resets a user's personality (destructive).

---

## 🔌 Standalone Services

### `embedding_service/main.py`

**Purpose:** A self-contained FastAPI service that wraps the Google Gemini Embedding API. It provides a consistent interface for the rest of the system and implements Redis caching to reduce costs and latency.

```python
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List
import google.generativeai as genai
import redis
import hashlib
import json
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Gemini Embedding Service")

# Initialize Gemini
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))
redis_client = redis.from_url(
    os.getenv("REDIS_URL", "redis://localhost:6379"),
    decode_responses=False
)

CACHE_TTL = 86400 * 7  # 7 days
EMBEDDING_MODEL = "models/gemini-embedding-001"
OUTPUT_DIMENSIONALITY = 1536  # Match existing OpenAI setup

class EmbeddingRequest(BaseModel):
    texts: List[str]
    model: str = EMBEDDING_MODEL
    output_dimensionality: int = OUTPUT_DIMENSIONALITY

class EmbeddingResponse(BaseModel):
    embeddings: List[List[float]]
    cached: List[bool]

def get_cache_key(text: str, model: str, dimensions: int) -> str:
    """Generate cache key for embedding"""
    content = f"{model}:{dimensions}:{text}"
    return f"emb:{hashlib.sha256(content.encode()).hexdigest()}"

@app.post("/embed", response_model=EmbeddingResponse)
async def create_embeddings(request: EmbeddingRequest):
    """Generate embeddings with caching"""
    embeddings = []
    cached_flags = []
    
    texts_to_embed = []
    indices_to_embed = []
    
    # Check cache first
    for idx, text in enumerate(request.texts):
        cache_key = get_cache_key(text, request.model, request.output_dimensionality)
        cached_emb = redis_client.get(cache_key)
        
        if cached_emb:
            embeddings.append(json.loads(cached_emb))
            cached_flags.append(True)
        else:
            embeddings.append(None)
            cached_flags.append(False)
            texts_to_embed.append(text)
            indices_to_embed.append(idx)
    
    # Generate missing embeddings
    if texts_to_embed:
        try:
            # Gemini supports batch embedding
            result = genai.embed_content(
                model=request.model,
                content=texts_to_embed,
                task_type="retrieval_document",  # For storing in vector DB
                output_dimensionality=request.output_dimensionality
            )
            
            generated_embeddings = result['embedding']
            
            for i, embedding in enumerate(generated_embeddings):
                original_idx = indices_to_embed[i]
                embeddings[original_idx] = embedding
                
                # Cache the result
                cache_key = get_cache_key(
                    texts_to_embed[i],
                    request.model,
                    request.output_dimensionality
                )
                redis_client.setex(
                    cache_key,
                    CACHE_TTL,
                    json.dumps(embedding)
                )
                
        except Exception as e:
            logger.error(f"Gemini API error: {str(e)}")
            raise HTTPException(
                status_code=500,
                detail=f"Gemini embedding generation failed: {str(e)}"
            )
    
    return EmbeddingResponse(embeddings=embeddings, cached=cached_flags)

@app.post("/embed_query")
async def embed_query(request: EmbeddingRequest):
    """
    Special endpoint for query embeddings.
    Uses task_type="retrieval_query" for semantic search optimization.
    """
    if len(request.texts) != 1:
        raise HTTPException(
            status_code=400,
            detail="Query embedding only supports single text input"
        )
    
    query_text = request.texts[0]
    
    # Check cache
    cache_key = get_cache_key(
        f"query:{query_text}",
        request.model,
        request.output_dimensionality
    )
    cached_emb = redis_client.get(cache_key)
    
    if cached_emb:
        return EmbeddingResponse(
            embeddings=[json.loads(cached_emb)],
            cached=[True]
        )
    
    try:
        result = genai.embed_content(
            model=request.model,
            content=query_text,
            task_type="retrieval_query",  # Optimized for queries
            output_dimensionality=request.output_dimensionality
        )
        
        embedding = result['embedding']
        
        # Cache
        redis_client.setex(cache_key, CACHE_TTL, json.dumps(embedding))
        
        return EmbeddingResponse(
            embeddings=[embedding],
            cached=[False]
        )
        
    except Exception as e:
        logger.error(f"Gemini query embedding error: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Query embedding failed: {str(e)}"
        )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        redis_client.ping()
        return {
            "status": "healthy",
            "model": EMBEDDING_MODEL,
            "dimensions": OUTPUT_DIMENSIONALITY
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e)
        }
```

---

## ⚙️ Infrastructure & Deployment

### Docker Compose

```yaml
# docker-compose.yml
version: '3.9'

services:
  postgres:
    image: pgvector/pgvector:pg16
    container_name: companion_postgres
    environment:
      POSTGRES_DB: companion
      POSTGRES_USER: companion_user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
      PGDATA: /var/lib/postgresql/data/pgdata
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./migrations:/docker-entrypoint-initdb.d:ro
    ports:
      - "127.0.0.1:5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U companion_user -d companion"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - companion_network

  qdrant:
    image: qdrant/qdrant:v1.12.1
    container_name: companion_qdrant
    environment:
      QDRANT__SERVICE__GRPC_PORT: 6334
    volumes:
      - qdrant_data:/qdrant/storage
    ports:
      - "127.0.0.1:6333:6333"
      - "127.0.0.1:6334:6334"
    healthcheck:
      test: ["CMD", "wget", "--spider", "-q", "http://localhost:6333/health"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - companion_network

  redis:
    image: redis:7.4.7-alpine
    container_name: companion_redis
    command: redis-server --appendonly yes --maxmemory 2gb --maxmemory-policy allkeys-lru
    volumes:
      - redis_data:/data
    ports:
      - "127.0.0.1:6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      timeout: 5s
      retries: 5
    restart: unless-stopped
    networks:
      - companion_network

  letta:
    image: letta/letta:v0.6.8
    container_name: companion_letta
    environment:
      DATABASE_URL: postgresql://companion_user:${POSTGRES_PASSWORD}@postgres:5432/companion
    depends_on:
      postgres:
        condition: service_healthy
    ports:
      - "127.0.0.1:8283:8283"
    volumes:
      - letta_data:/root/.letta
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8283/health"]
      interval: 30s
      timeout: 10s
      retries: 3
    restart: unless-stopped
    networks:
      - companion_network

  embedding_service:
    build:
      context: ./embedding_service
      dockerfile: Dockerfile
    container_name: companion_embeddings
    environment:
      GEMINI_API_KEY: ${GEMINI_API_KEY}
      REDIS_URL: redis://redis:6379
    depends_on:
      redis:
        condition: service_healthy
    ports:
      - "127.0.0.1:8001:8001"
    restart: unless-stopped
    networks:
      - companion_network

  gateway:
    build:
      context: ./gateway
      dockerfile: Dockerfile
    container_name: companion_gateway
    environment:
      DATABASE_URL: postgresql+asyncpg://companion_user:${POSTGRES_PASSWORD}@postgres:5432/companion
      LETTA_BASE_URL: http://letta:8283
      QDRANT_URL: http://qdrant:6333
      REDIS_URL: redis://redis:6379
      EMBEDDING_SERVICE_URL: http://embedding_service:8001
      CHUTES_API_KEY: ${CHUTES_API_KEY}
      GROQ_API_KEY: ${GROQ_API_KEY}
      GEMINI_API_KEY: ${GEMINI_API_KEY}
    depends_on:
      postgres:
        condition: service_healthy
      qdrant:
        condition: service_healthy
      redis:
        condition: service_healthy
      letta:
        condition: service_healthy
      embedding_service:
        condition: service_started
    ports:
      - "127.0.0.1:8000:8000"
    volumes:
      - ./gateway:/app
    restart: unless-stopped
    networks:
      - companion_network

  discord_bot:
    build:
      context: ./discord_bot
      dockerfile: Dockerfile
    container_name: companion_discord
    environment:
      DISCORD_TOKEN: ${DISCORD_TOKEN}
      GATEWAY_URL: http://gateway:8000
      DISCORD_GUILD_ID: ${DISCORD_GUILD_ID}
    depends_on:
      - gateway
    restart: unless-stopped
    networks:
      - companion_network

  caddy:
    image: caddy:2.10.2-alpine
    container_name: companion_caddy
    ports:
      - "80:80"
      - "443:443"
      - "443:443/udp"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
      - caddy_config:/config
    restart: unless-stopped
    networks:
      - companion_network

volumes:
  postgres_data:
  qdrant_data:
  redis_data:
  letta_data:
  caddy_data:
  caddy_config:

networks:
  companion_network:
    driver: bridge
```

### Scheduler Setup (`gateway/utils/scheduler.py`)

**Purpose:** Manages all recurring background jobs using APScheduler.

**Jobs to Schedule:**
1.  **Nightly Reflection (All Users):**
    -   **Function:** `reflection_engine.run_nightly_reflection()`
    -   **Trigger:** `CronTrigger(hour=3, minute=0)`
    -   **Purpose:** Consolidates memories, evolves personality baselines and quirks.
2.  **Needs Decay (All Users):**
    -   **Function:** `reflection_engine.update_needs_decay_all_users()`
    -   **Trigger:** `IntervalTrigger(hours=1)`
    -   **Purpose:** Gradually increases psychological needs over time.
3.  **Memory Recency Update (All Users):**
    -   **Function:** `memory_manager.update_recency_scores_all_users()`
    -   **Trigger:** `CronTrigger(hour=4, minute=0)`
    -   **Purpose:** Decays the recency score of memories, making older ones less likely to be retrieved.
4.  **Proactive Conversation Check (All Users):**
    -   **Function:** `proactive_manager.check_and_initiate_all_users()`
    -   **Trigger:** `IntervalTrigger(minutes=5)`
    -   **Purpose:** The main loop for the proactive conversation system.
5.  **Conflict Detection (All Users):**
    -   **Function:** `memory_manager.detect_conflicts_all_users()`
    -   **Trigger:** `CronTrigger(hour=2, minute=0)`
    -   **Purpose:** Scans for inconsistencies between memories.

---

## 🐛 Critical Implementation Details & Error Handling

### Service Initialization Order
To prevent circular dependencies, services must be initialized in a specific order within `gateway/main.py`:
1.  **Phase 1 (Infrastructure):** Database, Redis, Qdrant, and API clients (Groq, Chutes, Embedding).
2.  **Phase 2 (Core Business Logic):** Personality Engine, Importance Scorer, Memory Manager. These depend only on Phase 1.
3.  **Phase 3 (Integration Services):** Letta Service, Proactive Manager. These depend on Phase 1 & 2.
4.  **Phase 4 (Background Services):** Scheduler and Health Monitor. These depend on all previous phases.

### Error Recovery & Degraded Mode
The system is designed to be resilient. If a critical service fails, it enters a degraded mode:
-   **Letta Failure:** Fallback to direct Chutes API calls (less contextual).
-   **Groq Failure:** Fallback to heuristic-based importance scoring (less accurate).
-   **Qdrant Failure:** Fallback to PostgreSQL full-text search for memories (less semantic).
-   **Redis Failure:** Fallback to direct database queries (slower).
-   **Database Failure:** Read-only mode using cached data (no learning).

### Configuration Validation
The `gateway/config.py` file uses Pydantic's `root_validator` to perform cross-parameter validation, ensuring that settings like rate limits, personality drift rates, and security thresholds are logically consistent with each other, preventing misconfiguration errors at startup.

---

## 🚀 Deployment & Operations

This guide includes complete, executable scripts for automating the entire lifecycle of the application, addressing the limitations of LLMs in performing real-world DevOps tasks.

-   **`deploy_companion_system.sh`**: A comprehensive script that checks requirements, sets up the `.env` file, initializes and migrates the database, sets up Qdrant, and starts all services with health validation.
-   **`setup_domain.sh`**: A guided script to configure a public domain, update the Caddyfile, configure the firewall, and automatically provision SSL certificates with Let's Encrypt.
-   **`rotate_api_keys.sh`**: A secure procedure for rotating all external API keys, including backup, validation of new keys, and a rollback mechanism.
-   **`monitor_system.sh`**: A detailed monitoring script that checks Docker services, API endpoints, database connectivity, resource usage, and error rates, with options for alerting and auto-recovery.
-   **`backup_system.sh`**: An automated backup script that archives the PostgreSQL database, Qdrant vector data, configuration files, and logs, with a corresponding restore procedure for disaster recovery.